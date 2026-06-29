import json

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Callable, Awaitable

from entitlements import action_cost
from credits_service import InsufficientCredits
from redis_database import session_manager

ai_router = APIRouter()


async def _resolve_user_id(request: Request) -> Optional[str]:
    """Return the authenticated user_id from the session cookie, or None."""
    sid = request.cookies.get("session_id")
    if not sid:
        return None
    session = await session_manager.get_session(sid)
    return session["user_id"] if session else None


def _client_ip(request: Request) -> str:
    """Best-effort client IP (honours X-Forwarded-For behind a proxy)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class QuotaContext:
    """Result of acquiring AI quota for a request.

    `user_id` is the authenticated user (or None for anonymous). `refund()` reverses
    the reservation — a credit refund for users, a usage decrement for anonymous IPs —
    and is called when the AI call produces no output.
    """
    def __init__(self, user_id: Optional[str], refund: Optional[Callable[[], Awaitable[None]]] = None):
        self.user_id = user_id
        self._refund = refund

    async def refund(self) -> None:
        if self._refund:
            try:
                await self._refund()
            except Exception:
                pass


async def acquire_ai_quota(request: Request, action: str) -> QuotaContext:
    """Reserve quota for an AI action; raise HTTPException(402) if exhausted.

    Authenticated → spend credits (base then boost). Anonymous → consume one of the
    per-IP lifetime allowance. If neither service is configured, allow through.
    """
    credits = getattr(request.app.state, "credits_service", None)
    anon = getattr(request.app.state, "anon_usage", None)
    user_id = await _resolve_user_id(request)

    if user_id and credits:
        try:
            res = await credits.spend(user_id, action, action_cost(action), ref_type=action)
        except InsufficientCredits:
            raise HTTPException(status_code=402, detail={"reason": "insufficient_credits", "action": action})

        async def _refund():
            await credits.refund(user_id, res, reason=f"{action}_refund")

        return QuotaContext(user_id, _refund)

    if not user_id and anon:
        ip = _client_ip(request)
        allowed, count, limit = await anon.try_consume(ip)
        if not allowed:
            raise HTTPException(
                status_code=402,
                detail={"reason": "anon_limit", "action": action, "used": count, "limit": limit},
            )

        async def _refund():
            await anon.release(ip)

        return QuotaContext(None, _refund)

    return QuotaContext(user_id)


# ── Request / Response Models ──────────────────────────

class GenerateReportRequest(BaseModel):
    date: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ScreenerRequest(BaseModel):
    query: str
    limit: int = 20


# ── Report Endpoints ───────────────────────────────────

@ai_router.get("/reports")
async def list_reports(request: Request, limit: int = 30):
    report_repo = getattr(request.app.state, "ai_report_repo", None)
    if not report_repo:
        return {"reports": []}
    reports = await report_repo.list_reports(limit=limit)
    for r in reports:
        if "created_at" in r:
            r["created_at"] = r["created_at"].isoformat()
    return {"reports": reports}


@ai_router.get("/reports/{date}")
async def get_report(date: str, request: Request):
    report_repo = getattr(request.app.state, "ai_report_repo", None)
    if not report_repo:
        raise HTTPException(status_code=503, detail="AI reports not configured")
    report = await report_repo.get_report(date)
    if not report:
        raise HTTPException(status_code=404, detail=f"No report found for {date}")
    if "created_at" in report:
        report["created_at"] = report["created_at"].isoformat()
    return report


@ai_router.post("/reports/generate")
async def generate_report(
    body: GenerateReportRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    report_gen = getattr(request.app.state, "report_generator", None)
    if not report_gen:
        raise HTTPException(status_code=503, detail="AI report engine not configured (missing DEEPSEEK_API_KEY)")
    background_tasks.add_task(report_gen.generate_daily_report, body.date)
    return {"status": "started", "message": "Report generation triggered in background"}


@ai_router.delete("/reports/{date}")
async def delete_report(date: str, request: Request):
    report_repo = getattr(request.app.state, "ai_report_repo", None)
    if not report_repo:
        raise HTTPException(status_code=503, detail="AI reports not configured")
    deleted = await report_repo.delete_report(date)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No report found for {date}")
    return {"status": "deleted", "date": date}


# ── Chat Endpoints ────────────────────────────────────

@ai_router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    chat_agent = getattr(request.app.state, "chat_agent", None)
    if not chat_agent:
        raise HTTPException(status_code=503, detail="AI chat not configured (missing DEEPSEEK_API_KEY)")

    # Reserve quota up front (credits for users, per-IP allowance for anon).
    # Anon users are NOT refunded on error — the limit is a hard gate, not a credit charge.
    quota = await acquire_ai_quota(request, "chat")

    activity = getattr(request.app.state, "activity_service", None)
    if activity:
        await activity.log("chat_message", user_id=quota.user_id,
                           props={"chars": len(body.message)})

    async def event_stream():
        produced = False
        try:
            async for event in chat_agent.handle_message(
                message=body.message,
                conversation_id=body.conversation_id,
                user_id=quota.user_id or "anonymous",
            ):
                etype = event.get("type")
                if (etype == "text" and event.get("content")) or etype == "tool_result":
                    produced = True
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        finally:
            # Only refund authenticated users (credits). Anonymous IPs are never
            # refunded — failed requests still count against their lifetime limit.
            if not produced and quota.user_id:
                await quota.refund()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@ai_router.get("/chat/conversations")
async def list_conversations(request: Request, user_id: str = "anonymous", limit: int = 20):
    conv_repo = getattr(request.app.state, "ai_conversation_repo", None)
    if not conv_repo:
        return {"conversations": []}
    convs = await conv_repo.list_conversations(user_id=user_id, limit=limit)
    for c in convs:
        if "updated_at" in c:
            c["updated_at"] = c["updated_at"].isoformat()
    return {"conversations": convs}


@ai_router.get("/chat/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    conv_repo = getattr(request.app.state, "ai_conversation_repo", None)
    if not conv_repo:
        raise HTTPException(status_code=503, detail="Chat not configured")
    conv = await conv_repo.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@ai_router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request):
    conv_repo = getattr(request.app.state, "ai_conversation_repo", None)
    if not conv_repo:
        raise HTTPException(status_code=503, detail="Chat not configured")
    deleted = await conv_repo.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


# ── Screener Endpoints ────────────────────────────────

@ai_router.post("/screener")
async def screen_stocks(body: ScreenerRequest, request: Request):
    screener = getattr(request.app.state, "nl_screener", None)
    if not screener:
        raise HTTPException(status_code=503, detail="AI screener not configured")

    # Reserve quota up front. Anon IPs are not refunded on failure (hard gate).
    quota = await acquire_ai_quota(request, "screener")

    try:
        result = await screener.screen(query=body.query, limit=min(body.limit, 50))
    except Exception as e:
        if quota.user_id:
            await quota.refund()
        raise HTTPException(status_code=500, detail=str(e))

    if "error" in result:
        if quota.user_id:
            await quota.refund()
        raise HTTPException(status_code=400, detail=result["error"])

    # Log the screener query text per user (Phase 7 §9.5 — explicit requirement).
    activity = getattr(request.app.state, "activity_service", None)
    if activity:
        await activity.log("screener_query", user_id=quota.user_id, props={
            "text": body.query,
            "result_count": result.get("total_results"),
        })
    return result


# ── Health / Usage ─────────────────────────────────────

@ai_router.get("/usage")
async def get_ai_usage(request: Request):
    ai_client = getattr(request.app.state, "ai_client", None)
    if not ai_client:
        return {"status": "not configured"}
    return ai_client.get_usage_stats()

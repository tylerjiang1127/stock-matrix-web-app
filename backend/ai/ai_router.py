import json

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

ai_router = APIRouter()


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

    async def event_stream():
        try:
            async for event in chat_agent.handle_message(
                message=body.message,
                conversation_id=body.conversation_id,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

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
    result = await screener.screen(query=body.query, limit=min(body.limit, 50))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Health / Usage ─────────────────────────────────────

@ai_router.get("/usage")
async def get_ai_usage(request: Request):
    ai_client = getattr(request.app.state, "ai_client", None)
    if not ai_client:
        return {"status": "not configured"}
    return ai_client.get_usage_stats()

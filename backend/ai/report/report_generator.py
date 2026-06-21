import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

from ai.report.data_gatherer import MarketDataGatherer
from ai.report.report_prompts import (
    REPORT_SYSTEM_PROMPT,
    REPORT_SYSTEM_PROMPT_ZH,
    build_report_user_prompt,
)

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
MARKET_CLOSE_HOUR = 16  # 4:00 PM ET


class ReportGenerator:
    """Orchestrates data gathering → LLM report generation → storage."""

    def __init__(self, ai_client, pg_repo, stock_metadata_repo, report_repo):
        self.ai_client = ai_client
        self.gatherer = MarketDataGatherer(pg_repo, stock_metadata_repo)
        self.report_repo = report_repo

    @staticmethod
    def _last_completed_trading_date() -> str:
        """Return the most recent date whose market session has closed (ET)."""
        now_et = datetime.now(ET)
        if now_et.hour >= MARKET_CLOSE_HOUR and now_et.weekday() < 5:
            # Market closed today and it's a weekday — use today
            return now_et.strftime("%Y-%m-%d")
        # Otherwise walk back to the most recent weekday that has closed
        d = now_et.date()
        if now_et.hour < MARKET_CLOSE_HOUR or now_et.weekday() >= 5:
            d -= timedelta(days=1)
        while d.weekday() >= 5:  # skip weekends
            d -= timedelta(days=1)
        return d.strftime("%Y-%m-%d")

    async def generate_daily_report(self, date: str = None) -> Optional[Dict[str, Any]]:
        """Generate and store EN + ZH daily macro reports concurrently."""
        if date is None:
            date = self._last_completed_trading_date()

        try:
            raw_data = await self.gatherer.gather_all()
            raw_data["date"] = date

            if not raw_data.get("market_breadth"):
                logger.warning("No market breadth data available, skipping report")
                return None

            user_prompt = build_report_user_prompt(raw_data)
            msgs_en = [
                {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
            msgs_zh = [
                {"role": "system", "content": REPORT_SYSTEM_PROMPT_ZH},
                {"role": "user", "content": user_prompt},
            ]

            results = await asyncio.gather(
                self.ai_client.chat_completion(messages=msgs_en, temperature=0.5, max_tokens=8192),
                self.ai_client.chat_completion(messages=msgs_zh, temperature=0.5, max_tokens=8192),
                return_exceptions=True,
            )

            en_ok = not isinstance(results[0], Exception)
            zh_ok = not isinstance(results[1], Exception)

            if not en_ok:
                logger.error("English report generation failed: %s", results[0])
                return None

            en_content = self._strip_fences(results[0]["choices"][0]["message"]["content"])
            zh_content = self._strip_fences(results[1]["choices"][0]["message"]["content"]) if zh_ok else None

            if not zh_ok:
                logger.warning("Chinese report generation failed: %s", results[1])

            mood = self._detect_mood(en_content)

            en_usage = results[0].get("usage", {})
            zh_usage = results[1].get("usage", {}) if zh_ok else {}
            total_in = en_usage.get("prompt_tokens", 0) + zh_usage.get("prompt_tokens", 0)
            total_out = en_usage.get("completion_tokens", 0) + zh_usage.get("completion_tokens", 0)

            report = {
                "date": date,
                "report_type": "daily",
                "sections": {
                    "report_markdown": en_content,
                    "report_markdown_zh": zh_content,
                    "market_mood": mood,
                },
                "raw_data": self._sanitize_raw_data(raw_data),
                "model": self.ai_client.model,
                "tokens_used": {"input": total_in, "output": total_out},
            }

            await self.report_repo.save_report(report)
            logger.info("Daily macro report generated for %s (EN + ZH)", date)
            print(f"[AI Report] Generated for {date} — "
                  f"EN {en_usage.get('completion_tokens', '?')} tokens, "
                  f"ZH {zh_usage.get('completion_tokens', '?')} tokens")
            return report

        except Exception as e:
            logger.error("Report generation failed: %s", e)
            print(f"[AI Report] ERROR: {e}")
            return None

    @staticmethod
    def _strip_fences(text: str) -> str:
        text = text.strip()
        if text.startswith("```markdown"):
            text = text[len("```markdown"):].strip()
        elif text.startswith("```"):
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
        return text

    @staticmethod
    def _detect_mood(markdown: str) -> str:
        lower = markdown[:2000].lower()
        bull_words = ["bullish", "rally", "new high", "risk-on", "strong momentum", "breakout"]
        bear_words = ["bearish", "sell-off", "risk-off", "breakdown", "panic", "crash"]
        bull = sum(1 for w in bull_words if w in lower)
        bear = sum(1 for w in bear_words if w in lower)
        if bull > bear + 1:
            return "bullish"
        if bear > bull + 1:
            return "bearish"
        return "neutral"

    @staticmethod
    def _sanitize_raw_data(raw_data: Dict) -> Dict:
        """Convert any non-serializable values in raw data for MongoDB storage."""
        import math
        from decimal import Decimal

        def clean(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, float):
                if math.isnan(obj) or math.isinf(obj):
                    return None
                return obj
            if isinstance(obj, dict):
                return {k: clean(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [clean(i) for i in obj]
            return obj

        return clean(raw_data)

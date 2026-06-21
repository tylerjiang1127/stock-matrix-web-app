"""
Chat agent that orchestrates tool-calling conversations with the Deepseek LLM.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator

from ai.chat.chat_prompts import CHAT_SYSTEM_PROMPT
from ai.tools.stock_data_tools import TOOLS

logger = logging.getLogger(__name__)


class ChatAgent:

    def __init__(self, ai_client, tool_registry, conversation_repo):
        self.ai_client = ai_client
        self.tool_registry = tool_registry
        self.conversation_repo = conversation_repo

    async def handle_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: str = "anonymous",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        existing = await self.conversation_repo.get_conversation(conversation_id)
        if existing:
            messages = existing["messages"]
        else:
            messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

        messages.append({"role": "user", "content": message})

        yield {"type": "conversation_id", "conversation_id": conversation_id}

        async for event in self.ai_client.stream_tool_loop(
            messages=messages,
            tools=TOOLS,
            tool_registry=self.tool_registry.as_dict(),
            max_rounds=5,
        ):
            yield event

            if event["type"] == "text":
                messages.append({"role": "assistant", "content": event["content"]})

        storable = self._strip_for_storage(messages)
        await self.conversation_repo.save_conversation(conversation_id, user_id, storable)

    @staticmethod
    def _strip_for_storage(messages: List[Dict]) -> List[Dict]:
        """Keep only role/content for storage to limit document size."""
        stripped = []
        for m in messages:
            entry = {"role": m["role"]}
            if "content" in m and m["content"]:
                content = m["content"]
                if isinstance(content, str) and len(content) > 10000:
                    content = content[:10000] + "...(truncated)"
                entry["content"] = content
            if m.get("tool_calls"):
                entry["tool_calls"] = [
                    {"function": {"name": tc["function"]["name"]}}
                    for tc in m["tool_calls"]
                ]
            if m.get("tool_call_id"):
                entry["tool_call_id"] = m["tool_call_id"]
            stripped.append(entry)
        return stripped

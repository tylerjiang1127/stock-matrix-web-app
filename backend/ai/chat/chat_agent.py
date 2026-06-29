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
            # Filter out broken tool-call messages that may have been stored
            # before _strip_for_storage was fixed. Sending role=tool or
            # tool_call-only assistant messages with missing IDs causes 400.
            messages = [
                m for m in existing["messages"]
                if m.get("role") != "tool"
                and not (not m.get("content") and m.get("tool_calls"))
            ]
        else:
            messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

        messages.append({"role": "user", "content": message})

        yield {"type": "conversation_id", "conversation_id": conversation_id}

        # Each "text" event is the cumulative response so far (not a delta).
        # Only the last one has the complete text — appending on every chunk
        # would store dozens of duplicate partial messages in MongoDB.
        last_assistant_text = ""

        async for event in self.ai_client.stream_tool_loop(
            messages=messages,
            tools=TOOLS,
            tool_registry=self.tool_registry.as_dict(),
            max_rounds=5,
        ):
            yield event

            if event["type"] == "text":
                last_assistant_text = event["content"]

        if last_assistant_text:
            messages.append({"role": "assistant", "content": last_assistant_text})

        storable = self._strip_for_storage(messages)
        first_user = next((m.get("content", "") for m in storable if m.get("role") == "user"), "")
        title = (first_user[:40] + "…") if len(first_user) > 40 else first_user or None
        await self.conversation_repo.save_conversation(conversation_id, user_id, storable, title=title)

    @staticmethod
    def _strip_for_storage(messages: List[Dict]) -> List[Dict]:
        """Reduce messages to text-only role/content for storage.

        Tool call intermediate messages (role=tool, and assistant messages
        that only contain tool_calls with no text) are dropped entirely.
        Replaying them across turns breaks Deepseek's tool_call_id pairing
        because stored tool_call IDs get stripped, causing 400 errors on
        the next request.
        """
        stripped = []
        for m in messages:
            role = m["role"]
            content = m.get("content") or ""

            # Drop tool-result messages and tool-call-only assistant turns.
            if role == "tool":
                continue
            if not content and m.get("tool_calls"):
                continue

            entry: Dict = {"role": role}
            if isinstance(content, str):
                if len(content) > 10000:
                    content = content[:10000] + "...(truncated)"
                if content:
                    entry["content"] = content

            # Collapse consecutive assistant messages (streaming-chunk duplicates).
            # Keep the entry with the most content.
            if stripped and stripped[-1].get("role") == "assistant" == role:
                prev_len = len(stripped[-1].get("content", ""))
                if len(entry.get("content", "")) > prev_len:
                    stripped[-1] = entry
            else:
                stripped.append(entry)
        return stripped

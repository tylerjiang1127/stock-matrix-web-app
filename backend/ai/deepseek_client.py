import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator, Callable

import httpx

logger = logging.getLogger(__name__)


class DeepseekClient:

    BASE_URL = "https://api.deepseek.com/v1"

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = None,
        max_retries: int = 3,
        timeout: float = 120.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.max_retries = max_retries
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def close(self):
        await self._client.aclose()

    # ── Core completion ────────────────────────────────────

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ):
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
        if response_format:
            payload["response_format"] = response_format

        if stream:
            return self._stream_completion(payload)
        return await self._request_with_retry(payload)

    async def _request_with_retry(self, payload: Dict) -> Dict:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._client.post("/chat/completions", json=payload)
                if resp.status_code == 429 or resp.status_code >= 500:
                    wait = min(2 ** attempt * 2, 30)
                    logger.warning(
                        "Deepseek %s (attempt %d/%d), retrying in %ds",
                        resp.status_code, attempt + 1, self.max_retries, wait,
                    )
                    await asyncio.sleep(wait)
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    continue
                resp.raise_for_status()
                data = resp.json()
                self._track_usage(data)
                return data
            except httpx.TimeoutException:
                last_error = "Request timed out"
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Deepseek API error: {e.response.status_code} {e.response.text[:300]}") from e
        raise RuntimeError(f"Deepseek API failed after {self.max_retries} attempts: {last_error}")

    async def _stream_completion(self, payload: Dict) -> AsyncGenerator[Dict, None]:
        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    return
                try:
                    chunk = json.loads(data_str)
                    self._track_usage(chunk)
                    yield chunk
                except json.JSONDecodeError:
                    continue

    # ── Tool-calling loop ──────────────────────────────────

    async def execute_tool_loop(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict],
        tool_registry: Dict[str, Callable],
        max_rounds: int = 5,
    ) -> Dict:
        """Run multi-turn tool calling until the model produces a final text response."""
        conversation = list(messages)

        for _ in range(max_rounds):
            response = await self.chat_completion(
                messages=conversation,
                tools=tools,
                temperature=0.3,
            )
            choice = response["choices"][0]
            message = choice["message"]
            conversation.append(message)

            if not message.get("tool_calls"):
                return response

            for tool_call in message["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                try:
                    fn_args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    fn_args = {}

                handler = tool_registry.get(fn_name)
                if handler is None:
                    result = json.dumps({"error": f"Unknown tool: {fn_name}"})
                else:
                    try:
                        result_data = await handler(**fn_args)
                        result = json.dumps(result_data, default=str)
                    except Exception as e:
                        logger.error("Tool %s failed: %s", fn_name, e)
                        result = json.dumps({"error": str(e)})

                conversation.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result,
                })

        final = await self.chat_completion(messages=conversation, temperature=0.3)
        return final

    # ── Streaming tool loop (for chat) ─────────────────────

    async def stream_tool_loop(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict],
        tool_registry: Dict[str, Callable],
        max_rounds: int = 5,
    ) -> AsyncGenerator[Dict, None]:
        """Like execute_tool_loop but yields SSE-style events for streaming."""
        conversation = list(messages)

        for round_num in range(max_rounds):
            response = await self.chat_completion(
                messages=conversation, tools=tools, temperature=0.3,
            )
            choice = response["choices"][0]
            message = choice["message"]
            conversation.append(message)

            if not message.get("tool_calls"):
                content = message.get("content", "")
                yield {"type": "text", "content": content}
                yield {"type": "done"}
                return

            for tool_call in message["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                try:
                    fn_args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    fn_args = {}

                yield {"type": "tool_call", "name": fn_name, "arguments": fn_args}

                handler = tool_registry.get(fn_name)
                if handler is None:
                    result_data = {"error": f"Unknown tool: {fn_name}"}
                else:
                    try:
                        result_data = await handler(**fn_args)
                    except Exception as e:
                        result_data = {"error": str(e)}

                result_str = json.dumps(result_data, default=str)
                yield {"type": "tool_result", "name": fn_name, "data": result_data}

                conversation.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result_str,
                })

        final = await self.chat_completion(messages=conversation, temperature=0.3)
        content = final["choices"][0]["message"].get("content", "")
        yield {"type": "text", "content": content}
        yield {"type": "done"}

    # ── Usage tracking ─────────────────────────────────────

    def _track_usage(self, response: Dict):
        usage = response.get("usage")
        if usage:
            self.total_input_tokens += usage.get("prompt_tokens", 0)
            self.total_output_tokens += usage.get("completion_tokens", 0)

    def get_usage_stats(self) -> Dict[str, Any]:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": round(
                self.total_input_tokens * 0.27 / 1_000_000
                + self.total_output_tokens * 1.10 / 1_000_000,
                4,
            ),
        }

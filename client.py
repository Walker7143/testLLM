from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum

import httpx


class WireAPI(str, Enum):
    CHAT_COMPLETIONS = "chat_completions"
    RESPONSES = "responses"


@dataclass
class ChatResponse:
    content: str
    model: str
    finish_reason: str | None = None
    logprobs: dict | None = None
    response_headers: dict[str, str] = field(default_factory=dict)
    raw_response: dict = field(default_factory=dict)


class APIError(Exception):
    def __init__(self, status_code: int, body: str, url: str):
        self.status_code = status_code
        self.body = body
        self.url = url
        preview = str(body)[:200] if body else "[empty response]"
        if "<html" in str(body).lower() or "<!doctype" in str(body).lower():
            preview = "[HTML page returned]"
        super().__init__(f"API error {status_code} at {url}: {preview}")


class LLMClient:
    """Async client for OpenAI-compatible APIs, supporting both
    Chat Completions (/v1/chat/completions) and Responses API (/v1/responses)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        wire_api: WireAPI | None = None,
    ):
        self.base_url = self._normalize_url(base_url)
        self.model = model
        self._wire_api = wire_api  # None = auto-detect on first call
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    @staticmethod
    def _normalize_url(base_url: str) -> str:
        url = base_url.rstrip("/")
        if not url.endswith("/v1"):
            try:
                resp = httpx.get(
                    f"{url}/v1/models",
                    headers={"Authorization": "Bearer test"},
                    timeout=5.0,
                )
                if resp.status_code in (200, 401, 403):
                    return f"{url}/v1"
            except Exception:
                pass
        return url

    async def _detect_wire_api(self) -> WireAPI:
        """Auto-detect: try Chat Completions first (simpler), then Responses API."""
        # Try Chat Completions first - more widely supported, simpler format
        try:
            resp = await self._client.post(
                "/chat/completions",
                json={"model": self.model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 3},
            )
            ct = resp.headers.get("content-type", "")
            if "json" in ct and resp.status_code < 400:
                data = resp.json()
                if isinstance(data, dict) and "choices" in data:
                    return WireAPI.CHAT_COMPLETIONS
        except Exception:
            pass

        # Try Responses API
        try:
            resp = await self._client.post(
                "/responses",
                json={"model": self.model, "input": "hi", "max_output_tokens": 3},
            )
            ct = resp.headers.get("content-type", "")
            if "json" in ct and resp.status_code < 400:
                data = resp.json()
                if isinstance(data, dict) and "output" in data:
                    return WireAPI.RESPONSES
        except Exception:
            pass

        # Default to chat completions
        return WireAPI.CHAT_COMPLETIONS

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        logprobs: bool = False,
        top_logprobs: int | None = None,
        **kwargs,
    ) -> ChatResponse:
        if self._wire_api is None:
            self._wire_api = await self._detect_wire_api()

        if self._wire_api == WireAPI.RESPONSES:
            return await self._chat_responses(messages, max_tokens, **kwargs)
        else:
            return await self._chat_completions(
                messages, temperature, max_tokens, logprobs, top_logprobs, **kwargs
            )

    async def _chat_completions(
        self, messages, temperature, max_tokens, logprobs, top_logprobs, **kwargs
    ) -> ChatResponse:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if logprobs:
            payload["logprobs"] = True
            if top_logprobs is not None:
                payload["top_logprobs"] = top_logprobs
        payload.update(kwargs)

        resp = await self._client.post("/chat/completions", json=payload)
        return self._parse_chat_completions(resp)

    async def _chat_responses(self, messages, max_tokens, **kwargs) -> ChatResponse:
        input_text = self._messages_to_input(messages)
        payload: dict = {
            "model": self.model,
            "input": input_text,
        }
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        payload.update(kwargs)

        resp = await self._client.post("/responses", json=payload)
        return self._parse_responses_api(resp)

    @staticmethod
    def _messages_to_input(messages: list[dict]) -> str | list[dict]:
        if len(messages) == 1 and messages[0].get("role") == "user":
            content = messages[0].get("content", "")
            if isinstance(content, str):
                return content
        items = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            items.append({"role": role, "content": content})
        return items

    @staticmethod
    def _parse_chat_completions(resp: httpx.Response) -> ChatResponse:
        body = resp.text
        ct = resp.headers.get("content-type", "")
        if "json" not in ct:
            raise APIError(resp.status_code, body, str(resp.url))
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise APIError(resp.status_code, f"Unexpected response type: {type(data)}", str(resp.url))
        if "error" in data:
            raise APIError(resp.status_code, str(data["error"]), str(resp.url))

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        return ChatResponse(
            content=message.get("content", ""),
            model=data.get("model", ""),
            finish_reason=choice.get("finish_reason"),
            logprobs=choice.get("logprobs"),
            response_headers={k: v for k, v in resp.headers.items()},
            raw_response=data,
        )

    @staticmethod
    def _parse_responses_api(resp: httpx.Response) -> ChatResponse:
        body = resp.text
        ct = resp.headers.get("content-type", "")
        resp.raise_for_status()

        # Handle SSE (text/event-stream) responses — extract final JSON
        if "event-stream" in ct:
            data = None
            for line in body.splitlines():
                line = line.strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        data = json.loads(line[6:])
                    except json.JSONDecodeError:
                        pass
            # Fallback: body might be raw JSON despite content-type
            if data is None:
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    raise APIError(resp.status_code, f"No valid JSON in SSE stream: {body[:200]}", str(resp.url))
        elif "json" in ct:
            data = resp.json()
        else:
            raise APIError(resp.status_code, body, str(resp.url))
        if not isinstance(data, dict):
            raise APIError(resp.status_code, f"Unexpected response type: {type(data)}", str(resp.url))
        if "error" in data and data["error"]:
            raise APIError(resp.status_code, str(data["error"]), str(resp.url))

        content = ""
        output = data.get("output", [])
        for item in output:
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        content += part.get("text", "")
            elif item.get("type") == "output_text":
                content += item.get("text", "")

        return ChatResponse(
            content=content,
            model=data.get("model", ""),
            finish_reason=data.get("status"),
            logprobs=None,
            response_headers={k: v for k, v in resp.headers.items()},
            raw_response=data,
        )

    async def close(self):
        await self._client.aclose()

import time

import anthropic

import config

from services.llm.base import LLMError, LLMResult

TOOL_NAME = "respond"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str, client=None, max_tokens: int = 1024):
        self.model = model
        self._max_tokens = max_tokens
        self._client = client or anthropic.Anthropic(
            api_key=api_key, timeout=config.LLM_TIMEOUT_SECONDS, max_retries=0
        )

    def complete_json(self, system: str, user: str, schema: dict) -> LLMResult:
        started = time.monotonic()
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[{"name": TOOL_NAME, "description": "Return the structured result.", "input_schema": schema}],
                tool_choice={"type": "tool", "name": TOOL_NAME},
            )
        except anthropic.AnthropicError as exc:
            raise LLMError(f"Anthropic request failed: {exc}") from exc
        data = next((b.input for b in resp.content if getattr(b, "type", None) == "tool_use"), None)
        if not isinstance(data, dict):
            raise LLMError("Anthropic returned no structured result")
        return LLMResult(
            data=data,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

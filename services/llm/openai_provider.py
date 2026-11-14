import json
import time

import openai

from services.llm.base import LLMError, LLMResult


class OpenAIProvider:
    def __init__(
        self, model: str, api_key: str, client=None, base_url: str | None = None, name: str = "openai"
    ):
        """`base_url` points the client at any OpenAI-compatible server (a local LLM)."""
        self.name = name
        self.model = model
        if client is None:
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            client = openai.OpenAI(**kwargs)
        self._client = client

    def complete_json(self, system: str, user: str, schema: dict) -> LLMResult:
        started = time.monotonic()
        try:
            # No temperature: current OpenAI reasoning models reject non-default values.
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "result", "strict": True, "schema": schema},
                },
            )
        except openai.OpenAIError as exc:
            raise LLMError(f"OpenAI request failed: {exc}") from exc
        try:
            data = json.loads(resp.choices[0].message.content)
        except (TypeError, ValueError) as exc:
            raise LLMError("OpenAI returned unparseable JSON") from exc
        if not isinstance(data, dict):
            raise LLMError("OpenAI returned a non-object result")
        return LLMResult(
            data=data,
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

import json
import time

import openai

from services.llm.base import LLMError, LLMResult


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, api_key: str, client=None):
        self.model = model
        self._client = client or openai.OpenAI(api_key=api_key)

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

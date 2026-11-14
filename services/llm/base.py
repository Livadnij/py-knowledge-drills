"""Provider-agnostic LLM interface. A provider only does 'prompt in, JSON out'."""
from dataclasses import dataclass
from typing import Protocol


class LLMError(Exception):
    """Network/API failure or unparseable output from a provider."""


@dataclass
class LLMResult:
    data: dict
    input_tokens: int
    output_tokens: int
    latency_ms: int


class LLMProvider(Protocol):
    name: str
    model: str

    def complete_json(self, system: str, user: str, schema: dict) -> LLMResult: ...

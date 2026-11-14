from services.llm.base import LLMResult


class FakeProvider:
    """Queue-driven provider for tests. Items are LLMResult, dict (wrapped), or an Exception to raise."""

    name = "fake"
    model = "fake-1"

    def __init__(self, responses: list):
        self._queue = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str, schema: dict) -> LLMResult:
        self.calls.append((system, user))
        assert self._queue, "FakeProvider queue is empty"
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, dict):
            return LLMResult(data=item, input_tokens=100, output_tokens=20, latency_ms=1)
        return item

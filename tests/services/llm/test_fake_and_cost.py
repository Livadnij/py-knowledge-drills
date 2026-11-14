import pytest

from services.llm.base import LLMError, LLMResult
from services.llm.cost import llm_cost
from services.llm.fake import FakeProvider

SCHEMA = {"type": "object"}


def _r(**data):
    return LLMResult(data=data, input_tokens=10, output_tokens=5, latency_ms=1)


def test_fake_returns_queued_in_order():
    p = FakeProvider([_r(a=1), _r(a=2)])
    assert p.complete_json("s", "u", SCHEMA).data == {"a": 1}
    assert p.complete_json("s", "u", SCHEMA).data == {"a": 2}


def test_fake_accepts_plain_dicts():
    p = FakeProvider([{"verdict": "correct"}])
    r = p.complete_json("s", "u", SCHEMA)
    assert r.data == {"verdict": "correct"} and r.input_tokens > 0


def test_fake_raises_queued_exception():
    p = FakeProvider([LLMError("boom")])
    with pytest.raises(LLMError, match="boom"):
        p.complete_json("s", "u", SCHEMA)


def test_fake_records_calls():
    p = FakeProvider([{}])
    p.complete_json("sys", "usr", SCHEMA)
    assert p.calls == [("sys", "usr")]


def test_fake_raises_when_queue_empty():
    with pytest.raises(AssertionError):
        FakeProvider([]).complete_json("s", "u", SCHEMA)


def test_cost_math(monkeypatch):
    monkeypatch.setattr("config.PRICES_PER_MTOK", {"m": (3.0, 15.0)})
    assert llm_cost("m", 1_000_000, 1_000_000) == 18.0


def test_cost_unknown_model_is_zero():
    assert llm_cost("nope", 10, 10) == 0.0

import json
import os
from types import SimpleNamespace

import anthropic
import openai
import pytest

import config
from services.llm.anthropic_provider import AnthropicProvider
from services.llm.base import LLMError
from services.llm.factory import make_provider
from services.llm.openai_provider import OpenAIProvider

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


class _AnthropicStub:
    def __init__(self, response=None, error=None):
        self.calls, self._response, self._error = [], response, error
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        if self._error:
            raise self._error
        return self._response


def _anthropic_response(data):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="..."), SimpleNamespace(type="tool_use", input=data)],
        usage=SimpleNamespace(input_tokens=11, output_tokens=7),
    )


class _OpenAIStub:
    def __init__(self, content=None, error=None):
        self.calls, self._content, self._error = [], content, error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        if self._error:
            raise self._error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))],
            usage=SimpleNamespace(prompt_tokens=13, completion_tokens=5),
        )


def test_anthropic_returns_parsed_data_and_usage():
    stub = _AnthropicStub(_anthropic_response({"ok": True}))
    r = AnthropicProvider("m", "key", client=stub).complete_json("sys", "usr", SCHEMA)
    assert (r.data, r.input_tokens, r.output_tokens) == ({"ok": True}, 11, 7)
    assert r.latency_ms >= 0
    call = stub.calls[0]
    assert call["system"] == "sys" and "temperature" not in call
    assert call["tool_choice"]["type"] == "tool"
    assert call["tools"][0]["input_schema"] == SCHEMA


def test_openai_returns_parsed_data_and_usage():
    stub = _OpenAIStub(json.dumps({"ok": True}))
    r = OpenAIProvider("m", "key", client=stub).complete_json("sys", "usr", SCHEMA)
    assert (r.data, r.input_tokens, r.output_tokens) == ({"ok": True}, 13, 5)
    call = stub.calls[0]
    assert call["response_format"]["json_schema"]["schema"] == SCHEMA
    assert [m["role"] for m in call["messages"]] == ["system", "user"]


def test_sdk_error_wrapped_as_llm_error():
    anth = AnthropicProvider("m", "k", client=_AnthropicStub(error=anthropic.AnthropicError("x")))
    with pytest.raises(LLMError):
        anth.complete_json("s", "u", SCHEMA)
    oai = OpenAIProvider("m", "k", client=_OpenAIStub(error=openai.OpenAIError("x")))
    with pytest.raises(LLMError):
        oai.complete_json("s", "u", SCHEMA)


def test_unparseable_output_wrapped():
    with pytest.raises(LLMError):
        OpenAIProvider("m", "k", client=_OpenAIStub("not json {")).complete_json("s", "u", SCHEMA)
    with pytest.raises(LLMError):
        OpenAIProvider("m", "k", client=_OpenAIStub(None)).complete_json("s", "u", SCHEMA)
    no_tool = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="hi")],
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )
    with pytest.raises(LLMError):
        AnthropicProvider("m", "k", client=_AnthropicStub(no_tool)).complete_json("s", "u", SCHEMA)


def test_factory_unknown_provider():
    with pytest.raises(ValueError):
        make_provider("nope")


def test_factory_missing_key(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", None)
    with pytest.raises(LLMError):
        make_provider("anthropic")


def test_factory_builds_provider(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "k")
    p = make_provider("openai")
    assert (p.name, p.model) == ("openai", config.MODELS["openai"])


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")
def test_anthropic_live():
    r = make_provider("anthropic").complete_json("Reply with JSON.", "Set ok to true.", SCHEMA)
    assert r.data == {"ok": True}


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="needs OPENAI_API_KEY")
def test_openai_live():
    r = make_provider("openai").complete_json("Reply with JSON.", "Set ok to true.", SCHEMA)
    assert r.data == {"ok": True}


def test_openai_provider_passes_base_url_to_client(monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, **kw):
            seen.update(kw)

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    p = OpenAIProvider("m", "k", base_url="http://localhost:1234/v1", name="local")
    assert seen["api_key"] == "k" and seen["base_url"] == "http://localhost:1234/v1"
    assert p.name == "local"


def test_factory_builds_local_provider(monkeypatch):
    monkeypatch.setattr(config, "LOCAL_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setattr(config, "LOCAL_MODEL", "qwen3-8b")
    monkeypatch.setattr(config, "LOCAL_API_KEY", "local-key")
    p = make_provider("local")
    assert (p.name, p.model) == ("local", "qwen3-8b")


def test_factory_local_requires_url_and_model(monkeypatch):
    monkeypatch.setattr(config, "LOCAL_BASE_URL", None)
    monkeypatch.setattr(config, "LOCAL_MODEL", "m")
    with pytest.raises(LLMError, match="LOCAL_LLM_BASE_URL"):
        make_provider("local")
    monkeypatch.setattr(config, "LOCAL_BASE_URL", "http://x/v1")
    monkeypatch.setattr(config, "LOCAL_MODEL", None)
    with pytest.raises(LLMError, match="LOCAL_LLM_MODEL"):
        make_provider("local")


def test_clients_get_a_timeout_and_no_sdk_retries(monkeypatch):
    seen = {}

    class Capture:
        def __init__(self, **kw):
            seen.setdefault("calls", []).append(kw)

    monkeypatch.setattr(openai, "OpenAI", Capture)
    monkeypatch.setattr(anthropic, "Anthropic", Capture)
    OpenAIProvider("m", "k")
    AnthropicProvider("m", "k")
    for kw in seen["calls"]:
        assert kw["timeout"] == config.LLM_TIMEOUT_SECONDS <= 120
        assert kw["max_retries"] == 0

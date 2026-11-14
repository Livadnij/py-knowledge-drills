import json
from pathlib import Path

from db.models import Base
from db.session import make_engine, make_session_factory
from services.llm.fake import FakeProvider
from scripts.study_cli import main

FIX = Path(__file__).parent.parent / "fixtures"


def _factory():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def _run(argv, factory, inputs=(), provider=None):
    out, it = [], iter(inputs)
    code = main(argv, input_fn=lambda prompt="": next(it), print_fn=lambda *a: out.append(" ".join(map(str, a))),
                provider=provider, session_factory=factory)
    return code, "\n".join(out)


def test_cli_full_session_with_fake_provider():
    factory = _factory()
    code, out = _run(["import", str(FIX / "valid.json")], factory)
    assert code == 0 and "2 added" in out
    _, areas_out = _run(["areas"], factory)
    assert "databases" in areas_out

    provider = FakeProvider([{"verdict": "correct", "missed": [], "hint": None}])
    answer = "Optimistic uses a version column; pessimistic uses SELECT FOR UPDATE."
    code, out = _run(["study", "databases"], factory, inputs=[answer, "/surrender"], provider=provider)
    assert code == 0
    assert "Rating: Good" in out
    assert "Surrendered" in out
    assert out.count("Next due:") == 2


def test_cli_hint_loop_then_flag():
    factory = _factory()
    _run(["import", str(FIX / "valid.json")], factory)
    provider = FakeProvider([{"verdict": "partial", "missed": [1], "hint": "Think about who has to wait."}])
    answer = "Optimistic locking uses a version column and retries."
    code, out = _run(["study", "databases"], factory, inputs=[answer, "/flag checklist is odd", "/quit"], provider=provider)
    assert code == 0
    assert "Think about who has to wait." in out
    assert "Flagged" in out


def test_cli_empty_queue_message():
    factory = _factory()
    f = FIX.parent / "fixtures" / "_areas_only.json"
    f.write_text(json.dumps({"areas": [{"key": "empty", "name": "Empty"}]}))
    try:
        _run(["import", str(f)], factory)
    finally:
        f.unlink()
    code, out = _run(["study", "empty"], factory, provider=FakeProvider([]))
    assert code == 0 and "Nothing to study" in out


def test_cli_unknown_area_is_an_error():
    code, out = _run(["study", "nope"], _factory(), provider=FakeProvider([]))
    assert code != 0 and "nope" in out

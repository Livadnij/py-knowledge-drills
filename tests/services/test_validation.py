from domain import Fact
from services.validation import validate_area, validate_question


def _ok(**over):
    raw = {"area": "db", "text": "Q?", "answer": ["a"]}
    raw.update(over)
    return raw


def test_defaults_applied():
    q, errors = validate_question(_ok())
    assert errors == []
    assert (q.type, q.level, q.priority, q.external_id) == ("text", 3, False, None)


def test_fact_forms():
    q, errors = validate_question(_ok(answer=["a", {"fact": "b", "major": True}]))
    assert errors == []
    assert q.facts == [Fact("a", False), Fact("b", True)]


def test_all_errors_reported():
    q, errors = validate_question({"area": "db", "level": 9, "type": "x", "answer": ["ok", " "]}, "questions[2]")
    assert q is None
    assert len(errors) == 4
    assert all(e.startswith("questions[2]") for e in errors)


def test_empty_or_blank_answer_rejected():
    assert validate_question(_ok(answer=[]))[1]
    assert validate_question(_ok(answer=["  "]))[1]


def test_bad_area_key_rejected():
    for key in ("My Area", "UPPER", ""):
        _, errors = validate_area({"key": key, "name": "N"}, "areas[0]")
        assert errors, key
    assert validate_area({"key": "node-runtime", "name": "N"}, "areas[0]")[1] == []


def test_level_rejects_bool_and_float():
    assert validate_question(_ok(level=True))[1]
    assert validate_question(_ok(level=3.5))[1]

import json
from pathlib import Path

from sqlalchemy import func, select

from db.models import Area, ImportLog, Question
from db.repositories import areas, questions
from domain import Fact
from services.importer import import_file, import_files

FIX = Path(__file__).parent.parent / "fixtures"


def _count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_valid_file_imports_areas_and_questions(session):
    r = import_file(session, FIX / "valid.json")
    assert (r.ok, r.areas_created, r.questions_added, r.errors) == (True, 1, 2, [])
    q = session.scalars(select(Question).where(Question.external_id == "db-1")).one()
    assert questions.facts(q) == [Fact("Optimistic locking uses a version column."), Fact("Pessimistic locking uses SELECT FOR UPDATE.", True)]


def test_question_may_use_area_defined_in_same_file(session):
    assert import_file(session, FIX / "valid.json").ok


def test_question_may_use_existing_area(session, tmp_path):
    areas.create(session, "node", "Node")
    f = tmp_path / "q.json"
    f.write_text(json.dumps({"questions": [{"area": "node", "text": "Q?", "answer": ["a"]}]}))
    assert import_file(session, f).questions_added == 1


def test_unknown_area_rejects_whole_file(session):
    r = import_file(session, FIX / "bad_unknown_area.json")
    assert not r.ok
    assert any("nope" in e for e in r.errors)
    assert (_count(session, Area), _count(session, Question)) == (0, 0)


def test_all_errors_listed_and_nothing_written(session):
    r = import_file(session, FIX / "bad_multiple_errors.json")
    assert not r.ok and len(r.errors) >= 4
    assert (_count(session, Area), _count(session, Question)) == (0, 0)


def test_blank_fact_and_empty_answer_rejected(session):
    r = import_file(session, FIX / "bad_multiple_errors.json")
    assert any("answer" in e for e in r.errors)


def test_reimport_is_idempotent(session):
    import_file(session, FIX / "valid.json")
    r = import_file(session, FIX / "valid.json")
    assert (r.ok, r.questions_added, len(r.skipped)) == (True, 0, 2)
    assert _count(session, Question) == 2


def test_existing_area_redefined_is_left_untouched(session):
    areas.create(session, "databases", "My Own Name")
    r = import_file(session, FIX / "valid.json")
    assert r.areas_created == 0
    assert areas.get_by_key(session, "databases").name == "My Own Name"


def test_import_logged(session):
    import_files(session, [FIX / "valid.json", FIX / "bad_unknown_area.json"])
    rows = session.scalars(select(ImportLog)).all()
    assert [r.filename for r in rows] == ["valid.json"]  # rejected files write nothing


def test_invalid_json_file_reports_error(session, tmp_path):
    f = tmp_path / "broken.json"
    f.write_text("{not json")
    r = import_file(session, f)
    assert not r.ok and r.errors


def test_duplicates_within_one_file_are_skipped(session, tmp_path):
    f = tmp_path / "d.json"
    q = {"area": "a", "text": "Same?", "answer": ["x"]}
    f.write_text(json.dumps({"areas": [{"key": "a", "name": "A"}], "questions": [q, q]}))
    r = import_file(session, f)
    assert (r.questions_added, len(r.skipped)) == (1, 1)


# --- final-review fixes ---


def test_non_list_sections_are_rejected_with_a_report(session, tmp_path):
    for body in ({"areas": None}, {"questions": 5}, {"areas": "x", "questions": {}}):
        f = tmp_path / "s.json"
        f.write_text(json.dumps(body))
        r = import_file(session, f)
        assert not r.ok and r.errors, body


def test_one_crashing_file_does_not_hide_other_reports(session, monkeypatch, tmp_path):
    second = tmp_path / "second.json"
    second.write_text(json.dumps({"areas": [{"key": "net", "name": "Net"}],
                                  "questions": [{"area": "net", "text": "Q?", "answer": ["a"]}]}))
    real = questions.create
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 3:  # first question of the second file
            raise RuntimeError("disk on fire")
        return real(*a, **kw)

    monkeypatch.setattr(questions, "create", flaky)
    reports = import_files(session, [FIX / "valid.json", second])
    assert len(reports) == 2 and reports[0].ok
    assert reports[1].ok is False and any("disk on fire" in e for e in reports[1].errors)


def test_crash_midway_through_a_file_writes_nothing(session, monkeypatch):
    real = questions.create
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(*a, **kw)

    monkeypatch.setattr(questions, "create", flaky)
    (report,) = import_files(session, [FIX / "valid.json"])
    session.rollback()
    assert not report.ok
    assert (_count(session, Area), _count(session, Question)) == (0, 0)

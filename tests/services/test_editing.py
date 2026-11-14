import json
from datetime import datetime

from fsrs import Rating
from sqlalchemy import func, select

from db.models import Question, Review
from db.repositories import areas, cards, logs, questions
from domain import Fact
from services.editing import QuestionView, get_question, list_flagged, retire_question, update_question
from services.importer import import_file
from services.queue import build_queue, start_area
from services.scheduler import DrillScheduler

NOW = datetime(2026, 11, 14, 9, 0)
FACTS = [Fact("Old fact one."), Fact("Old fact two.", True)]


def _q(session, area, text="Old text?", **kw):
    return questions.create(session, area_id=area.id, text=text, facts=FACTS, **kw)


def _edit(session, qid, **over):
    args = dict(text="New text?", type="text", level=4, priority=True, facts=[Fact("New fact.", True)])
    args.update(over)
    return update_question(session, qid, **args)


def test_list_flagged_with_notes_and_area_filter(session):
    a, b = areas.create(session, "db", "DB"), areas.create(session, "net", "Net")
    q1, q2, _ok = _q(session, a, "q1"), _q(session, b, "q2"), _q(session, a, "ok")
    questions.set_flag(session, q1.id, "bad checklist")
    questions.set_flag(session, q2.id, None)
    everything = list_flagged(session)
    assert {v.id for v in everything} == {q1.id, q2.id}
    only_db = list_flagged(session, a.id)
    assert [(v.id, v.flag_note, v.area_name) for v in only_db] == [(q1.id, "bad checklist", "DB")]
    assert isinstance(only_db[0], QuestionView) and only_db[0].facts == FACTS


def test_update_clears_flag_and_keeps_card_by_default(session):
    a = areas.create(session, "db", "DB")
    q = _q(session, a)
    state, due = DrillScheduler().review(None, Rating.Good, NOW)
    cards.upsert(session, q.id, state, due)
    questions.set_flag(session, q.id, "wrong")
    assert _edit(session, q.id) == []
    view = get_question(session, q.id)
    assert (view.text, view.level, view.priority, view.flagged, view.facts) == ("New text?", 4, True, False, [Fact("New fact.", True)])
    assert cards.get(session, q.id).state == state


def test_update_with_reset_deletes_card_but_keeps_review_history(session):
    a = areas.create(session, "db", "DB")
    q = _q(session, a)
    state, due = DrillScheduler().review(None, Rating.Good, NOW)
    cards.upsert(session, q.id, state, due)
    logs.add_review(session, question_id=q.id, rating=3, state_after=state)
    assert _edit(session, q.id, reset_schedule=True) == []
    assert cards.get(session, q.id) is None
    assert session.query(Review).count() == 1


def test_invalid_update_returns_errors_and_changes_nothing(session):
    a = areas.create(session, "db", "DB")
    q = _q(session, a)
    questions.set_flag(session, q.id, "wrong")
    errors = _edit(session, q.id, level=9, facts=[Fact("  ")])
    assert len(errors) == 2
    view = get_question(session, q.id)
    assert (view.text, view.flagged, view.facts) == ("Old text?", True, FACTS)


def test_retire_removes_from_flagged_and_queue(session):
    a = areas.create(session, "db", "DB")
    q = _q(session, a)
    start_area(session, a.id, NOW)
    questions.set_flag(session, q.id, None)
    retire_question(session, q.id)
    assert list_flagged(session) == []
    assert build_queue(session, a.id, NOW, DrillScheduler()) == []


def test_reimport_does_not_overwrite_edited_question(session, tmp_path):
    original = {
        "areas": [{"key": "db", "name": "DB"}],
        "questions": [
            {"area": "db", "text": "With id?", "external_id": "x-1", "answer": ["a"]},
            {"area": "db", "text": "No id?", "answer": ["a"]},
        ],
    }
    f = tmp_path / "q.json"
    f.write_text(json.dumps(original))
    import_file(session, f)
    with_id = session.scalars(select(Question).where(Question.external_id == "x-1")).one()
    without_id = session.scalars(select(Question).where(Question.text == "No id?")).one()
    _edit(session, with_id.id, text="Edited with id?")
    _edit(session, without_id.id, text="Edited no id?")

    r = import_file(session, f)

    assert get_question(session, with_id.id).text == "Edited with id?"
    assert len(r.skipped) == 1  # matched by external_id
    assert r.questions_added == 1  # edited text no longer matches, so the id-less original comes back as new
    assert session.scalar(select(func.count()).select_from(Question)) == 3

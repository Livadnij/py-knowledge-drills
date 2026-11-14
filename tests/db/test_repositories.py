from datetime import datetime

from db.repositories import areas, cards, questions
from domain import Fact


def _q(session, area, text="What is X?", **kw):
    return questions.create(session, area_id=area.id, text=text, facts=[Fact("a")], **kw)


def test_find_duplicate_ignores_case_and_whitespace(session):
    a = areas.create(session, "db", "DB")
    b = areas.create(session, "net", "Net")
    q = _q(session, a, "What  is X?")
    assert questions.find_duplicate(session, a.id, " what is x? ", None).id == q.id
    assert questions.find_duplicate(session, b.id, "what is x?", None) is None


def test_find_duplicate_by_external_id(session):
    a = areas.create(session, "db", "DB")
    q = _q(session, a, "Original", external_id="ext-1")
    assert questions.find_duplicate(session, a.id, "Totally different text", "ext-1").id == q.id
    assert questions.find_duplicate(session, a.id, "Totally different text", "ext-2") is None


def test_set_flag_and_update_clears_flag(session):
    a = areas.create(session, "db", "DB")
    q = _q(session, a)
    questions.set_flag(session, q.id, "checklist is wrong")
    assert (q.flagged, q.flag_note) == (True, "checklist is wrong")
    questions.update(session, q.id, text="New?", type="code", level=4, priority=True, facts=[Fact("z", True)])
    assert (q.flagged, q.flag_note, q.text, q.level) == (False, None, "New?", 4)
    assert questions.facts(q) == [Fact("z", True)]


def test_cards_upsert_replaces_state(session):
    a = areas.create(session, "db", "DB")
    q = _q(session, a)
    cards.upsert(session, q.id, {"v": 1}, datetime(2026, 1, 1))
    cards.upsert(session, q.id, {"v": 2}, datetime(2026, 1, 5))
    card = cards.get(session, q.id)
    assert (card.state, card.due) == ({"v": 2}, datetime(2026, 1, 5))
    cards.delete(session, q.id)
    assert cards.get(session, q.id) is None


def test_mark_started_is_idempotent(session):
    a = areas.create(session, "db", "DB")
    areas.mark_started(session, a.id, datetime(2026, 1, 1))
    areas.mark_started(session, a.id, datetime(2026, 2, 2))
    assert a.started_at == datetime(2026, 1, 1)

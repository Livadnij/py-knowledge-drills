from datetime import datetime, timedelta

from fsrs import Rating

from db.repositories import areas, cards, questions
from domain import Fact
from services.queue import area_summaries, build_queue, start_area
from services.scheduler import DrillScheduler

NOW = datetime(2026, 11, 14, 9, 0)
sched = DrillScheduler()


def _setup(session, started=True):
    area = areas.create(session, "db", "DB")
    if started:
        start_area(session, area.id, NOW)
    return area


def _q(session, area, text, level=3, priority=False):
    return questions.create(session, area_id=area.id, text=text, facts=[Fact("a")], level=level, priority=priority)


def _reviewed(session, q, rating, days_ago):
    reviewed_at = NOW - timedelta(days=days_ago)
    state, due = sched.review(None, rating, reviewed_at)
    cards.upsert(session, q.id, state, due)
    return q


def test_unstarted_area_returns_empty_queue(session):
    a = _setup(session, started=False)
    _q(session, a, "Q")
    assert build_queue(session, a.id, NOW, sched) == []


def test_due_before_new(session):
    a = _setup(session)
    new = _q(session, a, "new")
    due = _reviewed(session, _q(session, a, "due"), Rating.Good, 30)
    assert build_queue(session, a.id, NOW, sched) == [due.id, new.id]


def test_due_ordered_by_lowest_retrievability(session):
    a = _setup(session)
    fresh = _reviewed(session, _q(session, a, "fresh"), Rating.Again, 1)   # due soon, just seen
    stale = _reviewed(session, _q(session, a, "stale"), Rating.Good, 60)   # long overdue
    assert build_queue(session, a.id, NOW, sched) == [stale.id, fresh.id]


def test_new_ordered_by_level_then_priority(session):
    a = _setup(session)
    l3 = _q(session, a, "l3", level=3)
    l1 = _q(session, a, "l1", level=1)
    l1p = _q(session, a, "l1p", level=1, priority=True)
    assert build_queue(session, a.id, NOW, sched) == [l1p.id, l1.id, l3.id]


def test_flagged_and_retired_excluded(session):
    a = _setup(session)
    ok = _q(session, a, "ok")
    flagged = _q(session, a, "flagged")
    retired = _q(session, a, "retired")
    questions.set_flag(session, flagged.id, None)
    questions.retire(session, retired.id)
    assert build_queue(session, a.id, NOW, sched) == [ok.id]


def test_not_yet_due_card_excluded(session):
    a = _setup(session)
    _reviewed(session, _q(session, a, "later"), Rating.Good, 0)
    assert build_queue(session, a.id, NOW, sched) == []


def test_empty_area_returns_empty_list(session):
    a = _setup(session)
    q = _q(session, a, "only")
    questions.set_flag(session, q.id, "bad")
    assert build_queue(session, a.id, NOW, sched) == []


def test_summaries_count_due_and_new(session):
    a = _setup(session)
    _reviewed(session, _q(session, a, "due"), Rating.Good, 30)
    _q(session, a, "new1")
    _q(session, a, "new2")
    b = areas.create(session, "net", "Net")
    _q(session, b, "unstarted")
    s = {x.key: x for x in area_summaries(session, NOW, sched)}
    assert (s["db"].started, s["db"].due, s["db"].new) == (True, 1, 2)
    assert (s["net"].started, s["net"].due, s["net"].new) == (False, 0, 0)

import json
from datetime import datetime, timedelta

from fsrs import Rating

from services.scheduler import DrillScheduler

NOW = datetime(2026, 11, 14, 9, 30)
sched = DrillScheduler()


def test_first_review_creates_state_and_future_due():
    state, due = sched.review(None, Rating.Good, NOW)
    assert isinstance(state, dict)
    assert due.date() > NOW.date()


def test_intervals_are_whole_days():
    for rating in Rating:
        _, due = sched.review(None, rating, NOW)
        assert due - NOW == timedelta(days=(due - NOW).days)
        assert (due - NOW).days >= 1


def test_again_is_due_sooner_than_good():
    _, again = sched.review(None, Rating.Again, NOW)
    _, good = sched.review(None, Rating.Good, NOW)
    assert again < good


def test_state_roundtrips_json():
    state, due = sched.review(None, Rating.Good, NOW)
    state2, due2 = sched.review(json.loads(json.dumps(state)), Rating.Good, due)
    assert due2 > due
    json.dumps(state2)


def test_is_due_compares_dates():
    due = datetime(2026, 11, 14, 23, 59)
    assert sched.is_due(due, datetime(2026, 11, 14, 0, 1))
    assert not sched.is_due(due, datetime(2026, 11, 13, 23, 59))


def test_retrievability_decreases_over_time():
    state, due = sched.review(None, Rating.Good, NOW)
    soon = sched.retrievability(state, NOW + timedelta(days=1))
    later = sched.retrievability(state, NOW + timedelta(days=30))
    assert 0 < later < soon <= 1

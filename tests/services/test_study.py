from datetime import datetime

import pytest
from fsrs import Rating

import config
from db.models import Attempt, LLMCall, Review
from db.repositories import areas, cards, questions
from domain import Fact, Verdict
from services.grading import Grader, GradingError
from services.llm.base import LLMError
from services.llm.fake import FakeProvider
from services.scheduler import DrillScheduler
from services.study import FinalResult, HintStep, StudyService

NOW = datetime(2026, 11, 14, 9, 0)
FACTS = [Fact("Optimistic locking uses a version column."), Fact("Pessimistic locking uses SELECT FOR UPDATE.", True)]
LONG = "a sufficiently long answer"


def _service(session, responses):
    provider = FakeProvider(responses)
    svc = StudyService(session, Grader(provider), DrillScheduler(), clock=lambda: NOW)
    area = areas.create(session, "db", "DB")
    q = questions.create(session, area_id=area.id, text="Locking?", facts=FACTS)
    return svc, provider, q


def _correct():
    return {"verdict": "correct", "missed": [], "hint": None}


def _partial(missed, hint="Think about who waits."):
    return {"verdict": "partial", "missed": missed, "hint": hint}


def _incorrect(hint="Reconsider the basics."):
    return {"verdict": "incorrect", "missed": [0, 1], "hint": hint}


def _count(session, model):
    return session.query(model).count()


def test_correct_first_try_gives_good_and_future_due(session):
    svc, _, q = _service(session, [_correct()])
    r = svc.submit(svc.open_question(q.id), LONG)
    assert isinstance(r, FinalResult)
    assert (r.rating, r.verdict, r.missed) == (Rating.Good, Verdict.correct, [])
    assert r.next_due.date() > NOW.date()
    assert cards.get(session, q.id).due == r.next_due
    assert session.query(Review).one().rating == int(Rating.Good)
    assert session.query(Attempt).one().verdict == "correct"


def test_claimed_easy_gives_easy(session):
    svc, _, q = _service(session, [_correct()])
    assert svc.submit(svc.open_question(q.id), LONG, claimed_easy=True).rating == Rating.Easy


def test_partial_then_hint_then_correct_gives_hard(session):
    svc, provider, q = _service(session, [_partial([1], "Think about who waits."), _correct()])
    rnd = svc.open_question(q.id)
    step = svc.submit(rnd, LONG)
    assert isinstance(step, HintStep)
    assert (step.verdict, step.hint, step.hints_used) == (Verdict.partial, "Think about who waits.", 1)
    assert rnd.hints == ["Think about who waits."]
    final = svc.submit(rnd, LONG + " revised")
    assert final.rating == Rating.Hard
    assert "Think about who waits." in provider.calls[1][1]


def test_incorrect_after_three_hints_gives_again_and_reveals_facts(session):
    svc, _, q = _service(session, [_incorrect(f"hint {i}") for i in range(3)] + [_incorrect(None)])
    rnd = svc.open_question(q.id)
    steps = [svc.submit(rnd, LONG) for _ in range(3)]
    assert all(isinstance(s, HintStep) for s in steps)
    assert [s.hints_used for s in steps] == [1, 2, 3]
    final = svc.submit(rnd, LONG)
    assert isinstance(final, FinalResult)
    assert (final.rating, final.facts, final.missed) == (Rating.Again, FACTS, FACTS)


def _four_attempts(missed_last):
    return [_partial([0], f"hint {i}") for i in range(3)] + [_partial(missed_last, None)]


def test_partial_minor_only_after_hints_gives_hard(session):
    svc, _, q = _service(session, _four_attempts([0]))
    rnd = svc.open_question(q.id)
    for _ in range(3):
        svc.submit(rnd, LONG)
    final = svc.submit(rnd, LONG)
    assert (final.rating, final.missed) == (Rating.Hard, [FACTS[0]])


def test_partial_with_major_missed_gives_again(session):
    svc, _, q = _service(session, _four_attempts([1]))
    rnd = svc.open_question(q.id)
    for _ in range(3):
        svc.submit(rnd, LONG)
    assert svc.submit(rnd, LONG).rating == Rating.Again


def test_short_answer_no_llm_call(session):
    svc, provider, q = _service(session, [])
    r = svc.submit(svc.open_question(q.id), "x" * (config.MIN_ANSWER_CHARS - 1))
    assert provider.calls == []
    assert (r.rating, r.verdict) == (Rating.Again, None)
    assert cards.get(session, q.id) is not None


def test_surrender_gives_again_and_reveals_facts(session):
    svc, provider, q = _service(session, [])
    r = svc.surrender(svc.open_question(q.id))
    assert (r.rating, r.surrendered, r.facts) == (Rating.Again, True, FACTS)
    assert provider.calls == []
    assert session.query(Review).one().surrendered is True


def test_flag_before_final_writes_no_review_and_keeps_card(session):
    svc, _, q = _service(session, [_partial([1])])
    cards.upsert(session, q.id, {"keep": 1}, datetime(2026, 11, 1))
    rnd = svc.open_question(q.id)
    svc.submit(rnd, LONG)
    r = svc.flag(rnd, "checklist asks for something the question never implied")
    assert (r.flagged, r.rating, r.next_due) == (True, None, None)
    assert _count(session, Review) == 0
    assert cards.get(session, q.id).state == {"keep": 1}
    assert (q.flagged, q.flag_note) == (True, "checklist asks for something the question never implied")
    assert _count(session, Attempt) == 1  # the attempt stays logged


def test_flag_after_final_reverts_existing_card(session):
    svc, _, q = _service(session, [_correct()])
    old_state, old_due = DrillScheduler().review(None, Rating.Good, datetime(2026, 10, 1))
    cards.upsert(session, q.id, old_state, old_due)
    rnd = svc.open_question(q.id)
    svc.submit(rnd, LONG)
    assert cards.get(session, q.id).due != old_due
    svc.flag(rnd, "grader was wrong")
    assert (cards.get(session, q.id).state, cards.get(session, q.id).due) == (old_state, old_due)
    assert _count(session, Review) == 0


def test_flag_after_final_on_new_card_removes_it(session):
    svc, _, q = _service(session, [_correct()])
    rnd = svc.open_question(q.id)
    svc.submit(rnd, LONG)
    svc.flag(rnd)
    assert cards.get(session, q.id) is None and q.flagged


def test_grading_error_changes_nothing_and_round_retryable(session):
    svc, _, q = _service(session, [LLMError("down"), LLMError("down"), _correct()])
    rnd = svc.open_question(q.id)
    with pytest.raises(GradingError):
        svc.submit(rnd, LONG)
    assert (_count(session, Attempt), _count(session, Review), cards.get(session, q.id)) == (0, 0, None)
    assert (rnd.hints, rnd.attempts, rnd.finished) == ([], 0, False)
    assert svc.submit(rnd, LONG).rating == Rating.Good


def test_llm_calls_logged_with_cost(session, monkeypatch):
    monkeypatch.setattr("config.PRICES_PER_MTOK", {"fake-1": (1_000_000.0, 0.0)})
    svc, _, q = _service(session, [_correct()])
    svc.submit(svc.open_question(q.id), LONG)
    call = session.query(LLMCall).one()
    assert (call.provider, call.model, call.purpose, call.input_tokens) == ("fake", "fake-1", "grade", 100)
    assert call.cost_usd == 100.0


def test_submit_after_finish_raises(session):
    svc, _, q = _service(session, [_correct()])
    rnd = svc.open_question(q.id)
    svc.submit(rnd, LONG)
    with pytest.raises(ValueError):
        svc.submit(rnd, LONG)

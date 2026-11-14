import pytest
from fsrs import Rating

from domain import Verdict
from services.rating import Outcome, rate

V = Verdict


@pytest.mark.parametrize(
    "outcome, expected",
    [
        (Outcome(surrendered=True), Rating.Again),
        (Outcome(too_short=True), Rating.Again),
        (Outcome(verdict=V.incorrect), Rating.Again),
        (Outcome(verdict=V.incorrect, hints_used=3), Rating.Again),
        (Outcome(verdict=V.partial, missed_major=True), Rating.Again),
        (Outcome(verdict=V.partial, missed_major=True, hints_used=2), Rating.Again),
        (Outcome(verdict=V.partial), Rating.Hard),
        (Outcome(verdict=V.partial, hints_used=3), Rating.Hard),
        (Outcome(verdict=V.correct, hints_used=1), Rating.Hard),
        (Outcome(verdict=V.correct, hints_used=2), Rating.Hard),
        (Outcome(verdict=V.correct, hints_used=3), Rating.Hard),
        (Outcome(verdict=V.correct), Rating.Good),
        (Outcome(verdict=V.correct, claimed_easy=True), Rating.Easy),
    ],
)
def test_rating_table(outcome, expected):
    assert rate(outcome) == expected


def test_claimed_easy_ignored_when_not_correct():
    assert rate(Outcome(verdict=V.partial, claimed_easy=True)) == Rating.Hard
    assert rate(Outcome(verdict=V.incorrect, claimed_easy=True)) == Rating.Again


def test_claimed_easy_ignored_when_hints_used():
    assert rate(Outcome(verdict=V.correct, hints_used=1, claimed_easy=True)) == Rating.Hard


def test_surrender_beats_everything():
    assert rate(Outcome(surrendered=True, verdict=V.correct, claimed_easy=True)) == Rating.Again


def test_rate_is_pure():
    o = Outcome(verdict=V.correct)
    assert rate(o) == rate(o) == Rating.Good

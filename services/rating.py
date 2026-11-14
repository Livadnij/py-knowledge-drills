"""The deterministic rule that turns a graded outcome into an FSRS rating."""
from dataclasses import dataclass

from fsrs import Rating

from domain import Verdict


@dataclass(frozen=True)
class Outcome:
    surrendered: bool = False
    too_short: bool = False
    verdict: Verdict | None = None
    missed_major: bool = False
    hints_used: int = 0
    claimed_easy: bool = False


def rate(outcome: Outcome) -> Rating:
    if outcome.surrendered or outcome.too_short:
        return Rating.Again
    if outcome.verdict not in (Verdict.correct, Verdict.partial):
        return Rating.Again
    if outcome.verdict == Verdict.partial:
        return Rating.Again if outcome.missed_major else Rating.Hard
    if outcome.hints_used > 0:
        return Rating.Hard
    return Rating.Easy if outcome.claimed_easy else Rating.Good

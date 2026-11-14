"""Thin wrapper over py-fsrs: whole-day intervals, JSON-friendly state, naive local datetimes."""
from datetime import UTC, datetime

from fsrs import Card, Rating, Scheduler

import config


def _utc(naive_local: datetime) -> datetime:
    return naive_local.astimezone(UTC)


def _local(aware: datetime) -> datetime:
    return aware.astimezone().replace(tzinfo=None)


class DrillScheduler:
    def __init__(self, desired_retention: float = config.DESIRED_RETENTION):
        # No learning/relearning steps and no fuzzing: every interval is whole days.
        self._fsrs = Scheduler(
            desired_retention=desired_retention,
            learning_steps=(),
            relearning_steps=(),
            enable_fuzzing=False,
        )

    def review(self, state: dict | None, rating: Rating, now: datetime) -> tuple[dict, datetime]:
        card = Card.from_dict(state) if state else Card()
        card, _log = self._fsrs.review_card(card, rating, _utc(now))
        return card.to_dict(), _local(card.due)

    def retrievability(self, state: dict, now: datetime) -> float:
        return self._fsrs.get_card_retrievability(Card.from_dict(state), _utc(now))

    def is_due(self, due: datetime, now: datetime) -> bool:
        return due.date() <= now.date()

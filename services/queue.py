"""Which questions to ask next in an area, and per-area counts for the picker."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Area, Card, Question
from db.repositories import areas
from services.scheduler import DrillScheduler


@dataclass
class AreaSummary:
    id: int
    key: str
    name: str
    started: bool
    due: int
    new: int


def start_area(session: Session, area_id: int, now: datetime) -> None:
    areas.mark_started(session, area_id, now)


def _eligible(session: Session, area_id: int) -> list[tuple[Question, Card | None]]:
    stmt = (
        select(Question, Card)
        .outerjoin(Card, Card.question_id == Question.id)
        .where(Question.area_id == area_id, Question.flagged.is_(False), Question.retired.is_(False))
    )
    return [(q, c) for q, c in session.execute(stmt).all()]


def _split(session: Session, area_id: int, now: datetime, scheduler: DrillScheduler):
    due, new = [], []
    for q, card in _eligible(session, area_id):
        if card is None:
            new.append(q)
        elif scheduler.is_due(card.due, now):
            due.append((scheduler.retrievability(card.state, now), q))
    due.sort(key=lambda pair: (pair[0], pair[1].id))
    new.sort(key=lambda q: (q.level, not q.priority, q.id))
    return [q for _, q in due], new


def build_queue(session: Session, area_id: int, now: datetime, scheduler: DrillScheduler) -> list[int]:
    area = session.get(Area, area_id)
    if area is None or area.started_at is None:
        return []
    due, new = _split(session, area_id, now, scheduler)
    return [q.id for q in due] + [q.id for q in new]


def area_summaries(session: Session, now: datetime, scheduler: DrillScheduler) -> list[AreaSummary]:
    out = []
    for area in areas.list_all(session):
        started = area.started_at is not None
        due, new = _split(session, area.id, now, scheduler) if started else ([], [])
        out.append(AreaSummary(area.id, area.key, area.name, started, len(due), len(new)))
    return out

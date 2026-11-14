from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Question
from domain import Fact


def normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def create(
    s: Session,
    *,
    area_id: int,
    text: str,
    facts: list[Fact],
    type: str = "text",
    level: int = 3,
    priority: bool = False,
    external_id: str | None = None,
    now: datetime | None = None,
) -> Question:
    q = Question(
        area_id=area_id,
        text=text,
        facts=[{"text": f.text, "major": f.major} for f in facts],
        type=type,
        level=level,
        priority=priority,
        external_id=external_id,
    )
    if now is not None:
        q.created_at = now
    s.add(q)
    s.flush()
    return q


def find_duplicate(s: Session, area_id: int, text: str, external_id: str | None) -> Question | None:
    wanted = normalize(text)
    for q in s.scalars(select(Question).where(Question.area_id == area_id)):
        if external_id is not None and q.external_id == external_id:
            return q
        if normalize(q.text) == wanted:
            return q
    return None


def get(s: Session, id: int) -> Question:
    return s.get(Question, id)


def set_flag(s: Session, id: int, note: str | None) -> None:
    q = s.get(Question, id)
    q.flagged = True
    q.flag_note = note
    s.flush()


def update(s: Session, id: int, *, text: str, type: str, level: int, priority: bool, facts: list[Fact]) -> None:
    q = s.get(Question, id)
    q.text, q.type, q.level, q.priority = text, type, level, priority
    q.facts = [{"text": f.text, "major": f.major} for f in facts]
    q.flagged = False
    q.flag_note = None
    s.flush()


def retire(s: Session, id: int) -> None:
    s.get(Question, id).retired = True
    s.flush()


def facts(q: Question) -> list[Fact]:
    return [Fact(f["text"], f["major"]) for f in q.facts]

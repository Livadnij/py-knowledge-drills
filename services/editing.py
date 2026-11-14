"""Flagged-question list and the minimal question editor (service side)."""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Area, Question
from db.repositories import cards, questions
from domain import Fact
from services.validation import validate_question


@dataclass
class QuestionView:
    id: int
    area_id: int
    area_name: str
    type: str
    level: int
    priority: bool
    text: str
    facts: list[Fact]
    flagged: bool
    flag_note: str | None


def _view(q: Question, area_name: str) -> QuestionView:
    return QuestionView(
        id=q.id, area_id=q.area_id, area_name=area_name, type=q.type, level=q.level,
        priority=q.priority, text=q.text, facts=questions.facts(q), flagged=q.flagged, flag_note=q.flag_note,
    )


def get_question(session: Session, question_id: int) -> QuestionView:
    q = questions.get(session, question_id)
    return _view(q, session.get(Area, q.area_id).name)


def list_flagged(session: Session, area_id: int | None = None) -> list[QuestionView]:
    stmt = (
        select(Question, Area.name)
        .join(Area, Area.id == Question.area_id)
        .where(Question.flagged.is_(True), Question.retired.is_(False))
        .order_by(Area.name, Question.id)
    )
    if area_id is not None:
        stmt = stmt.where(Question.area_id == area_id)
    return [_view(q, name) for q, name in session.execute(stmt).all()]


def update_question(
    session: Session,
    question_id: int,
    *,
    text: str,
    type: str,
    level: int,
    priority: bool,
    facts: list[Fact],
    reset_schedule: bool = False,
) -> list[str]:
    """Validate and save an edit. Returns errors (and saves nothing) if invalid. Clears the flag."""
    raw = {
        "area": "-",  # not editable here; satisfies the shared validator
        "text": text,
        "type": type,
        "level": level,
        "priority": priority,
        "answer": [{"fact": f.text, "major": f.major} for f in facts],
    }
    data, errors = validate_question(raw, "question")
    if errors:
        return errors
    questions.update(
        session, question_id, text=data.text, type=data.type, level=data.level,
        priority=data.priority, facts=data.facts,
    )
    if reset_schedule:
        cards.delete(session, question_id)
    return []


def retire_question(session: Session, question_id: int) -> None:
    questions.retire(session, question_id)

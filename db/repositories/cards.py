from datetime import datetime

from sqlalchemy.orm import Session

from db.models import Card


def get(s: Session, question_id: int) -> Card | None:
    return s.get(Card, question_id)


def upsert(s: Session, question_id: int, state: dict, due: datetime) -> Card:
    card = s.get(Card, question_id)
    if card is None:
        card = Card(question_id=question_id, state=state, due=due)
        s.add(card)
    else:
        card.state, card.due = state, due
    s.flush()
    return card


def delete(s: Session, question_id: int) -> None:
    card = s.get(Card, question_id)
    if card is not None:
        s.delete(card)
        s.flush()

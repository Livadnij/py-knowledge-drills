from sqlalchemy.orm import Session

from db.models import Attempt, ImportLog, LLMCall, Review


def _add(s: Session, row):
    s.add(row)
    s.flush()
    return row


def add_attempt(s: Session, **kw) -> Attempt:
    return _add(s, Attempt(**kw))


def add_review(s: Session, **kw) -> Review:
    return _add(s, Review(**kw))


def add_import(s: Session, **kw) -> ImportLog:
    return _add(s, ImportLog(**kw))


def add_llm_call(s: Session, **kw) -> LLMCall:
    return _add(s, LLMCall(**kw))

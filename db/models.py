from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now()


class Area(Base):
    __tablename__ = "areas"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"))
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, default="text")
    level: Mapped[int] = mapped_column(default=3)
    priority: Mapped[bool] = mapped_column(default=False)
    text: Mapped[str] = mapped_column(Text)
    facts: Mapped[list] = mapped_column(JSON)
    flagged: Mapped[bool] = mapped_column(default=False)
    flag_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    retired: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Card(Base):
    __tablename__ = "cards"
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    state: Mapped[dict] = mapped_column(JSON)
    due: Mapped[datetime] = mapped_column(DateTime)


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    ordinal: Mapped[int]
    answer: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    missed: Mapped[list] = mapped_column(JSON, default=list)
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    rating: Mapped[int]
    hints_used: Mapped[int] = mapped_column(default=0)
    claimed_easy: Mapped[bool] = mapped_column(default=False)
    surrendered: Mapped[bool] = mapped_column(default=False)
    state_before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    state_after: Mapped[dict] = mapped_column(JSON)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ImportLog(Base):
    __tablename__ = "imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    areas_created: Mapped[int] = mapped_column(default=0)
    questions_added: Mapped[int] = mapped_column(default=0)
    questions_skipped: Mapped[int] = mapped_column(default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class LLMCall(Base):
    __tablename__ = "llm_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    purpose: Mapped[str] = mapped_column(String)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    latency_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

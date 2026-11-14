"""The study loop: answer, grade, hint, revise, then rate and schedule."""
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from fsrs import Rating
from sqlalchemy.orm import Session

import config
from db.repositories import cards, logs, questions
from domain import Fact, Verdict
from services.grading import Grader, GradeResult
from services.llm.cost import llm_cost
from services.rating import Outcome, rate
from services.scheduler import DrillScheduler


@dataclass
class QuestionRound:
    question_id: int
    hints: list[str] = field(default_factory=list)
    attempts: int = 0
    finished: bool = False
    review_id: int | None = None
    prev_card: tuple[dict, datetime] | None = None  # card as it was before this round's review


@dataclass
class HintStep:
    verdict: Verdict
    hint: str
    hints_used: int


@dataclass
class FinalResult:
    rating: Rating | None
    verdict: Verdict | None
    surrendered: bool
    flagged: bool
    facts: list[Fact]
    missed: list[Fact]
    next_due: datetime | None


class StudyService:
    def __init__(
        self,
        session: Session,
        grader: Grader,
        scheduler: DrillScheduler,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self._s = session
        self._grader = grader
        self._scheduler = scheduler
        self._clock = clock

    def open_question(self, question_id: int) -> QuestionRound:
        questions.get(self._s, question_id)  # raises if missing
        return QuestionRound(question_id=question_id)

    def submit(self, rnd: QuestionRound, answer: str, claimed_easy: bool = False) -> HintStep | FinalResult:
        self._ensure_open(rnd)
        q = questions.get(self._s, rnd.question_id)
        facts = questions.facts(q)
        answer = answer.strip()

        if len(answer) < config.MIN_ANSWER_CHARS:
            self._log_attempt(rnd, answer, verdict=None, missed=[], hint=None)
            return self._finish(rnd, facts, facts, Outcome(too_short=True, hints_used=len(rnd.hints)))

        graded = self._grader.grade(q.text, facts, answer, list(rnd.hints), config.MAX_HINTS - len(rnd.hints))
        self._log_calls(graded)
        self._log_attempt(rnd, answer, graded.verdict, graded.missed, graded.hint)

        if graded.verdict != Verdict.correct and len(rnd.hints) < config.MAX_HINTS:
            rnd.hints.append(graded.hint)
            return HintStep(graded.verdict, graded.hint, len(rnd.hints))

        missed = [facts[i] for i in graded.missed]
        outcome = Outcome(
            verdict=graded.verdict,
            missed_major=any(f.major for f in missed),
            hints_used=len(rnd.hints),
            claimed_easy=claimed_easy,
        )
        return self._finish(rnd, facts, missed, outcome)

    def surrender(self, rnd: QuestionRound) -> FinalResult:
        self._ensure_open(rnd)
        facts = questions.facts(questions.get(self._s, rnd.question_id))
        return self._finish(rnd, facts, facts, Outcome(surrendered=True, hints_used=len(rnd.hints)))

    def flag(self, rnd: QuestionRound, note: str | None = None) -> FinalResult:
        """Mark the question faulty. The answer must not count for scheduling, even after grading."""
        if rnd.review_id is not None:
            self._revert_review(rnd)
        questions.set_flag(self._s, rnd.question_id, note)
        rnd.finished = True
        facts = questions.facts(questions.get(self._s, rnd.question_id))
        return FinalResult(None, None, False, True, facts, [], None)

    # -- internals --

    @staticmethod
    def _ensure_open(rnd: QuestionRound) -> None:
        if rnd.finished:
            raise ValueError("this question round is already finished")

    def _log_attempt(self, rnd, answer, verdict, missed, hint) -> None:
        rnd.attempts += 1
        logs.add_attempt(
            self._s, question_id=rnd.question_id, ordinal=rnd.attempts, answer=answer,
            verdict=verdict.value if verdict else None, missed=missed, hint=hint,
        )

    def _log_calls(self, graded: GradeResult) -> None:
        for call in graded.calls:
            logs.add_llm_call(
                self._s, provider=self._grader.provider_name, model=self._grader.model, purpose="grade",
                input_tokens=call.input_tokens, output_tokens=call.output_tokens,
                cost_usd=llm_cost(self._grader.model, call.input_tokens, call.output_tokens),
                latency_ms=call.latency_ms,
            )

    def _finish(self, rnd: QuestionRound, facts: list[Fact], missed: list[Fact], outcome: Outcome) -> FinalResult:
        now = self._clock()
        rating = rate(outcome)
        card = cards.get(self._s, rnd.question_id)
        before = card.state if card else None
        rnd.prev_card = (card.state, card.due) if card else None
        state, due = self._scheduler.review(before, rating, now)
        cards.upsert(self._s, rnd.question_id, state, due)
        review = logs.add_review(
            self._s, question_id=rnd.question_id, rating=int(rating), hints_used=outcome.hints_used,
            claimed_easy=outcome.claimed_easy, surrendered=outcome.surrendered,
            state_before=before, state_after=state, reviewed_at=now,
        )
        rnd.review_id, rnd.finished = review.id, True
        return FinalResult(rating, outcome.verdict, outcome.surrendered, False, facts, missed, due)

    def _revert_review(self, rnd: QuestionRound) -> None:
        from db.models import Review

        if rnd.prev_card is None:
            cards.delete(self._s, rnd.question_id)
        else:
            cards.upsert(self._s, rnd.question_id, *rnd.prev_card)
        self._s.delete(self._s.get(Review, rnd.review_id))
        self._s.flush()
        rnd.review_id = None

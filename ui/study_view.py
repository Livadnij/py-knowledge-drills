"""Answer one question at a time. All grading runs on worker threads."""
from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from db.session import session_scope
from services.editing import get_question
from services.grading import Grader, GradingError
from services.queue import build_queue
from services.scheduler import DrillScheduler
from services.study import FinalResult, HintStep, QuestionRound, StudyService
from ui.workers import run_in_thread


class StudyView(QWidget):
    finished = Signal()  # user wants to go back to the area picker
    edit_requested = Signal(int)  # question id

    def __init__(self, session_factory, provider, area_id: int, parent=None):
        super().__init__(parent)
        self._factory = session_factory
        self._provider = provider
        self._scheduler = DrillScheduler()
        self._queue: list[int] = []
        self._index = 0
        self._round: QuestionRound | None = None

        # Callbacks from worker threads may arrive after this widget is gone.
        self._alive = [True]
        self.destroyed.connect(lambda *_a, alive=self._alive: alive.__setitem__(0, False))

        self.question_label = QLabel()
        self.question_label.setWordWrap(True)
        self.feedback_label = QLabel()
        self.feedback_label.setWordWrap(True)
        self.answer_edit = QPlainTextEdit()
        self.answer_edit.setPlaceholderText("Type your answer…")
        self.easy_check = QCheckBox("This was easy")
        self.submit_button = QPushButton("Submit")
        self.surrender_button = QPushButton("Surrender")
        self.flag_note_edit = QLineEdit()
        self.flag_note_edit.setPlaceholderText("What is wrong with this question? (optional)")
        self.flag_button = QPushButton("Faulty question")
        self.result_view = QTextBrowser()
        self.next_button = QPushButton("Next")
        self.edit_button = QPushButton("Edit question")
        self.back_button = QPushButton("Back to areas")

        answer_row = QHBoxLayout()
        for w in (self.easy_check, self.submit_button, self.surrender_button):
            answer_row.addWidget(w)
        answer_row.addStretch()
        flag_row = QHBoxLayout()
        flag_row.addWidget(self.flag_note_edit, 1)
        flag_row.addWidget(self.flag_button)
        nav_row = QHBoxLayout()
        for w in (self.back_button, self.edit_button):
            nav_row.addWidget(w)
        nav_row.addStretch()
        nav_row.addWidget(self.next_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.question_label)
        layout.addWidget(self.answer_edit, 1)
        layout.addWidget(self.feedback_label)
        layout.addLayout(answer_row)
        layout.addWidget(self.result_view, 2)
        layout.addLayout(flag_row)
        layout.addLayout(nav_row)

        self.submit_button.clicked.connect(self._submit)
        self.surrender_button.clicked.connect(self._surrender)
        self.flag_button.clicked.connect(self._flag)
        self.next_button.clicked.connect(self._next)
        self.edit_button.clicked.connect(lambda: self.edit_requested.emit(self._round.question_id))
        self.back_button.clicked.connect(self.finished)

        with session_scope(self._factory) as s:
            self._queue = build_queue(s, area_id, datetime.now(), self._scheduler)
        self._load_current()

    # -- states --

    def _set_state(self, state: str) -> None:
        answering = state == "answering"
        for w in (self.answer_edit, self.easy_check, self.submit_button, self.surrender_button):
            w.setVisible(answering)
        for w in (self.flag_note_edit, self.flag_button):
            w.setVisible(state in ("answering", "final"))
        self.result_view.setVisible(state in ("final", "flagged"))
        for w in (self.next_button, self.edit_button):
            w.setVisible(state in ("final", "flagged"))
        self.back_button.setVisible(True)

    def _set_busy(self, busy: bool) -> None:
        for w in (self.answer_edit, self.easy_check, self.submit_button, self.surrender_button,
                  self.flag_button, self.flag_note_edit, self.next_button, self.edit_button):
            w.setEnabled(not busy)

    def _load_current(self) -> None:
        self.feedback_label.clear()
        self.result_view.clear()
        if not self._queue:
            self.question_label.setText("Nothing to study in this area right now.")
            self._set_state("empty")
            return
        if self._index >= len(self._queue):
            self.question_label.setText("Session complete. You can stop now or come back later.")
            self._set_state("complete")
            return
        qid = self._queue[self._index]
        with session_scope(self._factory) as s:
            text = get_question(s, qid).text
        self.question_label.setText(f"[{self._index + 1}/{len(self._queue)}] {text}")
        self._round = QuestionRound(question_id=qid)
        self.answer_edit.clear()
        self.easy_check.setChecked(False)
        self.flag_note_edit.clear()
        self._set_state("answering")
        self.answer_edit.setFocus()

    def _next(self) -> None:
        self._index += 1
        self._load_current()

    # -- actions (each runs the service on a worker thread) --

    def _guard(self, fn):
        alive = self._alive
        return lambda arg: fn(arg) if alive[0] else None

    def _run(self, action) -> None:
        provider, factory, scheduler = self._provider, self._factory, self._scheduler

        def work():
            with session_scope(factory) as s:
                return action(StudyService(s, Grader(provider), scheduler))

        self._set_busy(True)
        run_in_thread(work, self._guard(self._on_result), self._guard(self._on_error))

    def _submit(self) -> None:
        rnd, answer, easy = self._round, self.answer_edit.toPlainText(), self.easy_check.isChecked()
        self.feedback_label.setText("Grading…")
        self._run(lambda svc: svc.submit(rnd, answer, claimed_easy=easy))

    def _surrender(self) -> None:
        rnd = self._round
        self._run(lambda svc: svc.surrender(rnd))

    def _flag(self) -> None:
        rnd, note = self._round, self.flag_note_edit.text().strip() or None
        self._run(lambda svc: svc.flag(rnd, note))

    def _on_error(self, exc: Exception) -> None:
        self._set_busy(False)
        if isinstance(exc, GradingError):
            self.feedback_label.setText(f"{exc}. Your answer is kept: press Submit to retry, or Surrender.")
        else:
            self.feedback_label.setText(f"Something went wrong: {exc}")

    def _on_result(self, result: HintStep | FinalResult) -> None:
        self._set_busy(False)
        if isinstance(result, HintStep):
            self.feedback_label.setText(
                f"Verdict: {result.verdict.value}. Hint {result.hints_used}: {result.hint}\n"
                "Revise your answer and submit again."
            )
            return
        self._show_final(result)

    def _show_final(self, res: FinalResult) -> None:
        lines: list[str] = []
        if res.flagged:
            self.feedback_label.setText("Flagged as faulty. This answer does not count. Fix it with Edit or from the Flagged list.")
        else:
            self.feedback_label.clear()
            if res.surrendered:
                lines.append("Surrendered.")
            elif res.verdict:
                lines.append(f"Verdict: {res.verdict.value}")
            lines.append(f"Rating: {res.rating.name}")
            if res.missed:
                lines += ["", "Missed:"] + [f"  - {f.text}" for f in res.missed]
        lines += ["", "Checklist:"] + [f"  {'*' if f.major else '-'} {f.text}" for f in res.facts]
        if res.next_due:
            lines += ["", f"Next due: {res.next_due:%Y-%m-%d}"]
        self.result_view.setPlainText("\n".join(lines).strip())
        self._set_state("flagged" if res.flagged else "final")

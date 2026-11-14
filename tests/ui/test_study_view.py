import threading
from datetime import datetime

from PySide6.QtCore import Qt

from db.models import Review
from db.repositories import areas, questions
from db.session import session_scope
from domain import Fact
from services.llm.base import LLMError, LLMResult
from services.llm.fake import FakeProvider
from ui.study_view import StudyView

FACTS = [Fact("Optimistic locking uses a version column."), Fact("Pessimistic locking uses SELECT FOR UPDATE.", True)]
ANSWER = "Optimistic locking checks a version before updating."
HINT = "Think about who has to wait."


def _seed(factory, n=1, started=True):
    with session_scope(factory) as s:
        a = areas.create(s, "db", "DB")
        if started:
            areas.mark_started(s, a.id, datetime.now())
        ids = [questions.create(s, area_id=a.id, text=f"Question {i}?", facts=FACTS).id for i in range(n)]
        return a.id, ids


def _view(qtbot, factory, provider, area_id):
    view = StudyView(factory, provider, area_id)
    qtbot.addWidget(view)
    view.show()
    return view


def _correct():
    return {"verdict": "correct", "missed": [], "hint": None}


def _partial():
    return {"verdict": "partial", "missed": [1], "hint": HINT}


def _answer_and_submit(qtbot, view, text=ANSWER):
    view.answer_edit.setPlainText(text)
    qtbot.mouseClick(view.submit_button, Qt.MouseButton.LeftButton)


def _wait_final(qtbot, view):
    qtbot.waitUntil(lambda: view.result_view.isVisible(), timeout=3000)


def test_correct_answer_shows_final_result(qtbot, factory):
    area_id, _ = _seed(factory)
    view = _view(qtbot, factory, FakeProvider([_correct()]), area_id)
    assert "Question 0?" in view.question_label.text()
    _answer_and_submit(qtbot, view)
    _wait_final(qtbot, view)
    text = view.result_view.toPlainText()
    assert "Good" in text and "Next due" in text
    assert FACTS[0].text in text  # checklist is revealed at the end
    assert view.next_button.isVisible() and view.edit_button.isVisible()


def test_partial_shows_verdict_and_hint_then_revision_works(qtbot, factory):
    area_id, _ = _seed(factory)
    view = _view(qtbot, factory, FakeProvider([_partial(), _correct()]), area_id)
    _answer_and_submit(qtbot, view)
    qtbot.waitUntil(lambda: HINT in view.feedback_label.text(), timeout=3000)
    assert "partial" in view.feedback_label.text().lower()
    assert view.answer_edit.toPlainText() == ANSWER and view.submit_button.isEnabled()
    _answer_and_submit(qtbot, view, ANSWER + " And pessimistic locking uses SELECT FOR UPDATE.")
    _wait_final(qtbot, view)
    assert "Hard" in view.result_view.toPlainText()


def test_missed_facts_hidden_until_final(qtbot, factory):
    area_id, _ = _seed(factory)
    view = _view(qtbot, factory, FakeProvider([_partial()]), area_id)
    _answer_and_submit(qtbot, view)
    qtbot.waitUntil(lambda: HINT in view.feedback_label.text(), timeout=3000)
    assert view.result_view.isHidden()
    assert all(f.text not in view.feedback_label.text() for f in FACTS)


def test_surrender_shows_checklist(qtbot, factory):
    area_id, _ = _seed(factory)
    view = _view(qtbot, factory, FakeProvider([]), area_id)
    qtbot.mouseClick(view.surrender_button, Qt.MouseButton.LeftButton)
    _wait_final(qtbot, view)
    text = view.result_view.toPlainText()
    assert "Again" in text and FACTS[1].text in text


def test_flag_finishes_question_without_rating(qtbot, factory):
    area_id, (qid,) = _seed(factory)
    view = _view(qtbot, factory, FakeProvider([]), area_id)
    view.flag_note_edit.setText("checklist is odd")
    qtbot.mouseClick(view.flag_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: view.next_button.isVisible(), timeout=3000)
    assert "flagged" in view.feedback_label.text().lower()
    with session_scope(factory) as s:
        q = questions.get(s, qid)
        assert (q.flagged, q.flag_note) == (True, "checklist is odd")
        assert s.query(Review).count() == 0


def test_grading_error_keeps_answer_and_allows_retry(qtbot, factory):
    area_id, _ = _seed(factory)
    provider = FakeProvider([LLMError("down"), LLMError("down"), _correct()])
    view = _view(qtbot, factory, provider, area_id)
    _answer_and_submit(qtbot, view)
    qtbot.waitUntil(lambda: "Grading failed" in view.feedback_label.text(), timeout=3000)
    assert view.answer_edit.toPlainText() == ANSWER and view.submit_button.isEnabled()
    qtbot.mouseClick(view.submit_button, Qt.MouseButton.LeftButton)
    _wait_final(qtbot, view)


def test_empty_queue_message(qtbot, factory):
    area_id, _ = _seed(factory, n=0)
    view = _view(qtbot, factory, FakeProvider([]), area_id)
    assert "nothing to study" in view.question_label.text().lower()
    assert not view.submit_button.isVisible() and view.back_button.isVisible()


def test_next_moves_on_and_session_completes(qtbot, factory):
    area_id, _ = _seed(factory, n=2)
    view = _view(qtbot, factory, FakeProvider([_correct(), _correct()]), area_id)
    _answer_and_submit(qtbot, view)
    _wait_final(qtbot, view)
    qtbot.mouseClick(view.next_button, Qt.MouseButton.LeftButton)
    assert "Question 1?" in view.question_label.text() and view.result_view.isHidden()
    _answer_and_submit(qtbot, view)
    _wait_final(qtbot, view)
    qtbot.mouseClick(view.next_button, Qt.MouseButton.LeftButton)
    assert "complete" in view.question_label.text().lower()


class _SlowProvider:
    name, model = "slow", "slow-1"

    def __init__(self):
        self.release = threading.Event()
        self.entered = threading.Event()

    def complete_json(self, system, user, schema):
        self.entered.set()
        self.release.wait(5)
        return LLMResult(_correct(), 1, 1, 1)


def test_closing_during_worker_call_does_not_crash(qtbot, factory):
    area_id, _ = _seed(factory)
    provider = _SlowProvider()
    with qtbot.capture_exceptions() as exceptions:
        view = _view(qtbot, factory, provider, area_id)
        _answer_and_submit(qtbot, view)
        assert provider.entered.wait(3)
        view.close()
        view.deleteLater()
        provider.release.set()
        qtbot.wait(300)
    assert exceptions == []


def test_flag_after_grading_reverts_the_review(qtbot, factory):
    area_id, (qid,) = _seed(factory)
    view = _view(qtbot, factory, FakeProvider([_correct()]), area_id)
    _answer_and_submit(qtbot, view)
    _wait_final(qtbot, view)
    assert view.flag_button.isVisible()
    qtbot.mouseClick(view.flag_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "flagged" in view.feedback_label.text().lower(), timeout=3000)
    assert not view.flag_button.isVisible() and view.next_button.isVisible()
    with session_scope(factory) as s:
        from db.repositories import cards

        assert s.query(Review).count() == 0 and cards.get(s, qid) is None
        assert questions.get(s, qid).flagged

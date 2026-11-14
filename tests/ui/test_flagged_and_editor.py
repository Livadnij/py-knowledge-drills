from datetime import datetime

from fsrs import Rating
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from db.repositories import areas, cards, questions
from db.session import session_scope
from domain import Fact
from services.scheduler import DrillScheduler
from ui.editor_dialog import EditorDialog
from ui.flagged_view import FlaggedView

FACTS = [Fact("Old fact one."), Fact("Old fact two.", True)]


def _seed_flagged(factory, note="checklist is wrong", with_card=True):
    with session_scope(factory) as s:
        a = areas.create(s, "db", "DB")
        q = questions.create(s, area_id=a.id, text="Old text?", facts=FACTS, level=2)
        questions.set_flag(s, q.id, note)
        if with_card:
            state, due = DrillScheduler().review(None, Rating.Good, datetime(2026, 11, 1))
            cards.upsert(s, q.id, state, due)
        return q.id


def _click(qtbot, widget):
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)


def test_flagged_view_lists_notes(qtbot, factory):
    _seed_flagged(factory)
    view = FlaggedView(factory)
    qtbot.addWidget(view)
    assert view.list.count() == 1
    text = view.list.item(0).text()
    assert "Old text?" in text and "checklist is wrong" in text and "DB" in text


def test_retire_removes_row(qtbot, factory):
    _seed_flagged(factory)
    view = FlaggedView(factory)
    qtbot.addWidget(view)
    view.list.setCurrentRow(0)
    _click(qtbot, view.retire_button)
    assert view.list.count() == 0


def test_edit_button_emits_question_id(qtbot, factory):
    qid = _seed_flagged(factory)
    view = FlaggedView(factory)
    qtbot.addWidget(view)
    view.list.setCurrentRow(0)
    with qtbot.waitSignal(view.edit_requested, timeout=1000) as blocker:
        _click(qtbot, view.edit_button)
    assert blocker.args == [qid]


def test_editor_loads_question(qtbot, factory):
    qid = _seed_flagged(factory)
    dlg = EditorDialog(factory, qid)
    qtbot.addWidget(dlg)
    assert dlg.text_edit.toPlainText() == "Old text?"
    assert dlg.level_spin.value() == 2
    assert dlg.facts() == FACTS
    assert dlg.reset_check.isChecked() is False


def test_editor_saves_and_clears_flag_keeping_card(qtbot, factory):
    qid = _seed_flagged(factory)
    dlg = EditorDialog(factory, qid)
    qtbot.addWidget(dlg)
    dlg.text_edit.setPlainText("New text?")
    dlg.facts_table.item(0, 0).setText("New fact one.")
    _click(qtbot, dlg.save_button)
    assert dlg.result() == QDialog.DialogCode.Accepted
    with session_scope(factory) as s:
        q = questions.get(s, qid)
        assert (q.text, q.flagged, q.flag_note) == ("New text?", False, None)
        assert questions.facts(q) == [Fact("New fact one."), Fact("Old fact two.", True)]
        assert cards.get(s, qid) is not None


def test_editor_reset_checkbox_deletes_card_when_ticked(qtbot, factory):
    qid = _seed_flagged(factory)
    dlg = EditorDialog(factory, qid)
    qtbot.addWidget(dlg)
    dlg.reset_check.setChecked(True)
    _click(qtbot, dlg.save_button)
    with session_scope(factory) as s:
        assert cards.get(s, qid) is None


def test_editor_add_remove_and_major_toggle(qtbot, factory):
    qid = _seed_flagged(factory)
    dlg = EditorDialog(factory, qid)
    qtbot.addWidget(dlg)
    _click(qtbot, dlg.add_fact_button)
    dlg.facts_table.item(2, 0).setText("Third fact.")
    dlg.facts_table.item(2, 1).setCheckState(Qt.CheckState.Checked)
    dlg.facts_table.setCurrentCell(0, 0)
    _click(qtbot, dlg.remove_fact_button)
    assert dlg.facts() == [Fact("Old fact two.", True), Fact("Third fact.", True)]


def test_editor_shows_validation_errors_and_stays_open(qtbot, factory):
    qid = _seed_flagged(factory)
    dlg = EditorDialog(factory, qid)
    qtbot.addWidget(dlg)
    dlg.facts_table.item(0, 0).setText("   ")
    _click(qtbot, dlg.save_button)
    assert dlg.result() != QDialog.DialogCode.Accepted
    assert "blank" in dlg.error_label.text()
    with session_scope(factory) as s:
        q = questions.get(s, qid)
        assert q.flagged and q.text == "Old text?"

from ui.area_view import AreaView
from ui.main_window import MainWindow
from services.llm.fake import FakeProvider


def test_main_window_starts_on_area_picker(qtbot, factory):
    win = MainWindow(factory, FakeProvider([]))
    qtbot.addWidget(win)
    assert isinstance(win.stack.currentWidget(), AreaView)
    assert win.windowTitle() == "py-knowledge-drills"


def _seed(factory, flagged=False):
    from datetime import datetime

    from db.repositories import areas, questions
    from db.session import session_scope
    from domain import Fact

    with session_scope(factory) as s:
        a = areas.create(s, "db", "DB")
        q = questions.create(s, area_id=a.id, text="Q?", facts=[Fact("a")])
        if flagged:
            questions.set_flag(s, q.id, "bad")
        return a.id


def _click(qtbot, w):
    from PySide6.QtCore import Qt

    qtbot.mouseClick(w, Qt.MouseButton.LeftButton)


def test_choosing_area_opens_study_view_and_back_returns(qtbot, factory):
    from ui.study_view import StudyView

    _seed(factory)
    win = MainWindow(factory, FakeProvider([]))
    qtbot.addWidget(win)
    win.area_view.list.setCurrentRow(0)
    _click(qtbot, win.area_view.start_button)
    study = win.stack.currentWidget()
    assert isinstance(study, StudyView)
    _click(qtbot, study.back_button)
    assert isinstance(win.stack.currentWidget(), AreaView)
    assert win.stack.indexOf(study) == -1  # discarded, not leaked


def test_flagged_screen_opens_and_returns(qtbot, factory):
    from ui.flagged_view import FlaggedView

    _seed(factory, flagged=True)
    win = MainWindow(factory, FakeProvider([]))
    qtbot.addWidget(win)
    _click(qtbot, win.area_view.flagged_button)
    flagged = win.stack.currentWidget()
    assert isinstance(flagged, FlaggedView) and flagged.list.count() == 1
    _click(qtbot, flagged.back_button)
    assert isinstance(win.stack.currentWidget(), AreaView)


def test_edit_from_flagged_opens_editor_and_refreshes(qtbot, factory):
    from db.models import Question
    from db.session import session_scope
    from ui.editor_dialog import EditorDialog

    _seed(factory, flagged=True)
    win = MainWindow(factory, FakeProvider([]))
    qtbot.addWidget(win)
    _click(qtbot, win.area_view.flagged_button)
    flagged = win.stack.currentWidget()
    flagged.list.setCurrentRow(0)
    _click(qtbot, flagged.edit_button)
    assert isinstance(win.editor_dialog, EditorDialog)
    _click(qtbot, win.editor_dialog.save_button)  # saving clears the flag
    qtbot.waitUntil(lambda: flagged.list.count() == 0, timeout=2000)


def test_import_button_opens_import_dialog(qtbot, factory):
    from ui.import_dialog import ImportDialog

    win = MainWindow(factory, FakeProvider([]))
    qtbot.addWidget(win)
    _click(qtbot, win.area_view.import_button)
    assert isinstance(win.import_dialog, ImportDialog)
    win.import_dialog.close()

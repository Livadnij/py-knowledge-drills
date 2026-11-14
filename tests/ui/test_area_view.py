from datetime import datetime

from db.models import Area
from db.repositories import areas, questions
from db.session import session_scope
from domain import Fact
from ui.area_view import AreaView


def _seed(factory):
    with session_scope(factory) as s:
        a = areas.create(s, "databases", "Databases")
        questions.create(s, area_id=a.id, text="Q1?", facts=[Fact("a")])
        questions.create(s, area_id=a.id, text="Q2?", facts=[Fact("a")])
        areas.create(s, "networking", "Networking")
        return a.id


def test_area_view_lists_summaries(qtbot, factory):
    _seed(factory)
    view = AreaView(factory)
    qtbot.addWidget(view)
    texts = [view.list.item(i).text() for i in range(view.list.count())]
    assert any("Databases" in t and "not started" in t for t in texts)
    assert any("Networking" in t for t in texts)


def test_start_emits_area_chosen_and_marks_started(qtbot, factory):
    area_id = _seed(factory)
    view = AreaView(factory)
    qtbot.addWidget(view)
    view.list.setCurrentRow(0)  # Databases sorts before Networking
    with qtbot.waitSignal(view.area_chosen, timeout=1000) as blocker:
        qtbot.mouseClick(view.start_button, qt_left())
    assert blocker.args == [area_id]
    with session_scope(factory) as s:
        assert s.get(Area, area_id).started_at is not None


def test_start_disabled_without_selection(qtbot, factory):
    _seed(factory)
    view = AreaView(factory)
    qtbot.addWidget(view)
    view.list.setCurrentRow(-1)
    assert not view.start_button.isEnabled()


def test_started_area_shows_counts(qtbot, factory):
    area_id = _seed(factory)
    with session_scope(factory) as s:
        areas.mark_started(s, area_id, datetime.now())
    view = AreaView(factory)
    qtbot.addWidget(view)
    assert "0 due, 2 new" in view.list.item(0).text()


def qt_left():
    from PySide6.QtCore import Qt

    return Qt.MouseButton.LeftButton

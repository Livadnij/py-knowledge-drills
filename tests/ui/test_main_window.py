from ui.area_view import AreaView
from ui.main_window import MainWindow
from services.llm.fake import FakeProvider


def test_main_window_starts_on_area_picker(qtbot, factory):
    win = MainWindow(factory, FakeProvider([]))
    qtbot.addWidget(win)
    assert isinstance(win.stack.currentWidget(), AreaView)
    assert win.windowTitle() == "py-knowledge-drills"

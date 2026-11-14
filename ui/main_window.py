from PySide6.QtWidgets import QMainWindow, QStackedWidget

from ui.area_view import AreaView


class MainWindow(QMainWindow):
    def __init__(self, session_factory, provider, parent=None):
        super().__init__(parent)
        self.setWindowTitle("py-knowledge-drills")
        self.resize(900, 640)
        self._factory = session_factory
        self._provider = provider

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.area_view = AreaView(session_factory)
        self.stack.addWidget(self.area_view)

    def show_area_picker(self) -> None:
        self.area_view.refresh()
        self.stack.setCurrentWidget(self.area_view)

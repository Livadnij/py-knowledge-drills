from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget

from ui.area_view import AreaView
from ui.editor_dialog import EditorDialog
from ui.flagged_view import FlaggedView
from ui.import_dialog import ImportDialog
from ui.study_view import StudyView


class MainWindow(QMainWindow):
    def __init__(self, session_factory, provider, parent=None):
        super().__init__(parent)
        self.setWindowTitle("py-knowledge-drills")
        self.resize(900, 640)
        self._factory = session_factory
        self._provider = provider
        self.editor_dialog: EditorDialog | None = None
        self.import_dialog: ImportDialog | None = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.area_view = AreaView(session_factory)
        self.stack.addWidget(self.area_view)
        self.area_view.area_chosen.connect(self._open_study)
        self.area_view.import_requested.connect(self._open_import)
        self.area_view.flagged_requested.connect(self._open_flagged)

    def show_area_picker(self) -> None:
        self.area_view.refresh()
        self.stack.setCurrentWidget(self.area_view)

    def _show_temporary(self, widget: QWidget) -> None:
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)

    def _discard(self, widget: QWidget) -> None:
        self.stack.removeWidget(widget)
        widget.deleteLater()
        self.show_area_picker()

    def _open_study(self, area_id: int) -> None:
        view = StudyView(self._factory, self._provider, area_id)
        view.finished.connect(lambda: self._discard(view))
        view.edit_requested.connect(self._open_editor)
        self._show_temporary(view)

    def _open_flagged(self) -> None:
        view = FlaggedView(self._factory)
        view.back_requested.connect(lambda: self._discard(view))
        view.edit_requested.connect(lambda qid: self._open_editor(qid, on_done=view.refresh))
        self._show_temporary(view)

    def _open_editor(self, question_id: int, on_done=None) -> None:
        dialog = EditorDialog(self._factory, question_id, self)
        if on_done:
            dialog.accepted.connect(on_done)
        self.editor_dialog = dialog
        dialog.open()

    def _open_import(self) -> None:
        dialog = ImportDialog(self._factory, self)
        dialog.imported.connect(self.area_view.refresh)
        self.import_dialog = dialog
        dialog.open()

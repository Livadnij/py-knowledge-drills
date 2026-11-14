from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from db.session import session_scope
from services.editing import list_flagged, retire_question


class FlaggedView(QWidget):
    edit_requested = Signal(int)
    back_requested = Signal()

    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self._factory = session_factory
        self.list = QListWidget()
        self.edit_button = QPushButton("Edit")
        self.retire_button = QPushButton("Retire")
        self.back_button = QPushButton("Back to areas")
        row = QHBoxLayout()
        row.addWidget(self.back_button)
        row.addStretch()
        row.addWidget(self.edit_button)
        row.addWidget(self.retire_button)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Flagged questions (not scheduled until fixed or retired)"))
        layout.addWidget(self.list)
        layout.addLayout(row)

        self.list.currentRowChanged.connect(self._update_buttons)
        self.edit_button.clicked.connect(self._edit)
        self.retire_button.clicked.connect(self._retire)
        self.back_button.clicked.connect(self.back_requested)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        with session_scope(self._factory) as s:
            for v in list_flagged(s):
                note = f"  — note: {v.flag_note}" if v.flag_note else ""
                item = QListWidgetItem(f"[{v.area_name}] {v.text}{note}")
                item.setData(Qt.ItemDataRole.UserRole, v.id)
                self.list.addItem(item)
        self._update_buttons()

    def _update_buttons(self, *_args) -> None:
        has = self.list.currentRow() >= 0
        self.edit_button.setEnabled(has)
        self.retire_button.setEnabled(has)

    def _current_id(self) -> int | None:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _edit(self) -> None:
        qid = self._current_id()
        if qid is not None:
            self.edit_requested.emit(qid)

    def _retire(self) -> None:
        qid = self._current_id()
        if qid is None:
            return
        with session_scope(self._factory) as s:
            retire_question(s, qid)
        self.refresh()

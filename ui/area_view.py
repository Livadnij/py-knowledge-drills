from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from db.session import session_scope
from services.queue import area_summaries, start_area
from services.scheduler import DrillScheduler


class AreaView(QWidget):
    area_chosen = Signal(int)
    import_requested = Signal()
    flagged_requested = Signal()

    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self._factory = session_factory
        self._scheduler = DrillScheduler()

        self.list = QListWidget()
        self.start_button = QPushButton("Start")
        self.import_button = QPushButton("Import…")
        self.flagged_button = QPushButton("Flagged")

        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button)
        buttons.addStretch()
        buttons.addWidget(self.import_button)
        buttons.addWidget(self.flagged_button)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Pick an area to study"))
        layout.addWidget(self.list)
        layout.addLayout(buttons)

        self.list.currentRowChanged.connect(self._update_buttons)
        self.list.itemDoubleClicked.connect(lambda _item: self._start())
        self.start_button.clicked.connect(self._start)
        self.import_button.clicked.connect(self.import_requested)
        self.flagged_button.clicked.connect(self.flagged_requested)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        with session_scope(self._factory) as s:
            for summary in area_summaries(s, datetime.now(), self._scheduler):
                state = f"{summary.due} due, {summary.new} new" if summary.started else "not started"
                item = QListWidgetItem(f"{summary.name}  —  {state}")
                item.setData(Qt.ItemDataRole.UserRole, summary.id)
                self.list.addItem(item)
        self._update_buttons()

    def _update_buttons(self, *_args) -> None:
        self.start_button.setEnabled(self.list.currentRow() >= 0)

    def _start(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        area_id = item.data(Qt.ItemDataRole.UserRole)
        with session_scope(self._factory) as s:
            start_area(s, area_id, datetime.now())
        self.area_chosen.emit(area_id)

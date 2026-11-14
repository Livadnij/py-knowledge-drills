from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from db.session import session_scope
from domain import Fact
from services.editing import get_question, update_question

_EDITABLE = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
_CHECKABLE = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable


class EditorDialog(QDialog):
    def __init__(self, session_factory, question_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit question")
        self.resize(720, 560)
        self._factory = session_factory
        self._question_id = question_id

        self.text_edit = QPlainTextEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["text", "code"])
        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, 5)
        self.priority_check = QCheckBox("Priority")
        self.facts_table = QTableWidget(0, 2)
        self.facts_table.setHorizontalHeaderLabels(["Fact (one full sentence)", "Major"])
        self.facts_table.horizontalHeader().setStretchLastSection(False)
        self.facts_table.setColumnWidth(0, 540)
        self.add_fact_button = QPushButton("Add fact")
        self.remove_fact_button = QPushButton("Remove selected")
        self.reset_check = QCheckBox("Reset schedule (forget this question's review history)")
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #b00020")
        self.error_label.setWordWrap(True)
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")

        form = QFormLayout()
        form.addRow("Question", self.text_edit)
        form.addRow("Type", self.type_combo)
        form.addRow("Level (1-5)", self.level_spin)
        form.addRow("", self.priority_check)
        fact_buttons = QHBoxLayout()
        fact_buttons.addWidget(self.add_fact_button)
        fact_buttons.addWidget(self.remove_fact_button)
        fact_buttons.addStretch()
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.facts_table, 1)
        layout.addLayout(fact_buttons)
        layout.addWidget(self.reset_check)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)

        self.add_fact_button.clicked.connect(lambda: self._add_row(Fact("")))
        self.remove_fact_button.clicked.connect(self._remove_row)
        self.save_button.clicked.connect(self._save)
        self.cancel_button.clicked.connect(self.reject)
        self._load()

    def _load(self) -> None:
        with session_scope(self._factory) as s:
            view = get_question(s, self._question_id)
        self.text_edit.setPlainText(view.text)
        self.type_combo.setCurrentText(view.type)
        self.level_spin.setValue(view.level)
        self.priority_check.setChecked(view.priority)
        for fact in view.facts:
            self._add_row(fact)

    def _add_row(self, fact: Fact) -> None:
        row = self.facts_table.rowCount()
        self.facts_table.insertRow(row)
        text_item = QTableWidgetItem(fact.text)
        text_item.setFlags(_EDITABLE)
        major_item = QTableWidgetItem()
        major_item.setFlags(_CHECKABLE)
        major_item.setCheckState(Qt.CheckState.Checked if fact.major else Qt.CheckState.Unchecked)
        self.facts_table.setItem(row, 0, text_item)
        self.facts_table.setItem(row, 1, major_item)

    def _remove_row(self) -> None:
        row = self.facts_table.currentRow()
        if row >= 0:
            self.facts_table.removeRow(row)

    def facts(self) -> list[Fact]:
        return [
            Fact(
                self.facts_table.item(r, 0).text(),
                self.facts_table.item(r, 1).checkState() == Qt.CheckState.Checked,
            )
            for r in range(self.facts_table.rowCount())
        ]

    def _save(self) -> None:
        with session_scope(self._factory) as s:
            errors = update_question(
                s,
                self._question_id,
                text=self.text_edit.toPlainText(),
                type=self.type_combo.currentText(),
                level=self.level_spin.value(),
                priority=self.priority_check.isChecked(),
                facts=self.facts(),
                reset_schedule=self.reset_check.isChecked(),
            )
        if errors:
            self.error_label.setText("\n".join(errors))
            return
        self.accept()

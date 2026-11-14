from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout

from db.session import session_scope
from services.importer import ImportReport, import_files
from ui.workers import run_in_thread


def format_report(report: ImportReport) -> str:
    name = Path(report.path).name
    if not report.ok:
        return "\n".join([f"{name}: REJECTED (nothing imported)"] + [f"  {e}" for e in report.errors])
    lines = [f"{name}: {report.questions_added} added, {len(report.skipped)} skipped, "
             f"{report.areas_created} areas created"]
    lines += [f"  {s}" for s in report.skipped]
    return "\n".join(lines)


class ImportDialog(QDialog):
    imported = Signal()

    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import questions")
        self.resize(640, 420)
        self._factory = session_factory
        self._alive = [True]
        self.destroyed.connect(lambda *_a, alive=self._alive: alive.__setitem__(0, False))

        self.choose_button = QPushButton("Choose JSON files…")
        self.close_button = QPushButton("Close")
        self.report_view = QTextBrowser()
        row = QHBoxLayout()
        row.addWidget(self.choose_button)
        row.addStretch()
        row.addWidget(self.close_button)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.report_view)

        self.choose_button.clicked.connect(self._choose)
        self.close_button.clicked.connect(self.accept)

    def _choose(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(self, "Import questions", "", "JSON files (*.json)")
        if names:
            self.import_paths([Path(n) for n in names])

    def import_paths(self, paths: list[Path]) -> None:
        factory, alive = self._factory, self._alive
        self.choose_button.setEnabled(False)

        def work():
            with session_scope(factory) as s:
                return import_files(s, list(paths))

        def done(reports):
            if not alive[0]:
                return
            self.choose_button.setEnabled(True)
            for report in reports:
                self.report_view.append(format_report(report))
            self.imported.emit()

        def failed(exc):
            if not alive[0]:
                return
            self.choose_button.setEnabled(True)
            self.report_view.append(f"Import failed: {exc}")

        run_in_thread(work, done, failed)

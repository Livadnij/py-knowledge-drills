import json
from pathlib import Path

from sqlalchemy import func, select

from db.models import Question
from db.session import session_scope
from ui.import_dialog import ImportDialog

FIX = Path(__file__).parent.parent / "fixtures"


def _count(factory):
    with session_scope(factory) as s:
        return s.scalar(select(func.count()).select_from(Question))


def test_import_dialog_shows_errors_for_bad_file(qtbot, factory):
    dlg = ImportDialog(factory)
    qtbot.addWidget(dlg)
    dlg.import_paths([FIX / "bad_multiple_errors.json"])
    qtbot.waitUntil(lambda: "REJECTED" in dlg.report_view.toPlainText(), timeout=3000)
    text = dlg.report_view.toPlainText()
    assert "questions[0].level" in text and "questions[1].answer" in text
    assert _count(factory) == 0


def test_import_dialog_shows_skipped_on_reimport(qtbot, factory):
    dlg = ImportDialog(factory)
    qtbot.addWidget(dlg)
    dlg.import_paths([FIX / "valid.json"])
    qtbot.waitUntil(lambda: "2 added" in dlg.report_view.toPlainText(), timeout=3000)
    dlg.import_paths([FIX / "valid.json"])
    qtbot.waitUntil(lambda: "2 skipped" in dlg.report_view.toPlainText(), timeout=3000)
    assert "duplicate" in dlg.report_view.toPlainText()
    assert _count(factory) == 2


def test_import_dialog_imports_several_files_and_signals(qtbot, factory, tmp_path):
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"areas": [{"key": "net", "name": "Net"}],
                                 "questions": [{"area": "net", "text": "Q?", "answer": ["a"]}]}))
    dlg = ImportDialog(factory)
    qtbot.addWidget(dlg)
    with qtbot.waitSignal(dlg.imported, timeout=3000):
        dlg.import_paths([FIX / "valid.json", other])
    text = dlg.report_view.toPlainText()
    assert "valid.json" in text and "other.json" in text
    assert _count(factory) == 3

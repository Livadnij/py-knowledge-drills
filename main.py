import sys

from PySide6.QtWidgets import QApplication, QMessageBox

import config
from db.session import make_engine, make_session_factory
from services.llm.base import LLMError
from services.llm.factory import make_provider
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    try:
        provider = make_provider(config.PROVIDER)
    except LLMError as exc:
        QMessageBox.critical(None, "py-knowledge-drills", f"Cannot start the grader:\n{exc}")
        return 1
    factory = make_session_factory(make_engine(config.DB_URL))
    window = MainWindow(factory, provider)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

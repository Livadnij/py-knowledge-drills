"""Run blocking work (LLM calls, DB) off the UI thread and deliver results back on it."""
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _Bridge(QObject):
    """Lives on the UI thread. Emitting its signal from a worker thread queues the call onto the UI thread."""

    deliver = Signal(object, object)

    def __init__(self) -> None:
        super().__init__()
        self.deliver.connect(self._run)

    @Slot(object, object)
    def _run(self, callback: Callable[[Any], None], payload: Any) -> None:
        callback(payload)


_bridge: _Bridge | None = None


def _get_bridge() -> _Bridge:
    global _bridge
    if _bridge is None:
        _bridge = _Bridge()  # must first be created on the UI thread
    return _bridge


class _Task(QRunnable):
    def __init__(self, fn, on_result, on_error, bridge: _Bridge):
        super().__init__()
        self._fn, self._on_result, self._on_error, self._bridge = fn, on_result, on_error, bridge

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 - delivered to the caller
            self._bridge.deliver.emit(self._on_error, exc)
        else:
            self._bridge.deliver.emit(self._on_result, result)


def run_in_thread(
    fn: Callable[[], Any],
    on_result: Callable[[Any], None],
    on_error: Callable[[Exception], None],
) -> None:
    """Call from the UI thread. `fn` runs on a pool thread and must open its own DB session."""
    QThreadPool.globalInstance().start(_Task(fn, on_result, on_error, _get_bridge()))

import threading

from ui.workers import run_in_thread


def test_worker_delivers_result_on_main_thread(qtbot):
    seen = {}

    def work():
        seen["work_thread"] = threading.current_thread()
        return 41 + 1

    def done(value):
        seen["value"] = value
        seen["cb_thread"] = threading.current_thread()

    run_in_thread(work, done, lambda e: seen.setdefault("error", e))
    qtbot.waitUntil(lambda: "value" in seen, timeout=3000)
    assert seen["value"] == 42
    assert seen["cb_thread"] is threading.main_thread()
    assert seen["work_thread"] is not threading.main_thread()


def test_worker_delivers_error(qtbot):
    seen = {}

    def boom():
        raise RuntimeError("nope")

    run_in_thread(boom, lambda v: seen.setdefault("value", v), lambda e: seen.setdefault("error", e))
    qtbot.waitUntil(lambda: "error" in seen, timeout=3000)
    assert isinstance(seen["error"], RuntimeError) and "value" not in seen

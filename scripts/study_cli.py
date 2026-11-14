"""Throwaway terminal front-end over the services, for trying real study before the UI exists.

    uv run python -m scripts.study_cli import questions.json more.json
    uv run python -m scripts.study_cli areas
    uv run python -m scripts.study_cli study databases

While answering: /surrender, /flag <note>, /easy <answer>, /quit.
"""
import argparse
from datetime import datetime
from pathlib import Path

import config
from db.repositories import areas as area_repo
from db.session import make_engine, make_session_factory, session_scope
from services.editing import get_question
from services.grading import Grader, GradingError
from services.importer import import_files
from services.llm.factory import make_provider
from services.queue import area_summaries, build_queue, start_area
from services.scheduler import DrillScheduler
from services.study import FinalResult, HintStep, StudyService


def _print_final(res: FinalResult, print_fn) -> None:
    if res.flagged:
        print_fn("Flagged as faulty. Fix it later in the editor.")
        return
    if res.surrendered:
        print_fn("Surrendered.")
    elif res.verdict:
        print_fn(f"Verdict: {res.verdict.value}")
    print_fn(f"Rating: {res.rating.name}")
    if res.missed:
        print_fn("Missed:")
        for fact in res.missed:
            print_fn(f"  - {fact.text}")
    print_fn("Checklist:")
    for fact in res.facts:
        print_fn(f"  {'*' if fact.major else '-'} {fact.text}")
    print_fn(f"Next due: {res.next_due:%Y-%m-%d}")


def _study(session, area_key, provider, input_fn, print_fn, clock) -> int:
    area = area_repo.get_by_key(session, area_key)
    if area is None:
        print_fn(f"Unknown area '{area_key}'.")
        return 1
    scheduler = DrillScheduler()
    start_area(session, area.id, clock())
    queue = build_queue(session, area.id, clock(), scheduler)
    session.commit()
    if not queue:
        print_fn(f"Nothing to study in {area.name} right now.")
        return 0

    service = StudyService(session, Grader(provider), scheduler, clock=clock)
    for qid in queue:
        view = get_question(session, qid)
        rnd = service.open_question(qid)
        print_fn(f"\n[{area.name} | level {view.level}] {view.text}")
        while True:
            raw = input_fn("> ").strip()
            if raw == "/quit":
                return 0
            try:
                if raw == "/surrender":
                    result = service.surrender(rnd)
                elif raw.startswith("/flag"):
                    result = service.flag(rnd, raw[5:].strip() or None)
                else:
                    easy = raw.startswith("/easy ")
                    result = service.submit(rnd, raw[6:] if easy else raw, claimed_easy=easy)
            except GradingError as exc:
                print_fn(f"{exc}. Try again, or /surrender.")
                continue
            session.commit()
            if isinstance(result, HintStep):
                print_fn(f"Verdict: {result.verdict.value}. Hint {result.hints_used}: {result.hint}")
                continue
            _print_final(result, print_fn)
            break
    return 0


def main(
    argv: list[str] | None = None,
    input_fn=input,
    print_fn=print,
    provider=None,
    session_factory=None,
    clock=datetime.now,
) -> int:
    parser = argparse.ArgumentParser(prog="study_cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("import").add_argument("files", nargs="+", type=Path)
    sub.add_parser("areas")
    sub.add_parser("study").add_argument("area_key")
    args = parser.parse_args(argv)

    factory = session_factory or make_session_factory(make_engine(config.DB_URL))
    with session_scope(factory) as session:
        if args.cmd == "import":
            code = 0
            for report in import_files(session, args.files):
                if report.ok:
                    print_fn(f"{report.path}: {report.questions_added} added, {len(report.skipped)} skipped, {report.areas_created} areas created")
                    for s in report.skipped:
                        print_fn(f"  skipped {s}")
                else:
                    code = 1
                    print_fn(f"{report.path}: REJECTED")
                    for e in report.errors:
                        print_fn(f"  {e}")
            return code
        if args.cmd == "areas":
            for s in area_summaries(session, clock(), DrillScheduler()):
                state = f"{s.due} due, {s.new} new" if s.started else "not started"
                print_fn(f"{s.key}\t{s.name}\t{state}")
            return 0
        return _study(session, args.area_key, provider or make_provider(config.PROVIDER), input_fn, print_fn, clock)


if __name__ == "__main__":
    raise SystemExit(main())

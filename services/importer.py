"""Import areas and questions from JSON files, completely or not at all."""
import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from db.repositories import areas, logs, questions
from services.validation import validate_area, validate_question


@dataclass
class ImportReport:
    path: str
    ok: bool
    areas_created: int = 0
    questions_added: int = 0
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _rejected(path: Path, errors: list[str]) -> ImportReport:
    return ImportReport(path=str(path), ok=False, errors=errors)


def import_file(session: Session, path: Path) -> ImportReport:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _rejected(path, [f"{path.name}: cannot read JSON ({exc})"])
    if not isinstance(data, dict):
        return _rejected(path, ["top level must be an object with 'areas' and/or 'questions'"])

    errors: list[str] = []
    new_areas: list[dict] = []
    for i, raw in enumerate(data.get("areas", [])):
        area, errs = validate_area(raw, f"areas[{i}]")
        errors += errs
        if area:
            new_areas.append(area)

    parsed = []
    for i, raw in enumerate(data.get("questions", [])):
        q, errs = validate_question(raw, f"questions[{i}]")
        errors += errs
        if q:
            parsed.append((i, q))

    known_keys = {a["key"] for a in new_areas} | {a.key for a in areas.list_all(session)}
    for i, q in parsed:
        if q.area not in known_keys:
            errors.append(f"questions[{i}].area: unknown area '{q.area}'")
    if errors:
        return _rejected(path, errors)

    report = ImportReport(path=str(path), ok=True)
    with session.begin_nested():
        for a in new_areas:
            if areas.get_by_key(session, a["key"]) is None:
                areas.create(session, a["key"], a["name"], a["description"])
                report.areas_created += 1
        for i, q in parsed:
            area = areas.get_by_key(session, q.area)
            if questions.find_duplicate(session, area.id, q.text, q.external_id):
                report.skipped.append(f"questions[{i}]: duplicate: {q.text}")
                continue
            questions.create(
                session, area_id=area.id, text=q.text, facts=q.facts, type=q.type,
                level=q.level, priority=q.priority, external_id=q.external_id,
            )
            report.questions_added += 1
        logs.add_import(
            session, filename=path.name, areas_created=report.areas_created,
            questions_added=report.questions_added, questions_skipped=len(report.skipped),
        )
    return report


def import_files(session: Session, paths: list[Path]) -> list[ImportReport]:
    return [import_file(session, p) for p in paths]

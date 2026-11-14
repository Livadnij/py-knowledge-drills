"""Validation shared by the importer and the question editor."""
import re
from dataclasses import dataclass

from domain import Fact

AREA_KEY_RE = re.compile(r"^[a-z0-9-]+$")
TYPES = ("text", "code")


@dataclass
class QuestionData:
    area: str
    text: str
    type: str
    level: int
    priority: bool
    facts: list[Fact]
    external_id: str | None


def validate_area(raw: object, where: str = "area") -> tuple[dict | None, list[str]]:
    if not isinstance(raw, dict):
        return None, [f"{where}: must be an object"]
    errors: list[str] = []
    key, name = raw.get("key"), raw.get("name")
    if not isinstance(key, str) or not AREA_KEY_RE.match(key):
        errors.append(f"{where}.key: must be lowercase letters, digits and hyphens")
    if not isinstance(name, str) or not name.strip():
        errors.append(f"{where}.name: required")
    description = raw.get("description", "")
    if not isinstance(description, str):
        errors.append(f"{where}.description: must be a string")
    if errors:
        return None, errors
    return {"key": key, "name": name.strip(), "description": description}, []


def _fact(item: object, where: str) -> tuple[Fact | None, str | None]:
    if isinstance(item, str):
        text, major = item, False
    elif isinstance(item, dict):
        text, major = item.get("fact"), item.get("major", False)
        if not isinstance(major, bool):
            return None, f"{where}.major: must be true or false"
    else:
        return None, f"{where}: must be a string or an object with 'fact'"
    if not isinstance(text, str) or not text.strip():
        return None, f"{where}: fact text must not be blank"
    return Fact(text.strip(), major), None


def validate_question(raw: object, where: str = "question") -> tuple[QuestionData | None, list[str]]:
    if not isinstance(raw, dict):
        return None, [f"{where}: must be an object"]
    errors: list[str] = []

    area = raw.get("area")
    if not isinstance(area, str) or not area:
        errors.append(f"{where}.area: required")
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        errors.append(f"{where}.text: required")
    qtype = raw.get("type", "text")
    if qtype not in TYPES:
        errors.append(f"{where}.type: must be 'text' or 'code'")
    level = raw.get("level", 3)
    if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 5:
        errors.append(f"{where}.level: must be a whole number from 1 to 5")
    priority = raw.get("priority", False)
    if not isinstance(priority, bool):
        errors.append(f"{where}.priority: must be true or false")
    external_id = raw.get("external_id")
    if external_id is not None and not isinstance(external_id, str):
        errors.append(f"{where}.external_id: must be a string")

    facts: list[Fact] = []
    answer = raw.get("answer")
    if not isinstance(answer, list) or not answer:
        errors.append(f"{where}.answer: must be a non-empty list of facts")
    else:
        for i, item in enumerate(answer):
            fact, error = _fact(item, f"{where}.answer[{i}]")
            if error:
                errors.append(error)
            else:
                facts.append(fact)

    if errors:
        return None, errors
    return QuestionData(area, text.strip(), qtype, level, priority, facts, external_id), []

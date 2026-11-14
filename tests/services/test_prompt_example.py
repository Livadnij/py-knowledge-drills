import json
import re
from pathlib import Path

from services.validation import validate_area, validate_question

PROMPT = Path(__file__).parent.parent.parent / "prompts" / "generate_questions.md"


def test_example_in_prompt_is_valid():
    block = re.search(r"```json\n(.*?)```", PROMPT.read_text(encoding="utf-8"), re.S).group(1)
    data = json.loads(block)
    for i, a in enumerate(data["areas"]):
        assert validate_area(a, f"areas[{i}]")[1] == []
    for i, q in enumerate(data["questions"]):
        assert validate_question(q, f"questions[{i}]")[1] == []

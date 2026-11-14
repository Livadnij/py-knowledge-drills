"""Grader quality gate: run a fixed set of answers through a provider and check strictness.

    uv run python -m evals.run_eval --provider anthropic

Exit code is non-zero if any answer that should not be correct is graded correct
(the grader must never be lenient), or if fewer than EVAL_MIN_PASS of the cases match.
"""
import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import config
from domain import Fact
from services.grading import Grader, GradeResult, GradingError
from services.llm.factory import make_provider

EVAL_MIN_PASS = 0.9
DEFAULT_CASES = Path(__file__).parent / "cases.json"


@dataclass
class EvalCase:
    id: str
    question: str
    facts: list[Fact]
    answer: str
    hints_given: list[str]
    expect: list[str]  # acceptable verdicts
    expect_missed_major: bool | None


@dataclass
class EvalReport:
    passed: int = 0
    total: int = 0
    false_correct: list[str] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def load_cases(path: Path) -> list[EvalCase]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        EvalCase(
            id=c["id"],
            question=c["question"],
            facts=[Fact(f["text"], f["major"]) for f in c["facts"]],
            answer=c["answer"],
            hints_given=c.get("hints_given", []),
            expect=c["expect"],
            expect_missed_major=c.get("expect_missed_major"),
        )
        for c in raw
    ]


def score(results: list[tuple[EvalCase, GradeResult | None]]) -> EvalReport:
    report = EvalReport(total=len(results))
    for case, result in results:
        if result is None:
            report.mismatches.append(f"{case.id}: grading error")
            continue
        verdict = result.verdict.value
        if verdict == "correct" and "correct" not in case.expect:
            report.false_correct.append(case.id)
        missed_major = any(case.facts[i].major for i in result.missed)
        if verdict not in case.expect:
            report.mismatches.append(f"{case.id}: expected {case.expect}, got {verdict}")
        elif case.expect_missed_major is not None and verdict != "correct" and missed_major != case.expect_missed_major:
            report.mismatches.append(f"{case.id}: expected missed_major={case.expect_missed_major}, got {missed_major}")
        else:
            report.passed += 1
    return report


def run(cases: list[EvalCase], grader: Grader) -> list[tuple[EvalCase, GradeResult | None]]:
    results = []
    for case in cases:
        try:
            result = grader.grade(
                case.question, case.facts, case.answer, case.hints_given,
                config.MAX_HINTS - len(case.hints_given),
            )
        except GradingError:
            result = None
        results.append((case, result))
    return results


def main(argv: list[str] | None = None, provider_factory: Callable = make_provider) -> int:
    parser = argparse.ArgumentParser(description="Evaluate grader strictness")
    parser.add_argument("--provider", default=config.PROVIDER)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    report = score(run(cases, Grader(provider_factory(args.provider))))

    print(f"provider={args.provider}  pass {report.passed}/{report.total} ({report.rate:.0%})")
    for line in report.mismatches:
        print("  MISMATCH", line)
    for case_id in report.false_correct:
        print("  FALSE-CORRECT (too lenient)", case_id)
    ok = not report.false_correct and report.rate >= EVAL_MIN_PASS
    print("GATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

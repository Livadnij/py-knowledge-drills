from pathlib import Path

import pytest

from domain import Fact, Verdict
from evals.run_eval import EvalCase, load_cases, main, score
from services.grading import GradeResult
from services.llm.fake import FakeProvider

CASES = Path(__file__).parent.parent.parent / "evals" / "cases.json"


def _case(expect=("partial",), missed_major=False, facts=None):
    facts = facts or [Fact("minor fact one here."), Fact("major fact two here.", True)]
    return EvalCase("c", "Q?", facts, "answer text", [], list(expect), missed_major)


def _result(verdict, missed):
    return GradeResult(Verdict(verdict), missed, None, [])


def test_load_cases_valid_schema():
    cases = load_cases(CASES)
    assert len(cases) >= 24
    assert len({c.id for c in cases}) == len(cases)
    assert sum("ignore" in c.answer.lower() or "system:" in c.answer.lower() or "grader" in c.answer.lower() for c in cases) >= 3
    kinds = {v for c in cases for v in c.expect}
    assert kinds == {"correct", "partial", "incorrect"}
    assert len({c.question for c in cases}) >= 4


def test_score_flags_false_correct():
    report = score([(_case(), _result("correct", []))])
    assert report.false_correct == ["c"] and report.passed == 0


def test_score_counts_matches_and_checks_missed_major():
    good = (_case(missed_major=False), _result("partial", [0]))
    wrong_major = (_case(missed_major=False), _result("partial", [1]))
    wrong_verdict = (_case(expect=("incorrect",), missed_major=None), _result("partial", [0]))
    report = score([good, wrong_major, wrong_verdict])
    assert (report.passed, report.total) == (1, 3)
    assert len(report.mismatches) == 2 and report.false_correct == []


def _scripted_provider(cases, as_expected=True):
    responses = []
    for c in cases:
        verdict = c.expect[0] if as_expected else "correct"
        if verdict == "correct":
            responses.append({"verdict": "correct", "missed": [], "hint": None})
            continue
        majors = [i for i, f in enumerate(c.facts) if f.major]
        minors = [i for i, f in enumerate(c.facts) if not f.major]
        missed = {True: majors[:1], False: minors[:1], None: [0]}[c.expect_missed_major]
        responses.append({"verdict": verdict, "missed": missed, "hint": "Consider the underlying mechanism."})
    return FakeProvider(responses)


def test_runner_exit_code_zero_when_grader_matches_expectations(capsys):
    cases = load_cases(CASES)
    assert main(["--provider", "fake"], provider_factory=lambda name: _scripted_provider(cases)) == 0
    assert "pass" in capsys.readouterr().out.lower()


def test_runner_exit_code_nonzero_on_false_correct():
    cases = load_cases(CASES)
    code = main(["--provider", "fake"], provider_factory=lambda name: _scripted_provider(cases, as_expected=False))
    assert code != 0


def test_runner_reports_missing_key_without_traceback(capsys):
    from services.llm.base import LLMError

    def no_key(name):
        raise LLMError("OPENAI_API_KEY is not set (put it in .env)")

    assert main(["--provider", "openai"], provider_factory=no_key) == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().out


def test_score_flags_a_hint_that_repeats_an_earlier_one():
    case = _case(expect=("partial",), missed_major=None)
    case.hints_given.append("Think about what happens to the state after it finishes settling.")
    repeated = GradeResult(Verdict.partial, [0], "Consider what happens to the promise's state once it has finished settling.", [])
    fresh = GradeResult(Verdict.partial, [0], "Can a settled state ever go back to pending?", [])
    report = score([(case, repeated), (case, fresh)])
    assert (report.passed, len(report.mismatches)) == (1, 1)
    assert "repeats" in report.mismatches[0]


def test_eval_set_covers_ignored_hint_and_the_promise_regression():
    cases = {c.id: c for c in load_cases(CASES)}
    assert cases["lock-ignored-hint"].hints_given
    promise = cases["promise-states-correct"]
    assert promise.expect == ["correct"] and len(promise.facts) == 1

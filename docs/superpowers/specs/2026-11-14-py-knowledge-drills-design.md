# py-knowledge-drills: design and development plan

## Context and intent
A personal desktop tool for retaining technical knowledge. The user went easy on themselves with self-graded flashcards (Anki), so the core idea is **free-text answers graded by an LLM against a stored fact checklist**, scheduled by FSRS. Secondary goal: a portfolio piece the user fully controls. The README is the v1 spec; this document records what changed or was decided in brainstorming.

## Goals
- Reliable retention: strict, consistent grading; FSRS scheduling in whole days.
- Learning by correction: wrong/shaky answer -> verdict + nudging hint -> revise (up to 3 hints).
- Handle LLM-generated questions with imperfect checklists: flag and minimal in-app editor.
- Portfolio quality: layered code, TDD, migrations, an eval script for the grader, a clear README with screenshots.

## Non-goals (v1)
Mixed sessions across areas, stats, running code answers, disputing a grade, local LLMs, multi-user, mobile, a full "browse all questions" editor, a pre-answer "give me a hint" button.

## Anti-goals
- A lenient grader that makes this no better than self-grading.
- Silent corruption of the schedule by a broken question.
- Hints that state the missing fact.

## Constraints
Python 3.12, uv, PySide6, SQLite + Alembic, py-fsrs. LLM calls on worker threads. UI talks only to services. Provider-agnostic LLM interface.

## Approaches considered
- **A. Layer by layer** (db, services, UI): clean, but grading is unproven until the end.
- **B. Core first, then UI** *(chosen, with TDD)*: services and graders first, eval script, terminal study loop, then PySide6.
- **C. UI first against a fake LLM**: early feel, but grading risk stays hidden under UI code.

## Decisions made by the user
- Question bank is LLM-generated from docs and interview-question lists.
- Faulty questions can be **flagged** during a session; fixed later in a **minimal in-app editor**; the editor has a **"reset schedule" checkbox, default keep history**.
- Hints work as: answer, verdict + one hint, revise; the user chose "verdict + hint" visible after a non-correct attempt.
- **Provider-agnostic LLM interface.**
- **Core first, test-driven.**

## My calls (user should check these)
1. **Facts carry importance.** `answer` items are a string (minor) or `{"fact": "...", "major": true}`. This makes "partial, a major fact missed" deterministic.
2. **Hints are generated per attempt, not stored in advance.** The grader returns verdict, missed fact ids and one hint aimed at the most important missed fact, instructed never to state it. The attempt log replaces "stored hints", so editing a question can't leave stale hints.
3. **Missed facts and the full checklist stay hidden until the loop ends** (correct, 3 hints used, or surrender).
4. **Flagged answer:** the attempt is logged, the card is not updated. Flagged questions are excluded from sessions until fixed. A flag takes an optional one-line note.
5. **Editor scope:** opened from the Flagged list and the post-grading screen. Edits text, type, level, priority and facts with major marks. Saving clears the flag. Re-import never overwrites edits (duplicates are still skipped).
6. **"Claim easy" stays**, upgrading only a correct, no-hint answer to Easy. First thing to cut if it feels like self-grading.
7. **Grader determinism:** temperature 0 where supported; the rating rule is a pure function, so only the verdict can vary. This is documented as a known limit.
8. **Quality gate for the grader:** a versioned eval set of answers (correct, partial-minor, partial-major, wrong, vague bluffing, empty) run by a script against each provider.
9. **The question-generation prompt lives in the repo** (`prompts/generate_questions.md`) and produces valid import JSON.
10. **Cost log** records provider, model, tokens, cost and latency per call, using price constants in `config.py`.

## Rating rule (pure function)
| Situation | Rating |
|---|---|
| Surrendered | Again |
| Final verdict incorrect (including after 3 hints) | Again |
| Final partial, a major fact missed | Again |
| Final partial, only minor facts missed | Hard |
| Correct after one or more hints | Hard |
| Correct, no hints | Good |
| Claimed easy, correct, no hints | Easy |
| Empty/very short answer | Again, no AI call |

## Session rules (unchanged from README)
One area per session; due reviews first, lowest retrievability first; then new questions by lowest level, priority first within a level; no size or daily limit; whole-day scheduling; flagged questions excluded; unstarted areas never scheduled.

## Data model (sketch)
areas, questions (with facts as JSON or a child table, flagged + flag_note, retired), cards (FSRS state), attempts (answer text, verdict, missed fact ids, hint text, order), reviews (rating, card snapshot), imports, llm_calls.

## Development plan (TDD: failing test, minimal code, refactor, at every step)
1. **Foundation.** Project setup, config, SQLAlchemy models, Alembic baseline, repositories. Tests on in-memory SQLite.
2. **Importer.** Validation with all errors reported, atomic import, duplicate skipping, string-or-object facts. Tests use fixture JSON files.
3. **Scheduler and rating rule.** Rating function and FSRS wrapper (whole days, retrievability ordering, session queue). Pure-function tests, including every table row.
4. **LLM interface and fake provider.** `LLMProvider` protocol, structured grading response, cost logging. All later tests use the fake.
5. **Grading service.** Prompt builder, response validation, short-answer shortcut, hint loop state machine (up to 3 hints, surrender, flag). Fully tested with the fake.
6. **Real providers and eval script.** Anthropic and OpenAI adapters, with a small number of marked integration tests; eval set and report. Tune the prompt until strictness is acceptable. **Gate: do not start the UI until this passes.**
7. **Terminal study loop.** Throwaway CLI over the services, so real studying can begin.
8. **PySide6 UI.** Area picker, study view, worker threads, import dialog, Flagged list, editor with reset checkbox. UI tests where practical (pytest-qt), logic stays in services.
9. **Polish.** README with screenshots, backup note, prompt file, `.env.example`.

## Left to the builder
Exact schema, prompt wording, retry/timeout behaviour on LLM errors, the minimum answer length, UI layout details, the eval-set size.

## Verification
- `uv run pytest` green at the end of each step.
- Step 6: eval report shows correct/partial/wrong cases graded as expected on both providers.
- Step 7: a real session end-to-end from import to next due date.
- Step 8: run the app, import a file, finish a session with a hint round, flag a question, fix it in the editor, and confirm the card is kept or reset as chosen.

## Builder check
Read as a builder: the order, interfaces and the gate at step 6 are clear. The open items are the minor ones listed above, which are settled as my calls. No item remains that only the user can answer.

# py-knowledge-drills

A desktop app for learning technical knowledge by areas. Questions come back on an FSRS spaced repetition schedule, and an LLM grades each free-text answer against a stored checklist of facts. A fixed rule turns that grade into the rating, so the rating logic never depends on the model's mood.

Built with Python, PySide6, SQLite and py-fsrs (the `fsrs` package). It's a personal tool for one user.

The point: no self-grading. You type an answer, something else decides how good it was.

## How it works

1. **Pick an area**, like Node Runtime or Databases. An area is started the first time you study it. Questions in areas you haven't started are never scheduled.
2. **Answer one question at a time.** You can surrender at any point.
3. **The LLM grades your answer** fact by fact against the checklist stored with the question. It returns correct, partial or incorrect.
4. **If the answer isn't correct, you get the verdict and one hint**, written from your answer to push you toward the most important thing you missed without stating it. Revise and submit again. You get up to 3 hints. The missed facts and the full checklist stay hidden until the question is over.
5. **The app picks the rating** and FSRS schedules the next review.

| Situation                                          | Rating |
| -------------------------------------------------- | ------ |
| Surrendered                                        | Again  |
| Incorrect, including after all 3 hints             | Again  |
| Partial, a major fact missed                       | Again  |
| Partial, only minor facts missed                   | Hard   |
| Correct, after one or more hints                   | Hard   |
| Correct, no hints                                  | Good   |
| You claimed easy, and it was correct with no hints | Easy   |

Empty or very short answers are rated Again without calling the AI. When a question ends you see the verdict, the missed facts, the full checklist and the next due date.

### Faulty questions

Questions are usually LLM-generated, so some checklists will be wrong. Press **Faulty question** at any time, even after grading. The answer then does not count: the card keeps its old schedule, the question leaves your sessions, and it shows up in the **Flagged** list with your note. Open it in the editor to fix the text, level, priority and facts, then save. Saving clears the flag. A "Reset schedule" checkbox (off by default) throws away the review history if the question changed so much it is a new one.

## Session rules

- One area per session.
- Due reviews come first, the ones you're most likely to have forgotten at the top.
- When nothing in the area is due, questions you've never answered come next, lowest level first. Within the same level, priority questions come first.
- There's no session size and no daily limit. Answer 5 or 25, and stop whenever you want.
- Reviews are scheduled in whole days.
- Flagged and retired questions are never scheduled.

## Setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```
uv sync
copy .env.example .env
uv run alembic upgrade head
uv run main.py
```

Choose the grader in `config.py` (`PROVIDER`) and put its settings in `.env`:

| Provider    | `.env`                                                                 |
| ----------- | ---------------------------------------------------------------------- |
| `anthropic` | `ANTHROPIC_API_KEY`                                                    |
| `openai`    | `OPENAI_API_KEY`                                                       |
| `local`     | `LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL`, `LOCAL_LLM_API_KEY` (optional) |

`local` works with any OpenAI-compatible server (LM Studio, Ollama, vLLM, llama.cpp). Model names for the hosted providers, prices, file paths, `MAX_HINTS` and `MIN_ANSWER_CHARS` are constants in `config.py`.

### Check the grader

Grading strictness is the whole product, so there is an eval set of answers (correct, partial, wrong, vague bluffing, and prompt-injection attempts):

```
uv run python -m evals.run_eval --provider local
```

It fails if any answer that should not be correct is graded correct, or if fewer than 90% of cases match. Run it again whenever you change the model or the grading prompt.

## Adding questions

Questions come in through JSON files: use the Import button and pick one or more files. [`prompts/generate_questions.md`](prompts/generate_questions.md) is a prompt that makes an LLM turn documentation or interview-question lists into a valid file.

```json
{
  "areas": [{ "key": "databases", "name": "Databases", "description": "" }],
  "questions": [
    {
      "area": "databases",
      "type": "text",
      "level": 3,
      "priority": false,
      "external_id": "databases-locking-1",
      "text": "What's the difference between optimistic and pessimistic locking?",
      "answer": [
        "Optimistic locking adds a version column, updates only if the version is unchanged, and retries on conflict.",
        { "fact": "Pessimistic locking locks the row with SELECT FOR UPDATE, so other transactions wait.", "major": true }
      ]
    }
  ]
}
```

- Both sections are optional. An area needs a key of lowercase letters, digits and hyphens, a name, and optional description.
- A question's area must be the key of an existing area or of one defined in the same file. An unknown key rejects the file, so a typo never creates a new area.
- `area`, `text` and `answer` are required. `type` is `text` or `code` and defaults to `text`. `level` is a whole number from 1 to 5 and defaults to 3. `priority` defaults to false. `external_id` is optional.
- `answer` holds a list of facts, each a full sentence. A fact is a plain string (minor) or `{"fact": "...", "major": true}`. A major fact is one the question can't be considered answered without. Grading checks your answer fact by fact.
- A file is imported completely or not at all. Invalid files are rejected with a list of every problem.
- Duplicates in the same area (same text ignoring case and spacing, or same `external_id`) are skipped and reported. Re-importing never overwrites a question you edited.

## Data

The SQLite database lives next to the app and is ignored by git. Back it up before cleaning the folder. It stores areas, questions, FSRS cards, every attempt with its verdict and hint, the review log, imports and a log of every AI call with tokens, cost and latency.

## Project structure

```
config.py        constants for paths, models, prices and limits
main.py          entry point
domain.py        shared types (Fact, Verdict)
db/              models, session and repositories
services/        validation, importer, rating, scheduler, queue, grading,
                 study loop, editing, LLM providers
ui/              windows, views and worker threads
prompts/         the question-generation prompt
evals/           grader quality gate
scripts/         throwaway terminal study loop
migrations/      Alembic migrations
tests/           pytest tests
```

The UI only talks to services. AI calls run on worker threads so the window never freezes. A terminal version of the study loop exists for quick checks: `uv run python -m scripts.study_cli study <area-key>`.

Run the tests with `uv run pytest -m "not integration"`. The two `integration` tests call real APIs and need keys.

## Known limits

- The rating rule is deterministic, but the LLM's verdict can vary between runs of the same answer. The eval set measures how much.
- Flagging after grading restores the card only while the question screen is still open.

## Not in v1

Mixed sessions across all areas, a browse-all-questions editor, rewording questions, stats, running code answers, disputing a grade, multiple users and mobile.

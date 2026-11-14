# py-knowledge-drills

A desktop app for learning technical knowledge by areas. Questions come back on an FSRS spaced repetition schedule, and an AI grades each answer against a stored checklist. A fixed rule turns that grade into the rating, so the same answer always gets the same result.

Built with Python, PySide6, SQLite and py-fsrs. It's a personal tool for one user.

> Status: in development. This README describes the v1 target.

## How it works

1. **Pick an area**, like Node Runtime or Databases. An area is started the first time you study it. Questions in areas you haven't started are never scheduled.
2. **Answer one question at a time.** You can ask for up to 3 hints, or surrender at any point.
3. **The AI grades your answer** against the checklist stored with the question. It returns correct, partial or incorrect, plus the facts you missed.
4. **The app picks the rating** and FSRS schedules the next review.

| Situation                                          | Rating |
| -------------------------------------------------- | ------ |
| Surrendered                                        | Again  |
| Incorrect, including after all 3 hints             | Again  |
| Partial, a major fact missed                       | Again  |
| Partial, only minor facts missed                   | Hard   |
| Correct, with hints                                | Hard   |
| Correct, no hints                                  | Good   |
| You claimed easy, and it was correct with no hints | Easy   |

Empty or very short answers are rated Again without calling the AI. After grading you see the verdict, the missed facts, the full checklist and the next due date.

## Session rules

- One area per session.
- Due reviews come first, the ones you're most likely to have forgotten at the top.
- When nothing in the area is due, questions you've never answered come next, lowest level first. Within the same level, priority questions come first.
- There's no session size and no daily limit. Answer 5 or 25, and stop whenever you want.
- Reviews are scheduled in whole days.

## Setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```
uv sync
copy .env.example .env
uv run alembic upgrade head
uv run main.py
```

Put your LLM API key in `.env`. The model name, file paths and session limits are constants in `config.py`.

## Adding questions

Importing JSON files is the only way areas and questions get into the app at the moment. Use the Import button and pick one or more files.

```json
{
  "areas": [{ "key": "databases", "name": "Databases", "description": "" }],
  "questions": [
    {
      "area": "databases",
      "type": "text",
      "level": 3,
      "priority": false,
      "text": "What's the difference between optimistic and pessimistic locking?",
      "answer": [
        "Optimistic locking adds a version column, updates only if the version is unchanged, and retries on conflict.",
        "Pessimistic locking locks the row with SELECT FOR UPDATE, so other transactions wait."
      ]
    }
  ]
}
```

- Both sections are optional. An area needs a key of lowercase letters, digits and hyphens, a name, and optional description.
- A question's area must be the key of an existing area or of one defined in the same file. An unknown key rejects the file, so a typo never creates a new area.
- `area`, `text` and `answer` are required. `type` is `text` or `code` and defaults to `text`. `level` is a whole number from 1 to 5 and defaults to 3. `priority` defaults to false. `external_id` is optional.
- `answer` holds a list of facts, each a full sentence. Grading checks your answer fact by fact.
- A file is imported completely or not at all. Invalid files are rejected with a list of every problem.
- Duplicates in the same area are skipped and reported.

## Data

The SQLite database lives next to the app and is ignored by git. Back it up before cleaning the folder. It stores areas, questions, FSRS cards, stored hints, the review log, imports and a log of every AI call with tokens, cost and latency.

## Project structure

```
config.py        constants for paths, model, prices and limits
main.py          entry point
db/              models, session and repositories
services/        scheduler, grading, sessions, importer, LLM client
ui/              windows, views and worker threads
migrations/      Alembic migrations
tests/           pytest tests
```

The UI only talks to services. AI calls run on worker threads so the window never freezes.

## Not in v1

Mixed sessions across all areas, an in-app question editor, rewording questions, stats, running code answers, disputing a grade, local LLMs, multiple users and mobile.

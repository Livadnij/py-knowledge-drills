# Generate drill questions

Paste this prompt into an LLM, followed by your source material (documentation, an interview-question list, notes).
Save the reply as a `.json` file and use the app's Import button.

---

You turn source material into study questions for a spaced-repetition app. Output ONLY one JSON object, no commentary.

Rules:
- Each question tests understanding in free text, not recall of a single word. Write it so one short paragraph answers it.
- `answer` is a checklist of facts. Each fact is one complete sentence that could be checked independently against a learner's answer.
- Use 3 to 6 facts per question. Do not pad.
- Mark a fact as major (`{"fact": "...", "major": true}`) only if the question cannot be considered answered without it. All other facts are plain strings.
- `level` is 1 (basic recall) to 5 (deep, tricky, or cross-topic). Use 3 when unsure.
- `priority` is true only for questions that are essential in interviews or daily work.
- `type` is `text`, or `code` when the answer is about what code does or how to write it.
- `area` must be the `key` of an area you define in `areas`. Keys use lowercase letters, digits and hyphens.
- Do not repeat a question. Give each question a stable `external_id` such as `databases-locking-1`.
- Never include the answer, or any fact, inside the question text.

Example of the exact output format:

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

Source material:

# Questions Translation — Design

Date: 2026-07-12
Status: Approved (brainstorm), pending implementation plan

## Goal

Serve trivia questions in multiple languages. Add:
1. A `GET /languages` API reporting which languages have data.
2. An LLM translation workflow (backfill + inline) that reuses the existing
   Azure OpenAI enrichment pattern.

Source language: `en`. Target languages: `de`, `es`, `fr`, `lt`, `ru`, `hi`.

## Context

The system fetches trivia from OpenTDB, enriches/simplifies each question via
Azure OpenAI, embeds and semantically de-duplicates it, then appends it to
`questions.json` (`enrichment.py` background poller). The Flask app (`app.py`)
serves `GET /categories` and `GET /questions`, both bearer-authenticated and
rate limited (10/min).

Each question record today:

```json
{
  "question": "What is the largest ocean on Earth?",
  "answers": ["pacific ocean", "the pacific", "pacific"],
  "wrong_answers": ["Atlantic Ocean", "Indian Ocean", "..."],
  "category": "geography",
  "difficulty": "normal",
  "points": 800,
  "language": "en"
}
```

`answers` are lowercase natural variants used to match the player's typed
answer. `language` is currently always `"en"`.

## Data model

Translations are stored as **new records in the same `questions.json`**, one
per (source question, language). Fields:

- `question`, `answers`, `wrong_answers` — translated.
- `category`, `difficulty`, `points` — **copied unchanged** from the source
  (category is an enum; points/difficulty are properties of the question, not
  the language).
- `language` — the target code.
- `source_id` (new field) — `md5(english_question_text).hexdigest()`, the same
  hash already used to key the embeddings sidecar. Links a translation to its
  English source.

The uniqueness / idempotency key for a translation is `(source_id, language)`.

English records also get `source_id` backfilled (derivable from their own
question text) so every record is uniform.

## Translation module — `translation.py`

Mirrors `enrichment.py` conventions (same `_get_az_client()`, JSON-only system
prompt, shared `_validate_question`, atomic `_persist_question`).

- `TARGET_LANGUAGES = {"de", "es", "fr", "lt", "ru", "hi"}`
- `_translate_question(source_q: dict, lang: str) -> dict`
  - One LLM call per (question, language). Chosen for JSON robustness and
    consistency with the existing per-question call pattern. (Alternative of
    one call returning all languages was rejected as more fragile.)
  - System prompt requirements:
    - Output ONLY a single valid JSON object, no prose/markdown.
    - `question` — natural translation into the target language.
    - `answers` — natural **lowercase** answer variants **in the target
      language** (preserves the answer-matching behavior of the quiz).
    - `wrong_answers` — translated incorrect answers.
  - Copies `category`, `difficulty`, `points`, `source_id` from the source and
    sets `language` to the target.
- Translations **skip embedding and semantic dedup** — they are translations of
  already-deduped questions. Idempotency is purely `(source_id, language)`
  existence.

## Entry points

### Backfill script — `translate_questions.py`

- Loads `questions.json`, isolates English (`language == "en"`) records.
- Builds the set of existing `(source_id, language)` pairs already present.
- For each English question × each target language not yet present, calls
  `_translate_question`, validates, and appends via `_persist_question`.
- Idempotent and interrupt-safe: re-running resumes and only fills gaps.
- Optional flags: `--language <code>` (restrict to one target),
  `--limit <n>` (cap number of source questions this run).
- Scale note: full backfill is ~867 × 6 ≈ 5.2k LLM calls; run once, resumable.

### Inline poller translation — `enrichment.py`

After a new English question is successfully persisted in `_process_question`,
translate it into all `TARGET_LANGUAGES` and append each. Failures per language
are logged and skipped (the backfill script will catch them later). New
questions thus gain multilingual coverage automatically.

## Validation change

`_validate_question` currently returns `False` for any `language != "en"`.
Generalize: introduce `VALID_LANGUAGES = {"en"} | TARGET_LANGUAGES` and accept
any member. All other checks unchanged. The `source_id` field, if present, must
be a non-empty string.

## API changes — `app.py`

### `GET /languages`

Scans `questions.json`, returns distinct languages present with counts:

```json
{"languages": [{"code": "en", "count": 867}, {"code": "lt", "count": 412}]}
```

Bearer auth + rate limit as with other endpoints.

### `GET /questions`

Add optional `?language=` parameter, default `"en"` (existing clients
unchanged). Filter `data` to records matching the language before the existing
sampling / difficulty / category logic runs.

`GET /categories` is unchanged.

## Error handling

- Per-(question, language) failures (API error, JSON parse error, invalid
  schema) are logged and skipped. No partial records are written.
- The next backfill run retries anything that failed, via the
  `(source_id, language)` gap detection.

## Testing

Mirroring `test_enrichment.py`, with LLM calls mocked:

- `_validate_question` accepts each target language and rejects unknown codes.
- `source_id` computed and carried onto translated records.
- Idempotency: existing `(source_id, language)` pairs are skipped by the
  backfill.
- `_translate_question` returns valid schema for a mocked LLM response;
  malformed JSON raises and is skipped.
- `GET /languages` returns correct codes and counts for a fixture corpus.
- `GET /questions?language=<code>` filters correctly; default remains `en`.

## Out of scope

- On-demand (request-time) translation.
- Per-language files or nested-translation schemas.
- Translating `category` values (they remain the English enum).
- UI / client changes.

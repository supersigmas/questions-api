# Per-Language Translation Files — Design

**Date:** 2026-07-19
**Status:** Approved (design), pending implementation plan

## Problem

Translations are currently appended into the single `questions.json` as extra
records carrying a `language` field, produced one `(question, language)` API
call at a time. This bloats the primary file, makes dedup implicit, and couples
all languages into one artifact. We also have no stable per-question identifier
in the original file to link a translation back to its source.

The provider was also migrated off the dead Azure `gpt-4o` deployment to Claude
(see `translation.py`); this redesign builds on that.

## Goals

1. Give every original English question a stable `id`.
2. Translate each question into all missing target languages efficiently, using
   the Anthropic **Batch API**.
3. Store translations in **separate files per language**, linked by `id`.
4. Keep the HTTP API working end-to-end (`GET /questions?language=`, `/languages`).

Non-goals: changing auth, rate limiting, category selection, or the enrichment
model. Deploy/persistence wiring is called out but not implemented here.

## Decisions

- **ID = `md5(question_text)`** — the existing `_source_id`, promoted to a stored
  `id` field. Deterministic and corpus-independent (the 867-question repo copy
  and the 3,825-question prod copy agree automatically), giving free dedup.
  Trade-off accepted: editing a question's text changes its `id`, orphaning its
  translations (they'd be regenerated on the next run).
- **Anthropic Batch API** for translation (≈50% cheaper, async).
- **Update the serving side** so the API reads per-language files.
- **Metadata by lookup** — per-language files store only translated text; the
  language-invariant `category` / `difficulty` / `points` are read from the
  original by `id` at serve time (single source of truth, no drift).
- **Inline translation removed from the poller** — the poller only adds English
  questions; translation is a standalone async batch job.

## Data Model

### Original file — `questions.json`
`{"data": [ {id, question, answers, wrong_answers, category, difficulty, points, language: "en"}, ... ]}`
- `id = md5(question)` (32-hex). Added to every record.
- Existing fields unchanged.

### Per-language files — `translations/questions_<lang>.json`
`{"data": [ {id, question, answers, wrong_answers}, ... ]}`
- `id` matches the source English question's `id`.
- `question` / `answers` / `wrong_answers` are the translated text.
- No metadata — merged from the original at serve time.
- One file per target language in `TARGET_LANGUAGES` (`de, es, fr, lt, ru, hi`).
- `translations/` directory created on demand.

## Components

### `_source_id` / id stamping (`enrichment.py`)
- `id` is `_source_id(question)` (already `md5(question).hexdigest()`).
- `_persist_question` (new EN questions from the poller) stamps `id` on write.
- A small helper stamps `id` on any original record missing one, used by the
  translate script on load (and rewrites `questions.json` once if it changed).

### Translation generation (`translate_questions.py` + `translation.py`)
Rewrite the backfill flow around the Batch API:

1. Load originals (stamp missing `id`s, persist if changed).
2. For each target language, load `translations/questions_<lang>.json` → set of
   translated `id`s (create file lazily; empty set if absent).
3. Build work list: for each original, `missing_langs = [l for l in targets
   if id not in translated_ids[l]]`. Skip questions with no missing languages.
   A `--language <code>` flag restricts `targets` to one language; `--limit <n>`
   caps the number of source questions.
4. Create **one batch request per question** (`custom_id = id`) whose prompt
   asks Claude to translate into exactly that question's `missing_langs` and
   return a JSON object keyed by language code:
   `{ "<lang>": {question, answers, wrong_answers}, ... }`.
5. Submit `client.messages.batches.create(requests=[...])`; poll
   `batches.retrieve(id).processing_status` until `"ended"`.
6. Stream `batches.results(id)`; match by `custom_id`. For each `succeeded`
   result: parse the JSON (fence-tolerant), and for each returned language,
   validate and append `{id, question, answers, wrong_answers}` to that
   language's file. `errored` / `expired` results are logged and skipped.
7. Writes are idempotent (re-running only fills gaps) and interrupt-safe (each
   language file is written atomically, through symlinks — reuse
   `enrichment._atomic_write_json`).

Model configurable via `ANTHROPIC_TRANSLATION_MODEL` (default `claude-opus-4-8`;
`claude-haiku-4-5` recommended for the full bulk run). Requires an `anthropic`
SDK version new enough for `messages.batches` (pin in `requirements.txt`).

The system prompt is the all-languages variant of today's
`TRANSLATION_SYSTEM_PROMPT`: lowercase answer variants, preserve meaning and
difficulty, do not add/remove options, output JSON only.

### Serving (`app.py`)
- `_load_questions(language="en")`:
  - `en` → originals as-is.
  - else → load `translations/questions_<lang>.json`; build `id → original`
    index from originals; for each translated record with a known `id`, emit a
    merged dict: `category`/`difficulty`/`points` from the original + translated
    `question`/`answers`/`wrong_answers` + `language`. Records whose `id` is not
    in the originals are skipped (stale).
- `GET /questions?language=<code>` calls `_load_questions(code)`; the existing
  category/difficulty/count filtering is unchanged (it just operates on the
  merged list).
- `GET /languages`: `en` count = number of originals; each `<lang>` count =
  size of its translation file (intersected with known ids). Missing files → 0
  / omitted.
- `GET /categories`: unchanged (reads originals).

## Error Handling

- Batch request build: a question with empty `missing_langs` is not submitted.
- Batch results: `succeeded` parsed and validated per language via
  `_validate_question` (on the merged record shape); invalid or unparseable
  languages are logged and skipped, others in the same result still saved.
- `errored`/`expired`/`canceled` results logged with `custom_id`; the run stays
  partial and is safely re-runnable.
- Serving: a missing per-language file yields an empty list (not an error); a
  translated record with an unknown `id` is skipped.

## Testing (TDD, Batch client mocked)

- `id` stamping: `md5` value; idempotent; `_persist_question` stamps new EN.
- missing-langs computation: skips fully-translated ids; honors `--language`.
- batch-request building: one request per question, `custom_id = id`, prompt
  lists exactly the missing languages.
- result reassembly: a mocked batch result maps into the correct per-language
  files; partial-language failures don't block the rest.
- dedup: re-running with an existing translation file adds nothing.
- serve-time merge: metadata comes from the original by `id`; unknown ids
  skipped; `en` returns originals.
- `/languages` counts across original + translation files.

## Deploy Notes (out of scope for this change)

- `translations/*.json` need the same `shared/`-persistence + symlink-through-
  write treatment as `questions.json` (add the `translations/` files to
  `PERSISTENT_FILES` or persist the directory, seed `shared/` before deploy).
- `anthropic` (Batches-capable version) added to `requirements.txt` — installing
  it into the prod `shared/venv` must avoid the 1 GB-RAM / disk OOM landmine
  (it is small/pure-Python, so a direct `pip install` into `shared/venv` is
  feasible; see `questions-api-deploy-constraints` memory).
- Anthropic account needs credits before any live batch run.

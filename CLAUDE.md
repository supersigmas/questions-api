# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the API

**Local (dev):**
```bash
pip install -r requirements.txt
python app.py          # runs on http://0.0.0.0:5000 with debug=True
```

**Docker:**
```bash
docker build -t questions-api .
docker run -p 5000:5000 questions-api
# or
docker-compose up
```

The Dockerfile uses gunicorn in production (`CMD exec gunicorn --bind :$PORT ...`), but `app.py` uses Flask's dev server when run directly. Docker Compose reads from a `.env` file for the `$PORT` variable.

## Environment

`app.py` and `enrichment.py` load `.env`. The enrichment poller requires `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`. Optional: `PROMPT_VARIANT` (0–3, default 0), `DEDUP_THRESHOLD` (default 0.92). `.env` is gitignored.

## Testing the API

```bash
python -m pytest tests/   # unit tests for enrichment (mocked, no live API/network); pytest not in requirements.txt
python usage_test.py      # integration smoke test — hits live /questions with Bearer token
```

All endpoints require `Authorization: Bearer my_token` header. Rate limit is 10 requests/minute per IP.

## API Endpoints

- `GET /categories` — returns 4 randomly selected categories from `translations/questions_en.json`
- `GET /questions?category=<cat>&count=<n>&difficulty=<easy|...>` — returns randomized questions; defaults to count=20, difficulty=easy
- `GET /questions?language=<code>` — filters by language (default `en`); supported codes: en, de, es, fr, lt, ru, hi
- `GET /languages` — returns the language codes present in the corpus, each with a question count

## Architecture

English questions live in `translations/questions_en.json` (structure: `{"data": [...]}`) where each item has `id`, `category`, `difficulty`, and question fields — this is the source of truth and the join key (`id`) for every other language. Translated questions live alongside it in `translations/questions_<lang>.json` (de, es, fr, lt, ru, hi), each a self-contained record (`id`, `question`, `answers`, `wrong_answers`, `category`, `difficulty`, `points`, `language`) matched back to English by `id`. All files are read on every request (no caching).

**`app.py`** — the entire Flask application: auth validation, rate limiting (flask-limiter, in-memory storage), CORS, and route handlers. `_load_originals()` reads `translations/questions_en.json`; `_load_questions(language)` joins the requested `translations/questions_<lang>.json` to it by `id` for non-English requests.

**`translation.py`** — translates English questions into target languages (de, es, fr, lt, ru, hi) via Azure OpenAI, one (question, language) pair per call. Translated records copy category/difficulty/points from the source and carry `source_id` (md5 of the English question text) plus their `language`. Translations skip embedding/semantic-dedup; idempotency is keyed on `(source_id, language)`. The enrichment poller only appends new **English** questions — it does not translate inline. `translate_questions.py` backfills translations for the existing English corpus via the Anthropic Batch API (idempotent, interrupt-safe), appending into `translations/questions_<lang>.json`: `python translate_questions.py [--language <code>] [--limit <n>]`. Run it periodically, since new English questions from the poller won't appear in other languages until it's rerun.

**`extractions.py` / `checs.py`** — standalone utility scripts for inspecting `translations/questions_en.json` (category/difficulty counts, filtering). Not part of the API; run directly with `python <script>.py`.

## Background enrichment

`enrichment.py` runs a daemon poller, started at import time by `start_background_poller()` (called in `app.py:96`). Importing/running `app.py` therefore spawns a thread and, on first run, backfills embeddings — it is not a passive import.

The loop polls opentdb every `POLL_INTERVAL` (720s) and, per question: (1) transforms to the internal schema via Azure OpenAI, (2) simplifies for a family audience via Azure OpenAI (prompt chosen by `PROMPT_VARIANT`), (3) skips semantic duplicates using **local** `all-MiniLM-L6-v2` embeddings (sentence-transformers), (4) appends to `translations/questions_en.json` (`enrichment.QUESTIONS_FILE`). Embeddings are cached in `embeddings.json`.

`translations/questions_en.json` is written concurrently by the poller — all writes go through `_write_lock` + `_atomic_replace` (retries on Windows `PermissionError`). Preserve this when editing write paths.

Note: embeddings are local, but enrichment/simplification LLM calls still use Azure OpenAI — hence both `sentence-transformers` and `openai` in requirements.

## Auth

Bearer token is hardcoded as `my_token` in `validate_bearer_token()` in `app.py:55`. There is no config or env-based override currently.

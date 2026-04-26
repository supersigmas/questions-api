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

## Testing the API

```bash
python usage_test.py   # hits /questions with Bearer token
```

All endpoints require `Authorization: Bearer my_token` header. Rate limit is 10 requests/minute per IP.

## API Endpoints

- `GET /categories` — returns 4 randomly selected categories from `questions.json`
- `GET /questions?category=<cat>&count=<n>&difficulty=<easy|...>` — returns randomized questions; defaults to count=20, difficulty=easy

## Architecture

All data lives in `questions.json` (structure: `{"data": [...]}`) where each item has `category`, `difficulty`, and question fields. The file is read on every request (no caching).

**`app.py`** — the entire Flask application: auth validation, rate limiting (flask-limiter, in-memory storage), CORS, and two route handlers.

**`extractions.py` / `checs.py`** — standalone utility scripts for inspecting `questions.json` (category/difficulty counts, filtering). Not part of the API; run directly with `python <script>.py`.

## Auth

Bearer token is hardcoded as `my_token` in `validate_bearer_token()` in `app.py:55`. There is no config or env-based override currently.

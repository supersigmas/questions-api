# Questions Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve trivia questions in six additional languages via an LLM translation workflow (backfill + inline) plus a `GET /languages` endpoint, reusing the existing Azure OpenAI enrichment pattern.

**Architecture:** Translations are appended to `questions.json` as full question records carrying a `source_id` (md5 of the English question text) and a target `language`. A new `translation.py` module (mirroring `enrichment.py`) translates one (question, language) pair per LLM call, skipping embedding/dedup. A backfill script fills the existing corpus; the poller translates new questions inline. `app.py` gains a `/languages` endpoint and a `?language=` filter on `/questions`.

**Tech Stack:** Python, Flask, Azure OpenAI (`openai` SDK), pytest + `unittest.mock`.

**Source language:** `en`. **Target languages:** `de`, `es`, `fr`, `lt`, `ru`, `hi`.

---

## File Structure

- `enrichment.py` (modify) — add language constants, `_source_id()` helper, generalize `_validate_question`, add inline translation hook in `_process_question`.
- `translation.py` (create) — translation prompt, `_translate_question()`, idempotency helpers, `translate_and_persist()`.
- `translate_questions.py` (create) — standalone backfill CLI.
- `app.py` (modify) — `_load_questions()` helper, `GET /languages`, `?language=` on `/questions`.
- `tests/test_translation_unit.py` (create) — translation unit tests.
- `tests/test_app_unit.py` (create) — endpoint tests.
- `tests/test_enrichment_unit.py` (modify) — validation tests for new languages.

**Import direction (avoid circular imports):** `translation.py` imports helpers from `enrichment.py` at top level. `enrichment.py`'s inline hook imports `translation.py` **lazily inside the function**, never at module top level.

**source_id policy:** stored on every newly written record (new English questions from the poller + all translations). Legacy English records that lack it have it computed on the fly via `_source_id()`; no bulk migration of the existing file.

---

## Task 1: Language constants, source_id helper, and validation

**Files:**
- Modify: `enrichment.py`
- Test: `tests/test_enrichment_unit.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_enrichment_unit.py`:

```python
def test_valid_languages_includes_targets():
    from enrichment import VALID_LANGUAGES, TARGET_LANGUAGES
    assert TARGET_LANGUAGES == {"de", "es", "fr", "lt", "ru", "hi"}
    assert VALID_LANGUAGES == {"en"} | TARGET_LANGUAGES


def test_source_id_is_md5_of_text():
    import hashlib
    from enrichment import _source_id
    text = "What is the largest ocean on Earth?"
    assert _source_id(text) == hashlib.md5(text.encode()).hexdigest()


def _valid_lt_question():
    return {
        "question": "Koks didziausias vandenynas Zemeje?",
        "answers": ["ramusis vandenynas", "ramusis"],
        "wrong_answers": ["Atlanto vandenynas", "Indijos vandenynas"],
        "category": "geography",
        "difficulty": "normal",
        "points": 800,
        "language": "lt",
        "source_id": "abc123",
    }


def test_validate_accepts_target_language():
    from enrichment import _validate_question
    assert _validate_question(_valid_lt_question()) is True


def test_validate_rejects_unknown_language():
    from enrichment import _validate_question
    q = _valid_lt_question()
    q["language"] = "xx"
    assert _validate_question(q) is False


def test_validate_rejects_empty_source_id_when_present():
    from enrichment import _validate_question
    q = _valid_lt_question()
    q["source_id"] = ""
    assert _validate_question(q) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_enrichment_unit.py -k "language or source_id" -v`
Expected: FAIL (ImportError: cannot import name `VALID_LANGUAGES` / `_source_id`).

- [ ] **Step 3: Add constants and helper to `enrichment.py`**

After the existing `VALID_DIFFICULTIES = {...}` block, add:

```python
TARGET_LANGUAGES = {"de", "es", "fr", "lt", "ru", "hi"}
VALID_LANGUAGES = {"en"} | TARGET_LANGUAGES
```

Near the top-level helpers (e.g. just above `_get_az_client`), add:

```python
def _source_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()
```

- [ ] **Step 4: Generalize `_validate_question` in `enrichment.py`**

Replace the language check:

```python
    if q["language"] != "en":
        return False
```

with:

```python
    if q["language"] not in VALID_LANGUAGES:
        return False
    if "source_id" in q and (not isinstance(q["source_id"], str) or not q["source_id"]):
        return False
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_enrichment_unit.py -v`
Expected: PASS (all, including pre-existing tests).

- [ ] **Step 6: Commit**

```bash
git add enrichment.py tests/test_enrichment_unit.py
git commit -m "feat: language constants, source_id helper, multi-language validation"
```

---

## Task 2: Translation core — `_translate_question`

**Files:**
- Create: `translation.py`
- Test: `tests/test_translation_unit.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_translation_unit.py`:

```python
import json
from unittest.mock import MagicMock, patch


def _make_mock_response(content: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = json.dumps(content)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _source_en():
    return {
        "question": "What is the largest ocean on Earth?",
        "answers": ["pacific ocean", "pacific"],
        "wrong_answers": ["Atlantic Ocean", "Indian Ocean"],
        "category": "geography",
        "difficulty": "normal",
        "points": 800,
        "language": "en",
    }


def test_translate_prompt_requires_lowercase_answers():
    from translation import TRANSLATION_SYSTEM_PROMPT
    assert "lowercase" in TRANSLATION_SYSTEM_PROMPT.lower()
    assert "json" in TRANSLATION_SYSTEM_PROMPT.lower()


def test_translate_question_sets_language_and_copies_fields():
    from translation import _translate_question
    mock_result = {
        "question": "Koks didziausias vandenynas Zemeje?",
        "answers": ["ramusis vandenynas", "ramusis"],
        "wrong_answers": ["Atlanto vandenynas", "Indijos vandenynas"],
    }
    mock_resp = _make_mock_response(mock_result)

    with patch("translation._get_az_client") as mock_client_fn:
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        mock_client_fn.return_value = client
        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o"}):
            result = _translate_question(_source_en(), "lt")

    assert result["language"] == "lt"
    assert result["question"] == mock_result["question"]
    assert result["answers"] == mock_result["answers"]
    assert result["category"] == "geography"
    assert result["difficulty"] == "normal"
    assert result["points"] == 800
    # source_id is md5 of the English source question
    import hashlib
    assert result["source_id"] == hashlib.md5(_source_en()["question"].encode()).hexdigest()


def test_translate_question_passes_target_language_to_prompt():
    from translation import _translate_question
    mock_resp = _make_mock_response({
        "question": "x", "answers": ["a"], "wrong_answers": ["b"],
    })
    with patch("translation._get_az_client") as mock_client_fn:
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        mock_client_fn.return_value = client
        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o"}):
            _translate_question(_source_en(), "de")
    _, kwargs = client.chat.completions.create.call_args
    joined = " ".join(m["content"] for m in kwargs["messages"])
    assert "de" in joined or "German" in joined
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_translation_unit.py -v`
Expected: FAIL (ModuleNotFoundError: No module named `translation`).

- [ ] **Step 3: Create `translation.py`**

```python
import json
import logging
import os

from enrichment import (
    TARGET_LANGUAGES,
    _get_az_client,
    _source_id,
    _validate_question,
)

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "lt": "Lithuanian",
    "ru": "Russian",
    "hi": "Hindi",
}

TRANSLATION_SYSTEM_PROMPT = """You are a translation assistant for a family trivia game.

Translate the given trivia question into {language_name} ({language_code}).

Output ONLY a single valid JSON object. No prose, no markdown, no explanation.

The object MUST have exactly these fields:
- "question": string - the question translated naturally into {language_name}
- "answers": array of strings - natural LOWERCASE variants of the correct answer in {language_name} (keep 1-3 items, same meaning as the source)
- "wrong_answers": array of strings - the incorrect answers translated into {language_name}

Preserve the meaning and difficulty. Do not add or remove answer options.
Return only the JSON object."""


def _translate_question(source_q: dict, lang: str) -> dict:
    client = _get_az_client()
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    system_prompt = TRANSLATION_SYSTEM_PROMPT.format(
        language_name=LANGUAGE_NAMES[lang], language_code=lang
    )
    payload = {
        "question": source_q["question"],
        "answers": source_q["answers"],
        "wrong_answers": source_q["wrong_answers"],
    }
    preview = source_q.get("question", "")[:80]
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=512,
        )
        content = response.choices[0].message.content.strip()
        translated = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("Translation JSON parse failed (%s) for '%s': %s", lang, preview, e)
        raise
    except Exception as e:
        logger.error("Translation API call failed (%s) for '%s': %s", lang, preview, e)
        raise

    return {
        "question": translated["question"],
        "answers": translated["answers"],
        "wrong_answers": translated["wrong_answers"],
        "category": source_q["category"],
        "difficulty": source_q["difficulty"],
        "points": source_q["points"],
        "language": lang,
        "source_id": _source_id(source_q["question"]),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_translation_unit.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add translation.py tests/test_translation_unit.py
git commit -m "feat: translation core with _translate_question"
```

---

## Task 3: Idempotency helpers and `translate_and_persist`

**Files:**
- Modify: `translation.py`
- Test: `tests/test_translation_unit.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_translation_unit.py`:

```python
def test_existing_pairs_collects_source_id_language():
    from translation import _existing_pairs
    data = [
        {"question": "Q1", "language": "en"},
        {"question": "t", "language": "lt", "source_id": "sid1"},
        {"question": "t", "language": "de", "source_id": "sid1"},
    ]
    pairs = _existing_pairs(data)
    assert ("sid1", "lt") in pairs
    assert ("sid1", "de") in pairs


def test_translate_and_persist_skips_existing_languages():
    from translation import translate_and_persist, _source_id
    src = _source_en()
    sid = _source_id(src["question"])
    existing = {(sid, "lt"), (sid, "de"), (sid, "es"),
                (sid, "fr"), (sid, "ru"), (sid, "hi")}

    with patch("translation._translate_question") as mock_tr, \
         patch("translation._persist_question") as mock_persist:
        added = translate_and_persist(src, existing)

    assert added == 0
    mock_tr.assert_not_called()
    mock_persist.assert_not_called()


def test_translate_and_persist_translates_missing_languages():
    from translation import translate_and_persist, _source_id
    src = _source_en()
    sid = _source_id(src["question"])
    existing = {(sid, "de"), (sid, "es"), (sid, "fr"), (sid, "ru"), (sid, "hi")}

    def fake_translate(source_q, lang):
        return {
            "question": "x", "answers": ["a"], "wrong_answers": ["b"],
            "category": "geography", "difficulty": "normal", "points": 800,
            "language": lang, "source_id": sid,
        }

    with patch("translation._translate_question", side_effect=fake_translate) as mock_tr, \
         patch("translation._persist_question") as mock_persist:
        added = translate_and_persist(src, existing)

    assert added == 1  # only "lt" was missing
    mock_tr.assert_called_once_with(src, "lt")
    mock_persist.assert_called_once()
    assert existing == {(sid, l) for l in ("de", "es", "fr", "ru", "hi", "lt")}


def test_translate_and_persist_skips_invalid_result():
    from translation import translate_and_persist, _source_id
    src = _source_en()
    sid = _source_id(src["question"])
    existing = {(sid, l) for l in ("de", "es", "fr", "ru", "hi")}

    def bad_translate(source_q, lang):
        return {"question": "", "answers": [], "wrong_answers": [],
                "category": "geography", "difficulty": "normal", "points": 800,
                "language": lang, "source_id": sid}

    with patch("translation._translate_question", side_effect=bad_translate), \
         patch("translation._persist_question") as mock_persist:
        added = translate_and_persist(src, existing)

    assert added == 0
    mock_persist.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_translation_unit.py -k "existing_pairs or translate_and_persist" -v`
Expected: FAIL (cannot import `_existing_pairs` / `translate_and_persist`).

- [ ] **Step 3: Extend `translation.py`**

Add `_persist_question` to the import from `enrichment`:

```python
from enrichment import (
    TARGET_LANGUAGES,
    _get_az_client,
    _persist_question,
    _source_id,
    _validate_question,
)
```

Append:

```python
def _existing_pairs(data: list) -> set:
    """Set of (source_id, language) already present among translation records."""
    pairs = set()
    for q in data:
        if q.get("language") == "en":
            continue
        sid = q.get("source_id")
        if sid:
            pairs.add((sid, q["language"]))
    return pairs


def translate_and_persist(source_q: dict, existing: set) -> int:
    """Translate one English question into all missing target languages.

    `existing` is a mutable set of (source_id, language); it is updated in place
    as translations are persisted so callers stay idempotent within a run.
    Returns the number of translations added.
    """
    sid = _source_id(source_q["question"])
    added = 0
    for lang in sorted(TARGET_LANGUAGES):
        if (sid, lang) in existing:
            continue
        try:
            translated = _translate_question(source_q, lang)
        except Exception as exc:
            logger.error("TRANSLATION FAILED: %s (%s) | %s",
                         source_q["question"][:80], lang, str(exc)[:100])
            continue
        if not _validate_question(translated):
            logger.error("TRANSLATION INVALID: %s (%s)", source_q["question"][:80], lang)
            continue
        try:
            _persist_question(translated)
        except Exception as exc:
            logger.error("TRANSLATION PERSIST FAILED: %s (%s) | %s",
                         source_q["question"][:80], lang, str(exc)[:100])
            continue
        existing.add((sid, lang))
        added += 1
        logger.info("TRANSLATION SUCCESS: %s | %s", source_q["question"][:80], lang)
    return added
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_translation_unit.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add translation.py tests/test_translation_unit.py
git commit -m "feat: idempotent translate_and_persist with (source_id, language) gap detection"
```

---

## Task 4: Backfill CLI — `translate_questions.py`

**Files:**
- Create: `translate_questions.py`
- Test: `tests/test_translation_unit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_translation_unit.py`:

```python
def test_backfill_run_translates_english_records():
    import translate_questions
    data = [
        {"question": "Q1", "answers": ["a"], "wrong_answers": ["b"],
         "category": "geography", "difficulty": "easy", "points": 700, "language": "en"},
        {"question": "Q2", "answers": ["c"], "wrong_answers": ["d"],
         "category": "science", "difficulty": "easy", "points": 700, "language": "en"},
    ]
    calls = []

    def fake_tap(source_q, existing):
        calls.append(source_q["question"])
        return 6

    with patch.object(translate_questions, "_read_all", return_value=data), \
         patch.object(translate_questions, "translate_and_persist", side_effect=fake_tap):
        total = translate_questions.run(language=None, limit=None)

    assert total == 12
    assert calls == ["Q1", "Q2"]


def test_backfill_respects_limit():
    import translate_questions
    data = [
        {"question": f"Q{i}", "answers": ["a"], "wrong_answers": ["b"],
         "category": "geography", "difficulty": "easy", "points": 700, "language": "en"}
        for i in range(5)
    ]
    with patch.object(translate_questions, "_read_all", return_value=data), \
         patch.object(translate_questions, "translate_and_persist", return_value=1) as m:
        translate_questions.run(language=None, limit=2)
    assert m.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_translation_unit.py -k backfill -v`
Expected: FAIL (No module named `translate_questions`).

- [ ] **Step 3: Create `translate_questions.py`**

```python
#!/usr/bin/env python3
"""Backfill translations for existing English questions.

Idempotent: only fills missing (source_id, language) pairs. Safe to re-run or
interrupt. Usage:

    python translate_questions.py                 # all target languages
    python translate_questions.py --language lt   # only Lithuanian
    python translate_questions.py --limit 50      # first 50 English questions
"""
import argparse
import json
import logging

from enrichment import QUESTIONS_FILE, TARGET_LANGUAGES, _write_lock
from translation import _existing_pairs, translate_and_persist

logger = logging.getLogger(__name__)


def _read_all() -> list:
    with _write_lock:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)["data"]


def run(language: str = None, limit: int = None) -> int:
    data = _read_all()
    english = [q for q in data if q.get("language") == "en"]
    if limit is not None:
        english = english[:limit]

    existing = _existing_pairs(data)
    if language is not None:
        # Pretend all other languages are already present so only `language` runs.
        for q in english:
            from translation import _source_id
            sid = _source_id(q["question"])
            for other in TARGET_LANGUAGES - {language}:
                existing.add((sid, other))

    total = 0
    for i, q in enumerate(english, start=1):
        total += translate_and_persist(q, existing)
        if i % 25 == 0:
            logger.info("Backfill progress: %d/%d English questions processed", i, len(english))
    logger.info("Backfill complete: %d translations added", total)
    return total


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Backfill question translations")
    parser.add_argument("--language", choices=sorted(TARGET_LANGUAGES), default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run(language=args.language, limit=args.limit)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_translation_unit.py -k backfill -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add translate_questions.py tests/test_translation_unit.py
git commit -m "feat: translate_questions.py backfill CLI"
```

---

## Task 5: Inline translation hook in the poller

**Files:**
- Modify: `enrichment.py` (`_process_question`)
- Test: `tests/test_enrichment_unit.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_enrichment_unit.py`:

```python
def test_process_question_triggers_translation_after_persist():
    from unittest.mock import patch, MagicMock
    import enrichment

    raw_q = {"question": "Q?", "correct_answer": "a", "incorrect_answers": ["b"],
             "category": "Science", "difficulty": "easy", "type": "multiple"}
    enriched = {"question": "Q enriched?", "answers": ["a"], "wrong_answers": ["b"],
                "category": "science", "difficulty": "easy", "points": 700, "language": "en"}

    with patch.object(enrichment, "_enrich_question", return_value=enriched), \
         patch.object(enrichment, "_simplify_question", return_value={
             "question": "Q enriched?", "answers": ["a"], "wrong_answers": ["b"]}), \
         patch.object(enrichment, "_get_embedding", return_value=[0.0, 0.1]), \
         patch.object(enrichment, "_is_semantic_duplicate", return_value=False), \
         patch.object(enrichment, "_persist_question"), \
         patch.object(enrichment, "_persist_embedding"), \
         patch("translation.translate_and_persist") as mock_tap:
        ok = enrichment._process_question(raw_q, set(), {}, variant=0)

    assert ok is True
    mock_tap.assert_called_once()
    # source_id was stamped on the English record before translating
    passed_source = mock_tap.call_args[0][0]
    assert "source_id" in passed_source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_enrichment_unit.py -k triggers_translation -v`
Expected: FAIL (translate_and_persist not called).

- [ ] **Step 3: Add the hook in `_process_question`**

In `enrichment.py`, inside `_process_question`, locate the successful-persist block:

```python
    try:
        _persist_question(enriched)
        _persist_embedding(enriched["question"], embedding, embeddings_store)
    except Exception as exc:
        logger.error("PERSISTENCE FAILED: %s | Error: %s", question_text, str(exc)[:100])
        return False
```

Immediately BEFORE that `try` block, stamp the source_id:

```python
    enriched["source_id"] = _source_id(enriched["question"])
```

Immediately AFTER that `try/except` block (before the final success log), add the
translation hook with a lazy import to avoid a circular import:

```python
    try:
        from translation import translate_and_persist
        translate_and_persist(enriched, set())
    except Exception as exc:
        logger.error("INLINE TRANSLATION FAILED: %s | Error: %s", question_text, str(exc)[:100])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_enrichment_unit.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add enrichment.py tests/test_enrichment_unit.py
git commit -m "feat: translate new questions inline in the enrichment poller"
```

---

## Task 6: `GET /languages` endpoint

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_unit.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_app_unit.py`:

```python
from unittest.mock import patch
import pytest


@pytest.fixture
def client():
    # Prevent the background poller (network + model load) from starting on import.
    with patch("enrichment.start_background_poller"):
        import importlib
        import app as app_module
        importlib.reload(app_module)
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client(), app_module


AUTH = {"Authorization": "Bearer my_token"}

FIXTURE = [
    {"question": "Q1", "answers": ["a"], "wrong_answers": ["b"],
     "category": "geography", "difficulty": "easy", "points": 700, "language": "en"},
    {"question": "Q1 lt", "answers": ["a"], "wrong_answers": ["b"],
     "category": "geography", "difficulty": "easy", "points": 700,
     "language": "lt", "source_id": "s1"},
    {"question": "Q2", "answers": ["c"], "wrong_answers": ["d"],
     "category": "science", "difficulty": "easy", "points": 700, "language": "en"},
]


def test_languages_returns_codes_and_counts(client):
    test_client, app_module = client
    with patch.object(app_module, "_load_questions", return_value=FIXTURE):
        resp = test_client.get("/languages", headers=AUTH)
    assert resp.status_code == 200
    langs = {l["code"]: l["count"] for l in resp.get_json()["languages"]}
    assert langs == {"en": 2, "lt": 1}


def test_languages_requires_auth(client):
    test_client, _ = client
    resp = test_client.get("/languages")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_unit.py -k languages -v`
Expected: FAIL (404 on `/languages`, and `_load_questions` does not exist).

- [ ] **Step 3: Add `_load_questions` helper and `/languages` route in `app.py`**

Add a helper near `collect_categories` (replaces the leaking `open()` calls):

```python
def _load_questions() -> list:
    with open("questions.json", "r", encoding="utf-8") as f:
        return json.load(f)["data"]
```

Update `get_category` and `get_questions` to use it, replacing:

```python
    f = open("questions.json", "r")
    data = json.load(f)
    data = data["data"]
```

with:

```python
    data = _load_questions()
```

Add the new route (after `get_questions`):

```python
@app.route("/languages", methods=["GET"])
@limiter.limit("10 per minute")
def get_languages():
    if not validate_bearer_token(request.headers):
        return {"error": "Invalid bearer token"}, 401

    data = _load_questions()
    counts = {}
    for item in data:
        code = item.get("language", "en")
        counts[code] = counts.get(code, 0) + 1

    languages = [{"code": c, "count": n} for c, n in sorted(counts.items())]
    return {"languages": languages}, 200
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_unit.py -k languages -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_unit.py
git commit -m "feat: GET /languages endpoint and _load_questions helper"
```

---

## Task 7: `?language=` filter on `GET /questions`

**Files:**
- Modify: `app.py` (`get_questions_count`, `get_questions`)
- Test: `tests/test_app_unit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_app_unit.py`:

```python
MIXED = [
    {"question": "en-geo", "answers": ["a"], "wrong_answers": ["b"],
     "category": "geography", "difficulty": "easy", "points": 700, "language": "en"},
    {"question": "lt-geo", "answers": ["a"], "wrong_answers": ["b"],
     "category": "geography", "difficulty": "easy", "points": 700,
     "language": "lt", "source_id": "s1"},
]


def test_questions_defaults_to_english(client):
    test_client, app_module = client
    with patch.object(app_module, "_load_questions", return_value=MIXED):
        resp = test_client.get("/questions?count=10", headers=AUTH)
    qs = resp.get_json()["questions"]
    assert qs and all(q["language"] == "en" for q in qs)


def test_questions_filters_by_language(client):
    test_client, app_module = client
    with patch.object(app_module, "_load_questions", return_value=MIXED):
        resp = test_client.get("/questions?language=lt&count=10", headers=AUTH)
    qs = resp.get_json()["questions"]
    assert qs and all(q["language"] == "lt" for q in qs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_unit.py -k "language" -v`
Expected: FAIL (English default test may pass by luck, but `language=lt` returns mixed/English records).

- [ ] **Step 3: Add language filtering in `app.py`**

In `get_questions`, read the param and filter before sampling:

```python
    category = request.args.get("category")
    questions_count = request.args.get("count", default=20, type=int)
    difficulty = request.args.get("difficulty", default="easy", type=str)
    language = request.args.get("language", default="en", type=str)

    data = _load_questions()
    data = [q for q in data if q.get("language", "en") == language]

    if category:
        questions = get_questions_count(data, category, questions_count, difficulty)
    else:
        questions = get_questions_count(data=data, difficulty=difficulty, count=questions_count)
    return {"questions": questions}, 200
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app_unit.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_unit.py
git commit -m "feat: filter GET /questions by ?language= (default en)"
```

---

## Task 8: Full suite + docs

**Files:**
- Modify: `CLAUDE.md`, `README.md`

- [ ] **Step 1: Run the full test suite**

Run: `pytest -v`
Expected: PASS (all tests across enrichment, translation, app).

- [ ] **Step 2: Document the new endpoints and workflow**

In `CLAUDE.md` under "API Endpoints", add:

```markdown
- `GET /languages` — returns language codes present in the corpus with counts
- `GET /questions?language=<code>` — filters by language (default `en`); codes: en, de, es, fr, lt, ru, hi
```

Under "Architecture", add:

```markdown
**`translation.py`** — translates English questions into target languages
(de, es, fr, lt, ru, hi) via Azure OpenAI. Records carry `source_id`
(md5 of the English question) and a `language` field. New questions are
translated inline by the poller; run `python translate_questions.py` to
backfill the existing corpus.
```

In `README.md`, add a short "Translations" section describing
`python translate_questions.py [--language <code>] [--limit <n>]`.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: document languages endpoint and translation workflow"
```

---

## Notes for the implementer

- **Do not** run `translate_questions.py` against the real corpus as part of implementation — it makes ~5.2k paid Azure OpenAI calls. It is exercised only via mocked unit tests here. Running the real backfill is an explicit, separate operational step for the user.
- Azure OpenAI env vars (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`) are already configured in `.env`; unit tests mock the client and never hit the network.
- Follow the existing atomic-write pattern — always persist through `enrichment._persist_question`, never write `questions.json` directly.

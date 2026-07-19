# Per-Language Translation Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every English question a stable md5 `id`, translate all missing languages per question via the Anthropic Batch API, store translations in per-language files linked by `id`, and serve merged views from the API.

**Architecture:** Originals stay in `questions.json` (now with `id`). Translations live in `translations/questions_<lang>.json` holding only `{id, question, answers, wrong_answers}`. A rewritten `translate_questions.py` submits one Batch API request per question (all its missing languages) and writes results into the per-language files. `app.py` merges translated text with metadata from the original by `id` at serve time.

**Tech Stack:** Python 3.11, Flask, `anthropic` SDK (Batch API), pytest. Spec: `docs/superpowers/specs/2026-07-19-per-language-translation-files-design.md`.

**Run all tests with:** `python3 -m pytest tests/ -q`

---

### Task 1: Stamp `id` on originals and new questions (`enrichment.py`)

**Files:**
- Modify: `enrichment.py` (add `_stamp_ids`; stamp in `_persist_question:344`)
- Test: `tests/test_enrichment_unit.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_enrichment_unit.py`:

```python
def test_stamp_ids_adds_md5_id_when_missing():
    import hashlib
    from enrichment import _stamp_ids
    data = [{"question": "What is 2+2?"}, {"question": "Sky?", "id": "keep"}]
    changed = _stamp_ids(data)
    assert changed is True
    assert data[0]["id"] == hashlib.md5("What is 2+2?".encode()).hexdigest()
    assert data[1]["id"] == "keep"


def test_stamp_ids_idempotent():
    from enrichment import _stamp_ids
    data = [{"question": "Q", "id": "x"}]
    assert _stamp_ids(data) is False


def test_persist_question_stamps_id(tmp_path, monkeypatch):
    import json, hashlib, enrichment
    monkeypatch.chdir(tmp_path)
    (tmp_path / "questions.json").write_text(json.dumps({"data": []}))
    monkeypatch.setattr(enrichment, "_is_unique", lambda q, existing: True)
    enrichment._persist_question({
        "question": "New Q?", "answers": ["a"], "wrong_answers": ["b", "c", "d"],
        "category": "c", "difficulty": "easy", "points": 700, "language": "en",
    })
    data = json.loads((tmp_path / "questions.json").read_text())["data"]
    assert data[0]["id"] == hashlib.md5("New Q?".encode()).hexdigest()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_enrichment_unit.py -q -k "stamp_ids or persist_question_stamps"`
Expected: FAIL — `ImportError: cannot import name '_stamp_ids'` / persisted record has no `id`.

- [ ] **Step 3: Add `_stamp_ids` after `_source_id` (enrichment.py, after line 114)**

```python
def _stamp_ids(data: list) -> bool:
    """Add `id = md5(question)` to any record missing one. Returns True if any
    id was added (the store then needs to be persisted)."""
    changed = False
    for q in data:
        if not q.get("id"):
            q["id"] = _source_id(q["question"])
            changed = True
    return changed
```

- [ ] **Step 4: Stamp `id` in `_persist_question` (enrichment.py:353)**

Change the append block so it reads:

```python
        q["id"] = q.get("id") or _source_id(q["question"])
        store["data"].append(q)

        _atomic_write_json(store, QUESTIONS_FILE, indent=2)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_enrichment_unit.py -q`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add enrichment.py tests/test_enrichment_unit.py
git commit -m "feat: stamp md5 id on original and new questions"
```

---

### Task 2: Per-language file helpers (`translation.py`)

**Files:**
- Modify: `translation.py` (imports + new helpers)
- Test: `tests/test_translation_unit.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_translation_unit.py`:

```python
def test_lang_file_path():
    from translation import _lang_file
    assert _lang_file("fr").replace("\\", "/").endswith("translations/questions_fr.json")


def test_load_translated_ids_empty_when_missing(tmp_path, monkeypatch):
    import translation
    monkeypatch.chdir(tmp_path)
    assert translation._load_translated_ids("fr") == set()


def test_append_translations_writes_and_dedups(tmp_path, monkeypatch):
    import json, translation
    monkeypatch.chdir(tmp_path)
    recs = [{"id": "a", "question": "qa", "answers": ["x"], "wrong_answers": ["y"]}]
    translation._append_translations("fr", recs)
    translation._append_translations("fr", recs + [
        {"id": "b", "question": "qb", "answers": ["1"], "wrong_answers": ["2"]}])
    data = json.loads((tmp_path / "translations" / "questions_fr.json").read_text())["data"]
    assert [r["id"] for r in data] == ["a", "b"]
    assert translation._load_translated_ids("fr") == {"a", "b"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_translation_unit.py -q -k "lang_file or translated_ids or append_translations"`
Expected: FAIL — `AttributeError: module 'translation' has no attribute '_lang_file'`.

- [ ] **Step 3: Add `_atomic_write_json` to the enrichment import (translation.py:6)**

Change the `from enrichment import (...)` block to include `_atomic_write_json`:

```python
from enrichment import (
    TARGET_LANGUAGES,
    _atomic_write_json,
    _persist_question,
    _source_id,
    _validate_question,
)
```

- [ ] **Step 4: Add the helpers (translation.py, after `_get_anthropic_client`)**

```python
TRANSLATIONS_DIR = "translations"


def _lang_file(lang: str) -> str:
    return os.path.join(TRANSLATIONS_DIR, f"questions_{lang}.json")


def _load_translated_ids(lang: str) -> set:
    path = _lang_file(lang)
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return {r["id"] for r in json.load(f)["data"]}


def _append_translations(lang: str, records: list) -> None:
    """Append translated records to the per-language file, skipping ids already
    present. Writes atomically (through symlinks)."""
    path = _lang_file(lang)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            store = json.load(f)
    else:
        os.makedirs(TRANSLATIONS_DIR, exist_ok=True)
        store = {"data": []}
    have = {r["id"] for r in store["data"]}
    for rec in records:
        if rec["id"] not in have:
            store["data"].append(rec)
            have.add(rec["id"])
    _atomic_write_json(store, path, indent=2)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_translation_unit.py -q`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add translation.py tests/test_translation_unit.py
git commit -m "feat: per-language translation file helpers"
```

---

### Task 3: Batch request building + response parsing (`translation.py`)

**Files:**
- Modify: `translation.py` (all-languages prompt, request builder, parser, record builder)
- Test: `tests/test_translation_unit.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_translation_unit.py`:

```python
def test_build_batch_request_lists_missing_langs():
    from translation import _build_batch_request, ANTHROPIC_TRANSLATION_MODEL
    q = {"id": "abc", "question": "Q?", "answers": ["a"], "wrong_answers": ["b"]}
    req = _build_batch_request(q, ["fr", "de"])
    assert req["custom_id"] == "abc"
    sysp = req["params"]["system"]
    assert "French (fr)" in sysp and "German (de)" in sysp
    assert req["params"]["model"] == ANTHROPIC_TRANSLATION_MODEL
    assert req["params"]["messages"][0]["content"]


def test_parse_batch_translation_tolerates_fence():
    from translation import _parse_batch_translation
    raw = '```json\n{"fr": {"question":"x","answers":["a"],"wrong_answers":["b"]}}\n```'
    parsed = _parse_batch_translation(raw)
    assert parsed["fr"]["question"] == "x"


def test_translation_record_shape():
    from translation import _translation_record
    rec = _translation_record("id1", {"question": "q", "answers": ["a"], "wrong_answers": ["b"]})
    assert rec == {"id": "id1", "question": "q", "answers": ["a"], "wrong_answers": ["b"]}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_translation_unit.py -q -k "build_batch_request or parse_batch_translation or translation_record"`
Expected: FAIL — `ImportError`/`AttributeError` for the new names.

- [ ] **Step 3: Add the all-languages prompt and builders (translation.py, after the existing `TRANSLATION_SYSTEM_PROMPT`)**

```python
ALL_LANGS_SYSTEM_PROMPT = """You are a translation assistant for a family trivia game.

Translate the given English trivia question into EACH of these languages: {lang_list}.

Output ONLY a single valid JSON object. No prose, no markdown. The object maps
each language code to an object with exactly these fields:
- "question": string - the question translated naturally into that language
- "answers": array of strings - natural LOWERCASE variants of the correct answer (keep 1-3 items, same meaning as the source)
- "wrong_answers": array of strings - the incorrect answers translated

Example shape: {{"fr": {{"question": "...", "answers": ["..."], "wrong_answers": ["..."]}}}}

Preserve meaning and difficulty. Do not add or remove answer options.
Use these language codes exactly: {lang_codes}. Return only the JSON object."""


def _build_batch_request(source_q: dict, langs: list) -> dict:
    lang_list = ", ".join(f"{LANGUAGE_NAMES[l]} ({l})" for l in langs)
    system_prompt = ALL_LANGS_SYSTEM_PROMPT.format(
        lang_list=lang_list, lang_codes=", ".join(langs)
    )
    payload = {
        "question": source_q["question"],
        "answers": source_q["answers"],
        "wrong_answers": source_q["wrong_answers"],
    }
    return {
        "custom_id": source_q["id"],
        "params": {
            "model": ANTHROPIC_TRANSLATION_MODEL,
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        },
    }


def _parse_batch_translation(text: str) -> dict:
    return json.loads(_extract_json(text))


def _translation_record(qid: str, lang_obj: dict) -> dict:
    return {
        "id": qid,
        "question": lang_obj["question"],
        "answers": lang_obj["answers"],
        "wrong_answers": lang_obj["wrong_answers"],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_translation_unit.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add translation.py tests/test_translation_unit.py
git commit -m "feat: batch translation request building and parsing"
```

---

### Task 4: Batch-API backfill orchestration (`translate_questions.py`)

**Files:**
- Modify (rewrite): `translate_questions.py`
- Test: `tests/test_translation_unit.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_translation_unit.py`:

```python
def test_batch_run_translates_missing_language(tmp_path, monkeypatch):
    import json, hashlib, translate_questions
    from unittest.mock import MagicMock
    monkeypatch.chdir(tmp_path)
    (tmp_path / "questions.json").write_text(json.dumps({"data": [
        {"question": "Q1", "answers": ["a"], "wrong_answers": ["b", "c", "d"],
         "category": "geo", "difficulty": "easy", "points": 700, "language": "en"}]}))
    qid = hashlib.md5("Q1".encode()).hexdigest()

    client = MagicMock()
    batch = MagicMock(id="batch_1", processing_status="ended")
    client.messages.batches.create.return_value = batch
    client.messages.batches.retrieve.return_value = batch
    block = MagicMock(type="text")
    block.text = json.dumps({
        "fr": {"question": "Q1-fr", "answers": ["a"], "wrong_answers": ["b", "c", "d"]},
        "de": {"question": "Q1-de", "answers": ["a"], "wrong_answers": ["b", "c", "d"]},
    })
    res = MagicMock(custom_id=qid)
    res.result.type = "succeeded"
    res.result.message.content = [block]
    client.messages.batches.results.return_value = [res]

    monkeypatch.setattr(translate_questions, "_get_anthropic_client", lambda: client)
    monkeypatch.setattr(translate_questions, "BATCH_POLL_INTERVAL", 0)

    total = translate_questions.run(language="fr")
    assert total == 1
    fr = json.loads((tmp_path / "translations" / "questions_fr.json").read_text())["data"]
    assert fr[0]["id"] == qid and fr[0]["question"] == "Q1-fr"
    assert not (tmp_path / "translations" / "questions_de.json").exists()
    orig = json.loads((tmp_path / "questions.json").read_text())["data"]
    assert orig[0]["id"] == qid  # id stamped back into originals


def test_batch_run_skips_when_all_present(tmp_path, monkeypatch):
    import json, hashlib, translate_questions
    from unittest.mock import MagicMock
    monkeypatch.chdir(tmp_path)
    qid = hashlib.md5("Q1".encode()).hexdigest()
    (tmp_path / "questions.json").write_text(json.dumps({"data": [
        {"question": "Q1", "id": qid, "answers": ["a"], "wrong_answers": ["b", "c", "d"],
         "category": "geo", "difficulty": "easy", "points": 700, "language": "en"}]}))
    (tmp_path / "translations").mkdir()
    (tmp_path / "translations" / "questions_fr.json").write_text(json.dumps({"data": [
        {"id": qid, "question": "x", "answers": ["a"], "wrong_answers": ["b", "c", "d"]}]}))
    client = MagicMock()
    monkeypatch.setattr(translate_questions, "_get_anthropic_client", lambda: client)
    assert translate_questions.run(language="fr") == 0
    client.messages.batches.create.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_translation_unit.py -q -k "batch_run"`
Expected: FAIL — `AttributeError: module 'translate_questions' has no attribute 'BATCH_POLL_INTERVAL'` / `_get_anthropic_client`.

- [ ] **Step 3: Replace the entire contents of `translate_questions.py`**

```python
#!/usr/bin/env python3
"""Backfill translations for existing English questions using the Anthropic
Batch API. Idempotent and interrupt-safe. Usage:

    python translate_questions.py                 # all target languages
    python translate_questions.py --language fr   # only French
    python translate_questions.py --limit 50      # first 50 English questions
"""
import argparse
import json
import logging
import time

from enrichment import (
    QUESTIONS_FILE,
    TARGET_LANGUAGES,
    _atomic_write_json,
    _stamp_ids,
    _validate_question,
    _write_lock,
)
from translation import (
    _append_translations,
    _build_batch_request,
    _get_anthropic_client,
    _load_translated_ids,
    _parse_batch_translation,
    _translation_record,
)

logger = logging.getLogger(__name__)

BATCH_POLL_INTERVAL = 30


def _load_and_stamp_originals() -> list:
    with _write_lock:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            store = json.load(f)
        if _stamp_ids(store["data"]):
            _atomic_write_json(store, QUESTIONS_FILE, indent=2)
        return store["data"]


def _submit_and_wait(client, requests: list):
    batch = client.messages.batches.create(requests=requests)
    logger.info("Submitted batch %s with %d requests", batch.id, len(requests))
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            return batch
        logger.info("Batch %s status=%s", batch.id, batch.processing_status)
        time.sleep(BATCH_POLL_INTERVAL)


def _collect_results(client, batch_id: str, targets: set) -> dict:
    """Return {lang: [records]} parsed from succeeded batch results."""
    per_lang = {l: [] for l in targets}
    for result in client.messages.batches.results(batch_id):
        qid = result.custom_id
        if result.result.type != "succeeded":
            logger.error("Batch item %s: %s", qid, result.result.type)
            continue
        text = next((b.text for b in result.result.message.content if b.type == "text"), "")
        try:
            parsed = _parse_batch_translation(text)
        except Exception as exc:
            logger.error("Parse failed for %s: %s", qid, str(exc)[:100])
            continue
        for lang, obj in parsed.items():
            if lang not in per_lang:
                continue
            rec = _translation_record(qid, obj)
            probe = {**rec, "category": "x", "difficulty": "easy",
                     "points": 1, "language": lang}
            if not _validate_question(probe):
                logger.error("Invalid translation %s (%s)", qid, lang)
                continue
            per_lang[lang].append(rec)
    return per_lang


def run(language: str = None, limit: int = None) -> int:
    data = _load_and_stamp_originals()
    english = [q for q in data if q.get("language") == "en"]
    if limit is not None:
        english = english[:limit]

    targets = {language} if language else set(TARGET_LANGUAGES)
    translated_ids = {l: _load_translated_ids(l) for l in targets}

    requests = []
    for q in english:
        missing = [l for l in sorted(targets) if q["id"] not in translated_ids[l]]
        if missing:
            requests.append(_build_batch_request(q, missing))

    if not requests:
        logger.info("Nothing to translate.")
        return 0

    client = _get_anthropic_client()
    batch = _submit_and_wait(client, requests)
    per_lang = _collect_results(client, batch.id, targets)

    total = 0
    for lang, records in per_lang.items():
        if records:
            _append_translations(lang, records)
            total += len(records)
            logger.info("Wrote %d %s translations", len(records), lang)
    logger.info("Backfill complete: %d translations added", total)
    return total


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Backfill question translations (Batch API)")
    parser.add_argument("--language", choices=sorted(TARGET_LANGUAGES), default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run(language=args.language, limit=args.limit)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the full suite (the old backfill tests were replaced)**

Run: `python3 -m pytest tests/ -q`
Expected: PASS. The pre-existing backfill tests `test_backfill_*` in `tests/test_translation_unit.py` reference the removed `_read_all`/`translate_and_persist` orchestration — if any now fail, delete those specific obsolete tests (the new `test_batch_run_*` tests replace them) and re-run.

- [ ] **Step 5: Commit**

```bash
git add translate_questions.py tests/test_translation_unit.py
git commit -m "feat: batch-api backfill orchestration"
```

---

### Task 5: Remove inline translation from the poller (`enrichment.py`)

**Files:**
- Modify: `enrichment.py` (delete the `translate_and_persist` block near line 410-416)
- Test: `tests/test_enrichment_unit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_enrichment_unit.py`:

```python
def test_poller_has_no_inline_translation():
    import inspect, enrichment
    assert "translate_and_persist" not in inspect.getsource(enrichment)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_enrichment_unit.py -q -k "no_inline_translation"`
Expected: FAIL — the string is still present.

- [ ] **Step 3: Delete the inline-translation block (enrichment.py:410-416)**

Remove exactly this block:

```python
    try:
        # A freshly enriched question is unique by construction, so no prior
        # (source_id, language) pairs can exist; pass an empty set.
        from translation import translate_and_persist
        translate_and_persist(enriched, set())
    except Exception as exc:
        logger.error("INLINE TRANSLATION FAILED: %s | Error: %s", question_text, str(exc)[:100])
```

Leave the surrounding `ENRICHMENT SUCCESS` log and `return True` intact.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_enrichment_unit.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add enrichment.py tests/test_enrichment_unit.py
git commit -m "refactor: remove inline translation from enrichment poller"
```

---

### Task 6: Serve merged per-language questions (`app.py`)

**Files:**
- Modify: `app.py` (import `TARGET_LANGUAGES`; `_load_questions`; `/questions`; `/languages`)
- Test: `tests/test_app_unit.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_unit.py`:

```python
def _seed(tmp_path):
    import json
    (tmp_path / "questions.json").write_text(json.dumps({"data": [
        {"id": "1", "question": "Q", "answers": ["a"], "wrong_answers": ["b"],
         "category": "geo", "difficulty": "easy", "points": 700, "language": "en"}]}))


def test_load_questions_en_returns_originals(tmp_path, monkeypatch):
    import app
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    assert app._load_questions("en")[0]["question"] == "Q"


def test_load_questions_merges_translation_metadata(tmp_path, monkeypatch):
    import json, app
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    (tmp_path / "translations").mkdir()
    (tmp_path / "translations" / "questions_fr.json").write_text(json.dumps({"data": [
        {"id": "1", "question": "Q-fr", "answers": ["a-fr"], "wrong_answers": ["b-fr"]}]}))
    fr = app._load_questions("fr")
    assert len(fr) == 1
    assert fr[0]["question"] == "Q-fr"
    assert fr[0]["category"] == "geo" and fr[0]["points"] == 700
    assert fr[0]["language"] == "fr"


def test_load_questions_skips_unknown_ids(tmp_path, monkeypatch):
    import json, app
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    (tmp_path / "translations").mkdir()
    (tmp_path / "translations" / "questions_fr.json").write_text(json.dumps({"data": [
        {"id": "999", "question": "orphan", "answers": ["a"], "wrong_answers": ["b"]}]}))
    assert app._load_questions("fr") == []


def test_load_questions_missing_file_returns_empty(tmp_path, monkeypatch):
    import json, app
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    assert app._load_questions("de") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_app_unit.py -q -k "load_questions"`
Expected: FAIL — `_load_questions()` takes no argument / merge behavior absent.

- [ ] **Step 3: Update the import (app.py:10)**

```python
from enrichment import start_background_poller, TARGET_LANGUAGES
```

- [ ] **Step 4: Replace `_load_questions` (app.py:34-36)**

```python
TRANSLATIONS_DIR = "translations"


def _lang_file(lang: str) -> str:
    return os.path.join(TRANSLATIONS_DIR, f"questions_{lang}.json")


def _load_originals() -> list:
    with open("questions.json", "r", encoding="utf-8") as f:
        return json.load(f)["data"]


def _load_questions(language: str = "en") -> list:
    originals = _load_originals()
    if language == "en":
        return originals
    path = _lang_file(language)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        translated = json.load(f)["data"]
    by_id = {q["id"]: q for q in originals if q.get("id")}
    merged = []
    for t in translated:
        base = by_id.get(t["id"])
        if not base:
            continue
        merged.append({
            "id": t["id"],
            "question": t["question"],
            "answers": t["answers"],
            "wrong_answers": t["wrong_answers"],
            "category": base["category"],
            "difficulty": base["difficulty"],
            "points": base["points"],
            "language": language,
        })
    return merged
```

- [ ] **Step 5: Update `/questions` to use the merged loader (app.py:156-162)**

Replace the `data = _load_questions()` + filter lines with:

```python
    data = _load_questions(language)

    if category:
        questions = get_questions_count(data, category, questions_count, difficulty)
    else:
        questions = get_questions_count(data=data, difficulty=difficulty, count=questions_count)
    return {"questions": questions}, 200
```

- [ ] **Step 6: Update `/languages` to count across files (app.py:172-179)**

Replace the body with:

```python
    counts = {"en": len(_load_originals())}
    for lang in sorted(TARGET_LANGUAGES):
        merged = _load_questions(lang)
        if merged:
            counts[lang] = len(merged)

    languages = [{"code": c, "count": n} for c, n in sorted(counts.items())]
    return {"languages": languages}, 200
```

- [ ] **Step 7: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: PASS (all).

- [ ] **Step 8: Commit**

```bash
git add app.py tests/test_app_unit.py
git commit -m "feat: serve merged per-language questions"
```

---

### Task 7: Pin the anthropic SDK (`requirements.txt`)

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add/upgrade the anthropic pin**

Ensure `requirements.txt` contains a Batches-capable version (the currently installed 0.40.0 predates the batch shapes used here). Add or update the line:

```
anthropic>=0.45.0
```

Leave existing Azure/OpenAI dependencies in place — `enrichment.py` still uses Azure.

- [ ] **Step 2: Upgrade locally so a real run would work**

Run: `python3 -m pip install -q -U "anthropic>=0.45.0" && python3 -c "import anthropic; print(anthropic.__version__)"`
Expected: prints a version ≥ 0.45.0.

- [ ] **Step 3: Run the full suite once more**

Run: `python3 -m pytest tests/ -q`
Expected: PASS (all) — the mocked-client tests are unaffected by the SDK version.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: pin anthropic>=0.45.0 for Batch API"
```

---

## Notes for the implementer

- **Do not run a live translation** — the Anthropic account currently has no credits, and prod deploy is a separate follow-up (per the spec's Deploy Notes). All tasks are validated by the mocked unit tests.
- After Task 4, if the obsolete `test_backfill_*` tests in `tests/test_translation_unit.py` (which reference the removed `_read_all`/`translate_and_persist`) fail, delete just those tests — the `test_batch_run_*` tests replace them.
- Keep `_translate_question` / `TRANSLATION_SYSTEM_PROMPT` in `translation.py` — they remain useful and are still covered by existing tests; this plan adds the batch path alongside them.

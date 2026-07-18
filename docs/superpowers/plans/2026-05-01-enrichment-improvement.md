# Enrichment Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `enrichment.py` to a two-pass pipeline that rewrites bad questions, simplifies to family-friendly language, expands answer variations, and deduplicates using Azure OpenAI embeddings stored in a sidecar file.

**Architecture:** Pass 1 transforms schema and rewrites "which of these" questions; Pass 2 simplifies language and expands answers using one of 4 selectable prompt variants; after Pass 2, an embedding is generated and checked for cosine similarity against `embeddings.json` before persisting.

**Tech Stack:** Python 3, Azure OpenAI (chat completions + embeddings), numpy, threading, existing Flask app

---

## File Map

| File | Change |
|---|---|
| `enrichment.py` | All logic changes — new prompts, new functions, updated pipeline |
| `requirements.txt` | Add `numpy` |
| `.gitignore` | Add `embeddings.json` |
| `.env` | Add `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`, `PROMPT_VARIANT`, `DEDUP_THRESHOLD` |
| `tests/test_enrichment_unit.py` | New unit test file |

---

## Task 1: Add numpy and gitignore embeddings.json

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Add numpy to requirements.txt**

Open `requirements.txt`. It currently contains:
```
Flask
requests
Flask-Limiter
flask-cors
gunicorn
openai
python-dotenv
```

Replace with:
```
Flask
requests
Flask-Limiter
flask-cors
gunicorn
openai
python-dotenv
numpy
```

- [ ] **Step 2: Add embeddings.json to .gitignore**

Open `.gitignore`. It currently contains:
```
.env
```

Replace with:
```
.env
embeddings.json
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt .gitignore
git commit -m "chore: add numpy dep, gitignore embeddings sidecar"
```

---

## Task 2: Update Pass 1 prompt to rewrite list-dependent questions

**Files:**
- Modify: `enrichment.py` (lines 28–41, the `_SYSTEM_PROMPT` constant)

- [ ] **Step 1: Write unit test for the new Pass 1 prompt rule**

Create `tests/test_enrichment_unit.py`:

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


def test_system_prompt_contains_which_of_these_rule():
    from enrichment import _SYSTEM_PROMPT
    assert "which of these" in _SYSTEM_PROMPT.lower()
    assert "one of the following" in _SYSTEM_PROMPT.lower()


def test_enrich_question_passes_system_prompt_to_api():
    from enrichment import _enrich_question
    raw_q = {
        "question": "Which of these NHL teams originally played in Atlanta?",
        "correct_answer": "Calgary Flames",
        "incorrect_answers": ["Colorado Avalanche", "Carolina Hurricanes", "New Jersey Devils"],
        "category": "Sports",
        "difficulty": "easy",
        "type": "multiple",
    }
    mock_result = {
        "question": "What is the name of the NHL team that originally played in Atlanta before relocating?",
        "answers": ["calgary flames", "the flames"],
        "wrong_answers": ["Colorado Avalanche", "Carolina Hurricanes", "New Jersey Devils"],
        "category": "sports",
        "difficulty": "easy",
        "points": 700,
        "language": "en",
    }
    mock_resp = _make_mock_response(mock_result)

    with patch("enrichment._get_az_client") as mock_client_fn:
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        mock_client_fn.return_value = client

        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o"}):
            result = _enrich_question(raw_q)

    call_args = client.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    system_msg = messages[0]
    assert system_msg["role"] == "system"
    assert "which of these" in system_msg["content"].lower()
    assert result["question"] == mock_result["question"]
```

- [ ] **Step 2: Run test to verify it fails (missing rule in prompt)**

```bash
cd /c/PycharmProfProjects/questions-api && python -m pytest tests/test_enrichment_unit.py::test_system_prompt_contains_which_of_these_rule -v
```

Expected: FAIL — `AssertionError` because current `_SYSTEM_PROMPT` doesn't mention "which of these".

- [ ] **Step 3: Replace `_SYSTEM_PROMPT` in enrichment.py**

Find this block in `enrichment.py` (lines 28–41):

```python
_SYSTEM_PROMPT = """You are a data transformation assistant converting a trivia question to a specific schema.

Output ONLY a single valid JSON object. No prose, no markdown, no explanation.

The object MUST have exactly these fields:
- "question": string — question text with HTML entities decoded (&amp;→&, &#039;→')
- "answers": array of strings — correct answer + natural lowercase variants (1–3 items)
- "wrong_answers": array of strings — the incorrect answers as provided
- "category": string — map to one of: "geography", "science", "history", "entertainment", "sports", "art", "technology", "nature", "food", "general"
- "difficulty": string — "easy"→"easy", "medium" or "hard"→"normal"
- "points": integer — easy=700, medium=800, hard=1000
- "language": "en"

No extra fields. Return only the JSON object."""
```

Replace with:

```python
_SYSTEM_PROMPT = """You are a data transformation assistant converting a trivia question to a specific schema.

Output ONLY a single valid JSON object. No prose, no markdown, no explanation.

IMPORTANT: If the question contains "which of these", "one of the following", "which one of", or any phrasing that assumes the player can see a list of options, rewrite it as a self-contained question that makes sense without options.
Example: "Which of these NHL teams originally played in Atlanta?" → "What is the name of the NHL team that originally played in Atlanta before relocating?"

The object MUST have exactly these fields:
- "question": string — question text with HTML entities decoded (&amp;→&, &#039;→'), rewritten if it was list-dependent
- "answers": array of strings — correct answer + natural lowercase variants (1–3 items)
- "wrong_answers": array of strings — the incorrect answers as provided
- "category": string — map to one of: "geography", "science", "history", "entertainment", "sports", "art", "technology", "nature", "food", "general"
- "difficulty": string — "easy"→"easy", "medium" or "hard"→"normal"
- "points": integer — easy=700, medium=800, hard=1000
- "language": "en"

No extra fields. Return only the JSON object."""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_enrichment_unit.py::test_system_prompt_contains_which_of_these_rule tests/test_enrichment_unit.py::test_enrich_question_passes_system_prompt_to_api -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add enrichment.py tests/test_enrichment_unit.py
git commit -m "feat: rewrite list-dependent questions in Pass 1 prompt"
```

---

## Task 3: Add SIMPLIFY_PROMPTS dict and new constants

**Files:**
- Modify: `enrichment.py` — add after `_SYSTEM_PROMPT`

- [ ] **Step 1: Write test for SIMPLIFY_PROMPTS structure**

Append to `tests/test_enrichment_unit.py`:

```python
def test_simplify_prompts_has_four_variants():
    from enrichment import SIMPLIFY_PROMPTS
    assert len(SIMPLIFY_PROMPTS) == 4
    for i in range(4):
        assert i in SIMPLIFY_PROMPTS
        assert isinstance(SIMPLIFY_PROMPTS[i], str)
        assert len(SIMPLIFY_PROMPTS[i]) > 50


def test_simplify_prompts_all_require_minimum_three_answers():
    from enrichment import SIMPLIFY_PROMPTS
    for i, prompt in SIMPLIFY_PROMPTS.items():
        assert "minimum 3" in prompt or "at least 3" in prompt, (
            f"Variant {i} prompt does not mention minimum 3 answer variations"
        )
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_enrichment_unit.py::test_simplify_prompts_has_four_variants tests/test_enrichment_unit.py::test_simplify_prompts_all_require_minimum_three_answers -v
```

Expected: FAIL — `ImportError: cannot import name 'SIMPLIFY_PROMPTS'`.

- [ ] **Step 3: Add SIMPLIFY_PROMPTS and new constants to enrichment.py**

After the `_SYSTEM_PROMPT` block, add:

```python
SIMPLIFY_PROMPTS = {
    0: """You are a quiz question editor for a family trivia game.

Your task: gently simplify the given question for a family audience (age 8 and up). Preserve the original meaning closely — only replace obscure words with simpler ones and remove context that would confuse a child.

Also expand the "answers" array to include at least 3 natural variations of the correct answer: abbreviations, alternate spellings, common shorthand, and casual speech forms.

Output ONLY a JSON object with exactly these fields:
- "question": string — the simplified question text
- "answers": array of strings (minimum 3) — natural variations of the correct answer in lowercase
- "wrong_answers": array of strings — simplified incorrect answers

No prose, no markdown, no explanation. Return only the JSON object.""",

    1: """You are a quiz question editor for a family trivia game.

Your task: completely rewrite the question to be as simple and accessible as possible for a family audience (age 8 and up). Freely rephrase — change sentence structure if needed. Eliminate ALL assumed knowledge. Add brief context if necessary (e.g. "the sport of soccer" instead of just "soccer"). Keep facts accurate.

Also expand the "answers" array to include at least 3 natural variations of the correct answer: abbreviations, alternate spellings, common shorthand, and casual speech forms.

Output ONLY a JSON object with exactly these fields:
- "question": string — the rewritten question text
- "answers": array of strings (minimum 3) — natural variations of the correct answer in lowercase
- "wrong_answers": array of strings — rewritten incorrect answers in plain language

No prose, no markdown, no explanation. Return only the JSON object.""",

    2: """You are an enthusiastic quiz host writing questions for a fun family trivia game.

Your task: gently simplify the question for a family audience (age 8 and up) using a warm, engaging game-show tone. Preserve the original meaning closely — only replace obscure words and add warmth to the phrasing. Make it feel like a fun game, not a school exam.

Also expand the "answers" array to include at least 3 natural variations of the correct answer: abbreviations, alternate spellings, common shorthand, and casual speech forms.

Output ONLY a JSON object with exactly these fields:
- "question": string — the simplified, fun question text
- "answers": array of strings (minimum 3) — natural variations of the correct answer in lowercase
- "wrong_answers": array of strings — simplified incorrect answers

No prose, no markdown, no explanation. Return only the JSON object.""",

    3: """You are an enthusiastic quiz host writing questions for a fun family trivia game.

Your task: completely rewrite the question to be as fun and accessible as possible for a family audience (age 8 and up). Use a playful, engaging game-show tone. Freely rephrase — change sentence structure if needed. Eliminate ALL assumed knowledge and add brief context where helpful. Make every question feel like an exciting challenge, not a test.

Also expand the "answers" array to include at least 3 natural variations of the correct answer: abbreviations, alternate spellings, common shorthand, and casual speech forms.

Output ONLY a JSON object with exactly these fields:
- "question": string — the rewritten, fun question text
- "answers": array of strings (minimum 3) — natural variations of the correct answer in lowercase
- "wrong_answers": array of strings — rewritten incorrect answers in plain, fun language

No prose, no markdown, no explanation. Return only the JSON object.""",
}

EMBEDDINGS_FILE = "embeddings.json"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_enrichment_unit.py::test_simplify_prompts_has_four_variants tests/test_enrichment_unit.py::test_simplify_prompts_all_require_minimum_three_answers -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add enrichment.py tests/test_enrichment_unit.py
git commit -m "feat: add SIMPLIFY_PROMPTS with 4 variants and EMBEDDINGS_FILE constant"
```

---

## Task 4: Add embedding utility functions

**Files:**
- Modify: `enrichment.py` — add `_get_embedding`, `_cosine_similarity`, `_is_semantic_duplicate`

- [ ] **Step 1: Write unit tests for cosine similarity and duplicate detection**

Append to `tests/test_enrichment_unit.py`:

```python
def test_cosine_similarity_identical_vectors():
    from enrichment import _cosine_similarity
    v = [1.0, 0.0, 0.5]
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal_vectors():
    from enrichment import _cosine_similarity
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_similarity(a, b)) < 1e-6


def test_is_semantic_duplicate_above_threshold():
    from enrichment import _is_semantic_duplicate
    import hashlib
    store = {
        hashlib.md5(b"existing").hexdigest(): [1.0, 0.0, 0.0],
    }
    with patch.dict("os.environ", {"DEDUP_THRESHOLD": "0.92"}):
        assert _is_semantic_duplicate([0.999, 0.001, 0.0], store) is True


def test_is_semantic_duplicate_below_threshold():
    from enrichment import _is_semantic_duplicate
    import hashlib
    store = {
        hashlib.md5(b"existing").hexdigest(): [1.0, 0.0, 0.0],
    }
    with patch.dict("os.environ", {"DEDUP_THRESHOLD": "0.92"}):
        assert _is_semantic_duplicate([0.0, 1.0, 0.0], store) is False


def test_is_semantic_duplicate_empty_store():
    from enrichment import _is_semantic_duplicate
    with patch.dict("os.environ", {"DEDUP_THRESHOLD": "0.92"}):
        assert _is_semantic_duplicate([1.0, 0.0], {}) is False
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_enrichment_unit.py::test_cosine_similarity_identical_vectors tests/test_enrichment_unit.py::test_cosine_similarity_orthogonal_vectors tests/test_enrichment_unit.py::test_is_semantic_duplicate_above_threshold tests/test_enrichment_unit.py::test_is_semantic_duplicate_below_threshold tests/test_enrichment_unit.py::test_is_semantic_duplicate_empty_store -v
```

Expected: FAIL — `ImportError: cannot import name '_cosine_similarity'`.

- [ ] **Step 3: Add imports and functions to enrichment.py**

At the top of `enrichment.py`, after the existing imports, add:

```python
import hashlib

import numpy as np
```

After the `_write_lock` line, add:

```python
_embeddings_lock = threading.Lock()
```

After `_get_az_client()`, add these three functions:

```python
def _get_embedding(text: str) -> list:
    client = _get_az_client()
    deployment = os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"]
    response = client.embeddings.create(model=deployment, input=text)
    return response.data[0].embedding


def _cosine_similarity(a: list, b: list) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))


def _is_semantic_duplicate(embedding: list, store: dict) -> bool:
    threshold = float(os.environ.get("DEDUP_THRESHOLD", "0.92"))
    for vec in store.values():
        if _cosine_similarity(embedding, vec) >= threshold:
            return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_enrichment_unit.py::test_cosine_similarity_identical_vectors tests/test_enrichment_unit.py::test_cosine_similarity_orthogonal_vectors tests/test_enrichment_unit.py::test_is_semantic_duplicate_above_threshold tests/test_enrichment_unit.py::test_is_semantic_duplicate_below_threshold tests/test_enrichment_unit.py::test_is_semantic_duplicate_empty_store -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add enrichment.py tests/test_enrichment_unit.py
git commit -m "feat: add embedding utility functions (cosine similarity, duplicate detection)"
```

---

## Task 5: Add embeddings sidecar load/save functions

**Files:**
- Modify: `enrichment.py` — add `_save_embeddings`, `_load_embeddings`, `_persist_embedding`

- [ ] **Step 1: Write tests for sidecar persistence**

Append to `tests/test_enrichment_unit.py`:

```python
import json
import os
import tempfile
import hashlib


def test_save_and_load_embeddings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # create a minimal questions.json
    (tmp_path / "questions.json").write_text(json.dumps({"data": []}))

    import importlib
    import enrichment
    importlib.reload(enrichment)

    store = {"abc123": [0.1, 0.2, 0.3]}
    enrichment._save_embeddings(store)

    assert (tmp_path / "embeddings.json").exists()
    loaded = json.loads((tmp_path / "embeddings.json").read_text())
    assert loaded == store


def test_load_embeddings_creates_file_if_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "questions.json").write_text(json.dumps({"data": []}))

    import importlib
    import enrichment
    importlib.reload(enrichment)

    with patch("enrichment._get_embedding", return_value=[0.1, 0.2]):
        result = enrichment._load_embeddings()

    assert isinstance(result, dict)


def test_persist_embedding_adds_to_store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "embeddings.json").write_text(json.dumps({}))

    import importlib
    import enrichment
    importlib.reload(enrichment)

    store = {}
    enrichment._persist_embedding("What is 2+2?", [0.5, 0.5], store)

    key = hashlib.md5("What is 2+2?".encode()).hexdigest()
    assert key in store
    assert store[key] == [0.5, 0.5]

    saved = json.loads((tmp_path / "embeddings.json").read_text())
    assert key in saved
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_enrichment_unit.py::test_save_and_load_embeddings_roundtrip tests/test_enrichment_unit.py::test_load_embeddings_creates_file_if_missing tests/test_enrichment_unit.py::test_persist_embedding_adds_to_store -v
```

Expected: FAIL — `ImportError: cannot import name '_save_embeddings'`.

- [ ] **Step 3: Add sidecar functions to enrichment.py**

After `_is_semantic_duplicate`, add:

```python
def _save_embeddings(store: dict) -> None:
    with tempfile.NamedTemporaryFile(
        "w", dir=".", suffix=".tmp", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(store, tmp, ensure_ascii=False)
        tmp_path = tmp.name
    os.replace(tmp_path, EMBEDDINGS_FILE)


def _load_embeddings() -> dict:
    if os.path.exists(EMBEDDINGS_FILE):
        with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
            store = json.load(f)
    else:
        store = {}

    with _write_lock:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            questions = json.load(f)["data"]

    to_backfill = [
        q for q in questions
        if hashlib.md5(q["question"].encode()).hexdigest() not in store
    ]

    if to_backfill:
        logger.info("Backfilling embeddings for %d questions", len(to_backfill))
        for q in to_backfill:
            try:
                key = hashlib.md5(q["question"].encode()).hexdigest()
                store[key] = _get_embedding(q["question"])
            except Exception as e:
                logger.warning("Backfill embedding failed for '%s': %s", q["question"][:60], e)
        _save_embeddings(store)

    return store


def _persist_embedding(question_text: str, embedding: list, store: dict) -> None:
    with _embeddings_lock:
        key = hashlib.md5(question_text.encode()).hexdigest()
        store[key] = embedding
        _save_embeddings(store)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_enrichment_unit.py::test_save_and_load_embeddings_roundtrip tests/test_enrichment_unit.py::test_load_embeddings_creates_file_if_missing tests/test_enrichment_unit.py::test_persist_embedding_adds_to_store -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add enrichment.py tests/test_enrichment_unit.py
git commit -m "feat: add embeddings sidecar load/save/persist functions"
```

---

## Task 6: Implement _simplify_question()

**Files:**
- Modify: `enrichment.py` — add `_simplify_question` after `_enrich_question`

- [ ] **Step 1: Write unit test for _simplify_question**

Append to `tests/test_enrichment_unit.py`:

```python
def test_simplify_question_merges_fields_from_llm():
    from enrichment import _simplify_question
    enriched = {
        "question": "What is the capital of France?",
        "answers": ["paris"],
        "wrong_answers": ["London", "Berlin", "Madrid"],
        "category": "geography",
        "difficulty": "easy",
        "points": 700,
        "language": "en",
    }
    mock_result = {
        "question": "What city is the capital of France?",
        "answers": ["paris", "paris france", "the city of paris"],
        "wrong_answers": ["london", "berlin", "madrid"],
    }
    mock_resp = _make_mock_response(mock_result)

    with patch("enrichment._get_az_client") as mock_client_fn:
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        mock_client_fn.return_value = client

        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o"}):
            result = _simplify_question(enriched, variant=0)

    assert result["question"] == "What city is the capital of France?"
    assert len(result["answers"]) == 3
    assert "paris" in result["answers"]


def test_simplify_question_uses_correct_variant_prompt():
    from enrichment import _simplify_question, SIMPLIFY_PROMPTS
    enriched = {
        "question": "Test question?",
        "answers": ["answer"],
        "wrong_answers": ["wrong1", "wrong2", "wrong3"],
        "category": "general",
        "difficulty": "easy",
        "points": 700,
        "language": "en",
    }
    mock_result = {
        "question": "Test question?",
        "answers": ["answer", "the answer", "an answer"],
        "wrong_answers": ["wrong1", "wrong2", "wrong3"],
    }

    for variant in range(4):
        mock_resp = _make_mock_response(mock_result)
        with patch("enrichment._get_az_client") as mock_client_fn:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_resp
            mock_client_fn.return_value = client

            with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o"}):
                _simplify_question(enriched, variant=variant)

            call_args = client.chat.completions.create.call_args
            messages = call_args.kwargs["messages"]
            system_msg = messages[0]
            assert system_msg["content"] == SIMPLIFY_PROMPTS[variant], (
                f"Variant {variant} used wrong prompt"
            )
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_enrichment_unit.py::test_simplify_question_merges_fields_from_llm tests/test_enrichment_unit.py::test_simplify_question_uses_correct_variant_prompt -v
```

Expected: FAIL — `ImportError: cannot import name '_simplify_question'`.

- [ ] **Step 3: Add _simplify_question to enrichment.py**

After `_enrich_question`, add:

```python
def _simplify_question(enriched: dict, variant: int) -> dict:
    client = _get_az_client()
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    question_text = enriched.get("question", "")[:80]

    payload = {
        "question": enriched["question"],
        "answers": enriched["answers"],
        "wrong_answers": enriched["wrong_answers"],
    }

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": SIMPLIFY_PROMPTS[variant]},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.4,
            max_tokens=512,
        )
        content = response.choices[0].message.content.strip()
        result = json.loads(content)
        logger.debug("Simplification succeeded (variant=%d): %s", variant, question_text)
        return result
    except json.JSONDecodeError as e:
        logger.error("Simplification JSON parse failed for '%s': %s", question_text, e)
        raise
    except Exception as e:
        logger.error("Simplification API call failed for '%s': %s", question_text, e)
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_enrichment_unit.py::test_simplify_question_merges_fields_from_llm tests/test_enrichment_unit.py::test_simplify_question_uses_correct_variant_prompt -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add enrichment.py tests/test_enrichment_unit.py
git commit -m "feat: implement _simplify_question() with 4-variant prompt selection"
```

---

## Task 7: Update _process_question() for two-pass + semantic dedup

**Files:**
- Modify: `enrichment.py` — replace `_process_question`

- [ ] **Step 1: Write integration test for updated _process_question**

Append to `tests/test_enrichment_unit.py`:

```python
def test_process_question_full_pipeline_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "questions.json").write_text(json.dumps({"data": []}))
    (tmp_path / "embeddings.json").write_text(json.dumps({}))

    import importlib
    import enrichment
    importlib.reload(enrichment)

    raw_q = {
        "question": "What is the capital of Germany?",
        "correct_answer": "Berlin",
        "incorrect_answers": ["Munich", "Hamburg", "Frankfurt"],
        "category": "Geography",
        "difficulty": "easy",
        "type": "multiple",
    }

    pass1_result = {
        "question": "What is the capital city of Germany?",
        "answers": ["berlin"],
        "wrong_answers": ["Munich", "Hamburg", "Frankfurt"],
        "category": "geography",
        "difficulty": "easy",
        "points": 700,
        "language": "en",
    }

    pass2_result = {
        "question": "What is the capital city of Germany?",
        "answers": ["berlin", "berlin germany", "the city of berlin"],
        "wrong_answers": ["munich", "hamburg", "frankfurt"],
    }

    mock_resp1 = _make_mock_response(pass1_result)
    mock_resp2 = _make_mock_response(pass2_result)
    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        return mock_resp1 if call_count["n"] == 1 else mock_resp2

    with patch("enrichment._get_az_client") as mock_client_fn, \
         patch("enrichment._get_embedding", return_value=[0.1, 0.2, 0.3]):
        client = MagicMock()
        client.chat.completions.create.side_effect = fake_create
        mock_client_fn.return_value = client

        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o",
                                        "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT": "text-embedding-ada-002",
                                        "DEDUP_THRESHOLD": "0.92"}):
            store = {}
            result = enrichment._process_question(raw_q, set(), store, variant=0)

    assert result is True
    saved = json.loads((tmp_path / "questions.json").read_text())
    assert len(saved["data"]) == 1
    assert saved["data"][0]["answers"] == ["berlin", "berlin germany", "the city of berlin"]


def test_process_question_skips_semantic_duplicate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "questions.json").write_text(json.dumps({"data": []}))
    (tmp_path / "embeddings.json").write_text(json.dumps({}))

    import importlib
    import enrichment
    importlib.reload(enrichment)

    raw_q = {
        "question": "What is the capital of France?",
        "correct_answer": "Paris",
        "incorrect_answers": ["Lyon", "Marseille", "Nice"],
        "category": "Geography",
        "difficulty": "easy",
        "type": "multiple",
    }

    pass1_result = {
        "question": "What is the capital of France?",
        "answers": ["paris"],
        "wrong_answers": ["Lyon", "Marseille", "Nice"],
        "category": "geography",
        "difficulty": "easy",
        "points": 700,
        "language": "en",
    }
    pass2_result = {
        "question": "What is the capital of France?",
        "answers": ["paris", "paris france", "city of paris"],
        "wrong_answers": ["lyon", "marseille", "nice"],
    }

    mock_resp1 = _make_mock_response(pass1_result)
    mock_resp2 = _make_mock_response(pass2_result)
    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        return mock_resp1 if call_count["n"] == 1 else mock_resp2

    existing_embedding = [1.0, 0.0, 0.0]
    new_embedding = [0.999, 0.001, 0.0]

    import hashlib
    existing_store = {hashlib.md5(b"existing question").hexdigest(): existing_embedding}

    with patch("enrichment._get_az_client") as mock_client_fn, \
         patch("enrichment._get_embedding", return_value=new_embedding):
        client = MagicMock()
        client.chat.completions.create.side_effect = fake_create
        mock_client_fn.return_value = client

        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o",
                                        "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT": "text-embedding-ada-002",
                                        "DEDUP_THRESHOLD": "0.92"}):
            result = enrichment._process_question(raw_q, set(), existing_store, variant=0)

    assert result is False
    saved = json.loads((tmp_path / "questions.json").read_text())
    assert len(saved["data"]) == 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_enrichment_unit.py::test_process_question_full_pipeline_success tests/test_enrichment_unit.py::test_process_question_skips_semantic_duplicate -v
```

Expected: FAIL — `_process_question` doesn't accept `embeddings_store` or `variant` yet.

- [ ] **Step 3: Replace _process_question in enrichment.py**

Find and replace the entire `_process_question` function (lines 144–171 in the original file):

```python
def _process_question(raw_q: dict, existing_texts: set, embeddings_store: dict, variant: int) -> bool:
    question_text = raw_q.get("question", "")[:80]

    if not _is_unique(question_text, existing_texts):
        logger.debug("Skipped duplicate (exact): %s", question_text)
        return False

    existing_texts.add(question_text.strip().lower())

    try:
        enriched = _enrich_question(raw_q)
    except Exception as exc:
        logger.error("ENRICHMENT FAILED (pass1): %s | Error: %s", question_text, str(exc)[:100])
        return False

    if not _validate_question(enriched):
        logger.error("VALIDATION FAILED (pass1): %s | Invalid schema", question_text)
        return False

    try:
        simplified = _simplify_question(enriched, variant)
    except Exception as exc:
        logger.error("ENRICHMENT FAILED (pass2): %s | Error: %s", question_text, str(exc)[:100])
        return False

    enriched["question"] = simplified["question"]
    enriched["answers"] = simplified["answers"]
    enriched["wrong_answers"] = simplified["wrong_answers"]

    if not _validate_question(enriched):
        logger.error("VALIDATION FAILED (pass2): %s | Invalid schema", question_text)
        return False

    try:
        embedding = _get_embedding(enriched["question"])
    except Exception as exc:
        logger.error("EMBEDDING FAILED: %s | Error: %s", question_text, str(exc)[:100])
        return False

    if _is_semantic_duplicate(embedding, embeddings_store):
        logger.info("Skipped semantic duplicate: %s", enriched["question"][:80])
        return False

    try:
        _persist_question(enriched)
        _persist_embedding(enriched["question"], embedding, embeddings_store)
    except Exception as exc:
        logger.error("PERSISTENCE FAILED: %s | Error: %s", question_text, str(exc)[:100])
        return False

    logger.info(
        "ENRICHMENT SUCCESS: %s | Category: %s | Difficulty: %s | Points: %d | variant=%d",
        enriched["question"][:80], enriched["category"], enriched["difficulty"],
        enriched["points"], variant,
    )
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_enrichment_unit.py::test_process_question_full_pipeline_success tests/test_enrichment_unit.py::test_process_question_skips_semantic_duplicate -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add enrichment.py tests/test_enrichment_unit.py
git commit -m "feat: two-pass enrichment pipeline with semantic dedup in _process_question"
```

---

## Task 8: Update _poll_once() and start_background_poller()

**Files:**
- Modify: `enrichment.py` — update `_poll_once`, `_polling_loop`, `start_background_poller`

- [ ] **Step 1: Replace _poll_once, _polling_loop, and start_background_poller in enrichment.py**

Find and replace the three functions starting at `def _poll_once()` through the end of `start_background_poller`:

```python
def _poll_once(embeddings_store: dict, variant: int) -> None:
    try:
        raw_questions = _fetch_opentdb_questions()
        logger.info("=== POLL START === Fetched %d questions from opentdb", len(raw_questions))

        with _write_lock:
            with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
                store = json.load(f)
        existing_texts = {q["question"].strip().lower() for q in store["data"]}
        initial_count = len(store["data"])

        added = sum(_process_question(rq, existing_texts, embeddings_store, variant) for rq in raw_questions)

        with _write_lock:
            with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
                final_count = len(json.load(f)["data"])

        logger.info("=== POLL END === Success: %d | Failed: %d | Total questions: %d → %d",
                    added, len(raw_questions) - added, initial_count, final_count)

    except Exception as exc:
        logger.error("=== POLL FAILED === Critical error: %s", exc, exc_info=True)


def _polling_loop(embeddings_store: dict, variant: int) -> None:
    while True:
        _poll_once(embeddings_store, variant)
        time.sleep(POLL_INTERVAL)


def start_background_poller() -> None:
    variant = int(os.environ.get("PROMPT_VARIANT", "0"))
    embeddings_store = _load_embeddings()
    t = threading.Thread(
        target=_polling_loop,
        args=(embeddings_store, variant),
        daemon=True,
        name="enrichment-poller",
    )
    t.start()
    logger.info(
        "=== ENRICHMENT POLLER STARTED === Interval: %ds | Model: %s | Endpoint: %s | Variant: %d",
        POLL_INTERVAL, os.environ.get("AZURE_OPENAI_DEPLOYMENT", "unknown"),
        os.environ.get("AZURE_OPENAI_ENDPOINT", "unknown")[:30], variant,
    )
```

- [ ] **Step 2: Run all unit tests to verify nothing broke**

```bash
python -m pytest tests/test_enrichment_unit.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add enrichment.py
git commit -m "feat: wire embeddings_store and variant through polling loop"
```

---

## Task 9: Update .env with new variables

**Files:**
- Modify: `.env`

- [ ] **Step 1: Add new env vars to .env**

Open `.env`. It currently ends with `AZURE_OPENAI_DEPLOYMENT=gpt-4o`. Append:

```
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002
PROMPT_VARIANT=0
DEDUP_THRESHOLD=0.92
```

Replace `text-embedding-ada-002` with your actual Azure embeddings deployment name if it differs.

- [ ] **Step 2: Verify app still imports cleanly**

```bash
cd /c/PycharmProfProjects/questions-api && python -c "import enrichment; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

`.env` is gitignored so nothing to commit here. Done.

---

## Task 10: Run full test suite and verify

- [ ] **Step 1: Run all unit tests**

```bash
python -m pytest tests/test_enrichment_unit.py -v
```

Expected: all tests PASS, 0 failures.

- [ ] **Step 2: Verify enrichment.py imports with no errors**

```bash
python -c "
from enrichment import (
    _SYSTEM_PROMPT, SIMPLIFY_PROMPTS, EMBEDDINGS_FILE,
    _get_embedding, _cosine_similarity, _is_semantic_duplicate,
    _save_embeddings, _load_embeddings, _persist_embedding,
    _simplify_question, _process_question, start_background_poller,
)
print('All symbols imported OK')
print(f'SIMPLIFY_PROMPTS variants: {list(SIMPLIFY_PROMPTS.keys())}')
"
```

Expected output:
```
All symbols imported OK
SIMPLIFY_PROMPTS variants: [0, 1, 2, 3]
```

- [ ] **Step 3: Final commit**

```bash
git add tests/test_enrichment_unit.py
git commit -m "test: complete unit test suite for enrichment v2 pipeline"
```

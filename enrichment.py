import hashlib
import json
import logging
import os
import tempfile
import threading
import time

import numpy as np
import requests
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

logger = logging.getLogger(__name__)

QUESTIONS_FILE = "questions.json"
OPENTDB_URL = "https://opentdb.com/api.php?amount=20&difficulty=easy&type=multiple"
POLL_INTERVAL = 720  # 10 fetches per hour

VALID_CATEGORIES = {
    "geography", "science", "history", "entertainment",
    "sports", "art", "technology", "nature", "food", "general",
}
VALID_DIFFICULTIES = {"easy", "normal"}

TARGET_LANGUAGES = {"de", "es", "fr", "lt", "ru", "hi"}
VALID_LANGUAGES = {"en"} | TARGET_LANGUAGES

_write_lock = threading.Lock()
_embeddings_lock = threading.Lock()

_SYSTEM_PROMPT = """You are a data transformation assistant converting a trivia question to a specific schema.

Output ONLY a single valid JSON object. No prose, no markdown, no explanation.

IMPORTANT: Rewrite any question that cannot be answered without seeing a list of options, OR that asks what was NOT / did NOT / is NOT true (negative-knowledge questions are confusing without options). Rewrite as a clear positive-knowledge question using the correct answer as your guide.
Examples:
- "Which of these NHL teams originally played in Atlanta?" → "What is the name of the NHL team that originally played in Atlanta before relocating?"
- "Which actor was not in the 2016 movie Suicide Squad?" → "Which actor appeared in the 2016 movie Suicide Squad?" (flip to ask about the correct_answer instead)
- "Which of the following is NOT a mammal?" → "Is a [correct_answer] classified as a mammal?"

The object MUST have exactly these fields:
- "question": string — question text with HTML entities decoded (&amp;→&, &#039;→'), rewritten if it was list-dependent
- "answers": array of strings — correct answer + natural lowercase variants (1–3 items)
- "wrong_answers": array of strings — the incorrect answers as provided
- "category": string — map to one of: "geography", "science", "history", "entertainment", "sports", "art", "technology", "nature", "food", "general"
- "difficulty": string — "easy"→"easy", "medium" or "hard"→"normal"
- "points": integer — easy=700, medium=800, hard=1000
- "language": "en"

No extra fields. Return only the JSON object."""

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


def _source_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _stamp_ids(data: list) -> bool:
    """Add `id = md5(question)` to any record missing one. Returns True if any
    id was added (the store then needs to be persisted)."""
    changed = False
    for q in data:
        if not q.get("id"):
            q["id"] = _source_id(q["question"])
            changed = True
    return changed


def _get_az_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2024-02-15-preview",
    )


_embedding_model = None
_embedding_model_lock = threading.Lock()


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        with _embedding_model_lock:
            if _embedding_model is None:
                from sentence_transformers import SentenceTransformer
                _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def _get_embedding(text: str) -> list:
    return _get_embedding_model().encode(text).tolist()


def _cosine_similarity(a: list, b: list) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm == 0:
        return 0.0
    return float(np.dot(va, vb) / norm)


def _is_semantic_duplicate(embedding: list, store: dict) -> bool:
    threshold = float(os.environ.get("DEDUP_THRESHOLD", "0.92"))
    for vec in store.values():
        if _cosine_similarity(embedding, vec) >= threshold:
            return True
    return False


def _atomic_replace(src: str, dst: str) -> None:
    for attempt in range(10):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05)


def _atomic_write_json(data, path: str, **dump_kwargs) -> None:
    """Atomically write `data` as JSON to `path`, writing through symlinks.

    If `path` is a symlink (e.g. a release-dir file symlinked into shared/ so
    it survives deploys), resolve to the real target and write the temp file
    alongside it. os.replace onto a symlink would otherwise replace the symlink
    itself with a regular file, silently breaking cross-deploy persistence.
    """
    target = os.path.realpath(path)
    target_dir = os.path.dirname(target) or "."
    with tempfile.NamedTemporaryFile(
        "w", dir=target_dir, suffix=".tmp", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, **dump_kwargs)
        tmp_path = tmp.name
    _atomic_replace(tmp_path, target)


def _save_embeddings(store: dict) -> None:
    _atomic_write_json(store, EMBEDDINGS_FILE)


def _load_embeddings() -> dict:
    store = {}
    if os.path.exists(EMBEDDINGS_FILE):
        try:
            with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
                store = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load embeddings sidecar, starting fresh: %s", e)

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


def _fetch_opentdb_questions() -> list:
    wait_times = [15, 30, 60]
    logger.info("Fetching questions from opentdb (up to %d retries)", len(wait_times))
    for attempt, wait in enumerate(wait_times, start=1):
        response = requests.get(OPENTDB_URL, timeout=10)
        if response.status_code == 429:
            logger.warning("opentdb rate limited (429), waiting %ds before retry %d/%d", wait, attempt, len(wait_times))
            time.sleep(wait)
            continue
        response.raise_for_status()
        payload = response.json()
        if payload.get("response_code") != 0:
            raise ValueError(f"opentdb non-zero response_code: {payload.get('response_code')}")
        return payload["results"]
    raise requests.exceptions.HTTPError("opentdb 429 persisted after all retries; skipping poll cycle")


def _is_unique(question_text: str, existing_texts: set) -> bool:
    return question_text.strip().lower() not in existing_texts


def _enrich_question(raw_q: dict) -> dict:
    client = _get_az_client()
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    question_text = raw_q.get("question", "")[:80]

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(raw_q, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=512,
        )

        content = response.choices[0].message.content.strip()
        result = json.loads(content)
        logger.debug("Enrichment succeeded: %s", question_text)
        return result
    except json.JSONDecodeError as e:
        logger.error("Enrichment JSON parse failed for '%s': %s", question_text, e)
        raise
    except Exception as e:
        logger.error("Enrichment API call failed for '%s': %s", question_text, e)
        raise


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


def _validate_question(q: dict) -> bool:
    if not isinstance(q, dict):
        return False

    required = {"question", "answers", "wrong_answers", "category", "difficulty", "points", "language"}
    if not required.issubset(q.keys()):
        return False

    if not isinstance(q["question"], str) or not q["question"].strip():
        return False
    if not isinstance(q["answers"], list) or not q["answers"]:
        return False
    if not all(isinstance(a, str) for a in q["answers"]):
        return False
    if not isinstance(q["wrong_answers"], list) or not q["wrong_answers"]:
        return False
    if not all(isinstance(a, str) for a in q["wrong_answers"]):
        return False
    if q["category"] not in VALID_CATEGORIES:
        return False
    if q["difficulty"] not in VALID_DIFFICULTIES:
        return False
    if not isinstance(q["points"], int) or not (700 <= q["points"] <= 1000):
        return False
    if q["language"] not in VALID_LANGUAGES:
        return False
    if "source_id" in q and (not isinstance(q["source_id"], str) or not q["source_id"]):
        return False

    return True


def _persist_question(q: dict) -> None:
    with _write_lock:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            store = json.load(f)

        existing_texts = {item["question"].strip().lower() for item in store["data"]}
        if not _is_unique(q["question"], existing_texts):
            logger.info("Skipping duplicate (race): %s", q["question"][:80])
            return

        q["id"] = q.get("id") or _source_id(q["question"])
        store["data"].append(q)

        _atomic_write_json(store, QUESTIONS_FILE, indent=2)


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
        enriched["question"] = simplified["question"]
        enriched["answers"] = simplified["answers"]
        enriched["wrong_answers"] = simplified["wrong_answers"]
    except Exception as exc:
        logger.error("ENRICHMENT FAILED (pass2): %s | Error: %s", question_text, str(exc)[:100])
        return False

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

    enriched["source_id"] = _source_id(enriched["question"])

    try:
        _persist_question(enriched)
        _persist_embedding(enriched["question"], embedding, embeddings_store)
    except Exception as exc:
        logger.error("PERSISTENCE FAILED: %s | Error: %s", question_text, str(exc)[:100])
        return False

    try:
        # A freshly enriched question is unique by construction, so no prior
        # (source_id, language) pairs can exist; pass an empty set.
        from translation import translate_and_persist
        translate_and_persist(enriched, set())
    except Exception as exc:
        logger.error("INLINE TRANSLATION FAILED: %s | Error: %s", question_text, str(exc)[:100])

    logger.info(
        "ENRICHMENT SUCCESS: %s | Category: %s | Difficulty: %s | Points: %d | variant=%d",
        enriched["question"][:80], enriched["category"], enriched["difficulty"],
        enriched["points"], variant,
    )
    return True


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
    if variant not in SIMPLIFY_PROMPTS:
        raise ValueError(f"PROMPT_VARIANT={variant} is not valid; must be one of {list(SIMPLIFY_PROMPTS)}")
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

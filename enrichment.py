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
POLL_INTERVAL = 360  # 10 fetches per hour

VALID_CATEGORIES = {
    "geography", "science", "history", "entertainment",
    "sports", "art", "technology", "nature", "food", "general",
}
VALID_DIFFICULTIES = {"easy", "normal"}

_write_lock = threading.Lock()
_embeddings_lock = threading.Lock()

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


def _get_az_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2024-02-15-preview",
    )


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


def _fetch_opentdb_questions() -> list:
    response = requests.get(OPENTDB_URL, timeout=10)
    response.raise_for_status()
    payload = response.json()
    if payload.get("response_code") != 0:
        raise ValueError(f"opentdb non-zero response_code: {payload.get('response_code')}")
    return payload["results"]


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
    if q["language"] != "en":
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

        store["data"].append(q)

        with tempfile.NamedTemporaryFile(
            "w", dir=".", suffix=".tmp", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(store, tmp, indent=2, ensure_ascii=False)
            tmp_path = tmp.name

        os.replace(tmp_path, QUESTIONS_FILE)


def _process_question(raw_q: dict, existing_texts: set) -> bool:
    question_text = raw_q.get("question", "")[:80]

    if not _is_unique(question_text, existing_texts):
        logger.debug("Skipped duplicate: %s", question_text)
        return False

    existing_texts.add(question_text.strip().lower())

    try:
        enriched = _enrich_question(raw_q)
    except Exception as exc:
        logger.error("ENRICHMENT FAILED: %s | Error: %s", question_text, str(exc)[:100])
        return False

    if not _validate_question(enriched):
        logger.error("VALIDATION FAILED: %s | Invalid schema", question_text)
        return False

    try:
        _persist_question(enriched)
    except Exception as exc:
        logger.error("PERSISTENCE FAILED: %s | Error: %s", question_text, str(exc)[:100])
        return False

    logger.info("ENRICHMENT SUCCESS: %s | Category: %s | Difficulty: %s | Points: %d",
                enriched["question"][:80], enriched["category"], enriched["difficulty"], enriched["points"])
    return True


def _poll_once() -> None:
    try:
        raw_questions = _fetch_opentdb_questions()
        logger.info("=== POLL START === Fetched %d questions from opentdb", len(raw_questions))

        with _write_lock:
            with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
                store = json.load(f)
        existing_texts = {q["question"].strip().lower() for q in store["data"]}
        initial_count = len(store["data"])

        added = sum(_process_question(rq, existing_texts) for rq in raw_questions)

        with _write_lock:
            with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
                final_count = len(json.load(f)["data"])

        logger.info("=== POLL END === Success: %d | Failed: %d | Total questions: %d → %d",
                    added, len(raw_questions) - added, initial_count, final_count)

    except Exception as exc:
        logger.error("=== POLL FAILED === Critical error: %s", exc, exc_info=True)


def _polling_loop() -> None:
    while True:
        _poll_once()
        time.sleep(POLL_INTERVAL)


def start_background_poller() -> None:
    t = threading.Thread(target=_polling_loop, daemon=True, name="enrichment-poller")
    t.start()
    logger.info("=== ENRICHMENT POLLER STARTED === Interval: %ds | Model: %s | Endpoint: %s",
                POLL_INTERVAL, os.environ.get("AZURE_OPENAI_DEPLOYMENT", "unknown"),
                os.environ.get("AZURE_OPENAI_ENDPOINT", "unknown")[:30])

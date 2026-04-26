import json
import logging
import os
import tempfile
import threading
import time

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


def _get_az_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2024-02-01",
    )


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
    return json.loads(content)


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
    question_text = raw_q.get("question", "")

    if not _is_unique(question_text, existing_texts):
        logger.info("Skipping duplicate: %s", question_text[:80])
        return False

    existing_texts.add(question_text.strip().lower())

    try:
        enriched = _enrich_question(raw_q)
    except Exception as exc:
        logger.warning("Enrich failed for question '%s': %s", question_text[:60], exc)
        return False

    if not _validate_question(enriched):
        logger.warning("Validation failed for question '%s'", question_text[:60])
        return False

    try:
        _persist_question(enriched)
    except Exception as exc:
        logger.error("Persist failed: %s", exc)
        return False

    logger.info("Added: %s", enriched["question"][:80])
    return True


def _poll_once() -> None:
    try:
        raw_questions = _fetch_opentdb_questions()
        logger.info("Fetched %d questions from opentdb.", len(raw_questions))

        with _write_lock:
            with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
                store = json.load(f)
        existing_texts = {q["question"].strip().lower() for q in store["data"]}

        added = sum(_process_question(rq, existing_texts) for rq in raw_questions)
        logger.info("Poll complete. Added %d new questions.", added)

    except Exception as exc:
        logger.error("Poll cycle failed: %s", exc, exc_info=True)


def _polling_loop() -> None:
    while True:
        _poll_once()
        time.sleep(POLL_INTERVAL)


def start_background_poller() -> None:
    t = threading.Thread(target=_polling_loop, daemon=True, name="enrichment-poller")
    t.start()
    logger.info("Background question poller started (interval=%ds).", POLL_INTERVAL)

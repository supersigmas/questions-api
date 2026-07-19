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
            probe = {**rec, "category": "general", "difficulty": "easy",
                     "points": 700, "language": lang}
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

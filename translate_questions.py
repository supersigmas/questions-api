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

from enrichment import QUESTIONS_FILE, TARGET_LANGUAGES, _source_id, _write_lock
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

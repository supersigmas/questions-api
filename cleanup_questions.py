#!/usr/bin/env python3
"""
One-time script to reprocess existing questions.json entries that have
list-dependent or negative-knowledge question phrasing through the full
enrichment Pass 1 + Pass 2 pipeline.

Usage:
    python cleanup_questions.py [--dry-run]
"""
import argparse
import json
import re
import sys

from dotenv import load_dotenv

load_dotenv()

BAD_PATTERNS = re.compile(
    r"\bwhich of (these|the following)\b"
    r"|\bone of the following\b"
    r"|\bwhich one of\b"
    r"|\bwas not\b"
    r"|\bwere not\b"
    r"|\bis not\b"
    r"|\bare not\b"
    r"|\bdid not\b"
    r"|\bnot (a|an|the)\b",
    re.IGNORECASE,
)

QUESTIONS_FILE = "questions.json"


def needs_cleanup(q: dict) -> bool:
    return bool(BAD_PATTERNS.search(q.get("question", "")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show matches without modifying anything")
    args = parser.parse_args()

    from enrichment import _enrich_question, _simplify_question, _validate_question, SIMPLIFY_PROMPTS
    import os

    variant = int(os.environ.get("PROMPT_VARIANT", "0"))
    if variant not in SIMPLIFY_PROMPTS:
        print(f"ERROR: PROMPT_VARIANT={variant} is invalid. Must be 0-3.")
        sys.exit(1)

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        store = json.load(f)

    bad = [q for q in store["data"] if needs_cleanup(q)]
    print(f"Found {len(bad)} questions to reprocess (out of {len(store['data'])} total)")

    if args.dry_run:
        for q in bad:
            print(f"  - {q['question'][:100]}")
        return

    fixed = 0
    failed = 0
    for q in bad:
        original_text = q["question"]
        raw_q = {
            "question": original_text,
            "correct_answer": q["answers"][0] if q["answers"] else "",
            "incorrect_answers": q.get("wrong_answers", []),
            "category": q.get("category", "general"),
            "difficulty": "easy" if q.get("difficulty") == "easy" else "medium",
            "type": "multiple",
        }

        try:
            enriched = _enrich_question(raw_q)
            if not _validate_question(enriched):
                print(f"  SKIP (invalid after pass1): {original_text[:80]}")
                failed += 1
                continue

            simplified = _simplify_question(enriched, variant)
            enriched["question"] = simplified["question"]
            enriched["answers"] = simplified["answers"]
            enriched["wrong_answers"] = simplified["wrong_answers"]

            if not _validate_question(enriched):
                print(f"  SKIP (invalid after pass2): {original_text[:80]}")
                failed += 1
                continue

            # Replace in store
            for i, existing in enumerate(store["data"]):
                if existing["question"] == original_text:
                    store["data"][i] = enriched
                    break

            print(f"  OK: {original_text[:60]!r} → {enriched['question'][:60]!r}")
            fixed += 1

        except Exception as e:
            print(f"  ERROR: {original_text[:60]!r} — {e}")
            failed += 1

    if fixed > 0:
        import tempfile
        import os
        with tempfile.NamedTemporaryFile("w", dir=".", suffix=".tmp", delete=False, encoding="utf-8") as tmp:
            json.dump(store, tmp, indent=2, ensure_ascii=False)
            tmp_path = tmp.name
        os.replace(tmp_path, QUESTIONS_FILE)
        print(f"\nDone. Fixed: {fixed} | Failed/skipped: {failed}")
    else:
        print(f"\nNothing written. Fixed: {fixed} | Failed/skipped: {failed}")


if __name__ == "__main__":
    main()

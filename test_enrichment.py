#!/usr/bin/env python3
"""Test script to verify enrichment functionality."""

import json
import sys
from enrichment import _fetch_opentdb_questions, _enrich_question, _validate_question

def test_enrichment():
    print("1. Fetching raw questions from OpenTDB...")
    try:
        raw_questions = _fetch_opentdb_questions()
        print(f"   ✓ Fetched {len(raw_questions)} questions")
    except Exception as e:
        print(f"   ✗ Failed to fetch: {e}")
        return False

    if not raw_questions:
        print("   ✗ No questions returned")
        return False

    raw_q = raw_questions[0]
    print(f"   Raw question: {raw_q['question'][:60]}...")

    print("\n2. Enriching first question...")
    try:
        enriched = _enrich_question(raw_q)
        print(f"   ✓ Enrichment succeeded")
        print(f"   Enriched question: {enriched.get('question', 'N/A')[:60]}...")
    except Exception as e:
        print(f"   ✗ Enrichment failed: {e}")
        return False

    print("\n3. Validating enriched question...")
    if _validate_question(enriched):
        print(f"   ✓ Validation passed")
        print(f"\n   Full enriched question:")
        print(json.dumps(enriched, indent=2, ensure_ascii=False))
        return True
    else:
        print(f"   ✗ Validation failed")
        print(f"   Enriched data: {json.dumps(enriched, indent=2, ensure_ascii=False)}")
        return False

if __name__ == "__main__":
    success = test_enrichment()
    sys.exit(0 if success else 1)

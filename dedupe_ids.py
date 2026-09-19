#!/usr/bin/env python3
"""
One-off cleanup: remove duplicate `id`s from every language file.

Historically 6 English questions were appended twice, and those duplicate ids
were copied into every translation file. Same `id` (= md5 of the English text)
must be unique per file — the API joins across languages by `id`, so a repeated
id is ambiguous. This keeps the FIRST occurrence of each id (the original,
since new records are appended) and drops any later occurrences.

Processes all 7 files (en, de, es, fr, lt, ru, hi). Idempotent: a second run
finds nothing to drop. Writes atomically.

Usage:
    python dedupe_ids.py [--dry-run]
"""
import argparse
import json
import os
import tempfile
import time

LANGS = ["en", "de", "es", "fr", "lt", "ru", "hi"]
QFILE = "translations/questions_{}.json"


def _atomic_write_json(data, path):
    target = os.path.realpath(path)
    target_dir = os.path.dirname(target) or "."
    with tempfile.NamedTemporaryFile("w", dir=target_dir, suffix=".tmp",
                                     delete=False, encoding="utf-8") as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    for attempt in range(10):
        try:
            os.replace(tmp_path, target)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    total_dropped = 0
    for lang in LANGS:
        path = QFILE.format(lang)
        if not os.path.exists(path):
            print(f"[{lang}] (no file, skipped)")
            continue
        with open(path, "r", encoding="utf-8") as f:
            store = json.load(f)
        data = store["data"]

        seen = set()
        kept = []
        dropped = []
        for q in data:
            qid = q["id"]
            if qid in seen:
                dropped.append(qid)
                continue
            seen.add(qid)
            kept.append(q)

        total_dropped += len(dropped)
        print(f"[{lang}] {len(data)} -> {len(kept)} "
              f"(dropped {len(dropped)} duplicate record(s))")
        for qid in dropped:
            print(f"      drop later occurrence: {qid}")

        if not args.dry_run and dropped:
            store["data"] = kept
            _atomic_write_json(store, path)

    if args.dry_run:
        print(f"\nDry run - nothing written. Would drop {total_dropped} record(s).")
    else:
        print(f"\nDone. Dropped {total_dropped} duplicate record(s) total.")


if __name__ == "__main__":
    main()

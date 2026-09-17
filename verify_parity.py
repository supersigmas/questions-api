#!/usr/bin/env python3
"""
Verify cross-language parity of the question corpus.

Checks that the 6 active language files
(translations/questions_<lang>.json for en, de, es, fr, lt, ru) all contain
exactly the same set of question `id`s. English is the reference.

Reports, per language:
  - count vs English
  - ids present in English but MISSING from this language
  - ids present in this language but EXTRA (not in English)

Hindi (hi) is intentionally excluded — it is not an active language for now.

Exit code 0 = all in parity; 1 = at least one mismatch.

Usage:
    python verify_parity.py
"""
import json
import os
import sys

ACTIVE_LANGS = ["en", "de", "es", "fr", "lt", "ru"]
QFILE = "translations/questions_{}.json"
REFERENCE = "en"


def load_ids(lang):
    path = QFILE.format(lang)
    if not os.path.exists(path):
        return None, f"missing file: {path}"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)["data"]
    ids = [q["id"] for q in data]
    seen, dupes = set(), set()
    for i in ids:
        if i in seen:
            dupes.add(i)
        seen.add(i)
    return {"ids": set(ids), "count": len(ids), "dupes": dupes}, None


def main():
    ref, err = load_ids(REFERENCE)
    if err:
        print(f"FATAL: cannot load reference ({REFERENCE}): {err}")
        return 1
    print(f"Reference {REFERENCE}: {ref['count']} questions "
          f"({len(ref['ids'])} unique ids)")
    if ref["dupes"]:
        print(f"  WARNING: {len(ref['dupes'])} duplicate id(s) in {REFERENCE}")

    ok = True
    for lang in ACTIVE_LANGS:
        if lang == REFERENCE:
            continue
        info, err = load_ids(lang)
        if err:
            print(f"[{lang}] FAIL - {err}")
            ok = False
            continue

        missing = ref["ids"] - info["ids"]   # in en, not in lang
        extra = info["ids"] - ref["ids"]     # in lang, not in en
        status = "OK" if not missing and not extra and not info["dupes"] else "FAIL"
        if status == "FAIL":
            ok = False

        print(f"[{lang}] {status} - {info['count']} questions "
              f"(en has {ref['count']})")
        if info["dupes"]:
            print(f"     duplicate ids: {len(info['dupes'])}")
        if missing:
            sample = list(missing)[:10]
            print(f"     MISSING {len(missing)} id(s) present in en: {sample}"
                  + (" ..." if len(missing) > 10 else ""))
        if extra:
            sample = list(extra)[:10]
            print(f"     EXTRA {len(extra)} id(s) not in en: {sample}"
                  + (" ..." if len(extra) > 10 else ""))

    print("\nPARITY OK" if ok else "\nPARITY MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

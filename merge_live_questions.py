#!/usr/bin/env python3
"""Three-way merge of repo question files into live (shared/) question files.

  base  = repo files at the last commit already reflected on the server
  repo  = repo files at the commit to roll out (origin/main)
  live  = the server's shared/translations files (poller/translation writes)

Rules per id:
  - id in repo but not live                 -> append repo record   (new questions)
  - id in all three, live == base, repo != base -> take repo record  (repo edits, e.g. answer length)
  - id in all three, live != base, repo != base -> CONFLICT, keep live, report
  - anything else (live-only ids, unchanged)  -> keep live untouched

Dry run by default; --apply writes atomically and keeps a .bak-<ts> copy.
Usage: merge_live_questions.py BASE_DIR REPO_DIR LIVE_DIR [--apply]
"""
import json
import os
import sys
import tempfile
import time

LANGS = ["en", "de", "es", "fr", "hi", "lt", "ru"]


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def by_id(data):
    return {q["id"]: q for q in data["data"] if q.get("id")}


def atomic_write(data, path):
    target = os.path.realpath(path)
    with tempfile.NamedTemporaryFile("w", dir=os.path.dirname(target), suffix=".tmp",
                                     delete=False, encoding="utf-8") as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    os.chmod(tmp_path, os.stat(target).st_mode & 0o777)
    os.replace(tmp_path, target)


def merge(base, repo, live):
    b, r = by_id(base) if base else {}, by_id(repo)
    live_ids = {q.get("id") for q in live["data"]}
    added = updated = 0
    conflicts = []
    out = []
    for q in live["data"]:
        i = q.get("id")
        if i in r and i in b and r[i] != b[i]:
            if q == b[i]:
                out.append(r[i])
                updated += 1
                continue
            if q != r[i]:
                conflicts.append(i)
        out.append(q)
    for i, q in r.items():
        if i not in live_ids:
            out.append(q)
            added += 1
    return {**live, "data": out}, added, updated, conflicts


def main():
    args = [a for a in sys.argv[1:] if a != "--apply"]
    apply = "--apply" in sys.argv
    if len(args) != 3:
        sys.exit(__doc__)
    base_dir, repo_dir, live_dir = args
    ts = time.strftime("%Y%m%d-%H%M%S")
    results = []
    for lang in LANGS:
        name = f"questions_{lang}.json"
        repo, live = load(os.path.join(repo_dir, name)), load(os.path.join(live_dir, name))
        if repo is None or live is None:
            print(f"{lang}: skipped (repo={repo is not None}, live={live is not None})")
            continue
        merged, added, updated, conflicts = merge(load(os.path.join(base_dir, name)), repo, live)
        ids = [q.get("id") for q in merged["data"]]
        assert len(ids) == len(set(ids)), f"{lang}: duplicate ids after merge"
        print(f"{lang}: live={len(live['data'])} +added={added} ~updated={updated} "
              f"conflicts={len(conflicts)} -> {len(merged['data'])}")
        for c in conflicts[:5]:
            print(f"   conflict (kept live): {c}")
        results.append((os.path.join(live_dir, name), live, merged, added + updated))
    if not apply:
        print("dry run — nothing written (pass --apply)")
        return
    for path, live, merged, changes in results:
        if not changes:
            continue
        with open(f"{os.path.realpath(path)}.bak-{ts}", "w", encoding="utf-8") as f:
            json.dump(live, f, ensure_ascii=False, indent=2)
        atomic_write(merged, path)
        print(f"wrote {path} (backup .bak-{ts})")


if __name__ == "__main__":
    main()

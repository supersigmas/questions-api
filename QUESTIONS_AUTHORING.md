# Question Authoring Instructions

**Audience:** any agent (or human) adding trivia questions to this corpus.
**Rule of thumb:** a question is not "added" until it exists in **every** language file, is **not a semantic duplicate**, and its **embedding is recorded**. Partial adds corrupt the corpus.

---

## 1. Data model (read this first)

- Source of truth: `translations/questions_en.json` — structure `{"data": [ {...}, ... ]}`.
- One file per language: `translations/questions_<lang>.json` for
  **`en, de, es, fr, lt, ru`** (6 active languages).
  > Hindi (`hi`) exists in the repo but is **excluded for now** — do not add or
  > require `hi` for new questions until it is re-enabled here.
- Every question is identified by:

  ```
  id = md5(english_question_text)          # hex digest, lowercase
  ```

  The **same `id`** is the join key across all 7 language files. `app.py`
  joins non-English requests back to English by `id`. If a translation's `id`
  doesn't match an English `id`, that translation is invisible to the API.

### Record schema (identical shape in every language file)

```json
{
  "question": "What is the largest ocean on Earth?",
  "points": 800,
  "language": "en",
  "answers": ["pacific ocean", "the pacific", "pacific"],
  "wrong_answers": ["Atlantic Ocean", "Indian Ocean", "Arctic Ocean", "Southern Ocean"],
  "category": "geography",
  "difficulty": "normal",
  "id": "d90572b7214c6f4a208b55b8972a76b1"
}
```

- `id` is **the same string** in all languages (it is md5 of the *English* text, never re-hashed per language).
- `category`, `difficulty`, `points` are **copied from the English source** into every translation — do not localize or vary them per language.
- `language` matches the file (`"en"`, `"de"`, …).

---

## 2. Formatting conventions (must match existing data)

| Field | Rule |
|-------|------|
| `answers` | **lowercase**, accepted-answer variants (synonyms, short forms, with/without article). At least one entry. This is what the game checks user input against. |
| `wrong_answers` | **lowercase** distractors. 4 is the norm (min 3). Must be plausible and clearly wrong. |

> **All answer strings are lowercase** — both `answers` and `wrong_answers`.
> Do not use Title/proper case in either field (e.g. `"osaka"`, not `"Osaka"`).
> Non-cased scripts (e.g. Hindi, Russian proper nouns) are written as-is;
> `str.lower()` is applied uniformly.
| `question` | Natural sentence in the target language, correct punctuation (e.g. French `?` is preceded by a space: `... ?`). |
| `points` | Tied to difficulty — see §4. Same value across all languages. |

Translations must be **real translations**, not English copied over. Proper nouns
that localize should localize (e.g. `Tokyo → Tokio` in de, `токио` in ru;
`Beijing → Pékin` in fr, `пекин` in ru). Names that don't localize stay as-is.

---

## 3. Languages: all-or-nothing

**Every new `id` MUST appear in all 6 active language files** (`en, de, es, fr, lt, ru`).

- `hi` (Hindi) is **excluded for now** — do not add new questions to it. It
  already lags the others and will be backfilled separately when re-enabled.
- Never commit a batch that adds an `id` to some languages but not others.
- Verify parity after writing (see §6 checklist). Counts across the 6 active
  files must be equal.

If you genuinely cannot produce a language yet, **do not write any language** for
that question — hold the whole question back rather than create a partial record.

Run `python verify_parity.py` after a batch to confirm the 6 active files agree.

---

## 4. Categories, difficulty, points

**Allowed `category`** (use an existing one unless the user explicitly asks for a new category):

```
art, asia, entertainment, food, gaming, general, geography, history,
literature, lithuania, math, movies, nature, science, sports, technology
```

**Allowed `difficulty`** and the matching `points`:

| difficulty | points |
|------------|--------|
| `easy`     | 700 |
| `normal`   | 800 (or 900 for harder "normal" items) |

Keep `points` consistent with difficulty. Do not invent difficulties like
`hard` — they are not served/used.

---

## 5. Duplication prevention (the critical part)

Three independent guards. **All three must pass** before a question is written.

### 5a. ID idempotency (exact-duplicate guard)
Before adding, check whether `md5(english_text)` already exists in
`translations/questions_en.json`. If it does, **skip** — the question is already
in the corpus. This makes re-running a batch safe.

### 5b. Semantic dedup (near-duplicate guard)
Exact-match is not enough — "What's the biggest ocean?" and "Which ocean is the
largest?" have different ids but are the same question. Guard against this with
embeddings:

- Sidecar file: `embeddings.json`, keyed by `id` (= md5 of English text),
  value = `all-MiniLM-L6-v2` embedding of the **English** question.
- For each candidate English question, compute its embedding and compare
  (cosine similarity) against **every** stored embedding.
- If `cosine ≥ DEDUP_THRESHOLD` (env, default **0.92**) → **skip and report**
  the collision. Do not write it.
- Only when it passes: write the question to all languages **and** store its
  embedding in `embeddings.json` under its `id`.

Reuse the project's own functions — do not re-implement:

```python
from enrichment import _get_embedding, _cosine_similarity   # local MiniLM
```

### 5c. Within-batch dedup
Also compare each new question against the *others in the same batch* (same
embedding check), so a batch can't introduce internal near-duplicates.

> The background enrichment poller (`enrichment.py`) already does 5a+5b for
> auto-scraped English questions. When you add questions **manually**, you are
> responsible for running the same checks. `add_asia_questions.py` is the
> canonical reference implementation — copy its structure.

---

## 6. Write safety & workflow

### Writing
- All files are plain JSON with `indent=2`, `ensure_ascii=False` (keep native
  scripts readable, not `\uXXXX`).
- **Never** do a naive `open(...,"w")` on `questions_en.json` — the enrichment
  poller writes it concurrently. Use an **atomic replace** (write temp file in
  the same dir, then `os.replace`, retrying on Windows `PermissionError`). Copy
  `_atomic_write_json` from `add_asia_questions.py` / `enrichment._atomic_replace`.
- Append to `data`; never reorder or rewrite existing entries.

### Recommended flow for a new batch
1. Author the questions as structured data: for each item, `difficulty`,
   `points`, `category`, and a per-language `{question, answers, wrong_answers}`.
2. For each item compute `id = md5(english_question)`.
3. Guard: skip if `id` already in `questions_en.json` (5a); skip if semantic
   collision vs `embeddings.json` or within-batch (5b/5c) — **report** skips.
4. For survivors, append the record to **all 6 active** language files (`en, de, es, fr, lt, ru`).
5. Store the English embedding in `embeddings.json` under `id`.
6. Write every file atomically.
7. Support `--dry-run` (report what would be added/skipped, write nothing).

### Post-write checklist (verify before committing)
- [ ] `en, de, es, fr, lt, ru` all have the **same `id` count** (`python verify_parity.py`).
- [ ] Each new `id` is present in **all 6 active** files.
- [ ] `answers` **and** `wrong_answers` all lowercase; ≥1 answer, ≥3 wrong.
- [ ] `category` from the allowed set; `difficulty`/`points` consistent (§4).
- [ ] `id` == md5 of that record's **English** question text.
- [ ] New ids have entries in `embeddings.json`.
- [ ] No collision at threshold 0.92 was silently written.
- [ ] Files still valid JSON (`{"data":[...]}`), UTF-8, native scripts intact.

---

## 7. Reference

- `add_asia_questions.py` — canonical, idempotent, dedup-aware batch adder.
  Clone it for new batches; change `CATEGORY`, `LANGS` (keep `hi` out), and
  `QUESTIONS`.
- `verify_parity.py` — asserts equal `id` counts across the 6 active files and
  lists any missing ids. Run after every batch.
- `enrichment.py` — `_source_id`, `_get_embedding`, `_cosine_similarity`,
  `_is_semantic_duplicate`, `_atomic_replace`, `_write_lock`.
- `CLAUDE.md` — architecture, endpoints, env vars.

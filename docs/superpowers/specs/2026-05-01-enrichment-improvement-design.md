# Enrichment Improvement Design

**Date:** 2026-05-01  
**Branch:** feature/background-enrichment  
**Status:** Approved

## Overview

Improve the background question enrichment pipeline in `enrichment.py` to produce higher-quality, family-friendly questions with semantic deduplication and experimentable prompt variants.

## Goals

1. Rewrite "which of these / one of the following" questions into self-contained form
2. Simplify all questions to family-friendly level (accessible to age 8+)
3. Expand correct answer variations to at least 3 per question
4. Replace exact-string dedup with embedding-based semantic dedup
5. Support 4 prompt variants for experimentation

## Architecture: Two-Pass Enrichment

### Pass 1 — Schema Transform + Question Rewrite (`_enrich_question`)

Unchanged responsibility: transform raw opentdb JSON into the internal schema. Extended with one additional rule: any question containing "which of these", "one of the following", or similar list-dependent phrasing must be rewritten as a self-contained question.

**Example:**  
Before: *"Which of these NHL teams originally played in Atlanta?"*  
After: *"What is the name of the NHL team that originally played in Atlanta before relocating?"*

Temperature: 0.2 (reliable JSON output). Returns full enriched question object.

### Pass 2 — Simplification + Answer Expansion (`_simplify_question`)

New LLM call on the Pass 1 output. Responsibilities:
- Rewrite `question` field to plain, family-friendly vocabulary — no niche sports knowledge, no assumed cultural context, accessible to age 8+
- Simplify `answers` and `wrong_answers` if they contain jargon
- Expand `answers` array to at least 3 natural variations of the correct answer (abbreviations, common shorthand, alternate spellings, casual speech forms)

**Example answers expansion:**  
`["united states"]` → `["united states", "usa", "the us", "america", "u.s.a."]`

Returns updated `question`, `answers`, `wrong_answers` fields only; other fields pass through unchanged.

Variant selected via `PROMPT_VARIANT` env var (see Prompt Variants section).

## Semantic Deduplication

### Embeddings Sidecar (`embeddings.json`)

Structure: flat JSON dict mapping `md5(question_text)` → embedding vector array.

```json
{
  "a1b2c3...": [0.123, 0.456, ...],
  "d4e5f6...": [0.789, 0.012, ...]
}
```

**Startup behaviour:**
1. Load `embeddings.json` (create empty `{}` if missing)
2. For each question in `questions.json` with no entry in the sidecar, generate its embedding via Azure OpenAI Embeddings API and add it — one-time backfill per restart

**Runtime behaviour:**
1. After Pass 2 succeeds, generate embedding for the new question text
2. Compute cosine similarity against all in-memory embeddings
3. If max similarity >= `DEDUP_THRESHOLD` (default `0.92`, tunable via env var) → skip as duplicate
4. If unique → persist question to `questions.json`, append embedding to `embeddings.json` (atomic write, same pattern as questions file), update in-memory embedding list

The in-memory embedding list is the source of truth during a poll cycle; the sidecar file persists it across restarts.

### Configuration

| Env var | Default | Purpose |
|---|---|---|
| `DEDUP_THRESHOLD` | `0.92` | Cosine similarity threshold for duplicate detection |
| `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` | — | Embeddings model deployment name |

## Prompt Variants

4 variants stored in `SIMPLIFY_PROMPTS` dict, selected by `PROMPT_VARIANT` env var (default `0`):

| Variant | Simplification | Tone |
|---|---|---|
| 0 | Gentle | Neutral |
| 1 | Aggressive | Neutral |
| 2 | Gentle | Playful/fun |
| 3 | Aggressive | Playful/fun |

**Gentle simplification:** preserves original meaning closely, only replaces obscure words and removes assumed context.  
**Aggressive simplification:** freely rephrases to maximize accessibility, may change sentence structure significantly.  
**Neutral tone:** factual, direct phrasing.  
**Playful tone:** warm, engaging phrasing suited to a game show / family quiz context.

### Variant Logging

Every `ENRICHMENT SUCCESS` log line includes `variant=N`:

```
ENRICHMENT SUCCESS: What animal is known as... | Category: nature | Difficulty: easy | Points: 700 | variant=2
```

To compare variants after running:
```bash
grep "variant=0" app.log
grep "variant=2" app.log
```

Switch variants by updating `PROMPT_VARIANT` in `.env` and restarting.

## Data Flow

```
opentdb raw question
       ↓
  Pass 1: _enrich_question()
  - Schema transform
  - Rewrite "which of these" questions
       ↓
  Pass 2: _simplify_question(variant=N)
  - Family-friendly rewrite
  - Answer variation expansion (≥3 variants)
       ↓
  Embedding generation
       ↓
  Cosine similarity check vs embeddings.json
  - Duplicate? → skip, log
  - Unique? → persist to questions.json + embeddings.json
```

## Files Changed

- `enrichment.py` — main changes: add `_simplify_question()`, update `_enrich_question()` prompt, replace `_is_unique()` with embedding-based dedup, add sidecar load/save logic, add `SIMPLIFY_PROMPTS` dict
- `.env.example` — add `PROMPT_VARIANT`, `DEDUP_THRESHOLD`, `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`
- `requirements.txt` — add `numpy` (for cosine similarity) if not already present
- `embeddings.json` — new file, created automatically on first run, git-ignored

## Out of Scope

- Storing quality scores in question objects
- Vector database (sidecar file is sufficient at this scale)
- Automated prompt variant scoring/comparison

import json
import logging
import os

from enrichment import (
    TARGET_LANGUAGES,
    _get_az_client,
    _persist_question,
    _source_id,
    _validate_question,
)

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "lt": "Lithuanian",
    "ru": "Russian",
    "hi": "Hindi",
}

TRANSLATION_SYSTEM_PROMPT = """You are a translation assistant for a family trivia game.

Translate the given trivia question into {language_name} ({language_code}).

Output ONLY a single valid JSON object. No prose, no markdown, no explanation.

The object MUST have exactly these fields:
- "question": string - the question translated naturally into {language_name}
- "answers": array of strings - natural LOWERCASE variants of the correct answer in {language_name} (keep 1-3 items, same meaning as the source)
- "wrong_answers": array of strings - the incorrect answers translated into {language_name}

Preserve the meaning and difficulty. Do not add or remove answer options.
Return only the JSON object."""


def _translate_question(source_q: dict, lang: str) -> dict:
    client = _get_az_client()
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    system_prompt = TRANSLATION_SYSTEM_PROMPT.format(
        language_name=LANGUAGE_NAMES[lang], language_code=lang
    )
    payload = {
        "question": source_q["question"],
        "answers": source_q["answers"],
        "wrong_answers": source_q["wrong_answers"],
    }
    preview = source_q.get("question", "")[:80]
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=512,
        )
        content = response.choices[0].message.content.strip()
        translated = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("Translation JSON parse failed (%s) for '%s': %s", lang, preview, e)
        raise
    except Exception as e:
        logger.error("Translation API call failed (%s) for '%s': %s", lang, preview, e)
        raise

    return {
        "question": translated["question"],
        "answers": translated["answers"],
        "wrong_answers": translated["wrong_answers"],
        "category": source_q["category"],
        "difficulty": source_q["difficulty"],
        "points": source_q["points"],
        "language": lang,
        "source_id": _source_id(source_q["question"]),
    }


def _existing_pairs(data: list) -> set:
    """Set of (source_id, language) already present among translation records."""
    pairs = set()
    for q in data:
        if q.get("language") == "en":
            continue
        sid = q.get("source_id")
        if sid:
            pairs.add((sid, q["language"]))
    return pairs


def translate_and_persist(source_q: dict, existing: set) -> int:
    """Translate one English question into all missing target languages.

    `existing` is a mutable set of (source_id, language); it is updated in place
    as translations are persisted so callers stay idempotent within a run.
    Returns the number of translations added.
    """
    sid = source_q.get("source_id") or _source_id(source_q["question"])
    added = 0
    for lang in sorted(TARGET_LANGUAGES):
        if (sid, lang) in existing:
            continue
        try:
            translated = _translate_question(source_q, lang)
        except Exception as exc:
            logger.error("TRANSLATION FAILED: %s (%s) | %s",
                         source_q["question"][:80], lang, str(exc)[:100])
            continue
        if not _validate_question(translated):
            logger.error("TRANSLATION INVALID: %s (%s)", source_q["question"][:80], lang)
            continue
        try:
            _persist_question(translated)
        except Exception as exc:
            logger.error("TRANSLATION PERSIST FAILED: %s (%s) | %s",
                         source_q["question"][:80], lang, str(exc)[:100])
            continue
        existing.add((sid, lang))
        added += 1
        logger.info("TRANSLATION SUCCESS: %s | %s", source_q["question"][:80], lang)
    return added

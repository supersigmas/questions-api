import json
import logging
import os

from enrichment import (
    TARGET_LANGUAGES,
    _get_az_client,
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

import json
from unittest.mock import MagicMock, patch


def _make_mock_response(content: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = json.dumps(content)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _source_en():
    return {
        "question": "What is the largest ocean on Earth?",
        "answers": ["pacific ocean", "pacific"],
        "wrong_answers": ["Atlantic Ocean", "Indian Ocean"],
        "category": "geography",
        "difficulty": "normal",
        "points": 800,
        "language": "en",
    }


def test_translate_prompt_requires_lowercase_answers():
    from translation import TRANSLATION_SYSTEM_PROMPT
    assert "lowercase" in TRANSLATION_SYSTEM_PROMPT.lower()
    assert "json" in TRANSLATION_SYSTEM_PROMPT.lower()


def test_translate_question_sets_language_and_copies_fields():
    from translation import _translate_question
    mock_result = {
        "question": "Koks didziausias vandenynas Zemeje?",
        "answers": ["ramusis vandenynas", "ramusis"],
        "wrong_answers": ["Atlanto vandenynas", "Indijos vandenynas"],
    }
    mock_resp = _make_mock_response(mock_result)

    with patch("translation._get_az_client") as mock_client_fn:
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        mock_client_fn.return_value = client
        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o"}):
            result = _translate_question(_source_en(), "lt")

    assert result["language"] == "lt"
    assert result["question"] == mock_result["question"]
    assert result["answers"] == mock_result["answers"]
    assert result["category"] == "geography"
    assert result["difficulty"] == "normal"
    assert result["points"] == 800
    import hashlib
    assert result["source_id"] == hashlib.md5(_source_en()["question"].encode()).hexdigest()


def test_translate_question_passes_target_language_to_prompt():
    from translation import _translate_question
    mock_resp = _make_mock_response({
        "question": "x", "answers": ["a"], "wrong_answers": ["b"],
    })
    with patch("translation._get_az_client") as mock_client_fn:
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        mock_client_fn.return_value = client
        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o"}):
            _translate_question(_source_en(), "de")
    _, kwargs = client.chat.completions.create.call_args
    joined = " ".join(m["content"] for m in kwargs["messages"])
    assert "de" in joined or "German" in joined


def test_existing_pairs_collects_source_id_language():
    from translation import _existing_pairs
    data = [
        {"question": "Q1", "language": "en"},
        {"question": "t", "language": "lt", "source_id": "sid1"},
        {"question": "t", "language": "de", "source_id": "sid1"},
    ]
    pairs = _existing_pairs(data)
    assert ("sid1", "lt") in pairs
    assert ("sid1", "de") in pairs


def test_translate_and_persist_skips_existing_languages():
    from translation import translate_and_persist, _source_id
    src = _source_en()
    sid = _source_id(src["question"])
    existing = {(sid, "lt"), (sid, "de"), (sid, "es"),
                (sid, "fr"), (sid, "ru"), (sid, "hi")}

    with patch("translation._translate_question") as mock_tr, \
         patch("translation._persist_question") as mock_persist:
        added = translate_and_persist(src, existing)

    assert added == 0
    mock_tr.assert_not_called()
    mock_persist.assert_not_called()


def test_translate_and_persist_translates_missing_languages():
    from translation import translate_and_persist, _source_id
    src = _source_en()
    sid = _source_id(src["question"])
    existing = {(sid, "de"), (sid, "es"), (sid, "fr"), (sid, "ru"), (sid, "hi")}

    def fake_translate(source_q, lang):
        return {
            "question": "x", "answers": ["a"], "wrong_answers": ["b"],
            "category": "geography", "difficulty": "normal", "points": 800,
            "language": lang, "source_id": sid,
        }

    with patch("translation._translate_question", side_effect=fake_translate) as mock_tr, \
         patch("translation._persist_question") as mock_persist:
        added = translate_and_persist(src, existing)

    assert added == 1  # only "lt" was missing
    mock_tr.assert_called_once_with(src, "lt")
    mock_persist.assert_called_once()
    assert existing == {(sid, l) for l in ("de", "es", "fr", "ru", "hi", "lt")}


def test_translate_and_persist_skips_invalid_result():
    from translation import translate_and_persist, _source_id
    src = _source_en()
    sid = _source_id(src["question"])
    existing = {(sid, l) for l in ("de", "es", "fr", "ru", "hi")}

    def bad_translate(source_q, lang):
        return {"question": "", "answers": [], "wrong_answers": [],
                "category": "geography", "difficulty": "normal", "points": 800,
                "language": lang, "source_id": sid}

    with patch("translation._translate_question", side_effect=bad_translate), \
         patch("translation._persist_question") as mock_persist:
        added = translate_and_persist(src, existing)

    assert added == 0
    mock_persist.assert_not_called()


def test_translate_and_persist_skips_when_translation_raises():
    from translation import translate_and_persist, _source_id
    src = _source_en()
    sid = _source_id(src["question"])
    existing = {(sid, l) for l in ("de", "es", "fr", "ru", "hi")}  # only "lt" missing

    with patch("translation._translate_question", side_effect=RuntimeError("api down")), \
         patch("translation._persist_question") as mock_persist:
        added = translate_and_persist(src, existing)

    assert added == 0
    mock_persist.assert_not_called()
    assert (sid, "lt") not in existing


def test_translate_and_persist_skips_when_persist_raises():
    from translation import translate_and_persist, _source_id
    src = _source_en()
    sid = _source_id(src["question"])
    existing = {(sid, l) for l in ("de", "es", "fr", "ru", "hi")}  # only "lt" missing

    def ok_translate(source_q, lang):
        return {
            "question": "x", "answers": ["a"], "wrong_answers": ["b"],
            "category": "geography", "difficulty": "normal", "points": 800,
            "language": lang, "source_id": sid,
        }

    with patch("translation._translate_question", side_effect=ok_translate), \
         patch("translation._persist_question", side_effect=OSError("disk full")):
        added = translate_and_persist(src, existing)

    assert added == 0
    assert (sid, "lt") not in existing

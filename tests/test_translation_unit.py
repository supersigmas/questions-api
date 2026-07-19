import json
from unittest.mock import MagicMock, patch


def _make_mock_response(content: dict) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(content)
    resp = MagicMock()
    resp.content = [block]
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

    with patch("translation._get_anthropic_client") as mock_client_fn:
        client = MagicMock()
        client.messages.create.return_value = mock_resp
        mock_client_fn.return_value = client
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
    with patch("translation._get_anthropic_client") as mock_client_fn:
        client = MagicMock()
        client.messages.create.return_value = mock_resp
        mock_client_fn.return_value = client
        _translate_question(_source_en(), "de")
    _, kwargs = client.messages.create.call_args
    joined = kwargs["system"] + " ".join(m["content"] for m in kwargs["messages"])
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


def test_backfill_run_translates_english_records():
    import translate_questions
    from unittest.mock import patch
    data = [
        {"question": "Q1", "answers": ["a"], "wrong_answers": ["b"],
         "category": "geography", "difficulty": "easy", "points": 700, "language": "en"},
        {"question": "Q2", "answers": ["c"], "wrong_answers": ["d"],
         "category": "science", "difficulty": "easy", "points": 700, "language": "en"},
    ]
    calls = []

    def fake_tap(source_q, existing):
        calls.append(source_q["question"])
        return 6

    with patch.object(translate_questions, "_read_all", return_value=data), \
         patch.object(translate_questions, "translate_and_persist", side_effect=fake_tap):
        total = translate_questions.run(language=None, limit=None)

    assert total == 12
    assert calls == ["Q1", "Q2"]


def test_backfill_respects_limit():
    import translate_questions
    from unittest.mock import patch
    data = [
        {"question": f"Q{i}", "answers": ["a"], "wrong_answers": ["b"],
         "category": "geography", "difficulty": "easy", "points": 700, "language": "en"}
        for i in range(5)
    ]
    with patch.object(translate_questions, "_read_all", return_value=data), \
         patch.object(translate_questions, "translate_and_persist", return_value=1) as m:
        translate_questions.run(language=None, limit=2)
    assert m.call_count == 2


def test_backfill_language_flag_restricts_to_one_language():
    import translate_questions
    from unittest.mock import patch
    from enrichment import _source_id, TARGET_LANGUAGES
    data = [
        {"question": "Q1", "answers": ["a"], "wrong_answers": ["b"],
         "category": "geography", "difficulty": "easy", "points": 700, "language": "en"},
    ]
    sid = _source_id("Q1")
    captured = {}

    def capture_tap(source_q, existing):
        # snapshot the set as seen for this question
        captured["existing"] = set(existing)
        return 0

    with patch.object(translate_questions, "_read_all", return_value=data), \
         patch.object(translate_questions, "translate_and_persist", side_effect=capture_tap):
        translate_questions.run(language="lt", limit=None)

    # every non-chosen target language is pre-blocked for this source
    for other in TARGET_LANGUAGES - {"lt"}:
        assert (sid, other) in captured["existing"]
    # the chosen language is NOT pre-blocked, so it remains translatable
    assert (sid, "lt") not in captured["existing"]


def test_lang_file_path():
    from translation import _lang_file
    assert _lang_file("fr").replace("\\", "/").endswith("translations/questions_fr.json")


def test_load_translated_ids_empty_when_missing(tmp_path, monkeypatch):
    import translation
    monkeypatch.chdir(tmp_path)
    assert translation._load_translated_ids("fr") == set()


def test_append_translations_writes_and_dedups(tmp_path, monkeypatch):
    import json, translation
    monkeypatch.chdir(tmp_path)
    recs = [{"id": "a", "question": "qa", "answers": ["x"], "wrong_answers": ["y"]}]
    translation._append_translations("fr", recs)
    translation._append_translations("fr", recs + [
        {"id": "b", "question": "qb", "answers": ["1"], "wrong_answers": ["2"]}])
    data = json.loads((tmp_path / "translations" / "questions_fr.json").read_text())["data"]
    assert [r["id"] for r in data] == ["a", "b"]
    assert translation._load_translated_ids("fr") == {"a", "b"}

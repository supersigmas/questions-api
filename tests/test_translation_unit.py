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


def test_build_batch_request_lists_missing_langs():
    from translation import _build_batch_request, ANTHROPIC_TRANSLATION_MODEL
    q = {"id": "abc", "question": "Q?", "answers": ["a"], "wrong_answers": ["b"]}
    req = _build_batch_request(q, ["fr", "de"])
    assert req["custom_id"] == "abc"
    sysp = req["params"]["system"]
    assert "French (fr)" in sysp and "German (de)" in sysp
    assert req["params"]["model"] == ANTHROPIC_TRANSLATION_MODEL
    assert req["params"]["messages"][0]["content"]


def test_parse_batch_translation_tolerates_fence():
    from translation import _parse_batch_translation
    raw = '```json\n{"fr": {"question":"x","answers":["a"],"wrong_answers":["b"]}}\n```'
    parsed = _parse_batch_translation(raw)
    assert parsed["fr"]["question"] == "x"


def test_translation_record_shape():
    from translation import _translation_record
    rec = _translation_record("id1", {"question": "q", "answers": ["a"], "wrong_answers": ["b"]})
    assert rec == {"id": "id1", "question": "q", "answers": ["a"], "wrong_answers": ["b"]}


def test_batch_run_translates_missing_language(tmp_path, monkeypatch):
    import json, hashlib, translate_questions
    from unittest.mock import MagicMock
    monkeypatch.chdir(tmp_path)
    (tmp_path / "questions.json").write_text(json.dumps({"data": [
        {"question": "Q1", "answers": ["a"], "wrong_answers": ["b", "c", "d"],
         "category": "geo", "difficulty": "easy", "points": 700, "language": "en"}]}))
    qid = hashlib.md5("Q1".encode()).hexdigest()

    client = MagicMock()
    batch = MagicMock(id="batch_1", processing_status="ended")
    client.messages.batches.create.return_value = batch
    client.messages.batches.retrieve.return_value = batch
    block = MagicMock(type="text")
    block.text = json.dumps({
        "fr": {"question": "Q1-fr", "answers": ["a"], "wrong_answers": ["b", "c", "d"]},
        "de": {"question": "Q1-de", "answers": ["a"], "wrong_answers": ["b", "c", "d"]},
    })
    res = MagicMock(custom_id=qid)
    res.result.type = "succeeded"
    res.result.message.content = [block]
    client.messages.batches.results.return_value = [res]

    monkeypatch.setattr(translate_questions, "_get_anthropic_client", lambda: client)
    monkeypatch.setattr(translate_questions, "BATCH_POLL_INTERVAL", 0)

    total = translate_questions.run(language="fr")
    assert total == 1
    fr = json.loads((tmp_path / "translations" / "questions_fr.json").read_text())["data"]
    assert fr[0]["id"] == qid and fr[0]["question"] == "Q1-fr"
    assert not (tmp_path / "translations" / "questions_de.json").exists()
    orig = json.loads((tmp_path / "questions.json").read_text())["data"]
    assert orig[0]["id"] == qid  # id stamped back into originals


def test_batch_run_skips_when_all_present(tmp_path, monkeypatch):
    import json, hashlib, translate_questions
    from unittest.mock import MagicMock
    monkeypatch.chdir(tmp_path)
    qid = hashlib.md5("Q1".encode()).hexdigest()
    (tmp_path / "questions.json").write_text(json.dumps({"data": [
        {"question": "Q1", "id": qid, "answers": ["a"], "wrong_answers": ["b", "c", "d"],
         "category": "geo", "difficulty": "easy", "points": 700, "language": "en"}]}))
    (tmp_path / "translations").mkdir()
    (tmp_path / "translations" / "questions_fr.json").write_text(json.dumps({"data": [
        {"id": qid, "question": "x", "answers": ["a"], "wrong_answers": ["b", "c", "d"]}]}))
    client = MagicMock()
    monkeypatch.setattr(translate_questions, "_get_anthropic_client", lambda: client)
    assert translate_questions.run(language="fr") == 0
    client.messages.batches.create.assert_not_called()

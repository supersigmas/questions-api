import hashlib
import json
import os
from unittest.mock import MagicMock, patch


def _make_mock_response(content: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = json.dumps(content)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_system_prompt_contains_which_of_these_rule():
    from enrichment import _SYSTEM_PROMPT
    assert "which of these" in _SYSTEM_PROMPT.lower()
    assert "of the following" in _SYSTEM_PROMPT.lower()
    assert "was not" in _SYSTEM_PROMPT.lower()
    assert "negative-knowledge" in _SYSTEM_PROMPT.lower()


def test_enrich_question_passes_system_prompt_to_api():
    from enrichment import _enrich_question
    raw_q = {
        "question": "Which of these NHL teams originally played in Atlanta?",
        "correct_answer": "Calgary Flames",
        "incorrect_answers": ["Colorado Avalanche", "Carolina Hurricanes", "New Jersey Devils"],
        "category": "Sports",
        "difficulty": "easy",
        "type": "multiple",
    }
    mock_result = {
        "question": "What is the name of the NHL team that originally played in Atlanta before relocating?",
        "answers": ["calgary flames", "the flames"],
        "wrong_answers": ["Colorado Avalanche", "Carolina Hurricanes", "New Jersey Devils"],
        "category": "sports",
        "difficulty": "easy",
        "points": 700,
        "language": "en",
    }
    mock_resp = _make_mock_response(mock_result)

    with patch("enrichment._get_az_client") as mock_client_fn:
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        mock_client_fn.return_value = client

        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o"}):
            result = _enrich_question(raw_q)

    call_args = client.chat.completions.create.call_args
    _, kwargs = call_args
    messages = kwargs["messages"]
    system_msg = messages[0]
    assert system_msg["role"] == "system"
    assert "which of these" in system_msg["content"].lower()
    assert result["question"] == mock_result["question"]


def test_simplify_prompts_has_four_variants():
    from enrichment import SIMPLIFY_PROMPTS
    assert len(SIMPLIFY_PROMPTS) == 4
    for i in range(4):
        assert i in SIMPLIFY_PROMPTS
        assert isinstance(SIMPLIFY_PROMPTS[i], str)
        assert len(SIMPLIFY_PROMPTS[i]) > 50


def test_simplify_prompts_all_require_minimum_three_answers():
    from enrichment import SIMPLIFY_PROMPTS
    for i, prompt in SIMPLIFY_PROMPTS.items():
        assert "minimum 3" in prompt or "at least 3" in prompt, (
            f"Variant {i} prompt does not mention minimum 3 answer variations"
        )


def test_cosine_similarity_identical_vectors():
    from enrichment import _cosine_similarity
    v = [1.0, 0.0, 0.5]
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal_vectors():
    from enrichment import _cosine_similarity
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_similarity(a, b)) < 1e-6


def test_is_semantic_duplicate_above_threshold():
    from enrichment import _is_semantic_duplicate
    import hashlib
    store = {
        hashlib.md5(b"existing").hexdigest(): [1.0, 0.0, 0.0],
    }
    with patch.dict("os.environ", {"DEDUP_THRESHOLD": "0.92"}):
        assert _is_semantic_duplicate([0.999, 0.001, 0.0], store) is True


def test_is_semantic_duplicate_below_threshold():
    from enrichment import _is_semantic_duplicate
    import hashlib
    store = {
        hashlib.md5(b"existing").hexdigest(): [1.0, 0.0, 0.0],
    }
    with patch.dict("os.environ", {"DEDUP_THRESHOLD": "0.92"}):
        assert _is_semantic_duplicate([0.0, 1.0, 0.0], store) is False


def test_is_semantic_duplicate_empty_store():
    from enrichment import _is_semantic_duplicate
    with patch.dict("os.environ", {"DEDUP_THRESHOLD": "0.92"}):
        assert _is_semantic_duplicate([1.0, 0.0], {}) is False


def test_save_and_load_embeddings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # create a minimal questions.json
    (tmp_path / "questions.json").write_text(json.dumps({"data": []}))

    import importlib
    import enrichment
    importlib.reload(enrichment)

    store = {"abc123": [0.1, 0.2, 0.3]}
    enrichment._save_embeddings(store)

    assert (tmp_path / "embeddings.json").exists()
    loaded = json.loads((tmp_path / "embeddings.json").read_text())
    assert loaded == store


def test_load_embeddings_creates_file_if_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "questions.json").write_text(json.dumps({"data": []}))

    import importlib
    import enrichment
    importlib.reload(enrichment)

    with patch("enrichment._get_embedding", return_value=[0.1, 0.2]):
        result = enrichment._load_embeddings()

    assert isinstance(result, dict)


def test_persist_embedding_adds_to_store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "embeddings.json").write_text(json.dumps({}))

    import importlib
    import enrichment
    importlib.reload(enrichment)

    store = {}
    enrichment._persist_embedding("What is 2+2?", [0.5, 0.5], store)

    key = hashlib.md5("What is 2+2?".encode()).hexdigest()
    assert key in store
    assert store[key] == [0.5, 0.5]

    saved = json.loads((tmp_path / "embeddings.json").read_text())
    assert key in saved


def test_simplify_question_merges_fields_from_llm():
    from enrichment import _simplify_question
    enriched = {
        "question": "What is the capital of France?",
        "answers": ["paris"],
        "wrong_answers": ["London", "Berlin", "Madrid"],
        "category": "geography",
        "difficulty": "easy",
        "points": 700,
        "language": "en",
    }
    mock_result = {
        "question": "What city is the capital of France?",
        "answers": ["paris", "paris france", "the city of paris"],
        "wrong_answers": ["london", "berlin", "madrid"],
    }
    mock_resp = _make_mock_response(mock_result)

    with patch("enrichment._get_az_client") as mock_client_fn:
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        mock_client_fn.return_value = client

        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o"}):
            result = _simplify_question(enriched, variant=0)

    assert result["question"] == "What city is the capital of France?"
    assert len(result["answers"]) == 3
    assert "paris" in result["answers"]


def test_simplify_question_uses_correct_variant_prompt():
    from enrichment import _simplify_question, SIMPLIFY_PROMPTS
    enriched = {
        "question": "Test question?",
        "answers": ["answer"],
        "wrong_answers": ["wrong1", "wrong2", "wrong3"],
        "category": "general",
        "difficulty": "easy",
        "points": 700,
        "language": "en",
    }
    mock_result = {
        "question": "Test question?",
        "answers": ["answer", "the answer", "an answer"],
        "wrong_answers": ["wrong1", "wrong2", "wrong3"],
    }

    for variant in range(4):
        mock_resp = _make_mock_response(mock_result)
        with patch("enrichment._get_az_client") as mock_client_fn:
            client = MagicMock()
            client.chat.completions.create.return_value = mock_resp
            mock_client_fn.return_value = client

            with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o"}):
                _simplify_question(enriched, variant=variant)

            _, kwargs = client.chat.completions.create.call_args
            messages = kwargs["messages"]
            system_msg = messages[0]
            assert system_msg["content"] == SIMPLIFY_PROMPTS[variant], (
                f"Variant {variant} used wrong prompt"
            )


def test_process_question_full_pipeline_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "questions.json").write_text(json.dumps({"data": []}))
    (tmp_path / "embeddings.json").write_text(json.dumps({}))

    import importlib
    import enrichment
    importlib.reload(enrichment)

    raw_q = {
        "question": "What is the capital of Germany?",
        "correct_answer": "Berlin",
        "incorrect_answers": ["Munich", "Hamburg", "Frankfurt"],
        "category": "Geography",
        "difficulty": "easy",
        "type": "multiple",
    }

    pass1_result = {
        "question": "What is the capital city of Germany?",
        "answers": ["berlin"],
        "wrong_answers": ["Munich", "Hamburg", "Frankfurt"],
        "category": "geography",
        "difficulty": "easy",
        "points": 700,
        "language": "en",
    }

    pass2_result = {
        "question": "What is the capital city of Germany?",
        "answers": ["berlin", "berlin germany", "the city of berlin"],
        "wrong_answers": ["munich", "hamburg", "frankfurt"],
    }

    mock_resp1 = _make_mock_response(pass1_result)
    mock_resp2 = _make_mock_response(pass2_result)
    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        return mock_resp1 if call_count["n"] == 1 else mock_resp2

    with patch("enrichment._get_az_client") as mock_client_fn, \
         patch("enrichment._get_embedding", return_value=[0.1, 0.2, 0.3]):
        client = MagicMock()
        client.chat.completions.create.side_effect = fake_create
        mock_client_fn.return_value = client

        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o",
                                        "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT": "text-embedding-ada-002",
                                        "DEDUP_THRESHOLD": "0.92"}):
            store = {}
            result = enrichment._process_question(raw_q, set(), store, variant=0)

    assert result is True
    saved = json.loads((tmp_path / "questions.json").read_text())
    assert len(saved["data"]) == 1
    assert saved["data"][0]["answers"] == ["berlin", "berlin germany", "the city of berlin"]


def test_process_question_skips_semantic_duplicate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "questions.json").write_text(json.dumps({"data": []}))
    (tmp_path / "embeddings.json").write_text(json.dumps({}))

    import importlib
    import enrichment
    importlib.reload(enrichment)

    raw_q = {
        "question": "What is the capital of France?",
        "correct_answer": "Paris",
        "incorrect_answers": ["Lyon", "Marseille", "Nice"],
        "category": "Geography",
        "difficulty": "easy",
        "type": "multiple",
    }

    pass1_result = {
        "question": "What is the capital of France?",
        "answers": ["paris"],
        "wrong_answers": ["Lyon", "Marseille", "Nice"],
        "category": "geography",
        "difficulty": "easy",
        "points": 700,
        "language": "en",
    }
    pass2_result = {
        "question": "What is the capital of France?",
        "answers": ["paris", "paris france", "city of paris"],
        "wrong_answers": ["lyon", "marseille", "nice"],
    }

    mock_resp1 = _make_mock_response(pass1_result)
    mock_resp2 = _make_mock_response(pass2_result)
    call_count = {"n": 0}

    def fake_create(**kwargs):
        call_count["n"] += 1
        return mock_resp1 if call_count["n"] == 1 else mock_resp2

    existing_embedding = [1.0, 0.0, 0.0]
    new_embedding = [0.999, 0.001, 0.0]

    existing_store = {hashlib.md5(b"existing question").hexdigest(): existing_embedding}

    with patch("enrichment._get_az_client") as mock_client_fn, \
         patch("enrichment._get_embedding", return_value=new_embedding):
        client = MagicMock()
        client.chat.completions.create.side_effect = fake_create
        mock_client_fn.return_value = client

        with patch.dict("os.environ", {"AZURE_OPENAI_DEPLOYMENT": "gpt-4o",
                                        "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT": "text-embedding-ada-002",
                                        "DEDUP_THRESHOLD": "0.92"}):
            result = enrichment._process_question(raw_q, set(), existing_store, variant=0)

    assert result is False
    saved = json.loads((tmp_path / "questions.json").read_text())
    assert len(saved["data"]) == 0


def test_valid_languages_includes_targets():
    from enrichment import VALID_LANGUAGES, TARGET_LANGUAGES
    assert TARGET_LANGUAGES == {"de", "es", "fr", "lt", "ru", "hi"}
    assert VALID_LANGUAGES == {"en"} | TARGET_LANGUAGES


def test_source_id_is_md5_of_text():
    import hashlib
    from enrichment import _source_id
    text = "What is the largest ocean on Earth?"
    assert _source_id(text) == hashlib.md5(text.encode()).hexdigest()


def _valid_lt_question():
    return {
        "question": "Koks didziausias vandenynas Zemeje?",
        "answers": ["ramusis vandenynas", "ramusis"],
        "wrong_answers": ["Atlanto vandenynas", "Indijos vandenynas"],
        "category": "geography",
        "difficulty": "normal",
        "points": 800,
        "language": "lt",
        "source_id": "abc123",
    }


def test_validate_accepts_target_language():
    from enrichment import _validate_question
    assert _validate_question(_valid_lt_question()) is True


def test_validate_rejects_unknown_language():
    from enrichment import _validate_question
    q = _valid_lt_question()
    q["language"] = "xx"
    assert _validate_question(q) is False


def test_validate_rejects_empty_source_id_when_present():
    from enrichment import _validate_question
    q = _valid_lt_question()
    q["source_id"] = ""
    assert _validate_question(q) is False


def test_atomic_write_json_preserves_symlink_and_writes_through(tmp_path):
    """When the target path is a symlink into a shared dir, the atomic write
    must update the real file and leave the symlink intact (not clobber it
    with a regular file). This is what keeps enriched data persistent across
    releases-based deploys."""
    from enrichment import _atomic_write_json

    shared = tmp_path / "shared"
    shared.mkdir()
    real = shared / "questions.json"
    real.write_text(json.dumps({"data": ["old"]}), encoding="utf-8")

    release = tmp_path / "release"
    release.mkdir()
    link = release / "questions.json"
    link.symlink_to(real)

    _atomic_write_json({"data": ["new"]}, str(link))

    # symlink must survive
    assert os.path.islink(link), "symlink was replaced with a regular file"
    # real file in shared/ must hold the new content
    assert json.loads(real.read_text(encoding="utf-8")) == {"data": ["new"]}
    # reading through the symlink sees new content too
    assert json.loads(link.read_text(encoding="utf-8")) == {"data": ["new"]}


def test_stamp_ids_adds_md5_id_when_missing():
    import hashlib
    from enrichment import _stamp_ids
    data = [{"question": "What is 2+2?"}, {"question": "Sky?", "id": "keep"}]
    changed = _stamp_ids(data)
    assert changed is True
    assert data[0]["id"] == hashlib.md5("What is 2+2?".encode()).hexdigest()
    assert data[1]["id"] == "keep"


def test_stamp_ids_idempotent():
    from enrichment import _stamp_ids
    data = [{"question": "Q", "id": "x"}]
    assert _stamp_ids(data) is False


def test_persist_question_stamps_id(tmp_path, monkeypatch):
    import json, hashlib, enrichment
    monkeypatch.chdir(tmp_path)
    (tmp_path / "questions.json").write_text(json.dumps({"data": []}))
    monkeypatch.setattr(enrichment, "_is_unique", lambda q, existing: True)
    enrichment._persist_question({
        "question": "New Q?", "answers": ["a"], "wrong_answers": ["b", "c", "d"],
        "category": "c", "difficulty": "easy", "points": 700, "language": "en",
    })
    data = json.loads((tmp_path / "questions.json").read_text())["data"]
    assert data[0]["id"] == hashlib.md5("New Q?".encode()).hexdigest()


def test_poller_has_no_inline_translation():
    import inspect, enrichment
    assert "translate_and_persist" not in inspect.getsource(enrichment)

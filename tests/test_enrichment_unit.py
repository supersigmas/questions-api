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


def test_system_prompt_contains_which_of_these_rule():
    from enrichment import _SYSTEM_PROMPT
    assert "which of these" in _SYSTEM_PROMPT.lower()
    assert "one of the following" in _SYSTEM_PROMPT.lower()
    assert "which one of" in _SYSTEM_PROMPT.lower()


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

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
    messages = call_args.kwargs["messages"]
    system_msg = messages[0]
    assert system_msg["role"] == "system"
    assert "which of these" in system_msg["content"].lower()
    assert result["question"] == mock_result["question"]

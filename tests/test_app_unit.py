from unittest.mock import patch
import pytest


@pytest.fixture
def client():
    # Prevent the background poller (network + model load) from starting on import.
    with patch("enrichment.start_background_poller"):
        import importlib
        import app as app_module
        importlib.reload(app_module)
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client(), app_module


AUTH = {"Authorization": "Bearer my_token"}

FIXTURE = [
    {"question": "Q1", "answers": ["a"], "wrong_answers": ["b"],
     "category": "geography", "difficulty": "easy", "points": 700, "language": "en"},
    {"question": "Q1 lt", "answers": ["a"], "wrong_answers": ["b"],
     "category": "geography", "difficulty": "easy", "points": 700,
     "language": "lt", "source_id": "s1"},
    {"question": "Q2", "answers": ["c"], "wrong_answers": ["d"],
     "category": "science", "difficulty": "easy", "points": 700, "language": "en"},
]


def test_languages_returns_codes_and_counts(client):
    test_client, app_module = client
    with patch.object(app_module, "_load_questions", return_value=FIXTURE):
        resp = test_client.get("/languages", headers=AUTH)
    assert resp.status_code == 200
    langs = {l["code"]: l["count"] for l in resp.get_json()["languages"]}
    assert langs == {"en": 2, "lt": 1}


def test_languages_requires_auth(client):
    test_client, _ = client
    resp = test_client.get("/languages")
    assert resp.status_code == 401


MIXED = [
    {"question": "en-geo", "answers": ["a"], "wrong_answers": ["b"],
     "category": "geography", "difficulty": "easy", "points": 700, "language": "en"},
    {"question": "lt-geo", "answers": ["a"], "wrong_answers": ["b"],
     "category": "geography", "difficulty": "easy", "points": 700,
     "language": "lt", "source_id": "s1"},
]


def test_questions_defaults_to_english(client):
    test_client, app_module = client
    with patch.object(app_module, "_load_questions", return_value=MIXED):
        resp = test_client.get("/questions?count=10", headers=AUTH)
    qs = resp.get_json()["questions"]
    assert qs and all(q["language"] == "en" for q in qs)


def test_questions_filters_by_language(client):
    test_client, app_module = client
    with patch.object(app_module, "_load_questions", return_value=MIXED):
        resp = test_client.get("/questions?language=lt&count=10", headers=AUTH)
    qs = resp.get_json()["questions"]
    assert qs and all(q["language"] == "lt" for q in qs)

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
    en_qs = [q for q in FIXTURE if q["language"] == "en"]
    lt_qs = [q for q in FIXTURE if q["language"] == "lt"]

    def fake_load(lang="en"):
        if lang == "en":
            return en_qs
        if lang == "lt":
            return lt_qs
        return []

    with patch.object(app_module, "_load_originals", return_value=en_qs), \
         patch.object(app_module, "_load_questions", side_effect=fake_load):
        resp = test_client.get("/languages", headers=AUTH)
    assert resp.status_code == 200
    langs = {l["code"]: l["count"] for l in resp.get_json()["languages"]}
    assert langs["en"] == 2 and langs["lt"] == 1


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
    en_only = [q for q in MIXED if q["language"] == "en"]
    with patch.object(app_module, "_load_questions", return_value=en_only):
        resp = test_client.get("/questions?count=10", headers=AUTH)
    qs = resp.get_json()["questions"]
    assert qs and all(q["language"] == "en" for q in qs)


def test_questions_filters_by_language(client):
    test_client, app_module = client
    lt_only = [q for q in MIXED if q["language"] == "lt"]
    with patch.object(app_module, "_load_questions", return_value=lt_only):
        resp = test_client.get("/questions?language=lt&count=10", headers=AUTH)
    qs = resp.get_json()["questions"]
    assert qs and all(q["language"] == "lt" for q in qs)


def _seed(tmp_path):
    import json
    (tmp_path / "questions.json").write_text(json.dumps({"data": [
        {"id": "1", "question": "Q", "answers": ["a"], "wrong_answers": ["b"],
         "category": "geo", "difficulty": "easy", "points": 700, "language": "en"}]}))


def test_load_questions_en_returns_originals(tmp_path, monkeypatch):
    import app
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    assert app._load_questions("en")[0]["question"] == "Q"


def test_load_questions_merges_translation_metadata(tmp_path, monkeypatch):
    import json, app
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    (tmp_path / "translations").mkdir()
    (tmp_path / "translations" / "questions_fr.json").write_text(json.dumps({"data": [
        {"id": "1", "question": "Q-fr", "answers": ["a-fr"], "wrong_answers": ["b-fr"]}]}))
    fr = app._load_questions("fr")
    assert len(fr) == 1
    assert fr[0]["question"] == "Q-fr"
    assert fr[0]["category"] == "geo" and fr[0]["points"] == 700
    assert fr[0]["language"] == "fr"


def test_load_questions_skips_unknown_ids(tmp_path, monkeypatch):
    import json, app
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    (tmp_path / "translations").mkdir()
    (tmp_path / "translations" / "questions_fr.json").write_text(json.dumps({"data": [
        {"id": "999", "question": "orphan", "answers": ["a"], "wrong_answers": ["b"]}]}))
    assert app._load_questions("fr") == []


def test_load_questions_missing_file_returns_empty(tmp_path, monkeypatch):
    import json, app
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    assert app._load_questions("de") == []

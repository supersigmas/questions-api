"""Flask app module """
import json
import logging
import os
import random
from flask import Flask, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from enrichment import start_background_poller, TARGET_LANGUAGES


def _setup_logging() -> None:
    log_file = os.environ.get("LOG_FILE", "logs/app.log")
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(stream_handler)
    root.addHandler(file_handler)


_setup_logging()
logger = logging.getLogger(__name__)


TRANSLATIONS_DIR = "translations"


def _lang_file(lang: str) -> str:
    return os.path.join(TRANSLATIONS_DIR, f"questions_{lang}.json")


def _load_originals() -> list:
    with open("questions.json", "r", encoding="utf-8") as f:
        return json.load(f)["data"]


def _load_questions(language: str = "en") -> list:
    originals = _load_originals()
    if language == "en":
        return originals
    path = _lang_file(language)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        translated = json.load(f)["data"]
    by_id = {q["id"]: q for q in originals if q.get("id")}
    merged = []
    for t in translated:
        base = by_id.get(t["id"])
        if not base:
            continue
        merged.append({
            "id": t["id"],
            "question": t["question"],
            "answers": t["answers"],
            "wrong_answers": t["wrong_answers"],
            "category": base["category"],
            "difficulty": base["difficulty"],
            "points": base["points"],
            "language": language,
        })
    return merged


def collect_categories(data) -> list:
    """
    Collect all categories from the data
    :param data: JSON data
    :return: List of categories
    """
    categories = []
    for item in data:
        category = item["category"]
        if category not in categories:
            categories.append(category)
    return categories


def get_questions_count(
        data,
        category: str = None,
        count: int = 10,
        difficulty: str = "easy"
) -> list:
    """
    Get 20 questions from the specified category
    :param data: JSON data
    :param count: Number of questions to return
    :param category: Category
    :param difficulty: Difficulty level of the questions
    :return: List of questions
    """
    questions = []

    # reorder data in random order
    data = random.sample(data, len(data))

    for item in data:
        if difficulty == 'easy' and item["difficulty"] != "easy":
            continue
        if not category or item["category"] == category:
            questions.append(item)
        if len(questions) == count:
            break

    random.shuffle(questions)
    return questions


def validate_bearer_token(headers) -> bool:
    """
    Validate the bearer token
    :param headers: Request headers
    :return: True if the token is valid, False otherwise
    """
    if "Authorization" not in headers:
        return False

    token = headers["Authorization"]
    if (
        token
        != "Bearer my_token"
    ):
        return False

    return True


app = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False,
    allow_headers=["Authorization", "Content-Type"],
    methods=["GET", "OPTIONS"],
    max_age=3600,
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per minute"],
    storage_uri="memory://",
)

start_background_poller()


@app.after_request
def log_request(response):
    qs = request.query_string.decode()
    logger.info("REQUEST %s %s%s → %d", request.method, request.path, f"?{qs}" if qs else "", response.status_code)
    return response


@app.route("/categories", methods=["GET"])
@limiter.limit("10 per minute")
def get_category():
    if not validate_bearer_token(request.headers):
        return {"error": "Invalid bearer token"}, 401

    data = _load_questions()
    categories = collect_categories(data)
    random.shuffle(categories)
    categories = categories[:4]

    return {"categories": categories}, 200


@app.route("/questions", methods=["GET"])
@limiter.limit("10 per minute")
def get_questions():
    if not validate_bearer_token(request.headers):
        return {"error": "Invalid bearer token"}, 401

    category = request.args.get("category")
    questions_count = request.args.get("count", default=20, type=int)
    difficulty = request.args.get("difficulty", default="easy", type=str)
    language = request.args.get("language", default="en", type=str)

    data = _load_questions(language)

    if category:
        questions = get_questions_count(data, category, questions_count, difficulty)
    else:
        questions = get_questions_count(data=data, difficulty=difficulty, count=questions_count)
    return {"questions": questions}, 200


@app.route("/languages", methods=["GET"])
@limiter.limit("10 per minute")
def get_languages():
    if not validate_bearer_token(request.headers):
        return {"error": "Invalid bearer token"}, 401

    counts = {"en": len(_load_originals())}
    for lang in sorted(TARGET_LANGUAGES):
        merged = _load_questions(lang)
        if merged:
            counts[lang] = len(merged)

    languages = [{"code": c, "count": n} for c, n in sorted(counts.items())]
    return {"languages": languages}, 200


if __name__ == "__main__":
    """
    Run the app
    """

    # app.run()
    app.run(host="0.0.0.0", port=5000, debug=True)

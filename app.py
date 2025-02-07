"""Flask app module """
import json
import random
from flask import Flask, request


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


def get_20_questions(data, category: str = None) -> list:
    """
    Get 20 questions from the specified category
    :param data: JSON data
    :param category: Category
    :return: List of questions
    """
    questions = []
    for item in data:
        if category:
            if item["category"] == category:
                questions.append(item)
        else:
            questions.append(item)
        if len(questions) == 20:
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


@app.route("/categories", methods=["GET"])
def get_category():
    """
    Get all categories
    :return: list of categories
    """

    # Validate bearer token
    if not validate_bearer_token(request.headers):
        return {"error": "Invalid bearer token"}, 401

    f = open("questions.json", "r")
    data = json.load(f)

    data = data["data"]
    categories = collect_categories(data)
    return {"categories": categories}, 200


@app.route("/questions", methods=["GET"])
def get_questions():
    """
    Get 20 questions
    :return: list of questions
    """

    # Validate bearer token
    if not validate_bearer_token(request.headers):
        return {"error": "Invalid bearer token"}, 401

    # get categories from request
    category = request.args.get("category")

    f = open("questions.json", "r")
    data = json.load(f)

    data = data["data"]
    if category:
        questions = get_20_questions(data, category)
    else:
        questions = get_20_questions(data)
    return {"questions": questions}, 200


if __name__ == "__main__":
    """
    Run the app
    """

    # app.run()
    app.run(host="0.0.0.0", port=5000, debug=True)

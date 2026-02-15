import requests
import html

def generate_quiz(category: str, num_questions: int):
    """
    Generate a quiz using Open Trivia Database (no API key required).
    """
    url = "https://opentdb.com/api.php"
    params = {
        "amount": num_questions,
        "type": "multiple"
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    quiz = []

    for item in data.get("results", []):
        options = item["incorrect_answers"] + [item["correct_answer"]]
        quiz.append({
            "question": html.unescape(item["question"]),
            "options": [html.unescape(opt) for opt in options]
        })

    return {
        "category": category,
        "num_questions": len(quiz),
        "quiz": quiz
    }

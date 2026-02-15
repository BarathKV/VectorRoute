import requests

def get_latest_headlines(category: str):
    """
    Get latest news headlines by category using GNews public API.
    """
    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "topic": category,
        "lang": "en",
        "max": 5,
        "token": "demo"
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    headlines = []
    for article in data.get("articles", []):
        headlines.append({
            "title": article.get("title"),
            "source": article.get("source", {}).get("name"),
            "published_at": article.get("publishedAt")
        })

    return {
        "category": category,
        "headlines": headlines
    }

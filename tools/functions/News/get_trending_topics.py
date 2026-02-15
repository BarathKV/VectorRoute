import requests
from collections import Counter

def get_trending_topics():
    """
    Get trending news topics based on keyword frequency
    from recent headlines using GNews.
    """
    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "lang": "en",
        "max": 10,
        "token": "demo"
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    words = []

    for article in data.get("articles", []):
        title = article.get("title", "")
        for word in title.split():
            word = word.lower().strip(".,!?")
            if len(word) > 4:
                words.append(word)

    common = Counter(words).most_common(5)

    return {
        "trending_topics": [
            {"topic": word, "count": count}
            for word, count in common
        ]
    }

import requests

def summarize_news_by_keyword(keyword: str):
    """
    Fetch recent news articles by keyword and return a short summary.
    """
    url = "https://gnews.io/api/v4/search"
    params = {
        "q": keyword,
        "lang": "en",
        "max": 5,
        "token": "demo"
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    summaries = []

    for article in data.get("articles", []):
        description = article.get("description") or ""
        summaries.append({
            "title": article.get("title"),
            "summary": description[:200]  # lightweight deterministic summary
        })

    return {
        "keyword": keyword,
        "articles": summaries
    }

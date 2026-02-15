import requests

def get_stock_price(symbol: str):
    """
    Get the latest stock price for a symbol using Stooq (no API key required).
    """
    symbol = symbol.lower() + ".us"
    url = "https://stooq.com/q/l/"

    params = {
        "s": symbol,
        "f": "sd2t2ohlcv",
        "h": "",
        "e": "json"
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    if "data" not in data or not data["data"]:
        return None

    stock = data["data"][0]
    return {
        "symbol": stock.get("symbol"),
        "date": stock.get("date"),
        "open": stock.get("open"),
        "high": stock.get("high"),
        "low": stock.get("low"),
        "close": stock.get("close"),
        "volume": stock.get("volume")
    }

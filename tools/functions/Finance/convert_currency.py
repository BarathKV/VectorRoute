import requests

def convert_currency(from_currency: str, to_currency: str, amount: float):
    """
    Convert an amount from one currency to another using exchangerate.host.
    """
    url = "https://api.exchangerate.host/convert"
    params = {
        "from": from_currency,
        "to": to_currency,
        "amount": amount
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    return {
        "from": from_currency,
        "to": to_currency,
        "amount": amount,
        "converted_amount": data.get("result"),
        "rate": data.get("info", {}).get("rate")
    }

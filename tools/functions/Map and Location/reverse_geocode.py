import requests

def reverse_geocode(latitude: float, longitude: float):
    """
    Convert latitude and longitude into a human-readable address
    using Nominatim (OpenStreetMap).
    """
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "json"
    }
    headers = {
        "User-Agent": "agentic-tool-demo"
    }

    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    return {
        "latitude": latitude,
        "longitude": longitude,
        "address": data.get("display_name"),
        "details": data.get("address", {})
    }

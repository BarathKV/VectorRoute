import requests
import math

def _geocode_city(city: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": city,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "agentic-tool-demo"
    }

    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    if not data:
        return None

    return float(data[0]["lat"]), float(data[0]["lon"])


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2

    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_distance_between_cities(city_from: str, city_to: str):
    """
    Calculate distance between two cities in kilometers.
    """
    loc1 = _geocode_city(city_from)
    loc2 = _geocode_city(city_to)

    if not loc1 or not loc2:
        return {"error": "Unable to geocode one or both cities"}

    distance_km = _haversine(loc1[0], loc1[1], loc2[0], loc2[1])

    return {
        "from_city": city_from,
        "to_city": city_to,
        "distance_km": round(distance_km, 2)
    }

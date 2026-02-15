import requests

def get_route_distance(
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float
):
    """
    Calculate road route distance between two coordinates using OSRM.
    """
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{start_longitude},{start_latitude};{end_longitude},{end_latitude}"
    )

    params = {
        "overview": "false"
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    routes = data.get("routes")
    if not routes:
        return {"error": "No route found"}

    distance_meters = routes[0]["distance"]
    distance_km = distance_meters / 1000

    return {
        "start": {
            "latitude": start_latitude,
            "longitude": start_longitude
        },
        "end": {
            "latitude": end_latitude,
            "longitude": end_longitude
        },
        "distance_km": round(distance_km, 2)
    }

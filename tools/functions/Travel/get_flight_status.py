import requests

def get_flight_status(callsign: str):
    """
    Get live flight status using OpenSky Network (no API key required).
    Callsign example: AAL123, IAE456
    """
    url = "https://opensky-network.org/api/states/all"
    params = {
        "callsign": callsign.upper()
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    states = data.get("states")
    if not states:
        return {"callsign": callsign, "status": "No active flight found"}

    flight = states[0]

    return {
        "callsign": flight[1].strip(),
        "origin_country": flight[2],
        "longitude": flight[5],
        "latitude": flight[6],
        "altitude_m": flight[7],
        "velocity_mps": flight[9],
        "on_ground": flight[8]
    }

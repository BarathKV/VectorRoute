import requests

def get_current_weather(city: str):
    """
    Get current weather for a given city using wttr.in (no API key required).
    """
    url = f"https://wttr.in/{city}?format=j1"
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    data = response.json()
    current = data["current_condition"][0]

    return {
        "city": city,
        "temperature_c": current["temp_C"],
        "feels_like_c": current["FeelsLikeC"],
        "humidity": current["humidity"],
        "weather_description": current["weatherDesc"][0]["value"],
        "wind_kph": current["windspeedKmph"]
    }
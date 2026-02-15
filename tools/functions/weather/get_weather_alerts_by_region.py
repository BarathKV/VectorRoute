import requests

def get_weather_alerts_by_region(region: str):
    """
    Get active weather alerts for a region using wttr.in (no API key required).
    """
    url = f"https://wttr.in/{region}?format=j1"
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    data = response.json()

    alerts = data.get("weatherAlerts", [])

    formatted_alerts = []
    for alert in alerts:
        formatted_alerts.append({
            "title": alert.get("headline"),
            "description": alert.get("desc"),
            "severity": alert.get("severity"),
            "effective": alert.get("effective"),
            "expires": alert.get("expires")
        })

    return {
        "region": region,
        "alerts": formatted_alerts
    }

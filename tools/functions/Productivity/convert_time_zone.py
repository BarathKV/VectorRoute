import requests
from datetime import datetime
from dateutil import parser

def convert_time_zone(time_str: str, from_timezone: str, to_timezone: str):
    """
    Convert time from one timezone to another using WorldTimeAPI.
    time_str format: YYYY-MM-DD HH:MM
    """
    from_url = f"https://worldtimeapi.org/api/timezone/{from_timezone}"
    to_url = f"https://worldtimeapi.org/api/timezone/{to_timezone}"

    from_resp = requests.get(from_url, timeout=10)
    from_resp.raise_for_status()
    from_data = from_resp.json()

    to_resp = requests.get(to_url, timeout=10)
    to_resp.raise_for_status()
    to_data = to_resp.json()

    base_time = parser.parse(time_str)
    from_offset = from_data["utc_offset"]
    to_offset = to_data["utc_offset"]

    def offset_to_minutes(offset):
        sign = 1 if offset[0] == "+" else -1
        hours = int(offset[1:3])
        minutes = int(offset[4:6])
        return sign * (hours * 60 + minutes)

    delta_minutes = offset_to_minutes(to_offset) - offset_to_minutes(from_offset)
    converted_time = base_time + timedelta(minutes=delta_minutes)

    return {
        "original_time": time_str,
        "from_timezone": from_timezone,
        "to_timezone": to_timezone,
        "converted_time": converted_time.strftime("%Y-%m-%d %H:%M")
    }

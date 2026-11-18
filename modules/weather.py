"""
Live farm weather from Open-Meteo (https://open-meteo.com): free, no API key.

fetch_farm_weather() returns current conditions, the next 24 hours and a
7-day outlook for the farm coordinates, or None when the service cannot be
reached. Callers must show an unavailable state rather than placeholder data.
"""
from typing import Any, Dict, Optional

import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes -> (label, icon name in modules/ui.ICON_PATHS)
WMO_CODES = {
    0: ("Clear", "sun"),
    1: ("Mostly clear", "sun"),
    2: ("Partly cloudy", "cloud-sun"),
    3: ("Overcast", "cloud"),
    45: ("Fog", "cloud-fog"),
    48: ("Rime fog", "cloud-fog"),
    51: ("Light drizzle", "cloud-drizzle"),
    53: ("Drizzle", "cloud-drizzle"),
    55: ("Heavy drizzle", "cloud-drizzle"),
    56: ("Freezing drizzle", "cloud-drizzle"),
    57: ("Freezing drizzle", "cloud-drizzle"),
    61: ("Light rain", "cloud-rain"),
    63: ("Rain", "cloud-rain"),
    65: ("Heavy rain", "cloud-rain"),
    66: ("Freezing rain", "cloud-rain"),
    67: ("Freezing rain", "cloud-rain"),
    71: ("Light snow", "cloud"),
    73: ("Snow", "cloud"),
    75: ("Heavy snow", "cloud"),
    77: ("Snow grains", "cloud"),
    80: ("Light showers", "cloud-rain"),
    81: ("Showers", "cloud-rain"),
    82: ("Violent showers", "cloud-rain"),
    85: ("Snow showers", "cloud"),
    86: ("Snow showers", "cloud"),
    95: ("Thunderstorm", "cloud-lightning"),
    96: ("Thunderstorm, hail", "cloud-lightning"),
    99: ("Thunderstorm, hail", "cloud-lightning"),
}


def describe_weather_code(code: Optional[int]):
    return WMO_CODES.get(int(code) if code is not None else -1, ("Unknown", "cloud"))


def fetch_farm_weather(latitude: float, longitude: float, timeout: float = 6.0) -> Optional[Dict[str, Any]]:
    """Current conditions, next 24 hours and 7-day outlook, or None on failure."""
    params = {
        "latitude": round(float(latitude), 4),
        "longitude": round(float(longitude), 4),
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,precipitation_probability,relative_humidity_2m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 7,
    }
    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    current = data.get("current") or {}
    hourly = data.get("hourly") or {}
    daily = data.get("daily") or {}
    if not current or not daily.get("time"):
        return None

    # Next 24 hours from the current hour onwards
    now_key = (current.get("time") or "")[:13]
    times = hourly.get("time") or []
    start = next((i for i, t in enumerate(times) if t[:13] >= now_key), 0)
    end = start + 24

    label, icon_name = describe_weather_code(current.get("weather_code"))
    days = []
    for i, day in enumerate(daily["time"]):
        d_label, d_icon = describe_weather_code(daily["weather_code"][i])
        days.append({
            "date": day,
            "label": d_label,
            "icon": d_icon,
            "t_max": daily["temperature_2m_max"][i],
            "t_min": daily["temperature_2m_min"][i],
            "rain_mm": daily["precipitation_sum"][i],
            "rain_prob": daily["precipitation_probability_max"][i],
        })

    return {
        "timezone": data.get("timezone"),
        "current": {
            "time": current.get("time"),
            "temperature": current.get("temperature_2m"),
            "feels_like": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            "wind_speed": current.get("wind_speed_10m"),
            "label": label,
            "icon": icon_name,
        },
        "hourly": {
            "time": times[start:end],
            "temperature": (hourly.get("temperature_2m") or [])[start:end],
            "rain_prob": (hourly.get("precipitation_probability") or [])[start:end],
            "humidity": (hourly.get("relative_humidity_2m") or [])[start:end],
        },
        "daily": days,
    }

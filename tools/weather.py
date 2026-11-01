"""Weather via Open-Meteo (free, no API key).

* Trip within the next ~15 days  -> real forecast
* Further in the future / the past -> same dates in a previous year (typical climate)
"""
from datetime import date, timedelta

import requests

from config import FORECAST_HORIZON_DAYS

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY = "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"


def weather_label(code) -> str:
    code = int(code or 0)
    if code == 0:
        return "☀️ Clear"
    if code in (1, 2):
        return "🌤️ Mostly clear"
    if code == 3:
        return "☁️ Cloudy"
    if code in (45, 48):
        return "🌫️ Fog"
    if 51 <= code <= 57:
        return "🌦️ Drizzle"
    if 61 <= code <= 67:
        return "🌧️ Rain"
    if 71 <= code <= 77:
        return "❄️ Snow"
    if 80 <= code <= 82:
        return "🌧️ Showers"
    if code in (85, 86):
        return "❄️ Snow showers"
    if code >= 95:
        return "⛈️ Thunderstorm"
    return "🌡️ Mixed"


def geocode(city: str) -> dict:
    r = requests.get(GEO_URL, params={"name": city, "count": 1, "language": "en"}, timeout=15)
    r.raise_for_status()
    results = r.json().get("results")
    if not results:
        raise ValueError(f"Could not find location '{city}'")
    g = results[0]
    return {
        "name": g["name"],
        "country": g.get("country", ""),
        "lat": g["latitude"],
        "lon": g["longitude"],
    }


def _shift_year(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - years, day=28)


def get_weather(city: str, start: date, end: date) -> dict:
    loc = geocode(city)
    today = date.today()
    horizon = today + timedelta(days=FORECAST_HORIZON_DAYS)

    if start >= today and end <= horizon:
        mode, url = "forecast", FORECAST_URL
        q_start, q_end, shift = start, end, 0
    else:
        mode, url = "historical", ARCHIVE_URL
        shift = 1
        while _shift_year(end, shift) > today - timedelta(days=7):
            shift += 1
        q_start, q_end = _shift_year(start, shift), _shift_year(end, shift)

    r = requests.get(
        url,
        params={
            "latitude": loc["lat"],
            "longitude": loc["lon"],
            "daily": DAILY,
            "start_date": q_start.isoformat(),
            "end_date": q_end.isoformat(),
            "timezone": "auto",
        },
        timeout=20,
    )
    r.raise_for_status()
    d = r.json()["daily"]

    days = []
    for i, day_str in enumerate(d["time"]):
        actual = date.fromisoformat(day_str)
        trip_date = _shift_year(actual, -shift) if shift else actual
        days.append(
            {
                "date": trip_date.isoformat(),
                "max_c": d["temperature_2m_max"][i],
                "min_c": d["temperature_2m_min"][i],
                "rain_mm": d["precipitation_sum"][i] or 0,
                "condition": weather_label(d["weathercode"][i]),
            }
        )

    maxes = [x["max_c"] for x in days if x["max_c"] is not None]
    mins = [x["min_c"] for x in days if x["min_c"] is not None]
    return {
        "location": f'{loc["name"]}, {loc["country"]}',
        "mode": mode,
        "reference_year": q_start.year if mode == "historical" else None,
        "days": days,
        "avg_max_c": round(sum(maxes) / len(maxes), 1) if maxes else None,
        "avg_min_c": round(sum(mins) / len(mins), 1) if mins else None,
        "total_rain_mm": round(sum(x["rain_mm"] for x in days), 1),
        "rainy_days": sum(1 for x in days if x["rain_mm"] >= 1),
    }

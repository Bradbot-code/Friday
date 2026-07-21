from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class WeatherTools:
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, location_path: Path = Path("data/weather_location.json")) -> None:
        self.location_path = location_path

    def get_saved_location(self) -> dict[str, Any] | None:
        if not self.location_path.exists():
            return None
        try:
            return json.loads(self.location_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def search_locations(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        clean = query.strip()
        if len(clean) < 2:
            raise ValueError("Enter a city, postal code, or location name.")
        data = self._request_json(
            self.GEOCODING_URL,
            {"name": clean, "count": max(1, min(int(max_results), 10)), "language": "en", "format": "json"},
        )
        return [self._location(item) for item in data.get("results", [])]

    def save_location(self, query: str) -> dict[str, Any]:
        matches = self.search_locations(query, max_results=1)
        if not matches and "," in query:
            matches = self.search_locations(query.split(",", 1)[0], max_results=1)
        if not matches:
            raise ValueError(f"No weather location matched: {query}")
        location = matches[0]
        self.location_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.location_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(location, indent=2), encoding="utf-8")
        temporary.replace(self.location_path)
        return location

    def get_forecast(self, days: int = 3) -> dict[str, Any]:
        location = self._require_location()
        forecast_days = max(1, min(int(days), 16))
        data = self._request_json(
            self.FORECAST_URL,
            {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "timezone": "auto",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "forecast_days": forecast_days,
                "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_gusts_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max,sunrise,sunset",
            },
        )
        current = data.get("current", {})
        current["condition"] = self._condition(current.get("weather_code"))
        daily = data.get("daily", {})
        days_output = []
        for index, day in enumerate(daily.get("time", [])):
            days_output.append({
                "date": day,
                "condition": self._condition(self._at(daily, "weather_code", index)),
                "high_f": self._at(daily, "temperature_2m_max", index),
                "low_f": self._at(daily, "temperature_2m_min", index),
                "precipitation_chance_percent": self._at(daily, "precipitation_probability_max", index),
                "precipitation_inches": self._at(daily, "precipitation_sum", index),
                "max_wind_mph": self._at(daily, "wind_speed_10m_max", index),
                "max_gust_mph": self._at(daily, "wind_gusts_10m_max", index),
                "sunrise": self._at(daily, "sunrise", index),
                "sunset": self._at(daily, "sunset", index),
            })
        return {"location": location, "current": current, "daily": days_output, "timezone": data.get("timezone", location.get("timezone", ""))}

    def get_hourly_forecast(self, hours: int = 12) -> dict[str, Any]:
        location = self._require_location()
        data = self._request_json(self.FORECAST_URL, {
            "latitude": location["latitude"], "longitude": location["longitude"],
            "timezone": "auto", "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
            "forecast_hours": max(1, min(int(hours), 48)),
            "hourly": "temperature_2m,apparent_temperature,precipitation_probability,weather_code,wind_speed_10m,wind_gusts_10m",
        })
        hourly = data.get("hourly", {})
        output = []
        for index, stamp in enumerate(hourly.get("time", [])):
            output.append({"time": stamp, "condition": self._condition(self._at(hourly, "weather_code", index)), "temperature_f": self._at(hourly, "temperature_2m", index), "feels_like_f": self._at(hourly, "apparent_temperature", index), "precipitation_chance_percent": self._at(hourly, "precipitation_probability", index), "wind_mph": self._at(hourly, "wind_speed_10m", index), "gust_mph": self._at(hourly, "wind_gusts_10m", index)})
        return {"location": location, "hourly": output}

    def _require_location(self) -> dict[str, Any]:
        location = self.get_saved_location()
        if not location:
            raise RuntimeError("No weather location is saved. Add one in Settings.")
        return location

    @staticmethod
    def _request_json(url: str, parameters: dict[str, Any]) -> dict[str, Any]:
        request = Request(f"{url}?{urlencode(parameters)}", headers={"User-Agent": "Friday-Assistant/1.0"})
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Weather service unavailable: {exc}") from exc

    @staticmethod
    def _location(item: dict[str, Any]) -> dict[str, Any]:
        parts = [item.get("name", ""), item.get("admin1", ""), item.get("country", "")]
        return {"display_name": ", ".join(dict.fromkeys(part for part in parts if part)), "latitude": item["latitude"], "longitude": item["longitude"], "timezone": item.get("timezone", "auto")}

    @staticmethod
    def _at(data: dict[str, Any], key: str, index: int):
        values = data.get(key, [])
        return values[index] if index < len(values) else None

    @staticmethod
    def _condition(code: Any) -> str:
        descriptions = {0:"Clear",1:"Mostly clear",2:"Partly cloudy",3:"Overcast",45:"Fog",48:"Freezing fog",51:"Light drizzle",53:"Drizzle",55:"Heavy drizzle",61:"Light rain",63:"Rain",65:"Heavy rain",66:"Freezing rain",67:"Heavy freezing rain",71:"Light snow",73:"Snow",75:"Heavy snow",77:"Snow grains",80:"Light showers",81:"Showers",82:"Heavy showers",85:"Snow showers",86:"Heavy snow showers",95:"Thunderstorms",96:"Thunderstorms with hail",99:"Severe thunderstorms with hail"}
        return descriptions.get(code, "Unknown")

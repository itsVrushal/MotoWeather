"""
Weather service — Open-Meteo API.

Fetches hourly weather data for a list of (lat, lon, eta) waypoints.
All requests are made concurrently using httpx.AsyncClient + asyncio.gather.

Variables fetched per waypoint:
  - precipitation_probability  (0–100 %)
  - windspeed_10m              (km/h)
  - temperature_2m             (°C)
  - weathercode                (WMO code)

Timezone is fixed to Asia/Kolkata (IST) for ETA hour matching.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import datetime

import httpx
from dotenv import load_dotenv

from utils.logger import setup_logger

load_dotenv()

logger = setup_logger("weather")

OPEN_METEO_BASE_URL = os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1")
_TIMEZONE = "Asia/Kolkata"
_HOURLY_VARS = "precipitation_probability,windspeed_10m,temperature_2m,weathercode"

# Simple in-memory cache to prevent re-fetching the same waypoints during the sliding window optimizer loop
_BATCH_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class WaypointWeather:
    precip_pct: float
    wind_kmh: float
    temp_c: float
    weathercode: int


# ---------------------------------------------------------------------------
# Batch fetch (single request)
# ---------------------------------------------------------------------------

async def fetch_weather_batch(
    waypoints: list[tuple[float, float]],  # [(lat, lon), ...]
    etas: list[datetime],
) -> list[WaypointWeather]:
    """
    Fetch weather for all waypoints in a SINGLE API request using Open-Meteo's array feature.
    Results are cached for 5 minutes so the optimizer sliding window doesn't spam the API.
    """
    if not waypoints:
        return []

    lats = ",".join(str(round(lat, 5)) for lat, lon in waypoints)
    lons = ",".join(str(round(lon, 5)) for lat, lon in waypoints)
    
    cache_key = f"{lats}|{lons}"
    now = time.time()

    # Check cache first
    if cache_key in _BATCH_CACHE and (now - _BATCH_CACHE[cache_key][0] < _CACHE_TTL):
        logger.debug(f"Weather cache hit for {len(waypoints)} waypoints.")
        data_list = _BATCH_CACHE[cache_key][1]
    else:
        logger.debug(f"Weather cache miss. Fetching from Open-Meteo for {len(waypoints)} waypoints.")
        # Fetch from API
        async with httpx.AsyncClient() as client:
            params = {
                "latitude": lats,
                "longitude": lons,
                "hourly": _HOURLY_VARS,
                "timezone": _TIMEZONE,
                "forecast_days": 3,
            }
            try:
                response = await client.get(
                    f"{OPEN_METEO_BASE_URL}/forecast",
                    params=params,
                    timeout=15.0,
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                logger.error(f"Open-Meteo API error: {e}")
                raise
            data = response.json()
            
            # Open-Meteo returns a list if >1 coordinate, but a dict if exactly 1 coordinate
            if isinstance(data, dict):
                data_list = [data]
            else:
                data_list = data
                
            _BATCH_CACHE[cache_key] = (now, data_list)

    # Extract the specific ETA hours for each waypoint
    results = []
    for location_data, eta in zip(data_list, etas):
        hourly = location_data["hourly"]
        results.append(_extract_hourly(hourly, eta))

    return results


def _extract_hourly(hourly: dict, eta: datetime) -> WaypointWeather:
    time_strings: list[str] = hourly["time"]
    eta_hour_str = eta.strftime("%Y-%m-%dT%H:00")

    if eta_hour_str in time_strings:
        idx = time_strings.index(eta_hour_str)
    else:
        idx = min(len(time_strings) - 1, max(0, _find_nearest_hour_idx(time_strings, eta)))

    return WaypointWeather(
        precip_pct=float(hourly["precipitation_probability"][idx] or 0),
        wind_kmh=float(hourly["windspeed_10m"][idx] or 0),
        temp_c=float(hourly["temperature_2m"][idx] or 20),
        weathercode=int(hourly["weathercode"][idx] or 0),
    )


def _find_nearest_hour_idx(time_strings: list[str], eta: datetime) -> int:
    """Find the index of the time string closest to the given datetime."""
    target = eta.replace(minute=0, second=0, microsecond=0)
    target_str = target.strftime("%Y-%m-%dT%H:00")
    for i, ts in enumerate(time_strings):
        if ts >= target_str:
            return i
    return len(time_strings) - 1

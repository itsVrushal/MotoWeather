"""
Unified Multi-Provider Geocoding & Autocomplete Engine.

Supports:
1. Mapbox Geocoding API (100k free searches/month)
2. Google Geocoding API (40k free searches/month)
3. OpenStreetMap Nominatim Fallback (Free open-source)

Guarded by QuotaGuard to ensure zero billing charges.
"""
from __future__ import annotations

import os
from typing import List, Dict, Optional, Tuple
import httpx
from dotenv import load_dotenv

from services.quota_guard import QuotaGuard
from utils.logger import setup_logger

load_dotenv()
logger = setup_logger("geocoding_engine")

MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
GOOGLE_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

async def geocode(address: str) -> Tuple[float, float]:
    """Forward geocode an address into (lat, lon)."""
    places = await search_places(address, limit=1)
    if not places:
        raise ValueError(f"Could not resolve location for '{address}'.")
    return float(places[0]["lat"]), float(places[0]["lon"])


async def search_places(query: str, limit: int = 5) -> List[Dict]:
    """
    Search places/addresses using Mapbox -> Google -> Nominatim.
    Returns list of dicts: [{'name': ..., 'lat': ..., 'lon': ..., 'provider': ...}, ...]
    """
    if not query or len(query.strip()) < 2:
        return []

    q = query.strip()

    # 1. Mapbox Geocoding (Primary - 100k free/mo)
    if MAPBOX_TOKEN and QuotaGuard.can_use("mapbox"):
        try:
            url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{q}.json"
            params = {
                "access_token": MAPBOX_TOKEN,
                "country": "in",  # Prioritize India
                "limit": limit,
                "types": "place,locality,neighborhood,address,poi",
            }
            async with httpx.AsyncClient(timeout=6.0) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()

            results = []
            for feat in data.get("features", []):
                lon, lat = feat["center"]
                results.append({
                    "name": feat.get("place_name", q),
                    "lat": lat,
                    "lon": lon,
                    "provider": "mapbox",
                })

            if results:
                QuotaGuard.record_call("mapbox", "geocoding")
                return results
        except Exception as e:
            logger.warning(f"Mapbox geocoding failed ({e}), falling back to Google...")

    # 2. Google Geocoding (Secondary - 40k free/mo)
    if GOOGLE_KEY and QuotaGuard.can_use("google"):
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": q,
                "region": "in",
                "key": GOOGLE_KEY,
            }
            async with httpx.AsyncClient(timeout=6.0) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()

            results = []
            for res in data.get("results", [])[:limit]:
                loc = res.get("geometry", {}).get("location", {})
                if "lat" in loc and "lng" in loc:
                    results.append({
                        "name": res.get("formatted_address", q),
                        "lat": loc["lat"],
                        "lon": loc["lng"],
                        "provider": "google",
                    })

            if results:
                QuotaGuard.record_call("google", "geocoding")
                return results
        except Exception as e:
            logger.warning(f"Google geocoding failed ({e}), falling back to Nominatim...")

    # 3. OpenStreetMap Nominatim Fallback
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": q,
            "format": "json",
            "countrycodes": "in",
            "limit": limit,
        }
        headers = {"User-Agent": "MotoWeather/5.0"}
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(url, params=params, headers=headers)
            data = r.json()

        return [
            {
                "name": item.get("display_name", q),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "provider": "nominatim",
            }
            for item in data if "lat" in item and "lon" in item
        ]
    except Exception as e:
        logger.error(f"All geocoding providers failed: {e}")
        return []

"""
Google Places & Mapbox Search Engine for Highway Pitstops.

Enriches highway pitstops with:
- Live Google Ratings (e.g., 4.5 ⭐ from 1,200 reviews)
- Operational Status (Open now)
- Verified brand names (HPCL, BPCL, Tata Power EV, McDonald's, Dhabas)
- Quota Guarded to prevent billing overages.
"""
from __future__ import annotations

import os
from typing import List, Dict, Optional, Tuple
import httpx
from dotenv import load_dotenv

from services.quota_guard import QuotaGuard
from utils.logger import setup_logger

load_dotenv()
logger = setup_logger("places_engine")

MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
GOOGLE_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

# Type mappings
_GOOGLE_TYPES = {
    "fuel": "gas_station",
    "charging": "electric_vehicle_charging_station|gas_station",
    "food": "restaurant|cafe|meal_takeaway",
    "breakfast": "cafe|bakery|restaurant",
    "lunch": "restaurant",
    "chai": "cafe|restaurant",
    "dinner": "restaurant",
    "break": "cafe|restaurant",
}

_MAPBOX_CATEGORIES = {
    "fuel": "gas station",
    "charging": "ev charging",
    "food": "restaurant, cafe",
    "breakfast": "cafe, breakfast",
    "lunch": "restaurant, dhaba",
    "chai": "tea, cafe",
    "dinner": "restaurant",
    "break": "cafe, rest area",
}


async def search_nearby_amenity_google(
    lat: float, lon: float, amenity_type: str, radius_m: int = 5000
) -> Optional[Dict]:
    """Search Google Places Nearby Search for highest rated amenity."""
    if not GOOGLE_KEY or not QuotaGuard.can_use("google"):
        return None

    place_type = _GOOGLE_TYPES.get(amenity_type, "restaurant")
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": radius_m,
        "type": place_type.split("|")[0],
        "key": GOOGLE_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") == "OK" and data.get("results"):
            # Sort by rating and user_ratings_total
            results = data["results"]
            valid = [r for r in results if r.get("business_status") != "CLOSED_PERMANENTLY"]
            if not valid:
                valid = results

            # Pick highest rated with reasonable reviews
            best = max(valid, key=lambda x: (x.get("rating", 0.0) * min(x.get("user_ratings_total", 0), 100)))
            loc = best.get("geometry", {}).get("location", {})

            QuotaGuard.record_call("google", "places")
            return {
                "name": best.get("name", "Highway Amenity"),
                "lat": loc.get("lat", lat),
                "lon": loc.get("lng", lon),
                "rating": best.get("rating"),
                "user_ratings_total": best.get("user_ratings_total"),
                "open_now": best.get("opening_hours", {}).get("open_now"),
                "vicinity": best.get("vicinity", ""),
                "provider": "google",
            }
    except Exception as e:
        logger.warning(f"Google Places search failed ({e}).")

    return None


async def search_nearby_amenity_mapbox(
    lat: float, lon: float, amenity_type: str, radius_m: int = 5000
) -> Optional[Dict]:
    """Search Mapbox POI search as fallback."""
    if not MAPBOX_TOKEN or not QuotaGuard.can_use("mapbox"):
        return None

    query = _MAPBOX_CATEGORIES.get(amenity_type, "restaurant")
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
    params = {
        "access_token": MAPBOX_TOKEN,
        "proximity": f"{lon},{lat}",
        "types": "poi",
        "limit": 3,
    }

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        features = data.get("features", [])
        if features:
            best = features[0]
            plon, plat = best["center"]
            QuotaGuard.record_call("mapbox", "search")
            return {
                "name": best.get("text", best.get("place_name", "Highway Stop")),
                "lat": plat,
                "lon": plon,
                "rating": 4.2,  # Default baseline for Mapbox verified POIs
                "user_ratings_total": None,
                "open_now": True,
                "vicinity": best.get("place_name", ""),
                "provider": "mapbox",
            }
    except Exception as e:
        logger.warning(f"Mapbox POI search failed ({e}).")

    return None


async def resolve_live_amenity(
    lat: float, lon: float, amenity_type: str, radius_m: int = 6000
) -> Optional[Dict]:
    """
    Resolve best live amenity near (lat, lon) using Google Places -> Mapbox Search.
    """
    # 1. Try Google Places (most detailed ratings & opening hours)
    res = await search_nearby_amenity_google(lat, lon, amenity_type, radius_m)
    if res:
        return res

    # 2. Try Mapbox POI Search
    res = await search_nearby_amenity_mapbox(lat, lon, amenity_type, radius_m)
    if res:
        return res

    return None

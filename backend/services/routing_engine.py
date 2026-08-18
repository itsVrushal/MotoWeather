"""
Unified Multi-Provider Routing Engine with Real-Time Traffic & Roadworks.

Supports:
1. Mapbox Directions API (with driving-traffic profile & congestion annotations)
2. Google Maps Directions API (with live traffic duration & warnings)
3. Local OSRM Docker Engine (Offline safety net)

Guarded by QuotaGuard to prevent billing overages.
"""
from __future__ import annotations

import os
import re
from typing import Tuple, List, Dict, Optional
import httpx
from dotenv import load_dotenv

from services.quota_guard import QuotaGuard
from utils.logger import setup_logger

load_dotenv()
logger = setup_logger("routing_engine")

MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
GOOGLE_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "http://localhost:5000").rstrip("/")
ROUTING_PROVIDER = os.getenv("ROUTING_PROVIDER", "hybrid").lower()


# ---------------------------------------------------------------------------
# Polyline Decoder for Google Maps
# ---------------------------------------------------------------------------

def _decode_google_polyline(polyline_str: str) -> List[Tuple[float, float]]:
    """Decodes an encoded Google Maps polyline string to list of (lat, lon)."""
    index, lat, lng = 0, 0, 0
    coordinates = []
    length = len(polyline_str)

    while index < length:
        # Latitude
        shift, result = 0, 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        # Longitude
        shift, result = 0, 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        coordinates.append((lat / 1e5, lng / 1e5))

    return coordinates


# ---------------------------------------------------------------------------
# Mapbox Provider (Live Traffic & Congestion Annotations)
# ---------------------------------------------------------------------------

async def _fetch_mapbox_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> Tuple[List[Tuple[float, float]], float, float, List[Dict], List[str], List[str]]:
    if not MAPBOX_TOKEN:
        raise ValueError("MAPBOX_ACCESS_TOKEN is missing or empty.")

    url = (
        f"https://api.mapbox.com/directions/v5/mapbox/driving-traffic/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
    )
    params = {
        "access_token": MAPBOX_TOKEN,
        "geometries": "geojson",
        "overview": "full",
        "steps": "true",
        "annotations": "congestion,maxspeed",
    }

    async with httpx.AsyncClient(timeout=14.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("routes"):
        raise ValueError("No route found in Mapbox response.")

    route = data["routes"][0]
    coords_raw = route["geometry"]["coordinates"]  # [[lon, lat], ...]
    coords = [(c[1], c[0]) for c in coords_raw]  # [(lat, lon), ...]
    dist_km = route["distance"] / 1000.0
    duration_hrs = route["duration"] / 3600.0

    steps = []
    congestion_list = []
    roadwork_alerts = []

    legs = route.get("legs", [])
    for leg in legs:
        # Extract live congestion
        ann = leg.get("annotation", {})
        if "congestion" in ann:
            congestion_list.extend(ann["congestion"])

        # Extract highway steps
        for st in leg.get("steps", []):
            name = st.get("name", "").strip()
            dist_step = st.get("distance", 0.0) / 1000.0
            if name:
                steps.append({"name": name, "distance_km": dist_step})

            # Check for construction / closure notices
            for banner in st.get("bannerInstructions", []):
                text = banner.get("primary", {}).get("text", "")
                if any(w in text.lower() for w in ["construction", "roadwork", "diversion", "closed", "accident"]):
                    roadwork_alerts.append(f"{name or 'Route stretch'}: {text}")

    # If congestion length doesn't match coordinates, fill default
    if not congestion_list:
        congestion_list = ["low"] * len(coords)

    QuotaGuard.record_call("mapbox", "directions")
    return coords, dist_km, duration_hrs, steps, congestion_list, roadwork_alerts


# ---------------------------------------------------------------------------
# Google Maps Provider (Traffic & Warnings)
# ---------------------------------------------------------------------------

async def _fetch_google_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> Tuple[List[Tuple[float, float]], float, float, List[Dict], List[str], List[str]]:
    if not GOOGLE_KEY:
        raise ValueError("GOOGLE_MAPS_API_KEY is missing or empty.")

    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{start_lat},{start_lon}",
        "destination": f"{end_lat},{end_lon}",
        "mode": "driving",
        "departure_time": "now",  # Request live traffic conditions
        "key": GOOGLE_KEY,
    }

    async with httpx.AsyncClient(timeout=14.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") != "OK" or not data.get("routes"):
        raise ValueError(f"Google Maps routing failed: {data.get('status')} - {data.get('error_message')}")

    route = data["routes"][0]
    poly_encoded = route["overview_polyline"]["points"]
    coords = _decode_google_polyline(poly_encoded)

    total_meters = 0.0
    total_secs = 0.0
    steps = []
    roadwork_alerts = []

    # Check route-level warnings
    for warn in route.get("warnings", []):
        roadwork_alerts.append(warn)

    for leg in route.get("legs", []):
        total_meters += leg.get("distance", {}).get("value", 0.0)
        # Use duration_in_traffic if available
        dur_traffic = leg.get("duration_in_traffic", leg.get("duration", {}))
        total_secs += dur_traffic.get("value", 0.0)

        for st in leg.get("steps", []):
            instr = st.get("html_instructions", "")
            clean_name = re.sub(r"<[^>]+>", "", instr)
            step_dist_km = st.get("distance", {}).get("value", 0.0) / 1000.0
            if clean_name and step_dist_km > 0.5:
                steps.append({"name": clean_name, "distance_km": step_dist_km})

            if any(w in clean_name.lower() for w in ["construction", "road work", "diversion", "closed"]):
                roadwork_alerts.append(clean_name)

    dist_km = total_meters / 1000.0
    duration_hrs = total_secs / 3600.0
    congestion_list = ["low"] * len(coords)

    QuotaGuard.record_call("google", "directions")
    return coords, dist_km, duration_hrs, steps, congestion_list, roadwork_alerts


# ---------------------------------------------------------------------------
# Local OSRM Fallback Provider
# ---------------------------------------------------------------------------

async def _fetch_osrm_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> Tuple[List[Tuple[float, float]], float, float, List[Dict], List[str], List[str]]:
    url = f"{OSRM_BASE_URL}/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("OSRM returned no route.")

    route = data["routes"][0]
    coords_raw = route["geometry"]["coordinates"]
    coords = [(c[1], c[0]) for c in coords_raw]
    dist_km = route["distance"] / 1000.0
    duration_hrs = route["duration"] / 3600.0

    steps = []
    for leg in route.get("legs", []):
        for st in leg.get("steps", []):
            name = st.get("name", "").strip()
            dist_step = st.get("distance", 0.0) / 1000.0
            if name:
                steps.append({"name": name, "distance_km": dist_step})

    congestion_list = ["low"] * len(coords)
_ROUTE_CACHE: dict[str, tuple] = {}

async def get_unified_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> Tuple[List[Tuple[float, float]], float, float, List[Dict], List[str], List[str], str]:
    """
    Computes route using active provider with traffic & zero-billing failover:
    Mapbox (driving-traffic) -> Google Maps (traffic) -> Local OSRM.
    
    Cached in-memory to prevent repeated API calls for same origin/destination.
    Returns: (coords, distance_km, duration_hours, steps, congestion_list, roadwork_alerts, provider_name)
    """
    pref = os.getenv("ROUTING_PROVIDER", "hybrid").lower()
    cache_key = f"{round(start_lat, 4)}_{round(start_lon, 4)}_{round(end_lat, 4)}_{round(end_lon, 4)}_{pref}"
    if cache_key in _ROUTE_CACHE:
        logger.info(f"Returning cached route calculation for {cache_key}")
        return _ROUTE_CACHE[cache_key]

    # 1. Explicit provider
    if pref == "osrm":
        logger.info("Using explicit local OSRM provider.")
        coords, dist, dur, steps, cong, alerts = await _fetch_osrm_route(start_lat, start_lon, end_lat, end_lon)
        res = (coords, dist, dur, steps, cong, alerts, "osrm")
        _ROUTE_CACHE[cache_key] = res
        return res

    if pref == "google":
        if QuotaGuard.can_use("google"):
            logger.info("Using explicit Google Maps provider.")
            coords, dist, dur, steps, cong, alerts = await _fetch_google_route(start_lat, start_lon, end_lat, end_lon)
            res = (coords, dist, dur, steps, cong, alerts, "google")
            _ROUTE_CACHE[cache_key] = res
            return res
        logger.warning("Google quota full, falling back to OSRM.")
        coords, dist, dur, steps, cong, alerts = await _fetch_osrm_route(start_lat, start_lon, end_lat, end_lon)
        res = (coords, dist, dur, steps, cong, alerts, "osrm")
        _ROUTE_CACHE[cache_key] = res
        return res

    if pref == "mapbox":
        if QuotaGuard.can_use("mapbox"):
            logger.info("Using explicit Mapbox provider.")
            coords, dist, dur, steps, cong, alerts = await _fetch_mapbox_route(start_lat, start_lon, end_lat, end_lon)
            res = (coords, dist, dur, steps, cong, alerts, "mapbox")
            _ROUTE_CACHE[cache_key] = res
            return res
        logger.warning("Mapbox quota full, falling back to OSRM.")
        coords, dist, dur, steps, cong, alerts = await _fetch_osrm_route(start_lat, start_lon, end_lat, end_lon)
        res = (coords, dist, dur, steps, cong, alerts, "osrm")
        _ROUTE_CACHE[cache_key] = res
        return res

    # 2. Hybrid Mode: Mapbox (Primary) -> Google Maps (Backup) -> Local OSRM
    if MAPBOX_TOKEN and QuotaGuard.can_use("mapbox"):
        try:
            logger.info("Requesting live traffic route from Mapbox Directions API...")
            coords, dist, dur, steps, cong, alerts = await _fetch_mapbox_route(start_lat, start_lon, end_lat, end_lon)
            logger.info(f"Mapbox route success: {dist:.1f} km, {dur:.2f} hrs, {len(coords)} points.")
            res = (coords, dist, dur, steps, cong, alerts, "mapbox")
            _ROUTE_CACHE[cache_key] = res
            return res
        except Exception as e:
            logger.warning(f"Mapbox routing failed ({e}). Falling back to Google Maps...")

    if GOOGLE_KEY and QuotaGuard.can_use("google"):
        try:
            logger.info("Requesting route from Google Maps API...")
            coords, dist, dur, steps, cong, alerts = await _fetch_google_route(start_lat, start_lon, end_lat, end_lon)
            logger.info(f"Google Maps route success: {dist:.1f} km, {dur:.2f} hrs.")
            res = (coords, dist, dur, steps, cong, alerts, "google")
            _ROUTE_CACHE[cache_key] = res
            return res
        except Exception as e:
            logger.warning(f"Google Maps routing failed ({e}). Falling back to local OSRM...")

    logger.info("Falling back to local OSRM engine...")
    coords, dist, dur, steps, cong, alerts = await _fetch_osrm_route(start_lat, start_lon, end_lat, end_lon)
    res = (coords, dist, dur, steps, cong, alerts, "osrm")
    _ROUTE_CACHE[cache_key] = res
    return res

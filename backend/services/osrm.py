"""
OSRM routing service.

Fetches a driving route from the locally hosted OSRM instance
(Docker, Maharashtra OSM data) and decodes the GeoJSON polyline
into a list of (lat, lon) coordinate pairs.

Expected OSRM Docker to be running at OSRM_BASE_URL (default: localhost:5000).
"""
from __future__ import annotations

import os
from typing import Optional

import httpx
from dotenv import load_dotenv

from utils.logger import setup_logger

load_dotenv()

logger = setup_logger("osrm")

OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "http://localhost:5000")


async def fetch_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """
    Request a driving route from OSRM and return the raw API response.

    Args:
        start_lat, start_lon: Origin coordinates.
        end_lat, end_lon:     Destination coordinates.
        client:               Optional shared httpx.AsyncClient.

    Returns:
        Parsed OSRM JSON response dict.

    Raises:
        RuntimeError: If OSRM is unreachable or returns an error.
        ValueError:   If no route is found between the given coordinates.
    """
    # OSRM expects coordinates as lon,lat (note: longitude first)
    coordinates = f"{start_lon},{start_lat};{end_lon},{end_lat}"
    url = f"{OSRM_BASE_URL}/route/v1/driving/{coordinates}"
    params = {
        "overview": "full",
        "geometries": "geojson",  # GeoJSON is easier to decode than polyline6
        "steps": "true",
        "annotations": "false",
    }

    _own_client = client is None
    if _own_client:
        client = httpx.AsyncClient()

    try:
        logger.debug(f"Requesting OSRM route from {OSRM_BASE_URL} (lon,lat: {start_lon},{start_lat} to {end_lon},{end_lat})")
        response = await client.get(url, params=params, timeout=15.0)
    except httpx.ConnectError as e:
        logger.error(f"Failed to connect to OSRM at {OSRM_BASE_URL}")
        raise RuntimeError(
            f"Cannot connect to OSRM at {OSRM_BASE_URL}. "
            "Make sure the OSRM Docker container is running. "
            "See osrm/README.md for setup instructions."
        ) from e
    finally:
        if _own_client:
            await client.aclose()

    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok":
        raise ValueError(
            f"OSRM returned error code '{data.get('code')}': {data.get('message', 'Unknown error')}. "
            "The route may not be reachable within the Maharashtra OSM extract."
        )

    if not data.get("routes"):
        logger.error("OSRM returned valid JSON but no routes found.")
        raise ValueError("OSRM returned no routes for the given coordinates.")

    logger.debug("Successfully fetched raw route from OSRM.")
    return data


def decode_geojson_route(osrm_response: dict) -> tuple[list[tuple[float, float]], float, float]:
    """
    Extract the route polyline, total distance, and duration from an OSRM response.

    Args:
        osrm_response: Parsed OSRM JSON as returned by fetch_route().

    Returns:
        (coords, total_distance_km, total_duration_hours)
        where coords is a list of (lat, lon) tuples.
    """
    route = osrm_response["routes"][0]
    geometry = route["geometry"]  # GeoJSON LineString

    # GeoJSON coordinates are [lon, lat] — swap to (lat, lon)
    coords: list[tuple[float, float]] = [
        (point[1], point[0]) for point in geometry["coordinates"]
    ]

    total_distance_km = route["distance"] / 1000.0
    total_duration_hours = route["duration"] / 3600.0

    return coords, total_distance_km, total_duration_hours


def extract_highway_breakdown(osrm_response: dict) -> list[dict]:
    """
    Extract major highways and roads along the route with their distances and percentage.
    """
    routes = osrm_response.get("routes", [])
    if not routes:
        return []

    total_dist = routes[0].get("distance", 0) / 1000.0
    if total_dist <= 0:
        return []

    legs = routes[0].get("legs", [])
    highways: dict[str, float] = {}

    for leg in legs:
        for step in leg.get("steps", []):
            name = step.get("name", "").strip()
            # Clean up common road naming
            if not name:
                name = "State/Connecting Roads"
            dist_km = step.get("distance", 0) / 1000.0
            highways[name] = highways.get(name, 0.0) + dist_km

    # Sort descending by distance
    sorted_hw = sorted(highways.items(), key=lambda x: x[1], reverse=True)

    result = []
    for name, dist in sorted_hw:
        if dist >= 2.0:  # Only include segments of at least 2 km
            pct = round((dist / total_dist) * 100.0, 1)
            result.append({
                "name": name,
                "distance_km": round(dist, 1),
                "pct": pct
            })

    return result[:6]  # Top 6 major highway segments


async def get_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> tuple[list[tuple[float, float]], float, float]:
    """
    Convenience wrapper: fetch and decode in one call.

    Returns:
        (coords, total_distance_km, total_duration_hours)
    """
    raw = await fetch_route(start_lat, start_lon, end_lat, end_lon)
    coords, distance, duration = decode_geojson_route(raw)
    logger.info(f"OSRM returned {len(coords)} coordinate points, {distance:.2f} km, {duration:.2f} hours")
    return coords, distance, duration


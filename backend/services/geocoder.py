"""
Geocoding service using Nominatim (OpenStreetMap).

Converts human-readable addresses to (lat, lon) coordinates.
Restricted to India (countrycodes=in) for relevant results.

Nominatim usage policy requires:
  - A descriptive User-Agent header
  - Maximum 1 request per second
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

NOMINATIM_BASE_URL = os.getenv("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
_USER_AGENT = "MotoWeatherRouter/1.0 (local-dev; motorcycle routing app)"

# Nominatim rate limit: 1 request per second
_RATE_LIMIT_SECONDS = 1.1


async def geocode_address(
    address: str,
    client: httpx.AsyncClient,
) -> tuple[float, float]:
    """
    Convert a human-readable address string to (lat, lon).

    Args:
        address: e.g. "Pune, Maharashtra" or "Nashik"
        client:  Shared httpx.AsyncClient instance.

    Returns:
        (latitude, longitude) as floats.

    Raises:
        ValueError: If no result is found for the given address.
        httpx.HTTPError: On network-level failures.
    """
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
        "countrycodes": "in",
        "addressdetails": 0,
    }
    headers = {"User-Agent": _USER_AGENT}

    response = await client.get(
        f"{NOMINATIM_BASE_URL}/search",
        params=params,
        headers=headers,
        timeout=10.0,
    )
    response.raise_for_status()
    results = response.json()

    if not results:
        raise ValueError(
            f"Geocoding failed: no result found for '{address}'. "
            "Try a more specific address, e.g. 'Pune, Maharashtra, India'."
        )

    best = results[0]
    return float(best["lat"]), float(best["lon"])


async def geocode_pair(
    start_address: str,
    end_address: str,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    Geocode start and end addresses sequentially (respecting Nominatim rate limit).

    Returns:
        ((start_lat, start_lon), (end_lat, end_lon))
    """
    async with httpx.AsyncClient() as client:
        start_coords = await geocode_address(start_address, client)
        # Rate limit: wait before second request
        await asyncio.sleep(_RATE_LIMIT_SECONDS)
        end_coords = await geocode_address(end_address, client)

    return start_coords, end_coords

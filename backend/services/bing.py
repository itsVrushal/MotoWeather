"""
Bing Maps routing service.
Replaces OSRM for route calculation to offload local system resources.
"""
from __future__ import annotations

import os
from typing import Optional
import httpx
from dotenv import load_dotenv
from utils.logger import setup_logger

load_dotenv()
logger = setup_logger("bing")

BING_MAPS_API_KEY = os.getenv("BING_MAPS_API_KEY", "")

async def get_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> tuple[list[tuple[float, float]], float, float]:
    """
    Fetch a driving route from Bing Maps and return identical format to OSRM.
    
    Returns:
        (coords, total_distance_km, total_duration_hours)
    """
    if not BING_MAPS_API_KEY:
        raise ValueError("BING_MAPS_API_KEY environment variable is not set.")

    url = "https://dev.virtualearth.net/REST/v1/Routes/Driving"
    params = {
        "wp.0": f"{start_lat},{start_lon}",
        "wp.1": f"{end_lat},{end_lon}",
        "routeAttributes": "routePath",
        "key": BING_MAPS_API_KEY,
    }

    async with httpx.AsyncClient() as client:
        logger.debug(f"Requesting Bing Maps route from {start_lat},{start_lon} to {end_lat},{end_lon}")
        response = await client.get(url, params=params, timeout=15.0)
        
        # If API key is invalid or unauthorized, it returns 401 or 403
        if response.status_code in [401, 403]:
            raise ValueError(f"Bing Maps API key is invalid or forbidden ({response.status_code}). Please verify in Bing Dev Center.")
            
        response.raise_for_status()
        data = response.json()

    # Parse Bing Maps response
    resource_sets = data.get("resourceSets", [])
    if not resource_sets or not resource_sets[0].get("resources"):
        raise ValueError("Bing Maps returned no route resources.")
        
    route = resource_sets[0]["resources"][0]
    
    # Distance is returned in kilometers by default
    total_distance_km = route.get("travelDistance", 0.0)
    
    # Duration is returned in seconds
    total_duration_hours = route.get("travelDuration", 0.0) / 3600.0

    # Extract coordinates
    # Bing returns routePath -> line -> coordinates as a list of [lat, lon] arrays
    route_path = route.get("routePath", {})
    line = route_path.get("line", {})
    coords_list = line.get("coordinates", [])
    
    if not coords_list:
        raise ValueError("Bing Maps returned no route geometry.")

    # Bing already uses [lat, lon] natively (unlike GeoJSON's lon, lat)
    coords = [(float(pt[0]), float(pt[1])) for pt in coords_list]
    
    logger.info(f"Bing Maps returned {len(coords)} coordinate points, {total_distance_km:.2f} km, {total_duration_hours:.2f} hours")
    return coords, total_distance_km, total_duration_hours

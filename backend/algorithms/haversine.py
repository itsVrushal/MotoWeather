"""
Haversine distance formula and route sampling utilities.

Provides:
  - haversine(lat1, lon1, lat2, lon2) -> distance in km
  - cumulative_distances(coords)      -> list of km values
  - sample_route(coords, interval_km) -> sampled (lat, lon, cumulative_km) tuples
  - compute_eta(departure, cumulative_km, avg_speed_kmh) -> datetime
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0


# ---------------------------------------------------------------------------
# Haversine formula
# ---------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance in kilometres between two points
    on the Earth's surface using the Haversine formula.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


# ---------------------------------------------------------------------------
# Cumulative distance along a polyline
# ---------------------------------------------------------------------------

def cumulative_distances(coords: list[tuple[float, float]]) -> list[float]:
    """
    Given a list of (lat, lon) pairs representing a route polyline,
    return a parallel list of cumulative distances from the start (km).
    First element is always 0.0.
    """
    distances = [0.0]
    for i in range(1, len(coords)):
        lat1, lon1 = coords[i - 1]
        lat2, lon2 = coords[i]
        distances.append(distances[-1] + haversine(lat1, lon1, lat2, lon2))
    return distances


# ---------------------------------------------------------------------------
# Route sampling
# ---------------------------------------------------------------------------

class SampledPoint(NamedTuple):
    lat: float
    lon: float
    cumulative_km: float


def sample_route(
    coords: list[tuple[float, float]],
    interval_km: float = 25.0,
) -> list[SampledPoint]:
    """
    Sample waypoints from a route polyline at regular kilometre intervals.

    The first point (start) and last point (destination) are always included.
    Intermediate points are inserted every `interval_km` kilometres along
    the cumulative route distance.

    Args:
        coords:      List of (lat, lon) tuples decoded from OSRM polyline.
        interval_km: Desired spacing between sampled waypoints (default 25 km).

    Returns:
        List of SampledPoint(lat, lon, cumulative_km).
    """
    if not coords:
        return []

    cum_dists = cumulative_distances(coords)
    total_km = cum_dists[-1]

    # Build a list of target distances to sample at
    targets: list[float] = [0.0]
    next_target = interval_km
    while next_target < total_km:
        targets.append(next_target)
        next_target += interval_km
    if targets[-1] < total_km:
        targets.append(total_km)

    sampled: list[SampledPoint] = []
    coord_idx = 0

    for target in targets:
        # Advance along the polyline until we pass the target distance
        while coord_idx < len(cum_dists) - 1 and cum_dists[coord_idx + 1] < target:
            coord_idx += 1

        if coord_idx >= len(coords) - 1:
            # Clamp to last point
            lat, lon = coords[-1]
            sampled.append(SampledPoint(lat, lon, cum_dists[-1]))
            continue

        # Linearly interpolate between coord_idx and coord_idx+1
        d0 = cum_dists[coord_idx]
        d1 = cum_dists[coord_idx + 1]
        segment_len = d1 - d0

        if segment_len < 1e-9:
            lat, lon = coords[coord_idx]
        else:
            t = (target - d0) / segment_len
            lat0, lon0 = coords[coord_idx]
            lat1, lon1 = coords[coord_idx + 1]
            lat = lat0 + t * (lat1 - lat0)
            lon = lon0 + t * (lon1 - lon0)

        sampled.append(SampledPoint(lat, lon, target))

    return sampled


# ---------------------------------------------------------------------------
# ETA calculation
# ---------------------------------------------------------------------------

def compute_eta(
    departure: datetime,
    cumulative_km: float,
    avg_speed_kmh: float,
) -> datetime:
    """
    Compute the Expected Time of Arrival at a waypoint.

    ETA(P_i) = departure_time + cumulative_distance(P_i) / avg_speed

    Args:
        departure:      Rider's departure datetime (timezone-aware or naive).
        cumulative_km:  Distance from start to this waypoint in km.
        avg_speed_kmh:  Rider's average speed in km/h.

    Returns:
        Estimated arrival datetime at this waypoint.
    """
    if avg_speed_kmh <= 0:
        raise ValueError("avg_speed_kmh must be positive")
    hours = cumulative_km / avg_speed_kmh
    return departure + timedelta(hours=hours)

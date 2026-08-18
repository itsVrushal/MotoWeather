"""
FastAPI route router for MotoWeather — Integrated with Dual API (Mapbox + Google Maps), Traffic & Quota Guard.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, status

from algorithms.haversine import sample_route, compute_eta
from algorithms.fsm import run_fsm
from models.schemas import (
    Coordinate,
    HazardScore,
    HazardSegment,
    HighwaySegment,
    DaylightSummary,
    DepartureAdvice,
    Pitstop,
    PitstopRequest,
    PitstopResponse,
    PitstopType,
    RouteRequest,
    RouteResponse,
    Briefing,
    Waypoint,
)
from services.geocoding_engine import search_places, geocode
from services.optimizer import find_optimal_departure, build_departure_advice
from services.pitstops import resolve_pitstops
from services.quota_guard import QuotaGuard
from services.routing_engine import get_unified_route
from services.weather import fetch_weather_batch
from utils.logger import setup_logger

logger = setup_logger("route")

router = APIRouter(prefix="/api", tags=["route"])

_SAMPLE_INTERVAL_KM = float(os.getenv("SAMPLE_INTERVAL_KM", "25"))


# ---------------------------------------------------------------------------
# Helpers for Journey Analytics
# ---------------------------------------------------------------------------

def compute_daylight_summary(departure: datetime, total_hours: float) -> DaylightSummary:
    """Calculate daylight vs night driving split for Maharashtra."""
    total_mins = max(15, int(total_hours * 60))
    day_mins = 0
    night_mins = 0
    sunset_dt = None

    for m in range(0, total_mins, 15):
        cur = departure + timedelta(minutes=m)
        hr = cur.hour + cur.minute / 60.0
        # Daylight roughly 06:15 to 18:45
        if 6.25 <= hr <= 18.75:
            day_mins += 15
        else:
            night_mins += 15
            if sunset_dt is None and hr > 18.75:
                sunset_dt = cur

    day_hrs = round(day_mins / 60.0, 1)
    night_hrs = round(night_mins / 60.0, 1)
    day_pct = round((day_mins / total_mins) * 100.0)
    night_pct = 100 - day_pct

    sunset_str = sunset_dt.strftime("%I:%M %p") if sunset_dt else "06:45 PM"

    if night_hrs > 0:
        advisory = (
            f"{day_hrs}h in Daylight ({day_pct}%), {night_hrs}h Night riding ({night_pct}%). "
            f"Sunset expected around {sunset_str} — high-beam and reflective gear recommended."
        )
    else:
        advisory = f"100% Full Daylight ({day_hrs}h) — optimal road visibility from start to finish."

    return DaylightSummary(
        daylight_hours=day_hrs,
        night_hours=night_hrs,
        daylight_pct=day_pct,
        night_pct=night_pct,
        sunset_time_str=sunset_str,
        advisory=advisory,
    )


def extract_hazard_segments(waypoints: list[Waypoint], roadwork_alerts: list[str]) -> list[HazardSegment]:
    """Group waypoints with adverse weather, traffic, or construction into clear hazard cards with map coordinates."""
    segments: list[HazardSegment] = []

    # 1. High wind stretches
    windy_wps = [wp for wp in waypoints if wp.wind_kmh >= 26.0]
    if windy_wps:
        start_km = min(wp.cumulative_km for wp in windy_wps)
        end_km = max(wp.cumulative_km for wp in windy_wps)
        worst_wind_wp = max(windy_wps, key=lambda w: w.wind_kmh)
        segments.append(
            HazardSegment(
                title="High Crosswinds",
                stretch_km=f"Km {start_km:.0f}–{end_km:.0f}",
                hazard_type="wind",
                severity="moderate" if worst_wind_wp.wind_kmh < 35 else "high",
                description=f"Strong crosswinds up to {worst_wind_wp.wind_kmh:.0f} km/h. Keep steady handlebar grip on elevated flyovers.",
                lat=worst_wind_wp.lat,
                lon=worst_wind_wp.lon,
            )
        )

    # 2. Rain alert stretches
    rain_wps = [wp for wp in waypoints if wp.precip_pct >= 40.0]
    if rain_wps:
        start_km = min(wp.cumulative_km for wp in rain_wps)
        end_km = max(wp.cumulative_km for wp in rain_wps)
        worst_rain_wp = max(rain_wps, key=lambda w: w.precip_pct)
        segments.append(
            HazardSegment(
                title="Rain Warning Zone",
                stretch_km=f"Km {start_km:.0f}–{end_km:.0f}",
                hazard_type="rain",
                severity="high" if worst_rain_wp.precip_pct >= 65 else "moderate",
                description=f"Precipitation probability reaches {worst_rain_wp.precip_pct:.0f}%. Expect wet tarmac and reduced braking grip.",
                lat=worst_rain_wp.lat,
                lon=worst_rain_wp.lon,
            )
        )

    # 3. Traffic Congestion Alert
    heavy_traffic_wps = [wp for wp in waypoints if wp.traffic_level in ["heavy", "severe"]]
    if heavy_traffic_wps:
        start_km = min(wp.cumulative_km for wp in heavy_traffic_wps)
        end_km = max(wp.cumulative_km for wp in heavy_traffic_wps)
        worst_traffic_wp = heavy_traffic_wps[0]
        segments.append(
            HazardSegment(
                title="Heavy Traffic Congestion",
                stretch_km=f"Km {start_km:.0f}–{end_km:.0f}",
                hazard_type="traffic",
                severity="high",
                description="Peak city exit bottleneck / slow-moving traffic. Expect stop-and-go delays.",
                lat=worst_traffic_wp.lat,
                lon=worst_traffic_wp.lon,
            )
        )

    # 4. Roadworks & Construction alerts
    if roadwork_alerts and waypoints:
        mid_wp = waypoints[len(waypoints) // 3]
        for alert in roadwork_alerts[:2]:
            segments.append(
                HazardSegment(
                    title="Roadwork / Diversion Ahead",
                    stretch_km="Active Stretch",
                    hazard_type="roadwork",
                    severity="moderate",
                    description=alert,
                    lat=mid_wp.lat,
                    lon=mid_wp.lon,
                )
            )

    return segments


def build_departure_reason(optimal: datetime, preferred: datetime, scores: list) -> str:
    diff_min = int((optimal - preferred).total_seconds() / 60)
    if diff_min == 0:
        return "Your chosen departure matches optimal weather & traffic conditions along the route."
    direction = "later" if diff_min > 0 else "earlier"
    return (
        f"Departing {abs(diff_min)} min {direction} ({optimal.strftime('%I:%M %p')}) "
        f"avoids peak rain, wind, and city exit traffic bottlenecks."
    )


def compute_highway_breakdown(steps: list[dict], total_dist_km: float) -> list[HighwaySegment]:
    """Aggregate distance per highway name from turn-by-turn steps."""
    hw_totals: dict[str, float] = {}
    for st in steps:
        name = st.get("name", "").strip()
        dist = st.get("distance_km", 0.0)
        if name and dist > 0.3:
            hw_totals[name] = hw_totals.get(name, 0.0) + dist

    if not hw_totals and total_dist_km > 0:
        hw_totals["State / National Highway"] = total_dist_km

    sorted_hw = sorted(hw_totals.items(), key=lambda x: x[1], reverse=True)
    denom = max(1.0, total_dist_km)

    return [
        HighwaySegment(
            name=name,
            distance_km=round(dist, 1),
            pct=round((dist / denom) * 100.0, 1),
        )
        for name, dist in sorted_hw[:6]
    ]


def interpolate_traffic_levels(
    sampled_coords: list, full_coords: list, congestion_list: list[str]
) -> list[str]:
    """Maps continuous traffic congestion segments to sampled waypoints."""
    if not congestion_list:
        return ["low"] * len(sampled_coords)

    traffic_levels = []
    ratio = len(congestion_list) / max(1, len(sampled_coords))
    for i in range(len(sampled_coords)):
        idx = min(len(congestion_list) - 1, int(i * ratio))
        c = congestion_list[idx]
        traffic_levels.append(c if c in ["low", "moderate", "heavy", "severe"] else "low")

    return traffic_levels


# ---------------------------------------------------------------------------
# Endpoint: /api/route
# ---------------------------------------------------------------------------

@router.post(
    "/route",
    response_model=RouteResponse,
    summary="Calculate optimal route and weather briefing with Mapbox/Google dual engine & live traffic",
)
async def calculate_route(request: RouteRequest) -> RouteResponse:
    logger.info(f"Starting route calculation: '{request.start_address}' -> '{request.end_address}'")

    # 1. Resolve coordinates
    if request.start_lat is not None and request.start_lon is not None:
        start_lat, start_lon = request.start_lat, request.start_lon
    else:
        try:
            start_lat, start_lon = await geocode(request.start_address)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Start address error: {e}")

    if request.end_lat is not None and request.end_lon is not None:
        end_lat, end_lon = request.end_lat, request.end_lon
    else:
        try:
            end_lat, end_lon = await geocode(request.end_address)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Destination address error: {e}")

    # 2. Fetch driving route with traffic via Unified Engine (Mapbox -> Google -> OSRM)
    try:
        coords, total_distance_km, engine_duration_hours, steps, congestion_list, roadwork_alerts, provider = await get_unified_route(
            start_lat, start_lon, end_lat, end_lon
        )
        highways = compute_highway_breakdown(steps, total_distance_km)
        logger.info(f"Route calculated via {provider.upper()}: {total_distance_km:.1f} km, {len(highways)} highways, {len(roadwork_alerts)} alerts.")
    except Exception as e:
        logger.error(f"Routing failed: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Routing service error: {e}")

    # 3. Sample waypoints
    sampled = sample_route(coords, interval_km=_SAMPLE_INTERVAL_KM)
    sampled_coords = [(wp.lat, wp.lon) for wp in sampled]
    cumulative_kms = [wp.cumulative_km for wp in sampled]
    traffic_levels = interpolate_traffic_levels(sampled_coords, coords, congestion_list)

    # 4. Optimizer for departure time
    logger.info(f"Running optimizer with {request.window_minutes}min window.")
    optimal_departure, all_scores = await find_optimal_departure(
        preferred_departure=request.preferred_departure,
        window_minutes=request.window_minutes,
        step_minutes=request.window_step_minutes,
        sampled_coords=sampled_coords,
        avg_speed_kmh=request.avg_speed_kmh,
        weather_fetcher=fetch_weather_batch,
        eta_calculator=compute_eta,
        cumulative_kms=cumulative_kms,
    )

    # 5. Fetch weather for the requested departure time
    requested_departure = request.preferred_departure
    final_etas = [
        compute_eta(requested_departure, cum_km, request.avg_speed_kmh)
        for cum_km in cumulative_kms
    ]
    final_weather = await fetch_weather_batch(sampled_coords, final_etas)

    # 6. Waypoints and analytics
    waypoints_out = [
        Waypoint(
            lat=wp.lat,
            lon=wp.lon,
            cumulative_km=wp.cumulative_km,
            eta=eta,
            precip_pct=w.precip_pct,
            wind_kmh=w.wind_kmh,
            temp_c=w.temp_c,
            weathercode=w.weathercode,
            traffic_level=t_level,
        )
        for wp, eta, w, t_level in zip(sampled, final_etas, final_weather, traffic_levels)
    ]

    estimated_duration = total_distance_km / request.avg_speed_kmh
    daylight_summary = compute_daylight_summary(requested_departure, estimated_duration)
    hazard_segments = extract_hazard_segments(waypoints_out, roadwork_alerts)

    worst_rain_wp = max(zip(waypoints_out, final_weather), key=lambda x: x[1].precip_pct, default=None)
    max_wind_wp = max(zip(waypoints_out, final_weather), key=lambda x: x[1].wind_kmh, default=None)

    departure_reason = build_departure_reason(
        optimal=optimal_departure,
        preferred=request.preferred_departure,
        scores=all_scores,
    )

    advice_dict = build_departure_advice(
        optimal=optimal_departure,
        preferred=request.preferred_departure,
        daylight_hours=daylight_summary.daylight_hours,
        night_hours=daylight_summary.night_hours,
        hazard_title=hazard_segments[0].title if hazard_segments else None,
    )
    departure_advice = DepartureAdvice(**advice_dict)

    # Traffic summary description
    heavy_count = sum(1 for t in traffic_levels if t in ["heavy", "severe"])
    if heavy_count > 0:
        traffic_summary = f"Expect slow-moving traffic on {heavy_count * _SAMPLE_INTERVAL_KM:.0f} km of urban/corridor stretches."
    else:
        traffic_summary = "Free-flow highway traffic conditions detected along the entire corridor."

    briefing = Briefing(
        optimal_departure=optimal_departure,
        preferred_departure=request.preferred_departure,
        worst_rain_pct=worst_rain_wp[1].precip_pct if worst_rain_wp else 0.0,
        worst_rain_eta=worst_rain_wp[0].eta if worst_rain_wp else None,
        max_wind_kmh=max_wind_wp[1].wind_kmh if max_wind_wp else 0.0,
        departure_reason=departure_reason,
        departure_advice=departure_advice,
        highways=highways,
        daylight=daylight_summary,
        hazard_segments=hazard_segments,
        traffic_summary=traffic_summary,
        roadwork_alerts=roadwork_alerts,
    )

    hazard_scores = [
        HazardScore(
            departure_time=s.departure_time,
            total_score=s.total_score,
            rain_component=s.rain_component,
            wind_component=s.wind_component,
            delay_component=s.delay_component,
            traffic_component=getattr(s, "traffic_component", 0.0),
            is_optimal=s.is_optimal,
        )
        for s in all_scores
    ]

    logger.info("Route calculation finished successfully. Returning response.")

    return RouteResponse(
        optimal_departure=optimal_departure,
        total_distance_km=round(total_distance_km, 2),
        estimated_duration_hours=round(estimated_duration, 2),
        hazard_scores=hazard_scores,
        waypoints=waypoints_out,
        pitstops=[],
        briefing=briefing,
        geometry=[Coordinate(lat=lat, lon=lon) for lat, lon in coords],
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/pitstops (Google Places + Verified WSA Resolution)
# ---------------------------------------------------------------------------

@router.post(
    "/pitstops",
    response_model=PitstopResponse,
    summary="Fetch pitstops with live Google ratings and amenities",
)
async def calculate_pitstops(request: PitstopRequest) -> PitstopResponse:
    logger.info("Starting background pitstop calculation via Google Places + WSA...")

    from algorithms.haversine import SampledPoint
    sampled = [
        SampledPoint(lat=wp.lat, lon=wp.lon, cumulative_km=wp.cumulative_km)
        for wp in request.waypoints
    ]
    etas = [wp.eta for wp in request.waypoints]
    precip_pcts = [wp.precip_pct for wp in request.waypoints]

    triggers = run_fsm(
        waypoints=sampled,
        etas=etas,
        precip_pcts=precip_pcts,
        tank_range_km=request.tank_range_km,
        vehicle_type=request.vehicle_type,
        interval_km=_SAMPLE_INTERVAL_KM,
    )

    logger.info(f"Resolving {len(triggers)} pitstop triggers via Google Places / WSA Engine.")
    pitstop_results = await resolve_pitstops(
        triggers=triggers,
        buffer_km=request.pitstop_buffer_km,
    )
    logger.info(f"Found {len(pitstop_results)} actual pitstops.")

    pitstops_out = [
        Pitstop(
            type=PitstopType(r.trigger.trigger_type.value),
            sub_type=r.trigger.sub_type,
            lat=r.lat,
            lon=r.lon,
            name=r.name,
            dist_from_route_km=r.dist_from_query_km,
            route_dist_from_last_stop_km=r.trigger.route_dist_from_last_stop_km,
            at_waypoint_index=r.trigger.at_waypoint_index,
            eta=r.trigger.eta,
            osm_id=r.osm_id,
            rating=r.rating,
            user_ratings_total=r.user_ratings_total,
            open_now=r.open_now,
            vicinity=r.vicinity,
        )
        for r in pitstop_results
    ]

    pitstop_summary_lines = []
    emoji_map = {
        "charging": "⚡",
        "fuel": "⛽",
        "breakfast": "☕",
        "lunch": "🍽️",
        "chai": "☕",
        "dinner": "🍽️",
        "break": "☕",
    }
    label_map = {
        "charging": "EV Fast Charger",
        "fuel": "Fuel Plaza",
        "breakfast": "Breakfast Break",
        "lunch": "Family Lunch / Dhaba",
        "chai": "Chai & Snacks",
        "dinner": "Dinner Stop",
    }

    for ps in pitstops_out:
        sub = ps.sub_type or ps.type.value
        emoji = emoji_map.get(sub, "📍")
        label = label_map.get(sub, sub.capitalize())
        dist_str = f" • {ps.route_dist_from_last_stop_km:.0f} km from previous stop" if ps.route_dist_from_last_stop_km > 0 else ""
        rating_str = f" • ⭐ {ps.rating:.1f}" if ps.rating else ""
        pitstop_summary_lines.append(
            f"{emoji} {ps.name} [{label}]{rating_str} — {ps.dist_from_route_km:.1f} km detour{dist_str} — ETA {ps.eta.strftime('%I:%M %p')}"
        )

    logger.info("Background pitstop calculation finished.")
    return PitstopResponse(
        pitstops=pitstops_out,
        pitstop_summary=pitstop_summary_lines,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/geocode (Fast Multi-Provider Autocomplete)
# ---------------------------------------------------------------------------

@router.get("/geocode", summary="Search addresses using Mapbox / Google geocoding")
async def geocode_autocomplete(q: str = Query(..., min_length=2)):
    results = await search_places(q, limit=6)
    return {"query": q, "results": results}


# ---------------------------------------------------------------------------
# Endpoint: /api/quotas (Monitor Monthly Usage & Zero-Billing Caps)
# ---------------------------------------------------------------------------

@router.get("/quotas", summary="Get monthly API usage and remaining quota")
async def get_quotas():
    return QuotaGuard.get_usage_summary()

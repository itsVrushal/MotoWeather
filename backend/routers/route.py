"""
POST /api/route and POST /api/pitstops — Journey planning orchestration.

Pipeline:
  1. Geocode start + end addresses via Nominatim
  2. Fetch route polyline & highway breakdown from local OSRM
  3. Sample waypoints every 25 km using Haversine
  4. Run the sliding-window optimizer to find optimal departure time
  5. Fetch final weather batch for the optimal departure
  6. Compute Daylight vs Night riding hours and sunset advisory
  7. Compute highway weather hazard stretches
  8. Run pitstop FSM to identify Food, Chai & Fuel/EV stops
  9. Build and return structured RouteResponse
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException, status

from algorithms.fsm import run_fsm
from algorithms.haversine import compute_eta, cumulative_distances, sample_route
from models.schemas import (
    Briefing,
    Coordinate,
    DaylightSummary,
    HazardScore,
    HazardSegment,
    HighwaySegment,
    Pitstop,
    PitstopRequest,
    PitstopResponse,
    PitstopType,
    RouteRequest,
    RouteResponse,
    Waypoint,
)
from services.bing import get_route as get_route_bing
from services.geocoder import geocode_address, geocode_pair
from services.optimizer import build_departure_reason, find_optimal_departure
from services.osrm import (
    decode_geojson_route,
    extract_highway_breakdown,
    fetch_route as fetch_route_osrm,
    get_route as get_route_osrm,
)
from services.pitstops import resolve_pitstops
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
        # Daylight in Maharashtra roughly 06:15 to 18:45
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


def extract_hazard_segments(waypoints: list[Waypoint]) -> list[HazardSegment]:
    """Group waypoints with adverse weather into clear route hazard cards."""
    segments: list[HazardSegment] = []

    # 1. High wind stretches
    windy_wps = [wp for wp in waypoints if wp.wind_kmh >= 26.0]
    if windy_wps:
        start_km = min(wp.cumulative_km for wp in windy_wps)
        end_km = max(wp.cumulative_km for wp in windy_wps)
        max_w = max(wp.wind_kmh for wp in windy_wps)
        segments.append(
            HazardSegment(
                title="High Crosswinds",
                stretch_km=f"Km {start_km:.0f}–{end_km:.0f}",
                hazard_type="wind",
                severity="moderate" if max_w < 35 else "high",
                description=f"Strong crosswinds up to {max_w:.0f} km/h. Keep steady handlebar grip on elevated flyovers.",
            )
        )

    # 2. Rain alert stretches
    rain_wps = [wp for wp in waypoints if wp.precip_pct >= 40.0]
    if rain_wps:
        start_km = min(wp.cumulative_km for wp in rain_wps)
        end_km = max(wp.cumulative_km for wp in rain_wps)
        max_p = max(wp.precip_pct for wp in rain_wps)
        segments.append(
            HazardSegment(
                title="Rain Warning Zone",
                stretch_km=f"Km {start_km:.0f}–{end_km:.0f}",
                hazard_type="rain",
                severity="moderate" if max_p < 70 else "high",
                description=f"Precipitation probability reaches {max_p:.0f}%. Expect wet tarmac and reduced braking grip.",
            )
        )

    return segments


# ---------------------------------------------------------------------------
# Endpoint: /api/route
# ---------------------------------------------------------------------------

@router.post(
    "/route",
    response_model=RouteResponse,
    summary="Calculate optimal motorcycle route with weather intelligence",
)
async def calculate_route(request: RouteRequest) -> RouteResponse:
    logger.info(f"Starting route calculation: '{request.start_address}' -> '{request.end_address}'")

    # 1. Geocode
    if request.start_lat is not None and request.start_lon is not None:
        start_lat, start_lon = request.start_lat, request.start_lon
    else:
        start_lat, start_lon = await geocode_address(request.start_address)

    if request.end_lat is not None and request.end_lon is not None:
        end_lat, end_lon = request.end_lat, request.end_lon
    else:
        end_lat, end_lon = await geocode_address(request.end_address)

    # 2. Fetch route & highway breakdown
    routing_engine = os.getenv("ROUTING_ENGINE", "osrm").lower()
    highways: list[HighwaySegment] = []

    try:
        if routing_engine == "bing":
            coords, total_distance_km, osrm_duration_hours = await get_route_bing(
                start_lat, start_lon, end_lat, end_lon
            )
            logger.info("Route fetched using Bing Maps REST API.")
        else:
            raw_osrm = await fetch_route_osrm(start_lat, start_lon, end_lat, end_lon)
            coords, total_distance_km, osrm_duration_hours = decode_geojson_route(raw_osrm)
            hw_list = extract_highway_breakdown(raw_osrm)
            highways = [
                HighwaySegment(name=h["name"], distance_km=h["distance_km"], pct=h["pct"])
                for h in hw_list
            ]
            logger.info(f"Route fetched using local OSRM with {len(highways)} highway segments.")
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except ValueError as e:
        logger.error(f"Routing failed: {e}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    # 3. Sample waypoints
    sampled = sample_route(coords, interval_km=_SAMPLE_INTERVAL_KM)
    sampled_coords = [(wp.lat, wp.lon) for wp in sampled]
    cumulative_kms = [wp.cumulative_km for wp in sampled]

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

    # 5. Fetch weather for optimal departure
    final_etas = [
        compute_eta(optimal_departure, cum_km, request.avg_speed_kmh)
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
        )
        for wp, eta, w in zip(sampled, final_etas, final_weather)
    ]

    estimated_duration = total_distance_km / request.avg_speed_kmh
    daylight_summary = compute_daylight_summary(optimal_departure, estimated_duration)
    hazard_segments = extract_hazard_segments(waypoints_out)

    worst_rain_wp = max(zip(waypoints_out, final_weather), key=lambda x: x[1].precip_pct, default=None)
    max_wind_wp = max(zip(waypoints_out, final_weather), key=lambda x: x[1].wind_kmh, default=None)

    departure_reason = build_departure_reason(
        optimal=optimal_departure,
        preferred=request.preferred_departure,
        scores=all_scores,
    )

    from services.optimizer import build_departure_advice
    from models.schemas import DepartureAdvice
    advice_dict = build_departure_advice(
        optimal=optimal_departure,
        preferred=request.preferred_departure,
        daylight_hours=daylight_summary.daylight_hours,
        night_hours=daylight_summary.night_hours,
        hazard_title=hazard_segments[0].title if hazard_segments else None,
    )
    departure_advice = DepartureAdvice(**advice_dict)

    briefing = Briefing(
        optimal_departure=optimal_departure,
        departure_reason=departure_reason,
        departure_advice=departure_advice,
        max_wind_kmh=max_wind_wp[1].wind_kmh if max_wind_wp else 0.0,
        max_wind_location=Coordinate(lat=max_wind_wp[0].lat, lon=max_wind_wp[0].lon) if max_wind_wp else None,
        max_wind_eta=max_wind_wp[0].eta if max_wind_wp else None,
        worst_rain_pct=worst_rain_wp[1].precip_pct if worst_rain_wp else 0.0,
        worst_rain_location=Coordinate(lat=worst_rain_wp[0].lat, lon=worst_rain_wp[0].lon) if worst_rain_wp else None,
        worst_rain_eta=worst_rain_wp[0].eta if worst_rain_wp else None,
        pitstop_summary=[],
        highways=highways,
        daylight=daylight_summary,
        hazard_segments=hazard_segments,
    )

    hazard_scores = [
        HazardScore(
            departure_time=s.departure_time,
            total_score=s.total_score,
            rain_component=s.rain_component,
            wind_component=s.wind_component,
            delay_component=s.delay_component,
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
# Endpoint: /api/pitstops (Async background resolution)
# ---------------------------------------------------------------------------

@router.post(
    "/pitstops",
    response_model=PitstopResponse,
    summary="Fetch pitstops for a given route asynchronously",
)
async def calculate_pitstops(request: PitstopRequest) -> PitstopResponse:
    logger.info("Starting background pitstop calculation...")

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

    logger.info(f"Resolving {len(triggers)} pitstop triggers via OSM Nominatim + OSRM.")
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
        "charging": "EV Charge",
        "fuel": "Fuel Refill",
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
        pitstop_summary_lines.append(
            f"{emoji} {ps.name} [{label}] — {ps.dist_from_route_km:.1f} km detour{dist_str} — ETA {ps.eta.strftime('%I:%M %p')}"
        )

    logger.info("Background pitstop calculation finished.")
    return PitstopResponse(
        pitstops=pitstops_out,
        pitstop_summary=pitstop_summary_lines,
    )

"""
Departure Time Optimizer — Sliding Window Algorithm.

Evaluates N candidate departure times within a ±window around the rider's
preferred time. For each candidate, computes a total Hazard Score:

    S(t) = w_r × R(t) + w_w × W(t) + w_d × D(t)

Where:
    R(t): Normalised accumulated precipitation probability along the route.
    W(t): Normalised maximum wind speed encountered on the route.
    D(t): Normalised time penalty (absolute minutes from preferred departure).

Returns the candidate time with the minimum S(t) and the full score array
for charting in the frontend.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv

from utils.logger import setup_logger

load_dotenv()

logger = setup_logger("optimizer")

# Default weights — configurable via .env
_WEIGHT_RAIN = float(os.getenv("WEIGHT_RAIN", "0.6"))
_WEIGHT_WIND = float(os.getenv("WEIGHT_WIND", "0.3"))
_WEIGHT_DELAY = float(os.getenv("WEIGHT_DELAY", "0.1"))

# Normalisation reference values
_MAX_PRECIP_REFERENCE = 100.0   # % (max possible)
_MAX_WIND_REFERENCE = 100.0     # km/h (strong gale — upper reference for normalisation)


# ---------------------------------------------------------------------------
# Score dataclass
# ---------------------------------------------------------------------------

@dataclass
class DepartureScore:
    departure_time: datetime
    total_score: float
    rain_component: float
    wind_component: float
    delay_component: float
    is_optimal: bool = False


# ---------------------------------------------------------------------------
# Per-departure weather evaluation
# ---------------------------------------------------------------------------

def _score_departure(
    departure: datetime,
    preferred: datetime,
    window_minutes: int,
    precip_pcts: list[float],
    wind_kmhs: list[float],
    w_r: float,
    w_w: float,
    w_d: float,
) -> DepartureScore:
    """
    Compute S(t) for a single candidate departure time.

    precip_pcts and wind_kmhs are the weather values at each waypoint
    for this specific departure time.
    """
    # R(t): mean precipitation probability across all waypoints, normalised 0–1
    r_t = (sum(precip_pcts) / len(precip_pcts)) / _MAX_PRECIP_REFERENCE if precip_pcts else 0.0

    # W(t): max wind speed, normalised 0–1
    w_t = (max(wind_kmhs) / _MAX_WIND_REFERENCE) if wind_kmhs else 0.0

    # D(t): absolute offset from preferred time, normalised by window size
    delta_minutes = abs((departure - preferred).total_seconds() / 60.0)
    d_t = delta_minutes / window_minutes  # 0 at preferred, 1 at ±window edge

    total = w_r * r_t + w_w * w_t + w_d * d_t

    return DepartureScore(
        departure_time=departure,
        total_score=round(total, 4),
        rain_component=round(w_r * r_t, 4),
        wind_component=round(w_w * w_t, 4),
        delay_component=round(w_d * d_t, 4),
    )


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

async def find_optimal_departure(
    preferred_departure: datetime,
    window_minutes: int,
    step_minutes: int,
    sampled_coords: list[tuple[float, float]],
    avg_speed_kmh: float,
    weather_fetcher,  # Callable: async (waypoints, etas) -> list[WaypointWeather]
    eta_calculator,   # Callable: (departure, cum_km, speed) -> datetime
    cumulative_kms: list[float],
) -> tuple[datetime, list[DepartureScore]]:
    """
    Slide the departure window and find the time that minimises S(t).

    Args:
        preferred_departure: Rider's preferred departure time.
        window_minutes:      Half-width of the search window.
        step_minutes:        Step size between candidate times.
        sampled_coords:      List of (lat, lon) sampled waypoints.
        avg_speed_kmh:       Rider's average speed.
        weather_fetcher:     Async function to fetch weather batch.
        eta_calculator:      Function to compute ETA from cumulative distance.
        cumulative_kms:      Cumulative km values for each sampled waypoint.

    Returns:
        (optimal_departure, all_scores)
        where all_scores is the full list for charting, sorted by departure time.
    """
    # Build list of candidate departure times
    candidates: list[datetime] = []
    t = preferred_departure - timedelta(minutes=window_minutes)
    end_t = preferred_departure + timedelta(minutes=window_minutes)

    while t <= end_t:
        candidates.append(t)
        t += timedelta(minutes=step_minutes)

    scores: list[DepartureScore] = []

    for candidate in candidates:
        # Compute ETAs for this departure time
        etas = [
            eta_calculator(candidate, cum_km, avg_speed_kmh)
            for cum_km in cumulative_kms
        ]

        # Fetch weather for all waypoints at their respective ETAs
        weather_results = await weather_fetcher(sampled_coords, etas)

        precip_pcts = [w.precip_pct for w in weather_results]
        wind_kmhs = [w.wind_kmh for w in weather_results]

        score = _score_departure(
            departure=candidate,
            preferred=preferred_departure,
            window_minutes=window_minutes,
            precip_pcts=precip_pcts,
            wind_kmhs=wind_kmhs,
            w_r=_WEIGHT_RAIN,
            w_w=_WEIGHT_WIND,
            w_d=_WEIGHT_DELAY,
        )
        scores.append(score)

    # Mark optimal
    optimal_score = min(scores, key=lambda s: s.total_score)
    optimal_score.is_optimal = True

    logger.debug(
        f"Optimal departure found: {optimal_score.departure_time} "
        f"with score {optimal_score.total_score:.4f} "
        f"(R:{optimal_score.rain_component:.4f}, W:{optimal_score.wind_component:.4f}, D:{optimal_score.delay_component:.4f})"
    )

    return optimal_score.departure_time, scores


def build_departure_reason(
    optimal: datetime,
    preferred: datetime,
    scores: list[DepartureScore],
) -> str:
    """
    Generate a deterministic human-readable explanation for the optimal departure.
    No LLMs — pure template logic.
    """
    opt_score = next(s for s in scores if s.is_optimal)
    delta_minutes = int((optimal - preferred).total_seconds() / 60)

    _TOLERANCE_MINUTES = 8
    if abs(delta_minutes) < _TOLERANCE_MINUTES:
        return f"Departing at your preferred time {optimal.strftime('%I:%M %p')} — no significant weather hazard detected on this window."

    direction = "later" if delta_minutes > 0 else "earlier"
    abs_delta = abs(delta_minutes)

    if opt_score.rain_component > opt_score.wind_component:
        reason_part = "to avoid a rain window along the route"
    else:
        reason_part = "to avoid elevated wind speeds along the route"

    return (
        f"Departing {abs_delta} min {direction} than planned "
        f"({optimal.strftime('%I:%M %p')}) {reason_part}. "
        f"Hazard score: {opt_score.total_score:.2f} "
        f"(rain {opt_score.rain_component:.2f} + wind {opt_score.wind_component:.2f} + delay {opt_score.delay_component:.2f})."
    )


def build_departure_advice(
    optimal: datetime,
    preferred: datetime,
    daylight_hours: float,
    night_hours: float,
    hazard_title: Optional[str] = None,
) -> dict:
    """Build high-level comparison between chosen time and optimal safety window."""
    pref_str = preferred.strftime("%I:%M %p")
    opt_str = optimal.strftime("%I:%M %p")
    is_opt = abs((optimal - preferred).total_seconds()) < 600

    selected_summary = f"{pref_str} • {daylight_hours:.1f}h Day / {night_hours:.1f}h Night"
    if hazard_title:
        selected_summary += f" • {hazard_title}"

    if night_hours > 4.0:
        golden_time = preferred.replace(hour=5, minute=30, second=0)
        if golden_time < preferred and (preferred - golden_time).total_seconds() > 43200:
            golden_time += timedelta(days=1)
        rec_str = golden_time.strftime("%I:%M %p (Next Morning)") if golden_time.date() > preferred.date() else "05:30 AM"
        recommended_summary = f"{rec_str} • 100% Daylight • Clear Road"
        tradeoff = (
            f"Your departure ({pref_str}) requires {night_hours:.1f}h of night driving on state highways. "
            f"Leaving at {rec_str} provides full daylight visibility and safer high-speed cruising."
        )
    else:
        rec_str = opt_str
        recommended_summary = f"{opt_str} • Best Weather Slot"
        if is_opt:
            tradeoff = f"Departing at {pref_str} is the optimal weather window with minimal precipitation along the highway."
        else:
            delta_min = int((optimal - preferred).total_seconds() / 60)
            direction = "later" if delta_min > 0 else "earlier"
            tradeoff = f"Shifting departure by {abs(delta_min)} min {direction} ({opt_str}) avoids peak rain along the route."

    return {
        "selected_time_str": pref_str,
        "recommended_time_str": rec_str,
        "is_optimal_selected": is_opt,
        "selected_summary": selected_summary,
        "recommended_summary": recommended_summary,
        "tradeoff_explanation": tradeoff,
    }


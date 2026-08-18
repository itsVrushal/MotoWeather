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
_WEIGHT_RAIN = float(os.getenv("WEIGHT_RAIN", "0.40"))
_WEIGHT_WIND = float(os.getenv("WEIGHT_WIND", "0.15"))
_WEIGHT_DELAY = float(os.getenv("WEIGHT_DELAY", "0.05"))

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
    traffic_component: float = 0.0
    is_optimal: bool = False


def _compute_traffic_penalty(dt: datetime) -> float:
    """Estimates rush hour city bottleneck penalty (0.0 to 1.0)."""
    hr = dt.hour + dt.minute / 60.0
    # Evening rush: 17:30 - 20:30
    if 17.5 <= hr <= 20.5:
        return 0.45
    # Morning rush: 08:30 - 10:30
    if 8.5 <= hr <= 10.5:
        return 0.35
    # Mid-day normal
    if 11.0 <= hr <= 17.0:
        return 0.15
    # Early morning / late night clear roads
    return 0.02


# ---------------------------------------------------------------------------
# Per-departure weather evaluation
# ---------------------------------------------------------------------------

def _score_departure(
    departure: datetime,
    preferred: datetime,
    window_minutes: int,
    precip_pcts: list[float],
    wind_kmhs: list[float],
    temps: list[float],
    etas: list[datetime],
    w_r: float,
    w_w: float,
    w_d: float,
) -> DepartureScore:
    """
    Compute S(t) for a single candidate departure time including weather, traffic, heat, & daylight.
    """
    r_t = (sum(precip_pcts) / len(precip_pcts)) / _MAX_PRECIP_REFERENCE if precip_pcts else 0.0
    w_t = (max(wind_kmhs) / _MAX_WIND_REFERENCE) if wind_kmhs else 0.0

    delta_minutes = abs((departure - preferred).total_seconds() / 60.0)
    d_t = delta_minutes / max(1, window_minutes)

    # Traffic penalty
    tr_penalty = _compute_traffic_penalty(departure)

    # Heat stress penalty (penalize scorching temps > 35°C)
    max_temp = max(temps) if temps else 25.0
    heat_penalty = max(0.0, (max_temp - 35.0) / 10.0) if max_temp > 35.0 else 0.0

    # Night riding risk (penalize riding after dark on unlit highways)
    night_count = sum(1 for e in etas if (e.hour + e.minute / 60.0 < 6.25 or e.hour + e.minute / 60.0 > 18.75))
    night_penalty = night_count / max(1, len(etas))

    w_tr = 0.15
    w_heat = 0.10
    w_night = 0.15

    total = (
        w_r * r_t
        + w_w * w_t
        + w_d * d_t
        + w_tr * tr_penalty
        + w_heat * heat_penalty
        + w_night * night_penalty
    )

    return DepartureScore(
        departure_time=departure,
        total_score=round(total, 4),
        rain_component=round(w_r * r_t, 4),
        wind_component=round(w_w * w_t, 4),
        delay_component=round(w_d * d_t, 4),
        traffic_component=round(w_tr * tr_penalty, 4),
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
    """
    candidates: list[datetime] = []
    t = preferred_departure - timedelta(minutes=window_minutes)
    end_t = preferred_departure + timedelta(minutes=window_minutes)

    while t <= end_t:
        candidates.append(t)
        t += timedelta(minutes=step_minutes)

    scores: list[DepartureScore] = []

    for candidate in candidates:
        etas = [
            eta_calculator(candidate, cum_km, avg_speed_kmh)
            for cum_km in cumulative_kms
        ]

        weather_results = await weather_fetcher(sampled_coords, etas)

        precip_pcts = [w.precip_pct for w in weather_results]
        wind_kmhs = [w.wind_kmh for w in weather_results]
        temps = [w.temp_c for w in weather_results]

        score = _score_departure(
            departure=candidate,
            preferred=preferred_departure,
            window_minutes=window_minutes,
            precip_pcts=precip_pcts,
            wind_kmhs=wind_kmhs,
            temps=temps,
            etas=etas,
            w_r=_WEIGHT_RAIN,
            w_w=_WEIGHT_WIND,
            w_d=_WEIGHT_DELAY,
        )
        scores.append(score)

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


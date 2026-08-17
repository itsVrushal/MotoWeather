"""
Pitstop Finite State Machine (FSM).

Evaluates sampled route waypoints in sequence to plan:
1. Fuel / EV Refill Stops: Triggered by vehicle range thresholds (tank_range_km - 40km).
2. Food & Chill Breaks: Timed breaks for family/friends every 2.5–3.5 hours (Breakfast, Lunch, Chai, Dinner).

No emergency shelter triggers (hotel suggestions removed).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Optional

from algorithms.haversine import SampledPoint


# ---------------------------------------------------------------------------
# Trigger types
# ---------------------------------------------------------------------------

class TriggerType(str, Enum):
    FUEL = "fuel"
    FOOD = "food"


@dataclass
class PitstopTrigger:
    """Represents a single pitstop lookup request emitted by the FSM."""
    trigger_type: TriggerType
    sub_type: str              # 'fuel', 'charging', 'breakfast', 'lunch', 'chai', 'dinner', 'break'
    search_lat: float          # Primary search coordinate
    search_lon: float
    at_waypoint_index: int
    eta: datetime
    vehicle_type: str = "petrol"
    route_dist_from_last_stop_km: float = 0.0
    search_corridor: list[tuple[float, float]] = field(default_factory=list) # Waypoints for corridor fallback


# ---------------------------------------------------------------------------
# FSM State
# ---------------------------------------------------------------------------

@dataclass
class FSMState:
    """Mutable state carried across waypoints."""
    dist_since_fuel: float = 0.0
    dist_since_food: float = 0.0
    last_food_wp_index: int = -10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_meal_sub_type(dt: datetime) -> str:
    """Determine meal/break type based on arrival ETA hour."""
    hr = dt.hour + dt.minute / 60.0
    if 6.5 <= hr <= 10.5:
        return "breakfast"
    elif 11.5 <= hr <= 15.5:
        return "lunch"
    elif 16.5 <= hr <= 19.5:
        return "chai"
    elif 19.5 <= hr <= 23.5:
        return "dinner"
    return "chai"


# ---------------------------------------------------------------------------
# FSM runner
# ---------------------------------------------------------------------------

_FUEL_BUFFER_KM = 35.0
_FOOD_INTERVAL_KM = 140.0  # Approx every 2.0 - 2.5 hrs at highway speeds


def run_fsm(
    waypoints: list[SampledPoint],
    etas: list[datetime],
    precip_pcts: list[float],
    tank_range_km: float,
    vehicle_type: str = "petrol",
    interval_km: float = 25.0,
) -> list[PitstopTrigger]:
    """
    Run the pitstop FSM over all sampled waypoints.
    """
    if not waypoints:
        return []

    state = FSMState()
    triggers: list[PitstopTrigger] = []
    fuel_trigger_km = max(60.0, tank_range_km - _FUEL_BUFFER_KM)
    total_route_km = waypoints[-1].cumulative_km if waypoints else 0.0

    for i, (wp, eta) in enumerate(zip(waypoints, etas)):
        # Skip origin waypoint for stops
        if i == 0:
            continue

        # Skip final destination waypoint (within last 30km)
        if total_route_km - wp.cumulative_km < 35.0:
            continue

        prev_cum = waypoints[i - 1].cumulative_km
        step_km = wp.cumulative_km - prev_cum
        state.dist_since_fuel += step_km
        state.dist_since_food += step_km

        # Build candidate corridor (current waypoint + next 3 waypoints + prev 1 waypoint)
        corridor = [(wp.lat, wp.lon)]
        for delta in [1, 2, -1, 3]:
            idx = i + delta
            if 0 <= idx < len(waypoints):
                corridor.append((waypoints[idx].lat, waypoints[idx].lon))

        # --- 1. FUEL / EV Trigger ---
        if state.dist_since_fuel >= fuel_trigger_km:
            sub = "charging" if vehicle_type == "ev" else "fuel"
            triggers.append(PitstopTrigger(
                trigger_type=TriggerType.FUEL,
                sub_type=sub,
                search_lat=wp.lat,
                search_lon=wp.lon,
                at_waypoint_index=i,
                eta=eta,
                vehicle_type=vehicle_type,
                route_dist_from_last_stop_km=state.dist_since_fuel,
                search_corridor=corridor,
            ))
            state.dist_since_fuel = 0.0

        # --- 2. FOOD & CHILL Break Trigger ---
        # Plan a break every ~175km (or approx 3 hours) and make sure at least 3 waypoints between breaks
        if state.dist_since_food >= _FOOD_INTERVAL_KM and (i - state.last_food_wp_index) >= 4:
            meal_type = _get_meal_sub_type(eta)
            triggers.append(PitstopTrigger(
                trigger_type=TriggerType.FOOD,
                sub_type=meal_type,
                search_lat=wp.lat,
                search_lon=wp.lon,
                at_waypoint_index=i,
                eta=eta,
                vehicle_type=vehicle_type,
                route_dist_from_last_stop_km=state.dist_since_food,
                search_corridor=corridor,
            ))
            state.dist_since_food = 0.0
            state.last_food_wp_index = i

    return triggers

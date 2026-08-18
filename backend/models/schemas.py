"""
Pydantic v2 request and response schemas for the Moto-Weather Router API.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PitstopType(str, Enum):
    FUEL = "fuel"
    FOOD = "food"
    SHELTER = "shelter"


class WeatherCode(int, Enum):
    """WMO weather interpretation codes (subset used for briefing)."""
    CLEAR = 0
    PARTLY_CLOUDY = 2
    OVERCAST = 3
    DRIZZLE = 51
    RAIN = 61
    HEAVY_RAIN = 65
    THUNDERSTORM = 95


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class RouteRequest(BaseModel):
    start_address: str = Field(..., examples=["Pune, Maharashtra"])
    end_address: str = Field(..., examples=["Nashik, Maharashtra"])
    # Pre-resolved coordinates from frontend autocomplete (bypasses backend geocoding)
    start_lat: Optional[float] = Field(default=None, description="Pre-resolved start latitude")
    start_lon: Optional[float] = Field(default=None, description="Pre-resolved start longitude")
    end_lat: Optional[float] = Field(default=None, description="Pre-resolved end latitude")
    end_lon: Optional[float] = Field(default=None, description="Pre-resolved end longitude")
    preferred_departure: datetime = Field(
        ..., description="Rider's preferred departure time (local IST)"
    )
    avg_speed_kmh: float = Field(default=60.0, ge=20.0, le=150.0)
    tank_range_km: float = Field(default=300.0, ge=50.0, le=800.0)
    window_minutes: int = Field(
        default=240,
        ge=15,
        le=720,
        description="Half-width of departure search window in minutes (±this value)",
    )
    window_step_minutes: int = Field(
        default=30, ge=5, le=60,
        description="Step size in minutes between candidate departure times",
    )
    pitstop_buffer_km: float = Field(
        default=5.0, ge=1.0, le=20.0,
        description="Max off-route distance (km) for pitstop suggestions",
    )

class PitstopRequest(BaseModel):
    waypoints: list[Waypoint]
    vehicle_type: str = Field(default="petrol", description="Vehicle type: 'petrol' or 'ev'")
    tank_range_km: float = Field(default=300.0, ge=50.0, le=800.0)
    pitstop_buffer_km: float = Field(
        default=15.0, ge=1.0, le=50.0,
        description="Max off-route distance (km) for pitstop suggestions",
    )


# ---------------------------------------------------------------------------
# Sub-models for response
# ---------------------------------------------------------------------------

class Coordinate(BaseModel):
    lat: float
    lon: float


class Waypoint(BaseModel):
    lat: float
    lon: float
    cumulative_km: float
    eta: datetime
    precip_pct: float = Field(description="Precipitation probability 0–100")
    wind_kmh: float
    temp_c: float
    weathercode: int
    traffic_level: Optional[str] = Field(default="low", description="'low', 'moderate', 'heavy', 'severe'")


class HazardScore(BaseModel):
    departure_time: datetime
    total_score: float
    rain_component: float
    wind_component: float
    delay_component: float
    traffic_component: Optional[float] = 0.0
    is_optimal: bool


class HighwaySegment(BaseModel):
    name: str
    distance_km: float
    pct: float


class DaylightSummary(BaseModel):
    daylight_hours: float
    night_hours: float
    daylight_pct: float
    night_pct: float
    sunset_time_str: Optional[str] = None
    advisory: str


class HazardSegment(BaseModel):
    title: str
    stretch_km: str
    hazard_type: str  # 'rain', 'wind', 'night', 'traffic', 'roadwork'
    severity: str     # 'low', 'moderate', 'high'
    description: str


class DepartureAdvice(BaseModel):
    selected_time_str: str
    recommended_time_str: str
    is_optimal_selected: bool
    selected_summary: str
    recommended_summary: str
    tradeoff_explanation: str


class Pitstop(BaseModel):
    type: PitstopType
    sub_type: Optional[str] = None  # e.g., 'charging', 'fuel', 'breakfast', 'lunch', 'chai', 'dinner'
    lat: float
    lon: float
    name: str
    dist_from_route_km: float
    route_dist_from_last_stop_km: float = Field(default=0.0)
    at_waypoint_index: int
    eta: datetime
    osm_id: Optional[int] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    open_now: Optional[bool] = None
    vicinity: Optional[str] = None


class Briefing(BaseModel):
    optimal_departure: datetime
    preferred_departure: Optional[datetime] = None
    departure_reason: str
    departure_advice: Optional[DepartureAdvice] = None
    max_wind_kmh: float
    max_wind_location: Optional[Coordinate] = None
    max_wind_eta: Optional[datetime] = None
    worst_rain_pct: float
    worst_rain_location: Optional[Coordinate] = None
    worst_rain_eta: Optional[datetime] = None
    pitstop_summary: list[str] = Field(default_factory=list)
    highways: list[HighwaySegment] = Field(default_factory=list)
    daylight: Optional[DaylightSummary] = None
    hazard_segments: list[HazardSegment] = Field(default_factory=list)
    traffic_summary: Optional[str] = None
    roadwork_alerts: list[str] = Field(default_factory=list)



# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class RouteResponse(BaseModel):
    optimal_departure: datetime
    total_distance_km: float
    estimated_duration_hours: float
    hazard_scores: list[HazardScore]
    waypoints: list[Waypoint]
    pitstops: list[Pitstop]
    briefing: Briefing
    geometry: list[Coordinate]


class PitstopResponse(BaseModel):
    pitstops: list[Pitstop]
    pitstop_summary: list[str]


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    detail: str
    code: str

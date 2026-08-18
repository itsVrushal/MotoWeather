/**
 * Route store — global reactive state for the Moto-Weather Router.
 * All components subscribe to this; no prop-drilling required.
 */
import { writable } from 'svelte/store';

/**
 * @typedef {Object} Coordinate
 * @property {number} lat
 * @property {number} lon
 */

/**
 * @typedef {Object} Waypoint
 * @property {number} lat
 * @property {number} lon
 * @property {number} cumulative_km
 * @property {string} eta              - ISO datetime string
 * @property {number} precip_pct       - 0–100
 * @property {number} wind_kmh
 * @property {number} temp_c
 * @property {number} weathercode
 * @property {string} [traffic_level]
 */

/**
 * @typedef {Object} HazardScore
 * @property {string} departure_time
 * @property {number} total_score
 * @property {number} rain_component
 * @property {number} wind_component
 * @property {number} delay_component
 * @property {number} [traffic_component]
 * @property {boolean} is_optimal
 */

/**
 * @typedef {Object} Pitstop
 * @property {string} type
 * @property {string} [sub_type]
 * @property {number} lat
 * @property {number} lon
 * @property {string} name
 * @property {number} dist_from_route_km
 * @property {number} route_dist_from_last_stop_km
 * @property {number} at_waypoint_index
 * @property {string} eta
 * @property {number} [rating]
 * @property {number} [user_ratings_total]
 * @property {boolean} [open_now]
 * @property {string} [vicinity]
 */

/**
 * @typedef {Object} Briefing
 * @property {string} optimal_departure
 * @property {string} [preferred_departure]
 * @property {string} departure_reason
 * @property {Object} [departure_advice]
 * @property {number} max_wind_kmh
 * @property {number} worst_rain_pct
 * @property {string|null} worst_rain_eta
 * @property {string[]} pitstop_summary
 * @property {Array} [highways]
 * @property {Object} [daylight]
 * @property {Array} [hazard_segments]
 * @property {string} [traffic_summary]
 * @property {Array} [roadwork_alerts]
 */

export const routeStore = writable({
  loading: false,
  error: null,
  optimal_departure: null,
  total_distance_km: 0,
  estimated_duration_hours: 0,
  hazard_scores: [],
  waypoints: [],
  pitstops: [],
  briefing: null,
  selected_departure: null,
  geometry: [],
  departure_cache: {},
  prefetch_loading: false,
  last_request: null,
  isFetchingPitstops: false,

  // Mode: 'planned' vs 'recommended'
  active_view_mode: 'planned',
  planned_data: null,
  recommended_data: null,
  is_fetching_recommended: false,
});

/** Reset to clean state */
export function resetRoute() {
  routeStore.set({
    loading: false,
    error: null,
    optimal_departure: null,
    total_distance_km: 0,
    estimated_duration_hours: 0,
    hazard_scores: [],
    waypoints: [],
    pitstops: [],
    briefing: null,
    selected_departure: null,
    geometry: [],
    departure_cache: {},
    prefetch_loading: false,
    last_request: null,
    isFetchingPitstops: false,
    active_view_mode: 'planned',
    planned_data: null,
    recommended_data: null,
    is_fetching_recommended: false,
  });
}

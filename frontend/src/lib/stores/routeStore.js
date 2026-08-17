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
 */

/**
 * @typedef {Object} HazardScore
 * @property {string} departure_time
 * @property {number} total_score
 * @property {number} rain_component
 * @property {number} wind_component
 * @property {number} delay_component
 * @property {boolean} is_optimal
 */

/**
 * @typedef {Object} Pitstop
 * @property {'fuel'|'food'|'shelter'} type
 * @property {number} lat
 * @property {number} lon
 * @property {string} name
 * @property {number} dist_from_route_km
 * @property {number} at_waypoint_index
 * @property {string} eta
 */

/**
 * @typedef {Object} Briefing
 * @property {string} optimal_departure
 * @property {string} departure_reason
 * @property {number} max_wind_kmh
 * @property {Coordinate|null} max_wind_location
 * @property {string|null} max_wind_eta
 * @property {number} worst_rain_pct
 * @property {Coordinate|null} worst_rain_location
 * @property {string|null} worst_rain_eta
 * @property {string[]} pitstop_summary
 */

/**
 * @typedef {Object} RouteState
 * @property {boolean} loading
 * @property {string|null} error
 * @property {string|null} optimal_departure
 * @property {number} total_distance_km
 * @property {number} estimated_duration_hours
 * @property {HazardScore[]} hazard_scores
 * @property {Waypoint[]} waypoints
 * @property {Pitstop[]} pitstops
 * @property {Briefing|null} briefing
 * @property {string|null} selected_departure  - manual override
 */

/** @type {import('svelte/store').Writable<RouteState>} */
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
  /** Map<isoString, RouteResponse> — cached results for each departure slot */
  departure_cache: {},
  /** true while background pre-fetch is running */
  prefetch_loading: false,
  /** last submitted payload — used by bar clicks and pre-fetcher */
  last_request: null,
  /** true while background pitstop fetch is running */
  isFetchingPitstops: false,
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
  });
}

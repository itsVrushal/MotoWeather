/**
 * API utility — thin fetch wrapper for the FastAPI backend.
 * Handles Planned vs. Recommended Route background synchronization with Local Browser Caching.
 */
import { routeStore } from '$lib/stores/routeStore.js';
import { get } from 'svelte/store';
import { getCache, setCache, getRouteCacheKey, saveRecentTrip, TTL } from '$lib/utils/cache.js';

const API_BASE = 'http://localhost:8000';

/**
 * Apply a route payload to the store.
 */
function applyRouteData(data, keepPitstops = false, keepScores = false) {
  routeStore.update(s => ({
    ...s,
    loading: false,
    error: null,
    optimal_departure: data.optimal_departure,
    total_distance_km: data.total_distance_km,
    estimated_duration_hours: data.estimated_duration_hours,
    hazard_scores: keepScores ? s.hazard_scores : (data.hazard_scores || s.hazard_scores),
    waypoints: data.waypoints,
    pitstops: keepPitstops ? s.pitstops : (data.pitstops || []),
    briefing: {
      ...data.briefing,
      pitstop_summary: keepPitstops ? (s.briefing?.pitstop_summary || []) : (data.briefing?.pitstop_summary || []),
    },
    selected_departure: data.selected_departure || data.briefing?.preferred_departure || data.optimal_departure,
    geometry: data.geometry,
  }));
}

/**
 * Switch view between 'planned' and 'recommended' route.
 * Swaps waypoints, weather layers, daylight, hazards, and pitstops cleanly.
 * @param {'planned'|'recommended'} mode
 */
export function switchViewMode(mode) {
  const st = get(routeStore);
  if (mode === 'planned' && st.planned_data) {
    routeStore.update(s => ({
      ...s,
      active_view_mode: 'planned',
      waypoints: st.planned_data.waypoints,
      pitstops: st.planned_data.pitstops || [],
      briefing: st.planned_data.briefing,
      selected_departure: st.planned_data.selected_departure || st.planned_data.briefing?.preferred_departure,
    }));
  } else if (mode === 'recommended' && st.recommended_data) {
    routeStore.update(s => ({
      ...s,
      active_view_mode: 'recommended',
      waypoints: st.recommended_data.waypoints,
      pitstops: st.recommended_data.pitstops || [],
      briefing: st.recommended_data.briefing,
      selected_departure: st.recommended_data.selected_departure || st.recommended_data.optimal_departure,
    }));
  }
}

/**
 * Submit a route request to the backend with Browser Cache Optimization.
 */
export async function fetchRoute(params) {
  const cacheKey = getRouteCacheKey(params);
  const cachedPlanned = getCache(cacheKey);

  // 1. Instant Cache Hit: Return immediately in 0ms!
  if (cachedPlanned) {
    cachedPlanned.selected_departure = params.preferred_departure;
    routeStore.update(s => ({
      ...s,
      loading: false,
      error: null,
      active_view_mode: 'planned',
      planned_data: cachedPlanned,
      departure_cache: { ...s.departure_cache, [params.preferred_departure]: cachedPlanned },
    }));
    applyRouteData(cachedPlanned, false, false);

    // Also check if recommended is cached
    if (cachedPlanned.optimal_departure) {
      const recKey = getRouteCacheKey({ ...params, preferred_departure: cachedPlanned.optimal_departure });
      const cachedRec = getCache(recKey);
      if (cachedRec) {
        cachedRec.selected_departure = cachedPlanned.optimal_departure;
        routeStore.update(s => ({ ...s, recommended_data: cachedRec }));
        fetchPitstops(cachedRec.waypoints, params.vehicle_type, params.tank_range_km, params.pitstop_buffer_km, 'recommended');
      } else {
        computeRecommendedRoute(cachedPlanned.optimal_departure, params);
      }
    }

    // Check pitstops cache for planned route
    fetchPitstops(cachedPlanned.waypoints, params.vehicle_type, params.tank_range_km, params.pitstop_buffer_km, 'planned');
    return cachedPlanned;
  }

  // 2. Cache Miss: Fetch from backend
  routeStore.update(s => ({
    ...s,
    loading: true,
    error: null,
    active_view_mode: 'planned',
    planned_data: null,
    recommended_data: null,
  }));

  try {
    const response = await fetch(`${API_BASE}/api/route`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    data.selected_departure = params.preferred_departure;

    // Cache in Browser localStorage
    setCache(cacheKey, data);
    saveRecentTrip({
      start: params.start_address,
      end: params.end_address,
      start_lat: params.start_lat,
      start_lon: params.start_lon,
      end_lat: params.end_lat,
      end_lon: params.end_lon,
    });

    // Save as planned data in store
    routeStore.update(s => ({
      ...s,
      planned_data: data,
      departure_cache: { ...s.departure_cache, [params.preferred_departure]: data },
    }));

    applyRouteData(data, false, false);

    // 1. Kick off pitstops for Planned Route in background
    fetchPitstops(data.waypoints, params.vehicle_type, params.tank_range_km, params.pitstop_buffer_km, 'planned');

    // 2. In background, compute the Recommended Route and its pitstops
    if (data.optimal_departure && data.optimal_departure !== params.preferred_departure) {
      computeRecommendedRoute(data.optimal_departure, params);
    } else {
      // If optimal matches planned, recommended is ready immediately
      routeStore.update(s => ({ ...s, recommended_data: data }));
    }

    return data;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    routeStore.update(s => ({ ...s, loading: false, error: message }));
    throw err;
  }
}

/**
 * Silently computes the Recommended Route in the background with Browser Cache.
 */
async function computeRecommendedRoute(optimalDepartureIso, baseParams) {
  const recPayload = { ...baseParams, preferred_departure: optimalDepartureIso };
  const recKey = getRouteCacheKey(recPayload);
  const cachedRec = getCache(recKey);

  if (cachedRec) {
    cachedRec.selected_departure = optimalDepartureIso;
    routeStore.update(s => ({
      ...s,
      recommended_data: cachedRec,
      is_fetching_recommended: false,
    }));
    fetchPitstops(cachedRec.waypoints, baseParams.vehicle_type, baseParams.tank_range_km, baseParams.pitstop_buffer_km, 'recommended');
    return;
  }

  routeStore.update(s => ({ ...s, is_fetching_recommended: true }));

  try {
    const res = await fetch(`${API_BASE}/api/route`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(recPayload),
    });

    if (res.ok) {
      const recData = await res.json();
      recData.selected_departure = optimalDepartureIso;

      setCache(recKey, recData);

      routeStore.update(s => ({
        ...s,
        recommended_data: recData,
        is_fetching_recommended: false,
        departure_cache: { ...s.departure_cache, [optimalDepartureIso]: recData },
      }));

      // Fetch pitstops for Recommended route in background
      fetchPitstops(
        recData.waypoints,
        baseParams.vehicle_type,
        baseParams.tank_range_km,
        baseParams.pitstop_buffer_km,
        'recommended'
      );
    } else {
      routeStore.update(s => ({ ...s, is_fetching_recommended: false }));
    }
  } catch {
    routeStore.update(s => ({ ...s, is_fetching_recommended: false }));
  }
}

/**
 * Background fetcher for pitstops with caching.
 */
export async function fetchPitstops(waypoints, vehicle_type, tank_range_km, pitstop_buffer_km, targetMode = 'planned') {
  if (!waypoints || waypoints.length === 0) return;

  const firstWp = waypoints[0];
  const lastWp = waypoints[waypoints.length - 1];
  const pitKey = `mw_pit_${firstWp.lat.toFixed(2)}_${firstWp.lon.toFixed(2)}_${lastWp.lat.toFixed(2)}_${vehicle_type}_${tank_range_km}_${firstWp.eta || ''}`;
  const cachedPit = getCache(pitKey, TTL.PITSTOPS);

  if (cachedPit) {
    applyPitstopsToStore(cachedPit, targetMode);
    return;
  }

  routeStore.update(s => ({ ...s, isFetchingPitstops: true }));

  try {
    const payload = {
      waypoints,
      vehicle_type,
      tank_range_km,
      pitstop_buffer_km,
    };
    const response = await fetch(`${API_BASE}/api/pitstops`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      const data = await response.json();
      setCache(pitKey, data);
      applyPitstopsToStore(data, targetMode);
    } else {
      routeStore.update(s => ({ ...s, isFetchingPitstops: false }));
    }
  } catch {
    routeStore.update(s => ({ ...s, isFetchingPitstops: false }));
  }
}

function applyPitstopsToStore(data, targetMode) {
  routeStore.update(s => {
    let updatedPlanned = s.planned_data;
    let updatedRecommended = s.recommended_data;

    if (targetMode === 'planned' && updatedPlanned) {
      updatedPlanned = {
        ...updatedPlanned,
        pitstops: data.pitstops,
        briefing: { ...updatedPlanned.briefing, pitstop_summary: data.pitstop_summary },
      };
    } else if (targetMode === 'recommended' && updatedRecommended) {
      updatedRecommended = {
        ...updatedRecommended,
        pitstops: data.pitstops,
        briefing: { ...updatedRecommended.briefing, pitstop_summary: data.pitstop_summary },
      };
    }

    const isCurrentView = s.active_view_mode === targetMode;

    return {
      ...s,
      planned_data: updatedPlanned,
      recommended_data: updatedRecommended,
      pitstops: isCurrentView ? data.pitstops : s.pitstops,
      briefing: isCurrentView
        ? { ...s.briefing, pitstop_summary: data.pitstop_summary }
        : s.briefing,
      isFetchingPitstops: false,
    };
  });
}

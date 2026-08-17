/**
 * API utility — thin fetch wrapper for the FastAPI backend.
 * Handles loading/error state updates to the routeStore.
 */
import { routeStore } from '$lib/stores/routeStore.js';
import { get } from 'svelte/store';

const API_BASE = 'http://localhost:8000';

/**
 * Apply a route response payload to the store.
 * @param {Object} data - RouteResponse from backend
 */
function applyRouteData(data, keepPitstops = false, keepScores = false) {
  routeStore.update(s => ({
    ...s,
    loading: false,
    error: null,
    optimal_departure: data.optimal_departure,
    total_distance_km: data.total_distance_km,
    estimated_duration_hours: data.estimated_duration_hours,
    hazard_scores: keepScores ? s.hazard_scores : data.hazard_scores,
    waypoints: data.waypoints,
    pitstops: keepPitstops ? s.pitstops : data.pitstops,
    briefing: {
      ...data.briefing,
      pitstop_summary: keepPitstops ? (s.briefing?.pitstop_summary || []) : data.briefing.pitstop_summary,
    },
    selected_departure: data.optimal_departure,
    geometry: data.geometry,
  }));
}

/**
 * Submit a route request to the backend.
 * After the initial fetch, silently pre-fetches all other departure slots.
 * @param {boolean} keepScores - prevent overwriting hazard_scores
 */
export async function fetchRoute(params, keepPitstops = false, keepScores = false) {
  routeStore.update(s => ({ ...s, loading: true, error: null }));

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

    // Cache this result keyed by departure time
    const cacheKey = params.preferred_departure;
    routeStore.update(s => ({
      ...s,
      departure_cache: { ...s.departure_cache, [cacheKey]: data },
    }));

    applyRouteData(data, keepPitstops, keepScores);

    // After initial fetch succeeds, kick off background pre-fetching for all other slots
    prefetchAllSlots(data, params);

    return data;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    routeStore.update(s => ({ ...s, loading: false, error: message }));
    throw err;
  }
}

/**
 * Switch the displayed route to a different departure time slot.
 * Uses cache if available; otherwise fetches fresh.
 *
 * @param {string} departureIso - ISO 8601 departure time string
 */
export async function selectDeparture(departureIso) {
  const st = get(routeStore);
  
  // Cache hit — instant!
  if (st.departure_cache[departureIso]) {
    applyRouteData(st.departure_cache[departureIso], true, true);
    routeStore.update(s => ({ ...s, selected_departure: departureIso }));
    return;
  }

  // Cache miss — fetch on demand
  if (!st.last_request) return;
  const newPayload = { ...st.last_request, preferred_departure: departureIso };
  routeStore.update(s => ({ ...s, last_request: newPayload }));
  await fetchRoute(newPayload, true, true);
}

/**
 * Background pre-fetcher: silently fetches all departure slots from the hazard_scores list.
 * Results are stored in departure_cache so bar clicks are instant.
 *
 * @param {Object} initialData - The initial route response (already has hazard_scores list)
 * @param {Object} baseParams - The original request payload
 */
async function prefetchAllSlots(initialData, baseParams) {
  const scores = initialData.hazard_scores || [];
  if (scores.length < 2) return;

  routeStore.update(s => ({ ...s, prefetch_loading: true }));

  const initialKey = baseParams.preferred_departure;

  for (const score of scores) {
    const depTime = score.departure_time;
    // Skip already-cached entries and apply small delay to not hammer the server
    if (depTime === initialKey) continue;
    const st = get(routeStore);
    if (st.departure_cache[depTime]) continue;

    try {
      const payload = { ...baseParams, preferred_departure: depTime };
      const res = await fetch(`${API_BASE}/api/route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        routeStore.update(s => ({
          ...s,
          departure_cache: { ...s.departure_cache, [depTime]: data },
        }));
      }
    } catch {
      // Soft fail — non-critical background fetch
    }

    // Small delay between requests to not overwhelm the backend
    await new Promise(r => setTimeout(r, 500));
  }

  routeStore.update(s => ({ ...s, prefetch_loading: false }));
}

/**
 * Background fetcher for pitstops.
 */
export async function fetchPitstops(waypoints, vehicle_type, tank_range_km, pitstop_buffer_km) {
  routeStore.update(s => ({ ...s, isFetchingPitstops: true }));
  try {
    const payload = {
      waypoints,
      vehicle_type,
      tank_range_km,
      pitstop_buffer_km
    };
    const response = await fetch(`${API_BASE}/api/pitstops`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      const data = await response.json();
      routeStore.update(s => {
        // Also merge pitstops into departure_cache for the currently selected departure
        // so that clicking around doesn't clear pitstops if they were loaded for it.
        const st = get(routeStore);
        const currentDep = s.selected_departure || s.optimal_departure;
        
        let newCache = { ...s.departure_cache };
        if (newCache[currentDep]) {
          newCache[currentDep] = {
            ...newCache[currentDep],
            pitstops: data.pitstops,
            briefing: {
              ...newCache[currentDep].briefing,
              pitstop_summary: data.pitstop_summary
            }
          };
        }

        return {
          ...s,
          pitstops: data.pitstops,
          briefing: {
            ...s.briefing,
            pitstop_summary: data.pitstop_summary
          },
          departure_cache: newCache,
          isFetchingPitstops: false
        };
      });
    } else {
      routeStore.update(s => ({ ...s, isFetchingPitstops: false }));
    }
  } catch (err) {
    routeStore.update(s => ({ ...s, isFetchingPitstops: false }));
  }
}

/** Check if the backend is reachable */
export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

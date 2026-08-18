<script>
  import { onMount } from 'svelte';
  import { routeStore } from '$lib/stores/routeStore.js';
  import { fetchRoute, fetchPitstops } from '$lib/utils/api.js';
  import { getGeocodeCache, setGeocodeCache, getRecentTrips } from '$lib/utils/cache.js';

  // --- State ---
  let startAddress   = '';
  let endAddress     = '';
  let preferredDate  = getDefaultDate();
  let preferredTime  = getDefaultTime();
  let avgSpeed       = 60;
  let tankRange      = 300;
  let windowMin      = 240;
  let submitting     = false;
  let formError      = '';
  let showAdvanced   = false;
  let vehicleType    = 'petrol'; // 'petrol' or 'ev'
  let recentTrips    = [];

  // Resolved coordinates from autocomplete (avoids re-geocoding)
  let startCoord = null; // { lat, lon }
  let endCoord   = null;

  // Autocomplete state
  let startSuggestions = [];
  let endSuggestions   = [];
  let showStartDrop    = false;
  let showEndDrop      = false;
  let startTimer, endTimer;

  onMount(() => {
    recentTrips = getRecentTrips();
  });

  function pickRecent(t) {
    startAddress = t.start;
    endAddress = t.end;
    startCoord = (t.start_lat && t.start_lon) ? { lat: t.start_lat, lon: t.start_lon } : null;
    endCoord = (t.end_lat && t.end_lon) ? { lat: t.end_lat, lon: t.end_lon } : null;
  }

  function getDefaultDate() {
    const d = new Date();
    const p = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`;
  }

  function getDefaultTime() {
    const d = new Date();
    const p = n => String(n).padStart(2, '0');
    return `${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  // --- Nominatim autocomplete ---
  // Maharashtra viewbox: SW lon,lat to NE lon,lat
  const MH_VIEWBOX = '72.6,15.6,80.9,22.1';

  // Type → icon mapping for autocomplete
  const TYPE_ICONS = {
    city: '🏙️', town: '🏘️', village: '🏡', hamlet: '🏠',
    suburb: '📍', neighbourhood: '📍',
    fuel: '⛽', charging_station: '⚡',
    restaurant: '🍽️', cafe: '☕', hotel: '🏨',
    park: '🌳', forest: '🌲', beach: '🏖️', mountain: '⛰️',
    temple: '🛕', mosque: '🕌', church: '⛪',
    administrative: '🗺️', road: '🛣️', motorway: '🛣️',
  };

  function getIcon(type) {
    return TYPE_ICONS[type] || '📍';
  }

  async function fetchSuggestions(query) {
    if (!query || query.length < 2) return [];

    // 1. Check client-side browser cache (instant 0ms)
    const cached = getGeocodeCache(query);
    if (cached) return cached;

    try {
      const res = await fetch(`http://localhost:8000/api/geocode?q=${encodeURIComponent(query)}`);
      if (!res.ok) return [];
      const data = await res.json();
      const results = data.results || [];

      const formatted = results.map(r => ({
        short: r.name.split(',').slice(0, 3).join(', ').trim() || r.name,
        full:  r.name,
        lat:   parseFloat(r.lat),
        lon:   parseFloat(r.lon),
        type:  'city',
        icon:  '📍',
        subtype: r.provider || '',
      }));

      setGeocodeCache(query, formatted);
      return formatted;
    } catch { return []; }
  }

  function onStartInput(e) {
    clearTimeout(startTimer);
    startCoord = null; // user typed manually — clear resolved coord
    const v = e.target.value;
    if (v.length < 3) { startSuggestions = []; showStartDrop = false; return; }
    startTimer = setTimeout(async () => {
      startSuggestions = await fetchSuggestions(v);
      showStartDrop = startSuggestions.length > 0;
    }, 300);
  }

  function onEndInput(e) {
    clearTimeout(endTimer);
    endCoord = null; // user typed manually — clear resolved coord
    const v = e.target.value;
    if (v.length < 3) { endSuggestions = []; showEndDrop = false; return; }
    endTimer = setTimeout(async () => {
      endSuggestions = await fetchSuggestions(v);
      showEndDrop = endSuggestions.length > 0;
    }, 300);
  }

  function pickStart(s) {
    startAddress  = s.short;
    startCoord    = { lat: s.lat, lon: s.lon };
    showStartDrop = false;
    startSuggestions = [];
  }

  function pickEnd(s) {
    endAddress  = s.short;
    endCoord    = { lat: s.lat, lon: s.lon };
    showEndDrop = false;
    endSuggestions = [];
  }

  // --- Submit ---
  async function handleSubmit() {
    formError = '';
    if (!startAddress.trim() || !endAddress.trim()) {
      formError = 'Enter both start and destination.';
      return;
    }
    submitting = true;
    try {
      const payload = {
        start_address: startAddress,
        end_address:   endAddress,
        preferred_departure: `${preferredDate}T${preferredTime}:00`,
        avg_speed_kmh: avgSpeed,
        tank_range_km: tankRange,
        window_minutes: windowMin,
        window_step_minutes: 15,
        pitstop_buffer_km: 3.0,
        vehicle_type: vehicleType,
      };
      // Pass resolved coordinates to avoid backend re-geocoding ambiguity
      if (startCoord) { payload.start_lat = startCoord.lat; payload.start_lon = startCoord.lon; }
      if (endCoord)   { payload.end_lat   = endCoord.lat;   payload.end_lon   = endCoord.lon; }

      routeStore.update(st => ({ ...st, last_request: payload }));
      const routeData = await fetchRoute(payload);
      
      // Fetch pitstops in the background without awaiting it
      if (routeData && routeData.waypoints) {
        fetchPitstops(routeData.waypoints, payload.vehicle_type, payload.tank_range_km, payload.pitstop_buffer_km);
      }
    } catch (err) {
      formError = err.message ?? 'Request failed.';
    } finally {
      submitting = false;
    }
  }
</script>

<div class="gm-panel card slide-in">
  <!-- Header -->
  <div class="gm-header">
    <div>
      <div class="gm-title">Moto-Weather</div>
      <div class="gm-sub">Maharashtra Ride Planner</div>
    </div>
  </div>

  <form on:submit|preventDefault={handleSubmit} autocomplete="off">

    <!-- Search inputs -->
    <div class="search-stack">
      <!-- Start -->
      <div class="search-field">
        <div class="pin-dot green"></div>
        <div class="search-wrap">
          <input
            id="start"
            class="gm-input"
            type="text"
            placeholder="From — Starting point"
            bind:value={startAddress}
            on:input={onStartInput}
            on:focus={() => { if (startSuggestions.length) showStartDrop = true; }}
            on:blur={() => setTimeout(() => showStartDrop = false, 160)}
          />
          {#if showStartDrop}
            <div class="suggest-drop">
              {#each startSuggestions as s}
                <button type="button" class="suggest-item"
                  on:mousedown|preventDefault={() => pickStart(s)}>
                  <span class="suggest-icon">{s.icon}</span>
                  <div class="suggest-content">
                    <span class="suggest-text">{s.short}</span>
                    {#if s.subtype}<span class="suggest-sub">{s.subtype}</span>{/if}
                  </div>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <div class="route-connector">
        <div class="connector-line"></div>
        <button type="button" class="swap-btn" title="Swap" on:click={() => { const t = startAddress; startAddress = endAddress; endAddress = t; }}>
          ⇅
        </button>
      </div>

      <!-- End -->
      <div class="search-field">
        <div class="pin-dot red"></div>
        <div class="search-wrap">
          <input
            id="dest"
            class="gm-input"
            type="text"
            placeholder="To — Destination"
            bind:value={endAddress}
            on:input={onEndInput}
            on:focus={() => { if (endSuggestions.length) showEndDrop = true; }}
            on:blur={() => setTimeout(() => showEndDrop = false, 160)}
          />
          {#if showEndDrop}
            <div class="suggest-drop">
              {#each endSuggestions as s}
                <button type="button" class="suggest-item"
                  on:mousedown|preventDefault={() => pickEnd(s)}>
                  <span class="suggest-icon">{s.icon}</span>
                  <div class="suggest-content">
                    <span class="suggest-text">{s.short}</span>
                    {#if s.subtype}<span class="suggest-sub">{s.subtype}</span>{/if}
                  </div>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      </div>
    </div>

    <!-- Quick Recent Routes -->
    {#if recentTrips && recentTrips.length > 0}
      <div class="recent-trips-row">
        <span class="recent-label">⚡ Recent:</span>
        <div class="recent-chips">
          {#each recentTrips.slice(0, 3) as trip}
            <button
              type="button"
              class="recent-chip"
              on:click={() => pickRecent(trip)}
              title="{trip.start} ➔ {trip.end}"
            >
              {trip.start.split(',')[0]} ➔ {trip.end.split(',')[0]}
            </button>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Time row -->
    <div class="time-row">
      <span class="time-label">🕐 Depart</span>
      <div class="time-input date-input" role="button" tabindex="0"
        on:click={() => document.getElementById('dep-date').showPicker?.() ?? document.getElementById('dep-date').focus()}
        on:keydown={(e) => e.key === 'Enter' && (document.getElementById('dep-date').showPicker?.() ?? document.getElementById('dep-date').focus())}>
        <input id="dep-date" type="date" bind:value={preferredDate} required />
      </div>
      <div class="time-input" role="button" tabindex="0"
        on:click={() => document.getElementById('dep-time').showPicker?.() ?? document.getElementById('dep-time').focus()}
        on:keydown={(e) => e.key === 'Enter' && (document.getElementById('dep-time').showPicker?.() ?? document.getElementById('dep-time').focus())}>
        <input id="dep-time" type="time" bind:value={preferredTime} required />
      </div>
    </div>

    <!-- Rider settings -->
    <div class="advanced-grid fade-in">
        <label class="adv-label adv-full">
          <span>Vehicle Type</span>
          <div class="vehicle-toggle">
            <button type="button" class="veh-btn {vehicleType === 'petrol' ? 'active' : ''}" on:click={() => vehicleType = 'petrol'}>⛽ Petrol</button>
            <button type="button" class="veh-btn {vehicleType === 'ev' ? 'active' : ''}" on:click={() => vehicleType = 'ev'}>⚡ EV</button>
          </div>
        </label>
        <label class="adv-label">
          <span>Speed</span>
          <div class="adv-input-wrap">
            <input class="gm-input adv-input" type="number" min="20" max="150" bind:value={avgSpeed} />
            <span class="adv-unit">km/h</span>
          </div>
        </label>
        <label class="adv-label">
          <span>Tank</span>
          <div class="adv-input-wrap">
            <input class="gm-input adv-input" type="number" min="50" max="800" bind:value={tankRange} />
            <span class="adv-unit">km</span>
          </div>
        </label>
        <label class="adv-label adv-full">
          <span>Optimization Window ±{(windowMin / 60).toFixed(1)} hrs ({windowMin} min)</span>
          <input class="form-range" type="range" min="60" max="360" step="30" bind:value={windowMin} />
        </label>
      </div>
    <!-- Error -->
    {#if formError || $routeStore.error}
      <div class="gm-error">⚠️ {formError || $routeStore.error}</div>
    {/if}

    <!-- Submit -->
    <button
      class="plan-btn"
      type="submit"
      disabled={submitting || $routeStore.loading}
    >
      {#if submitting || $routeStore.loading}
        <span class="pulse-dot"></span> Calculating…
      {:else}
        🧭 Plan My Ride
      {/if}
    </button>

  </form>
</div>

<style>
  .gm-panel {
    width: 340px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-radius: var(--radius-lg);
  }

  @keyframes slideIn {
    from { opacity: 0; transform: translateX(-16px); }
    to   { opacity: 1; transform: translateX(0); }
  }

  .slide-in {
    animation: slideIn 0.3s ease forwards;
  }

  .gm-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding-bottom: 2px;
  }


  .gm-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
  }

  .gm-sub {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }

  /* Search stack */
  .search-stack {
    display: flex;
    flex-direction: column;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    overflow: visible;
    position: relative;
  }

  .search-field {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 2px 10px;
    position: relative;
  }

  .pin-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .pin-dot.green { background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,0.5); }
  .pin-dot.red   { background: #ef4444; box-shadow: 0 0 6px rgba(239,68,68,0.5); }

  .search-wrap {
    flex: 1;
    position: relative;
  }

  .gm-input {
    width: 100%;
    padding: 6px 0;
    background: transparent;
    border: none;
    border-bottom: 1px solid transparent;
    color: var(--text-primary);
    font-family: var(--font-ui);
    font-size: 13px;
    outline: none;
    transition: border-color 0.15s;
  }

  .gm-input:focus {
    border-bottom-color: var(--accent-orange);
  }

  .gm-input::placeholder { color: var(--text-muted); }

  /* Quick Recent Trips */
  .recent-trips-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 4px;
    margin-bottom: 2px;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .recent-label {
    font-size: 10px;
    font-weight: 700;
    color: var(--text-muted);
    white-space: nowrap;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .recent-chips {
    display: flex;
    gap: 4px;
  }

  .recent-chip {
    font-size: 10px;
    font-weight: 700;
    color: #475569;
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 99px;
    padding: 2px 8px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s ease;
  }

  .recent-chip:hover {
    background: #ffffff;
    border-color: rgba(249, 115, 22, 0.4);
    color: #ea580c;
  }

  /* Autocomplete dropdown */
  .suggest-drop {
    position: absolute;
    top: calc(100% + 4px);
    left: -22px;
    right: 0;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 10px;
    z-index: 100;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    display: flex;
    flex-direction: column;
  }

  .suggest-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 12px;
    background: none;
    border: none;
    color: var(--text-primary);
    font-size: 12px;
    font-family: var(--font-ui);
    cursor: pointer;
    text-align: left;
    transition: background 0.12s;
    border-bottom: 1px solid var(--border);
  }

  .suggest-item:last-child { border-bottom: none; }
  .suggest-item:hover { background: rgba(255,255,255,0.05); }

  .suggest-icon { font-size: 14px; flex-shrink: 0; }
  .suggest-content { display: flex; flex-direction: column; overflow: hidden; }
  .suggest-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
  .suggest-sub { font-size: 10px; color: var(--text-muted); text-transform: capitalize; margin-top: 1px; }

  /* Connector */
  .route-connector {
    display: flex;
    align-items: center;
    padding: 0 10px;
    height: 20px;
    position: relative;
  }

  .connector-line {
    position: absolute;
    left: 16px;
    width: 1px;
    height: 100%;
    background: var(--border);
  }

  .swap-btn {
    margin-left: auto;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 50%;
    width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 13px;
    z-index: 1;
    transition: all 0.15s;
  }

  .swap-btn:hover { color: var(--text-primary); background: var(--bg-surface); }

  /* Time row */
  .time-row {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 4px 10px;
  }

  .time-label {
    font-size: 12px;
    color: var(--text-muted);
    white-space: nowrap;
    margin-right: 4px;
  }

  /* Each time/date slot is a label that fills the whole hit target */
  .time-input {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    padding: 3px 4px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: #fff;
    cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .time-input:hover {
    border-color: var(--accent-orange);
  }

  .time-input:focus-within {
    border-color: var(--accent-orange);
    box-shadow: 0 0 0 2px rgba(249, 115, 22, 0.15);
  }

  .time-input input {
    width: 100%;
    background: transparent;
    border: none;
    outline: none;
    font-size: 12px;
    font-family: var(--font-ui);
    color: var(--text-primary);
    cursor: pointer;
    padding: 1px 0;
  }

  /* Remove the browser's default calendar/clock icon color */
  .time-input input::-webkit-calendar-picker-indicator {
    opacity: 0.5;
    cursor: pointer;
    filter: invert(0.4) sepia(1) saturate(4) hue-rotate(340deg);
  }

  /* Give date input enough room for full yyyy-mm-dd */
  .date-input { min-width: 108px; flex: 1.6; color-scheme: light; }

  /* Advanced settings */
  .advanced-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 12px;
    font-family: var(--font-ui);
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 6px;
    transition: color 0.15s;
    width: 100%;
  }

  .advanced-toggle:hover { color: var(--text-secondary); }

  .toggle-arrow {
    display: inline-block;
    transition: transform 0.2s;
    font-size: 16px;
  }

  .toggle-arrow.open { transform: rotate(90deg); }

  .advanced-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .adv-full { grid-column: 1 / -1; }

  .adv-label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .adv-input-wrap {
    position: relative;
  }

  .adv-input {
    padding-right: 36px !important;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
    padding: 5px 8px;
  }

  .adv-unit {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 10px;
    color: var(--text-muted);
    pointer-events: none;
  }

  /* Error */
  .gm-error {
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.2);
    border-radius: var(--radius-sm);
    padding: 8px 12px;
    font-size: 12px;
    color: var(--critical);
  }

  /* Plan button */
  .plan-btn {
    width: 100%;
    padding: 11px;
    background: var(--accent-orange);
    color: #fff;
    font-size: 13px;
    font-weight: 700;
    font-family: var(--font-ui);
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    letter-spacing: 0.02em;
    transition: background 0.15s, box-shadow 0.15s, transform 0.1s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 2px;
  }

  .plan-btn:hover:not(:disabled) {
    background: #ea6c0d;
    box-shadow: 0 4px 20px rgba(249,115,22,0.35);
    transform: translateY(-1px);
  }

  .plan-btn:disabled { opacity: 0.65; cursor: not-allowed; transform: none; }

  /* Vehicle Toggle */
  .vehicle-toggle {
    display: flex;
    background: var(--bg-alt);
    border: 1px solid var(--border-light);
    border-radius: 6px;
    padding: 2px;
    margin-top: 4px;
  }
  .veh-btn {
    flex: 1;
    background: none;
    border: none;
    padding: 6px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .veh-btn:hover {
    color: var(--text-primary);
  }
  .veh-btn.active {
    background: #fff;
    color: var(--accent-orange);
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }
</style>
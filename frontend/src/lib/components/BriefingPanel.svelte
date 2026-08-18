<script>
  import { routeStore } from '$lib/stores/routeStore.js';
  import { switchViewMode } from '$lib/utils/api.js';

  // Collapsible section states
  let openDaylight = true;
  let openMilestones = true;
  let openHighways = true;

  $: isRecommended = $routeStore.active_view_mode === 'recommended';
  $: activeData = (isRecommended && $routeStore.recommended_data) ? $routeStore.recommended_data : ($routeStore.planned_data || $routeStore);
  $: briefing   = activeData.briefing || $routeStore.briefing;
  $: distance   = activeData.total_distance_km || $routeStore.total_distance_km;
  $: duration   = activeData.estimated_duration_hours || $routeStore.estimated_duration_hours;
  $: displayDep = isRecommended
    ? (activeData.selected_departure || activeData.optimal_departure || briefing?.optimal_departure)
    : ($routeStore.planned_data?.selected_departure || briefing?.preferred_departure || activeData.optimal_departure);
  $: pitstops   = (activeData.pitstops && activeData.pitstops.length > 0)
    ? activeData.pitstops
    : ($routeStore.pitstops && $routeStore.pitstops.length > 0 ? $routeStore.pitstops : ($routeStore.planned_data?.pitstops || []));

  function fmtTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
  }

  function fmtDuration(h) {
    if (!h) return '—';
    const hr = Math.floor(h);
    const mn = Math.round((h - hr) * 60);
    return mn > 0 ? `${hr}h ${mn}m` : `${hr}h`;
  }

  function getStopBadge(ps) {
    const sub = (ps.sub_type || ps.type || '').toLowerCase();
    
    // Combined Fuel/EV + Meal stops
    if (sub.includes('charging') && sub.includes('dinner')) {
      return { emoji: '⚡🍽️', label: 'EV Charge + Dinner', color: '#2563eb', bg: 'rgba(37,99,235,0.12)' };
    }
    if (sub.includes('fuel') && sub.includes('dinner')) {
      return { emoji: '⛽🍽️', label: 'Fuel Refill + Dinner', color: '#ea580c', bg: 'rgba(234,88,12,0.12)' };
    }
    if (sub.includes('charging') && sub.includes('lunch')) {
      return { emoji: '⚡🍽️', label: 'EV Charge + Lunch', color: '#2563eb', bg: 'rgba(37,99,235,0.12)' };
    }
    if (sub.includes('fuel') && sub.includes('lunch')) {
      return { emoji: '⛽🍽️', label: 'Fuel Refill + Lunch', color: '#ea580c', bg: 'rgba(234,88,12,0.12)' };
    }
    if (sub.includes('charging') && (sub.includes('chai') || sub.includes('breakfast'))) {
      return { emoji: '⚡☕', label: 'EV Charge + Break', color: '#2563eb', bg: 'rgba(37,99,235,0.12)' };
    }
    if (sub.includes('fuel') && (sub.includes('chai') || sub.includes('breakfast'))) {
      return { emoji: '⛽☕', label: 'Fuel + Chai Break', color: '#ea580c', bg: 'rgba(234,88,12,0.12)' };
    }

    // Single stops
    if (sub === 'charging' || (ps.type === 'fuel' && $routeStore.last_request?.vehicle_type === 'ev')) {
      return { emoji: '⚡', label: 'EV Fast Charger', color: '#2563eb', bg: 'rgba(37,99,235,0.12)' };
    }
    if (sub === 'fuel' || ps.type === 'fuel') {
      return { emoji: '⛽', label: 'Fuel Plaza', color: '#ea580c', bg: 'rgba(234,88,12,0.12)' };
    }
    if (sub === 'breakfast' || sub === 'chai') {
      return { emoji: '☕', label: sub === 'breakfast' ? 'Breakfast' : 'Chai & Snacks', color: '#d97706', bg: 'rgba(217,119,6,0.12)' };
    }
    if (sub === 'lunch' || sub === 'dinner') {
      return { emoji: '🍽️', label: sub === 'lunch' ? 'Family Lunch / Dhaba' : 'Dinner Stop', color: '#dc2626', bg: 'rgba(220,38,38,0.12)' };
    }
    return { emoji: '📍', label: 'Highway Rest Stop', color: '#059669', bg: 'rgba(5,150,105,0.12)' };
  }
</script>

{#if briefing}
  <div class="results-panel fade-in">

    <!-- ────────── VIEW MODE SWITCHER (PLANNED VS RECOMMENDED) ────────── -->
    <div class="view-mode-toggle glass-panel">
      <button
        type="button"
        class="mode-btn"
        class:active={!isRecommended}
        on:click={() => switchViewMode('planned')}
        title="View route conditions for your entered departure time"
      >
        <span class="mode-icon">📍</span>
        <div class="mode-text-box">
          <span class="mode-title">My Plan</span>
          <span class="mode-sub">{fmtTime($routeStore.planned_data?.selected_departure || briefing.preferred_departure || displayDep)}</span>
        </div>
      </button>

      <button
        type="button"
        class="mode-btn rec-btn"
        class:active={isRecommended}
        on:click={() => switchViewMode('recommended')}
        title="View optimal departure with best weather, daylight, and traffic"
      >
        <span class="mode-icon">✨</span>
        <div class="mode-text-box">
          <span class="mode-title">Best Time</span>
          {#if $routeStore.is_fetching_recommended}
            <span class="mode-sub pulse-text">Optimizing...</span>
          {:else}
            <span class="mode-sub">{fmtTime($routeStore.recommended_data?.optimal_departure || briefing.optimal_departure)}</span>
          {/if}
        </div>
      </button>
    </div>

    <!-- ────────── HERO DEPARTURE CARD ────────── -->
    <div class="hero-card card glass-panel">
      <div class="hero-badge-row">
        <span class="hero-label">
          {!isRecommended ? '📍 Planned Departure' : '✨ Recommended Golden Window'}
        </span>
        {#if briefing.traffic_summary}
          <span class="hero-traffic-chip">🚦 Live Traffic Checked</span>
        {/if}
      </div>
      <div class="hero-time font-data">{fmtTime(displayDep)}</div>
      <div class="hero-stats">
        <div class="hero-stat">
          <span class="hero-stat-val font-data">{distance.toFixed(0)}</span>
          <span class="hero-stat-unit">km</span>
        </div>
        <div class="hero-divider"></div>
        <div class="hero-stat">
          <span class="hero-stat-val font-data">{fmtDuration(duration)}</span>
          <span class="hero-stat-unit">drive</span>
        </div>
      </div>
      {#if briefing.departure_reason}
        <div class="hero-reason">
          {#if !isRecommended && briefing.preferred_departure && briefing.optimal_departure && briefing.preferred_departure !== briefing.optimal_departure}
            <span>Your entered departure. Click <strong>✨ Best Time</strong> above for optimal conditions.</span>
          {:else}
            <span>{briefing.departure_reason}</span>
          {/if}
        </div>
      {/if}
    </div>

    <!-- ────────── PALETTE GLASS WEATHER TILES (RESPONSIVE GRID) ────────── -->
    <div class="weather-palette-row">
      <div class="palette-tile rain-tile">
        <span class="tile-icon">🌧️</span>
        <div class="tile-data">
          <div class="tile-value font-data">{briefing.worst_rain_pct.toFixed(0)}%</div>
          <div class="tile-label">Peak Rain</div>
        </div>
      </div>
      <div class="palette-tile wind-tile">
        <span class="tile-icon">💨</span>
        <div class="tile-data">
          <div class="tile-value font-data">{briefing.max_wind_kmh.toFixed(0)}</div>
          <div class="tile-label">km/h Wind</div>
        </div>
      </div>
      {#if briefing.worst_rain_eta}
        <div class="palette-tile eta-tile">
          <span class="tile-icon">⏱️</span>
          <div class="tile-data">
            <div class="tile-value font-data">{fmtTime(briefing.worst_rain_eta)}</div>
            <div class="tile-label">Rain ETA</div>
          </div>
        </div>
      {/if}
    </div>

    <!-- ────────── 1. DAYLIGHT & VISIBILITY (COLLAPSIBLE) ────────── -->
    {#if briefing.daylight}
      <div class="collapsible-section card glass-panel">
        <button type="button" class="section-toggle-header" on:click={() => openDaylight = !openDaylight}>
          <div class="header-left">
            <span class="toggle-icon">{openDaylight ? '▼' : '▶'}</span>
            <span class="section-heading">☀️ Daylight & Visibility</span>
          </div>
          <span class="daylight-split">{briefing.daylight.daylight_hours}h Day • {briefing.daylight.night_hours}h Night</span>
        </button>

        {#if openDaylight}
          <div class="section-body fade-in">
            <div class="daylight-bar">
              <div class="day-fill" style="width: {briefing.daylight.daylight_pct}%;"></div>
              <div class="night-fill" style="width: {briefing.daylight.night_pct}%;"></div>
            </div>
            <div class="daylight-advisory">{briefing.daylight.advisory}</div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- ────────── 2. HIGHWAY JOURNEY MILESTONES (COLLAPSIBLE & INTERNALLY SCROLLABLE) ────────── -->
    <div class="collapsible-section card glass-panel">
      <button type="button" class="section-toggle-header" on:click={() => openMilestones = !openMilestones}>
        <div class="header-left">
          <span class="toggle-icon">{openMilestones ? '▼' : '▶'}</span>
          <span class="section-heading">📍 Highway Journey Milestones</span>
        </div>
        {#if pitstops && pitstops.length > 0}
          <span class="milestones-count-badge">{pitstops.length} stops</span>
        {/if}
      </button>

      {#if openMilestones}
        <div class="section-body fade-in">
          {#if $routeStore.isFetchingPitstops && (!pitstops || pitstops.length === 0)}
            <div class="pitstop-skeleton">
              <div class="pulse-line" style="width: 70%;"></div>
              <div class="pulse-line" style="width: 45%; margin-top: 6px;"></div>
              <div class="pitstop-skeleton-text">Finding top-rated plazas & verified charging hubs...</div>
            </div>
          {:else if pitstops && pitstops.length > 0}
            <div class="timeline-list scrollable-sub-container">
              {#each pitstops as ps}
                {@const b = getStopBadge(ps)}
                <div class="timeline-item">
                  <div class="timeline-marker" style="background: {b.bg}; color: {b.color}; border-color: {b.color};">
                    {b.emoji}
                  </div>
                  <div class="timeline-content">
                    <div class="timeline-item-top">
                      <span class="stop-name" title={ps.name}>{ps.name}</span>
                      <span class="stop-badge" style="color: {b.color}; background: {b.bg};">{b.label}</span>
                    </div>
                    {#if ps.vicinity}
                      <div class="stop-vicinity" title={ps.vicinity}>{ps.vicinity}</div>
                    {/if}
                    <div class="stop-meta">
                      <span>🕐 ETA {fmtTime(ps.eta)}</span>
                      <span>📍 {ps.dist_from_route_km.toFixed(1)} km detour</span>
                      {#if ps.rating}
                        <span class="rating-badge">⭐ {ps.rating.toFixed(1)}{ps.user_ratings_total ? ` (${ps.user_ratings_total})` : ''}</span>
                      {/if}
                      {#if ps.route_dist_from_last_stop_km > 0}
                        <span class="stop-dist-from-prev">📏 {ps.route_dist_from_last_stop_km.toFixed(0)} km from prev</span>
                      {/if}
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          {:else}
            <div class="empty-timeline">
              <div class="empty-timeline-text">No off-highway detours needed for this route.</div>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- ────────── 3. HIGHWAYS & EXPRESSWAYS (COLLAPSIBLE & INTERNALLY SCROLLABLE) ────────── -->
    {#if briefing.highways && briefing.highways.length > 0}
      <div class="collapsible-section card glass-panel">
        <button type="button" class="section-toggle-header" on:click={() => openHighways = !openHighways}>
          <div class="header-left">
            <span class="toggle-icon">{openHighways ? '▼' : '▶'}</span>
            <span class="section-heading">🛣️ Route Highways & Expressways</span>
          </div>
        </button>

        {#if openHighways}
          <div class="section-body fade-in">
            <div class="highway-chips scrollable-sub-container">
              {#each briefing.highways as hw}
                <div class="hw-chip">
                  <span class="hw-name" title={hw.name}>{hw.name}</span>
                  <span class="hw-dist">{hw.distance_km} km ({hw.pct}%)</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}

  </div>
{/if}

<style>
  .results-panel {
    width: 390px;
    max-width: calc(100vw - 32px);
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-height: calc(100vh - 24px);
    overflow-y: auto;
    padding-bottom: 80px;
    box-sizing: border-box;
    scrollbar-width: thin;
    scrollbar-color: rgba(249, 115, 22, 0.3) transparent;
  }

  /* Internal Scrollable Containers */
  .scrollable-sub-container {
    max-height: 250px;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: rgba(148, 163, 184, 0.4) transparent;
    padding-right: 4px;
  }

  .scrollable-sub-container::-webkit-scrollbar {
    width: 4px;
  }
  .scrollable-sub-container::-webkit-scrollbar-thumb {
    background: rgba(148, 163, 184, 0.4);
    border-radius: 4px;
  }

  /* View Mode Toggle Pill Switcher */
  .view-mode-toggle {
    display: flex;
    gap: 4px;
    padding: 4px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.85);
  }

  .mode-btn {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border-radius: 8px;
    border: 1px solid transparent;
    background: transparent;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
    min-width: 0;
  }

  .mode-btn:hover {
    background: rgba(255, 255, 255, 0.6);
  }

  .mode-btn.active {
    background: #ffffff;
    border-color: rgba(249, 115, 22, 0.35);
    box-shadow: 0 4px 12px rgba(249, 115, 22, 0.12);
  }

  .mode-icon {
    font-size: 14px;
    flex-shrink: 0;
  }

  .mode-text-box {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .mode-title {
    font-size: 11px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
  }

  .mode-sub {
    font-size: 10px;
    font-weight: 600;
    color: #64748b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .mode-btn.active .mode-title {
    color: #ea580c;
  }

  .pulse-text {
    color: #ea580c;
    animation: pulse 1.2s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  /* Universal Glassmorphism Panel with Glassy Gradient */
  .glass-panel {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.92) 0%, rgba(255, 255, 255, 0.76) 100%) !important;
    backdrop-filter: blur(20px) saturate(180%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
    border: 1px solid rgba(255, 255, 255, 0.85) !important;
    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07), inset 0 1px 1.5px 0 rgba(255, 255, 255, 1) !important;
  }

  /* Hero card with Warm Sunlit Glass Gradient */
  .hero-card {
    padding: 14px 14px 12px;
    text-align: center;
    background: linear-gradient(145deg, rgba(255, 247, 237, 0.94) 0%, rgba(255, 255, 255, 0.80) 100%) !important;
    border: 1px solid rgba(249, 115, 22, 0.28) !important;
    box-shadow: 0 10px 30px rgba(249, 115, 22, 0.08), inset 0 1px 2px rgba(255, 255, 255, 1) !important;
  }

  .hero-badge-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 2px;
  }

  .hero-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent-orange);
    font-weight: 800;
  }

  .hero-traffic-chip {
    font-size: 9px;
    font-weight: 700;
    color: #059669;
    background: rgba(16, 185, 129, 0.12);
    padding: 2px 6px;
    border-radius: 99px;
  }

  .hero-time {
    font-size: 34px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
  }

  .hero-stats {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin-top: 6px;
  }

  .hero-stat {
    display: flex;
    align-items: baseline;
    gap: 3px;
  }

  .hero-stat-val {
    font-size: 18px;
    font-weight: 800;
    color: #0f172a;
  }

  .hero-stat-unit {
    font-size: 11px;
    color: #64748b;
    font-weight: 700;
    text-transform: uppercase;
  }

  .hero-divider {
    width: 1px;
    height: 18px;
    background: rgba(0, 0, 0, 0.12);
  }

  .hero-reason {
    margin-top: 8px;
    font-size: 11px;
    color: #475569;
    font-weight: 600;
    line-height: 1.4;
    padding: 6px 10px;
    background: rgba(255, 255, 255, 0.6);
    border-radius: 6px;
    word-break: break-word;
  }

  /* Weather Palette Tiles — Adaptive Grid Layout */
  .weather-palette-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
  }

  .palette-tile {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 8px;
    border-radius: 10px;
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border: 1px solid rgba(255, 255, 255, 0.85);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05), inset 0 1px 1.5px rgba(255, 255, 255, 0.95);
    min-width: 0;
    overflow: hidden;
  }

  .rain-tile {
    background: linear-gradient(135deg, rgba(254, 243, 199, 0.85) 0%, rgba(255, 255, 255, 0.65) 100%);
    border-color: rgba(245, 158, 11, 0.3);
  }

  .wind-tile {
    background: linear-gradient(135deg, rgba(224, 242, 254, 0.85) 0%, rgba(255, 255, 255, 0.65) 100%);
    border-color: rgba(56, 189, 248, 0.3);
  }

  .eta-tile {
    background: linear-gradient(135deg, rgba(243, 232, 255, 0.85) 0%, rgba(255, 255, 255, 0.65) 100%);
    border-color: rgba(192, 132, 252, 0.3);
  }

  .tile-icon {
    font-size: 16px;
    line-height: 1;
    flex-shrink: 0;
  }

  .tile-data {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .tile-value {
    font-size: 13px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
    white-space: nowrap;
  }

  .tile-label {
    font-size: 8.5px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #475569;
    font-weight: 700;
    white-space: nowrap;
  }

  /* Collapsible Sections */
  .collapsible-section {
    padding: 0;
    border-radius: 12px;
    box-sizing: border-box;
  }

  .section-toggle-header {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: transparent;
    border: none;
    cursor: pointer;
    text-align: left;
    transition: background 0.15s ease;
    min-height: 40px;
    box-sizing: border-box;
  }

  .section-toggle-header:hover {
    background: rgba(255, 255, 255, 0.4);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }

  .toggle-icon {
    font-size: 9px;
    color: #64748b;
    flex-shrink: 0;
  }

  .section-heading {
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #0f172a;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .section-body {
    padding: 4px 14px 14px 14px;
    box-sizing: border-box;
  }

  /* Daylight Section */
  .daylight-split {
    font-size: 10px;
    font-weight: 700;
    color: #ea580c;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .daylight-bar {
    display: flex;
    height: 8px;
    border-radius: 99px;
    overflow: hidden;
    background: #0f172a;
    margin-bottom: 8px;
  }

  .day-fill {
    background: linear-gradient(90deg, #f59e0b, #fbbf24);
    transition: width 0.3s ease;
  }

  .night-fill {
    background: #1e1b4b;
    transition: width 0.3s ease;
  }

  .daylight-advisory {
    font-size: 11px;
    color: #334155;
    font-weight: 600;
    line-height: 1.45;
    word-break: break-word;
  }

  /* Highways Section */
  .highway-chips {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .hw-chip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 8px;
    background: rgba(255, 255, 255, 0.6);
    border-radius: 6px;
    font-size: 11px;
    gap: 6px;
  }

  .hw-name {
    font-weight: 700;
    color: #0f172a;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 240px;
  }

  .hw-dist {
    font-weight: 700;
    color: #64748b;
    flex-shrink: 0;
    white-space: nowrap;
  }

  /* Milestones Section */
  .milestones-count-badge {
    font-size: 10px;
    font-weight: 700;
    color: #64748b;
    flex-shrink: 0;
  }

  .timeline-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .timeline-item {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding-bottom: 2px;
  }

  .timeline-marker {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    flex-shrink: 0;
    border: 1.5px solid currentColor;
    background: rgba(255, 255, 255, 0.9);
  }

  .timeline-content {
    flex: 1;
    min-width: 0;
  }

  .timeline-item-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
  }

  .stop-name {
    font-size: 12px;
    font-weight: 800;
    color: #0f172a;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 230px;
  }

  .stop-badge {
    font-size: 9px;
    font-weight: 800;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 4px;
    flex-shrink: 0;
    white-space: nowrap;
  }

  .stop-vicinity {
    font-size: 10px;
    color: #64748b;
    margin-top: 1px;
    margin-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rating-badge {
    background: #fef3c7;
    color: #b45309;
    padding: 1px 5px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 10px;
    white-space: nowrap;
  }

  .stop-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 8px;
    font-size: 11px;
    color: #475569;
    font-weight: 600;
  }

  .stop-dist-from-prev {
    color: #0f172a;
    font-weight: 700;
    white-space: nowrap;
  }

  .empty-timeline {
    padding: 10px;
    text-align: center;
  }
  .empty-timeline-text {
    font-size: 11px;
    color: #64748b;
  }

  .pitstop-skeleton {
    padding: 10px;
  }

  .pulse-line {
    height: 12px;
    border-radius: 4px;
    background: linear-gradient(90deg, rgba(255,255,255,0.4) 25%, rgba(255,255,255,0.8) 50%, rgba(255,255,255,0.4) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
  }

  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .pitstop-skeleton-text {
    font-size: 11px;
    color: #64748b;
    margin-top: 6px;
    text-align: center;
  }
</style>
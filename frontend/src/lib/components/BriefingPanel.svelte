<script>
  import { routeStore } from '$lib/stores/routeStore.js';

  let briefing = null;
  let distance = 0;
  let duration = 0;
  let optimalDep = null;
  let pitstops = [];

  // Collapsible section states
  let openDaylight = true;
  let openHighways = true;
  let openHazards = true;
  let openMilestones = true;

  $: {
    briefing   = $routeStore.briefing;
    distance   = $routeStore.total_distance_km;
    duration   = $routeStore.estimated_duration_hours;
    optimalDep = $routeStore.optimal_departure;
    pitstops   = $routeStore.pitstops || [];
  }

  function fmtTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
  }

  function fmtDuration(h) {
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

    <!-- ────────── HERO OPTIMAL DEPARTURE CARD ────────── -->
    <div class="hero-card card glass-panel">
      <div class="hero-label">Current Departure</div>
      <div class="hero-time font-data">{fmtTime(optimalDep)}</div>
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
    </div>

    <!-- ────────── PALETTE GLASS WEATHER TILES ────────── -->
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

    <!-- ────────── DAYLIGHT & VISIBILITY (COLLAPSIBLE) ────────── -->
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

    <!-- ────────── HIGHWAYS & EXPRESSWAYS (COLLAPSIBLE) ────────── -->
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
            <div class="highway-chips">
              {#each briefing.highways as hw}
                <div class="hw-chip">
                  <span class="hw-name">{hw.name}</span>
                  <span class="hw-dist">{hw.distance_km} km ({hw.pct}%)</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- ────────── HAZARDS & CAUTION STRETCHES (COLLAPSIBLE) ────────── -->
    {#if briefing.hazard_segments && briefing.hazard_segments.length > 0}
      <div class="collapsible-section card glass-panel">
        <button type="button" class="section-toggle-header" on:click={() => openHazards = !openHazards}>
          <div class="header-left">
            <span class="toggle-icon">{openHazards ? '▼' : '▶'}</span>
            <span class="section-heading">⚠️ Route Warnings & Cautions</span>
          </div>
          <span class="hazard-count-badge">{briefing.hazard_segments.length}</span>
        </button>

        {#if openHazards}
          <div class="section-body fade-in">
            <div class="hazards-list">
              {#each briefing.hazard_segments as haz}
                <div class="hazard-card {haz.severity}">
                  <div class="hazard-top">
                    <span class="hazard-badge">{haz.title}</span>
                    <span class="hazard-stretch">{haz.stretch_km}</span>
                  </div>
                  <div class="hazard-desc">{haz.description}</div>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- ────────── HIGHWAY JOURNEY MILESTONES (COLLAPSIBLE) ────────── -->
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
          {#if $routeStore.isFetchingPitstops}
            <div class="pitstop-skeleton">
              <div class="pulse-line" style="width: 70%;"></div>
              <div class="pulse-line" style="width: 45%; margin-top: 6px;"></div>
              <div class="pitstop-skeleton-text">Snapping verified expressway plazas & charging hubs...</div>
            </div>
          {:else if pitstops && pitstops.length > 0}
            <div class="timeline-list">
              {#each pitstops as ps}
                {@const b = getStopBadge(ps)}
                <div class="timeline-item">
                  <div class="timeline-marker" style="background: {b.bg}; color: {b.color}; border-color: {b.color};">
                    {b.emoji}
                  </div>
                  <div class="timeline-content">
                    <div class="timeline-item-top">
                      <span class="stop-name">{ps.name}</span>
                      <span class="stop-badge" style="color: {b.color}; background: {b.bg};">{b.label}</span>
                    </div>
                    <div class="stop-meta">
                      <span>🕐 ETA {fmtTime(ps.eta)}</span>
                      <span>📍 {ps.dist_from_route_km.toFixed(1)} km detour</span>
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

  </div>
{/if}

<style>
  .results-panel {
    width: 360px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: calc(100vh - 32px);
    overflow-y: auto;
    padding-bottom: 28px;
  }

  /* Universal Glassmorphism Panel with Glassy Gradient */
  .glass-panel {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.88) 0%, rgba(255, 255, 255, 0.65) 100%) !important;
    backdrop-filter: blur(20px) saturate(180%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
    border: 1px solid rgba(255, 255, 255, 0.85) !important;
    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07), inset 0 1px 1.5px 0 rgba(255, 255, 255, 1) !important;
  }

  /* Hero card with Warm Sunlit Glass Gradient */
  .hero-card {
    padding: 16px 14px 14px;
    text-align: center;
    background: linear-gradient(145deg, rgba(255, 247, 237, 0.92) 0%, rgba(255, 255, 255, 0.72) 100%) !important;
    border: 1px solid rgba(249, 115, 22, 0.28) !important;
    box-shadow: 0 10px 30px rgba(249, 115, 22, 0.08), inset 0 1px 2px rgba(255, 255, 255, 1) !important;
  }

  .hero-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent-orange);
    font-weight: 800;
    margin-bottom: 2px;
  }

  .hero-time {
    font-size: 38px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
  }

  .hero-stats {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin-top: 8px;
  }

  .hero-stat {
    display: flex;
    align-items: baseline;
    gap: 3px;
  }

  .hero-stat-val {
    font-size: 16px;
    font-weight: 800;
    color: #0f172a;
  }

  .hero-stat-unit {
    font-size: 11px;
    color: #64748b;
    text-transform: uppercase;
    font-weight: 700;
  }

  .hero-divider {
    width: 1px;
    height: 14px;
    background: rgba(0, 0, 0, 0.1);
  }

  /* Palette Glass Weather Tiles (Top) with Rich Glass Gradients */
  .weather-palette-row {
    display: flex;
    gap: 6px;
  }

  .palette-tile {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 10px;
    border-radius: var(--radius-md);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.04), inset 0 1px 1.5px rgba(255, 255, 255, 0.95);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }

  .rain-tile {
    background: linear-gradient(135deg, rgba(254, 243, 199, 0.9) 0%, rgba(254, 249, 195, 0.65) 100%);
    border: 1px solid rgba(245, 158, 11, 0.35);
  }
  .wind-tile {
    background: linear-gradient(135deg, rgba(224, 242, 254, 0.9) 0%, rgba(239, 246, 255, 0.65) 100%);
    border: 1px solid rgba(56, 189, 248, 0.35);
  }
  .eta-tile {
    background: linear-gradient(135deg, rgba(243, 232, 255, 0.9) 0%, rgba(250, 245, 255, 0.65) 100%);
    border: 1px solid rgba(192, 132, 252, 0.35);
  }

  .tile-icon { font-size: 20px; }
  .tile-data { display: flex; flex-direction: column; }
  .tile-value { font-size: 14px; font-weight: 800; color: #0f172a; line-height: 1.2; }
  .tile-label { font-size: 9px; text-transform: uppercase; color: #475569; font-weight: 800; letter-spacing: 0.04em; }

  /* Collapsible Section Container */
  .collapsible-section {
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-toggle-header {
    width: 100%;
    background: none;
    border: none;
    padding: 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    text-align: left;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .toggle-icon {
    font-size: 9px;
    color: #64748b;
    width: 12px;
  }

  .section-heading {
    font-size: 12px;
    font-weight: 800;
    color: #0f172a;
  }

  .daylight-split {
    font-size: 11px;
    font-weight: 800;
    color: #d97706;
  }

  .hazard-count-badge, .milestones-count-badge {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 10px;
    background: rgba(0, 0, 0, 0.06);
    color: #475569;
  }

  .section-body {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 4px;
  }

  /* Daylight Bar */
  .daylight-bar {
    display: flex;
    height: 6px;
    border-radius: 3px;
    overflow: hidden;
    background: #e2e8f0;
  }
  .day-fill { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
  .night-fill { background: #1e293b; }
  .daylight-advisory {
    font-size: 11px;
    color: #334155;
    line-height: 1.35;
  }

  /* Highways Chips */
  .highway-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .hw-chip {
    background: rgba(255, 255, 255, 0.75);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .hw-name { font-weight: 800; color: #0f172a; }
  .hw-dist { font-size: 10px; color: #64748b; font-weight: 700; }

  /* Hazards */
  .hazards-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .hazard-card {
    padding: 8px 10px;
    background: rgba(255, 255, 255, 0.7);
    border-radius: 6px;
    border-left: 3px solid #ea580c;
  }
  .hazard-card.high { border-left-color: #dc2626; }
  .hazard-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2px;
  }
  .hazard-badge { font-size: 11px; font-weight: 800; color: #0f172a; }
  .hazard-stretch {
    font-size: 10px;
    font-weight: 800;
    color: #ea580c;
    background: rgba(234,88,12,0.12);
    padding: 1px 5px;
    border-radius: 4px;
  }
  .hazard-desc { font-size: 11px; color: #334155; line-height: 1.3; }

  /* Timeline */
  .timeline-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .timeline-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }

  .timeline-marker {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 1.5px solid;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    flex-shrink: 0;
    margin-top: 1px;
  }

  .timeline-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .timeline-item-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 6px;
  }

  .stop-name {
    font-size: 12px;
    font-weight: 800;
    color: #0f172a;
  }

  .stop-badge {
    font-size: 9px;
    font-weight: 800;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 4px;
    flex-shrink: 0;
  }

  .stop-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 10px;
    font-size: 11px;
    color: #475569;
    font-weight: 600;
  }

  .stop-dist-from-prev {
    color: #0f172a;
    font-weight: 700;
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
    font-weight: 700;
    text-align: center;
    margin-top: 6px;
  }
</style>
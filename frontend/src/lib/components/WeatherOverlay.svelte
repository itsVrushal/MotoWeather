<script>
  import { onMount, onDestroy, getContext } from 'svelte';
  import * as maplibregl from 'maplibre-gl';
  import { routeStore } from '$lib/stores/routeStore.js';

  const BASE_ID = 'route-base';
  const HEAT_ID = 'route-heat';
  const WP_ID   = 'waypoint-dots';

  const { getMap } = getContext('map');

  /** @type {import('maplibre-gl').Map | null} */
  let map = null;
  let popup = null;
  let activeLayer = 'rain';

  // ─── Colour scales ───────────────────────────────────────────────────
  function lerp(a, b, t) { return a + (b - a) * t; }
  function toRgb(r, g, b) { return `rgb(${Math.round(r)},${Math.round(g)},${Math.round(b)})`; }

  const scales = {
    rain: [
      [0,   [34,  197, 94]],
      [0.2, [234, 179, 8]],
      [0.5, [249, 115, 22]],
      [0.7, [239, 68,  68]],
      [1,   [185, 28,  28]],
    ],
    wind: [
      [0,    [16,  185, 129]],  // emerald   ~0 km/h
      [0.12, [20,  184, 166]],  // teal      ~10 km/h
      [0.22, [14,  165, 233]],  // sky        ~18 km/h
      [0.38, [59,  130, 246]],  // blue       ~30 km/h
      [0.55, [99,  102, 241]],  // indigo     ~44 km/h
      [0.72, [139, 92,  246]],  // violet     ~58 km/h
      [1,    [217, 70,  239]],  // fuchsia    ~80+ km/h
    ],
    temp: [
      [0,    [59,  130, 246]],
      [0.2,  [34,  211, 238]],
      [0.5,  [132, 204, 22]],
      [0.75, [249, 115, 22]],
      [1,    [239, 68,  68]],
    ],
    daylight: [
      [0,    [30,  27,  75]],   // midnight deep indigo
      [0.3,  [56,  189, 248]],  // twilight / dusk
      [1,    [245, 158, 11]],   // golden daylight
    ],
    traffic: [
      [0,    [16,  185, 129]],  // emerald (low / free flow)
      [0.35, [245, 158, 11]],   // amber (moderate)
      [0.7,  [249, 115, 22]],   // orange (heavy congestion)
      [1,    [220, 38,  38]],   // crimson (severe bottleneck)
    ],
  };

  function sampleColor(scale, t) {
    t = Math.max(0, Math.min(1, t));
    for (let i = 1; i < scale.length; i++) {
      if (t <= scale[i][0]) {
        const prev = scale[i - 1], next = scale[i];
        const local = (t - prev[0]) / (next[0] - prev[0]);
        return toRgb(
          lerp(prev[1][0], next[1][0], local),
          lerp(prev[1][1], next[1][1], local),
          lerp(prev[1][2], next[1][2], local),
        );
      }
    }
    return toRgb(...scale[scale.length - 1][1]);
  }

  const norms = {
    rain: v => v / 100,
    wind: v => Math.min(v / 80, 1),
    temp: v => Math.min(Math.max((v - 10) / 40, 0), 1),
    daylight: v => v,
    traffic: v => v,
  };

  // ─── Geometry helpers ────────────────────────────────────────────────
  function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) ** 2 +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function findNearestWaypoint(pt, waypoints) {
    let best = waypoints[0], bestD = Infinity;
    for (const wp of waypoints) {
      const d = haversine(pt.lat, pt.lon, wp.lat, wp.lon);
      if (d < bestD) { bestD = d; best = wp; }
    }
    return best;
  }

  function isDaytime(etaStr) {
    if (!etaStr) return true;
    const d = new Date(etaStr);
    const hr = d.getHours() + d.getMinutes() / 60;
    return hr >= 6.25 && hr <= 18.75;
  }

  function getVal(wp, layer) {
    if (layer === 'rain') return norms.rain(wp.precip_pct ?? 0);
    if (layer === 'wind') return norms.wind(wp.wind_kmh ?? 0);
    if (layer === 'temp') return norms.temp(wp.temp_c ?? 25);
    if (layer === 'daylight') return isDaytime(wp.eta) ? 1 : 0;
    if (layer === 'traffic') {
      const tMap = { low: 0.0, moderate: 0.35, heavy: 0.7, severe: 1.0 };
      return tMap[wp.traffic_level || 'low'] ?? 0.0;
    }
    return 0;
  }

  function buildGradientExpr(geometry, waypoints, layer) {
    const totalPts = geometry.length;
    if (totalPts < 2) return '#3b82f6';

    const numStops = Math.min(totalPts, 80);
    const step = (totalPts - 1) / (numStops - 1);
    const stops = [];

    for (let i = 0; i < numStops; i++) {
      const pIdx = Math.round(i * step);
      const pt = geometry[pIdx];
      const prog = Math.round((pIdx / (totalPts - 1)) * 1000) / 1000;
      const wp = findNearestWaypoint(pt, waypoints);
      const val = getVal(wp, layer);
      const color = sampleColor(scales[layer], val);
      stops.push({ p: prog, c: color });
    }

    if (stops[0].p > 0) stops.unshift({ p: 0, c: stops[0].c });
    if (stops[stops.length-1].p < 1) stops.push({ p: 1, c: stops[stops.length-1].c });

    const deduped = [stops[0]];
    for (let i = 1; i < stops.length; i++) {
      if (Math.abs(stops[i].p - deduped[deduped.length-1].p) > 0.001) {
        deduped.push(stops[i]);
      }
    }

    const args = [];
    for (const { p, c } of deduped) { args.push(p, c); }

    return ['interpolate', ['linear'], ['line-progress'], ...args];
  }

  function buildRouteGeoJSON(geometry) {
    return {
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: geometry.map(p => [p.lon, p.lat]),
      },
    };
  }

  function buildWaypointsGeoJSON(waypoints) {
    return {
      type: 'FeatureCollection',
      features: waypoints.map((wp, i) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [wp.lon, wp.lat] },
        properties: {
          index: i,
          km: wp.cumulative_km,
          eta: wp.eta,
          precip: wp.precip_pct,
          wind: wp.wind_kmh,
          temp: wp.temp_c,
          weathercode: wp.weathercode,
          traffic: wp.traffic_level || 'low',
        },
      })),
    };
  }

  function renderLayers(geometry, waypoints) {
    if (!map || !geometry || geometry.length === 0) return;

    const routeData = buildRouteGeoJSON(geometry);
    const wpData    = buildWaypointsGeoJSON(waypoints);

    if (map.getSource(BASE_ID)) {
      map.getSource(BASE_ID).setData(routeData);
      map.getSource(WP_ID).setData(wpData);
    } else {
      map.addSource(BASE_ID, { type: 'geojson', data: routeData, lineMetrics: true });
      map.addSource(WP_ID,   { type: 'geojson', data: wpData });

      map.addLayer({
        id: BASE_ID,
        type: 'line',
        source: BASE_ID,
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#ffffff', 'line-width': 10, 'line-opacity': 0.8 },
      });

      map.addLayer({
        id: HEAT_ID,
        type: 'line',
        source: BASE_ID,
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-width': 6,
          'line-gradient': buildGradientExpr(geometry, waypoints, activeLayer),
        },
      });

      map.addLayer({
        id: WP_ID,
        type: 'circle',
        source: WP_ID,
        paint: {
          'circle-radius': 4.5,
          'circle-color': '#ffffff',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#0f172a',
        },
      });

      map.on('click', WP_ID, onWaypointClick);
      map.on('mouseenter', WP_ID, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', WP_ID, () => { map.getCanvas().style.cursor = ''; });
    }

    if (map.getLayer(HEAT_ID)) {
      map.setPaintProperty(HEAT_ID, 'line-gradient', buildGradientExpr(geometry, waypoints, activeLayer));
    }
  }

  function onWaypointClick(e) {
    if (!e.features || e.features.length === 0) return;
    const props = e.features[0].properties;
    const [lon, lat] = e.features[0].geometry.coordinates;

    const etaStr = new Date(props.eta).toLocaleTimeString('en-IN', {
      hour: '2-digit', minute: '2-digit', hour12: true,
    });

    const isDay = isDaytime(props.eta);

    popup?.remove();
    popup = new maplibregl.Popup({ offset: 12, closeButton: false, className: 'wp-popup' })
      .setLngLat([lon, lat])
      .setHTML(`
        <div style="font-family: 'Inter', sans-serif; padding: 4px; color: #0f172a;">
          <div style="font-weight:700; font-size:13px; margin-bottom:4px;">Km ${Number(props.km).toFixed(0)} • ${etaStr}</div>
          <div style="font-size:12px; margin-bottom:2px;">🌧️ Rain: <strong>${Number(props.precip).toFixed(0)}%</strong></div>
          <div style="font-size:12px; margin-bottom:2px;">💨 Wind: <strong>${Number(props.wind).toFixed(0)} km/h</strong></div>
          <div style="font-size:12px; margin-bottom:2px;">🌡️ Temp: <strong>${Number(props.temp).toFixed(0)}°C</strong></div>
          <div style="font-size:12px; margin-bottom:2px;">🚦 Traffic: <strong style="text-transform:capitalize;">${props.traffic || 'Free Flow'}</strong></div>
          <div style="font-size:11px; margin-top:4px; color:#64748b;">${isDay ? '☀️ Daylight' : '🌙 Night Driving'}</div>
        </div>
      `)
      .addTo(map);
  }

  function setLayer(layer) {
    activeLayer = layer;
    routeStore.update(s => ({ ...s, active_heatmap_layer: layer }));
    const { geometry, waypoints } = $routeStore;
    if (map && map.getLayer(HEAT_ID) && geometry?.length && waypoints?.length) {
      map.setPaintProperty(HEAT_ID, 'line-gradient', buildGradientExpr(geometry, waypoints, activeLayer));
    }
  }

  $: {
    const { geometry, waypoints } = $routeStore;
    if (map && geometry && geometry.length > 0 && waypoints && waypoints.length > 0) {
      renderLayers(geometry, waypoints);
    }
  }

  onMount(() => {
    map = getMap();
    if (map) {
      if (map.loaded()) {
        const { geometry, waypoints } = $routeStore;
        if (geometry?.length && waypoints?.length) renderLayers(geometry, waypoints);
      } else {
        map.on('load', () => {
          const { geometry, waypoints } = $routeStore;
          if (geometry?.length && waypoints?.length) renderLayers(geometry, waypoints);
        });
      }
    }
  });

  onDestroy(() => {
    popup?.remove();
    if (map) {
      if (map.getLayer(WP_ID))   map.removeLayer(WP_ID);
      if (map.getLayer(HEAT_ID)) map.removeLayer(HEAT_ID);
      if (map.getLayer(BASE_ID)) map.removeLayer(BASE_ID);
      if (map.getSource(WP_ID))   map.removeSource(WP_ID);
      if (map.getSource(BASE_ID)) map.removeSource(BASE_ID);
    }
  });
</script>

{#if $routeStore.geometry && $routeStore.geometry.length > 0}
  <div class="heatmap-controls">
    <div class="heatmap-label">Map Layer</div>
    <div class="heatmap-btns">
      <button
        class="hm-btn {activeLayer === 'rain' ? 'active rain' : ''}"
        on:click={() => setLayer('rain')}
        title="Rain probability along route"
      >
        🌧️ Rain
      </button>
      <button
        class="hm-btn {activeLayer === 'wind' ? 'active wind' : ''}"
        on:click={() => setLayer('wind')}
        title="Wind speed along route"
      >
        💨 Wind
      </button>
      <button
        class="hm-btn {activeLayer === 'temp' ? 'active temp' : ''}"
        on:click={() => setLayer('temp')}
        title="Temperature"
      >
        🌡️ Temp
      </button>
      <button
        class="hm-btn {activeLayer === 'traffic' ? 'active traffic' : ''}"
        on:click={() => setLayer('traffic')}
        title="Live Traffic Congestion & Roadworks"
      >
        🚦 Traffic
      </button>
      <button
        class="hm-btn {activeLayer === 'daylight' ? 'active daylight' : ''}"
        on:click={() => setLayer('daylight')}
        title="Daylight vs Night driving road stretches"
      >
        ☀️ Day/Night
      </button>
    </div>

    <!-- Dynamic legend for active layer -->
    <div class="legend-card">
      {#if activeLayer === 'rain'}
        <div class="legend-title">Rain Probability</div>
        <div class="legend-bar" style="background: linear-gradient(to right, #22c55e, #eab308, #f97316, #ef4444, #b91c1c)"></div>
        <div class="legend-ticks">
          <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
        </div>
        <div class="legend-swatches">
          <span class="swatch" style="background:#22c55e"></span><span class="swatch-label">Safe</span>
          <span class="swatch" style="background:#eab308"></span><span class="swatch-label">Low</span>
          <span class="swatch" style="background:#f97316"></span><span class="swatch-label">Mod</span>
          <span class="swatch" style="background:#ef4444"></span><span class="swatch-label">High</span>
        </div>
      {:else if activeLayer === 'wind'}
        <div class="legend-title">Wind Speed</div>
        <div class="legend-bar" style="background: linear-gradient(to right, #14b8a6, #3b82f6, #8b5cf6, #d946ef)"></div>
        <div class="legend-ticks">
          <span>0</span><span>20</span><span>40</span><span>60</span><span>80+ km/h</span>
        </div>
        <div class="legend-swatches">
          <span class="swatch" style="background:#14b8a6"></span><span class="swatch-label">Calm</span>
          <span class="swatch" style="background:#3b82f6"></span><span class="swatch-label">Breezy</span>
          <span class="swatch" style="background:#8b5cf6"></span><span class="swatch-label">Windy</span>
          <span class="swatch" style="background:#d946ef"></span><span class="swatch-label">Strong</span>
        </div>
      {:else if activeLayer === 'temp'}
        <div class="legend-title">Temperature</div>
        <div class="legend-bar" style="background: linear-gradient(to right, #3b82f6, #22d3ee, #84cc16, #f97316, #ef4444)"></div>
        <div class="legend-ticks">
          <span>10°</span><span>20°</span><span>30°</span><span>40°</span><span>50°C</span>
        </div>
        <div class="legend-swatches">
          <span class="swatch" style="background:#3b82f6"></span><span class="swatch-label">Cool</span>
          <span class="swatch" style="background:#84cc16"></span><span class="swatch-label">Warm</span>
          <span class="swatch" style="background:#f97316"></span><span class="swatch-label">Hot</span>
          <span class="swatch" style="background:#ef4444"></span><span class="swatch-label">Scorch</span>
        </div>
      {:else if activeLayer === 'traffic'}
        <div class="legend-title">Live Traffic Congestion</div>
        <div class="legend-bar" style="background: linear-gradient(to right, #10b981, #f59e0b, #f97316, #dc2626)"></div>
        <div class="legend-ticks">
          <span>🟢 Free Flow</span><span>🟡 Mod</span><span>🔴 Jam</span>
        </div>
        <div class="legend-swatches">
          <span class="swatch" style="background:#10b981"></span><span class="swatch-label">Free Flow</span>
          <span class="swatch" style="background:#f59e0b"></span><span class="swatch-label">Moderate</span>
          <span class="swatch" style="background:#dc2626"></span><span class="swatch-label">Heavy</span>
        </div>
      {:else if activeLayer === 'daylight'}
        <div class="legend-title">Daylight vs Night Driving</div>
        <div class="legend-bar" style="background: linear-gradient(to right, #f59e0b, #38bdf8, #1e1b4b)"></div>
        <div class="legend-ticks">
          <span>☀️ Daylight</span><span>🌇 Dusk</span><span>🌙 Night</span>
        </div>
        <div class="legend-swatches">
          <span class="swatch" style="background:#f59e0b"></span><span class="swatch-label">Daylight (Full Sun)</span>
          <span class="swatch" style="background:#1e1b4b"></span><span class="swatch-label">Night (High-Beam)</span>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .heatmap-controls {
    position: absolute;
    bottom: 40px;
    left: 16px;
    z-index: 10;
    display: flex;
    flex-direction: column;
    gap: 6px;
    pointer-events: auto;
  }

  .heatmap-label {
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #475569;
    padding-left: 2px;
  }

  .heatmap-btns {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .hm-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.9);
    border-radius: 8px;
    color: #1e293b;
    font-size: 12px;
    font-weight: 700;
    padding: 7px 12px;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
    transition: all 0.18s ease;
    white-space: nowrap;
  }

  .hm-btn:hover {
    background: #ffffff;
    color: #0f172a;
    transform: translateX(2px);
  }

  .hm-btn.active {
    background: #ffffff;
    font-weight: 800;
    transform: translateX(3px);
  }

  .hm-btn.active.rain {
    border-color: #f97316;
    color: #ea580c;
    box-shadow: 0 4px 14px rgba(249, 115, 22, 0.25);
  }

  .hm-btn.active.wind {
    border-color: #3b82f6;
    color: #2563eb;
    box-shadow: 0 4px 14px rgba(59, 130, 246, 0.25);
  }

  .hm-btn.active.temp {
    border-color: #84cc16;
    color: #65a30d;
    box-shadow: 0 4px 14px rgba(132, 204, 22, 0.25);
  }

  .hm-btn.active.traffic {
    border-color: #ef4444;
    color: #dc2626;
    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.25);
  }

  .hm-btn.active.daylight {
    border-color: #f59e0b;
    color: #d97706;
    box-shadow: 0 4px 14px rgba(245, 158, 11, 0.25);
  }

  /* Legend card */
  .legend-card {
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.95);
    border-radius: 10px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 7px;
    min-width: 190px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  }

  .legend-title {
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #334155;
  }

  .legend-bar {
    height: 8px;
    border-radius: 99px;
    width: 100%;
  }

  .legend-ticks {
    display: flex;
    justify-content: space-between;
    font-size: 9px;
    color: #64748b;
    font-weight: 700;
    margin-top: -3px;
  }

  .legend-swatches {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
    margin-top: 2px;
  }

  .swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
    border: 1px solid rgba(0,0,0,0.15);
  }

  .swatch-label {
    font-size: 9px;
    font-weight: 600;
    color: #334155;
    margin-right: 4px;
  }
</style>
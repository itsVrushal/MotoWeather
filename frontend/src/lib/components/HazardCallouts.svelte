<script>
  import { onMount, onDestroy, getContext } from 'svelte';
  import * as maplibregl from 'maplibre-gl';
  import { routeStore } from '$lib/stores/routeStore.js';

  const { getMap } = getContext('map');

  /** @type {import('maplibre-gl').Map | null} */
  let map = null;
  /** @type {import('maplibre-gl').Marker[]} */
  let markers = [];

  function clearMarkers() {
    markers.forEach(m => m.remove());
    markers = [];
  }

  function getHazardIcon(type) {
    if (type === 'rain') return '🌧️';
    if (type === 'wind') return '💨';
    if (type === 'traffic') return '🚦';
    if (type === 'roadwork') return '🚧';
    if (type === 'temp') return '🌡️';
    if (type === 'night') return '🌙';
    return '⚠️';
  }

  function matchesActiveLayer(hazardType, activeLayer) {
    if (!activeLayer || activeLayer === 'rain') {
      return hazardType === 'rain';
    }
    if (activeLayer === 'wind') {
      return hazardType === 'wind';
    }
    if (activeLayer === 'traffic') {
      return hazardType === 'traffic' || hazardType === 'roadwork';
    }
    if (activeLayer === 'temp') {
      return hazardType === 'temp';
    }
    if (activeLayer === 'daylight') {
      return hazardType === 'night';
    }
    return false;
  }

  function addHazardCallouts(hazards, activeLayer) {
    clearMarkers();
    if (!map || !hazards || hazards.length === 0) return;

    // Filter only hazards relevant to the currently selected map view
    const relevantHazards = hazards.filter(h => matchesActiveLayer(h.hazard_type, activeLayer));

    relevantHazards.forEach(haz => {
      if (!haz.lat || !haz.lon) return;

      const el = document.createElement('div');
      el.className = `static-glass-warning ${haz.severity || 'moderate'} ${haz.hazard_type || 'general'}`;
      
      const icon = getHazardIcon(haz.hazard_type);
      
      el.innerHTML = `
        <div class="warning-pill-box">
          <span class="warning-icon">${icon}</span>
          <div class="warning-text-block">
            <span class="warning-title">${haz.title}</span>
            <span class="warning-stretch">${haz.stretch_km}</span>
          </div>
        </div>
      `;

      // Detailed popup on click
      const popup = new maplibregl.Popup({ offset: [0, -10], closeButton: false, className: 'glass-hazard-popup' })
        .setHTML(`
          <div class="glass-popup-box">
            <div class="popup-top">
              <span>${icon} <strong>${haz.title}</strong></span>
              <span class="popup-stretch">${haz.stretch_km}</span>
            </div>
            <div class="popup-desc">${haz.description}</div>
          </div>
        `);

      // Anchor beside the coordinate without dynamic jiggle or diagonal lines
      const marker = new maplibregl.Marker({ element: el, anchor: 'bottom-left', offset: [12, -6] })
        .setLngLat([haz.lon, haz.lat])
        .setPopup(popup)
        .addTo(map);

      markers.push(marker);
    });
  }

  onMount(() => {
    map = getMap();
  });

  $: {
    const isRecommended = $routeStore.active_view_mode === 'recommended';
    const activeData = (isRecommended && $routeStore.recommended_data) ? $routeStore.recommended_data : ($routeStore.planned_data || $routeStore);
    const hazards = activeData.briefing?.hazard_segments || [];
    const activeLayer = $routeStore.active_heatmap_layer || 'rain';
    
    if (map) {
      if (hazards && hazards.length > 0) {
        addHazardCallouts(hazards, activeLayer);
      } else {
        clearMarkers();
      }
    }
  }

  onDestroy(clearMarkers);
</script>

<style>
  /* Static, rock-solid pinned warning badge without jiggle animation or transform delay */
  :global(.static-glass-warning) {
    cursor: pointer;
    z-index: 25;
    pointer-events: auto;
    user-select: none;
    -webkit-user-select: none;
  }

  :global(.warning-pill-box) {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.94) 0%, rgba(255, 255, 255, 0.82) 100%);
    backdrop-filter: blur(14px) saturate(180%);
    -webkit-backdrop-filter: blur(14px) saturate(180%);
    border: 1.2px solid rgba(255, 255, 255, 0.95);
    border-radius: 10px;
    padding: 6px 10px;
    display: flex;
    align-items: center;
    gap: 7px;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08), inset 0 1px 1.5px rgba(255, 255, 255, 1);
    white-space: nowrap;
  }

  :global(.static-glass-warning.high .warning-pill-box) {
    background: linear-gradient(135deg, rgba(254, 242, 242, 0.95) 0%, rgba(255, 255, 255, 0.85) 100%);
    border-color: rgba(239, 68, 68, 0.35);
    box-shadow: 0 4px 16px rgba(239, 68, 68, 0.12), inset 0 1px 1.5px rgba(255, 255, 255, 1);
  }

  :global(.static-glass-warning.moderate .warning-pill-box) {
    background: linear-gradient(135deg, rgba(255, 247, 237, 0.95) 0%, rgba(255, 255, 255, 0.85) 100%);
    border-color: rgba(249, 115, 22, 0.35);
    box-shadow: 0 4px 16px rgba(249, 115, 22, 0.12), inset 0 1px 1.5px rgba(255, 255, 255, 1);
  }

  :global(.warning-icon) {
    font-size: 15px;
    line-height: 1;
    flex-shrink: 0;
  }

  :global(.warning-text-block) {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
  }

  :global(.warning-title) {
    font-size: 11.5px;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.01em;
  }

  :global(.static-glass-warning.high .warning-title) {
    color: #991b1b;
  }

  :global(.static-glass-warning.moderate .warning-title) {
    color: #9a3412;
  }

  :global(.warning-stretch) {
    font-size: 9.5px;
    font-weight: 700;
    color: #64748b;
  }

  /* Glass Detail Popup */
  :global(.glass-hazard-popup .maplibregl-popup-content) {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(255, 255, 255, 0.85) 100%);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border: 1px solid rgba(255, 255, 255, 0.95);
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(15, 23, 42, 0.14);
    padding: 10px 14px;
    max-width: 250px;
    font-family: 'Inter', sans-serif;
  }

  :global(.glass-popup-box) {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  :global(.popup-top) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    color: #0f172a;
  }

  :global(.popup-stretch) {
    font-size: 10px;
    font-weight: 700;
    color: #ea580c;
    background: rgba(234, 88, 12, 0.1);
    padding: 2px 6px;
    border-radius: 4px;
  }

  :global(.popup-desc) {
    font-size: 11px;
    color: #334155;
    line-height: 1.4;
  }
</style>

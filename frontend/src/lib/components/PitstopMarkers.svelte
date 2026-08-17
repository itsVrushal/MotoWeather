<script>
  import { onMount, onDestroy, getContext } from 'svelte';
  import * as maplibregl from 'maplibre-gl';
  import { routeStore } from '$lib/stores/routeStore.js';

  const { getMap } = getContext('map');

  /** @type {maplibregl.Map | null} */
  let map = null;
  /** @type {maplibregl.Marker[]} */
  let markers = [];

  function getMarkerConfig(ps) {
    const sub = ps.sub_type || ps.type;
    if (sub === 'charging' || (ps.type === 'fuel' && $routeStore.last_request?.vehicle_type === 'ev')) {
      return { emoji: '⚡', color: '#3b82f6', label: 'EV Charging Station' };
    }
    if (sub === 'fuel' || ps.type === 'fuel') {
      return { emoji: '⛽', color: '#f97316', label: 'Fuel Station' };
    }
    if (sub === 'breakfast' || sub === 'chai') {
      return { emoji: '☕', color: '#eab308', label: sub === 'breakfast' ? 'Breakfast Stop' : 'Chai & Snacks' };
    }
    if (sub === 'lunch' || sub === 'dinner') {
      return { emoji: '🍽️', color: '#ef4444', label: sub === 'lunch' ? 'Lunch / Dhaba' : 'Dinner Stop' };
    }
    return { emoji: '📍', color: '#10b981', label: 'Road Stop' };
  }

  function createMarkerEl(ps) {
    const cfg = getMarkerConfig(ps);
    
    // Outer container controlled by MapLibre
    const container = document.createElement('div');
    container.className = 'pitstop-marker-container';
    container.style.cssText = `
      width: 40px;
      height: 48px;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      cursor: pointer;
    `;

    // Inner element handles hover scaling
    const inner = document.createElement('div');
    inner.style.cssText = `
      width: 32px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 150ms cubic-bezier(0.4, 0, 0.2, 1);
      transform-origin: bottom center;
    `;
    
    inner.innerHTML = `
      <svg width="32" height="40" viewBox="0 0 32 40" fill="none" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0px 4px 6px rgba(0,0,0,0.3));">
        <path d="M16 0C7.16344 0 0 7.16344 0 16C0 27.2 16 40 16 40C16 40 32 27.2 32 16C32 7.16344 24.8366 0 16 0Z" fill="${cfg.color}"/>
        <circle cx="16" cy="16" r="12" fill="#1e293b"/>
        <text x="16" y="21" font-size="14" text-anchor="middle" fill="white">${cfg.emoji}</text>
      </svg>
    `;
    
    container.title = cfg.label;
    container.appendChild(inner);

    container.addEventListener('mouseenter', () => {
      inner.style.transform = 'scale(1.25)';
    });
    container.addEventListener('mouseleave', () => {
      inner.style.transform = 'scale(1)';
    });
    
    return container;
  }

  function clearMarkers() {
    markers.forEach(m => m.remove());
    markers = [];
  }

  function addMarkers(pitstops) {
    if (!map) return;
    clearMarkers();

    pitstops.forEach(ps => {
      const cfg = getMarkerConfig(ps);
      const el = createMarkerEl(ps);
      const eta = new Date(ps.eta);
      const timeStr = eta.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

      const popup = new maplibregl.Popup({
        offset: [0, -35],
        closeButton: true,
        className: 'pitstop-popup',
      }).setHTML(`
        <div style="
          font-family: 'Inter', sans-serif;
          background: #131720;
          color: #f1f5f9;
          border-radius: 8px;
          padding: 6px;
          min-width: 200px;
        ">
          <div style="font-weight:700; font-size:14px; margin-bottom:2px;">${cfg.emoji} ${ps.name}</div>
          <div style="color:${cfg.color}; font-size:11px; font-weight:600; margin-bottom:6px; text-transform:uppercase;">${cfg.label}</div>
          <div style="display:flex; flex-direction:column; gap:3px;">
            <div style="font-size:12px;">🕐 ETA: <strong>${timeStr}</strong></div>
            <div style="font-size:12px;">📍 ${ps.dist_from_route_km.toFixed(1)} km detour from highway</div>
            ${ps.route_dist_from_last_stop_km > 0 ? `<div style="font-size:12px; color:#cbd5e1;">📏 <strong>${ps.route_dist_from_last_stop_km.toFixed(0)} km</strong> from previous stop</div>` : ''}
          </div>
        </div>
      `);

      const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
        .setLngLat([ps.lon, ps.lat])
        .setPopup(popup)
        .addTo(map);

      markers.push(marker);
    });
  }

  onMount(() => {
    map = getMap();
  });

  $: {
    const pitstops = $routeStore.pitstops;
    if (map) {
      if (pitstops && pitstops.length > 0) {
        addMarkers(pitstops);
      } else {
        clearMarkers();
      }
    }
  }

  onDestroy(clearMarkers);
</script>
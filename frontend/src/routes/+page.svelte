<script>
  import '../app.css';
  import MapView from '$lib/components/MapView.svelte';
  import WeatherOverlay from '$lib/components/WeatherOverlay.svelte';
  import PitstopMarkers from '$lib/components/PitstopMarkers.svelte';
  import RouteForm from '$lib/components/RouteForm.svelte';
  import BriefingPanel from '$lib/components/BriefingPanel.svelte';
  import { routeStore } from '$lib/stores/routeStore.js';
</script>

<svelte:head>
  <title>Moto-Weather — Maharashtra Ride Planner</title>
  <meta name="description" content="Plan your motorcycle ride with real-time weather intelligence. Optimised departure times, weather heatmaps, and pitstop suggestions." />
</svelte:head>

<!-- Full-screen map fills everything -->
<div class="app-shell">

  <!-- The map is the full background -->
  <div class="map-bg">
    <MapView>
      <WeatherOverlay />
      <PitstopMarkers />
    </MapView>
  </div>

  <!-- ── Left overlay: form + (after results) heatmap note ── -->
  <div class="left-overlay">
    <RouteForm />
  </div>

  <!-- ── Right overlay: results panel ── -->
  {#if $routeStore.briefing}
    <div class="right-overlay">
      <BriefingPanel />
    </div>
  {/if}

  <!-- ── Loading overlay ── -->
  {#if $routeStore.loading}
    <div class="loading-overlay">
      <div class="loading-pill">
        <div class="spinner"></div>
        <span>Crunching weather data…</span>
      </div>
    </div>
  {/if}

</div>

<style>
  :global(body) { overflow: hidden; }

  .app-shell {
    position: relative;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
  }

  /* Map fills everything */
  .map-bg {
    position: absolute;
    inset: 0;
    z-index: 0;
  }

  /* Left floating panel */
  .left-overlay {
    position: absolute;
    top: 16px;
    left: 16px;
    z-index: 20;
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: calc(100vh - 32px);
    overflow-y: auto;
    /* hide scrollbar */
    scrollbar-width: none;
  }
  .left-overlay::-webkit-scrollbar { display: none; }

  /* Right floating panel */
  .right-overlay {
    position: absolute;
    top: 16px;
    right: 16px;
    z-index: 20;
    max-height: calc(100vh - 32px);
    overflow-y: auto;
    scrollbar-width: none;
  }
  .right-overlay::-webkit-scrollbar { display: none; }

  /* Loading overlay */
  .loading-overlay {
    position: absolute;
    inset: 0;
    z-index: 50;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    padding-bottom: 40px;
    pointer-events: none;
  }

  .loading-pill {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--bg-elevated, rgba(255,255,255,0.96));
    border: 1px solid rgba(249,115,22,0.25);
    border-radius: 99px;
    padding: 11px 22px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary, #1e293b);
    backdrop-filter: blur(20px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.12), 0 0 0 1px rgba(249,115,22,0.08);
    pointer-events: all;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid var(--border);
    border-top-color: var(--accent-orange);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
</style>

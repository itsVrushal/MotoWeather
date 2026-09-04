<script>
  import '../app.css';
  import MapView from '$lib/components/MapView.svelte';
  import WeatherOverlay from '$lib/components/WeatherOverlay.svelte';
  import PitstopMarkers from '$lib/components/PitstopMarkers.svelte';
  import HazardCallouts from '$lib/components/HazardCallouts.svelte';
  import RouteForm from '$lib/components/RouteForm.svelte';
  import BriefingPanel from '$lib/components/BriefingPanel.svelte';
  import { routeStore } from '$lib/stores/routeStore.js';

  // Mobile bottom-sheet state
  let sheetExpanded = false;
  // When a route result arrives, auto-expand the sheet
  $: if ($routeStore.briefing) sheetExpanded = true;
</script>

<svelte:head>
  <title>Moto-Weather — Maharashtra Ride Planner</title>
  <meta name="description" content="Plan your motorcycle ride with real-time weather intelligence. Optimised departure times, weather heatmaps, and pitstop suggestions." />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
</svelte:head>

<!-- Full-screen map fills everything -->
<div class="app-shell">

  <!-- The map is the full background -->
  <div class="map-bg">
    <MapView>
      <WeatherOverlay />
      <PitstopMarkers />
      <HazardCallouts />
    </MapView>
  </div>

  <!-- ── DESKTOP: Left overlay: form ── -->
  <div class="left-overlay desktop-only">
    <RouteForm />
  </div>

  <!-- ── DESKTOP: Right overlay: results panel ── -->
  {#if $routeStore.briefing}
    <div class="right-overlay desktop-only">
      <BriefingPanel />
    </div>
  {/if}

  <!-- ── MOBILE: Bottom Sheet ── -->
  <div class="mobile-sheet mobile-only" class:expanded={sheetExpanded}>
    <!-- Drag handle -->
    <button
      class="sheet-handle-area"
      aria-label="Toggle panel"
      on:click={() => sheetExpanded = !sheetExpanded}
    >
      <div class="sheet-handle"></div>
    </button>

    <!-- Sheet content: scrollable -->
    <div class="sheet-body">
      {#if $routeStore.briefing}
        <!-- Tab switcher for mobile -->
        <div class="mobile-tabs">
          <button
            class="mobile-tab"
            class:active={!sheetExpanded}
            on:click={() => sheetExpanded = false}
          >🗺️ Plan</button>
          <button
            class="mobile-tab"
            class:active={sheetExpanded}
            on:click={() => sheetExpanded = true}
          >📊 Results</button>
        </div>

        {#if sheetExpanded}
          <BriefingPanel />
        {:else}
          <RouteForm />
        {/if}
      {:else}
        <RouteForm />
      {/if}
    </div>
  </div>

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

  /* ── DESKTOP PANELS ── */
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

  /* ── MOBILE / TABLET RESPONSIVE ── */
  /* Show/hide helpers */
  .desktop-only { display: flex; }
  .mobile-only  { display: none; }

  /* ── MOBILE BOTTOM SHEET ── */
  .mobile-sheet {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 30;
    display: none; /* hidden on desktop */
    flex-direction: column;
    background: rgba(255, 255, 255, 0.97);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border-top-left-radius: 20px;
    border-top-right-radius: 20px;
    box-shadow: 0 -8px 40px rgba(0, 0, 0, 0.18);
    /* Collapsed: show just the handle + a peek of the form */
    max-height: 65vh;
    transition: max-height 0.35s cubic-bezier(0.32, 0.72, 0, 1);
  }

  .mobile-sheet.expanded {
    max-height: 88vh;
  }

  .sheet-handle-area {
    width: 100%;
    padding: 10px 0 6px;
    display: flex;
    justify-content: center;
    background: transparent;
    border: none;
    cursor: pointer;
    flex-shrink: 0;
  }

  .sheet-handle {
    width: 40px;
    height: 4px;
    background: rgba(0, 0, 0, 0.18);
    border-radius: 99px;
  }

  .sheet-body {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 0 12px 24px;
    /* safe area for phones with home bar */
    padding-bottom: calc(24px + env(safe-area-inset-bottom, 0px));
    scrollbar-width: none;
  }
  .sheet-body::-webkit-scrollbar { display: none; }

  /* Mobile tab switcher */
  .mobile-tabs {
    display: flex;
    gap: 6px;
    margin-bottom: 12px;
    background: rgba(243, 244, 246, 0.9);
    border-radius: 10px;
    padding: 4px;
  }

  .mobile-tab {
    flex: 1;
    padding: 8px 12px;
    background: transparent;
    border: none;
    border-radius: 7px;
    font-size: 13px;
    font-weight: 600;
    font-family: var(--font-ui);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.18s ease;
  }

  .mobile-tab.active {
    background: #ffffff;
    color: var(--accent-orange);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  @media (max-width: 639px) {
    .desktop-only { display: none !important; }
    .mobile-only  { display: flex !important; }

    /* On mobile, nudge loading pill up so it clears the sheet */
    .loading-overlay {
      padding-bottom: calc(68vh + 16px);
    }
  }
</style>

<script>
  import { onMount } from 'svelte';
  import '../app.css';
  import MapView from '$lib/components/MapView.svelte';
  import WeatherOverlay from '$lib/components/WeatherOverlay.svelte';
  import PitstopMarkers from '$lib/components/PitstopMarkers.svelte';
  import HazardCallouts from '$lib/components/HazardCallouts.svelte';
  import RouteForm from '$lib/components/RouteForm.svelte';
  import BriefingPanel from '$lib/components/BriefingPanel.svelte';
  import { routeStore } from '$lib/stores/routeStore.js';

  // Mobile bottom-sheet state
  // Snap states: 'peek' (~74px), 'half' (~50vh), 'form' (~75vh / 500px), 'expanded' (~88vh)
  let currentSnap = 'form';
  let activeMobileTab = 'plan'; // 'plan' | 'results'
  let isDragging = false;
  let sheetHeight = 500;
  let snapHeights = { peek: 74, half: 380, form: 500, expanded: 700 };

  // Drag tracking
  let startY = 0;
  let startHeight = 0;
  let lastY = 0;
  let lastTime = 0;
  let velocityY = 0;
  let hasMoved = false;

  let sheetHeaderEl;
  let sheetBodyEl;

  // Track briefing changes — auto-minimize to peek so appropriate view of map is seen
  let prevBriefing = null;
  $: if ($routeStore.briefing && $routeStore.briefing !== prevBriefing) {
    prevBriefing = $routeStore.briefing;
    activeMobileTab = 'results';
    snapTo('peek');
  }

  // Also auto-minimize immediately when loading starts after clicking Plan My Ride
  let prevLoading = false;
  $: if ($routeStore.loading && !prevLoading) {
    prevLoading = true;
    snapTo('peek');
  } else if (!$routeStore.loading) {
    prevLoading = false;
  }

  function updateSnapHeights() {
    if (typeof window === 'undefined') return;
    const h = window.innerHeight;

    // Dynamically calculate form height so Plan My Ride is snug at the bottom
    let formH = 400;
    if (sheetBodyEl) {
      const formEl = sheetBodyEl.querySelector('.gm-panel') || sheetBodyEl.firstElementChild;
      const headerH = sheetHeaderEl ? sheetHeaderEl.offsetHeight : 64;
      if (formEl && formEl.offsetHeight > 100) {
        formH = headerH + formEl.offsetHeight + 10;
      }
    }

    snapHeights = {
      peek: 74,
      half: Math.round(h * 0.50),
      form: Math.min(Math.round(h * 0.85), formH),
      expanded: Math.round(h * 0.88),
    };
    if (!isDragging) {
      sheetHeight = snapHeights[currentSnap] || snapHeights.form;
    }
  }

  onMount(() => {
    updateSnapHeights();
    setTimeout(updateSnapHeights, 100);
    window.addEventListener('resize', updateSnapHeights);
    return () => window.removeEventListener('resize', updateSnapHeights);
  });

  function snapTo(snap) {
    currentSnap = snap;
    updateSnapHeights();
    sheetHeight = snapHeights[snap] || snapHeights.half;
  }

  function toggleSheet() {
    if (currentSnap === 'peek') {
      snapTo(activeMobileTab === 'plan' ? 'form' : 'half');
    } else {
      snapTo('peek');
    }
  }

  function setTab(tab) {
    activeMobileTab = tab;
    if (tab === 'plan') {
      setTimeout(updateSnapHeights, 50);
      snapTo('form');
    } else {
      if (currentSnap === 'peek') {
        snapTo('half');
      }
    }
  }

  // Pointer drag on handle / header
  function onPointerDown(e) {
    if (e.button !== 0 && e.pointerType === 'mouse') return;
    isDragging = true;
    hasMoved = false;
    startY = e.clientY;
    startHeight = sheetHeight;
    lastY = e.clientY;
    lastTime = performance.now();
    velocityY = 0;
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {}
  }

  function onPointerMove(e) {
    if (!isDragging) return;
    const deltaY = startY - e.clientY; // upward drag increases height
    if (Math.abs(deltaY) > 4) {
      hasMoved = true;
    }
    const now = performance.now();
    const dt = now - lastTime;
    if (dt > 0) {
      velocityY = (e.clientY - lastY) / dt; // positive = moving DOWN
      lastY = e.clientY;
      lastTime = now;
    }
    const minH = snapHeights.peek;
    const maxH = snapHeights.expanded;
    sheetHeight = Math.max(minH, Math.min(maxH, startHeight + deltaY));
  }

  function onPointerUp(e) {
    if (!isDragging) return;
    isDragging = false;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {}

    if (!hasMoved) {
      toggleSheet();
      return;
    }

    const peekH = snapHeights.peek;
    const midH  = activeMobileTab === 'plan' ? snapHeights.form : snapHeights.half;
    const expH  = snapHeights.expanded;

    // Velocity-based quick flick
    if (velocityY > 0.4) {
      // Swiped DOWN
      if (sheetHeight > midH + 40) snapTo(activeMobileTab === 'plan' ? 'form' : 'half');
      else snapTo('peek');
    } else if (velocityY < -0.4) {
      // Swiped UP
      if (sheetHeight < midH - 40) snapTo(activeMobileTab === 'plan' ? 'form' : 'half');
      else snapTo('expanded');
    } else {
      // Snap to nearest position
      const dPeek = Math.abs(sheetHeight - peekH);
      const dMid  = Math.abs(sheetHeight - midH);
      const dExp  = Math.abs(sheetHeight - expH);
      const minD = Math.min(dPeek, dMid, dExp);
      if (minD === dPeek) snapTo('peek');
      else if (minD === dMid) snapTo(activeMobileTab === 'plan' ? 'form' : 'half');
      else snapTo('expanded');
    }
  }

  // Touch pull down from top of scroll in sheet body
  let bodyStartY = 0;
  let bodyCanPull = false;

  function onBodyTouchStart(e) {
    const el = e.currentTarget;
    if (el.scrollTop <= 0) {
      bodyCanPull = true;
      bodyStartY = e.touches[0].clientY;
    } else {
      bodyCanPull = false;
    }
  }

  function onBodyTouchMove(e) {
    if (!bodyCanPull) return;
    const currentY = e.touches[0].clientY;
    const dy = currentY - bodyStartY;
    if (dy > 45 && currentSnap !== 'peek') {
      bodyCanPull = false;
      if (currentSnap === 'expanded') snapTo('half');
      else snapTo('peek');
    }
  }
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

  <!-- ── MOBILE: Draggable Bottom Sheet ── -->
  <div
    class="mobile-sheet mobile-only"
    class:animating={!isDragging}
    style="height: {sheetHeight}px;"
  >
    <!-- Draggable Header Area -->
    <div
      class="sheet-header"
      bind:this={sheetHeaderEl}
      on:pointerdown={onPointerDown}
      on:pointermove={onPointerMove}
      on:pointerup={onPointerUp}
      on:pointercancel={onPointerUp}
      role="region"
      aria-label="Drag sheet"
    >
      <div class="sheet-handle-bar">
        <div class="sheet-handle"></div>
      </div>

      {#if $routeStore.briefing}
        <!-- Tab switcher for mobile -->
        <div class="mobile-tabs" on:pointerdown|stopPropagation>
          <button
            class="mobile-tab"
            class:active={activeMobileTab === 'plan'}
            on:click|stopPropagation={() => setTab('plan')}
          >🗺️ Plan</button>
          <button
            class="mobile-tab"
            class:active={activeMobileTab === 'results'}
            on:click|stopPropagation={() => setTab('results')}
          >📊 Results</button>
        </div>
      {:else}
        <div class="sheet-title-peek">
          <span class="sheet-title-text">🏍️ Plan Your Ride</span>
          <span class="sheet-drag-hint">{currentSnap === 'peek' ? '▲ Drag up' : '▼ Drag down to map'}</span>
        </div>
      {/if}
    </div>

    <!-- Sheet content: scrollable -->
    <div
      class="sheet-body"
      class:is-plan={activeMobileTab === 'plan'}
      bind:this={sheetBodyEl}
      on:touchstart={onBodyTouchStart}
      on:touchmove={onBodyTouchMove}
    >
      {#if $routeStore.briefing}
        {#if activeMobileTab === 'results'}
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

  /* ── DESKTOP PANELS (UNTOUCHED) ── */
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
  .desktop-only { display: flex; }
  .mobile-only  { display: none; }

  /* ── MOBILE DRAGGABLE BOTTOM SHEET ── */
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
    border-top-left-radius: 22px;
    border-top-right-radius: 22px;
    box-shadow: 0 -8px 40px rgba(0, 0, 0, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.9);
    overflow: hidden;
    touch-action: none;
  }

  .mobile-sheet.animating {
    transition: height 0.32s cubic-bezier(0.25, 1, 0.5, 1);
  }

  .sheet-header {
    width: 100%;
    padding: 8px 14px 6px;
    display: flex;
    flex-direction: column;
    align-items: center;
    cursor: grab;
    user-select: none;
    touch-action: none;
    flex-shrink: 0;
    background: rgba(255, 255, 255, 0.98);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-bottom: 1px solid rgba(0, 0, 0, 0.05);
    z-index: 2;
  }
  .sheet-header:active {
    cursor: grabbing;
  }

  .sheet-handle-bar {
    width: 100%;
    display: flex;
    justify-content: center;
    padding: 2px 0 6px;
  }

  .sheet-handle {
    width: 42px;
    height: 4px;
    background: rgba(148, 163, 184, 0.6);
    border-radius: 99px;
    transition: background 0.2s;
  }

  .sheet-header:hover .sheet-handle {
    background: rgba(100, 116, 139, 0.8);
  }

  .sheet-title-peek {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 2px 4px 4px;
  }

  .sheet-title-text {
    font-size: 13px;
    font-weight: 700;
    color: #0f172a;
  }

  .sheet-drag-hint {
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
  }

  /* Mobile tab switcher */
  .mobile-tabs {
    width: 100%;
    display: flex;
    gap: 6px;
    margin-top: 2px;
    margin-bottom: 2px;
    background: rgba(241, 245, 249, 0.95);
    border-radius: 10px;
    padding: 3px;
    box-sizing: border-box;
  }

  .mobile-tab {
    flex: 1;
    padding: 7px 12px;
    background: transparent;
    border: none;
    border-radius: 7px;
    font-size: 12px;
    font-weight: 700;
    font-family: var(--font-ui);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.18s ease;
    text-align: center;
  }

  .mobile-tab.active {
    background: #ffffff;
    color: var(--accent-orange);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .sheet-body {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 0 12px 24px;
    padding-bottom: calc(24px + env(safe-area-inset-bottom, 0px));
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
    touch-action: pan-y;
  }
  .sheet-body.is-plan {
    padding: 0 12px 6px;
    padding-bottom: calc(6px + env(safe-area-inset-bottom, 0px));
    overflow-y: hidden;
  }
  .sheet-body::-webkit-scrollbar { display: none; }

  @media (max-width: 639px) {
    .desktop-only { display: none !important; }
    .mobile-only  { display: flex !important; }

    /* On mobile, center loading pill in visible map area */
    .loading-overlay {
      align-items: flex-start;
      padding-top: 80px;
      padding-bottom: 0;
    }
  }
</style>

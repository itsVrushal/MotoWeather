<script>
  import { onMount, onDestroy, setContext } from 'svelte';
  import * as maplibregl from 'maplibre-gl';

  import 'maplibre-gl/dist/maplibre-gl.css';

  /** @type {maplibregl.Map | null} */
  let map = null;
  let mapContainer;

  // Maharashtra bounding box: SW [15.6, 72.6] → NE [22.1, 80.9]
  const MH_BOUNDS = [[72.6, 15.6], [80.9, 22.1]];
  const MH_CENTER = [76.5, 19.0];

  setContext('map', {
    getMap: () => map,
  });

  onMount(() => {
    if (!mapContainer) return;

    map = new maplibregl.Map({
      container: mapContainer,
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center: MH_CENTER,
      zoom: 6.5,
      maxBounds: [[68.0, 12.0], [85.0, 26.0]],
      attributionControl: true,
    });

    map.addControl(new maplibregl.NavigationControl(), 'bottom-right');
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');

    map.fitBounds(MH_BOUNDS, { padding: 40, duration: 1200 });

    // Handle container resize
    const ro = new ResizeObserver(() => {
      if (map) map.resize();
    });
    ro.observe(mapContainer);
    map._resizeObserver = ro;
  });

  onDestroy(() => {
    map?._resizeObserver?.disconnect();
    map?.remove();
    map = null;
  });
</script>

<div class="map-wrapper">
  <div bind:this={mapContainer} class="map-canvas"></div>
  {#if map}
    <slot />
  {/if}
</div>

<style>
  .map-wrapper {
    position: relative;
    width: 100%;
    height: 100%;
  }

  .map-canvas {
    width: 100%;
    height: 100%;
  }
</style>
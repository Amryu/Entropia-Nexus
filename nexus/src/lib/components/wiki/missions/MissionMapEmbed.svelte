<!--
  @component MissionMapEmbed
  A compact embedded map showing mission objective locations with optional path drawing.

  Shows:
  - Objective markers numbered by step/sequence
  - Path lines connecting sequential objectives
  - Mini zoom controls
  - Click to expand to full map (opens new tab)
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import { encodeURIComponentSafe } from '$lib/util';

  /** @type {Array<{stepIndex: number, title?: string, coordinates: {Longitude: number, Latitude: number, Altitude?: number}, type: string, planetId?: number}>} */
  export let objectives = [];

  /** @type {{Id: number, Name: string, TechnicalName?: string, X?: number, Y?: number, Width?: number, Height?: number}} */
  export let planet = null;

  /** @type {boolean} Whether to draw path lines between objectives */
  export let showPath = true;

  /** @type {number} Height of the embed in pixels */
  export let height = 280;

  /** @type {string} Optional title for the map section */
  export let title = 'Mission Objectives';

  // Canvas and rendering state
  let canvas;
  let ctx;
  let container;
  let mapImage = null;
  let mapLoaded = false;
  let viewScale = 1;
  let viewX = 0;
  let viewY = 0;
  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let animationFrameId;

  // Planet map bounds (from planet data or defaults for Calypso)
  $: mapBounds = planet?.X != null ? {
    x: planet.X,
    y: planet.Y,
    width: planet.Width || 100000,
    height: planet.Height || 100000
  } : { x: 0, y: 0, width: 100000, height: 100000 };

  // Get map image URL based on planet
  $: mapImageUrl = planet?.TechnicalName
    ? `/maps/${planet.TechnicalName}.jpg`
    : planet?.Name
      ? `/maps/Planet_${planet.Name}.jpg`
      : '/maps/Planet_Calypso.jpg';

  // Compute bounds of all objectives for auto-centering
  $: objectiveBounds = (() => {
    if (!objectives.length) return null;
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;

    for (const obj of objectives) {
      if (obj.coordinates?.Longitude != null && obj.coordinates?.Latitude != null) {
        minX = Math.min(minX, obj.coordinates.Longitude);
        maxX = Math.max(maxX, obj.coordinates.Longitude);
        minY = Math.min(minY, obj.coordinates.Latitude);
        maxY = Math.max(maxY, obj.coordinates.Latitude);
      }
    }

    if (minX === Infinity) return null;

    // Add padding (10% of range or minimum 2000 units)
    const padding = Math.max(2000, Math.max(maxX - minX, maxY - minY) * 0.15);
    return {
      minX: minX - padding,
      maxX: maxX + padding,
      minY: minY - padding,
      maxY: maxY + padding,
      centerX: (minX + maxX) / 2,
      centerY: (minY + maxY) / 2
    };
  })();

  // Colors for different objective types
  const objectiveColors = {
    Dialog: '#4ade80',        // Green
    KillCount: '#ef4444',     // Red
    KillCycle: '#f97316',     // Orange
    Explore: '#3b82f6',       // Blue
    Interact: '#a855f7',      // Purple
    HandIn: '#eab308',        // Yellow
    CraftSuccess: '#06b6d4',  // Cyan
    CraftAttempt: '#06b6d4',  // Cyan
    CraftCycle: '#06b6d4',    // Cyan
    MiningCycle: '#d97706',   // Amber
    MiningClaim: '#d97706',   // Amber
    MiningPoints: '#d97706',  // Amber
    Collect: '#10b981',       // Emerald
    default: '#ffffff'        // White
  };

  const pathColor = 'rgba(74, 158, 255, 0.6)';
  const pathWidth = 3;

  // Convert game coordinates to canvas coordinates
  function gameToCanvas(longitude, latitude) {
    if (!mapImage || !canvas) return { x: 0, y: 0 };

    const imgWidth = mapImage.naturalWidth || mapImage.width;
    const imgHeight = mapImage.naturalHeight || mapImage.height;

    // Game coords to normalized (0-1)
    const nx = (longitude - mapBounds.x) / mapBounds.width;
    const ny = 1 - (latitude - mapBounds.y) / mapBounds.height; // Y is inverted

    // Normalized to image coords
    const imgX = nx * imgWidth;
    const imgY = ny * imgHeight;

    // Image to canvas coords (with view transform)
    const canvasX = (imgX * viewScale) + viewX;
    const canvasY = (imgY * viewScale) + viewY;

    return { x: canvasX, y: canvasY };
  }

  // Initialize view to center on objectives
  function centerOnObjectives() {
    if (!canvas || !mapImage || !objectiveBounds) return;

    const imgWidth = mapImage.naturalWidth || mapImage.width;
    const imgHeight = mapImage.naturalHeight || mapImage.height;
    const canvasWidth = canvas.width / (window.devicePixelRatio || 1);
    const canvasHeight = canvas.height / (window.devicePixelRatio || 1);

    // Calculate the image region containing all objectives
    const nx1 = (objectiveBounds.minX - mapBounds.x) / mapBounds.width;
    const nx2 = (objectiveBounds.maxX - mapBounds.x) / mapBounds.width;
    const ny1 = 1 - (objectiveBounds.maxY - mapBounds.y) / mapBounds.height;
    const ny2 = 1 - (objectiveBounds.minY - mapBounds.y) / mapBounds.height;

    const regionWidth = (nx2 - nx1) * imgWidth;
    const regionHeight = (ny2 - ny1) * imgHeight;
    const regionCenterX = ((nx1 + nx2) / 2) * imgWidth;
    const regionCenterY = ((ny1 + ny2) / 2) * imgHeight;

    // Calculate scale to fit region in canvas with some margin
    const scaleX = canvasWidth / (regionWidth * 1.2);
    const scaleY = canvasHeight / (regionHeight * 1.2);
    viewScale = Math.min(scaleX, scaleY, 2); // Cap at 2x zoom

    // Center the view
    viewX = (canvasWidth / 2) - (regionCenterX * viewScale);
    viewY = (canvasHeight / 2) - (regionCenterY * viewScale);
  }

  // Draw the map and objectives
  function draw() {
    if (!ctx || !canvas) return;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.width / dpr;
    const height = canvas.height / dpr;

    // Clear
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.scale(dpr, dpr);

    // Draw map image
    if (mapImage && mapLoaded) {
      ctx.drawImage(
        mapImage,
        viewX, viewY,
        mapImage.naturalWidth * viewScale,
        mapImage.naturalHeight * viewScale
      );
    } else {
      // Loading placeholder
      ctx.fillStyle = '#1a1a2e';
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = '#666';
      ctx.font = '14px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('Loading map...', width / 2, height / 2);
    }

    // Draw path lines between sequential objectives
    if (showPath && objectives.length > 1) {
      ctx.strokeStyle = pathColor;
      ctx.lineWidth = pathWidth;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.setLineDash([8, 4]);

      ctx.beginPath();
      let started = false;

      // Sort by step index and draw path
      const sorted = [...objectives]
        .filter(o => o.coordinates?.Longitude != null)
        .sort((a, b) => a.stepIndex - b.stepIndex);

      for (const obj of sorted) {
        const pos = gameToCanvas(obj.coordinates.Longitude, obj.coordinates.Latitude);
        if (!started) {
          ctx.moveTo(pos.x, pos.y);
          started = true;
        } else {
          ctx.lineTo(pos.x, pos.y);
        }
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw objective markers
    for (const obj of objectives) {
      if (obj.coordinates?.Longitude == null) continue;

      const pos = gameToCanvas(obj.coordinates.Longitude, obj.coordinates.Latitude);
      const color = objectiveColors[obj.type] || objectiveColors.default;
      const radius = 12;

      // Outer ring
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, radius + 3, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
      ctx.fill();

      // Main circle
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Step number
      ctx.fillStyle = '#000';
      ctx.font = 'bold 11px system-ui';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(obj.stepIndex + 1), pos.x, pos.y);
    }

    ctx.restore();
  }

  // Handle mouse/touch events for panning
  function handlePointerDown(e) {
    isDragging = true;
    dragStartX = e.clientX - viewX;
    dragStartY = e.clientY - viewY;
    canvas.style.cursor = 'grabbing';
  }

  function handlePointerMove(e) {
    if (!isDragging) return;
    viewX = e.clientX - dragStartX;
    viewY = e.clientY - dragStartY;
    draw();
  }

  function handlePointerUp() {
    isDragging = false;
    if (canvas) canvas.style.cursor = 'grab';
  }

  // Handle zoom
  function handleWheel(e) {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newScale = Math.max(0.3, Math.min(5, viewScale * delta));

    // Zoom toward mouse position
    viewX = mouseX - (mouseX - viewX) * (newScale / viewScale);
    viewY = mouseY - (mouseY - viewY) * (newScale / viewScale);
    viewScale = newScale;

    draw();
  }

  function zoomIn() {
    const centerX = canvas.width / (2 * (window.devicePixelRatio || 1));
    const centerY = canvas.height / (2 * (window.devicePixelRatio || 1));
    const newScale = Math.min(5, viewScale * 1.3);
    viewX = centerX - (centerX - viewX) * (newScale / viewScale);
    viewY = centerY - (centerY - viewY) * (newScale / viewScale);
    viewScale = newScale;
    draw();
  }

  function zoomOut() {
    const centerX = canvas.width / (2 * (window.devicePixelRatio || 1));
    const centerY = canvas.height / (2 * (window.devicePixelRatio || 1));
    const newScale = Math.max(0.3, viewScale / 1.3);
    viewX = centerX - (centerX - viewX) * (newScale / viewScale);
    viewY = centerY - (centerY - viewY) * (newScale / viewScale);
    viewScale = newScale;
    draw();
  }

  function resetView() {
    centerOnObjectives();
    draw();
  }

  // Open full map
  function openFullMap() {
    if (!planet?.Name) return;
    const slug = encodeURIComponentSafe(planet.Name.toLowerCase());
    window.open(`/maps/${slug}`, '_blank');
  }

  // Setup canvas
  function setupCanvas() {
    if (!canvas || !container) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    ctx = canvas.getContext('2d');

    if (mapLoaded) {
      centerOnObjectives();
      draw();
    }
  }

  // Load map image
  function loadMapImage() {
    if (!browser) return;

    mapImage = new Image();
    mapImage.onload = () => {
      mapLoaded = true;
      centerOnObjectives();
      draw();
    };
    mapImage.onerror = () => {
      console.warn('Failed to load map image:', mapImageUrl);
      mapLoaded = false;
      draw();
    };
    mapImage.src = mapImageUrl;
  }

  onMount(() => {
    setupCanvas();
    loadMapImage();

    const resizeObserver = new ResizeObserver(() => {
      setupCanvas();
    });
    if (container) resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
    };
  });

  onDestroy(() => {
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
  });

  // Reload map when planet changes
  $: if (browser && mapImageUrl) {
    loadMapImage();
  }
</script>

{#if objectives.length > 0}
  <div class="mission-map-embed" style="height: {height}px">
    {#if title}
      <div class="map-header">
        <h4 class="map-title">{title}</h4>
        <div class="map-controls">
          <button class="zoom-btn" on:click={zoomIn} title="Zoom in">+</button>
          <button class="zoom-btn" on:click={zoomOut} title="Zoom out">-</button>
          <button class="zoom-btn" on:click={resetView} title="Reset view">&#8634;</button>
          <button class="expand-btn" on:click={openFullMap} title="Open full map">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="15 3 21 3 21 9"></polyline>
              <polyline points="9 21 3 21 3 15"></polyline>
              <line x1="21" y1="3" x2="14" y2="10"></line>
              <line x1="3" y1="21" x2="10" y2="14"></line>
            </svg>
          </button>
        </div>
      </div>
    {/if}

    <div class="map-container" bind:this={container}>
      <canvas
        bind:this={canvas}
        on:pointerdown={handlePointerDown}
        on:pointermove={handlePointerMove}
        on:pointerup={handlePointerUp}
        on:pointerleave={handlePointerUp}
        on:wheel={handleWheel}
      ></canvas>
    </div>

    <div class="map-legend">
      {#each Object.entries(objectiveColors) as [type, color]}
        {#if type !== 'default'}
          <div class="legend-item">
            <span class="legend-dot" style="background-color: {color}"></span>
            <span class="legend-label">{type}</span>
          </div>
        {/if}
      {/each}
    </div>
  </div>
{/if}

<style>
  .mission-map-embed {
    display: flex;
    flex-direction: column;
    background: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    overflow: hidden;
  }

  .map-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: var(--secondary-color);
    border-bottom: 1px solid var(--border-color, #555);
  }

  .map-title {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .map-controls {
    display: flex;
    gap: 4px;
  }

  .zoom-btn,
  .expand-btn {
    width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    background: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    font-size: 14px;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.15s;
  }

  .zoom-btn:hover,
  .expand-btn:hover {
    background: var(--hover-color);
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }

  .map-container {
    flex: 1;
    position: relative;
    overflow: hidden;
    min-height: 0;
  }

  canvas {
    display: block;
    width: 100%;
    height: 100%;
    cursor: grab;
  }

  canvas:active {
    cursor: grabbing;
  }

  .map-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 6px 12px;
    background: var(--secondary-color);
    border-top: 1px solid var(--border-color, #555);
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 1px solid rgba(255, 255, 255, 0.3);
  }

  .legend-label {
    font-size: 10px;
    color: var(--text-muted, #999);
  }

  @media (max-width: 600px) {
    .map-legend {
      justify-content: center;
    }
  }
</style>

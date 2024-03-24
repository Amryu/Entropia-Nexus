<script>
  //@ts-nocheck

  import { writable } from 'svelte/store';
  import { onMount, onDestroy } from 'svelte';
  import Tooltip from './Tooltip.svelte';
  import { tooltip } from './Tooltip';
  import { navigate } from '$lib/util';
  import ContextMenu from './ContextMenu.svelte';
  import { contextmenu } from './ContextMenu';

  import { pathDataToPolys }  from 'svg-path-to-polygons'

  export let mapName = '';
  export let planet = null;
  export let locations = [];
  export let selected;
  export let hovered;
  export let mapSettings;

  let filteredLocations = [];

  const mapLoadedStore = writable(false);

  let mapLoaded;

  initPromise();

  $: if ($mapLoadedStore === false) {
    initPromise();
  }

  let imageTileSize;
  let imageToEntropiaRatio;
  let entropiaTileSize;

  let imgLoaded = false;

  let mapCenterPos = { x: 0, y: 0 };
  let mousePos = { x: 0, y: 0 };

  let dragging = false;
  $: if (typeof window !== 'undefined') document.documentElement.style.setProperty('--cursorStatus', dragging ? 'grabbing' : 'default');

  let zoom = 1;
  let targetZoom = zoom;
  let zoomTransitionStart = null;
  let zoomAnimationId = null;
  let moveAnimationId = null;
  
  let canvasElement;
  let img;
  let ctx;
  let canvasBounds;
  let drawAnimationId;

  let tooltipElement;
  let tooltipText;
  let wasPositionCopied = false;

  let editMode = false;
  let editType = null;
  let editLocation = null;

  let editDrag = false;

  function initShapeData(e, editLocation) {
    if (e.target.value === 'Circle') {
      editLocation.Properties.Data = {
        x: editLocation.Properties.Coordinates.Longitude ?? 0,
        y: editLocation.Properties.Coordinates.Latitude ?? 0,
        radius: editLocation.Properties.Data.radius ?? 0
      };
    } else if (e.target.value === 'Rectangle') {
      editLocation.Properties.Data = {
        x: editLocation.Properties.Coordinates.Longitude ?? 0,
        y: editLocation.Properties.Coordinates.Latitude ?? 0,
        width: editLocation.Properties.Data.width ?? 500,
        height: editLocation.Properties.Data.height ?? 500
      };
    } else if (e.target.value === 'Polygon') {
      editLocation.Properties._vertices = editLocation.Properties._vertices ?? [];
      editLocation.Properties.Data = { vertices: [] };
    }
  }

  $: if (editLocation?.Properties?.Shape === 'Circle') {
    editLocation.Properties.Coordinates.Longitude = editLocation.Properties.Data.x;
    editLocation.Properties.Coordinates.Latitude = editLocation.Properties.Data.y;
  }

  $: if (editLocation?.Properties?.Shape === 'Polygon') {
    if (!editLocation.Properties._vertices) {
      editLocation.Properties._vertices = [];
    }

    editLocation.Properties.Data.vertices = editLocation.Properties._vertices.flatMap(vertex => {
      return [Math.round(vertex[0] + editLocation.Properties.Coordinates.Longitude), Math.round(vertex[1] + editLocation.Properties.Coordinates.Latitude)];
    });
  }

  $: if (editLocation) {
    if (!locations.find(x => x === editLocation)) {
      locations.push(editLocation);
    }

    locations = locations;
    

    console.log('editLocation:', editLocation)
  }

  let svgContextMenu = [
    { label: 'Copy Waypoint', action: (payload) => copyLocation(payload)},
  ];
  let svgContextMenuElement;
  
  let mapContextMenu = [
    { label: 'Add Location', action: (_, position) => {
      if (editLocation !== null) {
        locations = locations.filter(x => x !== editLocation);
      }
      
      let canvasCoords = windowToCanvasCoords(position.x, position.y);
      let entropiaCoords = canvasCoordsToEntropiaCoords(canvasCoords.x, canvasCoords.y);
      
      editLocation = {
        _isCustom: true,
        Name: 'New Location',
        Planet: planet,
        Properties: {
          Type: 'Teleporter',
          Coordinates: {
            Longitude: Math.round(entropiaCoords.x),
            Latitude: Math.round(entropiaCoords.y),
            Altitude: 100
          },
        }
      };

      editMode = true;
      editType = 'Location';
    }},
    { label: 'Add Area', action: (_, position) => {
      if (editLocation !== null) {
        locations = locations.filter(x => x !== editLocation);
      }

      let canvasCoords = windowToCanvasCoords(position.x, position.y);
      let entropiaCoords = canvasCoordsToEntropiaCoords(canvasCoords.x, canvasCoords.y);
      
      editLocation = {
        _isCustom: true,
        Name: 'New Area',
        Planet: planet,
        Properties: {
          Type: 'LandArea',
          Shape: 'Circle',
          Data: {
            x: Math.round(entropiaCoords.x),
            y: Math.round(entropiaCoords.y),
            radius: 500
          },
          Coordinates: {
            Longitude: Math.round(entropiaCoords.x),
            Latitude: Math.round(entropiaCoords.y),
            Altitude: 100
          }
        }
      };

      editMode = true;
      editType = 'Area';
    }},
    { 
      label: 'Copy Waypoint',
      action: (_, position) => {
        let canvasCoords = windowToCanvasCoords(position.x, position.y);
        let entropiaCoords = canvasCoordsToEntropiaCoords(canvasCoords.x, canvasCoords.y);
        
        navigator.clipboard.writeText(`/wp ${getWaypoint(planet.Properties.TechnicalName ?? planet.Name, entropiaCoords.x.toFixed(0), entropiaCoords.y.toFixed(0), 100, 'Waypoint')}`)
      }
    },
  ];
  let mapContextMenuElement;

  $: if (canvasBounds && mapCenterPos != null && zoom) {
    locations = locations;
  }

  $: if (mapName) reloadImage(mapName);

  $: if (selected) {
    focusOnLocation(selected);
  }

  $: if (mapSettings) {
    filteredLocations = locations.filter(x => {
      if (mapSettings.locations.enabled && !x.Properties.Type.endsWith('Area')) {
        if (mapSettings.locations.teleporters && x.Properties.Type === 'Teleporter') return true;
        if (mapSettings.locations.outposts && x.Properties.Type === 'Outpost') return true;
        if (mapSettings.locations.missions && (x.Properties.Type === 'Mission' || x.Properties.Type === 'Objective')) return true;
      }

      if (mapSettings.areas.enabled && x.Properties.Type.endsWith('Area')) {
        if (mapSettings.areas.landAreas && x.Properties.Type === 'LandArea') return true;
        if (mapSettings.areas.zoneAreas && x.Properties.Type === 'ZoneArea') return true;
        if (mapSettings.areas.pvpAreas && (x.Properties.Type === 'PvpArea' || x.Properties.Type === 'PvpLootArea')) return true;
        if (mapSettings.areas.eventAreas && x.Properties.Type === 'EventArea') return true;
        if (mapSettings.areas.waveEvents && item.Properties?.Type === 'WaveEventArea') return true;
      }

      if (mapSettings.mobs.enabled && x.Properties.Type === 'MobArea') {
        return true;
        if (mapSettings.mobs.rookie && false) return true;
        if (mapSettings.mobs.adept && false) return true;
        if (mapSettings.mobs.intermediate && false) return true;
        if (mapSettings.mobs.expert && false) return true;
        if (mapSettings.mobs.uber && false) return true;
      }

      return false;
    });
  }

  async function focusOnLocation(location) {
    if (typeof window === 'undefined') {
      return;
    }

    console.log('moving to location:', location);

    await mapLoaded;
      
    moveAndZoomTo(entropiaCoordsToImageCoords(location.Properties.Coordinates.Longitude, location.Properties.Coordinates.Latitude), 1/(planet.Properties.Map.Width*0.5));
  }

  let resizeObserver;

  onMount(async () => {
    resizeObserver = new ResizeObserver((entries) => {
        for (let entry of entries) {
          if (entry.target === canvasElement) {
            initCanvas();
          }
        }
      }
    );

    resizeObserver.observe(canvasElement);
  });

  onDestroy(() => {
    if (resizeObserver) {
      resizeObserver.disconnect();
    }
  });
  
  function reloadImage(mapName) {
    if (typeof window === 'undefined') {
      return;
    }

    imgLoaded = false;
    $mapLoadedStore = false;
    img = new Image();
    img.src = `/${mapName.replace(/[^0-9a-zA-Z]/g, '').toLowerCase()}.jpg`;

    img.onload = () => {
      imgLoaded = true;

      mapCenterPos.x = img.width / 2;
      mapCenterPos.y = img.height / 2;
      
      imageTileSize = img.width / planet.Properties.Map.Width;
      imageToEntropiaRatio = 8192 / imageTileSize;
      entropiaTileSize = imageTileSize * imageToEntropiaRatio;

      zoomTransitionStart = null;
      zoom = imageTileSize / img.width;
      targetZoom = zoom;

      $mapLoadedStore = true;
    };
  }

  function initPromise() {
    mapLoaded = new Promise(resolve => {
      const unsubscribe = mapLoadedStore.subscribe(mapLoaded => {
        if (mapLoaded === true) {
          resolve(mapLoaded);
          unsubscribe();
        }
      });
    })
  }

  function clampCoordinates() {
    const minX = 0;
    const minY = 0;
    const maxX = img.width;
    const maxY = img.height;
    mapCenterPos.x = Math.max(minX, Math.min(maxX, mapCenterPos.x));
    mapCenterPos.y = Math.max(minY, Math.min(maxY, mapCenterPos.y));
  }

  function onMouseDown(event) {
    if (event.button === 0) {
      event.preventDefault();
      dragging = true;
      mousePos.x = event.clientX;
      mousePos.y = event.clientY;
    }
  }

  function onMouseMove(event) {
    if (dragging) {
      const visibleImageHeight = imageTileSize / zoom;
      const imagePixelSize = canvasBounds.height / visibleImageHeight;

      const dx = (event.clientX - mousePos.x) * window.devicePixelRatio / imagePixelSize;
      const dy = (event.clientY - mousePos.y) * window.devicePixelRatio / imagePixelSize;
      mousePos.x = event.clientX;
      mousePos.y = event.clientY;

      mapCenterPos.x -= dx;
      mapCenterPos.y -= dy;

      clampCoordinates();
    }
  }

  function onMouseUp() {
    dragging = false;
  }

  function onWheel(event) {
    event.preventDefault();

    // Calculate the new zoom level
    const delta = Math.sign(event.deltaY);
    if (delta < 0) {
      targetZoom *= 11 / 10; // increase zoom
    } else {
      targetZoom *= 10 / 11; // decrease zoom
    }

    // Clamp the zoom level to a minimum and maximum value
    targetZoom = Math.max(imageTileSize / img.width, Math.min(2, targetZoom));

    zoomTo(targetZoom);
  }

  function animateZoom(timestamp, animationDuration = 150) {
    if (zoomTransitionStart === -1) {
      zoomTransitionStart = timestamp;
    }
    if (zoomTransitionStart === null) return;
    if (!$mapLoadedStore) {
      zoomTransitionStart = timestamp;
      zoomAnimationId = requestAnimationFrame((timestamp) => animateZoom(timestamp, animationDuration));
      return;
    }
    
    const progress = Math.min((timestamp - zoomTransitionStart) / animationDuration, 1);
    zoom = zoom + (targetZoom - zoom) * progress;

    if (progress < 1) {
      zoomAnimationId = requestAnimationFrame((timestamp) => animateZoom(timestamp, animationDuration));
    } else {
      zoomTransitionStart = null;
      zoomAnimationId = null;
    }
  }

  function animateMove(timestamp, animationDuration) {
    if (moveTransitionStart === -1) {
      moveTransitionStart = timestamp;
    }
    if (moveTransitionStart === null) return;
    if (!$mapLoadedStore) {
      zoomTransitionStart = timestamp;
      moveAnimationId = requestAnimationFrame((timestamp) => animateMove(timestamp, animationDuration));
      return;
    }
    
    const progress = Math.min((timestamp - moveTransitionStart) / animationDuration, 1);
    mapCenterPos.x = mapCenterPos.x + (target.x - mapCenterPos.x) * progress;
    mapCenterPos.y = mapCenterPos.y + (target.y - mapCenterPos.y) * progress;

    clampCoordinates();

    if (progress < 1) {
      moveAnimationId = requestAnimationFrame((timestamp) => animateMove(timestamp, animationDuration));
    } else {
      moveTransitionStart = null;
      moveAnimationId = null;
    }
  }

  let target = null;
  let moveTransitionStart = null;

  function moveTo(position, animationDuration = 150) {
    target = position;

    moveTransitionStart = -1;

    if (moveAnimationId != null) {
      cancelAnimationFrame(moveAnimationId);
      moveAnimationId = null;
    }

    moveAnimationId = requestAnimationFrame((timestamp) => animateMove(timestamp, animationDuration));
  }

  function zoomTo(zoom, animationDuration = 50) {
    targetZoom = zoom;

    zoomTransitionStart = -1;

    if (zoomAnimationId != null) {
      cancelAnimationFrame(zoomAnimationId);
      zoomAnimationId = null;
    }

    zoomAnimationId = requestAnimationFrame((timestamp) => animateZoom(timestamp, animationDuration));
  }

  function moveAndZoomTo(position, zoom, animationDuration = 300) {
    moveTo(position, animationDuration);
    zoomTo(zoom, animationDuration);
  }

  function initCanvas() {
    canvasBounds = canvasElement.getBoundingClientRect();

    canvasElement.width = canvasBounds.width * window.devicePixelRatio;
    canvasElement.height = canvasBounds.height * window.devicePixelRatio;

    ctx = canvasElement.getContext('2d');
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    if (drawAnimationId != null) {
      cancelAnimationFrame(drawAnimationId);
      drawAnimationId = null;
    }
    
    draw();
  }

  function draw() {
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, canvasBounds.width, canvasBounds.height);

    if (!imgLoaded) {
      drawAnimationId = requestAnimationFrame(draw);

      return;
    }

    // Calculate the visible height and width of the image based on the zoom level
    const visibleHeight = imageTileSize / zoom;
    const visibleWidth = (canvasBounds.width / canvasBounds.height) * visibleHeight;

    // Calculate the source and destination coordinates and dimensions
    const srcX = mapCenterPos.x - visibleWidth / 2;
    const srcY = mapCenterPos.y - visibleHeight / 2;
    const destX = 0;
    const destY = 0;
    const destWidth = canvasBounds.width;
    const destHeight = (visibleHeight / visibleWidth) * destWidth;

    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, srcX, srcY, visibleWidth, visibleHeight, destX, destY, destWidth, destHeight);

    if (mapSettings.settings.showGrid) drawGrid(ctx);

    drawAnimationId = requestAnimationFrame(draw);
  }

  function drawGrid(ctx) {
    const visibleHeight = imageTileSize / zoom;
    const visibleWidth = (canvasBounds.width / canvasBounds.height) * visibleHeight;

    const srcX = mapCenterPos.x - visibleWidth / 2;
    const srcY = mapCenterPos.y - visibleHeight / 2;

    const gridStep = imageTileSize;
    const gridColor = 'rgba(255, 255, 255, 0.3)';
    const gridWidth = 1;

    ctx.strokeStyle = gridColor;
    ctx.lineWidth = gridWidth;

    const gridStartX = Math.floor(srcX / gridStep) * gridStep;
    const gridStartY = Math.floor(srcY / gridStep) * gridStep;

    for (let x = gridStartX; x < srcX + visibleWidth; x += gridStep) {
      const canvasX = (x - srcX) * (canvasBounds.width / visibleWidth);
      ctx.beginPath();
      ctx.moveTo(canvasX, 0);
      ctx.lineTo(canvasX, canvasBounds.height);
      ctx.stroke();
    }

    for (let y = gridStartY; y < srcY + visibleHeight; y += gridStep) {
      const canvasY = (y - srcY) * (canvasBounds.height / visibleHeight);
      ctx.beginPath();
      ctx.moveTo(0, canvasY);
      ctx.lineTo(canvasBounds.width, canvasY);
      ctx.stroke();
    }
  }

  function entropiaCoordsToImageCoords(entropiaX, entropiaY) {
    const planetOffsetX = planet.Properties.Map.X * entropiaTileSize;
    const planetOffsetY = planet.Properties.Map.Y * entropiaTileSize;
    const planetHeight = planet.Properties.Map.Height * entropiaTileSize;

    return {
      x: (entropiaX - planetOffsetX) / imageToEntropiaRatio,
      y: (planetHeight - (entropiaY - planetOffsetY)) / imageToEntropiaRatio,
    };
  }

  function imageCoordsToEntropiaCoords(imageX, imageY) {
    const planetOffsetX = planet.Properties.Map.X * entropiaTileSize;
    const planetOffsetY = planet.Properties.Map.Y * entropiaTileSize;
    const planetHeight = planet.Properties.Map.Height * entropiaTileSize;

    return {
      x: imageX * imageToEntropiaRatio + planetOffsetX,
      y: planetHeight - (imageY * imageToEntropiaRatio) + planetOffsetY,
    };
  }

  function imageCoordsToCanvasCoords(imageX, imageY) {
    const visibleHeight = imageTileSize / zoom;
    const visibleWidth = (canvasBounds.width / canvasBounds.height) * visibleHeight;

    // Calculate the source and destination coordinates and dimensions
    const srcX = mapCenterPos.x - visibleWidth / 2;
    const srcY = mapCenterPos.y - visibleHeight / 2;

    // Transform the image coordinates to canvas coordinates
    const canvasX = (imageX - srcX) * (canvasBounds.width / visibleWidth);
    const canvasY = (imageY - srcY) * (canvasBounds.height / visibleHeight);

    return { x: canvasX, y: canvasY };
  }

  function canvasCoordsToImageCoords(canvasX, canvasY) {
    const visibleHeight = imageTileSize / zoom;
    const visibleWidth = (canvasBounds.width / canvasBounds.height) * visibleHeight;

    // Calculate the source and destination coordinates and dimensions
    const srcX = mapCenterPos.x - visibleWidth / 2;
    const srcY = mapCenterPos.y - visibleHeight / 2;

    // Transform the canvas coordinates to image coordinates
    const imageX = srcX + (canvasX / canvasBounds.width) * visibleWidth;
    const imageY = srcY + (canvasY / canvasBounds.height) * visibleHeight;

    return { x: imageX, y: imageY };
  }

  function entropiaCoordsToCanvasCoords(entropiaX, entropiaY) {
    const imageCoords = entropiaCoordsToImageCoords(entropiaX, entropiaY);
    return imageCoordsToCanvasCoords(imageCoords.x, imageCoords.y);
  }

  function canvasCoordsToEntropiaCoords(canvasX, canvasY) {
    const imageCoords = canvasCoordsToImageCoords(canvasX, canvasY);
    return imageCoordsToEntropiaCoords(imageCoords.x, imageCoords.y);
  }

  function windowToCanvasCoords(windowX, windowY) {
    if (typeof window === 'undefined') {
      return { x: 0, y: 0 };
    }

    const rect = canvasElement.getBoundingClientRect();
    return {
      x: (windowX - rect.left) * window.devicePixelRatio,
      y: (windowY - rect.top) * window.devicePixelRatio,
    };
  }

  function canvasToWindowCoords(canvasX, canvasY) {
    if (typeof window === 'undefined') {
      return { x: 0, y: 0 };
    }

    const rect = canvasElement.getBoundingClientRect();
    return {
      x: canvasX / window.devicePixelRatio + rect.left,
      y: canvasY / window.devicePixelRatio + rect.top,
    };
  }

  function getAreas(locations) {
    return locations.filter(x => x.Properties.Type.endsWith('Area'));
  }

  function getTooltipText(object) {
    return `${object.Name} - <span style="color: gray;">(${wasPositionCopied ? 'Copied!' : 'Right-click to copy'})</span><br />${getWaypointFromLocation(object)}`;
  }

  function copyLocation(object) {
    navigator.clipboard.writeText(`/wp ${getWaypointFromLocation(object)}`);
  }

  function getWaypointFromLocation(location) {
    return `/wp ${getWaypoint(location.Planet.Properties.TechnicalName ?? location.Planet.Name, location.Properties.Coordinates.Longitude, location.Properties.Coordinates.Latitude, location.Properties.Coordinates.Altitude, location.Name)}`;
  }

  function getWaypoint(planet, x, y, z, name) {
    return `[${planet}, ${x}, ${y}, ${z}, ${name}]`;
  }

  function getColorByType(type) {
    switch (type) {
      case 'Teleporter':
        return { color: 'aqua', pattern: null };
      case 'LandArea':
        return { color: 'green', pattern: null };
      case 'ZoneArea':
        return { color: 'blue', pattern: null };
      case 'PvpLootArea':
        return { color: 'red', pattern: null };
      case 'PvpArea':
        return { color: 'orange', pattern: null };
      case 'Creature':
        return { color: 'yellow', pattern: null };
      case 'EventArea':
        return { color: 'white', pattern: null };
      case 'WaveEventArea':
        return { color: 'purple', pattern: null };
      case 'MobArea':
        return { color: 'yellow', pattern: null };
      default:
        return 'white';
    }
  }

  function handleSvgImport(event) {
    const file = event.target.files[0];
    const reader = new FileReader();

    reader.onload = function(e) {
      const svg = e.target.result;
      const parser = new DOMParser();
      const doc = parser.parseFromString(svg, 'image/svg+xml');
      const svgElement = doc.querySelector('svg');
      const paths = svgElement.querySelectorAll('path');

      if (paths.length !== 1) {
        throw new Error('Expected exactly one path in the SVG');
      }

      // Convert svg path to absolute coordinates
      const path = paths[0];

      const pathData = path.getAttribute('d');

      let vertices = pathDataToPolys(pathData, { decimals: 0 })[0];

      editLocation.Properties._vertices = vertices;
    };

    reader.readAsText(file);
  }

  let mapContextMenuObject = { contextMenu: null, payload: null }

  $: mapContextMenuObject = { contextMenu: mapContextMenuElement, payload: null }
</script>

<style>
  canvas {
    width: 100%;
    height: 100%;
    cursor: var(--cursorStatus);
    user-select: none;
  }

  .map-container {
    padding: 0;
    height: 100%;
    width: 100%;
    position: relative;
  }

  .map-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    pointer-events: none;
  }

  .map-overlay > * {
    pointer-events: auto;
    cursor: pointer;
  }

  .map-overlay.dragging > * {
    pointer-events: none;
  }

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }

  .blinking-drop-shadow {
    animation: blink 1s infinite;
  }

  @keyframes -global-pulse {
    0%, 100% { transform: 1; }
    50% { transform: 1.5; }
  }

  .location-hovered {
    fill: blue;
  }

  .location-selected {
    fill: yellow;
  }

  .edit-window {
    z-index: 100;
    position: absolute;
    bottom: 10px;
    right: 10px;
    background-color: var(--secondary-color);
    padding: 6px;
    border: 1px solid var(--text-color);
    display: none;
    width: 200px;
    grid-template-columns: repeat(max-content 1fr);
  }
</style>

<Tooltip
  bind:this={tooltipElement}
  bind:text={tooltipText}
  on:show={(e) => tooltipText = getTooltipText(e.detail.payload)}
  on:hide={() => wasPositionCopied = false}
  on:elementClick={(e) => {
    if (e.detail.button === 0) {
      navigate(`/maps/${planet.Name.replace(/[^0-9a-zA-Z]/, '').toLowerCase()}/${e.detail.payload.Name}`);
    }
  }} />
<ContextMenu
  bind:this={svgContextMenuElement}
  menu={svgContextMenu} />
<ContextMenu
  bind:this={mapContextMenuElement}
  menu={mapContextMenu} />
<div class="map-container">
  <canvas use:contextmenu={mapContextMenuObject} bind:this={canvasElement} on:mousedown={onMouseDown} on:mousemove={onMouseMove} on:mouseup={onMouseUp} on:mouseleave={onMouseUp} on:wheel={onWheel}>
  </canvas>
  <!-- EDITOR START -->
  {#if editMode && editLocation}
  <div class="edit-window" style="display: {editMode ? 'grid' : 'none'};">
    <input style="grid-column: span 2;" type="text" bind:value={editLocation.Name} />
    {#if editType === 'Location'}
      Type:
      <select bind:value={editLocation.Properties.Type}>
        <option>Teleporter</option>
        <option>Outpost</option>
        <option value="Npc">NPC</option>
        <option value="Objective">Mission Objective</option>
        <option>Vendor</option>
        <option>Other</option>
      </select>
      Longitude:
      <input size="1" type="text" bind:value={editLocation.Properties.Coordinates.Longitude} />
      Latitude
      <input size="1" type="text" bind:value={editLocation.Properties.Coordinates.Latitude} />
      Altitude
      <input size="1" type="text" bind:value={editLocation.Properties.Coordinates.Altitude} />
    {:else if editType === 'Area'}
      Type:
      <select bind:value={editLocation.Properties.Type}>
        <option value="LandArea">Land Area</option>
        <option value="ZoneArea">Zone</option>
        <option value="PvpLootArea">Lootable PvP</option>
        <option value="PvpArea">PvP</option>
        <option value="EventArea">Event Area</option>
        <option value="WaveEventArea">Wave Event</option>
        <option value="MobArea">Mob Spawn</option>
      </select>
      Shape:
      <select on:change={(e) => initShapeData(e, editLocation)} bind:value={editLocation.Properties.Shape}>
        <option>Circle</option>
        <option>Rectangle</option>
        <option>Polygon</option>
      </select>
      {#if editLocation.Properties.Shape === 'Circle'}
      Longitude:
      <input type="number" style="width: 70%;" bind:value={editLocation.Properties.Data.x} />
      Latitude:
      <input type="number" style="width: 70%;" bind:value={editLocation.Properties.Data.y} />
      Radius:
      <input type="number" style="width: 70%;" bind:value={editLocation.Properties.Data.radius} />
      {:else if editLocation.Properties.Shape === 'Rectangle'}
      Longitude:
      <input type="number" style="width: 70%;" bind:value={editLocation.Properties.Data.x} />
      Latitude:
      <input type="number" style="width: 70%;" bind:value={editLocation.Properties.Data.y} />
      Width:
      <input type="number" style="width: 70%;" bind:value={editLocation.Properties.Data.width} />
      Height:
      <input type="number" style="width: 70%;" bind:value={editLocation.Properties.Data.height} />
      {:else if editLocation.Properties.Shape === 'Polygon'}
      Longitude:
      <input type="number" style="width: 70%;" bind:value={editLocation.Properties.Coordinates.Longitude} />
      Latitude:
      <input type="number" style="width: 70%;" bind:value={editLocation.Properties.Coordinates.Latitude} />
      Vertices:
      <textarea bind:value={editLocation.Properties._vertices} />
      Import: <input type="file" accept=".svg" on:change={handleSvgImport} />
      {/if}
      Altitude:
      <input type="number" style="width: 70%;" bind:value={editLocation.Properties.Coordinates.Altitude} />
    {/if}

    <button style="grid-column: span 2;" on:click={() => alert('This tool is intended to help adding new map elements. When you hit "Save" you will copy a JSON object, which can be submitted to the Entropia Nexus Discord. I greatly appreciate the help!')}>Help</button>
    <button style="grid-column: span 2;" on:click={() => { locations = locations.filter(location => location !== editLocation); editLocation = null; editMode = false; }}>Cancel and Delete</button>
    <button style="grid-column: span 2;" on:click={() => { navigator.clipboard.writeText(JSON.stringify(editLocation)); locations = locations.filter(location => location !== editLocation); editLocation = null; editMode = false; }}>Save to Clipboard</button>
  </div>
  {/if}
  <!-- EDITOR END -->
  <svg class="map-overlay {dragging ? 'dragging' : ''}" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <pattern id="stripe-lightblue" patternUnits="userSpaceOnUse" width="4" height="4">
        <path d="M-1,1 l2,-2 M0,4 l4,-4 M3,5 l2,-2" style="stroke: lightblue; stroke-width: 3;" />
      </pattern>
      <pattern id="stripe-green" patternUnits="userSpaceOnUse" width="4" height="4">
        <path d="M-1,1 l2,-2 M0,4 l4,-4 M3,5 l2,-2" style="stroke: green; stroke-width: 3;" />
      </pattern>
      <pattern id="stripe-yellow" patternUnits="userSpaceOnUse" width="4" height="4">
        <path d="M-1,1 l2,-2 M0,4 l4,-4 M3,5 l2,-2" style="stroke: yellow; stroke-width: 3;" />
      </pattern>
      <pattern id="stripe-purple" patternUnits="userSpaceOnUse" width="4" height="4">
        <path d="M-1,1 l2,-2 M0,4 l4,-4 M3,5 l2,-2" style="stroke: purple; stroke-width: 3;" />
      </pattern>
      <pattern id="stripe-black" patternUnits="userSpaceOnUse" width="4" height="4">
        <path d="M-1,1 l2,-2 M0,4 l4,-4 M3,5 l2,-2" style="stroke: black; stroke-width: 3;" />
      </pattern>
      <pattern id="wave" patternUnits="userSpaceOnUse" width="10" height="10">
        <path d="M 0 10 C 2.5 0, 7.5 0, 10 10" style="stroke: purple; stroke-width: 3;" />
      </pattern>
    </defs>
    {#if canvasBounds != null && imageTileSize && imgLoaded}
      {#each (getAreas(filteredLocations) ?? [])
        .filter(x => x.Properties.Shape === 'Circle')
        .map(x => { 
          let centerPoint = entropiaCoordsToCanvasCoords(x.Properties.Data.x, x.Properties.Data.y);
          let outerPoint = entropiaCoordsToCanvasCoords(x.Properties.Data.x + x.Properties.Data.radius, x.Properties.Data.y);
          let adjustedRadius = outerPoint.x - centerPoint.x;

          return { 
            ...centerPoint,
            radius: adjustedRadius,
            object: x
          };
        }).filter(x => !isNaN(x.x) && !isNaN(x.y)) as circle (circle.object.Name+','+circle.x+','+circle.y)}
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <!-- svelte-ignore a11y-mouse-events-have-key-events -->
        <circle
          use:tooltip={{ tooltip: tooltipElement, payload: circle.object }}
          use:contextmenu={{ contextMenu: svgContextMenuElement, payload: circle.object }}
          on:mousewheel={onWheel}
          on:mousedown={(e) => {
            editDrag = circle.object === editLocation;
            
            mousePos.x = e.clientX;
            mousePos.y = e.clientY;
          }}
          on:mousemove={(e) => {
            if (!editDrag || !editLocation) {
              return;
            }
            
            let canvasCoords = windowToCanvasCoords(e.clientX, e.clientY);
            let entropiaCoords = canvasCoordsToEntropiaCoords(canvasCoords.x, canvasCoords.y);
  
            editLocation.Properties.Data.x = Math.round(entropiaCoords.x);
            editLocation.Properties.Data.y = Math.round(entropiaCoords.y);
          }}
          on:mouseup={() => editDrag = false}
          cx={circle.x}
          cy={circle.y}
          r={circle.radius}
          fill={getColorByType(circle.object.Properties.Type).color}
          fill-opacity="0.3"
          stroke={getColorByType(circle.object.Properties.Type).color}
          stroke-width="1" />
      {/each}

      {#each (getAreas(filteredLocations) ?? [])
        .filter(x => x.Properties.Shape === 'Rectangle')
        .map(x => {
          let startCoords = entropiaCoordsToCanvasCoords(x.Properties.Data.x, x.Properties.Data.y);
          let endCoords = entropiaCoordsToCanvasCoords(x.Properties.Data.x + x.Properties.Data.width, x.Properties.Data.y + x.Properties.Data.height);
          let width = endCoords.x - startCoords.x;
          let height = startCoords.y - endCoords.y;

          return {
            x: startCoords.x,
            y: startCoords.y - height,
            width: width,
            height: height,
            object: x
          };
        }).filter(x => !isNaN(x.x) && !isNaN(x.y)) as rect (rect.object.Name+','+rect.x+','+rect.y)}
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <!-- svelte-ignore a11y-mouse-events-have-key-events -->
        <rect
        use:tooltip={{ tooltip: tooltipElement, payload: rect.object }}
        use:contextmenu={{ contextMenu: svgContextMenuElement, payload: rect.object }}
        on:mousewheel={onWheel}
        on:mousedown={(e) => {
          editDrag = rect.object === editLocation;
          
          mousePos.x = e.clientX;
          mousePos.y = e.clientY;
        }}
        on:mousemove={(e) => {
          if (!editDrag || !editLocation) {
            return;
          }

          let dx = e.clientX - mousePos.x;
          let dy = e.clientY - mousePos.y;
          mousePos.x = e.clientX;
          mousePos.y = e.clientY;

          let canvasCoords = entropiaCoordsToCanvasCoords(editLocation.Properties.Data.x, editLocation.Properties.Data.y)
          let windowCoords = canvasToWindowCoords(canvasCoords.x, canvasCoords.y);

          windowCoords.x += dx;
          windowCoords.y += dy;

          canvasCoords = windowToCanvasCoords(windowCoords.x, windowCoords.y);
          let entropiaCoords = canvasCoordsToEntropiaCoords(canvasCoords.x, canvasCoords.y);

          editLocation.Properties.Data.x = Math.round(entropiaCoords.x);
          editLocation.Properties.Data.y = Math.round(entropiaCoords.y);
        }}
        on:mouseup={() => editDrag = false}
        x={rect.x}
        y={rect.y}
        width={rect.width}
        height={rect.height}
        fill={getColorByType(rect.object.Properties.Type).color}
        fill-opacity="0.3"
        stroke={getColorByType(rect.object.Properties.Type).color}
        stroke-width="1" />
      {/each}
      
      {#each (getAreas(filteredLocations) ?? [])
        .filter(x => x.Properties.Shape === 'Polygon')
        .map(x => {
          return {
            object: x,
            vertices: (x.Properties.Data.vertices ?? []).reduce((result, value, index, array) => {
              if (index % 2 === 0)
                  result.push([value, array[index + 1]]);
              return result;
            }, []).map(vertex => entropiaCoordsToCanvasCoords(vertex[0], vertex[1]))
          };
        }) as polygon (polygon.object.Name+','+polygon.object.Properties.Coordinates.Longitude+','+polygon.object.Properties.Coordinates.Latitude)}
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <!-- svelte-ignore a11y-mouse-events-have-key-events -->
        <polygon
          use:tooltip={{ tooltip: tooltipElement, payload: polygon.object }}
          use:contextmenu={{ contextMenu: svgContextMenuElement, payload: polygon.object }}
          on:mousewheel={onWheel}
          on:mousedown={(e) => {
            editDrag = polygon.object === editLocation;
            
            mousePos.x = e.clientX;
            mousePos.y = e.clientY;
          }}
          on:mousemove={(e) => {
            if (!editDrag || !editLocation) {
              return;
            }

            let dx = e.clientX - mousePos.x;
            let dy = e.clientY - mousePos.y;
            mousePos.x = e.clientX;
            mousePos.y = e.clientY;

            let canvasCoords = entropiaCoordsToCanvasCoords(editLocation.Properties.Coordinates.Longitude, editLocation.Properties.Coordinates.Latitude)
            let windowCoords = canvasToWindowCoords(canvasCoords.x, canvasCoords.y);

            windowCoords.x += dx;
            windowCoords.y += dy;

            canvasCoords = windowToCanvasCoords(windowCoords.x, windowCoords.y);
            let entropiaCoords = canvasCoordsToEntropiaCoords(canvasCoords.x, canvasCoords.y);

            editLocation.Properties.Coordinates.Longitude = Math.round(entropiaCoords.x);
            editLocation.Properties.Coordinates.Latitude = Math.round(entropiaCoords.y);
          }}
          on:mouseup={() => editDrag = false}
          points={polygon.vertices.map(vertex => `${vertex.x},${vertex.y}`).join(' ')}
          fill={getColorByType(polygon.object.Properties.Type).color}
          fill-opacity="0.3"
          stroke={getColorByType(polygon.object.Properties.Type).color}
          stroke-width="1" />
      {/each}
      
      {#each (filteredLocations ?? [])
        .filter(x => !getAreas(filteredLocations).find(y => x.Name === y.Name && x.Properties.Type === y.Properties.Type))
        .map(x =>  {
          return {
            ...entropiaCoordsToCanvasCoords(x.Properties.Coordinates.Longitude, x.Properties.Coordinates.Latitude),
            object: x
          };
        }).filter(x => !isNaN(x.x) && !isNaN(x.y)) as location}
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <!-- svelte-ignore a11y-mouse-events-have-key-events -->
        {#if location.object.Properties.Type === 'Teleporter'}
          <circle
            use:tooltip={{ tooltip: tooltipElement, payload: location.object }}
            use:contextmenu={{ contextMenu: svgContextMenuElement, payload: location.object }}
            on:mousewheel={onWheel}
            on:mouseover={() => hovered = location.object}
            on:mouseout={() => hovered = null}
            class:location-hovered={hovered?.Name === location.object.Name && hovered !== selected}
            class:location-selected={selected?.Name === location.object.Name}
            cx={location.x}
            cy={location.y}
            r={selected?.Name === location.object.Name || hovered?.Name === location.object.Name ? 6 : 4}
            fill="aqua"
            stroke="red"
            stroke-width=1 />
        {:else}
          <rect
            use:tooltip={{ tooltip: tooltipElement, payload: location.object }}
            use:contextmenu={{ contextMenu: svgContextMenuElement, payload: location.object }}
            on:mousewheel={onWheel}
            on:mouseover={() => hovered = location.object}
            on:mouseout={() => hovered = null}
            class:location-hovered={hovered?.Name === location.object.Name && hovered !== selected}
            class:location-selected={selected?.Name === location.object.Name}
            x={location.x - 5}
            y={location.y - 5}
            width={10}
            height={10}
            fill="white"
            stroke="black"
            stroke-width=1 />
        {/if}
      {/each}
    {/if}
  </svg>
</div>
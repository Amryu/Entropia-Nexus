<script>
  //@ts-nocheck

  import { writable } from 'svelte/store';
  import { onMount, onDestroy } from 'svelte';
  import Tooltip from './Tooltip.svelte';
  import { tooltip } from './Tooltip';
  import { navigate } from '$lib/util';
  import ContextMenu from './ContextMenu.svelte';
  import { contextmenu } from './ContextMenu';

  export let mapName = '';
  export let planet = null;
  export let locations = [];
  export let selected;
  export let hovered;
  export let highlighted = '';

  const mapLoadedStore = writable(false);

  let mapLoaded;

  initPromise();

  $: if ($mapLoadedStore === false) {
    initPromise();
  }

  let mapContextMenu = [
    { label: 'Copy', action: (payload) => copyLocation(payload)},
  ];

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

  let contextMenuElement;

  $: if (selected) {
    focusOnLocation(selected);
  }

  async function focusOnLocation(location) {
    if (typeof window === 'undefined') {
      return;
    }

    console.log('moving to location:', location);

    await mapLoaded;
      
    moveAndZoomTo(entropiaCoordsToImageCoords(location.Properties.Coordinates.Longitude, location.Properties.Coordinates.Latitude), 1/(planet.Properties.Map.Width*0.5));
  }

  $: if (canvasBounds && mapCenterPos != null && zoom) {
    locations = locations;
  }

  $: if (mapName) reloadImage(mapName);

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

  function animateZoom(timestamp, animationDuration = 50) {
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

  function moveTo(position, animationDuration = 50) {
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

    drawAnimationId = requestAnimationFrame(draw);
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

  function getAreas(locations) {
    return locations.filter(x => x.Properties.Type.endsWith('Area'));
  }

  function getTooltipText(object) {
    return `${object.Name} - <span style="color: gray;">(${wasPositionCopied ? 'Copied!' : 'Right-click to copy'})</span><br />${getLocationString(object)}`;
  }

  function copyLocation(object) {
    navigator.clipboard.writeText(`/wp ${getLocationString(object)}`);
  }

  function getLocationString(object) {
    return `[${object.Planet.Properties.TechnicalName ?? object.Planet.Name}, ${object.Properties.Coordinates.Longitude}, ${object.Properties.Coordinates.Latitude}, ${object.Properties.Coordinates.Altitude}, ${object.Name}]`;
  }
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
    else if (e.detail.button === 2) {
      copyTooltipText(e.detail.payload);
      tooltipText = getTooltipText(e.detail.payload);
      selected = e.detail.payload;
    }
  }} />
<ContextMenu
  bind:this={contextMenuElement}
  menu={mapContextMenu} />
<div class="map-container">
  <canvas bind:this={canvasElement} on:mousedown={onMouseDown} on:mousemove={onMouseMove} on:mouseup={onMouseUp} on:mouseleave={onMouseUp} on:wheel={onWheel}>
  </canvas>
  <svg class="map-overlay {dragging ? 'dragging' : ''}" xmlns="http://www.w3.org/2000/svg">
    {#if canvasBounds != null && imageTileSize && imgLoaded}
      {#each (getAreas(locations) ?? [])
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
        <circle
          use:tooltip={{ tooltip: tooltipElement, payload: circle.object }}
          use:contextmenu={{ contextMenu: contextMenuElement, payload: circle.object }}
          on:mousewheel={onWheel}
          cx={circle.x}
          cy={circle.y}
          r={circle.radius}
          fill="blue"
          fill-opacity="0.3"
          stroke="blue"
          stroke-width="1" />
      {/each}

      {#each (getAreas(locations) ?? [])
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
        <rect
        use:tooltip={{ tooltip: tooltipElement, payload: rect.object }}
        use:contextmenu={{ contextMenu: contextMenuElement, payload: rect.object }}
        on:mousewheel={onWheel}
        x={rect.x}
        y={rect.y}
        width={rect.width}
        height={rect.height}
        fill="green"
        fill-opacity="0.3"
        stroke="green"
        stroke-width="1" />
      {/each}
      
      {#each (getAreas(locations) ?? [])
        .filter(x => x.Properties.Shape === 'Polygon')
        .map(x => {
          return {
            object: x,
            vertices: x.Properties.Data.vertices.reduce((result, value, index, array) => {
              if (index % 2 === 0)
                  result.push([value, array[index + 1]]);
              return result;
            }, []).map(vertex => entropiaCoordsToCanvasCoords(vertex[0], vertex[1]))
          };
        }) as polygon (polygon.object.Name+','+polygon.x+','+polygon.y)}
        <polygon
          use:tooltip={{ tooltip: tooltipElement, payload: polygon.object }}
          use:contextmenu={{ contextMenu: contextMenuElement, payload: polygon.object }}
          on:mousewheel={onWheel}
          points={polygon.vertices.map(vertex => `${vertex.x},${vertex.y}`).join(' ')}
          fill="red"
          fill-opacity="0.3"
          stroke="red"
          stroke-width="1" />
      {/each}
      
      {#each (locations ?? [])
        .filter(x => !getAreas(locations).find(y => x.Name === y.Name && x.Properties.Type === y.Properties.Type))
        .map(x =>  {
          return {
            ...entropiaCoordsToCanvasCoords(x.Properties.Coordinates.Longitude, x.Properties.Coordinates.Latitude),
            object: x
          };
        }).filter(x => !isNaN(x.x) && !isNaN(x.y)) as location}
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <!-- svelte-ignore a11y-mouse-events-have-key-events -->
        <circle
          use:tooltip={{ tooltip: tooltipElement, payload: location.object }}
          use:contextmenu={{ contextMenu: contextMenuElement, payload: location.object }}
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
      {/each}
    {/if}
  </svg>
</div>
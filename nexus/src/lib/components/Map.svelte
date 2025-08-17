<script>
  //@ts-nocheck


  // --- No spatial grid or offscreen canvas optimizations ---

  function drawShape(ctx, loc, isHovered, isSelected) {
    const type = loc.Properties.Shape;
    ctx.save();
    let baseColor = getColorByType(loc.Properties.Type)?.color || 'white';
    // Enhanced highlight for selected
    if (isSelected) {
      ctx.shadowColor = 'yellow';
      ctx.shadowBlur = 18;
      ctx.lineWidth = 5;
      ctx.globalAlpha = 0.85;
      ctx.strokeStyle = lightenColor(baseColor, 0.7);
      ctx.fillStyle = lightenColor(baseColor, 0.5);
    } else if (isHovered) {
      ctx.shadowColor = 'orange';
      ctx.shadowBlur = 8;
      ctx.lineWidth = 3;
      ctx.globalAlpha = 0.6;
      ctx.strokeStyle = lightenColor(baseColor, 0.4);
      ctx.fillStyle = lightenColor(baseColor, 0.2);
    } else {
      ctx.shadowBlur = 0;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.3;
      ctx.strokeStyle = ctx.fillStyle = baseColor;
    }
    if (type === 'Circle') {
      const center = entropiaCoordsToCanvasCoords(loc.Properties.Data.x, loc.Properties.Data.y);
      const outer = entropiaCoordsToCanvasCoords(loc.Properties.Data.x + loc.Properties.Data.radius, loc.Properties.Data.y);
      const radius = outer.x - center.x;
      ctx.beginPath();
      ctx.arc(center.x, center.y, radius, 0, 2 * Math.PI);
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
    } else if (type === 'Rectangle') {
      const start = entropiaCoordsToCanvasCoords(loc.Properties.Data.x, loc.Properties.Data.y);
      const end = entropiaCoordsToCanvasCoords(loc.Properties.Data.x + loc.Properties.Data.width, loc.Properties.Data.y + loc.Properties.Data.height);
      const width = end.x - start.x;
      const height = start.y - end.y;
      ctx.beginPath();
      ctx.rect(start.x, start.y - height, width, height);
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
    } else if (type === 'Polygon') {
      const verts = (loc.Properties.Data.vertices ?? []).reduce((result, value, idx, arr) => {
        if (idx % 2 === 0) result.push([value, arr[idx + 1]]);
        return result;
      }, []).map(v => entropiaCoordsToCanvasCoords(v[0], v[1]));
      if (verts.length > 1) {
        ctx.beginPath();
        ctx.moveTo(verts[0].x, verts[0].y);
        for (let i = 1; i < verts.length; i++) ctx.lineTo(verts[i].x, verts[i].y);
        ctx.closePath();
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.stroke();
      }
    } else {
      // Draw as point
      const pt = entropiaCoordsToCanvasCoords(loc.Properties.Coordinates.Longitude, loc.Properties.Coordinates.Latitude);
      if (loc.Properties.Type === 'Teleporter') {
        ctx.beginPath();
        const showLarge = isHovered || isSelected;
        ctx.arc(pt.x, pt.y, showLarge ? 8 : 4, 0, 2 * Math.PI);
        ctx.fillStyle = isSelected ? 'yellow' : isHovered ? 'orange' : 'aqua';
        ctx.strokeStyle = isSelected ? 'orange' : isHovered ? 'yellow' : 'red';
        ctx.globalAlpha = isSelected ? 1 : 0.85;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.lineWidth = showLarge ? 4 : 2;
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.rect(pt.x - 7, pt.y - 7, 14, 14);
        ctx.fillStyle = isSelected ? 'yellow' : isHovered ? 'orange' : 'white';
        ctx.globalAlpha = isSelected ? 1 : isHovered ? 0.8 : 0.7;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.strokeStyle = isSelected ? 'orange' : isHovered ? 'yellow' : 'black';
        ctx.lineWidth = isSelected ? 4 : isHovered ? 2 : 1;
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  import { writable } from 'svelte/store';
  import { onMount, onDestroy } from 'svelte';
  import Tooltip from './Tooltip.svelte';
  import { tooltip } from './Tooltip';
  import { navigate } from '$lib/util';
  import ContextMenu from './ContextMenu.svelte';
  import { contextmenu } from './ContextMenu';

  import { copyLocation, getTooltipText, locationFilter, getWaypoint } from '$lib/mapUtil';

  export let mapName = '';
  export let planet = null;
  // No cache invalidation needed
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
  let tooltipShow = false;
  let tooltipPos = { x: 0, y: 0 };
  let wasPositionCopied = false;

  let editMode = false;
  let editType = null;
  
  let mapContextMenu = [
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



  $: if (mapSettings) {
    const newFiltered = locations.filter(x => locationFilter(x, mapSettings));
    if (filteredLocations !== newFiltered) {
      filteredLocations = newFiltered;
    }
  }


  async function focusOnLocation(location) {
    if (typeof window === 'undefined' || !location || !location.Properties?.Coordinates) {
      return;
    }

    await mapLoaded;
    moveAndZoomTo(entropiaCoordsToImageCoords(location.Properties.Coordinates.Longitude, location.Properties.Coordinates.Latitude), 1/(planet.Properties.Map.Width*0.5));
  }

  // --- React to selection from outside (e.g. MapList) ---
  // No auto-centering, only visual highlight

  let resizeObserver;


  onMount(async () => {
    resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        if (entry.target === canvasElement) {
          initCanvas();
        }
      }
    });
    resizeObserver.observe(canvasElement);
    // Ensure canvas is initialized on mount
    if (canvasElement) {
      initCanvas();
    }
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
      zoom = imageTileSize / Math.max(img.width, img.height);
      targetZoom = zoom;

      $mapLoadedStore = true;
      // Re-init canvas after image load
      if (canvasElement) {
        initCanvas();
      }
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
  // removed: offscreenCacheValid = false;
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
    targetZoom = Math.max(imageTileSize / Math.max(img.width, img.height), Math.min(4, targetZoom));

  // removed: offscreenCacheValid = false;
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
  // removed: offscreenCacheValid = false;

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
  // removed: offscreenCacheValid = false;

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

  // --- Canvas Drawing and Hit Detection ---
  let lastHover = null;
  let lastHoverType = null;
  let lastHoverIndex = null;
  let lastClick = null;
  let lastRightClick = null;

  function draw() {
    ctx.clearRect(0, 0, canvasBounds.width, canvasBounds.height);
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

    // Draw all shapes (no spatial grid, no offscreen cache)
    for (const loc of filteredLocations) {
      const isHovered = !!hovered && !!loc && hovered.Id === loc.Id;
      const isSelected = !!selected && !!loc && selected.Id === loc.Id;
      drawShape(ctx, loc, isHovered, isSelected);
    }

    drawAnimationId = requestAnimationFrame(draw);
  }

  // drawShapesAndLocations is now handled by spatial index + offscreen cache

  // Helper to lighten a color (hex or named)
  function lightenColor(color, percent) {
    // Only works for hex or rgb(a) colors
    let r, g, b;
    if (color.startsWith('#')) {
      let hex = color.replace('#', '');
      if (hex.length === 3) hex = hex.split('').map(x => x + x).join('');
      r = parseInt(hex.substring(0,2), 16);
      g = parseInt(hex.substring(2,4), 16);
      b = parseInt(hex.substring(4,6), 16);
    } else if (color.startsWith('rgb')) {
      [r, g, b] = color.match(/\d+/g).map(Number);
    } else {
      // fallback for named colors
      return color;
    }
    r = Math.min(255, Math.floor(r + (255 - r) * percent));
    g = Math.min(255, Math.floor(g + (255 - g) * percent));
    b = Math.min(255, Math.floor(b + (255 - b) * percent));
    return `rgb(${r},${g},${b})`;
  }

  // --- Hit Detection ---
  function getShapeAtCanvasPos(x, y) {
    // Check all filteredLocations for hit, no duplicate filtering
    for (let i = filteredLocations.length - 1; i >= 0; i--) {
      const loc = filteredLocations[i];
      const type = loc.Properties.Shape;
      if (type === 'Circle') {
        const center = entropiaCoordsToCanvasCoords(loc.Properties.Data.x, loc.Properties.Data.y);
        const outer = entropiaCoordsToCanvasCoords(loc.Properties.Data.x + loc.Properties.Data.radius, loc.Properties.Data.y);
        const radius = outer.x - center.x;
        const dx = x - center.x, dy = y - center.y;
        if (dx * dx + dy * dy <= radius * radius) return { type: 'area', shape: loc, index: i };
      } else if (type === 'Rectangle') {
        const start = entropiaCoordsToCanvasCoords(loc.Properties.Data.x, loc.Properties.Data.y);
        const end = entropiaCoordsToCanvasCoords(loc.Properties.Data.x + loc.Properties.Data.width, loc.Properties.Data.y + loc.Properties.Data.height);
        const width = end.x - start.x;
        const height = start.y - end.y;
        if (x >= start.x && x <= start.x + width && y >= start.y - height && y <= start.y) return { type: 'area', shape: loc, index: i };
      } else if (type === 'Polygon') {
        const verts = (loc.Properties.Data.vertices ?? []).reduce((result, value, idx, arr) => {
          if (idx % 2 === 0) result.push([value, arr[idx + 1]]);
          return result;
        }, []).map(v => entropiaCoordsToCanvasCoords(v[0], v[1]));
        if (pointInPolygon({ x, y }, verts)) return { type: 'area', shape: loc, index: i };
      } else {
        const pt = entropiaCoordsToCanvasCoords(loc.Properties.Coordinates.Longitude, loc.Properties.Coordinates.Latitude);
        if (loc.Properties.Type === 'Teleporter') {
          const dx = x - pt.x, dy = y - pt.y;
          if (dx * dx + dy * dy <= 25) return { type: 'location', shape: loc, index: i };
        } else {
          if (x >= pt.x - 5 && x <= pt.x + 5 && y >= pt.y - 5 && y <= pt.y + 5) return { type: 'location', shape: loc, index: i };
        }
      }
    }
    return null;
  }

  function pointInPolygon(point, vs) {
    let x = point.x, y = point.y;
    let inside = false;
    for (let i = 0, j = vs.length - 1; i < vs.length; j = i++) {
      let xi = vs[i].x, yi = vs[i].y;
      let xj = vs[j].x, yj = vs[j].y;
      let intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi + 0.00001) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }

  // --- Mouse Events for Canvas ---
  let canvasHover = null;
  let canvasHoverType = null;
  let canvasHoverIndex = null;

  function handleCanvasMouseMove(event) {
    const rect = canvasElement.getBoundingClientRect();
    const x = (event.clientX - rect.left) * window.devicePixelRatio;
    const y = (event.clientY - rect.top) * window.devicePixelRatio;
    const hit = getShapeAtCanvasPos(x, y);
    if (hit) {
      canvasHover = hit.shape;
      canvasHoverType = hit.type;
      canvasHoverIndex = hit.index;
      hovered = hit.shape;
      canvasElement.style.cursor = 'pointer';
      tooltipText = getTooltipText(hit.shape);
      tooltipShow = true;
      tooltipPos = { x: event.clientX, y: event.clientY };
    } else {
      canvasHover = null;
      canvasHoverType = null;
      canvasHoverIndex = null;
      hovered = null;
      canvasElement.style.cursor = dragging ? 'grabbing' : 'default';
      tooltipShow = false;
    }
  }

  function getAllShapesAtCanvasPos(x, y) {
    // Returns all shapes (areas and locations) at the given canvas position, topmost first
    const found = [];
    for (let i = filteredLocations.length - 1; i >= 0; i--) {
      const loc = filteredLocations[i];
      const type = loc.Properties.Shape;
      if (type === 'Circle') {
        const center = entropiaCoordsToCanvasCoords(loc.Properties.Data.x, loc.Properties.Data.y);
        const outer = entropiaCoordsToCanvasCoords(loc.Properties.Data.x + loc.Properties.Data.radius, loc.Properties.Data.y);
        const radius = outer.x - center.x;
        const dx = x - center.x, dy = y - center.y;
        if (dx * dx + dy * dy <= radius * radius) found.push({ type: 'area', shape: loc });
      } else if (type === 'Rectangle') {
        const start = entropiaCoordsToCanvasCoords(loc.Properties.Data.x, loc.Properties.Data.y);
        const end = entropiaCoordsToCanvasCoords(loc.Properties.Data.x + loc.Properties.Data.width, loc.Properties.Data.y + loc.Properties.Data.height);
        const width = end.x - start.x;
        const height = start.y - end.y;
        if (x >= start.x && x <= start.x + width && y >= start.y - height && y <= start.y) found.push({ type: 'area', shape: loc });
      } else if (type === 'Polygon') {
        const verts = (loc.Properties.Data.vertices ?? []).reduce((result, value, idx, arr) => {
          if (idx % 2 === 0) result.push([value, arr[idx + 1]]);
          return result;
        }, []).map(v => entropiaCoordsToCanvasCoords(v[0], v[1]));
        if (pointInPolygon({ x, y }, verts)) found.push({ type: 'area', shape: loc });
      } else {
        const pt = entropiaCoordsToCanvasCoords(loc.Properties.Coordinates.Longitude, loc.Properties.Coordinates.Latitude);
        if (loc.Properties.Type === 'Teleporter') {
          const dx = x - pt.x, dy = y - pt.y;
          if (dx * dx + dy * dy <= 25) found.push({ type: 'location', shape: loc });
        } else {
          if (x >= pt.x - 5 && x <= pt.x + 5 && y >= pt.y - 5 && y <= pt.y + 5) found.push({ type: 'location', shape: loc });
        }
      }
    }
    return found;
  }

  function truncateName(name) {
    if (!name) return '';
    return name.length > 80 ? name.slice(0, 77) + '...' : name;
  }

  async function handleCanvasClick(event) {
    const rect = canvasElement.getBoundingClientRect();
    const x = (event.clientX - rect.left) * window.devicePixelRatio;
    const y = (event.clientY - rect.top) * window.devicePixelRatio;
    const hits = getAllShapesAtCanvasPos(x, y);
    const currentId = selected?.Id;
    if (hits.length === 1) {
      const hit = hits[0];
      selected = hit.shape;
      if (hit.shape?.Properties?.Coordinates) {
        if (typeof window !== 'undefined' && planet && hit.shape?.Id) {
          const planetSimpleName = planet.Name.replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
          const newUrl = `/maps/${planetSimpleName}/${hit.shape.Id}`;
          if (hit.shape.Id !== currentId) {
            await navigate(newUrl);
          }
        }
        // focusOnLocation removed: only visual highlight
      }
    } else if (hits.length > 1) {
      // Only show context menu if at least one hit is a location (not just areas)
      const hasLocation = hits.some(obj => obj.type === 'location');
      if (hasLocation) {
        const menu = hits.map(obj => ({
          label: truncateName(obj.shape.Name),
          action: async () => {
            selected = obj.shape;
            if (obj.shape?.Properties?.Coordinates) {
              if (typeof window !== 'undefined' && planet && obj.shape?.Id) {
                const planetSimpleName = planet.Name.replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
                const newUrl = `/maps/${planetSimpleName}/${obj.shape.Id}`;
                if (obj.shape.Id !== currentId) {
                  await navigate(newUrl);
                }
              }
              // focusOnLocation removed: only visual highlight
            }
          }
        }));
        if (typeof window !== 'undefined') {
          // Dispatch a custom event to trigger the contextmenu action
          const customEvent = new CustomEvent('contextmenu', {
            detail: {
              menu,
              position: { x: event.clientX, y: event.clientY }
            },
            bubbles: true,
            cancelable: true
          });
          canvasElement.dispatchEvent(customEvent);
        }
      } else {
        // If only areas, just select the topmost area
        const hit = hits[0];
        selected = hit.shape;
        if (hit.shape?.Properties?.Coordinates) {
          if (typeof window !== 'undefined' && planet && hit.shape?.Id) {
            const planetSimpleName = planet.Name.replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
            const newUrl = `/maps/${planetSimpleName}/${hit.shape.Id}`;
            if (hit.shape.Id !== currentId) {
              await navigate(newUrl);
            }
          }
          // focusOnLocation removed: only visual highlight
        }
      }
    }
  }

  function handleCanvasRightClick(event) {
    event.preventDefault();
    const rect = canvasElement.getBoundingClientRect();
    const x = (event.clientX - rect.left) * window.devicePixelRatio;
    const y = (event.clientY - rect.top) * window.devicePixelRatio;
    const hit = getShapeAtCanvasPos(x, y);
    if (hit) {
      // Automatically copy waypoint to clipboard
      copyLocation(hit.shape);
    }
  }

  // Attach canvas event listeners
  onMount(() => {
    canvasElement.addEventListener('mousemove', handleCanvasMouseMove);
    canvasElement.addEventListener('click', handleCanvasClick);
    canvasElement.addEventListener('contextmenu', handleCanvasRightClick);
  });
  onDestroy(() => {
    if (typeof window !== 'undefined' && canvasElement) {
      canvasElement.removeEventListener('mousemove', handleCanvasMouseMove);
      canvasElement.removeEventListener('click', handleCanvasClick);
      canvasElement.removeEventListener('contextmenu', handleCanvasRightClick);
    }
  });

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

  export function canvasToWindowCoords(canvasX, canvasY) {
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
    return locations.filter(x => x.Properties?.Type?.endsWith('Area') === true);
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

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }

  @keyframes -global-pulse {
    0%, 100% { transform: 1; }
    50% { transform: 1.5; }
  }
</style>

<Tooltip
  bind:this={tooltipElement}
  bind:text={tooltipText}
  bind:show={tooltipShow}
  bind:tooltipPos={tooltipPos}
  on:hide={() => wasPositionCopied = false}
  on:elementClick={(e) => {
    if (e.detail.button === 0) {
      navigate(`/maps/${planet.Name.replace(/[^0-9a-zA-Z]/g, '').toLowerCase()}/${e.detail.payload.Id}`);
    }
  }} />
<ContextMenu
  bind:this={mapContextMenuElement}
  menu={mapContextMenu} />
<div class="map-container">
  <canvas use:contextmenu={mapContextMenuObject} bind:this={canvasElement} on:mousedown={onMouseDown} on:mousemove={onMouseMove} on:mouseup={onMouseUp} on:mouseleave={onMouseUp} on:wheel={onWheel}>
  </canvas>
</div>
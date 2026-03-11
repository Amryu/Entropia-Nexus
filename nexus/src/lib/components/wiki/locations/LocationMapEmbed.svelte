<!--
  @component LocationMapEmbed
  A compact embedded map showing a location with optional area shape rendering.

  Shows:
  - Location marker at coordinates
  - Area shapes (polygon, circle, rectangle) if applicable
  - Mini zoom controls
  - Click to open full map view
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import { goto } from '$app/navigation';
  import { encodeURIComponentSafe } from '$lib/util';

  /** @type {{Id: number, Name: string, Properties: {Coordinates: {Longitude: number, Latitude: number, Altitude?: number}, Type: string, AreaType?: string, Shape?: string, Data?: any}}} */
  export let location = null;

  /** @type {{Id: number, Name: string, Properties?: {Map?: {X: number, Y: number, Width: number, Height: number}, TechnicalName?: string}}} */
  export let planet = null;

  /** @type {number} Height of the embed in pixels */
  export let height = 200;

  /** @type {string} Optional title for the map section */
  export let title = '';

  /** @type {Array} Nearby locations to display (land areas and teleporters) */
  export let nearbyLocations = [];

  // Coordinate conversion ratios (computed when map loads)
  let imageTileSize = 1;
  let imageToEntropiaRatio = 1;
  let entropiaTileSize = 8192;

  // Canvas and rendering state
  let canvas;
  let ctx;
  let container;
  let mapImage = null;
  let mapLoaded = false;
  let viewScale = 1;
  let viewX = 0;
  let viewY = 0;

  // Mouse drag state
  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let lastMouseX = 0;
  let lastMouseY = 0;

  // Touch state for pinch zoom and inertia
  let isTouching = false;
  let lastTouchDistance = null;
  let lastTouchCenter = null;
  let touchStartPos = null;
  let touchMoved = false;
  let touchMoveDistance = 0;
  const touchSlop = 8;

  // Inertia state
  let velocity = { x: 0, y: 0 };
  let lastMoveTime = 0;
  let inertiaId = null;

  // Hover state for nearby locations
  let hoveredLocation = null;

  // Layer visibility toggles
  let showTeleporters = true;
  let showLandAreas = true;
  let showNpcs = false;       // Not yet implemented
  let showMobAreas = false;   // Not yet implemented
  let showEstates = false;    // Not yet implemented

  // Get map image URL based on planet (matches Map.svelte format)
  $: mapImageUrl = planet?.Name
    ? `/${planet.Name.replace(/[^0-9a-zA-Z]/g, '').toLowerCase()}.jpg`
    : '/calypso.jpg';

  // Get location coordinates
  $: locationCoords = location?.Properties?.Coordinates;

  // Color based on location type
  const typeColors = {
    Teleporter: '#4ade80',   // Green
    Npc: '#f97316',          // Orange
    Interactable: '#a855f7', // Purple
    Area: '#3b82f6',         // Blue
    Estate: '#eab308',       // Yellow
    Outpost: '#ef4444',      // Red
    Camp: '#22c55e',         // Emerald
    City: '#6366f1',         // Indigo
    default: '#ffffff'       // White
  };

  const areaTypeColors = {
    WaveEventArea: '#ec4899'  // Pink
  };

  $: markerColor = (location?.Properties?.Type === 'Area' && areaTypeColors[location?.Properties?.AreaType])
    || typeColors[location?.Properties?.Type]
    || typeColors.default;

  // Convert game (entropia) coordinates to image coordinates
  // Uses the same logic as Map.svelte's entropiaCoordsToImageCoords
  function gameToImageCoords(entropiaX, entropiaY) {
    if (!planet?.Properties?.Map) return { x: 0, y: 0 };

    const map = planet.Properties.Map;
    const planetOffsetX = map.X * entropiaTileSize;
    const planetOffsetY = map.Y * entropiaTileSize;
    const planetHeight = map.Height * entropiaTileSize;

    return {
      x: (entropiaX - planetOffsetX) / imageToEntropiaRatio,
      y: (planetHeight - (entropiaY - planetOffsetY)) / imageToEntropiaRatio
    };
  }

  // Convert game coordinates to canvas coordinates
  function gameToCanvas(longitude, latitude) {
    if (!mapImage || !canvas) return { x: 0, y: 0 };

    // First convert game coords to image coords using planet map properties
    const imgCoords = gameToImageCoords(longitude, latitude);

    // Then convert image coords to canvas coords (with view transform)
    const canvasX = (imgCoords.x * viewScale) + viewX;
    const canvasY = (imgCoords.y * viewScale) + viewY;

    return { x: canvasX, y: canvasY };
  }

  // Initialize view to center on location
  function centerOnLocation() {
    if (!canvas || !mapImage || !locationCoords) return;

    const canvasWidth = canvas.width / (window.devicePixelRatio || 1);
    const canvasHeight = canvas.height / (window.devicePixelRatio || 1);

    // Calculate the image position of the location using proper coordinate conversion
    const imgCoords = gameToImageCoords(locationCoords.Longitude, locationCoords.Latitude);

    // Set zoom level - show a reasonable area around the location
    viewScale = 1.5;

    // Center the view on the location
    viewX = (canvasWidth / 2) - (imgCoords.x * viewScale);
    viewY = (canvasHeight / 2) - (imgCoords.y * viewScale);
  }

  // Check if a location is the currently selected one
  function isCurrentLocation(loc) {
    if (!loc || !location) return false;
    if (loc.Id && location.Id && loc.Id === location.Id) return true;
    return false;
  }

  // Draw the map and location marker
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

    // Draw nearby land areas first (they go behind other elements)
    if (showLandAreas) {
      for (const loc of nearbyLocations) {
        if (isCurrentLocation(loc)) continue; // Skip current location
        if (loc.Properties?.AreaType === 'LandArea') {
          const isHovered = hoveredLocation && hoveredLocation.Id === loc.Id;
          drawNearbyArea(loc, isHovered);
        }
      }
    }

    // Draw area shape if current location is an Area
    if (location?.Properties?.Type === 'Area' && location?.Properties?.Data) {
      drawAreaShape();
    }

    // Draw nearby teleporters
    if (showTeleporters) {
      for (const loc of nearbyLocations) {
        if (isCurrentLocation(loc)) continue; // Skip current location
        if (loc.Properties?.Type === 'Teleporter') {
          const isHovered = hoveredLocation && hoveredLocation.Id === loc.Id;
          drawTeleporter(loc, false, isHovered);
        }
      }
    }

    // Draw location marker for current location
    if (locationCoords?.Longitude != null) {
      // If current location is a teleporter, draw it as selected
      if (location?.Properties?.Type === 'Teleporter') {
        drawTeleporter(location, true);
      } else {
        // Draw standard marker for non-teleporter locations
        const pos = gameToCanvas(locationCoords.Longitude, locationCoords.Latitude);
        const radius = 14;

        // Outer glow
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius + 6, 0, Math.PI * 2);
        ctx.fillStyle = `${markerColor}33`;
        ctx.fill();

        // Outer ring
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius + 3, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fill();

        // Main circle
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = markerColor;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Center dot
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#fff';
        ctx.fill();
      }
    }

    ctx.restore();
  }

  // Draw a teleporter marker
  function drawTeleporter(loc, isSelected, isHovered = false) {
    const coords = loc?.Properties?.Coordinates;
    if (!coords?.Longitude) return;

    const pos = gameToCanvas(coords.Longitude, coords.Latitude);
    ctx.save();

    if (isSelected) {
      // Selected teleporter - larger with glow
      ctx.shadowColor = 'yellow';
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 8, 0, Math.PI * 2);
      ctx.fillStyle = 'yellow';
      ctx.fill();
      ctx.strokeStyle = 'orange';
      ctx.lineWidth = 3;
      ctx.stroke();
    } else if (isHovered) {
      // Hovered teleporter - orange highlight
      ctx.shadowColor = 'orange';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = 'orange';
      ctx.fill();
      ctx.strokeStyle = 'yellow';
      ctx.lineWidth = 2;
      ctx.stroke();
    } else {
      // Normal teleporter - aqua with red border
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = 'aqua';
      ctx.globalAlpha = 0.85;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = 'red';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    ctx.restore();
  }

  // Draw a nearby area shape
  function drawNearbyArea(loc, isHovered = false) {
    const data = loc?.Properties?.Data;
    const shape = loc?.Properties?.Shape;
    if (!data) return;

    ctx.save();

    if (isHovered) {
      // Hovered area - brighter highlight
      ctx.shadowColor = 'orange';
      ctx.shadowBlur = 8;
      ctx.strokeStyle = 'rgba(255, 165, 0, 0.9)'; // Orange for hover
      ctx.fillStyle = 'rgba(255, 165, 0, 0.35)';
      ctx.lineWidth = 2;
    } else {
      // Normal area - green
      ctx.strokeStyle = 'rgba(0, 255, 0, 0.6)';
      ctx.fillStyle = 'rgba(0, 255, 0, 0.15)';
      ctx.lineWidth = 1;
    }

    if (shape === 'Polygon' && data.vertices?.length > 2) {
      // Handle vertices array format (flat array of x,y pairs)
      const verts = [];
      for (let i = 0; i < data.vertices.length; i += 2) {
        verts.push(gameToCanvas(data.vertices[i], data.vertices[i + 1]));
      }
      if (verts.length > 1) {
        ctx.beginPath();
        ctx.moveTo(verts[0].x, verts[0].y);
        for (let i = 1; i < verts.length; i++) {
          ctx.lineTo(verts[i].x, verts[i].y);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
    } else if (shape === 'Circle' && data.radius) {
      const center = gameToCanvas(data.x, data.y);
      const edge = gameToCanvas(data.x + data.radius, data.y);
      const radiusPixels = edge.x - center.x;
      ctx.beginPath();
      ctx.arc(center.x, center.y, radiusPixels, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    } else if (shape === 'Rectangle' && data.width && data.height) {
      const topLeft = gameToCanvas(data.x, data.y + data.height);
      const bottomRight = gameToCanvas(data.x + data.width, data.y);
      ctx.fillRect(topLeft.x, topLeft.y, bottomRight.x - topLeft.x, bottomRight.y - topLeft.y);
      ctx.strokeRect(topLeft.x, topLeft.y, bottomRight.x - topLeft.x, bottomRight.y - topLeft.y);
    }

    ctx.restore();
  }

  // Draw area shape (polygon, circle, rectangle)
  function drawAreaShape() {
    const data = location?.Properties?.Data;
    const shape = location?.Properties?.Shape;
    if (!data || !shape) return;

    ctx.strokeStyle = `${markerColor}aa`;
    ctx.fillStyle = `${markerColor}33`;
    ctx.lineWidth = 2;

    if (shape === 'Polygon' && data.points?.length > 2) {
      ctx.beginPath();
      const firstPoint = gameToCanvas(data.points[0].x, data.points[0].y);
      ctx.moveTo(firstPoint.x, firstPoint.y);
      for (let i = 1; i < data.points.length; i++) {
        const pt = gameToCanvas(data.points[i].x, data.points[i].y);
        ctx.lineTo(pt.x, pt.y);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    } else if (shape === 'Circle' && data.radius) {
      const centerX = data.x || locationCoords?.Longitude;
      const centerY = data.y || locationCoords?.Latitude;
      const center = gameToCanvas(centerX, centerY);
      const edge = gameToCanvas(centerX + data.radius, centerY);
      const radiusPixels = edge.x - center.x;
      ctx.beginPath();
      ctx.arc(center.x, center.y, radiusPixels, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    } else if (shape === 'Rectangle' && data.width && data.height) {
      const topLeft = gameToCanvas(data.x, data.y + data.height);
      const bottomRight = gameToCanvas(data.x + data.width, data.y);
      ctx.fillRect(topLeft.x, topLeft.y, bottomRight.x - topLeft.x, bottomRight.y - topLeft.y);
      ctx.strokeRect(topLeft.x, topLeft.y, bottomRight.x - topLeft.x, bottomRight.y - topLeft.y);
    }
  }

  // Stop inertia animation
  function stopInertia() {
    if (inertiaId) {
      cancelAnimationFrame(inertiaId);
      inertiaId = null;
    }
    velocity = { x: 0, y: 0 };
  }

  // Hit detection: check if point is inside a teleporter
  function isPointInTeleporter(canvasX, canvasY, loc) {
    const coords = loc?.Properties?.Coordinates;
    if (!coords?.Longitude) return false;
    const pos = gameToCanvas(coords.Longitude, coords.Latitude);
    const hitRadius = 10; // Larger than visual for easier clicking
    const dx = canvasX - pos.x;
    const dy = canvasY - pos.y;
    return (dx * dx + dy * dy) <= (hitRadius * hitRadius);
  }

  // Hit detection: check if point is inside an area shape
  function isPointInArea(canvasX, canvasY, loc) {
    const data = loc?.Properties?.Data;
    const shape = loc?.Properties?.Shape;
    if (!data) return false;

    if (shape === 'Polygon' && data.vertices?.length > 2) {
      // Point-in-polygon test using ray casting
      const verts = [];
      for (let i = 0; i < data.vertices.length; i += 2) {
        verts.push(gameToCanvas(data.vertices[i], data.vertices[i + 1]));
      }
      let inside = false;
      for (let i = 0, j = verts.length - 1; i < verts.length; j = i++) {
        const xi = verts[i].x, yi = verts[i].y;
        const xj = verts[j].x, yj = verts[j].y;
        if (((yi > canvasY) !== (yj > canvasY)) &&
            (canvasX < (xj - xi) * (canvasY - yi) / (yj - yi) + xi)) {
          inside = !inside;
        }
      }
      return inside;
    } else if (shape === 'Circle' && data.radius) {
      const center = gameToCanvas(data.x, data.y);
      const edge = gameToCanvas(data.x + data.radius, data.y);
      const radiusPixels = edge.x - center.x;
      const dx = canvasX - center.x;
      const dy = canvasY - center.y;
      return (dx * dx + dy * dy) <= (radiusPixels * radiusPixels);
    } else if (shape === 'Rectangle' && data.width && data.height) {
      const topLeft = gameToCanvas(data.x, data.y + data.height);
      const bottomRight = gameToCanvas(data.x + data.width, data.y);
      return canvasX >= topLeft.x && canvasX <= bottomRight.x &&
             canvasY >= topLeft.y && canvasY <= bottomRight.y;
    }
    return false;
  }

  // Find the location under the mouse (teleporters checked first as they're on top)
  function findLocationAtPoint(canvasX, canvasY) {
    // Check teleporters first (they're drawn on top)
    if (showTeleporters) {
      for (const loc of nearbyLocations) {
        if (isCurrentLocation(loc)) continue;
        if (loc.Properties?.Type === 'Teleporter' && isPointInTeleporter(canvasX, canvasY, loc)) {
          return loc;
        }
      }
    }
    // Check areas
    if (showLandAreas) {
      for (const loc of nearbyLocations) {
        if (isCurrentLocation(loc)) continue;
        if (loc.Properties?.AreaType === 'LandArea' && isPointInArea(canvasX, canvasY, loc)) {
          return loc;
        }
      }
    }
    return null;
  }

  // Get canvas coordinates from mouse event
  function getCanvasCoords(e) {
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  }

  // Navigate to location page
  function navigateToLocation(loc) {
    if (!loc?.Name) return;
    // Determine the type slug for the URL
    const type = loc.Properties?.Type;
    const areaType = loc.Properties?.AreaType;
    let typeSlug = '';
    if (type === 'Teleporter') typeSlug = 'teleporters';
    else if (areaType === 'LandArea') typeSlug = 'areas';
    else typeSlug = type?.toLowerCase() || '';

    const url = `/information/locations/${typeSlug}/${encodeURIComponentSafe(loc.Name)}`;
    goto(url);
  }

  // Mouse event handlers
  let dragDistance = 0;
  const clickThreshold = 5; // Max drag distance to count as a click

  function handleMouseDown(e) {
    if (e.button !== 0) return;
    e.preventDefault();
    stopInertia();
    isDragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;
    dragDistance = 0;
    lastMoveTime = Date.now();
    canvas.style.cursor = 'grabbing';
  }

  function handleMouseMove(e) {
    const canvasCoords = getCanvasCoords(e);

    if (isDragging) {
      const now = Date.now();
      const dt = Math.max(16, now - lastMoveTime);

      const dx = e.clientX - lastMouseX;
      const dy = e.clientY - lastMouseY;

      // Track total drag distance
      dragDistance += Math.sqrt(dx * dx + dy * dy);

      viewX += dx;
      viewY += dy;

      // Track velocity for inertia
      velocity = {
        x: (dx / dt) * 16,
        y: (dy / dt) * 16
      };

      lastMouseX = e.clientX;
      lastMouseY = e.clientY;
      lastMoveTime = now;
      draw();
    } else {
      // Not dragging - check for hover
      const loc = findLocationAtPoint(canvasCoords.x, canvasCoords.y);
      if (loc !== hoveredLocation) {
        hoveredLocation = loc;
        canvas.style.cursor = loc ? 'pointer' : 'grab';
        draw();
      }
    }
  }

  function handleMouseUp(e) {
    if (!isDragging) return;
    isDragging = false;

    // Check what's under the mouse now
    const canvasCoords = getCanvasCoords(e);
    const loc = findLocationAtPoint(canvasCoords.x, canvasCoords.y);

    // Check if this was a click (minimal drag) - navigate to location if so
    if (dragDistance < clickThreshold && loc) {
      navigateToLocation(loc);
      if (canvas) canvas.style.cursor = 'pointer';
      return;
    }

    // Update hover state and cursor
    hoveredLocation = loc;
    if (canvas) canvas.style.cursor = loc ? 'pointer' : 'grab';
    draw();

    // Start inertia if velocity is significant
    if (Math.abs(velocity.x) > 0.5 || Math.abs(velocity.y) > 0.5) {
      startInertia();
    }
  }

  function handleMouseLeave() {
    if (isDragging) {
      isDragging = false;
      if (Math.abs(velocity.x) > 0.5 || Math.abs(velocity.y) > 0.5) {
        startInertia();
      }
    }
    if (hoveredLocation) {
      hoveredLocation = null;
      draw();
    }
  }

  // Touch event helpers
  function getTouchDistance(touches) {
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function getTouchCenter(touches) {
    return {
      x: (touches[0].clientX + touches[1].clientX) / 2,
      y: (touches[0].clientY + touches[1].clientY) / 2
    };
  }

  // Touch event handlers
  function handleTouchStart(e) {
    if (!e.touches?.length) return;
    e.preventDefault();
    stopInertia();
    isTouching = true;
    touchMoved = false;
    touchMoveDistance = 0;
    lastMoveTime = Date.now();

    if (e.touches.length === 1) {
      isDragging = true;
      lastMouseX = e.touches[0].clientX;
      lastMouseY = e.touches[0].clientY;
      touchStartPos = { x: lastMouseX, y: lastMouseY };
      lastTouchDistance = null;
      lastTouchCenter = null;
    } else if (e.touches.length === 2) {
      isDragging = false;
      lastTouchDistance = getTouchDistance(e.touches);
      lastTouchCenter = getTouchCenter(e.touches);
    }
  }

  function handleTouchMove(e) {
    if (!e.touches?.length) return;
    e.preventDefault();

    const now = Date.now();
    const dt = Math.max(16, now - lastMoveTime);

    if (touchStartPos && e.touches.length === 1) {
      const dx = e.touches[0].clientX - touchStartPos.x;
      const dy = e.touches[0].clientY - touchStartPos.y;
      touchMoveDistance = Math.sqrt(dx * dx + dy * dy);
      if (touchMoveDistance > touchSlop) {
        touchMoved = true;
      }
    }

    if (e.touches.length === 1 && isDragging) {
      const dx = e.touches[0].clientX - lastMouseX;
      const dy = e.touches[0].clientY - lastMouseY;

      if (touchMoveDistance > touchSlop) {
        viewX += dx;
        viewY += dy;

        velocity = {
          x: (dx / dt) * 16,
          y: (dy / dt) * 16
        };
      }

      lastMouseX = e.touches[0].clientX;
      lastMouseY = e.touches[0].clientY;
      draw();
    } else if (e.touches.length === 2) {
      touchMoved = true;
      const distance = getTouchDistance(e.touches);
      const center = getTouchCenter(e.touches);

      // Pinch zoom
      if (lastTouchDistance) {
        const rect = canvas.getBoundingClientRect();
        const centerX = center.x - rect.left;
        const centerY = center.y - rect.top;

        const delta = distance / lastTouchDistance;
        const newScale = Math.max(0.3, Math.min(5, viewScale * delta));

        // Zoom toward pinch center
        viewX = centerX - (centerX - viewX) * (newScale / viewScale);
        viewY = centerY - (centerY - viewY) * (newScale / viewScale);
        viewScale = newScale;
      }

      // Pan with pinch
      if (lastTouchCenter) {
        const dx = center.x - lastTouchCenter.x;
        const dy = center.y - lastTouchCenter.y;
        viewX += dx;
        viewY += dy;
      }

      lastTouchDistance = distance;
      lastTouchCenter = center;
      draw();
    }

    lastMoveTime = now;
  }

  function handleTouchEnd(e) {
    e.preventDefault();

    if (!e.touches?.length) {
      isDragging = false;
      isTouching = false;

      // Start inertia if velocity is significant and we were dragging
      if (touchMoved && (Math.abs(velocity.x) > 0.5 || Math.abs(velocity.y) > 0.5)) {
        startInertia();
      }

      touchStartPos = null;
      lastTouchDistance = null;
      lastTouchCenter = null;
      return;
    }

    // If one finger remains, switch to single-finger drag
    if (e.touches.length === 1) {
      isDragging = true;
      lastMouseX = e.touches[0].clientX;
      lastMouseY = e.touches[0].clientY;
      lastTouchDistance = null;
      lastTouchCenter = null;
    }
  }

  // Inertia animation
  function startInertia() {
    const friction = 0.93;

    function step() {
      velocity.x *= friction;
      velocity.y *= friction;

      viewX += velocity.x;
      viewY += velocity.y;

      draw();

      if (Math.abs(velocity.x) < 0.1 && Math.abs(velocity.y) < 0.1) {
        inertiaId = null;
        return;
      }

      inertiaId = requestAnimationFrame(step);
    }

    inertiaId = requestAnimationFrame(step);
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
    if (locationCoords?.Longitude != null) {
      centerOnLocation();
    } else {
      centerOnMap();
    }
    draw();
  }

  // Center on the whole map (when no location selected)
  function centerOnMap() {
    if (!canvas || !mapImage) return;

    const canvasWidth = canvas.width / (window.devicePixelRatio || 1);
    const canvasHeight = canvas.height / (window.devicePixelRatio || 1);

    // Fit the map to the canvas
    const scaleX = canvasWidth / mapImage.naturalWidth;
    const scaleY = canvasHeight / mapImage.naturalHeight;
    viewScale = Math.min(scaleX, scaleY) * 0.9;

    // Center the map
    viewX = (canvasWidth - mapImage.naturalWidth * viewScale) / 2;
    viewY = (canvasHeight - mapImage.naturalHeight * viewScale) / 2;
  }

  // Toggle layer visibility
  function toggleTeleporters() {
    showTeleporters = !showTeleporters;
    draw();
  }

  function toggleLandAreas() {
    showLandAreas = !showLandAreas;
    draw();
  }

  function toggleNpcs() {
    showNpcs = !showNpcs;
    draw();
  }

  function toggleMobAreas() {
    showMobAreas = !showMobAreas;
    draw();
  }

  function toggleEstates() {
    showEstates = !showEstates;
    draw();
  }

  // Open full map
  function openFullMap() {
    if (!planet?.Name) return;
    const slug = planet.Name.toLowerCase().replace(/[^a-z0-9]/g, '');
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
      centerOnLocation();
      draw();
    }
  }

  // Load map image
  function loadMapImage() {
    if (!browser) return;

    mapImage = new Image();
    mapImage.onload = () => {
      mapLoaded = true;

      // Calculate coordinate conversion ratios (same as Map.svelte)
      if (planet?.Properties?.Map?.Width) {
        imageTileSize = mapImage.width / planet.Properties.Map.Width;
        imageToEntropiaRatio = 8192 / imageTileSize;
        entropiaTileSize = imageTileSize * imageToEntropiaRatio;
      }

      centerOnLocation();
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

    // Add touch listeners with passive: false for preventDefault
    if (canvas) {
      canvas.addEventListener('touchstart', handleTouchStart, { passive: false });
      canvas.addEventListener('touchmove', handleTouchMove, { passive: false });
      canvas.addEventListener('touchend', handleTouchEnd, { passive: false });
      canvas.addEventListener('touchcancel', handleTouchEnd, { passive: false });
    }

    const resizeObserver = new ResizeObserver(() => {
      setupCanvas();
    });
    if (container) resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      stopInertia();
      if (canvas) {
        canvas.removeEventListener('touchstart', handleTouchStart);
        canvas.removeEventListener('touchmove', handleTouchMove);
        canvas.removeEventListener('touchend', handleTouchEnd);
        canvas.removeEventListener('touchcancel', handleTouchEnd);
      }
    };
  });

  // Reload map when planet changes
  $: if (browser && mapImageUrl) {
    loadMapImage();
  }

  // Re-center map when location changes (external navigation)
  // Track location.Id to detect when we've navigated to a different location
  let lastLocationId = null;
  $: if (browser && mapLoaded && location?.Id !== lastLocationId) {
    lastLocationId = location?.Id;
    // Only re-center if we have valid coordinates
    if (locationCoords?.Longitude != null) {
      centerOnLocation();
      draw();
    }
  }
</script>

{#if locationCoords?.Longitude != null}
  <div class="location-map-embed" style="height: {height}px">
    <div class="map-header">
      {#if title}
        <h4 class="map-title">{title}</h4>
      {:else}
        <div class="map-title-spacer"></div>
      {/if}
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

    <div class="map-container" bind:this={container}>
      <canvas
        bind:this={canvas}
        on:mousedown={handleMouseDown}
        on:mousemove={handleMouseMove}
        on:mouseup={handleMouseUp}
        on:mouseleave={handleMouseLeave}
        on:wheel={handleWheel}
      ></canvas>

      <!-- Layer toggles (top-left) -->
      <div class="layer-toggles">
        <button
          class="layer-btn"
          class:active={showTeleporters}
          on:click={toggleTeleporters}
          title="Toggle Teleporters"
        >
          <span class="layer-icon tp-icon">TP</span>
        </button>
        <button
          class="layer-btn"
          class:active={showLandAreas}
          on:click={toggleLandAreas}
          title="Toggle Land Areas"
        >
          <span class="layer-icon la-icon">LA</span>
        </button>
        <button
          class="layer-btn"
          class:active={showNpcs}
          on:click={toggleNpcs}
          title="Toggle NPCs"
        >
          <span class="layer-icon npc-icon">NPC</span>
        </button>
        <button
          class="layer-btn"
          class:active={showMobAreas}
          on:click={toggleMobAreas}
          title="Toggle Mob Areas"
        >
          <span class="layer-icon ma-icon">MA</span>
        </button>
        <button
          class="layer-btn"
          class:active={showEstates}
          on:click={toggleEstates}
          title="Toggle Estates"
        >
          <span class="layer-icon est-icon">EST</span>
        </button>
      </div>

      <!-- Re-center button (bottom-right) -->
      <button class="recenter-btn" on:click={resetView} title="Re-center on location">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M12 2v4m0 12v4m-10-10h4m12 0h4"></path>
        </svg>
      </button>

      <!-- Hover tooltip -->
      {#if hoveredLocation}
        <div class="hover-tooltip">
          <span class="tooltip-type">{hoveredLocation.Properties?.Type === 'Teleporter' ? 'TP' : 'Area'}</span>
          <span class="tooltip-name">{hoveredLocation.Name}</span>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .location-map-embed {
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

  .map-title-spacer {
    flex: 1;
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

  /* Hover tooltip */
  .hover-tooltip {
    position: absolute;
    top: 8px;
    right: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: rgba(0, 0, 0, 0.8);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    pointer-events: none;
    z-index: 10;
  }

  .tooltip-type {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--accent-color, #4a9eff);
    padding: 2px 4px;
    background: rgba(74, 158, 255, 0.2);
    border-radius: 3px;
  }

  .tooltip-name {
    font-size: 12px;
    font-weight: 500;
    color: white;
  }

  /* Layer toggles (top-left) */
  .layer-toggles {
    position: absolute;
    top: 8px;
    left: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    z-index: 10;
  }

  .layer-btn {
    width: 28px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    background: rgba(0, 0, 0, 0.7);
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
    opacity: 0.5;
  }

  .layer-btn.active {
    opacity: 1;
    border-color: var(--accent-color, #4a9eff);
  }

  .layer-btn:hover {
    opacity: 1;
    background: rgba(0, 0, 0, 0.85);
  }

  .layer-icon {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
  }

  .tp-icon {
    color: aqua;
  }

  .la-icon {
    color: #4ade80;
  }

  .npc-icon {
    color: #f97316;
  }

  .ma-icon {
    color: #ef4444;
  }

  .est-icon {
    color: #eab308;
  }

  /* Re-center button (bottom-right) */
  .recenter-btn {
    position: absolute;
    bottom: 8px;
    right: 8px;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    background: rgba(0, 0, 0, 0.7);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s;
    z-index: 10;
  }

  .recenter-btn:hover {
    background: rgba(0, 0, 0, 0.85);
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }
</style>

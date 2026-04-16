<script>
  //@ts-nocheck

  // ─── Marker style registry ──────────────────────────────────────────
  // Each entry: { color, shape }
  // shapes: 'circle' | 'square' | 'diamond' | 'roundedSquare' | 'triUp' | 'triDown' |
  //         'pentagon' | 'hexagon' | 'star' | 'cross' | 'ring'
  const MARKER_STYLES = {
    Teleporter:       { color: '#00ffff', shape: 'circle' },
    Npc:              { color: '#ff69b4', shape: 'diamond' },
    Vendor:           { color: '#ffa07a', shape: 'roundedSquare' },
    Interactable:     { color: '#dda0dd', shape: 'triUp' },
    Outpost:          { color: '#87ceeb', shape: 'pentagon' },
    Camp:             { color: '#f0e68c', shape: 'triDown' },
    City:             { color: '#90ee90', shape: 'hexagon' },
    MagicalFlower:    { color: '#ff77aa', shape: 'star' },
    RevivalPoint:     { color: '#98fb98', shape: 'cross' },
    InstanceEntrance: { color: '#b0c4de', shape: 'ring' },
    Estate:           { color: '#deb887', shape: 'roundedSquare' }
  };

  function drawMarkerShape(ctx, shape, x, y, r) {
    ctx.beginPath();
    switch (shape) {
      case 'circle':
        ctx.arc(x, y, r, 0, 2 * Math.PI);
        break;
      case 'square':
        ctx.rect(x - r, y - r, r * 2, r * 2);
        break;
      case 'diamond':
        ctx.moveTo(x, y - r);
        ctx.lineTo(x + r, y);
        ctx.lineTo(x, y + r);
        ctx.lineTo(x - r, y);
        ctx.closePath();
        break;
      case 'roundedSquare': {
        const rr = Math.max(1, r * 0.35);
        const x0 = x - r, y0 = y - r, w = r * 2, h = r * 2;
        ctx.moveTo(x0 + rr, y0);
        ctx.arcTo(x0 + w, y0, x0 + w, y0 + h, rr);
        ctx.arcTo(x0 + w, y0 + h, x0, y0 + h, rr);
        ctx.arcTo(x0, y0 + h, x0, y0, rr);
        ctx.arcTo(x0, y0, x0 + w, y0, rr);
        ctx.closePath();
        break;
      }
      case 'triUp':
        ctx.moveTo(x, y - r);
        ctx.lineTo(x + r, y + r * 0.85);
        ctx.lineTo(x - r, y + r * 0.85);
        ctx.closePath();
        break;
      case 'triDown':
        ctx.moveTo(x, y + r);
        ctx.lineTo(x + r, y - r * 0.85);
        ctx.lineTo(x - r, y - r * 0.85);
        ctx.closePath();
        break;
      case 'pentagon':
        for (let i = 0; i < 5; i++) {
          const a = -Math.PI / 2 + (i * 2 * Math.PI) / 5;
          const px = x + Math.cos(a) * r;
          const py = y + Math.sin(a) * r;
          if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.closePath();
        break;
      case 'hexagon':
        for (let i = 0; i < 6; i++) {
          const a = (i * Math.PI) / 3;
          const px = x + Math.cos(a) * r;
          const py = y + Math.sin(a) * r;
          if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.closePath();
        break;
      case 'star': {
        const inner = r * 0.45;
        for (let i = 0; i < 10; i++) {
          const rad = i % 2 === 0 ? r : inner;
          const a = -Math.PI / 2 + (i * Math.PI) / 5;
          const px = x + Math.cos(a) * rad;
          const py = y + Math.sin(a) * rad;
          if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.closePath();
        break;
      }
      case 'cross': {
        const t = r * 0.38;
        ctx.moveTo(x - t, y - r);
        ctx.lineTo(x + t, y - r);
        ctx.lineTo(x + t, y - t);
        ctx.lineTo(x + r, y - t);
        ctx.lineTo(x + r, y + t);
        ctx.lineTo(x + t, y + t);
        ctx.lineTo(x + t, y + r);
        ctx.lineTo(x - t, y + r);
        ctx.lineTo(x - t, y + t);
        ctx.lineTo(x - r, y + t);
        ctx.lineTo(x - r, y - t);
        ctx.lineTo(x - t, y - t);
        ctx.closePath();
        break;
      }
      case 'ring':
        ctx.arc(x, y, r, 0, 2 * Math.PI);
        break;
      default:
        ctx.rect(x - r, y - r, r * 2, r * 2);
    }
  }

  function drawPointMarker(ctx, type, pt, isHovered, isSelected) {
    const style = MARKER_STYLES[type] || { color: '#ffffff', shape: 'square' };
    const isTp = type === 'Teleporter';
    const baseR = isTp ? 4 : 6;
    const activeR = isTp ? 8 : 9;
    const r = (isHovered || isSelected) ? activeR : baseR;

    let fillColor = style.color;
    let strokeColor = isTp ? 'red' : 'black';
    let fillAlpha = 0.9;
    let lineWidth = 1.5;

    if (isSelected) {
      fillColor = 'yellow';
      strokeColor = 'orange';
      fillAlpha = 1;
      lineWidth = 3;
    } else if (isHovered) {
      fillColor = 'orange';
      strokeColor = 'yellow';
      fillAlpha = 0.95;
      lineWidth = 2.5;
    }

    ctx.save();
    ctx.lineWidth = lineWidth;
    ctx.fillStyle = fillColor;
    ctx.strokeStyle = strokeColor;

    if (style.shape === 'ring') {
      ctx.globalAlpha = fillAlpha;
      drawMarkerShape(ctx, 'ring', pt.x, pt.y, r);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, r * 0.45, 0, 2 * Math.PI);
      ctx.fill();
    } else {
      ctx.globalAlpha = fillAlpha;
      drawMarkerShape(ctx, style.shape, pt.x, pt.y, r);
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawShape(ctx, loc, isHovered, isSelected) {
    const type = loc.Properties.Shape;
    ctx.save();
    let baseColor = getColorByType(loc.Properties.AreaType || loc.Properties.Type, loc)?.color || 'white';
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
      const center = imageCoordsToCanvasCoords(loc._imgCircle.cx, loc._imgCircle.cy);
      const outer = imageCoordsToCanvasCoords(loc._imgCircle.ox, loc._imgCircle.oy);
      const radius = outer.x - center.x;
      ctx.beginPath();
      ctx.arc(center.x, center.y, radius, 0, 2 * Math.PI);
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
    } else if (type === 'Rectangle') {
      const start = imageCoordsToCanvasCoords(loc._imgRect.sx, loc._imgRect.sy);
      const end = imageCoordsToCanvasCoords(loc._imgRect.ex, loc._imgRect.ey);
      const width = end.x - start.x;
      const height = start.y - end.y;
      ctx.beginPath();
      ctx.rect(start.x, start.y - height, width, height);
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.stroke();
    } else if (type === 'Polygon') {
      const verts = (loc._imgVerts ?? []).map(v => imageCoordsToCanvasCoords(v.x, v.y));
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
      // Draw as point — dispatch per location type
      if (!loc._imgPoint) { ctx.restore(); return; }
      const pt = imageCoordsToCanvasCoords(loc._imgPoint.x, loc._imgPoint.y);
      drawPointMarker(ctx, loc.Properties.Type, pt, isHovered, isSelected);
    }
    ctx.restore();
  }

  function drawSearchResult(ctx, loc, index) {
    // Draw shape with its actual color at reduced opacity, plus a numbered label
    const shape = loc.Properties.Shape;
    const isArea = ['Circle', 'Rectangle', 'Polygon'].includes(shape);
    const baseColor = getColorByType(loc.Properties.AreaType || loc.Properties.Type, loc)?.color || 'yellow';
    ctx.save();
    ctx.shadowBlur = 0;
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.35;
    ctx.strokeStyle = baseColor;
    ctx.fillStyle = baseColor;

    if (shape === 'Circle') {
      const center = imageCoordsToCanvasCoords(loc._imgCircle.cx, loc._imgCircle.cy);
      const outer = imageCoordsToCanvasCoords(loc._imgCircle.ox, loc._imgCircle.oy);
      const radius = outer.x - center.x;
      ctx.beginPath();
      ctx.arc(center.x, center.y, radius, 0, 2 * Math.PI);
      ctx.fill();
      ctx.globalAlpha = 0.7;
      ctx.stroke();
    } else if (shape === 'Rectangle') {
      const start = imageCoordsToCanvasCoords(loc._imgRect.sx, loc._imgRect.sy);
      const end = imageCoordsToCanvasCoords(loc._imgRect.ex, loc._imgRect.ey);
      const width = end.x - start.x;
      const height = start.y - end.y;
      ctx.beginPath();
      ctx.rect(start.x, start.y - height, width, height);
      ctx.fill();
      ctx.globalAlpha = 0.7;
      ctx.stroke();
    } else if (shape === 'Polygon') {
      const verts = (loc._imgVerts ?? []).map(v => imageCoordsToCanvasCoords(v.x, v.y));
      if (verts.length > 1) {
        ctx.beginPath();
        ctx.moveTo(verts[0].x, verts[0].y);
        for (let i = 1; i < verts.length; i++) ctx.lineTo(verts[i].x, verts[i].y);
        ctx.closePath();
        ctx.fill();
        ctx.globalAlpha = 0.7;
        ctx.stroke();
      }
    } else {
      // Point location
      if (!loc._imgPoint) { ctx.restore(); return; }
      const pt = imageCoordsToCanvasCoords(loc._imgPoint.x, loc._imgPoint.y);
      ctx.globalAlpha = 0.5;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 5, 0, 2 * Math.PI);
      ctx.fill();
      ctx.globalAlpha = 0.8;
      ctx.stroke();
    }

    // Draw numbered label for areas
    if (isArea && loc._imgPoint) {
      const center = imageCoordsToCanvasCoords(loc._imgPoint.x, loc._imgPoint.y);
      const label = String(index + 1);
      const fontSize = 14;
      ctx.globalAlpha = 1;
      ctx.font = `bold ${fontSize}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const textWidth = ctx.measureText(label).width;
      const radius = Math.max(10, (textWidth / 2) + 5);

      // Background circle
      ctx.beginPath();
      ctx.arc(center.x, center.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = 'white';
      ctx.stroke();

      // Number text
      ctx.fillStyle = 'white';
      ctx.fillText(label, center.x, center.y);
    }

    ctx.restore();
  }

  function drawDesaturated(ctx, loc) {
    // Draw non-matching areas with reduced opacity and gray color during search
    const shape = loc.Properties.Shape;
    ctx.save();
    ctx.shadowBlur = 0;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.12;
    ctx.strokeStyle = '#888';
    ctx.fillStyle = '#666';

    if (shape === 'Circle') {
      const center = imageCoordsToCanvasCoords(loc._imgCircle.cx, loc._imgCircle.cy);
      const outer = imageCoordsToCanvasCoords(loc._imgCircle.ox, loc._imgCircle.oy);
      const radius = outer.x - center.x;
      ctx.beginPath();
      ctx.arc(center.x, center.y, radius, 0, 2 * Math.PI);
      ctx.fill();
      ctx.globalAlpha = 0.25;
      ctx.stroke();
    } else if (shape === 'Rectangle') {
      const start = imageCoordsToCanvasCoords(loc._imgRect.sx, loc._imgRect.sy);
      const end = imageCoordsToCanvasCoords(loc._imgRect.ex, loc._imgRect.ey);
      const width = end.x - start.x;
      const height = start.y - end.y;
      ctx.beginPath();
      ctx.rect(start.x, start.y - height, width, height);
      ctx.fill();
      ctx.globalAlpha = 0.25;
      ctx.stroke();
    } else if (shape === 'Polygon') {
      const verts = (loc._imgVerts ?? []).map(v => imageCoordsToCanvasCoords(v.x, v.y));
      if (verts.length > 1) {
        ctx.beginPath();
        ctx.moveTo(verts[0].x, verts[0].y);
        for (let i = 1; i < verts.length; i++) ctx.lineTo(verts[i].x, verts[i].y);
        ctx.closePath();
        ctx.fill();
        ctx.globalAlpha = 0.25;
        ctx.stroke();
      }
    } else {
      // Point locations — very faint
      if (!loc._imgPoint) { ctx.restore(); return; }
      const pt = imageCoordsToCanvasCoords(loc._imgPoint.x, loc._imgPoint.y);
      ctx.globalAlpha = 0.15;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 3, 0, 2 * Math.PI);
      ctx.fill();
    }
    ctx.restore();
  }

  const SUB_DIVISIONS = 4;

  function drawFishingOverlay(ctx) {
    if (!fishingOverlay || !imageTileSize || !planet) return;
    const cellSize = imageTileSize / SUB_DIVISIONS;
    const totalRows = planet.Properties.Map.Height * SUB_DIVISIONS;
    const sectors = fishingOverlay.sectors;
    const searchKeys = fishingOverlay.searchKeys;
    const hasSearch = searchKeys != null && searchKeys.size > 0;
    const selKey = selectedFishingSector ? `${selectedFishingSector.Col},${selectedFishingSector.Row}` : null;
    const hovKey = hoveredFishingSector ? `${hoveredFishingSector.Col},${hoveredFishingSector.Row}` : null;

    ctx.save();
    for (const [key, data] of sectors) {
      const [colStr, rowStr] = key.split(',');
      const col = Number(colStr);
      const row = Number(rowStr);
      const imgX = col * cellSize;
      const imgY = (totalRows - row - 1) * cellSize;
      const topLeft = imageCoordsToCanvasCoords(imgX, imgY);
      const bottomRight = imageCoordsToCanvasCoords(imgX + cellSize, imgY + cellSize);
      const w = bottomRight.x - topLeft.x;
      const h = bottomRight.y - topLeft.y;

      const isSel = key === selKey;
      const isHov = key === hovKey;
      const isSearchHit = hasSearch && searchKeys.has(key);

      if (hasSearch && !isSearchHit && !isSel && !isHov) {
        ctx.globalAlpha = 0.08;
        ctx.fillStyle = '#666';
        ctx.fillRect(topLeft.x, topLeft.y, w, h);
        continue;
      }

      if (isSel) {
        ctx.globalAlpha = 0.7;
        ctx.fillStyle = data.color;
        ctx.fillRect(topLeft.x, topLeft.y, w, h);
        ctx.globalAlpha = 1;
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 3;
        ctx.strokeRect(topLeft.x, topLeft.y, w, h);
      } else if (isHov) {
        ctx.globalAlpha = 0.55;
        ctx.fillStyle = data.color;
        ctx.fillRect(topLeft.x, topLeft.y, w, h);
        ctx.globalAlpha = 0.9;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.lineWidth = 2;
        ctx.strokeRect(topLeft.x, topLeft.y, w, h);
      } else {
        ctx.globalAlpha = hasSearch && isSearchHit ? 0.5 : 0.35;
        ctx.fillStyle = data.color;
        ctx.fillRect(topLeft.x, topLeft.y, w, h);
      }
    }

    // Grid lines
    const totalCols = planet.Properties.Map.Width * SUB_DIVISIONS;
    ctx.globalAlpha = 0.25;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';

    for (let col = 0; col <= totalCols; col++) {
      const isMajor = col % SUB_DIVISIONS === 0;
      ctx.lineWidth = isMajor ? 1.5 : 0.5;
      if (!isMajor) ctx.globalAlpha = 0.12;
      else ctx.globalAlpha = 0.25;
      const x = col * cellSize;
      const start = imageCoordsToCanvasCoords(x, 0);
      const end = imageCoordsToCanvasCoords(x, totalRows * cellSize);
      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
      ctx.stroke();
    }
    for (let row = 0; row <= totalRows; row++) {
      const isMajor = row % SUB_DIVISIONS === 0;
      ctx.lineWidth = isMajor ? 1.5 : 0.5;
      if (!isMajor) ctx.globalAlpha = 0.12;
      else ctx.globalAlpha = 0.25;
      const y = row * cellSize;
      const start = imageCoordsToCanvasCoords(0, (totalRows - row) * cellSize);
      const end = imageCoordsToCanvasCoords(totalCols * cellSize, (totalRows - row) * cellSize);
      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function getFishingSectorAtCanvasPos(x, y) {
    if (!fishingOverlay || !imageTileSize || !planet) return null;
    const imageCoords = canvasCoordsToImageCoords(x, y);
    const cellSize = imageTileSize / SUB_DIVISIONS;
    const totalRows = planet.Properties.Map.Height * SUB_DIVISIONS;
    const col = Math.floor(imageCoords.x / cellSize);
    const row = totalRows - 1 - Math.floor(imageCoords.y / cellSize);
    if (col < 0 || row < 0) return null;
    if (col >= planet.Properties.Map.Width * SUB_DIVISIONS) return null;
    if (row >= totalRows) return null;
    const key = `${col},${row}`;
    if (fishingOverlay.sectors.has(key)) {
      return { Col: col, Row: row, key };
    }
    return null;
  }

  import { writable } from 'svelte/store';
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import Tooltip from './Tooltip.svelte';
  import { tooltip } from './Tooltip';
  import { navigate } from '$lib/util';
  import ContextMenu from './ContextMenu.svelte';
  import { contextmenu } from './ContextMenu';

  import { copyLocation, getTooltipText, getWaypoint, getMobAreaDifficulty } from '$lib/mapUtil';

  
  /**
   * @typedef {Object} Props
   * @property {string} [mapName]
   * @property {any} [planet]
   * @property {any} [locations] - No cache invalidation needed
   * @property {any} selected
   * @property {any} hovered
   * @property {any} [searchResults]
   */

  /** @type {Props} */
  let {
    mapName = '',
    planet = null,
    locations = $bindable([]),
    selected = $bindable(),
    hovered = $bindable(),
    searchResults = [],
    activeRecurringEvents = new Set(),
    embedMode = false,
    hideLayerToggles = false,
    fishingOverlay = null,
    selectedFishingSector = null,
    hoveredFishingSector = $bindable(null),
    onfishingsectorclick,
  } = $props();
  let filteredLocations = [];
  let filteredAreas = [];
  let filteredPoints = [];

  // Pre-compute search result lookup (Id → index) to avoid creating a Map every draw frame
  let searchResultMap = new Map();

  // ─── Layer filter system ──────────────────────────────────────────
  // Main toggle buttons (TP/LA/MA/TR/PVP/WE) map a short label to types
  // they control. Click = exclusive (others off). Shift+click = toggle in set.
  // "OTH" opens a popover with checkboxes for everything else.
  const OUTPOST_TP_CULL_RADIUS = 200; // meters — outposts within this distance
                                      // of a teleporter are hidden while zoomed out
  const POINT_DETAIL_THRESHOLD_EU = 20000; // visible width (game units) below which
                                           // fine-grained point markers become visible
  const ZOOM_GATED_POINT_TYPES = new Set([
    'Npc', 'Vendor', 'Interactable', 'Camp', 'City',
    'MagicalFlower', 'RevivalPoint', 'InstanceEntrance', 'Estate'
  ]);

  function pointPassesZoomGate(loc, visibleWidthGame) {
    const type = loc?.Properties?.Type;
    if (type === 'Teleporter') return true;
    if (type === 'Outpost') {
      // Near-TP outposts only visible when zoomed in; others always
      if (loc._nearTp) return visibleWidthGame <= POINT_DETAIL_THRESHOLD_EU;
      return true;
    }
    if (ZOOM_GATED_POINT_TYPES.has(type)) {
      return visibleWidthGame <= POINT_DETAIL_THRESHOLD_EU;
    }
    return true;
  }

  const MAIN_LAYERS = [
    { id: 'TP',  full: 'Teleporters',    color: '#00ffff', types: ['Teleporter'] },
    { id: 'LA',  full: 'Land Areas',     color: '#4ade80', types: ['LandArea'] },
    { id: 'MA',  full: 'Mob Areas',      color: '#facc15', types: ['MobArea'] },
    { id: 'TR',  full: 'Tree Areas',     color: '#15803d', types: ['TreeArea'] },
    { id: 'PVP', full: 'PvP Areas',      color: '#ef4444', types: ['PvpArea', 'PvpLootArea'] },
    { id: 'WE',  full: 'Wave Events',    color: '#da70d6', types: ['WaveEventArea'] }
  ];
  // Everything not covered by a main button lives in the "Other" popover.
  const OTHER_GROUPS = [
    { label: 'Points', items: [
      { type: 'Outpost',          label: 'Outposts' },
      { type: 'Npc',              label: 'NPCs' },
      { type: 'Vendor',           label: 'Vendors' },
      { type: 'Interactable',     label: 'Interactables' },
      { type: 'Camp',             label: 'Camps' },
      { type: 'City',             label: 'Cities' },
      { type: 'MagicalFlower',    label: 'Magical Flowers' },
      { type: 'RevivalPoint',     label: 'Revival Points' },
      { type: 'InstanceEntrance', label: 'Instance Entrances' },
      { type: 'Estate',           label: 'Estates' }
    ]},
    { label: 'Areas', items: [
      { type: 'ZoneArea',   label: 'Zone Areas' },
      { type: 'CityArea',   label: 'City Areas' },
      { type: 'EstateArea', label: 'Estate Areas' },
      { type: 'EventArea',  label: 'Event Areas' }
    ]}
  ];
  const DEFAULT_MAIN = new Set(['TP', 'MA', 'TR', 'PVP']);
  const DEFAULT_OTHER = new Set(['Outpost']);

  let activeMain = $state(new Set(DEFAULT_MAIN));
  let activeOther = $state(new Set(DEFAULT_OTHER));
  let otherPopoverOpen = $state(false);

  const mapLoadedStore = writable(false);

  let mapLoaded;

  initPromise();


  let imageTileSize;
  let imageToEntropiaRatio;
  let entropiaTileSize;

  let imgLoaded = false;

  let mapCenterPos = { x: 0, y: 0 };
  let mousePos = { x: 0, y: 0 };
  let dragStartPos = { x: 0, y: 0 };
  let dragMoved = false;
  let ignoreNextClick = false;
  const dragSlop = 4;

  let dragging = $state(false);
  let isTouching = false;
  let lastTouchDistance = null;
  let lastTouchCenter = null;
  let touchMoved = false;
  let touchStartPos = null;
  let touchSlop = 8;
  let touchMoveDistance = 0;
  let lastTouchTime = 0;
  let lastTapTime = 0;
  let lastTapPos = null;
  let inertiaId = null;
  let velocity = { x: 0, y: 0 };

  let zoom = 1;
  let targetZoom = zoom;
  let zoomTransitionStart = null;
  let zoomAnimationId = null;
  let moveAnimationId = null;
  
  let canvasElement = $state();
  let img;
  let ctx;
  let canvasBounds;
  let drawAnimationId;

  // Dirty-flag rendering: only redraw when something changes
  let _renderDirty = true;
  function markDirty() { _renderDirty = true; }


  let tooltipElement = $state();
  let tooltipText = $state();
  let tooltipShow = $state(false);
  let tooltipPos = $state({ x: 0, y: 0 });


  let editMode = false;
  let editType = null;
  
  let mapContextMenu = [
    {
      label: 'Copy Waypoint',
      action: (_, position) => {
        if (!browser) return;
        updateTransform();
        let canvasCoords = windowToCanvasCoords(position.x, position.y);
        let entropiaCoords = canvasCoordsToEntropiaCoords(canvasCoords.x, canvasCoords.y);
        navigator.clipboard.writeText(`/wp ${getWaypoint(planet.Properties.TechnicalName ?? planet.Name, entropiaCoords.x.toFixed(0), entropiaCoords.y.toFixed(0), 100, 'Waypoint')}`)
      }
    },
  ];
  let mapContextMenuElement = $state();








  function getMinZoom() {
    if (!img || !img.width || !img.height || !imageTileSize) return 0.1;
    return imageTileSize / Math.max(img.width, img.height);
  }

  function getMaxZoom() {
    return 5;
  }

  export async function focusOnLocation(location, focusZoom = null, immediate = false) {
    if (typeof window === 'undefined' || !location || !location.Properties?.Coordinates) {
      return;
    }

    await mapLoaded;
    const target = entropiaCoordsToImageCoords(location.Properties.Coordinates.Longitude, location.Properties.Coordinates.Latitude);
    const baseZoom = 1 / (planet.Properties.Map.Width * 0.35);
    const requestedZoom = focusZoom ?? baseZoom;
    const clampedZoom = Math.max(getMinZoom(), Math.min(getMaxZoom(), requestedZoom));

    // Only zoom in if currently zoomed out too far, never zoom out
    const finalZoom = Math.max(zoom, clampedZoom);

    if (immediate) {
      // Immediate move and zoom (no animation)
      mapCenterPos = { x: target.x, y: target.y };
      zoom = finalZoom;
      targetZoom = finalZoom;
      clampCoordinates();
    } else {
      moveAndZoomTo(target, finalZoom, 350);
    }
  }

  export async function panTo(location) {
    if (typeof window === 'undefined' || !location || !location.Properties?.Coordinates) return;
    await mapLoaded;
    const target = entropiaCoordsToImageCoords(
      location.Properties.Coordinates.Longitude,
      location.Properties.Coordinates.Latitude
    );
    moveTo(target, 250);
  }

  export async function panToCoords(longitude, latitude) {
    if (typeof window === 'undefined') return;
    await mapLoaded;
    const target = entropiaCoordsToImageCoords(longitude, latitude);
    moveTo(target, 250);
  }

  export function setZoom(level) {
    const clamped = Math.max(getMinZoom(), Math.min(getMaxZoom(), level));
    zoomTo(clamped, 200);
  }

  export function getZoom() { return zoom; }

  // Legacy layer name aliases used by the embed postMessage API
  const LEGACY_LAYER_ALIASES = {
    teleporters: 'TP', landAreas: 'LA', mobAreas: 'MA',
    pvpAreas: 'PVP', waveEventAreas: 'WE', treeAreas: 'TR',
    otherAreas: '__OTHER__'
  };
  export function setLayerVisibility(layer, visible) {
    const resolved = LEGACY_LAYER_ALIASES[layer] || layer;
    const main = new Set(activeMain);
    const other = new Set(activeOther);
    if (resolved === '__OTHER__') {
      if (visible) {
        for (const g of OTHER_GROUPS) for (const it of g.items) other.add(it.type);
      } else {
        other.clear();
      }
    } else {
      const def = MAIN_LAYERS.find(d => d.id === resolved);
      if (def) {
        if (visible) main.add(resolved); else main.delete(resolved);
      } else {
        if (visible) other.add(resolved); else other.delete(resolved);
      }
    }
    activeMain = main;
    activeOther = other;
    markDirty();
  }

  export function getLayerVisibility() {
    return {
      main: Array.from(activeMain),
      other: Array.from(activeOther)
    };
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

      // Invalidate image-space cache (planet/ratio changed)
      for (const loc of (locations ?? [])) loc._imgCacheRatio = null;
      $mapLoadedStore = true;
      markDirty();
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
      dragStartPos = { x: event.clientX, y: event.clientY };
      dragMoved = false;
    }
  }

  function onMouseMove(event) {
    if (dragging) {
      const visibleImageHeight = imageTileSize / (targetZoom || zoom);
      const imagePixelSize = canvasBounds.height / visibleImageHeight;

      const dx = (event.clientX - mousePos.x) / imagePixelSize;
      const dy = (event.clientY - mousePos.y) / imagePixelSize;
      mousePos.x = event.clientX;
      mousePos.y = event.clientY;
      const moveDx = event.clientX - dragStartPos.x;
      const moveDy = event.clientY - dragStartPos.y;
      if (!dragMoved && (moveDx * moveDx + moveDy * moveDy) > (dragSlop * dragSlop)) {
        dragMoved = true;
      }

      mapCenterPos.x -= dx;
      mapCenterPos.y -= dy;
      clampCoordinates();
      markDirty();
    }
  }

  function onMouseUp() {
    dragging = false;
    if (dragMoved) {
      ignoreNextClick = true;
    }
  }

  function onWheel(event) {
    event.preventDefault();
    updateTransform();

    // Get mouse position in canvas coordinates
    const canvasCoords = windowToCanvasCoords(event.clientX, event.clientY);

    // Get image coordinates under mouse before zoom
    const imageCoordsBefore = canvasCoordsToImageCoords(canvasCoords.x, canvasCoords.y);

    // Calculate the new zoom level
    const delta = Math.sign(event.deltaY);
    const oldZoom = zoom;
    let newZoom = oldZoom;
    if (delta < 0) {
      newZoom *= 11 / 10; // increase zoom
    } else {
      newZoom *= 10 / 11; // decrease zoom
    }

    // Clamp the zoom level to a minimum and maximum value
    newZoom = Math.max(getMinZoom(), Math.min(getMaxZoom(), newZoom));

    // Calculate position adjustment to keep the image point under mouse stationary
    const zoomRatio = newZoom / oldZoom;

    // Calculate the offset from center to mouse in image coords
    const offsetX = imageCoordsBefore.x - mapCenterPos.x;
    const offsetY = imageCoordsBefore.y - mapCenterPos.y;

    // After zoom, the same canvas point should map to the same image point
    mapCenterPos.x = imageCoordsBefore.x - offsetX / zoomRatio;
    mapCenterPos.y = imageCoordsBefore.y - offsetY / zoomRatio;

    // Set zoom directly (no animation) for smooth feel
    zoom = newZoom;
    targetZoom = newZoom;

    clampCoordinates();
    markDirty();
  }

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

  function onTouchStart(event) {
    if (!event.touches?.length) return;
    event.preventDefault();
    isTouching = true;
    touchMoved = false;
    touchMoveDistance = 0;
    velocity = { x: 0, y: 0 };
    lastTouchTime = Date.now();

    if (event.touches.length === 1) {
      dragging = true;
      mousePos.x = event.touches[0].clientX;
      mousePos.y = event.touches[0].clientY;
      touchStartPos = { x: mousePos.x, y: mousePos.y };
      lastTouchDistance = null;
      lastTouchCenter = null;
      if (inertiaId) {
        cancelAnimationFrame(inertiaId);
        inertiaId = null;
      }
    } else if (event.touches.length === 2) {
      dragging = false;
      lastTouchDistance = getTouchDistance(event.touches);
      lastTouchCenter = getTouchCenter(event.touches);
    }
  }

  function onTouchMove(event) {
    if (!event.touches?.length) return;
    event.preventDefault();
    if (touchStartPos && event.touches.length === 1) {
      const dx = event.touches[0].clientX - touchStartPos.x;
      const dy = event.touches[0].clientY - touchStartPos.y;
      touchMoveDistance = Math.sqrt(dx * dx + dy * dy);
      if (touchMoveDistance > touchSlop) {
        touchMoved = true;
      }
    }
    const now = Date.now();
    const dt = Math.max(16, now - lastTouchTime);

    if (event.touches.length === 1 && dragging) {
      const visibleImageHeight = imageTileSize / (targetZoom || zoom);
      const imagePixelSize = canvasBounds.height / visibleImageHeight;
      const dx = (event.touches[0].clientX - mousePos.x) / imagePixelSize;
      const dy = (event.touches[0].clientY - mousePos.y) / imagePixelSize;
      mousePos.x = event.touches[0].clientX;
      mousePos.y = event.touches[0].clientY;
      if (touchMoveDistance > touchSlop) {
        mapCenterPos.x -= dx;
        mapCenterPos.y -= dy;
        clampCoordinates();
        markDirty();
        velocity = {
          x: -(dx / dt) * 16,
          y: -(dy / dt) * 16
        };
      }
    } else if (event.touches.length === 2) {
      touchMoved = true;
      const distance = getTouchDistance(event.touches);
      const center = getTouchCenter(event.touches);
      if (lastTouchDistance) {
        const delta = distance / lastTouchDistance;
        targetZoom = Math.max(getMinZoom(), Math.min(getMaxZoom(), zoom * delta));
        zoom = targetZoom;
      }
      if (lastTouchCenter) {
        const visibleImageHeight = imageTileSize / (targetZoom || zoom);
        const imagePixelSize = canvasBounds.height / visibleImageHeight;
        const dx = (center.x - lastTouchCenter.x) / imagePixelSize;
        const dy = (center.y - lastTouchCenter.y) / imagePixelSize;
        mapCenterPos.x -= dx;
        mapCenterPos.y -= dy;
        clampCoordinates();
        markDirty();
      }
      lastTouchDistance = distance;
      lastTouchCenter = center;
    }
    lastTouchTime = now;
  }

  async function onTouchEnd(event) {
    event.preventDefault();
    if (!event.touches?.length) {
      dragging = false;
      isTouching = false;
      if (touchStartPos && !touchMoved) {
        const endTouch = event.changedTouches && event.changedTouches[0];
        const tapX = endTouch?.clientX ?? touchStartPos.x;
        const tapY = endTouch?.clientY ?? touchStartPos.y;
        const fakeEvent = {
          clientX: tapX,
          clientY: tapY
        };
        await handleCanvasClick(fakeEvent);
        const now = Date.now();
        if (lastTapTime && now - lastTapTime < 280 && lastTapPos) {
          const dx = tapX - lastTapPos.x;
          const dy = tapY - lastTapPos.y;
          if ((dx * dx + dy * dy) < 900) {
            const zoomFactor = 1.35;
            const nextZoom = Math.max(getMinZoom(), Math.min(getMaxZoom(), (targetZoom || zoom) * zoomFactor));
            zoomTo(nextZoom, 220);
            lastTapTime = 0;
            lastTapPos = null;
            return;
          }
        }
        lastTapTime = now;
        lastTapPos = { x: tapX, y: tapY };
      }
      if (touchMoved && (Math.abs(velocity.x) > 0.5 || Math.abs(velocity.y) > 0.5)) {
        const friction = 0.93;
        const step = () => {
          velocity.x *= friction;
          velocity.y *= friction;
          mapCenterPos.x += velocity.x;
          mapCenterPos.y += velocity.y;
          clampCoordinates();
          markDirty();
          if (Math.abs(velocity.x) < 0.1 && Math.abs(velocity.y) < 0.1) {
            inertiaId = null;
            return;
          }
          inertiaId = requestAnimationFrame(step);
        };
        inertiaId = requestAnimationFrame(step);
      }
      touchStartPos = null;
      lastTouchDistance = null;
      lastTouchCenter = null;
      return;
    }

    if (event.touches.length === 1) {
      dragging = true;
      mousePos.x = event.touches[0].clientX;
      mousePos.y = event.touches[0].clientY;
      lastTouchDistance = null;
      lastTouchCenter = null;
    }
  }

  function animateZoom(timestamp, animationDuration = 200) {
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
    markDirty();

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
    markDirty();

    if (progress < 1) {
      moveAnimationId = requestAnimationFrame((timestamp) => animateMove(timestamp, animationDuration));
    } else {
      moveTransitionStart = null;
      moveAnimationId = null;
    }
  }

  let target = null;
  let moveTransitionStart = null;

  function moveTo(position, animationDuration = 220) {
    target = position;

    moveTransitionStart = -1;

    if (moveAnimationId != null) {
      cancelAnimationFrame(moveAnimationId);
      moveAnimationId = null;
    }

    moveAnimationId = requestAnimationFrame((timestamp) => animateMove(timestamp, animationDuration));
  }

  function zoomTo(zoom, animationDuration = 120) {
    targetZoom = zoom;

    zoomTransitionStart = -1;

    if (zoomAnimationId != null) {
      cancelAnimationFrame(zoomAnimationId);
      zoomAnimationId = null;
    }

    zoomAnimationId = requestAnimationFrame((timestamp) => animateZoom(timestamp, animationDuration));
  }

  function moveAndZoomTo(position, zoom, animationDuration = 350) {
    moveTo(position, animationDuration);
    zoomTo(zoom, animationDuration);
  }


  function initCanvas() {
    canvasBounds = canvasElement.getBoundingClientRect();

    const dpr = typeof window !== 'undefined' ? window.devicePixelRatio : 1;
    canvasElement.width = canvasBounds.width * dpr;
    canvasElement.height = canvasBounds.height * dpr;

    ctx = canvasElement.getContext('2d');
    ctx.scale(dpr, dpr);

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
    if (!_renderDirty) {
      drawAnimationId = requestAnimationFrame(draw);
      return;
    }
    _renderDirty = false;

    ctx.clearRect(0, 0, canvasBounds.width, canvasBounds.height);
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, canvasBounds.width, canvasBounds.height);

    if (!imgLoaded) {
      drawAnimationId = requestAnimationFrame(draw);
      return;
    }

    // Precompute transform for this frame (used by imageCoordsToCanvasCoords)
    updateTransform();

    // Calculate the visible height and width of the image based on the zoom level
    const visibleHeight = imageTileSize / zoom;
    const visibleWidth = (canvasBounds.width / canvasBounds.height) * visibleHeight;

    // Calculate the source and destination coordinates and dimensions
    const srcX = _txSrcX;
    const srcY = _txSrcY;
    const destWidth = canvasBounds.width;
    const destHeight = (visibleHeight / visibleWidth) * destWidth;

    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, srcX, srcY, visibleWidth, visibleHeight, 0, 0, destWidth, destHeight);

    // Draw fishing overlay (below location overlays)
    if (fishingOverlay) {
      drawFishingOverlay(ctx);
    }

    // Ensure image-space cache is ready for all visible locations
    prepareLocationsCache();

    // Viewport bounds in image space for culling off-screen shapes
    const viewX0 = srcX;
    const viewY0 = srcY;
    const viewX1 = srcX + visibleWidth;
    const viewY1 = srcY + visibleHeight;
    const isInViewport = (loc) => {
      const bb = loc._imgBbox;
      if (!bb) return true;
      return bb.x1 >= viewX0 && bb.x0 <= viewX1 && bb.y1 >= viewY0 && bb.y0 <= viewY1;
    };

    // Skip location overlays when fishing overlay is active
    if (!fishingOverlay) {
      // Draw areas first (below), then point locations on top
      // Cache reactive values to avoid repeated proxy reads in hot loop
      const _searchMap = searchResultMap;
      const _hoveredId = hovered?.Id;
      const _selectedId = selected?.Id;
      const hasSearch = _searchMap.size > 0;

      // First pass: draw areas (they go underneath)
      for (const loc of filteredAreas) {
        if (!isInViewport(loc)) continue;
        const isHov = _hoveredId != null && loc.Id === _hoveredId;
        const isSel = _selectedId != null && loc.Id === _selectedId;
        if (hasSearch && _searchMap.has(loc.Id) && !isHov && !isSel) {
          drawSearchResult(ctx, loc, _searchMap.get(loc.Id));
        } else if (hasSearch && !_searchMap.has(loc.Id) && !isHov && !isSel) {
          drawDesaturated(ctx, loc);
        } else {
          drawShape(ctx, loc, isHov, isSel);
        }
      }

      // Second pass: draw point locations (they go on top)
      // Compute visible width in game units for zoom gate
      const _visGameW = (imageTileSize / zoom) * (canvasBounds.width / canvasBounds.height)
                        * imageToEntropiaRatio;
      for (const loc of filteredPoints) {
        if (!isInViewport(loc)) continue;
        const isHov = _hoveredId != null && loc.Id === _hoveredId;
        const isSel = _selectedId != null && loc.Id === _selectedId;
        const isTeleporter = loc.Properties?.Type === 'Teleporter';
        const isSearchHit = _searchMap.has(loc.Id);
        // Zoom gate — bypass for hover/selection/search hits
        if (!isHov && !isSel && !isSearchHit && !pointPassesZoomGate(loc, _visGameW)) {
          continue;
        }
        if (hasSearch && isSearchHit && !isHov && !isSel) {
          drawSearchResult(ctx, loc, _searchMap.get(loc.Id));
        } else if (hasSearch && !isSearchHit && !isHov && !isSel && !isTeleporter) {
          drawDesaturated(ctx, loc);
        } else {
          drawShape(ctx, loc, isHov, isSel);
        }
      }
    }

    drawAnimationId = requestAnimationFrame(draw);
  }

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
  function getShapeAtCanvasPos(x, y, buffer = 0) {
    const isAreaType = (loc) => ['Circle', 'Rectangle', 'Polygon'].includes(loc.Properties?.Shape);

    // Viewport culling in image space — skip off-screen locations (uses precomputed transform)
    const visibleHeight = imageTileSize / zoom;
    const visibleWidth = visibleHeight * canvasBounds.width / canvasBounds.height;
    const viewX0 = _txSrcX;
    const viewY0 = _txSrcY;
    const viewX1 = _txSrcX + visibleWidth;
    const viewY1 = _txSrcY + visibleHeight;
    const isInViewport = (loc) => {
      const bb = loc._imgBbox;
      if (!bb) return true;
      return bb.x1 >= viewX0 && bb.x0 <= viewX1 && bb.y1 >= viewY0 && bb.y0 <= viewY1;
    };

    // Helper to check if point hits a location (uses cached image-space coords)
    const checkHit = (loc, i) => {
      if (!loc._imgBbox) return null;
      const type = loc.Properties.Shape;
      if (type === 'Circle') {
        const center = imageCoordsToCanvasCoords(loc._imgCircle.cx, loc._imgCircle.cy);
        const outer = imageCoordsToCanvasCoords(loc._imgCircle.ox, loc._imgCircle.oy);
        const radius = outer.x - center.x + buffer;
        const dx = x - center.x, dy = y - center.y;
        if (dx * dx + dy * dy <= radius * radius) return { type: 'area', shape: loc, index: i };
      } else if (type === 'Rectangle') {
        const start = imageCoordsToCanvasCoords(loc._imgRect.sx, loc._imgRect.sy);
        const end = imageCoordsToCanvasCoords(loc._imgRect.ex, loc._imgRect.ey);
        const width = end.x - start.x;
        const height = start.y - end.y;
        if (
          x >= start.x - buffer &&
          x <= start.x + width + buffer &&
          y >= start.y - height - buffer &&
          y <= start.y + buffer
        ) return { type: 'area', shape: loc, index: i };
      } else if (type === 'Polygon') {
        const verts = (loc._imgVerts ?? []).map(v => imageCoordsToCanvasCoords(v.x, v.y));
        if (pointInPolygon({ x, y }, verts)) return { type: 'area', shape: loc, index: i };
      } else {
        const pt = imageCoordsToCanvasCoords(loc._imgPoint.x, loc._imgPoint.y);
        if (loc.Properties.Type === 'Teleporter') {
          const dx = x - pt.x, dy = y - pt.y;
          const radius = 14 + buffer;
          if (dx * dx + dy * dy <= radius * radius) return { type: 'location', shape: loc, index: i };
        } else {
          const size = 6 + buffer;
          if (x >= pt.x - size && x <= pt.x + size && y >= pt.y - size && y <= pt.y + size) return { type: 'location', shape: loc, index: i };
        }
      }
      return null;
    };

    // Zoom gate matches draw loop — don't hit-test invisible points
    const _hitVisGameW = visibleWidth * imageToEntropiaRatio;

    // First pass: check point locations (higher click priority - they render on top)
    for (let i = filteredLocations.length - 1; i >= 0; i--) {
      const loc = filteredLocations[i];
      if (isAreaType(loc)) continue;
      if (!isInViewport(loc)) continue;
      if (!pointPassesZoomGate(loc, _hitVisGameW)) continue;
      const hit = checkHit(loc, i);
      if (hit) return hit;
    }

    // Second pass: check areas (lower click priority - they render below)
    for (let i = filteredLocations.length - 1; i >= 0; i--) {
      const loc = filteredLocations[i];
      if (!isAreaType(loc)) continue;
      if (!isInViewport(loc)) continue;
      const hit = checkHit(loc, i);
      if (hit) return hit;
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
    if (dragging) {
      if (hovered) {
        hovered = null;
        canvasHover = null;
        canvasHoverType = null;
        canvasHoverIndex = null;
        tooltipShow = false;
        markDirty();
      }
      if (hoveredFishingSector) {
        hoveredFishingSector = null;
        markDirty();
      }
      return;
    }
    const rect = canvasElement.getBoundingClientRect();
    const x = (event.clientX - rect.left);
    const y = (event.clientY - rect.top);
    updateTransform();

    // Fishing overlay hover takes priority when active
    if (fishingOverlay) {
      const prevHovKey = hoveredFishingSector ? `${hoveredFishingSector.Col},${hoveredFishingSector.Row}` : null;
      const sector = getFishingSectorAtCanvasPos(x, y);
      if (sector) {
        hoveredFishingSector = { Col: sector.Col, Row: sector.Row };
        canvasElement.style.cursor = 'pointer';
        const sectorData = fishingOverlay.sectors.get(sector.key);
        const fishNames = sectorData?.fish?.map(f => f.Name).join(', ') || '';
        tooltipText = fishNames;
        tooltipShow = !!fishNames;
        tooltipPos = { x: event.clientX, y: event.clientY };
      } else {
        hoveredFishingSector = null;
        canvasElement.style.cursor = 'default';
        tooltipShow = false;
      }
      hovered = null;
      canvasHover = null;
      const newKey = hoveredFishingSector ? `${hoveredFishingSector.Col},${hoveredFishingSector.Row}` : null;
      if (newKey !== prevHovKey) markDirty();
      return;
    }

    prepareLocationsCache();
    const hit = getShapeAtCanvasPos(x, y);
    const prevHovered = hovered;
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
    if (hovered?.Id !== prevHovered?.Id) markDirty();
  }

  function getAllShapesAtCanvasPos(x, y, buffer = 0) {
    // Returns all shapes at the given canvas position, with point locations first (topmost), then areas
    const isAreaType = (loc) => ['Circle', 'Rectangle', 'Polygon'].includes(loc.Properties?.Shape);
    const foundLocations = [];
    const foundAreas = [];

    // Viewport culling in image space (uses precomputed transform)
    const visibleHeight = imageTileSize / zoom;
    const visibleWidth = visibleHeight * canvasBounds.width / canvasBounds.height;
    const viewX0 = _txSrcX;
    const viewY0 = _txSrcY;
    const viewX1 = _txSrcX + visibleWidth;
    const viewY1 = _txSrcY + visibleHeight;

    for (let i = filteredLocations.length - 1; i >= 0; i--) {
      const loc = filteredLocations[i];
      const bb = loc._imgBbox;
      if (bb && (bb.x1 < viewX0 || bb.x0 > viewX1 || bb.y1 < viewY0 || bb.y0 > viewY1)) continue;
      const type = loc.Properties.Shape;
      if (type === 'Circle') {
        const center = imageCoordsToCanvasCoords(loc._imgCircle.cx, loc._imgCircle.cy);
        const outer = imageCoordsToCanvasCoords(loc._imgCircle.ox, loc._imgCircle.oy);
        const radius = outer.x - center.x + buffer;
        const dx = x - center.x, dy = y - center.y;
        if (dx * dx + dy * dy <= radius * radius) foundAreas.push({ type: 'area', shape: loc });
      } else if (type === 'Rectangle') {
        const start = imageCoordsToCanvasCoords(loc._imgRect.sx, loc._imgRect.sy);
        const end = imageCoordsToCanvasCoords(loc._imgRect.ex, loc._imgRect.ey);
        const width = end.x - start.x;
        const height = start.y - end.y;
        if (
          x >= start.x - buffer &&
          x <= start.x + width + buffer &&
          y >= start.y - height - buffer &&
          y <= start.y + buffer
        ) foundAreas.push({ type: 'area', shape: loc });
      } else if (type === 'Polygon') {
        const verts = (loc._imgVerts ?? []).map(v => imageCoordsToCanvasCoords(v.x, v.y));
        if (pointInPolygon({ x, y }, verts)) foundAreas.push({ type: 'area', shape: loc });
      } else {
        const pt = imageCoordsToCanvasCoords(loc._imgPoint.x, loc._imgPoint.y);
        if (loc.Properties.Type === 'Teleporter') {
          const dx = x - pt.x, dy = y - pt.y;
          const radius = 14 + buffer;
          if (dx * dx + dy * dy <= radius * radius) foundLocations.push({ type: 'location', shape: loc });
        } else {
          const size = 6 + buffer;
          if (x >= pt.x - size && x <= pt.x + size && y >= pt.y - size && y <= pt.y + size) foundLocations.push({ type: 'location', shape: loc });
        }
      }
    }
    // Return point locations first (higher priority), then areas
    return [...foundLocations, ...foundAreas];
  }

  function getNearestShapesAtCanvasPos(x, y, buffer = 0) {
    const candidates = [];

    // Viewport culling in image space (uses precomputed transform)
    const visibleHeight = imageTileSize / zoom;
    const visibleWidth = visibleHeight * canvasBounds.width / canvasBounds.height;
    const viewX0 = _txSrcX;
    const viewY0 = _txSrcY;
    const viewX1 = _txSrcX + visibleWidth;
    const viewY1 = _txSrcY + visibleHeight;

    for (let i = filteredLocations.length - 1; i >= 0; i--) {
      const loc = filteredLocations[i];
      const bb = loc._imgBbox;
      if (bb && (bb.x1 < viewX0 || bb.x0 > viewX1 || bb.y1 < viewY0 || bb.y0 > viewY1)) continue;
      const type = loc.Properties.Shape;
      if (type === 'Circle') {
        const center = imageCoordsToCanvasCoords(loc._imgCircle.cx, loc._imgCircle.cy);
        const outer = imageCoordsToCanvasCoords(loc._imgCircle.ox, loc._imgCircle.oy);
        const radius = outer.x - center.x + buffer;
        const dx = x - center.x, dy = y - center.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist <= radius) candidates.push({ type: 'area', shape: loc, dist, priority: 2 });
      } else if (type === 'Rectangle') {
        const start = imageCoordsToCanvasCoords(loc._imgRect.sx, loc._imgRect.sy);
        const end = imageCoordsToCanvasCoords(loc._imgRect.ex, loc._imgRect.ey);
        const width = end.x - start.x;
        const height = start.y - end.y;
        if (
          x >= start.x - buffer &&
          x <= start.x + width + buffer &&
          y >= start.y - height - buffer &&
          y <= start.y + buffer
        ) {
          const cx = start.x + width / 2;
          const cy = start.y - height / 2;
          const dx = x - cx, dy = y - cy;
          const dist = Math.sqrt(dx * dx + dy * dy);
          candidates.push({ type: 'area', shape: loc, dist, priority: 2 });
        }
      } else if (type === 'Polygon') {
        const verts = (loc._imgVerts ?? []).map(v => imageCoordsToCanvasCoords(v.x, v.y));
        if (pointInPolygon({ x, y }, verts)) {
          candidates.push({ type: 'area', shape: loc, dist: 0, priority: 2 });
        }
      } else {
        const pt = imageCoordsToCanvasCoords(loc._imgPoint.x, loc._imgPoint.y);
        const dx = x - pt.x, dy = y - pt.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const radius = (loc.Properties.Type === 'Teleporter' ? 14 : 6) + buffer;
        if (dist <= radius) {
          candidates.push({ type: 'location', shape: loc, dist, priority: 0 });
        }
      }
    }
    if (candidates.length === 0) return [];
    // Sort by priority first (locations = 0 before areas = 2), then by distance
    return candidates
      .sort((a, b) => (a.priority - b.priority) || (a.dist - b.dist))
      .map(({ type, shape }) => ({ type, shape }));
  }

  function truncateName(name) {
    if (!name) return '';
    return name.length > 80 ? name.slice(0, 77) + '...' : name;
  }

  async function handleCanvasClick(event) {
    if (ignoreNextClick) {
      ignoreNextClick = false;
      return;
    }
    const rect = canvasElement.getBoundingClientRect();
    const x = (event.clientX - rect.left);
    const y = (event.clientY - rect.top);
    updateTransform();

    // Fishing overlay click
    if (fishingOverlay) {
      const sector = getFishingSectorAtCanvasPos(x, y);
      if (sector) {
        onfishingsectorclick?.(sector.Col, sector.Row);
      } else {
        onfishingsectorclick?.(null, null);
      }
      markDirty();
      return;
    }

    prepareLocationsCache();
    const hitBuffer = typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches ? 28 : 0;
    const hits = getAllShapesAtCanvasPos(x, y, hitBuffer);
    const currentId = selected?.Id;
    if (hits.length === 0) {
      selected = null;
      hovered = null;
      markDirty();
      if (!embedMode && typeof window !== 'undefined' && planet) {
        const planetSimpleName = planet.Name.replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
        await navigate(`/maps/${planetSimpleName}`);
      }
      return;
    }
    const bestHits = getNearestShapesAtCanvasPos(x, y, hitBuffer);
    const targetHit = bestHits[0] || hits[0];
    selected = targetHit.shape;
    markDirty();
    if (targetHit.shape?.Properties?.Coordinates) {
      if (!embedMode && typeof window !== 'undefined' && planet && targetHit.shape?.Id) {
        const planetSimpleName = planet.Name.replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
        const newUrl = `/maps/${planetSimpleName}/${targetHit.shape.Id}`;
        if (targetHit.shape.Id !== currentId) {
          await navigate(newUrl);
        }
      }
    }
  }

  function handleCanvasRightClick(event) {
    event.preventDefault();
    const rect = canvasElement.getBoundingClientRect();
    const x = (event.clientX - rect.left);
    const y = (event.clientY - rect.top);
    updateTransform();
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
    canvasElement.addEventListener('touchstart', onTouchStart, { passive: false });
    canvasElement.addEventListener('touchmove', onTouchMove, { passive: false });
    canvasElement.addEventListener('touchend', onTouchEnd, { passive: false });
    canvasElement.addEventListener('touchcancel', onTouchEnd, { passive: false });
  });
  onDestroy(() => {
    if (typeof window !== 'undefined' && canvasElement) {
      canvasElement.removeEventListener('mousemove', handleCanvasMouseMove);
      canvasElement.removeEventListener('click', handleCanvasClick);
      canvasElement.removeEventListener('contextmenu', handleCanvasRightClick);
      canvasElement.removeEventListener('touchstart', onTouchStart);
      canvasElement.removeEventListener('touchmove', onTouchMove);
      canvasElement.removeEventListener('touchend', onTouchEnd);
      canvasElement.removeEventListener('touchcancel', onTouchEnd);
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

  // --- Image-space coordinate cache ---
  // entropiaCoordsToImageCoords is stable for a given planet (depends only on planet map config).
  // Pre-computing image coords per location avoids calling entropiaCoordsToImageCoords every frame.
  // Only imageCoordsToCanvasCoords (which depends on pan/zoom) needs to run per frame.

  function _prepareLocImgCache(loc) {
    const shape = loc.Properties?.Shape;
    const d = loc.Properties?.Data;
    if (shape === 'Circle') {
      const c = entropiaCoordsToImageCoords(d.x, d.y);
      const o = entropiaCoordsToImageCoords(d.x + d.radius, d.y);
      loc._imgCircle = { cx: c.x, cy: c.y, ox: o.x, oy: o.y };
      const r = o.x - c.x;
      loc._imgBbox = { x0: c.x - r, y0: c.y - r, x1: c.x + r, y1: c.y + r };
    } else if (shape === 'Rectangle') {
      const s = entropiaCoordsToImageCoords(d.x, d.y);
      const e = entropiaCoordsToImageCoords(d.x + d.width, d.y + d.height);
      loc._imgRect = { sx: s.x, sy: s.y, ex: e.x, ey: e.y };
      loc._imgBbox = { x0: Math.min(s.x, e.x), y0: Math.min(s.y, e.y), x1: Math.max(s.x, e.x), y1: Math.max(s.y, e.y) };
    } else if (shape === 'Polygon') {
      const verts = (d?.vertices ?? []).reduce((result, value, idx, arr) => {
        if (idx % 2 === 0) result.push([value, arr[idx + 1]]);
        return result;
      }, []).map(v => entropiaCoordsToImageCoords(v[0], v[1]));
      loc._imgVerts = verts;
      if (verts.length > 0) {
        let x0 = verts[0].x, y0 = verts[0].y, x1 = verts[0].x, y1 = verts[0].y;
        for (const v of verts) {
          if (v.x < x0) x0 = v.x; if (v.y < y0) y0 = v.y;
          if (v.x > x1) x1 = v.x; if (v.y > y1) y1 = v.y;
        }
        loc._imgBbox = { x0, y0, x1, y1 };
      } else {
        loc._imgBbox = null;
      }
    } else {
      const coords = loc.Properties?.Coordinates;
      if (coords) {
        const pt = entropiaCoordsToImageCoords(coords.Longitude, coords.Latitude);
        loc._imgPoint = pt;
        loc._imgBbox = { x0: pt.x - 8, y0: pt.y - 8, x1: pt.x + 8, y1: pt.y + 8 };
      }
    }
    loc._imgCacheRatio = imageToEntropiaRatio;
  }

  function prepareLocationsCache() {
    if (!imageToEntropiaRatio) return;
    for (const loc of filteredLocations) {
      if (loc._imgCacheRatio !== imageToEntropiaRatio) {
        _prepareLocImgCache(loc);
      }
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

  // Precomputed transform parameters (updated once per frame in draw())
  let _txSrcX = 0, _txSrcY = 0, _txScaleX = 1, _txScaleY = 1;

  function updateTransform() {
    const visibleHeight = imageTileSize / zoom;
    const visibleWidth = (canvasBounds.width / canvasBounds.height) * visibleHeight;
    _txSrcX = mapCenterPos.x - visibleWidth / 2;
    _txSrcY = mapCenterPos.y - visibleHeight / 2;
    _txScaleX = canvasBounds.width / visibleWidth;
    _txScaleY = canvasBounds.height / visibleHeight;
  }

  function imageCoordsToCanvasCoords(imageX, imageY) {
    return {
      x: (imageX - _txSrcX) * _txScaleX,
      y: (imageY - _txSrcY) * _txScaleY
    };
  }

  function canvasCoordsToImageCoords(canvasX, canvasY) {
    // Inverse of imageCoordsToCanvasCoords using precomputed transform
    return {
      x: _txSrcX + canvasX / _txScaleX,
      y: _txSrcY + canvasY / _txScaleY
    };
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
      x: (windowX - rect.left),
      y: (windowY - rect.top),
    };
  }

  export function canvasToWindowCoords(canvasX, canvasY) {
    if (typeof window === 'undefined') {
      return { x: 0, y: 0 };
    }

    const rect = canvasElement.getBoundingClientRect();
    return {
      x: canvasX + rect.left,
      y: canvasY + rect.top,
    };
  }

  function getAreas(locations) {
    return locations.filter(x => x.Properties?.Type === 'Area' || !!x.Properties?.AreaType);
  }

  function getColorByType(type, loc) {
    switch (type) {
      case 'LandArea':
        return { color: 'green', pattern: null };
      case 'TreeArea':
        return { color: '#15803d', pattern: null };
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
      case 'CityArea':
        return { color: '#90ee90', pattern: null };
      case 'EstateArea':
        return { color: '#deb887', pattern: null };
      case 'WaveEventArea':
        return { color: '#da70d6', pattern: null };
      case 'MobArea': {
        const reColor = loc?.Properties?.RecurringEventColor;
        if (reColor) return { color: reColor, pattern: null };
        const diff = loc?._difficulty;
        return { color: diff?.color || 'yellow', pattern: null };
      }
      default: {
        const style = MARKER_STYLES[type];
        return { color: style?.color || 'white', pattern: null };
      }
    }
  }

  let mapContextMenuObject = $state({ contextMenu: null, payload: null })


  // ─── Layer toggle handlers ────────────────────────────────────────
  function handleLayerClick(id, ev) {
    const shift = ev && (ev.shiftKey || ev.metaKey);
    const next = new Set(activeMain);
    if (shift) {
      if (next.has(id)) next.delete(id); else next.add(id);
    } else {
      // Exclusive among main buttons — OTH selection untouched
      next.clear();
      next.add(id);
    }
    activeMain = next;
    markDirty();
  }
  function handleOtherClick(ev) {
    // OTH button just opens/closes the popover — no exclusive change
    ev.stopPropagation();
    otherPopoverOpen = !otherPopoverOpen;
  }
  function closeOtherPopover() {
    if (otherPopoverOpen) otherPopoverOpen = false;
  }
  function toggleOtherItem(type) {
    const next = new Set(activeOther);
    if (next.has(type)) next.delete(type); else next.add(type);
    activeOther = next;
    markDirty();
  }
  function selectAllOther() {
    const all = new Set();
    for (const g of OTHER_GROUPS) for (const it of g.items) all.add(it.type);
    activeOther = all;
    markDirty();
  }
  function selectNoneOther() {
    activeOther = new Set();
    markDirty();
  }

  // Pre-compute outpost-near-teleporter flag once per locations load
  let _tpCullVersion = 0;
  function computeOutpostCull(locs) {
    if (!locs || !locs.length) return;
    const tps = [];
    for (const loc of locs) {
      if (loc.Properties?.Type === 'Teleporter') {
        const c = loc.Properties?.Coordinates;
        if (c && c.Longitude != null && c.Latitude != null) {
          tps.push([c.Longitude, c.Latitude]);
        }
      }
    }
    const r2 = OUTPOST_TP_CULL_RADIUS * OUTPOST_TP_CULL_RADIUS;
    for (const loc of locs) {
      if (loc.Properties?.Type !== 'Outpost') continue;
      const c = loc.Properties?.Coordinates;
      if (!c || c.Longitude == null || c.Latitude == null) { loc._nearTp = false; continue; }
      let near = false;
      for (const [tx, ty] of tps) {
        const dx = c.Longitude - tx;
        const dy = c.Latitude - ty;
        if (dx * dx + dy * dy <= r2) { near = true; break; }
      }
      loc._nearTp = near;
    }
  }

  $effect(() => { searchResultMap = new Map(searchResults.map((sr, i) => [sr.Id, i])); if (browser) markDirty(); });
  $effect(() => { if (fishingOverlay) markDirty(); });
  $effect(() => {
    if (locations) {
      computeOutpostCull(locations);
      _tpCullVersion++;
      if (browser) markDirty();
    }
  });
  // Filter locations based on layer toggles
  $effect(() => {
    const _deps = [activeMain, activeOther, selected, searchResults, activeRecurringEvents, _tpCullVersion];
    const searchResultIds = new Set(searchResults.map(sr => sr.Id));
    const mainTypeSet = new Set();
    for (const def of MAIN_LAYERS) {
      if (activeMain.has(def.id)) for (const t of def.types) mainTypeSet.add(t);
    }
    filteredLocations = locations ? locations.filter(loc => {
      if (selected && loc.Id === selected.Id) return true;
      if (searchResultIds.has(loc.Id)) return true;

      const type = loc.Properties?.Type;
      const areaType = loc.Properties?.AreaType || type;
      const key = areaType === 'Area' ? null : areaType;

      // Main categories
      if (mainTypeSet.has(key)) {
        // Mob areas / wave events gated on active recurring events
        if (key === 'MobArea' || key === 'WaveEventArea') {
          const reName = loc.Properties?.RecurringEventName;
          if (reName) return activeRecurringEvents.has(reName);
        }
        return true;
      }

      // Other popover items
      if (activeOther.has(key) || activeOther.has(type)) return true;

      return false;
    }) : [];
    // Pre-split into areas and points for the two-pass draw loop
    const _areas = [], _points = [];
    for (const loc of filteredLocations) {
      const s = loc.Properties?.Shape;
      if (s === 'Circle' || s === 'Rectangle' || s === 'Polygon') _areas.push(loc);
      else _points.push(loc);
    }
    filteredAreas = _areas;
    filteredPoints = _points;
    if (browser) markDirty();
  });
  $effect(() => {
    if ($mapLoadedStore === false) {
      initPromise();
    }
  });
  $effect(() => {
    if (typeof window !== 'undefined') document.documentElement.style.setProperty('--cursorStatus', dragging ? 'grabbing' : 'default');
  });
  $effect(() => {
    if (mapName) reloadImage(mapName);
  });
  // Pre-compute difficulty colors for MobArea locations
  $effect(() => {
    if (locations) {
      for (const loc of locations) {
        if (loc.Properties?.AreaType === 'MobArea' && !loc._difficulty) {
          loc._difficulty = getMobAreaDifficulty(loc.Maturities);
        }
      }
    }
  });
  $effect(() => {
    mapContextMenuObject = { contextMenu: mapContextMenuElement, payload: null }
  });
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

  /* Layer toggles (bottom-left, desktop only) */
  .layer-toggles {
    position: absolute;
    bottom: 16px;
    left: 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    z-index: 10;
    align-items: flex-start;
  }

  .layer-btn {
    height: 32px;
    min-width: 40px;
    width: 40px;
    max-width: 40px;
    display: flex;
    align-items: center;
    padding: 0;
    background: rgba(0, 0, 0, 0.75);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    cursor: pointer;
    transition: max-width 0.22s ease, width 0.22s ease,
                background 0.15s, opacity 0.15s, border-color 0.15s;
    opacity: 0.5;
    white-space: nowrap;
    overflow: hidden;
    color: var(--text-color, #e8e8e8);
  }

  .layer-btn.active {
    opacity: 1;
    border-color: var(--accent-color, #4a9eff);
  }

  .layer-btn:hover {
    opacity: 1;
    background: rgba(0, 0, 0, 0.92);
    width: 170px;
    max-width: 170px;
  }

  .layer-btn:focus-visible {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .layer-icon {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    width: 38px;
    text-align: center;
    flex-shrink: 0;
  }

  .layer-full {
    font-size: 11px;
    font-weight: 600;
    padding-right: 12px;
    opacity: 0;
    transform: translateX(-4px);
    transition: opacity 0.18s ease, transform 0.22s ease;
    flex-shrink: 0;
  }

  .layer-btn:hover .layer-full {
    opacity: 1;
    transform: translateX(0);
  }

  .layer-hint {
    font-size: 10px;
    color: var(--text-muted-color, #888);
    padding: 4px 10px 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    margin-top: 2px;
  }

  /* Other popover */
  .other-popover {
    position: absolute;
    left: 48px;
    bottom: 0;
    min-width: 220px;
    max-height: 60vh;
    overflow-y: auto;
    background: rgba(10, 10, 14, 0.96);
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 8px 0;
    z-index: 20;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.6);
  }

  .other-popover-header {
    display: flex;
    justify-content: space-between;
    gap: 6px;
    padding: 4px 10px 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .other-popover-header button {
    flex: 1;
    background: transparent;
    color: var(--accent-color, #4a9eff);
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    padding: 3px 6px;
    font-size: 10px;
    cursor: pointer;
  }

  .other-popover-header button:hover {
    background: rgba(255, 255, 255, 0.06);
  }

  .other-group-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-muted-color, #888);
    padding: 6px 10px 2px;
    letter-spacing: 0.5px;
  }

  .other-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px;
    cursor: pointer;
    font-size: 11px;
    color: var(--text-color, #e8e8e8);
  }

  .other-item:hover {
    background: rgba(255, 255, 255, 0.06);
  }

  .other-item input[type="checkbox"] {
    width: 12px;
    height: 12px;
    cursor: pointer;
    accent-color: var(--accent-color, #4a9eff);
  }

  /* Hide layer toggles on mobile */
  @media (max-width: 768px) {
    .layer-toggles {
      display: none;
    }
  }
</style>

<svelte:window onclick={closeOtherPopover} />
<Tooltip
  bind:this={tooltipElement}
  bind:text={tooltipText}
  bind:show={tooltipShow}
  bind:tooltipPos={tooltipPos}
/>
<ContextMenu
  bind:this={mapContextMenuElement}
  menu={mapContextMenu} />
<div class="map-container">
  <canvas use:contextmenu={mapContextMenuObject} bind:this={canvasElement} onmousedown={onMouseDown} onmousemove={onMouseMove} onmouseup={onMouseUp} onmouseleave={onMouseUp} onwheel={onWheel}>
  </canvas>

  <!-- Layer toggles (bottom-left, desktop only) — hidden when fishing overlay is active -->
  {#if !hideLayerToggles && !fishingOverlay}
  <div class="layer-toggles">
    {#each MAIN_LAYERS as layer (layer.id)}
      <button
        class="layer-btn"
        class:active={activeMain.has(layer.id)}
        onclick={(e) => handleLayerClick(layer.id, e)}
        title={`${layer.full} — click to show only, shift+click to toggle`}
      >
        <span class="layer-icon" style="color: {layer.color}">{layer.id}</span>
        <span class="layer-full">{layer.full}</span>
      </button>
    {/each}
    <button
      class="layer-btn"
      class:active={activeOther.size > 0}
      onclick={handleOtherClick}
      title="Other layers — open picker"
    >
      <span class="layer-icon" style="color: #a78bfa">OTH</span>
      <span class="layer-full">Other…</span>
    </button>
    {#if otherPopoverOpen}
      <div
        class="other-popover"
        role="dialog"
        aria-label="Other layer filters"
        tabindex="-1"
        onclick={(e) => e.stopPropagation()}
        onkeydown={(e) => { if (e.key === 'Escape') closeOtherPopover(); }}
      >
        <div class="other-popover-header">
          <button onclick={selectAllOther}>Select all</button>
          <button onclick={selectNoneOther}>Select none</button>
        </div>
        {#each OTHER_GROUPS as group}
          <div class="other-group-label">{group.label}</div>
          {#each group.items as item}
            <label class="other-item">
              <input
                type="checkbox"
                checked={activeOther.has(item.type)}
                onchange={() => toggleOtherItem(item.type)}
              />
              {item.label}
            </label>
          {/each}
        {/each}
      </div>
    {/if}
    <div class="layer-hint">Shift+click for multi</div>
  </div>
  {/if}
</div>

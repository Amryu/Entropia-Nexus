<!--
  @component FishSectorGrid
  Canvas-based sector grid for marking fish locations on planet maps.
  Each server tile (8x8km) is subdivided into a 4x4 sub-grid (2x2km cells).
  Features: map background, pan/zoom, Calypso deadzones.
-->
<script>
  // @ts-nocheck
  import { untrack } from 'svelte';

  const SUB_DIVISIONS = 4;
  const CELL_SIZE = 20;
  const LABEL_MARGIN = 32;
  const MIN_ZOOM = 0.15;
  const MAX_ZOOM = 8;
  const DRAG_THRESHOLD = 4;

  const RARITIES = ['Common', 'Uncommon', 'Rare', 'Very Rare', 'Extremely Rare'];
  const RARITY_COLORS = {
    'Common':         'rgba(34, 197, 94, 0.55)',
    'Uncommon':       'rgba(59, 130, 246, 0.55)',
    'Rare':           'rgba(234, 179, 8, 0.6)',
    'Very Rare':      'rgba(239, 68, 68, 0.6)',
    'Extremely Rare': 'rgba(168, 85, 247, 0.65)'
  };
  const RARITY_BORDER = {
    'Common':         '#22c55e',
    'Uncommon':       '#3b82f6',
    'Rare':           '#eab308',
    'Very Rare':      '#ef4444',
    'Extremely Rare': '#a855f7'
  };

  // Calypso deadzones in tile coordinates (0-indexed)
  const CALYPSO_DEADZONES = [
    { rowMin: 5, rowMax: 8, colMin: 0, colMax: 3 },
    { rowMin: 6, rowMax: 8, colMin: 4, colMax: 4 },
    { rowMin: 0, rowMax: 3, colMin: 3, colMax: 8 },
    { rowMin: 4, rowMax: 4, colMin: 5, colMax: 8 },
  ];

  let {
    locations = [],
    planets = [],
    isEditMode = false,
    planetsList = null,
    onchange
  } = $props();

  let activeTabIndex = $state(0);
  let selectedCol = $state(null);
  let selectedRow = $state(null);
  let canvasEl = $state(null);
  let containerEl = $state(null);
  let mapImage = $state(null);
  let canvasWidth = $state(600);
  let canvasHeight = $state(420);
  let zoom = $state(1);
  let panX = $state(0);
  let panY = $state(0);
  let hoveredCol = $state(null);
  let hoveredRow = $state(null);
  let mouseX = $state(0);
  let mouseY = $state(0);

  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragStartPanX = 0;
  let dragStartPanY = 0;
  let hasDragged = false;
  let drawQueued = false;
  let globalMoveHandler = null;
  let globalUpHandler = null;
  let resizeObserver = null;

  function colLabel(c) {
    if (c < 26) return String.fromCharCode(65 + c);
    return String.fromCharCode(65 + Math.floor(c / 26) - 1) + String.fromCharCode(65 + (c % 26));
  }
  function rowLabel(r) { return String(r + 1); }
  function sectorNotation(c, r) { return colLabel(c) + rowLabel(r); }

  let relevantPlanets = $derived.by(() => {
    const names = (planets || []).map(p => p?.Name).filter(Boolean);
    return names.map(name => {
      const loc = (locations || []).find(l => l.PlanetName === name);
      const full = (planetsList || []).find(p => p?.Name === name);
      const fromPlanets = (planets || []).find(p => p?.Name === name);
      const w = loc?.Width ?? full?.Properties?.Map?.Width ?? fromPlanets?.Width ?? 1;
      const h = loc?.Height ?? full?.Properties?.Map?.Height ?? fromPlanets?.Height ?? 1;
      return {
        name,
        width: w * SUB_DIVISIONS,
        height: h * SUB_DIVISIONS,
        tileWidth: w,
        tileHeight: h,
        sectors: loc?.Sectors || []
      };
    });
  });

  let activePlanet = $derived(relevantPlanets[Math.min(activeTabIndex, relevantPlanets.length - 1)] ?? null);
  let activePlanetName = $derived(activePlanet?.name);

  function findSector(sectors, col, row) {
    return sectors?.find(s => s.Col === col && s.Row === row) ?? null;
  }

  let selectedSector = $derived.by(() => {
    if (selectedCol == null || selectedRow == null || !activePlanet) return null;
    return findSector(activePlanet.sectors, selectedCol, selectedRow);
  });

  function isDeadzone(planetName, col, row) {
    if (planetName !== 'Calypso') return false;
    const tc = Math.floor(col / SUB_DIVISIONS);
    const tr = Math.floor(row / SUB_DIVISIONS);
    return CALYPSO_DEADZONES.some(dz =>
      tr >= dz.rowMin && tr <= dz.rowMax && tc >= dz.colMin && tc <= dz.colMax
    );
  }

  function getMapImageUrl(name) {
    return `/${name.replace(/[^0-9a-zA-Z]/g, '').toLowerCase()}.jpg`;
  }

  function canvasToWorld(cx, cy) {
    return { x: (cx - panX) / zoom, y: (cy - panY) / zoom };
  }

  function cellAtCanvas(cx, cy) {
    if (!activePlanet) return null;
    const w = canvasToWorld(cx, cy);
    const gx = w.x - LABEL_MARGIN;
    const gy = w.y - LABEL_MARGIN;
    if (gx < 0 || gy < 0) return null;
    const col = Math.floor(gx / CELL_SIZE);
    const vr = Math.floor(gy / CELL_SIZE);
    if (col < 0 || col >= activePlanet.width || vr < 0 || vr >= activePlanet.height) return null;
    return { col, row: activePlanet.height - 1 - vr };
  }

  let hoverInfo = $derived.by(() => {
    if (hoveredCol == null || hoveredRow == null || !activePlanet) return null;
    const tc = Math.floor(hoveredCol / SUB_DIVISIONS);
    const tr = Math.floor(hoveredRow / SUB_DIVISIONS);
    const tileName = rowLabel(tr) + colLabel(tc);
    const isDz = isDeadzone(activePlanet.name, hoveredCol, hoveredRow);
    if (isDz) return `${tileName} (inaccessible)`;
    const sector = findSector(activePlanet.sectors, hoveredCol, hoveredRow);
    if (sector) return `${tileName} - ${sector.Rarity}${sector.Note ? ' - ' + sector.Note : ''}`;
    return tileName;
  });

  // --- Drawing ---

  function requestDraw() {
    if (drawQueued) return;
    drawQueued = true;
    requestAnimationFrame(() => { drawQueued = false; draw(); });
  }

  function draw() {
    if (!canvasEl || !activePlanet) return;
    const ctx = canvasEl.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    ctx.fillStyle = '#12121f';
    ctx.fillRect(0, 0, canvasWidth, canvasHeight);

    ctx.save();
    ctx.translate(panX, panY);
    ctx.scale(zoom, zoom);

    const gx = LABEL_MARGIN;
    const gy = LABEL_MARGIN;
    const gridW = activePlanet.width * CELL_SIZE;
    const gridH = activePlanet.height * CELL_SIZE;

    // Grid area background
    ctx.fillStyle = '#0d0d1a';
    ctx.fillRect(gx, gy, gridW, gridH);

    // Map image
    if (mapImage) {
      ctx.globalAlpha = 0.6;
      ctx.drawImage(mapImage, gx, gy, gridW, gridH);
      ctx.globalAlpha = 1;
    }

    // Deadzone overlay
    if (activePlanet.name === 'Calypso') {
      for (const dz of CALYPSO_DEADZONES) {
        const x1 = gx + dz.colMin * SUB_DIVISIONS * CELL_SIZE;
        const vrMax = activePlanet.tileHeight - 1 - dz.rowMax;
        const y1 = gy + vrMax * SUB_DIVISIONS * CELL_SIZE;
        const w = (dz.colMax - dz.colMin + 1) * SUB_DIVISIONS * CELL_SIZE;
        const h = (dz.rowMax - dz.rowMin + 1) * SUB_DIVISIONS * CELL_SIZE;
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(x1, y1, w, h);

        ctx.save();
        ctx.beginPath();
        ctx.rect(x1, y1, w, h);
        ctx.clip();
        ctx.strokeStyle = 'rgba(255, 50, 50, 0.12)';
        ctx.lineWidth = 1;
        const stride = 12;
        for (let d = 0; d < w + h; d += stride) {
          ctx.beginPath();
          ctx.moveTo(x1 + d, y1);
          ctx.lineTo(x1 + d - h, y1 + h);
          ctx.stroke();
        }
        ctx.restore();
      }
    }

    // Sector fills
    const sectorSet = new Set();
    for (const s of activePlanet.sectors) {
      sectorSet.add(`${s.Col},${s.Row}`);
      const sx = gx + s.Col * CELL_SIZE;
      const sy = gy + (activePlanet.height - 1 - s.Row) * CELL_SIZE;
      ctx.fillStyle = RARITY_COLORS[s.Rarity] || RARITY_COLORS['Common'];
      ctx.fillRect(sx, sy, CELL_SIZE, CELL_SIZE);
    }

    // Sector borders - only draw edges not shared with same-rarity neighbor
    ctx.lineWidth = 1.2;
    for (const s of activePlanet.sectors) {
      const sx = gx + s.Col * CELL_SIZE;
      const sy = gy + (activePlanet.height - 1 - s.Row) * CELL_SIZE;
      const color = RARITY_BORDER[s.Rarity] || '#fff';
      ctx.strokeStyle = color;

      const neighbors = [
        { dc: 0, dr: 1, edge: () => { ctx.moveTo(sx, sy); ctx.lineTo(sx + CELL_SIZE, sy); } },
        { dc: 0, dr: -1, edge: () => { ctx.moveTo(sx, sy + CELL_SIZE); ctx.lineTo(sx + CELL_SIZE, sy + CELL_SIZE); } },
        { dc: -1, dr: 0, edge: () => { ctx.moveTo(sx, sy); ctx.lineTo(sx, sy + CELL_SIZE); } },
        { dc: 1, dr: 0, edge: () => { ctx.moveTo(sx + CELL_SIZE, sy); ctx.lineTo(sx + CELL_SIZE, sy + CELL_SIZE); } },
      ];

      for (const n of neighbors) {
        const nc = s.Col + n.dc;
        const nr = s.Row + n.dr;
        const adj = activePlanet.sectors.find(o => o.Col === nc && o.Row === nr);
        if (adj && adj.Rarity === s.Rarity) continue;
        ctx.beginPath();
        n.edge();
        ctx.stroke();
      }
    }

    // Minor grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 0.5;
    for (let c = 0; c <= activePlanet.width; c++) {
      if (c % SUB_DIVISIONS === 0) continue;
      ctx.beginPath();
      ctx.moveTo(gx + c * CELL_SIZE, gy);
      ctx.lineTo(gx + c * CELL_SIZE, gy + gridH);
      ctx.stroke();
    }
    for (let r = 0; r <= activePlanet.height; r++) {
      if (r % SUB_DIVISIONS === 0) continue;
      ctx.beginPath();
      ctx.moveTo(gx, gy + r * CELL_SIZE);
      ctx.lineTo(gx + gridW, gy + r * CELL_SIZE);
      ctx.stroke();
    }

    // Major grid lines (tile boundaries)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.lineWidth = 1.5;
    for (let c = 0; c <= activePlanet.width; c += SUB_DIVISIONS) {
      ctx.beginPath();
      ctx.moveTo(gx + c * CELL_SIZE, gy);
      ctx.lineTo(gx + c * CELL_SIZE, gy + gridH);
      ctx.stroke();
    }
    for (let r = 0; r <= activePlanet.height; r += SUB_DIVISIONS) {
      ctx.beginPath();
      ctx.moveTo(gx, gy + r * CELL_SIZE);
      ctx.lineTo(gx + gridW, gy + r * CELL_SIZE);
      ctx.stroke();
    }

    // Hover highlight
    if (hoveredCol != null && hoveredRow != null) {
      const hx = gx + hoveredCol * CELL_SIZE;
      const hy = gy + (activePlanet.height - 1 - hoveredRow) * CELL_SIZE;
      const isDz = isDeadzone(activePlanet.name, hoveredCol, hoveredRow);
      ctx.fillStyle = isDz ? 'rgba(255, 0, 0, 0.15)' : 'rgba(255, 255, 255, 0.2)';
      ctx.fillRect(hx, hy, CELL_SIZE, CELL_SIZE);
      if (!isDz) {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
        ctx.lineWidth = 1;
        ctx.strokeRect(hx + 0.5, hy + 0.5, CELL_SIZE - 1, CELL_SIZE - 1);
      }
    }

    // Selection highlight
    if (selectedCol != null && selectedRow != null) {
      const sx = gx + selectedCol * CELL_SIZE;
      const sy = gy + (activePlanet.height - 1 - selectedRow) * CELL_SIZE;
      ctx.strokeStyle = '#4a9eff';
      ctx.lineWidth = 2.5;
      ctx.strokeRect(sx + 1, sy + 1, CELL_SIZE - 2, CELL_SIZE - 2);
    }

    // Labels at tile boundaries
    const fontSize = Math.min(18, Math.max(8, 11 / zoom));
    ctx.font = `600 ${fontSize}px system-ui, sans-serif`;
    ctx.fillStyle = 'rgba(200, 200, 200, 0.85)';

    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    for (let tc = 0; tc < activePlanet.tileWidth; tc++) {
      const x = gx + tc * SUB_DIVISIONS * CELL_SIZE + (SUB_DIVISIONS * CELL_SIZE) / 2;
      ctx.fillText(colLabel(tc), x, gy - 3 / zoom);
    }

    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let tr = 0; tr < activePlanet.tileHeight; tr++) {
      const vtRow = activePlanet.tileHeight - 1 - tr;
      const y = gy + vtRow * SUB_DIVISIONS * CELL_SIZE + (SUB_DIVISIONS * CELL_SIZE) / 2;
      ctx.fillText(rowLabel(tr), gx - 4 / zoom, y);
    }

    ctx.restore();
  }

  // --- Interaction ---

  function handleMouseDown(e) {
    if (e.button !== 0) return;
    isDragging = true;
    hasDragged = false;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragStartPanX = panX;
    dragStartPanY = panY;
    if (canvasEl) canvasEl.style.cursor = 'grabbing';

    globalMoveHandler = handleGlobalMouseMove;
    globalUpHandler = handleGlobalMouseUp;
    window.addEventListener('mousemove', globalMoveHandler);
    window.addEventListener('mouseup', globalUpHandler);
  }

  function handleGlobalMouseMove(e) {
    if (!isDragging) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    if (Math.abs(dx) + Math.abs(dy) > DRAG_THRESHOLD) hasDragged = true;
    panX = dragStartPanX + dx;
    panY = dragStartPanY + dy;
    requestDraw();
  }

  function handleGlobalMouseUp(e) {
    window.removeEventListener('mousemove', globalMoveHandler);
    window.removeEventListener('mouseup', globalUpHandler);
    globalMoveHandler = null;
    globalUpHandler = null;

    const wasDragging = isDragging;
    isDragging = false;
    updateCursor(e);

    if (wasDragging && !hasDragged && canvasEl) {
      const rect = canvasEl.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      const cell = cellAtCanvas(cx, cy);
      if (cell) handleCellClick(cell.col, cell.row);
    }
  }

  function handleCanvasMouseMove(e) {
    const rect = canvasEl?.getBoundingClientRect();
    if (!rect) return;
    mouseX = e.clientX - rect.left;
    mouseY = e.clientY - rect.top;
    if (isDragging) return;
    const cell = cellAtCanvas(mouseX, mouseY);
    const newCol = cell?.col ?? null;
    const newRow = cell?.row ?? null;
    if (newCol !== hoveredCol || newRow !== hoveredRow) {
      hoveredCol = newCol;
      hoveredRow = newRow;
      updateCursor(e);
      requestDraw();
    }
  }

  function updateCursor(e) {
    if (!canvasEl) return;
    if (isDragging) { canvasEl.style.cursor = 'grabbing'; return; }
    if (hoveredCol == null) { canvasEl.style.cursor = 'grab'; return; }
    if (isEditMode && isDeadzone(activePlanet?.name, hoveredCol, hoveredRow)) {
      canvasEl.style.cursor = 'not-allowed';
    } else if (isEditMode) {
      canvasEl.style.cursor = 'pointer';
    } else {
      canvasEl.style.cursor = 'grab';
    }
  }

  function handleContextMenu(e) {
    e.preventDefault();
    if (!isEditMode || !activePlanet) return;
    const rect = canvasEl?.getBoundingClientRect();
    if (!rect) return;
    const cell = cellAtCanvas(e.clientX - rect.left, e.clientY - rect.top);
    if (!cell) return;
    const existing = findSector(activePlanet.sectors, cell.col, cell.row);
    if (existing) {
      const newSectors = activePlanet.sectors.filter(s => !(s.Col === cell.col && s.Row === cell.row));
      if (selectedCol === cell.col && selectedRow === cell.row) {
        selectedCol = null;
        selectedRow = null;
      }
      emitChange(activePlanet.name, newSectors);
    }
  }

  function handleMouseLeave() {
    if (isDragging) return;
    hoveredCol = null;
    hoveredRow = null;
    if (canvasEl) canvasEl.style.cursor = 'grab';
    requestDraw();
  }

  function handleWheel(e) {
    e.preventDefault();
    const rect = canvasEl.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const wb = canvasToWorld(cx, cy);
    const factor = e.deltaY > 0 ? 0.88 : 1.14;
    zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom * factor));
    panX = cx - wb.x * zoom;
    panY = cy - wb.y * zoom;
    requestDraw();
  }

  // Touch: pinch-to-zoom + single-finger pan
  let touchStartDist = 0;
  let touchStartZoom = 1;

  function handleTouchStart(e) {
    e.preventDefault();
    if (e.touches.length === 1) {
      isDragging = true;
      hasDragged = false;
      dragStartX = e.touches[0].clientX;
      dragStartY = e.touches[0].clientY;
      dragStartPanX = panX;
      dragStartPanY = panY;
    } else if (e.touches.length === 2) {
      isDragging = false;
      const dx = e.touches[1].clientX - e.touches[0].clientX;
      const dy = e.touches[1].clientY - e.touches[0].clientY;
      touchStartDist = Math.hypot(dx, dy);
      touchStartZoom = zoom;
      dragStartPanX = panX;
      dragStartPanY = panY;
      dragStartX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
      dragStartY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
    }
  }

  function handleTouchMove(e) {
    e.preventDefault();
    if (e.touches.length === 1 && isDragging) {
      const dx = e.touches[0].clientX - dragStartX;
      const dy = e.touches[0].clientY - dragStartY;
      if (Math.abs(dx) + Math.abs(dy) > DRAG_THRESHOLD) hasDragged = true;
      panX = dragStartPanX + dx;
      panY = dragStartPanY + dy;
      requestDraw();
    } else if (e.touches.length === 2) {
      hasDragged = true;
      const dx = e.touches[1].clientX - e.touches[0].clientX;
      const dy = e.touches[1].clientY - e.touches[0].clientY;
      const dist = Math.hypot(dx, dy);
      const rect = canvasEl.getBoundingClientRect();
      const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left;
      const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top;
      const wb = { x: (midX - dragStartPanX) / touchStartZoom, y: (midY - dragStartPanY) / touchStartZoom };
      zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, touchStartZoom * (dist / touchStartDist)));
      panX = midX - wb.x * zoom;
      panY = midY - wb.y * zoom;
      requestDraw();
    }
  }

  function handleTouchEnd(e) {
    if (e.touches.length === 0) {
      if (!hasDragged && e.changedTouches.length > 0) {
        const rect = canvasEl.getBoundingClientRect();
        const cx = e.changedTouches[0].clientX - rect.left;
        const cy = e.changedTouches[0].clientY - rect.top;
        const cell = cellAtCanvas(cx, cy);
        if (cell) handleCellClick(cell.col, cell.row);
      }
      isDragging = false;
    }
  }

  // --- View management ---

  function updateCanvasSize() {
    if (!canvasEl) return;
    const dpr = window.devicePixelRatio || 1;
    canvasEl.width = canvasWidth * dpr;
    canvasEl.height = canvasHeight * dpr;
  }

  function fitToView() {
    if (!activePlanet || canvasWidth <= 0 || canvasHeight <= 0) return;
    const totalW = LABEL_MARGIN + activePlanet.width * CELL_SIZE + 8;
    const totalH = LABEL_MARGIN + activePlanet.height * CELL_SIZE + 8;
    const scaleX = canvasWidth / totalW;
    const scaleY = canvasHeight / totalH;
    zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.min(scaleX, scaleY) * 0.95));
    panX = (canvasWidth - totalW * zoom) / 2;
    panY = (canvasHeight - totalH * zoom) / 2;
  }

  // --- Actions (lifecycle binding) ---

  function setupCanvas(el) {
    canvasEl = el;
    el.addEventListener('wheel', handleWheel, { passive: false });
    el.addEventListener('touchstart', handleTouchStart, { passive: false });
    el.addEventListener('touchmove', handleTouchMove, { passive: false });
    el.addEventListener('touchend', handleTouchEnd, { passive: false });

    updateCanvasSize();
    fitToView();
    requestDraw();

    return {
      destroy() {
        canvasEl = null;
        el.removeEventListener('wheel', handleWheel);
        el.removeEventListener('touchstart', handleTouchStart);
        el.removeEventListener('touchmove', handleTouchMove);
        el.removeEventListener('touchend', handleTouchEnd);
        if (globalMoveHandler) {
          window.removeEventListener('mousemove', globalMoveHandler);
          window.removeEventListener('mouseup', globalUpHandler);
        }
      }
    };
  }

  function setupContainer(el) {
    containerEl = el;
    let initialFitDone = false;
    resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        if (width <= 0) continue;
        canvasWidth = Math.floor(width);
        canvasHeight = Math.floor(Math.min(Math.max(width * 0.75, 300), 600));
        updateCanvasSize();
        if (!initialFitDone) { fitToView(); initialFitDone = true; }
        requestDraw();
      }
    });
    resizeObserver.observe(el);
    return {
      destroy() {
        containerEl = null;
        resizeObserver?.disconnect();
      }
    };
  }

  // --- Effects ---

  $effect(() => {
    const name = activePlanetName;
    if (!name) { mapImage = null; return; }
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => { if (activePlanetName === name) { mapImage = img; requestDraw(); } };
    img.onerror = () => { if (activePlanetName === name) { mapImage = null; requestDraw(); } };
    img.src = getMapImageUrl(name);
    untrack(() => { fitToView(); updateCanvasSize(); requestDraw(); });
  });

  $effect(() => {
    activePlanet;
    selectedCol;
    selectedRow;
    mapImage;
    requestDraw();
  });

  // --- Data mutation ---

  function emitChange(planetName, newSectors) {
    let newLocations = (locations || []).map(l =>
      l.PlanetName === planetName ? { ...l, Sectors: newSectors } : { ...l }
    );
    if (!newLocations.find(l => l.PlanetName === planetName)) {
      const planet = relevantPlanets.find(p => p.name === planetName);
      newLocations.push({
        PlanetName: planetName,
        Width: planet?.tileWidth ?? 1,
        Height: planet?.tileHeight ?? 1,
        Sectors: newSectors
      });
    }
    newLocations = newLocations.filter(l => l.Sectors.length > 0);
    onchange?.(newLocations);
  }

  function handleCellClick(col, row) {
    if (!isEditMode || !activePlanet) return;
    if (isDeadzone(activePlanet.name, col, row)) return;

    const existing = findSector(activePlanet.sectors, col, row);
    if (existing) {
      if (selectedCol === col && selectedRow === row) {
        const newSectors = activePlanet.sectors.filter(s => !(s.Col === col && s.Row === row));
        selectedCol = null;
        selectedRow = null;
        emitChange(activePlanet.name, newSectors);
      } else {
        selectedCol = col;
        selectedRow = row;
      }
    } else {
      const newSectors = [...activePlanet.sectors, { Col: col, Row: row, Rarity: 'Common', Note: null }];
      selectedCol = col;
      selectedRow = row;
      emitChange(activePlanet.name, newSectors);
    }
  }

  function updateSelectedRarity(rarity) {
    if (!activePlanet || selectedCol == null) return;
    const newSectors = activePlanet.sectors.map(s =>
      (s.Col === selectedCol && s.Row === selectedRow) ? { ...s, Rarity: rarity } : s
    );
    emitChange(activePlanet.name, newSectors);
  }

  function updateSelectedNote(note) {
    if (!activePlanet || selectedCol == null) return;
    const newSectors = activePlanet.sectors.map(s =>
      (s.Col === selectedCol && s.Row === selectedRow) ? { ...s, Note: note || null } : s
    );
    emitChange(activePlanet.name, newSectors);
  }

  function removeSelected() {
    if (!activePlanet || selectedCol == null) return;
    const newSectors = activePlanet.sectors.filter(s => !(s.Col === selectedCol && s.Row === selectedRow));
    selectedCol = null;
    selectedRow = null;
    emitChange(activePlanet.name, newSectors);
  }

  function zoomIn() {
    const cx = canvasWidth / 2;
    const cy = canvasHeight / 2;
    const wb = canvasToWorld(cx, cy);
    zoom = Math.min(MAX_ZOOM, zoom * 1.4);
    panX = cx - wb.x * zoom;
    panY = cy - wb.y * zoom;
    requestDraw();
  }

  function zoomOut() {
    const cx = canvasWidth / 2;
    const cy = canvasHeight / 2;
    const wb = canvasToWorld(cx, cy);
    zoom = Math.max(MIN_ZOOM, zoom / 1.4);
    panX = cx - wb.x * zoom;
    panY = cy - wb.y * zoom;
    requestDraw();
  }

  function resetView() {
    fitToView();
    requestDraw();
  }
</script>

{#if relevantPlanets.length === 0}
  <p class="muted">Add planets to this fish to set sector locations.</p>
{:else}
  {#if relevantPlanets.length > 1}
    <div class="planet-tabs">
      {#each relevantPlanets as planet, i}
        <button
          class="planet-tab"
          class:active={activeTabIndex === i}
          onclick={() => { activeTabIndex = i; selectedCol = null; selectedRow = null; }}
        >
          {planet.name}
          {#if planet.sectors.length > 0}
            <span class="sector-count">{planet.sectors.length}</span>
          {/if}
        </button>
      {/each}
    </div>
  {:else}
    <div class="planet-single">{relevantPlanets[0].name}</div>
  {/if}

  {#if activePlanet}
    <div class="canvas-wrapper" use:setupContainer>
      <canvas
        use:setupCanvas
        class="sector-canvas"
        style="width: {canvasWidth}px; height: {canvasHeight}px;"
        onmousedown={handleMouseDown}
        onmousemove={handleCanvasMouseMove}
        onmouseleave={handleMouseLeave}
        oncontextmenu={handleContextMenu}
      ></canvas>

      <div class="canvas-controls">
        <button class="ctrl-btn" onclick={zoomIn} title="Zoom in">+</button>
        <button class="ctrl-btn" onclick={zoomOut} title="Zoom out">&minus;</button>
        <button class="ctrl-btn reset-btn" onclick={resetView} title="Reset view">Fit</button>
      </div>

      {#if hoverInfo}
        <div class="hover-info" style="left: {mouseX + 12}px; top: {mouseY - 28}px;">{hoverInfo}</div>
      {/if}
    </div>

    <div class="legend">
      {#each RARITIES as r}
        <div class="legend-item">
          <span class="legend-swatch" style="background-color: {RARITY_COLORS[r]}; border-color: {RARITY_BORDER[r]};"></span>
          <span>{r}</span>
        </div>
      {/each}
      {#if activePlanet.name === 'Calypso'}
        <div class="legend-item">
          <span class="legend-swatch deadzone-swatch"></span>
          <span>Inaccessible</span>
        </div>
      {/if}
    </div>

    {#if isEditMode && selectedSector}
      <div class="sector-detail">
        <div class="detail-header">
          <strong>{sectorNotation(selectedCol, selectedRow)}</strong>
          <button type="button" class="remove-btn" onclick={removeSelected}>Remove</button>
        </div>
        <div class="detail-row">
          <label>Rarity</label>
          <select value={selectedSector.Rarity} onchange={(e) => updateSelectedRarity(e.currentTarget.value)}>
            {#each RARITIES as r}
              <option value={r}>{r}</option>
            {/each}
          </select>
        </div>
        <div class="detail-row">
          <label>Note</label>
          <input type="text" value={selectedSector.Note || ''} placeholder="Optional note..."
            onchange={(e) => updateSelectedNote(e.currentTarget.value)} />
        </div>
      </div>
    {/if}
  {/if}
{/if}

<style>
  .muted {
    color: var(--text-muted, #999);
    font-style: italic;
    margin: 0;
  }

  .planet-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }

  .planet-tab {
    padding: 6px 14px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    color: var(--text-color);
    transition: all 0.15s;
  }

  .planet-tab.active {
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-color: var(--accent-color, #4a9eff);
  }

  .planet-tab:hover:not(.active) {
    background-color: var(--hover-color);
  }

  .sector-count {
    font-size: 11px;
    margin-left: 4px;
    opacity: 0.7;
  }

  .planet-single {
    font-weight: 600;
    font-size: 13px;
    margin-bottom: 8px;
    color: var(--text-muted, #999);
  }

  .canvas-wrapper {
    position: relative;
    margin-bottom: 10px;
    border-radius: 6px;
    overflow: hidden;
    border: 1px solid var(--border-color, #555);
  }

  .sector-canvas {
    display: block;
    cursor: grab;
    touch-action: none;
  }

  .canvas-controls {
    position: absolute;
    top: 8px;
    right: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .ctrl-btn {
    width: 30px;
    height: 30px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    background: rgba(0, 0, 0, 0.5);
    color: rgba(255, 255, 255, 0.8);
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(4px);
  }

  .ctrl-btn:hover {
    background: rgba(0, 0, 0, 0.7);
    color: white;
  }

  .reset-btn {
    font-size: 10px;
    font-weight: 600;
  }

  .hover-info {
    position: absolute;
    padding: 4px 10px;
    background: rgba(0, 0, 0, 0.75);
    color: rgba(255, 255, 255, 0.9);
    font-size: 12px;
    border-radius: 4px;
    pointer-events: none;
    backdrop-filter: blur(4px);
    white-space: nowrap;
    z-index: 10;
  }

  .legend {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 10px;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: var(--text-muted, #999);
  }

  .legend-swatch {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid;
  }

  .deadzone-swatch {
    background: repeating-linear-gradient(
      -45deg,
      rgba(0, 0, 0, 0.5),
      rgba(0, 0, 0, 0.5) 2px,
      rgba(255, 50, 50, 0.15) 2px,
      rgba(255, 50, 50, 0.15) 4px
    );
    border-color: rgba(255, 50, 50, 0.3);
  }

  .sector-detail {
    background-color: var(--secondary-color, var(--bg-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: 360px;
  }

  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 14px;
  }

  .detail-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .detail-row label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted, #999);
    min-width: 50px;
  }

  .detail-row select,
  .detail-row input {
    flex: 1;
    padding: 4px 8px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    font-size: 13px;
  }

  .detail-row select:focus,
  .detail-row input:focus {
    border-color: var(--accent-color, #4a9eff);
    outline: none;
  }

  .remove-btn {
    padding: 3px 10px;
    font-size: 11px;
    background: transparent;
    color: var(--error-color, #ef4444);
    border: 1px solid var(--error-color, #ef4444);
    border-radius: 4px;
    cursor: pointer;
  }

  .remove-btn:hover {
    background-color: rgba(239, 68, 68, 0.15);
  }
</style>

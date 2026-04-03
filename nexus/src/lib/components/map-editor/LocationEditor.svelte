<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { addToast } from '$lib/stores/toasts.js';
  import { apiCall } from '$lib/util.js';
  import { LOCATION_TYPES, AREA_TYPES, SHAPES, isArea, getEffectiveType, DEFAULT_ALTITUDE } from './mapEditorUtils.js';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';
  import JsonTreeNode from '$lib/components/JsonTreeNode.svelte';

  /** @type {typeof import('$lib/components/wiki/RichTextEditor.svelte').default|null} */
  let RichTextEditor = $state(null);
  onMount(async () => {
    const [mod, reData] = await Promise.all([
      import('$lib/components/wiki/RichTextEditor.svelte'),
      apiCall(fetch, '/recurringevents')
    ]);
    RichTextEditor = mod.default;
    if (reData) recurringEvents = reData;
  });

  
  
  
  
  /**
   * @typedef {Object} Props
   * @property {any} [location] - The selected location object (or null)
   * @property {boolean} [isNew] - Whether this is a newly drawn shape
   * @property {boolean} [readOnly] - If true, all fields are disabled (inspect only)
   * @property {any} [drawnShapeData] - { shape, data, center } from drawing
   * @property {'admin' | 'public'} [mode]
   * @property {boolean} [isAdmin]
   * @property {any} [lockedBy] - If this location is locked by another user's pending change, this is the change object
   * @property {any} [allLocations] - All locations on current planet (for parent picker)
   * @property {boolean} [isDbChange] - Whether this pending add has a corresponding DB change (submitted, not local-only)
   */

  /** @type {Props} */
  let {
    location = null,
    isNew = false,
    readOnly = false,
    drawnShapeData = null,
    mode = 'admin',
    isAdmin = false,
    lockedBy = null,
    allLocations = [],
    isDbChange = false,
    pendingMobData = null,
    pendingWaveData = null,
    onedit,
    ondelete,
    onremovePendingAdd,
    ondeleteDbChange,
    onrevert,
    oneditMobArea,
    oneditWaveArea,
    onpreview
  } = $props();

  // Edit form state
  let name = $state('');
  let locationType = $state('Area');
  let longitude = $state(0);
  let latitude = $state(0);
  let altitude = $state(DEFAULT_ALTITUDE);
  let areaType = $state('MobArea');
  let shape = $state('Polygon');
  let shapeDataJson = $state('');

  // Structured shape fields (Circle / Rectangle)
  let circleX = $state(0);
  let circleY = $state(0);
  let circleRadius = $state(100);
  let rectX = $state(0);
  let rectY = $state(0);
  let rectWidth = $state(100);
  let rectHeight = $state(100);

  // Description (rich text)
  let description = $state('');

  // Parent location state
  let parentLocationName = $state('');

  // MobArea state
  let isEvent = $state(false);
  let isShared = $state(false);
  let recurringEventId = $state(null);
  let recurringEvents = $state([]);

  // LandArea state
  let landAreaOwner = $state('');
  let taxRateHunting = $state(null);
  let taxRateMining = $state(null);
  let taxRateShops = $state(null);

  // Shape data cache — preserves shape data when swapping types (imperative, not reactive)
  let _shapeCache = { Circle: null, Rectangle: null, Polygon: null };

  // Related entities
  let relatedExpanded = $state(false);
  let relatedMissions = $state(null);
  let relatedLoading = $state(false);

  /**
   * Parse a pasted waypoint string.
   * Supports: [Planet, x, y, z, Name] or simple x, y, z
   */
  function parseWaypoint(str) {
    // Full waypoint: [Planet, x, y, z, Name]
    const fullMatch = str.match(/\[([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,\]]+)(?:,\s*([^\]]*))?\]/);
    if (fullMatch) {
      return {
        x: parseFloat(fullMatch[2]) || 0,
        y: parseFloat(fullMatch[3]) || 0,
        z: parseFloat(fullMatch[4]) || 0,
        name: fullMatch[5]?.trim() || null
      };
    }
    // Simple: x, y, z (with or without brackets)
    const simpleMatch = str.match(/^\[?\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]?$/);
    if (simpleMatch) {
      return {
        x: parseFloat(simpleMatch[1]) || 0,
        y: parseFloat(simpleMatch[2]) || 0,
        z: parseFloat(simpleMatch[3]) || 0,
        name: null
      };
    }
    return null;
  }

  function handleCoordPaste(event) {
    const text = event.clipboardData?.getData('text') || '';
    const parsed = parseWaypoint(text);
    if (!parsed) return;
    event.preventDefault();
    longitude = parsed.x;
    latitude = parsed.y;
    altitude = parsed.z;
    if (parsed.name && !name) {
      name = parsed.name;
    }
    scheduleAutoSave();
  }

  // Track which location is loaded to avoid resetting form when same location re-renders
  // These are imperative guards/caches — not reactive (no $state) to avoid cross-effect cascading
  let loadedLocationId = null;
  let loadedDrawnShapeRef = null;
  let _lastShapeDataRef = null;
  let _lastCoordsRef = null;
  let _populatingForm = false;






  // Track previous shape for swap caching (imperative, not reactive)
  let _prevShape = null;

  function handleShapeSwap(oldShape, newShape) {
    // Save current shape data to cache
    if (oldShape === 'Circle') {
      _shapeCache.Circle = { x: circleX, y: circleY, radius: circleRadius };
    } else if (oldShape === 'Rectangle') {
      _shapeCache.Rectangle = { x: rectX, y: rectY, width: rectWidth, height: rectHeight };
    } else if (oldShape === 'Polygon') {
      _shapeCache.Polygon = shapeDataJson;
    }

    // Restore from cache or set defaults
    const cached = _shapeCache[newShape];
    if (newShape === 'Circle') {
      if (cached) {
        circleX = cached.x; circleY = cached.y; circleRadius = cached.radius;
      } else {
        // Default: use current coordinates as center
        circleX = Number(longitude) || 0;
        circleY = Number(latitude) || 0;
        circleRadius = 100;
      }
    } else if (newShape === 'Rectangle') {
      if (cached) {
        rectX = cached.x; rectY = cached.y; rectWidth = cached.width; rectHeight = cached.height;
      } else {
        rectX = Number(longitude) || 0;
        rectY = Number(latitude) || 0;
        rectWidth = 100; rectHeight = 100;
      }
    } else if (newShape === 'Polygon') {
      if (cached) {
        shapeDataJson = cached;
      } else if (oldShape === 'Rectangle') {
        // Convert rectangle to 4-vertex polygon
        const x = Number(rectX) || 0, y = Number(rectY) || 0;
        const w = Number(rectWidth) || 100, h = Number(rectHeight) || 100;
        const verts = [x, y, x + w, y, x + w, y + h, x, y + h, x, y];
        shapeDataJson = JSON.stringify({ vertices: verts }, null, 2);
      } else if (oldShape === 'Circle') {
        // Convert circle to hexagon
        const cx = Number(circleX) || 0, cy = Number(circleY) || 0;
        const r = Number(circleRadius) || 100;
        const verts = [];
        for (let i = 0; i < 6; i++) {
          const angle = (Math.PI / 3) * i - Math.PI / 2; // start at top
          verts.push(Math.round(cx + r * Math.cos(angle)), Math.round(cy + r * Math.sin(angle)));
        }
        // Close the ring
        verts.push(verts[0], verts[1]);
        shapeDataJson = JSON.stringify({ vertices: verts }, null, 2);
      } else {
        shapeDataJson = '';
      }
    }
    scheduleAutoSave();
  }

  // Build shape data object from current form state
  function buildShapeData(shapeType) {
    if (shapeType === 'Circle') {
      return { x: Number(circleX), y: Number(circleY), radius: Number(circleRadius) };
    } else if (shapeType === 'Rectangle') {
      return { x: Number(rectX), y: Number(rectY), width: Number(rectWidth), height: Number(rectHeight) };
    } else if (shapeType === 'Polygon') {
      try {
        if (shapeDataJson.trim()) return JSON.parse(shapeDataJson);
      } catch { return null; }
    }
    return null;
  }

  // Dispatch preview events when form fields change (debounced)
  let previewTimeout;

  // Auto-save: dispatch edit when form fields change via user interaction
  let autoSaveTimer;

  function scheduleAutoSave() {
    if (readOnly || isLocked || _populatingForm) return;
    clearTimeout(autoSaveTimer);
    autoSaveTimer = setTimeout(dispatchAutoSave, 300);
  }

  function dispatchAutoSave() {
    if (readOnly || isLocked || !location) return;

    const modified = {
      name,
      locationType,
      longitude: Number(longitude),
      latitude: Number(latitude),
      altitude: altitude != null && altitude !== '' ? Number(altitude) : null,
      areaType: locationType === 'Area' ? areaType : null,
      shape: locationType === 'Area' ? shape : null,
      shapeData: locationType === 'Area' ? buildShapeData(shape) : null,
      parentLocationName: parentLocationName || null,
      description: description || null,
      isEvent: isMobArea ? isEvent : null,
      isShared: isMobArea ? isShared : null,
      recurringEventId: isMobArea ? recurringEventId : null,
      landAreaOwner: (isLandArea && landAreaOwner) ? landAreaOwner : null,
      taxRateHunting: isLandArea ? taxRateHunting : null,
      taxRateMining: isLandArea ? taxRateMining : null,
      taxRateShops: isLandArea ? taxRateShops : null
    };

    onedit?.({ original: location, modified });
  }

  function handleDelete() {
    if (!location) return;
    if (mode === 'public' && !isAdmin) {
      // Non-admin public mode: copy location details for admin review
      const type = getEffectiveType(location);
      const coords = location.Properties?.Coordinates;
      const coordStr = coords ? `${coords.Longitude ?? 0}, ${coords.Latitude ?? 0}, ${coords.Altitude ?? 0}` : 'N/A';
      const text = `Location: ${location.Name} (ID: ${location.Id}), Type: ${type}, Coords: ${coordStr}`;
      navigator.clipboard?.writeText(text);
      addToast('Delete info copied to clipboard', { type: 'success' });
    } else if (mode === 'public' && isAdmin) {
      // Admin in public mode: copy SQL DELETE query (cascading FKs handle related rows)
      const id = location.Id;
      const sql = `-- Delete: ${location.Name} (${getEffectiveType(location)})\nDELETE FROM "Locations" WHERE "Id" = ${Number(id)};`;
      navigator.clipboard?.writeText(sql);
      addToast('SQL DELETE query copied to clipboard', { type: 'success' });
    } else {
      ondelete?.(location);
    }
  }

  function handleRemovePendingAdd() {
    if (!location) return;
    if (isDbChange) {
      ondeleteDbChange?.(location.Id);
    } else {
      onremovePendingAdd?.(location.Id);
    }
  }

  function handleRevert() {
    onrevert?.(location);
  }

  function handleEditMobArea() {
    oneditMobArea?.({ location, isNew });
  }

  function handleEditWaveArea() {
    oneditWaveArea?.({ location, isNew });
  }

  function handleDescriptionChange(data) {
    description = data;
    scheduleAutoSave();
  }


  async function fetchRelatedEntities() {
    if (!location?.Id || location._isPendingAdd || relatedLoading) return;
    relatedLoading = true;
    try {
      const missions = await apiCall(fetch, `/missions?StartLocationId=${location.Id}`);
      relatedMissions = missions || [];
    } catch (e) {
      relatedMissions = [];
    } finally {
      relatedLoading = false;
    }
  }

  function toggleRelated() {
    relatedExpanded = !relatedExpanded;
    if (relatedExpanded && relatedMissions === null) {
      fetchRelatedEntities();
    }
  }

  // Raw JSON dialog
  let showRawJson = $state(false);
  let jsonCollapsedPaths = $state(new Set());


  function collectArrayPaths(obj, path = '') {
    if (obj === null || typeof obj !== 'object') return [];
    const paths = [];
    if (Array.isArray(obj)) {
      if (path) paths.push(path);
      obj.forEach((item, i) => paths.push(...collectArrayPaths(item, `${path}[${i}]`)));
    } else {
      Object.entries(obj).forEach(([k, v]) => {
        const p = path ? `${path}.${k}` : k;
        paths.push(...collectArrayPaths(v, p));
      });
    }
    return paths;
  }

  function openRawJson() {
    const paths = new Set(collectArrayPaths(currentJson));
    // Expand Maturities array itself, but collapse heavy sub-objects within each entry
    if (currentJson?.Maturities) {
      paths.delete('Maturities');
      currentJson.Maturities.forEach((entry, i) => {
        const matPath = `Maturities[${i}].Maturity`;
        for (const key of ['Properties', 'Attacks', 'Mob', 'Links']) {
          if (entry?.Maturity?.[key] != null) paths.add(`${matPath}.${key}`);
        }
      });
    }
    jsonCollapsedPaths = paths;
    showRawJson = true;
  }

  function closeRawJson() { showRawJson = false; }

  function toggleJsonCollapse(path) {
    if (jsonCollapsedPaths.has(path)) {
      jsonCollapsedPaths.delete(path);
    } else {
      jsonCollapsedPaths.add(path);
    }
    jsonCollapsedPaths = new Set(jsonCollapsedPaths);
  }
  let isLocked = $derived(!!lockedBy && !isAdmin);
  // Parent location options for SearchInput (areas only)
  let parentOptions = $derived(allLocations
    .filter(l => isArea(l) && l.Id !== location?.Id)
    .map(l => ({ label: l.Name, value: String(l.Id), sublabel: getEffectiveType(l) })));
  // Populate form from location or drawn data — only when the actual location changes
  $effect(() => {
    if (location && !isNew && location.Id !== loadedLocationId) {
      _populatingForm = true;
      clearTimeout(autoSaveTimer);
      loadedLocationId = location.Id;
      loadedDrawnShapeRef = null;
      name = location.Name || '';
      locationType = location.Properties?.Type === 'Area' || isArea(location) ? 'Area' : (location.Properties?.Type || 'Area');
      longitude = location.Properties?.Coordinates?.Longitude ?? 0;
      latitude = location.Properties?.Coordinates?.Latitude ?? 0;
      altitude = location.Properties?.Coordinates?.Altitude ?? DEFAULT_ALTITUDE;
      areaType = location.Properties?.AreaType || (location.Properties?.Type !== 'Area' ? location.Properties?.Type : null) || 'MobArea';
      shape = location.Properties?.Shape || 'Polygon';
      const existingData = location.Properties?.Data;
      if (shape === 'Circle' && existingData) {
        circleX = existingData.x ?? 0;
        circleY = existingData.y ?? 0;
        circleRadius = existingData.radius ?? 100;
        shapeDataJson = '';
      } else if (shape === 'Rectangle' && existingData) {
        rectX = existingData.x ?? 0;
        rectY = existingData.y ?? 0;
        rectWidth = existingData.width ?? 100;
        rectHeight = existingData.height ?? 100;
        shapeDataJson = '';
      } else {
        shapeDataJson = existingData ? JSON.stringify(existingData, null, 2) : '';
      }
      parentLocationName = location.ParentLocation?.Name || '';
      description = location.Properties?.Description || '';
      isEvent = location.Properties?.IsEvent ?? false;
      recurringEventId = location.Properties?.RecurringEventId ?? null;
      isShared = location.Properties?.IsShared ?? false;
      landAreaOwner = location.Owner?.Name || location.Properties?.LandAreaOwnerName || '';
      taxRateHunting = location.Properties?.TaxRateHunting ?? null;
      taxRateMining = location.Properties?.TaxRateMining ?? null;
      taxRateShops = location.Properties?.TaxRateShops ?? null;
      _lastShapeDataRef = location.Properties?.Data;
      _lastCoordsRef = location.Properties?.Coordinates;
      _prevShape = shape;
      _shapeCache = { Circle: null, Rectangle: null, Polygon: null };
      // Reset related data when location changes
      relatedMissions = null;
      relatedExpanded = false;
      // Allow DOM to settle before re-enabling auto-save (prevents spurious change events)
      setTimeout(() => { _populatingForm = false; }, 0);
    }
  });
  // Clear tracking when deselected (guard to avoid redundant writes)
  $effect(() => {
    if (!location && !isNew) {
      loadedLocationId = null;
      loadedDrawnShapeRef = null;
      _lastShapeDataRef = null;
      _lastCoordsRef = null;
    }
  });
  $effect(() => {
    if (isNew && drawnShapeData && drawnShapeData !== loadedDrawnShapeRef) {
      _populatingForm = true;
      clearTimeout(autoSaveTimer);
      loadedDrawnShapeRef = drawnShapeData;
      loadedLocationId = null;
      name = '';
      description = '';
      locationType = drawnShapeData.isMarker ? 'Teleporter' : 'Area';
      longitude = drawnShapeData.center?.x ?? 0;
      latitude = drawnShapeData.center?.y ?? 0;
      altitude = DEFAULT_ALTITUDE;
      areaType = 'MobArea';
      shape = drawnShapeData.shape || 'Polygon';
      const drawnData = drawnShapeData.data;
      if (shape === 'Circle' && drawnData) {
        circleX = drawnData.x ?? 0;
        circleY = drawnData.y ?? 0;
        circleRadius = drawnData.radius ?? 100;
        shapeDataJson = '';
      } else if (shape === 'Rectangle' && drawnData) {
        rectX = drawnData.x ?? 0;
        rectY = drawnData.y ?? 0;
        rectWidth = drawnData.width ?? 100;
        rectHeight = drawnData.height ?? 100;
        shapeDataJson = '';
      } else {
        shapeDataJson = drawnData ? JSON.stringify(drawnData, null, 2) : '';
      }
      _prevShape = shape;
      _shapeCache = { Circle: null, Rectangle: null, Polygon: null };
      setTimeout(() => { _populatingForm = false; }, 0);
    }
  });
  // Update shape fields when shape data changes externally (e.g., map drag/resize)
  // Uses JSON comparison because selectedLocation is a $derived that always creates new objects
  $effect(() => {
    if (location && location.Id === loadedLocationId && !isNew) {
      const newData = location.Properties?.Data;
      const newCoords = location.Properties?.Coordinates;
      const newDataJson = newData ? JSON.stringify(newData) : null;
      const lastDataJson = _lastShapeDataRef ? JSON.stringify(_lastShapeDataRef) : null;
      if (newDataJson !== lastDataJson) {
        _lastShapeDataRef = newData;
        if (newData) {
          const currentShape = location.Properties?.Shape || shape;
          if (currentShape === 'Circle') {
            circleX = newData.x ?? 0;
            circleY = newData.y ?? 0;
            circleRadius = newData.radius ?? 100;
          } else if (currentShape === 'Rectangle') {
            rectX = newData.x ?? 0;
            rectY = newData.y ?? 0;
            rectWidth = newData.width ?? 100;
            rectHeight = newData.height ?? 100;
          } else {
            shapeDataJson = JSON.stringify(newData, null, 2);
          }
        }
      }
      const newCoordsJson = newCoords ? `${newCoords.Longitude},${newCoords.Latitude}` : null;
      const lastCoordsJson = _lastCoordsRef ? `${_lastCoordsRef.Longitude},${_lastCoordsRef.Latitude}` : null;
      if (newCoordsJson !== lastCoordsJson) {
        _lastCoordsRef = newCoords;
        if (newCoords) {
          longitude = newCoords.Longitude ?? longitude;
          latitude = newCoords.Latitude ?? latitude;
        }
      }
      // Sync name when it changes externally (e.g., MobAreaEditor auto-generated name)
      if (isMobArea) {
        const newName = location.Name || '';
        if (newName !== name) {
          name = newName;
        }
      }
    }
  });
  $effect(() => {
    // Track all shape-related fields for reactivity
    const _shape = shape;
    const _shapeDataJson = shapeDataJson;
    const _cX = circleX; const _cY = circleY; const _cR = circleRadius;
    const _rX = rectX; const _rY = rectY; const _rW = rectWidth; const _rH = rectHeight;
    const _lon = longitude;
    const _lat = latitude;
    const _locType = locationType;
    const _active = location || isNew;

    // Skip preview during programmatic form population
    if (_populatingForm) return;

    clearTimeout(previewTimeout);
    previewTimeout = setTimeout(() => {
      if (!_active) {
        onpreview?.(null);
        return;
      }

      if (_locType === 'Area' && _shape) {
        let shapeData = null;
        if (_shape === 'Circle') {
          shapeData = { x: Number(_cX), y: Number(_cY), radius: Number(_cR) };
        } else if (_shape === 'Rectangle') {
          shapeData = { x: Number(_rX), y: Number(_rY), width: Number(_rW), height: Number(_rH) };
        } else if (_shape === 'Polygon') {
          try {
            if (_shapeDataJson.trim()) shapeData = JSON.parse(_shapeDataJson);
          } catch { return; } // invalid JSON — skip preview update
        }
        if (shapeData) {
          onpreview?.({ shape: _shape, data: shapeData, center: null });
        } else {
          onpreview?.(null);
        }
      } else if (_locType !== 'Area') {
        onpreview?.({ shape: null, data: null, center: { x: Number(_lon), y: Number(_lat) } });
      } else {
        onpreview?.(null);
      }
    }, 150);
  });
  let isAreaType = $derived(locationType === 'Area');
  let isMobArea = $derived(isAreaType && areaType === 'MobArea');
  let isLandArea = $derived(isAreaType && areaType === 'LandArea');
  let isWaveEvent = $derived(isAreaType && areaType === 'WaveEventArea');
  // Always reflects current form state — used by the JSON dialog
  let currentJson = $derived((location || isNew) ? (() => {
    const effectiveAreaType = locationType === 'Area' ? areaType : null;
    return {
      ...(location?.Id != null ? { Id: location.Id } : {}),
      Name: name,
      Properties: {
        Type: locationType,
        ...(effectiveAreaType ? { AreaType: effectiveAreaType } : {}),
        Description: description || null,
        Coordinates: {
          Longitude: Number(longitude),
          Latitude: Number(latitude),
          Altitude: altitude != null && altitude !== '' ? Number(altitude) : null
        },
        ...(locationType === 'Area' ? { Shape: shape, Data: buildShapeData(shape) } : {}),
        ...(location?.Properties?.TechnicalId ? { TechnicalId: location.Properties.TechnicalId } : {}),
        ...(isLandArea ? { TaxRateHunting: taxRateHunting, TaxRateMining: taxRateMining, TaxRateShops: taxRateShops } : {}),
        ...(isMobArea ? { IsEvent: isEvent, IsShared: isShared, RecurringEventId: recurringEventId } : {}),
        ...(pendingMobData ? { Density: pendingMobData.density } : {})
      },
      ...(location?.Planet ? { Planet: location.Planet } : {}),
      ParentLocation: parentLocationName ? { Name: parentLocationName } : null,
      Facilities: location?.Facilities ?? [],
      ...(pendingWaveData?.waves ? { Waves: pendingWaveData.waves } : location?.Waves ? { Waves: location.Waves } : {}),
      ...(pendingMobData ? { Maturities: pendingMobData.maturities } : location?.Maturities ? { Maturities: location.Maturities } : {})
    };
  })() : null);
</script>

<style>
  .editor-container {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    height: 100%;
    overflow-y: auto;
  }

  .editor-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
    margin: 0;
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .field-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .field-input {
    padding: 6px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 13px;
    width: 100%;
    box-sizing: border-box;
  }

  .field-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  select.field-input {
    cursor: pointer;
  }

  textarea.field-input {
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 11px;
    resize: vertical;
    min-height: 60px;
  }

  .coord-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 4px;
  }

  .field-hint {
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
    font-size: 11px;
    margin-left: 6px;
    color: var(--accent-color);
    opacity: 0.65;
  }

  .lock-notice {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 10px 12px;
    margin-top: 4px;
    background: rgba(168, 85, 247, 0.1);
    border: 1px solid rgba(168, 85, 247, 0.3);
    border-radius: 4px;
    font-size: 12px;
    color: var(--text-color);
  }
  .lock-icon { font-size: 16px; flex-shrink: 0; }
  .lock-title { font-weight: 600; margin-bottom: 2px; }
  .lock-detail { color: var(--text-muted); font-size: 11px; }

  .actions {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .btn {
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    text-align: center;
    background: var(--secondary-color);
    color: var(--text-color);
  }
  .btn:hover:not(:disabled) { background: var(--hover-color); }
  .btn:disabled { opacity: 0.5; cursor: default; }

  .btn-danger {
    border-color: #ef4444;
    color: #ef4444;
  }
  .btn-danger:hover { background: rgba(239, 68, 68, 0.15); }

  .btn-mob {
    border-color: #eab308;
    color: #eab308;
  }
  .btn-mob:hover { background: rgba(234, 179, 8, 0.15); }

  .toggle-row {
    display: flex;
    gap: 16px;
  }
  .toggle-label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: var(--text-color);
    cursor: pointer;
  }
  .toggle-label input[type="checkbox"] { cursor: pointer; }
  .event-select {
    padding: 2px 4px;
    font-size: 12px;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 3px;
  }

  .description-editor :global(.rich-text-editor) {
    font-size: 13px;
  }
  .description-editor :global(.editor-container) {
    min-height: 80px;
    max-height: 200px;
  }
  .description-editor :global(.tiptap-content) {
    min-height: 60px;
    font-size: 13px;
  }
  .description-preview {
    font-size: 13px;
    color: var(--text-color);
    line-height: 1.5;
    padding: 4px 0;
  }

  .section-divider {
    border-top: 1px solid var(--border-color);
    margin: 4px 0;
  }

  .no-selection {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    font-size: 13px;
    text-align: center;
    padding: 20px;
  }

  .related-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 6px 0;
    border: none;
    background: none;
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    cursor: pointer;
  }
  .related-toggle:hover { color: var(--text-color); }

  .related-toggle-arrow {
    font-size: 10px;
    transition: transform 0.15s ease;
  }

  .related-section {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .related-loading, .related-empty {
    font-size: 12px;
    color: var(--text-muted);
    padding: 4px 0;
  }

  .related-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .related-item {
    font-size: 12px;
    color: var(--accent-color);
    text-decoration: none;
    padding: 2px 0;
  }
  .related-item:hover { text-decoration: underline; }

  .title-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .title-row .editor-title { flex: 1; }
  .btn-json {
    background: none;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 11px;
    font-family: monospace;
    padding: 1px 5px;
    line-height: 1.4;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .btn-json:hover { border-color: var(--accent-color); color: var(--accent-color); }

  .json-dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .json-dialog {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 90%;
    max-width: 560px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    font-size: 12px;
  }
  .json-dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }
  .json-dialog-header h3 { margin: 0; font-size: 13px; font-weight: 600; color: var(--text-color); }
  .json-dialog-close {
    background: none;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 16px;
    width: 24px;
    height: 24px;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .json-dialog-close:hover { background: var(--hover-color); }
  .json-dialog-body {
    overflow: auto;
    padding: 12px 14px;
    font-family: 'Consolas', 'Menlo', monospace;
    font-size: 11px;
    line-height: 1.6;
    color: var(--text-color);
  }
</style>

{#if !location && !isNew}
  <div class="no-selection">
    Select a location on the map or in the list, or draw a new shape to edit.
  </div>
{:else}
  <div class="editor-container" oninput={scheduleAutoSave} onchange={scheduleAutoSave}>
    <div class="title-row">
      <h3 class="editor-title">{isNew ? 'New Location' : readOnly ? (location?.Name || '') : `Edit: ${location?.Name || ''}`}</h3>
      {#if location}
        <button class="btn-json" onclick={openRawJson} title="View raw JSON">&#123;&#125;</button>
      {/if}
    </div>

    {#if isLocked}
      <div class="lock-notice">
        <span class="lock-icon">&#x1F512;</span>
        <div>
          <div class="lock-title">Locked by another user</div>
          <div class="lock-detail">{lockedBy.author_name || lockedBy.author_eu_name || 'Another user'} has a pending {lockedBy.state?.toLowerCase() || ''} change for this location.</div>
        </div>
      </div>
    {/if}

    {#if !readOnly}
      <div class="actions">
        {#if !isNew && location?._isPendingAdd}
          <button class="btn btn-danger" onclick={handleRemovePendingAdd}>
            {isDbChange ? 'Delete submitted change' : 'Remove'}
          </button>
        {:else if !isNew}
          <button class="btn btn-danger" onclick={handleDelete} disabled={isLocked}
            title={mode === 'public' && isAdmin ? 'Copies SQL DELETE query to clipboard' : mode === 'public' ? 'Copies location details to your clipboard — send this to an admin if you believe this location should be deleted' : null}
          >
            {mode !== 'public' ? 'Mark for Deletion' : isAdmin ? 'Copy DELETE SQL' : 'Copy Delete Info'}
          </button>
          <button class="btn" onclick={handleRevert}>Revert Changes</button>
        {/if}
      </div>
    {/if}

    <div class="section-divider"></div>

    <div class="field-group">
      <span class="field-label">Name</span>
      <input class="field-input" type="text" bind:value={name} placeholder="Location name" disabled={readOnly || isMobArea} title={isMobArea ? 'Mob area names are auto-generated — edit via Mob Spawns' : ''} />
    </div>

    <div class="field-group">
      <span class="field-label">Type</span>
      <select class="field-input" bind:value={locationType} disabled={readOnly || (!isNew && isAreaType)}>
        {#each LOCATION_TYPES as t}
          <option value={t}>{t}</option>
        {/each}
        {#if isNew || isAreaType}
          <option value="Area">Area</option>
        {/if}
      </select>
    </div>

    <div class="field-group">
      <span class="field-label">Coordinates <span class="field-hint">paste waypoint</span></span>
      <div class="coord-row">
        <input class="field-input" type="number" bind:value={longitude} placeholder="Lon" title="Longitude" disabled={readOnly} onpaste={handleCoordPaste} />
        <input class="field-input" type="number" bind:value={latitude} placeholder="Lat" title="Latitude" disabled={readOnly} onpaste={handleCoordPaste} />
        <input class="field-input" type="number" bind:value={altitude} placeholder="Alt" title="Altitude" disabled={readOnly} onpaste={handleCoordPaste} />
      </div>
    </div>

    {#if isAreaType}
      <div class="section-divider"></div>

      <div class="field-group">
        <span class="field-label">Area Type</span>
        <select class="field-input" bind:value={areaType} disabled={readOnly}>
          {#each AREA_TYPES as t}
            <option value={t}>{t}</option>
          {/each}
        </select>
      </div>

      <div class="field-group">
        <span class="field-label">Shape</span>
        <select class="field-input" bind:value={shape} disabled={readOnly}
          onchange={(e) => {
            if (_prevShape && _prevShape !== shape) handleShapeSwap(_prevShape, shape);
            _prevShape = shape;
          }}>
          {#each SHAPES as s}
            <option value={s}>{s}</option>
          {/each}
        </select>
      </div>

      {#if shape === 'Circle'}
        <div class="field-group">
          <span class="field-label">Center</span>
          <div class="coord-row" style="grid-template-columns: 1fr 1fr;">
            <input class="field-input" type="number" bind:value={circleX} placeholder="X" title="Center X" disabled={readOnly} />
            <input class="field-input" type="number" bind:value={circleY} placeholder="Y" title="Center Y" disabled={readOnly} />
          </div>
        </div>
        <div class="field-group">
          <span class="field-label">Radius</span>
          <input class="field-input" type="number" bind:value={circleRadius} min="1" placeholder="Radius" title="Radius" disabled={readOnly} />
        </div>
      {:else if shape === 'Rectangle'}
        <div class="field-group">
          <span class="field-label">Origin</span>
          <div class="coord-row" style="grid-template-columns: 1fr 1fr;">
            <input class="field-input" type="number" bind:value={rectX} placeholder="X" title="Origin X" disabled={readOnly} />
            <input class="field-input" type="number" bind:value={rectY} placeholder="Y" title="Origin Y" disabled={readOnly} />
          </div>
        </div>
        <div class="field-group">
          <span class="field-label">Size</span>
          <div class="coord-row" style="grid-template-columns: 1fr 1fr;">
            <input class="field-input" type="number" bind:value={rectWidth} min="1" placeholder="Width" title="Width" disabled={readOnly} />
            <input class="field-input" type="number" bind:value={rectHeight} min="1" placeholder="Height" title="Height" disabled={readOnly} />
          </div>
        </div>
      {:else}
        <div class="field-group">
          <span class="field-label">Shape Data (JSON)</span>
          <textarea class="field-input" bind:value={shapeDataJson} rows="4" disabled={readOnly}></textarea>
        </div>
      {/if}

      {#if isMobArea}
        {#if !readOnly}
          <button class="btn btn-mob" onclick={handleEditMobArea}>
            Edit Mob Spawns
          </button>
        {/if}
        <div class="toggle-row">
          <label class="toggle-label">
            <select bind:value={recurringEventId} disabled={readOnly} onchange={() => { isEvent = recurringEventId != null; scheduleAutoSave(); }} class="event-select">
              <option value={null}>No Event</option>
              {#each recurringEvents as re}
                <option value={re.Id}>{re.Name}</option>
              {/each}
            </select>
          </label>
          <label class="toggle-label">
            <input type="checkbox" bind:checked={isShared} disabled={readOnly} onchange={scheduleAutoSave} />
            Shared
          </label>
        </div>
      {/if}

      {#if isWaveEvent}
        {#if !readOnly}
          <button class="btn btn-mob" onclick={handleEditWaveArea}>
            Edit Wave Spawns
          </button>
        {/if}
      {/if}

      {#if isLandArea}
        <div class="section-divider"></div>
        <div class="field-group">
          <span class="field-label">Land Area Owner</span>
          <input class="field-input" type="text" bind:value={landAreaOwner} placeholder="Player name (resolved on approval)" disabled={readOnly} />
        </div>
        <div class="field-group">
          <span class="field-label">Tax Rates (%)</span>
          <div class="coord-row">
            <input class="field-input" type="number" bind:value={taxRateHunting} min="0" max="5" step="0.1" placeholder="Hunt" title="Hunting Tax %" disabled={readOnly} />
            <input class="field-input" type="number" bind:value={taxRateMining} min="0" max="5" step="0.1" placeholder="Mine" title="Mining Tax %" disabled={readOnly} />
            <input class="field-input" type="number" bind:value={taxRateShops} min="0" max="5" step="0.1" placeholder="Shop" title="Shops Tax %" disabled={readOnly} />
          </div>
        </div>
      {/if}
    {/if}

    <div class="section-divider"></div>

    <!-- Parent Location -->
    <div class="field-group">
      <span class="field-label">Parent Location</span>
      {#if allLocations.length > 0}
        <SearchInput
          value={parentLocationName}
          options={parentOptions}
          placeholder="Search parent area..."
          limit={15}
          disabled={readOnly}
          onchange={(e) => { parentLocationName = e.value; scheduleAutoSave(); }}
          onselect={(e) => { parentLocationName = e.data?.label || e.value; scheduleAutoSave(); }}
        />
      {:else}
        <input class="field-input" type="text" bind:value={parentLocationName} placeholder="Parent area name" disabled={readOnly} />
      {/if}
    </div>

    <div class="section-divider"></div>

    <!-- Description (rich text) -->
    <div class="field-group">
      <span class="field-label">Description</span>
      {#if RichTextEditor && !readOnly && !isLocked}
        <div class="description-editor">
          <RichTextEditor
            content={description}
            placeholder="Describe this location..."
            showHeadings={false}
            showCodeBlock={false}
            showVideo={false}
            showImages={false}
            showWaypoints={true}
            onchange={handleDescriptionChange}
          />
        </div>
      {:else if description}
        <div class="description-preview description-content">{@html description}</div>
      {:else}
        <span class="field-hint" style="margin-left:0">No description</span>
      {/if}
    </div>

    <!-- Related Entities (read-only, collapsible) -->
    {#if !isNew && location?.Id}
      <div class="section-divider"></div>
      <button class="related-toggle" onclick={toggleRelated}>
        <span class="related-toggle-label">Related Entities</span>
        <span class="related-toggle-arrow" class:expanded={relatedExpanded}>{relatedExpanded ? '\u25B2' : '\u25BC'}</span>
      </button>
      {#if relatedExpanded}
        <div class="related-section">
          {#if relatedLoading}
            <div class="related-loading">Loading...</div>
          {:else if relatedMissions !== null}
            {#if relatedMissions.length > 0}
              <span class="field-label">Missions ({relatedMissions.length})</span>
              <div class="related-list">
                {#each relatedMissions as mission}
                  <a class="related-item" href="/information/missions/{mission.Id}" target="_blank" rel="noopener">
                    {mission.Name}
                  </a>
                {/each}
              </div>
            {:else}
              <div class="related-empty">No related entities found.</div>
            {/if}
          {/if}
        </div>
      {/if}
    {/if}
  </div>
{/if}

<svelte:window onkeydown={e => { if (e.key === 'Escape' && showRawJson) closeRawJson(); }} />

{#if showRawJson}
  <div class="json-dialog-overlay" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) closeRawJson(); }}>
    <div class="json-dialog">
      <div class="json-dialog-header">
        <h3>{location?.Name || 'Raw JSON'}</h3>
        <button class="json-dialog-close" onclick={closeRawJson}>×</button>
      </div>
      <div class="json-dialog-body">
        <JsonTreeNode
          data={currentJson}
          path=""
          collapsedPaths={jsonCollapsedPaths}
          toggleCollapse={toggleJsonCollapse}
        />
      </div>
    </div>
  </div>
{/if}

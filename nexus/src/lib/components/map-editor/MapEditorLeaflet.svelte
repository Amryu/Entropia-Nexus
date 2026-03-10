<script>
  // @ts-nocheck
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { buildCoordTransforms, getTypeColor, getEffectiveType, isArea, poleOfInaccessibility, getServerGridLines, snapAngleToDirection, getShapeVertices, getShapeEdges, computeVertexSnap, SERVER_TILE_SIZE, VERTEX_SNAP_THRESHOLD_PX, VERTEX_SNAP_THRESHOLD_MAX_EU, getGridSpacing } from './mapEditorUtils.js';
  import { formatMobSpawnDisplayName } from '$lib/mapUtil.js';
  import ContextMenu from '../ContextMenu.svelte';

  export let planet = null;
  export let locations = [];
  export let filteredLocationIds = null; // Set of IDs to show, or null for all
  export let selectedId = null;
  export let pendingChanges = new Map();
  export let editMode = false;
  export let previewShape = null;
  export let dbPendingChanges = [];
  export let currentUserId = null;
  export let isAdmin = false;

  const dispatch = createEventDispatcher();

  let mapContainer;
  let map;
  let imageOverlay;
  let layerGroup;
  let dbChangesLayerGroup;
  let drawControl;
  let transforms = null;
  let imgWidth = 0;
  let imgHeight = 0;
  let layerById = new Map();
  let L;

  // Snap state
  let snapEnabled = true;
  let snapToGrid = true;
  let snapGap = 20;
  let snapGuideLayerGroup;
  let gridOverlayGroup;
  let _cachedGridLines = null;
  let _activeVertexSnapData = null; // { vertices, gridLines, gap, threshold } for vertex editing
  let _editingLoc = null; // Location object being edited (for reactive snap refresh)

  // Preview and editing state
  let previewLayer = null;
  let drawnLayer = null; // Temporary layer for just-drawn shapes (removed on add/cancel)
  let editingLayer = null;
  let editableOverlay = null;
  let queuedPanTarget = null;
  let _clickedLayer = false;
  let _editingActive = false;
  let _editDebounceTimer = null;

  // Context menu state
  let contextMenuElement;
  let contextMenuVisible = false;
  let contextMenuPos = { x: 0, y: 0 };
  let contextMenuPayload = null;
  const contextMenuItems = [
    {
      label: 'Clone Shape',
      action: (payload) => {
        if (payload) dispatch('clone', payload);
      }
    },
    {
      label: 'Copy Waypoint',
      action: (payload) => {
        if (!payload) return;
        const coords = payload.Properties?.Coordinates;
        if (!coords) return;
        const wp = `/wp [${planet?.Name || ''}, ${coords.Longitude ?? 0}, ${coords.Latitude ?? 0}, ${coords.Altitude ?? 0}, ${payload.Name || ''}]`;
        navigator.clipboard?.writeText(wp);
      }
    }
  ];

  $: if (map && locations && pendingChanges !== undefined && !_editingActive) rebuildLayers();
  $: if (map && dbPendingChanges && transforms) rebuildDbChangesOverlay();
  $: if (map && filteredLocationIds !== undefined) updateVisibility();
  $: if (map && selectedId !== undefined) updateSelection();
  $: if (map && editMode !== undefined) toggleDrawControl();
  $: if (map && L && transforms) updatePreview(previewShape);

  // Refresh vertex snap data reactively when snap settings change during editing
  $: if (_editingActive && _editingLoc) {
    if (snapEnabled || snapToGrid) {
      _activeVertexSnapData = {
        vertices: snapEnabled ? getVertexSnapCandidates(_editingLoc) : [],
        edges: snapEnabled ? getEdgeSnapCandidates(_editingLoc) : [],
        gridLines: snapToGrid ? _cachedGridLines : null,
        gap: snapGap,
        threshold: getVertexSnapThreshold(),
      };
    } else {
      _activeVertexSnapData = null;
      clearSnapGuides();
    }
  }

  onMount(async () => {
    L = await import('leaflet');
    await import('leaflet-draw');

    // Patch leaflet-draw strict-mode bugs: undeclared variable assignments crash in ESM.
    // See: https://github.com/Leaflet/Leaflet.draw/issues/1026
    // CRS.Simple doesn't need real area formatting, so returning '' is safe.
    const safeReadableArea = function () { return ''; };
    if (L.GeometryUtil) L.GeometryUtil.readableArea = safeReadableArea;
    if (window.L?.GeometryUtil) window.L.GeometryUtil.readableArea = safeReadableArea;

    // Patch undeclared `radius` in L.Edit.Circle._resize (same class of bug).
    // Must patch on both the module L and window.L since leaflet-draw may use either.
    const fixedResize = function (latlng) {
      var moveLatLng = this._moveMarker.getLatLng();
      var radius = (L.GeometryUtil?.isVersion07x?.())
        ? moveLatLng.distanceTo(latlng)
        : this._map.distance(moveLatLng, latlng);
      this._shape.setRadius(radius);
      this._map.fire(L.Draw.Event.EDITRESIZE, { layer: this._shape });
    };
    if (L.Edit?.Circle?.prototype) L.Edit.Circle.prototype._resize = fixedResize;
    if (window.L?.Edit?.Circle?.prototype) window.L.Edit.Circle.prototype._resize = fixedResize;

    // Patch polygon vertex drag for angle snapping, vertex position snapping,
    // and visual class toggling on the dragged vertex handle.
    const patchVertexDrag = (lib) => {
      const proto = lib?.Edit?.PolyVerticesEdit?.prototype;
      if (!proto || proto._origOnMarkerDrag) return;

      // Highlight the dragged vertex handle
      proto._origOnMarkerDragStart = proto._onMarkerDragStart;
      proto._onMarkerDragStart = function(e) {
        const el = e.target?._icon;
        if (el) el.classList.add('vertex-dragging');
        this._origOnMarkerDragStart.call(this, e);
      };

      // Remove highlight on dragend (_fireEdit is the dragend handler)
      proto._origFireEdit = proto._fireEdit;
      proto._fireEdit = function() {
        if (this._markerGroup) {
          this._markerGroup.eachLayer(m => {
            m._icon?.classList.remove('vertex-dragging');
          });
        }
        this._origFireEdit.call(this);
      };

      proto._origOnMarkerDrag = proto._onMarkerDrag;
      proto._onMarkerDrag = function(e) {
        const marker = e.target;

        // Shift+drag: angle snap (16 directions / 22.5° steps)
        if (e.originalEvent?.shiftKey) {
          const idx = marker._index;
          if (idx !== undefined && this._poly) {
            const latlngs = this._poly.getLatLngs()[0];
            if (latlngs?.length > 1) {
              const prevIdx = (idx - 1 + latlngs.length) % latlngs.length;
              const prevLL = latlngs[prevIdx];
              const curLL = marker.getLatLng();
              const dx = curLL.lng - prevLL.lng;
              const dy = curLL.lat - prevLL.lat;
              const dist = Math.sqrt(dx * dx + dy * dy);
              const angle = Math.atan2(dy, dx);
              const snapped = snapAngleToDirection(angle);
              marker._latlng.lat = prevLL.lat + dist * Math.sin(snapped);
              marker._latlng.lng = prevLL.lng + dist * Math.cos(snapped);
            }
          }
        }

        // Vertex position snap: snap to candidate vertices and grid lines
        if (_activeVertexSnapData && transforms) {
          const curLL = marker.getLatLng();
          const ePos = transforms.leafletToEntropia(curLL.lat, curLL.lng);
          const snap = computeVertexSnap(
            ePos.x, ePos.y,
            _activeVertexSnapData.vertices,
            _activeVertexSnapData.gridLines,
            _activeVertexSnapData.gap,
            _activeVertexSnapData.threshold,
            _activeVertexSnapData.edges
          );
          const snappedX = ePos.x + snap.dx;
          const snappedY = ePos.y + snap.dy;
          if (snap.dx !== 0 || snap.dy !== 0) {
            const [newLat, newLng] = transforms.entropiaToLeaflet(snappedX, snappedY);
            marker._latlng.lat = newLat;
            marker._latlng.lng = newLng;
          }
          updateVertexSnapGuides(snappedX, snappedY, snap);
        }

        this._origOnMarkerDrag.call(this, e);
      };
    };
    patchVertexDrag(L);
    patchVertexDrag(window.L);

    // Import CSS
    const linkLeaflet = document.createElement('link');
    linkLeaflet.rel = 'stylesheet';
    linkLeaflet.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(linkLeaflet);

    const linkDraw = document.createElement('link');
    linkDraw.rel = 'stylesheet';
    linkDraw.href = 'https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css';
    document.head.appendChild(linkDraw);

    map = L.map(mapContainer, {
      crs: L.CRS.Simple,
      minZoom: -5,
      maxZoom: 10,
      zoomSnap: 0.25,
      zoomDelta: 0.5,
      attributionControl: false,
      markerZoomAnimation: false,
    });

    layerGroup = L.layerGroup().addTo(map);
    dbChangesLayerGroup = L.layerGroup().addTo(map);
    snapGuideLayerGroup = L.layerGroup().addTo(map);
    gridOverlayGroup = L.layerGroup().addTo(map);

    // Draw events — use string literal; L.Draw.Event.CREATED may be undefined with ESM imports
    map.on('draw:created', (e) => {
      const layer = e.layer;
      const shapeType = e.layerType;

      const entropiaData = leafletShapeToEntropia(layer, shapeType);
      if (entropiaData) {
        entropiaData.isMarker = (shapeType === 'marker');
      }

      // Keep the drawn layer on the map temporarily so the user can see it
      // while filling the form. Style it with the default type color (MobArea).
      if (drawnLayer) {
        map.removeLayer(drawnLayer);
      }
      const color = getTypeColor('MobArea');
      layer.options.interactive = false;
      if (layer.setStyle) {
        layer.setStyle({ color, fillColor: color, weight: 2, opacity: 0.9, fillOpacity: 0.3 });
      }
      layer.addTo(map);
      drawnLayer = layer;

      dispatch('drawCreated', entropiaData);
    });

    // Deselect on empty click
    map.on('click', () => {
      if (_clickedLayer) {
        _clickedLayer = false;
        return;
      }
      dispatch('select', null);
    });

    // Hide context menu on map click
    map.on('click', () => {
      contextMenuVisible = false;
    });

    if (planet) loadPlanetImage();
  });

  onDestroy(() => {
    if (_editDebounceTimer) clearTimeout(_editDebounceTimer);
    if (map) map.remove();
  });

  export function loadPlanetImage() {
    if (!planet || !map || !L) return;

    const planetSlug = planet.Name.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
    const imageUrl = `/${planetSlug}.jpg`;

    const img = new Image();
    img.onload = () => {
      imgWidth = img.naturalWidth;
      imgHeight = img.naturalHeight;

      transforms = buildCoordTransforms(planet, imgWidth, imgHeight);
      _cachedGridLines = getServerGridLines(planet);

      if (imageOverlay) map.removeLayer(imageOverlay);

      const bounds = [[0, 0], [imgHeight, imgWidth]];
      imageOverlay = L.imageOverlay(imageUrl, bounds).addTo(map);
      map.fitBounds(bounds);

      updateMaxBounds();
      map.on('zoomend', updateMaxBounds);
      map.on('zoomend', rebuildGridOverlay);
      map.on('moveend', rebuildGridOverlay);

      rebuildLayers();
      rebuildGridOverlay();

      if (queuedPanTarget) {
        const target = queuedPanTarget;
        queuedPanTarget = null;
        panToLocation(target);
      }
    };
    img.onerror = () => {
      console.error(`Failed to load planet image: ${imageUrl}`);
    };
    img.src = imageUrl;
  }

  function updateMaxBounds() {
    if (!map || !imgWidth || !imgHeight) return;
    // Pad by 50% of the current viewport size so the image edge can reach screen center
    const mapSize = map.getSize();
    const zoom = map.getZoom();
    const scale = map.options.crs.scale(zoom);
    const padLat = (mapSize.y / scale) * 0.5;
    const padLng = (mapSize.x / scale) * 0.5;
    map.setMaxBounds([[-padLat, -padLng], [imgHeight + padLat, imgWidth + padLng]]);
  }

  /**
   * Merge pending edit data into a location for visual display.
   * Returns the original loc if no pending edit exists.
   */
  function getEffectiveLocData(loc) {
    const pending = pendingChanges.get(loc.Id);
    if (!pending || pending.action !== 'edit' || !pending.modified) return loc;
    const mod = pending.modified;
    return {
      ...loc,
      Name: mod.name ?? loc.Name,
      Properties: {
        ...loc.Properties,
        Type: mod.locationType === 'Area' ? 'Area' : (mod.locationType ?? loc.Properties?.Type),
        AreaType: mod.areaType ?? loc.Properties?.AreaType,
        Shape: mod.shape ?? loc.Properties?.Shape,
        Data: mod.shapeData !== undefined ? mod.shapeData : loc.Properties?.Data,
        Coordinates: {
          ...loc.Properties?.Coordinates,
          ...(mod.longitude !== undefined ? { Longitude: mod.longitude } : {}),
          ...(mod.latitude !== undefined ? { Latitude: mod.latitude } : {}),
          ...(mod.altitude !== undefined ? { Altitude: mod.altitude } : {})
        }
      }
    };
  }

  function rebuildLayers() {
    if (!map || !transforms || !L) return;

    cleanupEditing();
    // Remove temporary drawn layer — pending add now renders via createPendingAddLayer
    if (drawnLayer) {
      map.removeLayer(drawnLayer);
      drawnLayer = null;
    }
    layerGroup.clearLayers();
    layerById.clear();

    // Sort: draw areas first (underneath), then points on top
    const sorted = [...locations].sort((a, b) => {
      const aIsArea = isArea(a);
      const bIsArea = isArea(b);
      if (aIsArea && !bIsArea) return -1;
      if (!aIsArea && bIsArea) return 1;
      return 0;
    });

    for (const loc of sorted) {
      const effectiveLoc = getEffectiveLocData(loc);
      const layer = createLocationLayer(effectiveLoc);
      if (layer) {
        layer._locId = loc.Id;
        layer.on('click', () => {
          _clickedLayer = true;
          dispatch('select', loc.Id);
        });
        // Right-click context menu
        layer.on('contextmenu', (e) => {
          if (!editMode) return;
          L.DomEvent.stop(e);
          contextMenuPos = { x: e.originalEvent.clientX, y: e.originalEvent.clientY };
          contextMenuPayload = effectiveLoc;
          contextMenuVisible = true;
        });
        layerGroup.addLayer(layer);
        layerById.set(loc.Id, layer);
      }
    }

    // Also add pending 'add' items as selectable layers
    for (const [tempId, change] of pendingChanges) {
      if (change.action !== 'add' || !change.modified) continue;
      const mod = change.modified;
      const layer = createPendingAddLayer(mod, tempId);
      if (layer) {
        layer._locId = tempId;
        layer.on('click', () => {
          _clickedLayer = true;
          dispatch('select', tempId);
        });
        layer.on('contextmenu', (e) => {
          if (!editMode) return;
          L.DomEvent.stop(e);
          contextMenuPos = { x: e.originalEvent.clientX, y: e.originalEvent.clientY };
          contextMenuPayload = { Id: tempId, Name: mod.name, Properties: { Coordinates: { Longitude: mod.longitude, Latitude: mod.latitude } } };
          contextMenuVisible = true;
        });
        layerGroup.addLayer(layer);
        layerById.set(tempId, layer);
      }
    }

    updateVisibility();
    updateSelection();
  }

  function createLocationLayer(loc) {
    if (!transforms || !L) return null;
    const effectiveType = getEffectiveType(loc);
    const color = getTypeColor(effectiveType);
    const changeState = getChangeState(loc.Id);

    if (isArea(loc)) {
      return createShapeLayer(loc, color, changeState);
    } else {
      return createPointLayer(loc, color, changeState);
    }
  }

  function createPointLayer(loc, color, changeState) {
    const coords = loc.Properties?.Coordinates;
    if (!coords?.Longitude && coords?.Longitude !== 0) return null;

    const [lat, lng] = transforms.entropiaToLeaflet(coords.Longitude, coords.Latitude);
    const style = getChangeStyle(changeState, color);

    const marker = L.circleMarker([lat, lng], {
      radius: 5,
      fillColor: style.fillColor,
      color: style.borderColor,
      weight: style.weight,
      opacity: 1,
      fillOpacity: style.fillOpacity,
      dashArray: style.dashArray
    });
    const tooltipName = loc.Properties?.Type === 'MobArea' ? formatMobSpawnDisplayName(loc.Name, loc.Maturities) : loc.Name;
    marker.bindTooltip(tooltipName, { direction: 'top', offset: [0, -8] });
    return marker;
  }

  /**
   * Create a Leaflet shape layer from Entropia shape data.
   * Shared by createShapeLayer, createPendingAddLayer, and rebuildDbChangesOverlay.
   */
  function createLeafletShape(shape, data, style) {
    if (!data || !transforms || !L) return null;
    if (shape === 'Circle' && data.x != null) {
      const [lat, lng] = transforms.entropiaToLeaflet(data.x, data.y);
      return L.circle([lat, lng], { ...style, radius: (data.radius || 0) / transforms.ratio });
    } else if (shape === 'Rectangle' && data.x != null) {
      const [lat1, lng1] = transforms.entropiaToLeaflet(data.x, data.y);
      const [lat2, lng2] = transforms.entropiaToLeaflet(data.x + (data.width || 0), data.y + (data.height || 0));
      return L.rectangle([[lat1, lng1], [lat2, lng2]], style);
    } else if (shape === 'Polygon' && data.vertices?.length >= 6) {
      const latLngs = [];
      for (let i = 0; i < data.vertices.length; i += 2) {
        const [lat, lng] = transforms.entropiaToLeaflet(data.vertices[i], data.vertices[i + 1]);
        latLngs.push([lat, lng]);
      }
      return L.polygon(latLngs, style);
    }
    return null;
  }

  function createShapeLayer(loc, color, changeState) {
    const shape = loc.Properties.Shape;
    const data = loc.Properties.Data;
    if (!data) return null;

    const style = getChangeStyle(changeState, color);
    const options = {
      color: style.borderColor,
      fillColor: style.fillColor,
      weight: style.weight,
      opacity: 0.8,
      fillOpacity: style.fillOpacity,
      dashArray: style.dashArray
    };

    const layer = createLeafletShape(shape, data, options);
    if (layer) {
      const tooltipName = loc.Properties?.Type === 'MobArea' ? formatMobSpawnDisplayName(loc.Name, loc.Maturities) : loc.Name;
      layer.bindTooltip(tooltipName, { sticky: true });
    }
    return layer;
  }

  function createPendingAddLayer(mod, tempId) {
    if (!transforms || !L) return null;
    const effectiveType = mod.locationType === 'Area'
      ? (mod.areaType || 'Area')
      : (mod.locationType || 'Location');
    const baseColor = getTypeColor(effectiveType);
    const style = getChangeStyle('add', baseColor);
    const addStyle = {
      fillColor: style.fillColor,
      color: style.borderColor,
      weight: style.weight,
      fillOpacity: style.fillOpacity,
      dashArray: style.dashArray,
      interactive: true
    };

    const isAreaAdd = mod.locationType === 'Area' && mod.shape && mod.shapeData;
    if (isAreaAdd) {
      const layer = createLeafletShape(mod.shape, mod.shapeData, addStyle);
      if (layer) layer.bindTooltip(mod.name || '(new)', { sticky: true });
      return layer;
    } else if (mod.longitude != null && mod.latitude != null) {
      const [lat, lng] = transforms.entropiaToLeaflet(mod.longitude, mod.latitude);
      const marker = L.circleMarker([lat, lng], {
        radius: 5,
        ...addStyle,
        fillOpacity: 0.7
      });
      marker.bindTooltip(mod.name || '(new)', { direction: 'top', offset: [0, -8] });
      return marker;
    }
    return null;
  }

  function getChangeState(locId) {
    for (const [, change] of pendingChanges) {
      if (change.original?.Id === locId) return change.action;
    }
    return null;
  }

  const CHANGE_EDGE_COLORS = {
    add: '#22c55e',
    edit: '#f59e0b',
    delete: '#ef4444'
  };

  function normalizeChangeState(changeTypeOrState) {
    if (changeTypeOrState === 'Create' || changeTypeOrState === 'add') return 'add';
    if (changeTypeOrState === 'Delete' || changeTypeOrState === 'delete') return 'delete';
    if (changeTypeOrState === 'Update' || changeTypeOrState === 'edit') return 'edit';
    return null;
  }

  function getChangeStyle(changeState, baseColor) {
    const base = {
      fillColor: baseColor,
      borderColor: baseColor,
      weight: 2,
      fillOpacity: 0.25,
      dashArray: null
    };

    if (changeState === 'delete') {
      return { ...base, borderColor: CHANGE_EDGE_COLORS.delete, fillColor: CHANGE_EDGE_COLORS.delete, fillOpacity: 0.15, dashArray: '8,4', weight: 3 };
    } else if (changeState === 'edit') {
      return { ...base, borderColor: CHANGE_EDGE_COLORS.edit, dashArray: '6,3', weight: 3 };
    } else if (changeState === 'add') {
      return { ...base, borderColor: CHANGE_EDGE_COLORS.add, dashArray: '6,3', weight: 3 };
    }
    return base;
  }

  // --- DB Pending Changes Overlay ---
  function getDbChangeStyle(changeTypeOrState, baseColor) {
    const state = normalizeChangeState(changeTypeOrState);
    const style = getChangeStyle(state, baseColor);
    return {
      color: style.borderColor,
      fillColor: style.fillColor,
      weight: style.weight,
      opacity: 0.8,
      fillOpacity: style.fillOpacity,
      dashArray: style.dashArray,
      interactive: true
    };
  }

  function getDbChangePointStyle(changeTypeOrState, baseColor) {
    const state = normalizeChangeState(changeTypeOrState);
    const style = getChangeStyle(state, baseColor);
    return {
      radius: 7,
      color: style.borderColor,
      fillColor: style.fillColor,
      weight: style.weight,
      opacity: 0.8,
      fillOpacity: state === 'delete' ? 0.25 : 0.35,
      dashArray: style.dashArray,
      interactive: true
    };
  }

  function rebuildDbChangesOverlay() {
    if (!dbChangesLayerGroup || !transforms || !L) return;
    dbChangesLayerGroup.clearLayers();

    for (const change of dbPendingChanges) {
      // Skip changes seeded into local pendingChanges (author/admin editable path)
      if (pendingChanges.has(-change.id)) continue;
      // Skip Update-type changes seeded as pending edits (key = entity Id)
      if (change.type === 'Update' && change.data?.Id && pendingChanges.has(change.data.Id)) continue;

      const data = change.data;
      if (!data?.Properties) continue;

      const props = data.Properties;
      const effectiveType = (props.Shape || props.Type === 'Area' || String(props.Type || '').endsWith('Area'))
        ? (props.AreaType || props.Type || 'Area')
        : (props.Type || 'Location');
      const baseColor = getTypeColor(effectiveType);
      const areaStyle = getDbChangeStyle(change.type, baseColor);
      const pointStyle = getDbChangePointStyle(change.type, baseColor);
      const authorLabel = change.author_name || change.author_eu_name || `User #${change.author_id}`;
      const stateLabel = change.state === 'Draft' ? 'Draft' : 'Pending';
      const typeLabel = change.type === 'Create' ? 'New' : (change.type === 'Delete' ? 'Delete' : 'Edit');
      const tooltip = `${typeLabel}: ${data.Name || '(unnamed)'}\nby ${authorLabel} (${stateLabel})`;

      const dbChangeId = `db-${change.id}`;

      // Areas with shape data
      if (props.Shape && props.Data) {
        const layer = createLeafletShape(props.Shape, props.Data, areaStyle);
        if (layer) {
          layer._dbChangeId = dbChangeId;
          layer._dbChangeData = change;
          layer.bindTooltip(tooltip, { sticky: true });
          layer.on('click', () => {
            _clickedLayer = true;
            dispatch('selectDbChange', change);
          });
          dbChangesLayerGroup.addLayer(layer);
        }
      }
      // Point locations (no shape)
      else if (props.Coordinates?.Longitude != null) {
        const [lat, lng] = transforms.entropiaToLeaflet(props.Coordinates.Longitude, props.Coordinates.Latitude);
        const marker = L.circleMarker([lat, lng], pointStyle);
        marker._dbChangeId = dbChangeId;
        marker._dbChangeData = change;
        marker.bindTooltip(tooltip, { direction: 'top', offset: [0, -8] });
        marker.on('click', () => {
          _clickedLayer = true;
          dispatch('selectDbChange', change);
        });
        dbChangesLayerGroup.addLayer(marker);
      }
    }
  }

  function updateVisibility() {
    if (!layerGroup) return;
    layerGroup.eachLayer(layer => {
      const locId = layer._locId;
      if (locId === undefined) return;
      // Keep pending items visible regardless of list/search filters.
      const isPending = pendingChanges.has(locId) || !!getChangeState(locId);
      const visible = isPending || !filteredLocationIds || filteredLocationIds.has(locId);
      if (visible && !map.hasLayer(layer)) map.addLayer(layer);
      else if (!visible && map.hasLayer(layer)) map.removeLayer(layer);
    });
  }

  function updateSelection() {
    cleanupEditing();

    layerGroup.eachLayer(layer => {
      const locId = layer._locId;
      if (locId === undefined) return;
      if (locId === selectedId) {
        if (layer.setStyle) layer.setStyle({ weight: 4, color: '#ffff00' });
        if (editMode && (isAdmin || pendingChanges.has(locId))) enableEditing(layer, locId);
      } else {
        // Check if this is a pending add (negative tempId)
        const pending = pendingChanges.get(locId);
        if (pending?.action === 'add') {
          // Restore pending add style
          const effectiveType = pending.modified?.locationType === 'Area'
            ? (pending.modified?.areaType || 'Area')
            : (pending.modified?.locationType || 'Location');
          const baseColor = getTypeColor(effectiveType);
          const style = getChangeStyle('add', baseColor);
          if (layer.setStyle) layer.setStyle({ weight: style.weight, color: style.borderColor, dashArray: style.dashArray });
        } else {
          const loc = locations.find(l => l.Id === locId);
          if (loc && layer.setStyle) {
            const effectiveType = getEffectiveType(loc);
            const color = getTypeColor(effectiveType);
            const changeState = getChangeState(locId);
            const style = getChangeStyle(changeState, color);
            layer.setStyle({ weight: style.weight, color: style.borderColor });
          }
        }
      }
    });

    // Highlight selected DB change overlay (no grabbers)
    if (dbChangesLayerGroup) {
      dbChangesLayerGroup.eachLayer(layer => {
        if (!layer._dbChangeId) return;
        if (layer._dbChangeId === selectedId) {
          if (layer.setStyle) layer.setStyle({ weight: 4, color: '#ffff00' });
        } else {
          // Restore original style
          const change = layer._dbChangeData;
          if (change && layer.setStyle) {
            const data = change.data;
            const props = data?.Properties || {};
            const effectiveType = (props.Shape || props.Type === 'Area' || String(props.Type || '').endsWith('Area'))
              ? (props.AreaType || props.Type || 'Area')
              : (props.Type || 'Location');
            const baseColor = getTypeColor(effectiveType);
            const state = normalizeChangeState(change.type);
            const style = getChangeStyle(state, baseColor);
            layer.setStyle({ weight: style.weight, color: style.borderColor, dashArray: style.dashArray });
          }
        }
      });
    }
  }

  // --- Snap helpers ---

  function getVertexSnapCandidates(loc) {
    const type = getEffectiveType(loc);
    const excludeId = loc.Id;

    // Build a set of own vertices (both original and edited) to exclude by value.
    // This prevents self-snapping even if the same shape appears through different paths.
    const ownVertexSet = new Set();
    const originalLoc = locations.find(l => l.Id === excludeId);
    if (originalLoc) {
      for (const v of getShapeVertices(originalLoc)) ownVertexSet.add(`${v.x},${v.y}`);
    }
    for (const v of getShapeVertices(loc)) ownVertexSet.add(`${v.x},${v.y}`);

    const allVertices = [];
    for (const other of locations) {
      if (other.Id === excludeId) continue;
      if (!isArea(other)) continue;
      if (getEffectiveType(other) !== type) continue;
      for (const v of getShapeVertices(getEffectiveLocData(other))) {
        if (!ownVertexSet.has(`${v.x},${v.y}`)) allVertices.push(v);
      }
    }
    for (const [tempId, change] of pendingChanges) {
      if (change.action !== 'add' || !change.modified) continue;
      if (tempId === excludeId) continue;
      const mod = change.modified;
      if (mod.locationType !== 'Area' || !mod.shape || !mod.shapeData) continue;
      if ((mod.areaType || 'Area') !== type) continue;
      const fakeLoc = { Properties: { Shape: mod.shape, Data: mod.shapeData } };
      for (const v of getShapeVertices(fakeLoc)) {
        if (!ownVertexSet.has(`${v.x},${v.y}`)) allVertices.push(v);
      }
    }
    return allVertices;
  }

  function getEdgeSnapCandidates(loc) {
    const type = getEffectiveType(loc);
    const excludeId = loc.Id;

    const allEdges = [];
    for (const other of locations) {
      if (other.Id === excludeId) continue;
      if (!isArea(other)) continue;
      if (getEffectiveType(other) !== type) continue;
      for (const e of getShapeEdges(getEffectiveLocData(other))) {
        allEdges.push(e);
      }
    }
    for (const [tempId, change] of pendingChanges) {
      if (change.action !== 'add' || !change.modified) continue;
      if (tempId === excludeId) continue;
      const mod = change.modified;
      if (mod.locationType !== 'Area' || !mod.shape || !mod.shapeData) continue;
      if ((mod.areaType || 'Area') !== type) continue;
      const fakeLoc = { Properties: { Shape: mod.shape, Data: mod.shapeData } };
      for (const e of getShapeEdges(fakeLoc)) {
        allEdges.push(e);
      }
    }
    return allEdges;
  }

  /** Tighter threshold for vertex editing — mouse follows precisely, no need for large floor. */
  function getVertexSnapThreshold() {
    if (!transforms || !map) return VERTEX_SNAP_THRESHOLD_MAX_EU;
    const pixelBased = VERTEX_SNAP_THRESHOLD_PX * transforms.ratio / map.options.crs.scale(map.getZoom());
    return Math.min(VERTEX_SNAP_THRESHOLD_MAX_EU, Math.max(15, pixelBased));
  }

  /**
   * Draw focused vertex snap guides: localized alignment lines + highlighted candidate vertices.
   * Includes connecting lines and distance labels showing per-axis distance.
   * Green highlighting when distance equals the configured gap.
   */
  function updateVertexSnapGuides(snappedX, snappedY, snap) {
    if (!snapGuideLayerGroup || !transforms || !L) return;
    snapGuideLayerGroup.clearLayers();
    if (snap.guideX == null && snap.guideY == null && !snap.bisector && !snap.edge) return;

    const gap = snap.gap || 0;
    const guideStyle = { color: '#ff00ff', weight: 1.5, dashArray: '6,4', opacity: 0.8, interactive: false };
    const connectGap = { color: '#22cc44', weight: 1.5, opacity: 0.8, interactive: false };
    const connectBisect = { color: '#00ffff', weight: 1, opacity: 0.6, interactive: false };
    const matchStyleGap = { radius: 5, color: '#22cc44', fillColor: '#22cc44', weight: 2, opacity: 0.9, fillOpacity: 0.4, interactive: false };
    const matchStyle = { radius: 5, color: '#ff00ff', fillColor: '#ff00ff', weight: 2, opacity: 0.9, fillOpacity: 0.4, interactive: false };
    const mapInfo = planet?.Properties?.Map;

    // Grid guides: planet-spanning lines for guideX/guideY
    if (snap.guideX != null && mapInfo) {
      const yMin = mapInfo.Y * SERVER_TILE_SIZE;
      const yMax = yMin + mapInfo.Height * SERVER_TILE_SIZE;
      const [lat1, lng1] = transforms.entropiaToLeaflet(snap.guideX, yMin);
      const [lat2, lng2] = transforms.entropiaToLeaflet(snap.guideX, yMax);
      snapGuideLayerGroup.addLayer(L.polyline([[lat1, lng1], [lat2, lng2]], guideStyle));
    }
    if (snap.guideY != null && mapInfo) {
      const xMin = mapInfo.X * SERVER_TILE_SIZE;
      const xMax = xMin + mapInfo.Width * SERVER_TILE_SIZE;
      const [lat1, lng1] = transforms.entropiaToLeaflet(xMin, snap.guideY);
      const [lat2, lng2] = transforms.entropiaToLeaflet(xMax, snap.guideY);
      snapGuideLayerGroup.addLayer(L.polyline([[lat1, lng1], [lat2, lng2]], guideStyle));
    }

    // Bisector guide line (cyan) + connecting line to corner + distance label
    if (snap.bisector) {
      const { cx, cy, dirX, dirY } = snap.bisector;
      const BISECTOR_GUIDE_LEN = 400;
      const [latA, lngA] = transforms.entropiaToLeaflet(cx - BISECTOR_GUIDE_LEN * dirX, cy - BISECTOR_GUIDE_LEN * dirY);
      const [latB, lngB] = transforms.entropiaToLeaflet(cx + BISECTOR_GUIDE_LEN * dirX, cy + BISECTOR_GUIDE_LEN * dirY);
      const bisectorStyle = { color: '#00ffff', weight: 1.5, dashArray: '4,4', opacity: 0.7, interactive: false };
      snapGuideLayerGroup.addLayer(L.polyline([[latA, lngA], [latB, lngB]], bisectorStyle));

      const bisectDist = Math.round(Math.sqrt((snappedX - cx) ** 2 + (snappedY - cy) ** 2));
      const isBisectGap = gap > 0 && bisectDist === Math.round(gap);
      const cornerStyle = isBisectGap ? matchStyleGap : matchStyle;

      // Highlight the corner vertex
      const [cLat, cLng] = transforms.entropiaToLeaflet(cx, cy);
      snapGuideLayerGroup.addLayer(L.circleMarker([cLat, cLng], cornerStyle));

      // Connecting line from snapped vertex to corner + distance label
      if (bisectDist > 0) {
        const connStyle = isBisectGap ? connectGap : connectBisect;
        const [sLat, sLng] = transforms.entropiaToLeaflet(snappedX, snappedY);
        snapGuideLayerGroup.addLayer(L.polyline([[sLat, sLng], [cLat, cLng]], connStyle));
        const midX = (snappedX + cx) / 2;
        const midY = (snappedY + cy) / 2;
        const [midLat, midLng] = transforms.entropiaToLeaflet(midX, midY);
        const cls = isBisectGap ? 'snap-dist-label snap-dist-gap' : 'snap-dist-label snap-dist-bisector';
        const icon = L.divIcon({ className: cls, html: `${bisectDist}`, iconSize: [40, 16], iconAnchor: [20, 20] });
        snapGuideLayerGroup.addLayer(L.marker([midLat, midLng], { icon, interactive: false }));
      }
    }

    // Edge guide: solid edge segment + dashed extensions + snap point + gap connecting line
    if (snap.edge) {
      const { ax, ay, bx, by, projX, projY, isGap, isExtension } = snap.edge;
      const edgeColor = isGap ? '#22cc44' : '#ff8800';
      const EXTENSION_LEN = 400;

      // Compute extension endpoints beyond both segment endpoints
      const edx = bx - ax, edy = by - ay;
      const eLen = Math.sqrt(edx * edx + edy * edy);
      if (eLen > 0) {
        const udx = edx / eLen, udy = edy / eLen;

        // Solid line for actual edge segment
        const edgeStyle = { color: edgeColor, weight: 2.5, opacity: 0.9, interactive: false };
        const [eLatA, eLngA] = transforms.entropiaToLeaflet(ax, ay);
        const [eLatB, eLngB] = transforms.entropiaToLeaflet(bx, by);
        snapGuideLayerGroup.addLayer(L.polyline([[eLatA, eLngA], [eLatB, eLngB]], edgeStyle));

        // Dashed extensions beyond both endpoints
        const extStyle = { color: edgeColor, weight: 1.5, dashArray: '6,4', opacity: 0.6, interactive: false };
        const extAx = ax - EXTENSION_LEN * udx, extAy = ay - EXTENSION_LEN * udy;
        const extBx = bx + EXTENSION_LEN * udx, extBy = by + EXTENSION_LEN * udy;
        const [extLatA, extLngA] = transforms.entropiaToLeaflet(extAx, extAy);
        const [extLatB, extLngB] = transforms.entropiaToLeaflet(extBx, extBy);
        snapGuideLayerGroup.addLayer(L.polyline([[extLatA, extLngA], [eLatA, eLngA]], extStyle));
        snapGuideLayerGroup.addLayer(L.polyline([[eLatB, eLngB], [extLatB, extLngB]], extStyle));

        // Snap point marker
        const [sLat, sLng] = transforms.entropiaToLeaflet(snappedX, snappedY);
        const snapMarkerStyle = { radius: 4, color: edgeColor, fillColor: edgeColor, weight: 2, opacity: 0.9, fillOpacity: 0.5, interactive: false };
        snapGuideLayerGroup.addLayer(L.circleMarker([sLat, sLng], snapMarkerStyle));

        if (isGap) {
          // Gap snap (bounded or extension): perpendicular connecting line to original edge/extension
          let nx = -edy / eLen, ny = edx / eLen;
          const dotToVertex = (snappedX - ax) * nx + (snappedY - ay) * ny;
          if (dotToVertex < 0) { nx = -nx; ny = -ny; }
          const origProjX = snappedX - nx * gap;
          const origProjY = snappedY - ny * gap;
          const [oLat, oLng] = transforms.entropiaToLeaflet(origProjX, origProjY);
          snapGuideLayerGroup.addLayer(L.polyline([[sLat, sLng], [oLat, oLng]], connectGap));

          const edgeDist = Math.round(gap);
          const midX = (snappedX + origProjX) / 2;
          const midY = (snappedY + origProjY) / 2;
          const [midLat, midLng] = transforms.entropiaToLeaflet(midX, midY);
          const cls = 'snap-dist-label snap-dist-gap';
          const icon = L.divIcon({ className: cls, html: `${edgeDist}`, iconSize: [40, 16], iconAnchor: [20, 20] });
          snapGuideLayerGroup.addLayer(L.marker([midLat, midLng], { icon, interactive: false }));
        } else if (isExtension) {
          // Direct extension magnetic point: connecting line + distance to nearest endpoint
          const distA = Math.sqrt((snappedX - ax) ** 2 + (snappedY - ay) ** 2);
          const distB = Math.sqrt((snappedX - bx) ** 2 + (snappedY - by) ** 2);
          const nearX = distA < distB ? ax : bx;
          const nearY = distA < distB ? ay : by;
          const dist = Math.round(Math.min(distA, distB));

          const connStyle = { color: '#ff8800', weight: 1, opacity: 0.6, interactive: false };
          const [nLat, nLng] = transforms.entropiaToLeaflet(nearX, nearY);
          snapGuideLayerGroup.addLayer(L.polyline([[sLat, sLng], [nLat, nLng]], connStyle));

          if (dist > 0) {
            const midX = (snappedX + nearX) / 2;
            const midY = (snappedY + nearY) / 2;
            const [midLat, midLng] = transforms.entropiaToLeaflet(midX, midY);
            const icon = L.divIcon({ className: 'snap-dist-label', html: `${dist}`, iconSize: [40, 16], iconAnchor: [20, 20] });
            snapGuideLayerGroup.addLayer(L.marker([midLat, midLng], { icon, interactive: false }));
          }
        }
      }
    }
  }

  function clearSnapGuides() {
    if (snapGuideLayerGroup) snapGuideLayerGroup.clearLayers();
  }

  function rebuildGridOverlay() {
    if (!gridOverlayGroup || !transforms || !L) return;
    gridOverlayGroup.clearLayers();
    if (!snapToGrid) return;

    const mapInfo = planet?.Properties?.Map;
    if (!mapInfo || !map) return;

    // Planet bounds in Entropia coords
    const planetXMin = mapInfo.X * SERVER_TILE_SIZE;
    const planetXMax = planetXMin + mapInfo.Width * SERVER_TILE_SIZE;
    const planetYMin = mapInfo.Y * SERVER_TILE_SIZE;
    const planetYMax = planetYMin + mapInfo.Height * SERVER_TILE_SIZE;

    // Visible viewport in Entropia coords (clamp to planet bounds)
    const bounds = map.getBounds();
    const topLeft = transforms.leafletToEntropia(bounds.getNorth(), bounds.getWest());
    const bottomRight = transforms.leafletToEntropia(bounds.getSouth(), bounds.getEast());
    const viewXMin = Math.max(planetXMin, Math.min(topLeft.x, bottomRight.x));
    const viewXMax = Math.min(planetXMax, Math.max(topLeft.x, bottomRight.x));
    const viewYMin = Math.max(planetYMin, Math.min(topLeft.y, bottomRight.y));
    const viewYMax = Math.min(planetYMax, Math.max(topLeft.y, bottomRight.y));

    // Get finest displayable spacing at current zoom
    const spacing = getGridSpacing(map.getZoom(), transforms.ratio);

    // Draw grid lines at each power-of-2 level from spacing up to SERVER_TILE_SIZE
    // Coarser levels get brighter/thicker lines
    for (let level = spacing; level <= SERVER_TILE_SIZE; level *= 2) {
      const isServerBorder = level === SERVER_TILE_SIZE;
      const style = isServerBorder
        ? { color: '#ffffff', weight: 1.0, opacity: 0.45, dashArray: '8,8', interactive: false }
        : level >= SERVER_TILE_SIZE / 2
          ? { color: '#ffffff', weight: 0.6, opacity: 0.30, dashArray: '6,6', interactive: false }
          : { color: '#ffffff', weight: 0.4, opacity: 0.22, interactive: false };

      // Vertical lines (constant X)
      const xStart = Math.ceil(viewXMin / level) * level;
      for (let gx = xStart; gx <= viewXMax; gx += level) {
        // Skip if a coarser level will draw this line
        if (level < SERVER_TILE_SIZE && gx % (level * 2) === 0) continue;
        const [lat1, lng1] = transforms.entropiaToLeaflet(gx, viewYMin);
        const [lat2, lng2] = transforms.entropiaToLeaflet(gx, viewYMax);
        gridOverlayGroup.addLayer(L.polyline([[lat1, lng1], [lat2, lng2]], style));
      }

      // Horizontal lines (constant Y)
      const yStart = Math.ceil(viewYMin / level) * level;
      for (let gy = yStart; gy <= viewYMax; gy += level) {
        if (level < SERVER_TILE_SIZE && gy % (level * 2) === 0) continue;
        const [lat1, lng1] = transforms.entropiaToLeaflet(viewXMin, gy);
        const [lat2, lng2] = transforms.entropiaToLeaflet(viewXMax, gy);
        gridOverlayGroup.addLayer(L.polyline([[lat1, lng1], [lat2, lng2]], style));
      }
    }
  }

  // --- Edit mode: drag/drop and shape editing ---

  function cleanupEditing() {
    // Clear pending debounce to prevent stale callbacks after layer destruction
    if (_editDebounceTimer) {
      clearTimeout(_editDebounceTimer);
      _editDebounceTimer = null;
    }
    clearSnapGuides();
    _activeVertexSnapData = null;
    _editingLoc = null;
    _editingActive = false;
    if (editingLayer) {
      // Remove handler BEFORE disabling editing — editing.disable() can fire
      // a final 'edit' event, which would start a stale debounce cycle
      editingLayer.off('edit');
      if (editingLayer.editing) {
        try { editingLayer.editing.disable(); } catch {}
      }
      editingLayer = null;
    }
    if (editableOverlay) {
      map.removeLayer(editableOverlay);
      editableOverlay = null;
    }
  }

  function enableEditing(layer, locId) {
    let loc = locations.find(l => l.Id === locId);
    if (loc) {
      loc = getEffectiveLocData(loc);
    } else {
      // Check pending adds (negative tempIds)
      const pending = pendingChanges.get(locId);
      if (!pending?.modified) return;
      const mod = pending.modified;
      loc = {
        Id: locId,
        Name: mod.name || '',
        _isPendingAdd: true,
        Properties: {
          Type: mod.locationType === 'Area' ? 'Area' : (mod.locationType || 'Area'),
          AreaType: mod.areaType || null,
          Coordinates: { Longitude: mod.longitude, Latitude: mod.latitude, Altitude: mod.altitude },
          Shape: mod.shape || null,
          Data: mod.shapeData || null,
        }
      };
    }

    if (isArea(loc)) {
      // Areas: enable vertex/shape editing via leaflet-draw
      if (layer.editing) {
        layer.editing.enable();
        editingLayer = layer;
        _editingLoc = loc;
        _editingActive = true;

        // Set up vertex snap data for polygon vertex editing
        // (also refreshed reactively when snap settings change — see reactive statement)
        if (snapEnabled || snapToGrid) {
          _activeVertexSnapData = {
            vertices: snapEnabled ? getVertexSnapCandidates(loc) : [],
            edges: snapEnabled ? getEdgeSnapCandidates(loc) : [],
            gridLines: snapToGrid ? _cachedGridLines : null,
            gap: snapGap,
            threshold: getVertexSnapThreshold(),
          };
        } else {
          _activeVertexSnapData = null;
        }

        // Debounce edit events — leaflet-draw fires 'edit' on every drag step.
        // _editingActive suppresses rebuildLayers so the layer isn't destroyed mid-edit.
        layer.on('edit', () => {
          clearTimeout(_editDebounceTimer);
          _editDebounceTimer = setTimeout(() => {
            _editDebounceTimer = null;
            const shapeType = loc.Properties.Shape.toLowerCase();
            const entropiaData = leafletShapeToEntropia(layer, shapeType);
            if (entropiaData) {
              // Update move handle position to match new pole of inaccessibility
              if (editableOverlay && entropiaData.center) {
                const [lat, lng] = transforms.entropiaToLeaflet(entropiaData.center.x, entropiaData.center.y);
                editableOverlay.setLatLng([lat, lng]);
              }
              dispatch('shapeEdited', { locId, entropiaData });
            }
          }, 80);
        });
      }

      // Add center drag handle for moving entire shapes
      // Circles already have a built-in move handle from leaflet-draw.
      // Rectangles also get one (L.Edit.Rectangle extends L.Edit.SimpleShape),
      // so remove it to avoid a duplicate — our custom handle dispatches entropia coords.
      if (loc.Properties.Shape === 'Rectangle' && layer.editing?._moveMarker) {
        layer.editing._moveMarker.remove();
        layer.editing._moveMarker = null;
      }
      if (loc.Properties.Shape !== 'Circle') {
        // Use the stored coordinates — these are the pole of inaccessibility,
        // guaranteed to be inside the shape and far from edges
        const coords = loc.Properties?.Coordinates;
        const center = coords
          ? L.latLng(...transforms.entropiaToLeaflet(coords.Longitude, coords.Latitude))
          : layer.getBounds().getCenter();
        const moveIcon = L.divIcon({
          className: 'move-handle',
          iconSize: new L.Point(14, 14)
        });
        editableOverlay = L.marker(center, { draggable: true, icon: moveIcon }).addTo(map);

        let dragState = null;
        editableOverlay.on('dragstart', () => {
          // Disable vertex editing during whole-shape move
          if (editingLayer?.editing) {
            try { editingLayer.editing.disable(); } catch {}
          }
          const startPos = editableOverlay.getLatLng();
          if (loc.Properties.Shape === 'Rectangle') {
            dragState = { startCenter: startPos, bounds: layer.getBounds() };
          } else if (loc.Properties.Shape === 'Polygon') {
            dragState = {
              startCenter: startPos,
              latLngs: layer.getLatLngs()[0].map(ll => L.latLng(ll.lat, ll.lng)),
            };
          }
        });

        editableOverlay.on('drag', () => {
          if (!dragState) return;
          const pos = editableOverlay.getLatLng();
          const dLat = pos.lat - dragState.startCenter.lat;
          const dLng = pos.lng - dragState.startCenter.lng;

          if (loc.Properties.Shape === 'Rectangle' && dragState.bounds) {
            const b = dragState.bounds;
            layer.setBounds(L.latLngBounds(
              [b.getSouth() + dLat, b.getWest() + dLng],
              [b.getNorth() + dLat, b.getEast() + dLng]
            ));
          } else if (loc.Properties.Shape === 'Polygon' && dragState.latLngs) {
            layer.setLatLngs([dragState.latLngs.map(ll =>
              L.latLng(ll.lat + dLat, ll.lng + dLng)
            )]);
          }
        });

        editableOverlay.on('dragend', () => {
          if (!dragState) return;
          const pos = editableOverlay.getLatLng();
          const dLat = pos.lat - dragState.startCenter.lat;
          const dLng = pos.lng - dragState.startCenter.lng;

          const eFinalCenter = transforms.leafletToEntropia(
            dragState.startCenter.lat + dLat, dragState.startCenter.lng + dLng
          );
          let entropiaData;

          if (loc.Properties.Shape === 'Rectangle' && dragState.bounds) {
            const b = dragState.bounds;
            const sw = transforms.leafletToEntropia(b.getSouth() + dLat, b.getWest() + dLng);
            const ne = transforms.leafletToEntropia(b.getNorth() + dLat, b.getEast() + dLng);
            const x = Math.min(sw.x, ne.x);
            const y = Math.min(sw.y, ne.y);
            entropiaData = {
              shape: 'Rectangle',
              data: { x, y, width: Math.abs(ne.x - sw.x), height: Math.abs(ne.y - sw.y) },
              center: eFinalCenter
            };
          } else if (loc.Properties.Shape === 'Polygon' && dragState.latLngs) {
            const vertices = [];
            for (const ll of dragState.latLngs) {
              const e = transforms.leafletToEntropia(ll.lat + dLat, ll.lng + dLng);
              vertices.push(e.x, e.y);
            }
            ensureClosedRing(vertices);
            entropiaData = {
              shape: 'Polygon',
              data: { vertices },
              center: poleOfInaccessibility(vertices)
            };
          }

          dragState = null;
          if (entropiaData) {
            dispatch('shapeEdited', { locId, entropiaData });
          }
          // Re-enable vertex editing so handles reattach to moved geometry.
          // L.Edit.Poly caches latlngs at init; update the stale reference
          // after setLatLngs() replaced the polygon's _latlngs array.
          if (editingLayer?.editing) {
            if (editingLayer.editing.latlngs) {
              editingLayer.editing.latlngs = [editingLayer._latlngs];
            }
            try { editingLayer.editing.enable(); } catch (e) {
              console.warn('Failed to re-enable editing after drag:', e);
            }
            // Remove Leaflet-Draw's built-in move marker for Rectangles — we use our own custom handle.
            // editing.enable() recreates it, so we must re-remove it after every drag.
            if (loc.Properties.Shape === 'Rectangle' && editingLayer.editing?._moveMarker) {
              editingLayer.editing._moveMarker.remove();
              editingLayer.editing._moveMarker = null;
            }
          }
        });
      }
    } else {
      // Point locations: overlay a draggable marker
      const coords = loc.Properties?.Coordinates;
      if (!coords) return;
      const [lat, lng] = transforms.entropiaToLeaflet(coords.Longitude, coords.Latitude);
      editableOverlay = L.marker([lat, lng], { draggable: true }).addTo(map);
      editableOverlay.on('dragend', () => {
        const newPos = editableOverlay.getLatLng();
        const eCoords = transforms.leafletToEntropia(newPos.lat, newPos.lng);
        dispatch('shapeEdited', { locId, entropiaData: { shape: null, data: null, center: eCoords } });
        // Update the underlying circleMarker position
        if (layer.setLatLng) layer.setLatLng(newPos);
      });
    }
  }

  // --- Preview layer for shape data editing ---

  function updatePreview(ps) {
    if (previewLayer) {
      map.removeLayer(previewLayer);
      previewLayer = null;
    }
    if (!ps || !transforms || !L) return;

    const previewStyle = {
      color: '#00ffff',
      fillColor: '#00ffff',
      weight: 2,
      opacity: 0.9,
      fillOpacity: 0.15,
      dashArray: '6,4'
    };

    try {
      if (ps.shape === 'Circle' && ps.data) {
        const x = Number(ps.data.x), y = Number(ps.data.y), r = Number(ps.data.radius);
        if (!isFinite(x) || !isFinite(y) || !isFinite(r) || r <= 0) return;
        const [lat, lng] = transforms.entropiaToLeaflet(x, y);
        const radius = r / transforms.ratio;
        previewLayer = L.circle([lat, lng], { ...previewStyle, radius });
      } else if (ps.shape === 'Rectangle' && ps.data) {
        const x = Number(ps.data.x), y = Number(ps.data.y), w = Number(ps.data.width), h = Number(ps.data.height);
        if (!isFinite(x) || !isFinite(y) || !isFinite(w) || !isFinite(h)) return;
        const [lat1, lng1] = transforms.entropiaToLeaflet(x, y);
        const [lat2, lng2] = transforms.entropiaToLeaflet(x + w, y + h);
        previewLayer = L.rectangle([[lat1, lng1], [lat2, lng2]], previewStyle);
      } else if (ps.shape === 'Polygon' && ps.data?.vertices?.length >= 6) {
        const latLngs = [];
        for (let i = 0; i < ps.data.vertices.length; i += 2) {
          const vx = Number(ps.data.vertices[i]), vy = Number(ps.data.vertices[i + 1]);
          if (!isFinite(vx) || !isFinite(vy)) return;
          const [lat, lng] = transforms.entropiaToLeaflet(vx, vy);
          latLngs.push([lat, lng]);
        }
        previewLayer = L.polygon(latLngs, previewStyle);
      } else if (!ps.shape && ps.center) {
        const cx = Number(ps.center.x), cy = Number(ps.center.y);
        if (!isFinite(cx) || !isFinite(cy)) return;
        const [lat, lng] = transforms.entropiaToLeaflet(cx, cy);
        previewLayer = L.circleMarker([lat, lng], {
          ...previewStyle,
          radius: 7,
          fillOpacity: 0.4
        });
      }
    } catch (e) {
      // Invalid shape data — skip preview silently
      return;
    }

    if (previewLayer) {
      previewLayer.addTo(map);
    }
  }

  function toggleDrawControl() {
    if (!map || !L) return;
    if (editMode && !drawControl) {
      drawControl = new L.Control.Draw({
        position: 'topright',
        draw: {
          polygon: { allowIntersection: false, shapeOptions: { color: '#00ff00' } },
          rectangle: { shapeOptions: { color: '#00ff00' } },
          circle: { shapeOptions: { color: '#00ff00' } },
          marker: true,
          polyline: false,
          circlemarker: false
        },
        edit: false // We use our own enableEditing(), not leaflet-draw's edit toolbar
      });
      map.addControl(drawControl);
      map.on('draw:drawstart', () => dispatch('select', null));
    } else if (!editMode && drawControl) {
      cleanupEditing();
      map.off('draw:drawstart');
      map.removeControl(drawControl);
      drawControl = null;
    }
  }

  /** Ensure polygon vertex array is a closed ring (first vertex == last vertex). */
  function ensureClosedRing(vertices) {
    if (vertices.length < 4) return; // need at least 2 coordinate pairs
    const EPS = 0.01; // tolerance for rounding errors
    const fx = vertices[0], fy = vertices[1];
    const lx = vertices[vertices.length - 2], ly = vertices[vertices.length - 1];
    if (Math.abs(fx - lx) < EPS && Math.abs(fy - ly) < EPS) {
      // Already closed — snap last to exactly match first (fix rounding)
      vertices[vertices.length - 2] = fx;
      vertices[vertices.length - 1] = fy;
    } else {
      // Not closed — append first vertex
      vertices.push(fx, fy);
    }
  }

  function leafletShapeToEntropia(layer, shapeType) {
    if (shapeType === 'circle') {
      const center = layer.getLatLng();
      const eCenter = transforms.leafletToEntropia(center.lat, center.lng);
      const radius = Math.round(layer.getRadius() * transforms.ratio);
      return { shape: 'Circle', data: { x: eCenter.x, y: eCenter.y, radius }, center: eCenter };
    } else if (shapeType === 'rectangle') {
      const bounds = layer.getBounds();
      const sw = transforms.leafletToEntropia(bounds.getSouthWest().lat, bounds.getSouthWest().lng);
      const ne = transforms.leafletToEntropia(bounds.getNorthEast().lat, bounds.getNorthEast().lng);
      const x = Math.min(sw.x, ne.x);
      const y = Math.min(sw.y, ne.y);
      const width = Math.abs(ne.x - sw.x);
      const height = Math.abs(ne.y - sw.y);
      const cx = Math.round(x + width / 2);
      const cy = Math.round(y + height / 2);
      return { shape: 'Rectangle', data: { x, y, width, height }, center: { x: cx, y: cy } };
    } else if (shapeType === 'polygon') {
      const latLngs = layer.getLatLngs()[0];
      const vertices = [];
      for (const ll of latLngs) {
        const e = transforms.leafletToEntropia(ll.lat, ll.lng);
        vertices.push(e.x, e.y);
      }
      ensureClosedRing(vertices);
      const center = poleOfInaccessibility(vertices);
      return { shape: 'Polygon', data: { vertices }, center };
    } else if (shapeType === 'marker') {
      const ll = layer.getLatLng();
      const e = transforms.leafletToEntropia(ll.lat, ll.lng);
      return { shape: null, data: null, center: e };
    }
    return null;
  }

  /**
   * Directly update a layer's geometry without a full rebuild.
   * Used for real-time form-to-map updates during editing.
   */
  export function updateLayerShape(locId, shapeInfo) {
    const layer = layerById.get(locId);
    if (!layer || !transforms || !L) return;
    // Don't programmatically update a layer that leaflet-draw is actively editing —
    // the round-trip through integer Entropia coords would desync the editing handles.
    if (layer === editingLayer) return;

    if (shapeInfo.shape === 'Circle' && shapeInfo.data) {
      const [lat, lng] = transforms.entropiaToLeaflet(shapeInfo.data.x, shapeInfo.data.y);
      const radius = shapeInfo.data.radius / transforms.ratio;
      if (layer.setLatLng) layer.setLatLng([lat, lng]);
      if (layer.setRadius) layer.setRadius(radius);
    } else if (shapeInfo.shape === 'Rectangle' && shapeInfo.data) {
      const d = shapeInfo.data;
      const [lat1, lng1] = transforms.entropiaToLeaflet(d.x, d.y);
      const [lat2, lng2] = transforms.entropiaToLeaflet(d.x + d.width, d.y + d.height);
      if (layer.setBounds) layer.setBounds([[lat1, lng1], [lat2, lng2]]);
    } else if (shapeInfo.shape === 'Polygon' && shapeInfo.data?.vertices?.length >= 6) {
      const latLngs = [];
      for (let i = 0; i < shapeInfo.data.vertices.length; i += 2) {
        const [lat, lng] = transforms.entropiaToLeaflet(shapeInfo.data.vertices[i], shapeInfo.data.vertices[i + 1]);
        latLngs.push([lat, lng]);
      }
      if (layer.setLatLngs) layer.setLatLngs([latLngs]);
    } else if (!shapeInfo.shape && shapeInfo.center) {
      const [lat, lng] = transforms.entropiaToLeaflet(shapeInfo.center.x, shapeInfo.center.y);
      if (layer.setLatLng) layer.setLatLng([lat, lng]);
    }
  }

  /**
   * Pan the map to a specific location.
   */
  export function clearDrawnLayer() {
    if (drawnLayer && map) {
      map.removeLayer(drawnLayer);
      drawnLayer = null;
    }
  }

  /** Force cleanup of editing state and rebuild all layers. */
  export function forceRebuild() {
    cleanupEditing();
    rebuildLayers();
  }

  /** Rebuild the DB pending changes overlay (call when seeding state changes). */
  export function rebuildDbOverlay() {
    rebuildDbChangesOverlay();
  }

  export function panToLocation(loc) {
    if (!loc) return;
    if (!map || !transforms || !L) {
      queuedPanTarget = loc;
      return;
    }
    queuedPanTarget = null;

    const FOCUS_PADDING = [40, 40];
    const FOCUS_MAX_ZOOM = 6;
    const POINT_FOCUS_ZOOM = 4;

    if (isArea(loc) && loc.Properties.Data) {
      const d = loc.Properties.Data;
      if (loc.Properties.Shape === 'Circle') {
        const [lat, lng] = transforms.entropiaToLeaflet(d.x, d.y);
        const radius = Math.max(1, Number(d.radius || 0) / transforms.ratio);
        const bounds = L.circle([lat, lng], { radius }).getBounds();
        map.fitBounds(bounds, { padding: FOCUS_PADDING, maxZoom: FOCUS_MAX_ZOOM });
      } else if (loc.Properties.Shape === 'Rectangle') {
        const [lat1, lng1] = transforms.entropiaToLeaflet(d.x, d.y);
        const [lat2, lng2] = transforms.entropiaToLeaflet(d.x + d.width, d.y + d.height);
        map.fitBounds([[lat1, lng1], [lat2, lng2]], { padding: FOCUS_PADDING, maxZoom: FOCUS_MAX_ZOOM });
      } else if (loc.Properties.Shape === 'Polygon' && d.vertices?.length >= 2) {
        const latLngs = [];
        for (let i = 0; i < d.vertices.length; i += 2) {
          const [lat, lng] = transforms.entropiaToLeaflet(d.vertices[i], d.vertices[i + 1]);
          latLngs.push([lat, lng]);
        }
        if (latLngs.length > 0) {
          map.fitBounds(latLngs, { padding: FOCUS_PADDING, maxZoom: FOCUS_MAX_ZOOM });
        }
      }
    } else {
      const coords = loc.Properties?.Coordinates;
      if (coords?.Longitude || coords?.Longitude === 0) {
        const [lat, lng] = transforms.entropiaToLeaflet(coords.Longitude, coords.Latitude);
        map.setView([lat, lng], Math.max(map.getZoom(), POINT_FOCUS_ZOOM));
      }
    }
  }
</script>

<style>
  .map-wrapper {
    width: 100%;
    height: 100%;
    position: relative;
  }

  .map-container {
    width: 100%;
    height: 100%;
    background: #1a1a2e;
  }

  .map-container :global(.leaflet-container) {
    background: #1a1a2e;
    width: 100%;
    height: 100%;
  }

  .map-container :global(.move-handle) {
    background: var(--accent-color, #3b82f6);
    border: 2px solid white;
    border-radius: 50%;
    cursor: grab;
    box-shadow: 0 1px 4px rgba(0,0,0,0.4);
  }
  .map-container :global(.move-handle:active) {
    cursor: grabbing;
  }

  .snap-toolbar {
    position: absolute;
    bottom: 8px;
    left: 8px;
    z-index: 1000;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 6px;
    background: rgba(0, 0, 0, 0.75);
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    font-size: 12px;
    color: var(--text-color, #e0e0e0);
  }

  .snap-btn {
    padding: 3px 8px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted, #999);
    font-size: 11px;
    cursor: pointer;
    white-space: nowrap;
  }
  .snap-btn:hover { background: rgba(255, 255, 255, 0.1); }
  .snap-btn.active {
    background: var(--accent-color, #3b82f6);
    color: white;
    border-color: var(--accent-color, #3b82f6);
  }

  .snap-gap-label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-muted, #999);
  }
  .snap-gap-input {
    width: 60px;
    padding: 2px 4px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-color, #e0e0e0);
    font-size: 11px;
  }

  .snap-hint {
    font-size: 10px;
    color: var(--text-muted, #777);
    padding-left: 4px;
  }

  /* Vertex editing handles: smaller and round.
     Total visual size = 8px content + 2×2px border = 12px.
     Margins must be half of total (−6px) to center on the vertex. */
  .map-container :global(.leaflet-editing-icon) {
    width: 8px !important;
    height: 8px !important;
    margin-left: -6px !important;
    margin-top: -6px !important;
    border-radius: 50%;
    border: 2px solid white;
    background: var(--accent-color, #3b82f6);
    box-shadow: 0 0 3px rgba(0, 0, 0, 0.5);
  }
  .map-container :global(.leaflet-editing-icon.vertex-dragging) {
    background: #ff8c00;
    box-shadow: 0 0 6px rgba(255, 140, 0, 0.7);
    opacity: 0.7;
  }

  .map-container :global(.snap-dist-label) {
    background: rgba(0, 0, 0, 0.8);
    color: #ff00ff;
    font-size: 11px;
    font-weight: 600;
    padding: 1px 4px;
    border-radius: 3px;
    border: 1px solid rgba(255, 0, 255, 0.4);
    white-space: nowrap;
    text-align: center;
    pointer-events: none;
    line-height: 14px;
  }

  .map-container :global(.snap-dist-label.snap-dist-gap) {
    color: #22cc44;
    border-color: rgba(34, 204, 68, 0.5);
  }

  .map-container :global(.snap-dist-label.snap-dist-bisector) {
    color: #00ffff;
    border-color: rgba(0, 255, 255, 0.4);
  }
</style>

<div class="map-wrapper">
  <div class="map-container" bind:this={mapContainer}></div>
  {#if editMode}
    <div class="snap-toolbar">
      <button
        class="snap-btn"
        class:active={snapEnabled}
        on:click={() => snapEnabled = !snapEnabled}
      >Snap</button>
      <button
        class="snap-btn"
        class:active={snapToGrid}
        on:click={() => { snapToGrid = !snapToGrid; rebuildGridOverlay(); }}
      >Snap Grid</button>
      {#if snapEnabled}
        <label class="snap-gap-label">
          Gap
          <input
            type="number"
            class="snap-gap-input"
            bind:value={snapGap}
            min="0"
            step="100"
          />
        </label>
      {/if}
      <span class="snap-hint">Shift+drag vertex = angle snap</span>
    </div>
  {/if}
</div>

<ContextMenu
  bind:element={contextMenuElement}
  menu={contextMenuItems}
  bind:visible={contextMenuVisible}
  bind:contextMenuPos={contextMenuPos}
  bind:payload={contextMenuPayload}
/>

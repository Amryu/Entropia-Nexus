<script>
  // @ts-nocheck
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { buildCoordTransforms, getTypeColor, getEffectiveType, isArea, poleOfInaccessibility } from './mapEditorUtils.js';
  import { formatMobSpawnDisplayName } from '$lib/mapUtil.js';
  import ContextMenu from '../ContextMenu.svelte';

  export let planet = null;
  export let locations = [];
  export let filteredLocationIds = null; // Set of IDs to show, or null for all
  export let selectedId = null;
  export let pendingChanges = new Map();
  export let editMode = false;
  export let previewShape = null;

  const dispatch = createEventDispatcher();

  let mapContainer;
  let map;
  let imageOverlay;
  let layerGroup;
  let drawControl;
  let transforms = null;
  let imgWidth = 0;
  let imgHeight = 0;
  let layerById = new Map();
  let L;

  // Preview and editing state
  let previewLayer = null;
  let drawnLayer = null; // Temporary layer for just-drawn shapes (removed on add/cancel)
  let editingLayer = null;
  let editableOverlay = null;
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
  $: if (map && filteredLocationIds !== undefined) updateVisibility();
  $: if (map && selectedId !== undefined) updateSelection();
  $: if (map && editMode !== undefined) toggleDrawControl();
  $: if (map && L && transforms) updatePreview(previewShape);

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
      maxZoom: 5,
      zoomSnap: 0.25,
      zoomDelta: 0.5,
      attributionControl: false
    });

    layerGroup = L.layerGroup().addTo(map);

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

      if (imageOverlay) map.removeLayer(imageOverlay);

      const bounds = [[0, 0], [imgHeight, imgWidth]];
      imageOverlay = L.imageOverlay(imageUrl, bounds).addTo(map);
      map.fitBounds(bounds);

      updateMaxBounds();
      map.on('zoomend', updateMaxBounds);

      rebuildLayers();
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

    let layer;

    if (shape === 'Circle') {
      const [lat, lng] = transforms.entropiaToLeaflet(data.x, data.y);
      const radius = data.radius / transforms.ratio;
      layer = L.circle([lat, lng], { ...options, radius });
    } else if (shape === 'Rectangle') {
      const [lat1, lng1] = transforms.entropiaToLeaflet(data.x, data.y);
      const [lat2, lng2] = transforms.entropiaToLeaflet(data.x + data.width, data.y + data.height);
      layer = L.rectangle([[lat1, lng1], [lat2, lng2]], options);
    } else if (shape === 'Polygon') {
      const verts = data.vertices || [];
      const latLngs = [];
      for (let i = 0; i < verts.length; i += 2) {
        const [lat, lng] = transforms.entropiaToLeaflet(verts[i], verts[i + 1]);
        latLngs.push([lat, lng]);
      }
      if (latLngs.length < 3) return null;
      layer = L.polygon(latLngs, options);
    }

    if (layer) {
      const tooltipName = loc.Properties?.Type === 'MobArea' ? formatMobSpawnDisplayName(loc.Name, loc.Maturities) : loc.Name;
      layer.bindTooltip(tooltipName, { sticky: true });
    }
    return layer;
  }

  function createPendingAddLayer(mod, tempId) {
    if (!transforms || !L) return null;
    const addStyle = {
      fillColor: '#00ff00',
      color: '#00ff00',
      weight: 3,
      fillOpacity: 0.2,
      dashArray: '6,3',
      interactive: true
    };

    const isAreaAdd = mod.locationType === 'Area' && mod.shape && mod.shapeData;
    if (isAreaAdd) {
      const data = mod.shapeData;
      let layer;
      if (mod.shape === 'Circle') {
        const [lat, lng] = transforms.entropiaToLeaflet(data.x, data.y);
        const radius = data.radius / transforms.ratio;
        layer = L.circle([lat, lng], { ...addStyle, radius });
      } else if (mod.shape === 'Rectangle') {
        const [lat1, lng1] = transforms.entropiaToLeaflet(data.x, data.y);
        const [lat2, lng2] = transforms.entropiaToLeaflet(data.x + data.width, data.y + data.height);
        layer = L.rectangle([[lat1, lng1], [lat2, lng2]], addStyle);
      } else if (mod.shape === 'Polygon' && data.vertices?.length >= 6) {
        const latLngs = [];
        for (let i = 0; i < data.vertices.length; i += 2) {
          const [lat, lng] = transforms.entropiaToLeaflet(data.vertices[i], data.vertices[i + 1]);
          latLngs.push([lat, lng]);
        }
        layer = L.polygon(latLngs, addStyle);
      }
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

  function getChangeStyle(changeState, baseColor) {
    const base = {
      fillColor: baseColor,
      borderColor: baseColor,
      weight: 2,
      fillOpacity: 0.25,
      dashArray: null
    };

    if (changeState === 'delete') {
      return { ...base, borderColor: '#ff0000', fillColor: '#ff0000', fillOpacity: 0.15, dashArray: '8,4', weight: 3 };
    } else if (changeState === 'edit') {
      return { ...base, borderColor: '#ff8800', dashArray: '6,3', weight: 3 };
    } else if (changeState === 'add') {
      return { ...base, borderColor: '#00ff00', dashArray: '6,3', weight: 3 };
    }
    return base;
  }

  function updateVisibility() {
    if (!layerGroup) return;
    layerGroup.eachLayer(layer => {
      const locId = layer._locId;
      if (locId === undefined) return;
      // Pending adds (negative tempIds) are always visible regardless of filters
      const isPendingAdd = pendingChanges.has(locId) && pendingChanges.get(locId).action === 'add';
      const visible = isPendingAdd || !filteredLocationIds || filteredLocationIds.has(locId);
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
        if (editMode) enableEditing(layer, locId);
      } else {
        // Check if this is a pending add (negative tempId)
        const pending = pendingChanges.get(locId);
        if (pending?.action === 'add') {
          // Restore pending add style
          if (layer.setStyle) layer.setStyle({ weight: 3, color: '#00ff00', dashArray: '6,3' });
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
  }

  // --- Edit mode: drag/drop and shape editing ---

  function cleanupEditing() {
    // Clear pending debounce to prevent stale callbacks after layer destruction
    if (_editDebounceTimer) {
      clearTimeout(_editDebounceTimer);
      _editDebounceTimer = null;
    }
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
        _editingActive = true;

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
          }, 300);
        });
      }

      // Add center drag handle for moving entire shapes
      // (Circles already have a built-in move handle from leaflet-draw)
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
          // Store original geometry and disable vertex editing during move
          if (editingLayer?.editing) {
            try { editingLayer.editing.disable(); } catch {}
          }
          const startPos = editableOverlay.getLatLng();
          if (loc.Properties.Shape === 'Rectangle') {
            dragState = { bounds: layer.getBounds(), startCenter: startPos };
          } else if (loc.Properties.Shape === 'Polygon') {
            dragState = {
              latLngs: layer.getLatLngs()[0].map(ll => L.latLng(ll.lat, ll.lng)),
              startCenter: startPos
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
          const eCenter = transforms.leafletToEntropia(pos.lat, pos.lng);
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
              center: eCenter
            };
          } else if (loc.Properties.Shape === 'Polygon' && dragState.latLngs) {
            const vertices = [];
            for (const ll of dragState.latLngs) {
              const e = transforms.leafletToEntropia(ll.lat + dLat, ll.lng + dLng);
              vertices.push(e.x, e.y);
            }
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
    } else if (!editMode && drawControl) {
      cleanupEditing();
      map.removeControl(drawControl);
      drawControl = null;
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

  export function panToLocation(loc) {
    if (!map || !transforms) return;

    if (isArea(loc) && loc.Properties.Data) {
      const d = loc.Properties.Data;
      if (loc.Properties.Shape === 'Circle') {
        const [lat, lng] = transforms.entropiaToLeaflet(d.x, d.y);
        map.setView([lat, lng], map.getZoom());
      } else if (loc.Properties.Shape === 'Rectangle') {
        const [lat, lng] = transforms.entropiaToLeaflet(d.x + d.width / 2, d.y + d.height / 2);
        map.setView([lat, lng], map.getZoom());
      } else if (loc.Properties.Shape === 'Polygon' && d.vertices?.length >= 2) {
        let sx = 0, sy = 0, n = 0;
        for (let i = 0; i < d.vertices.length; i += 2) { sx += d.vertices[i]; sy += d.vertices[i + 1]; n++; }
        const [lat, lng] = transforms.entropiaToLeaflet(sx / n, sy / n);
        map.setView([lat, lng], map.getZoom());
      }
    } else {
      const coords = loc.Properties?.Coordinates;
      if (coords?.Longitude || coords?.Longitude === 0) {
        const [lat, lng] = transforms.entropiaToLeaflet(coords.Longitude, coords.Latitude);
        map.setView([lat, lng], map.getZoom());
      }
    }
  }
</script>

<style>
  .map-container {
    width: 100%;
    height: 100%;
    background: #1a1a2e;
    position: relative;
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
</style>

<div class="map-container" bind:this={mapContainer}></div>

<ContextMenu
  bind:element={contextMenuElement}
  menu={contextMenuItems}
  bind:visible={contextMenuVisible}
  bind:contextMenuPos={contextMenuPos}
  bind:payload={contextMenuPayload}
/>

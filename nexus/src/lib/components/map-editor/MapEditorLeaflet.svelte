<script>
  // @ts-nocheck
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { buildCoordTransforms, getTypeColor, getEffectiveType, isArea } from './mapEditorUtils.js';
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
  let drawnItems;
  let transforms = null;
  let imgWidth = 0;
  let imgHeight = 0;
  let layerById = new Map();
  let L;

  // Preview and editing state
  let previewLayer = null;
  let editingLayer = null;
  let editableOverlay = null;
  let _clickedLayer = false;

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

  $: if (map && locations && pendingChanges !== undefined) rebuildLayers();
  $: if (map && filteredLocationIds !== undefined) updateVisibility();
  $: if (map && selectedId !== undefined) updateSelection();
  $: if (map && editMode !== undefined) toggleDrawControl();
  $: if (map && L && transforms) updatePreview(previewShape);

  onMount(async () => {
    L = await import('leaflet');
    await import('leaflet-draw');

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
    drawnItems = new L.FeatureGroup().addTo(map);

    // Draw events — use string literal; L.Draw.Event.CREATED may be undefined with ESM imports
    map.on('draw:created', (e) => {
      const layer = e.layer;
      const shapeType = e.layerType;
      drawnItems.addLayer(layer);
      const entropiaData = leafletShapeToEntropia(layer, shapeType);
      if (entropiaData) {
        entropiaData.isMarker = (shapeType === 'marker');
      }
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

  function rebuildLayers() {
    if (!map || !transforms || !L) return;

    cleanupEditing();
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
      const layer = createLocationLayer(loc);
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
          contextMenuPayload = loc;
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

    // Clear drawn items (they've been converted to pending changes)
    if (drawnItems) drawnItems.clearLayers();

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
      dashArray: '6,3'
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
      const visible = !filteredLocationIds || filteredLocationIds.has(locId);
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
        const loc = locations.find(l => l.Id === locId);
        if (loc && layer.setStyle) {
          const effectiveType = getEffectiveType(loc);
          const color = getTypeColor(effectiveType);
          const changeState = getChangeState(locId);
          const style = getChangeStyle(changeState, color);
          layer.setStyle({ weight: style.weight, color: style.borderColor });
        }
      }
    });
  }

  // --- Edit mode: drag/drop and shape editing ---

  function cleanupEditing() {
    if (editingLayer) {
      if (editingLayer.editing) {
        try { editingLayer.editing.disable(); } catch {}
      }
      editingLayer.off('edit');
      editingLayer = null;
    }
    if (editableOverlay) {
      map.removeLayer(editableOverlay);
      editableOverlay = null;
    }
  }

  function enableEditing(layer, locId) {
    const loc = locations.find(l => l.Id === locId);
    if (!loc) return;

    if (isArea(loc)) {
      // Areas: enable vertex/shape editing via leaflet-draw
      if (layer.editing) {
        layer.editing.enable();
        editingLayer = layer;

        layer.on('edit', () => {
          const shapeType = loc.Properties.Shape.toLowerCase();
          const entropiaData = leafletShapeToEntropia(layer, shapeType);
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
        edit: { featureGroup: drawnItems, remove: false }
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
      let sumX = 0, sumY = 0;
      for (const ll of latLngs) {
        const e = transforms.leafletToEntropia(ll.lat, ll.lng);
        vertices.push(e.x, e.y);
        sumX += e.x; sumY += e.y;
      }
      const cx = Math.round(sumX / latLngs.length);
      const cy = Math.round(sumY / latLngs.length);
      return { shape: 'Polygon', data: { vertices }, center: { x: cx, y: cy } };
    } else if (shapeType === 'marker') {
      const ll = layer.getLatLng();
      const e = transforms.leafletToEntropia(ll.lat, ll.lng);
      return { shape: null, data: null, center: e };
    }
    return null;
  }

  /**
   * Pan the map to a specific location.
   */
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
</style>

<div class="map-container" bind:this={mapContainer}></div>

<ContextMenu
  bind:element={contextMenuElement}
  menu={contextMenuItems}
  bind:visible={contextMenuVisible}
  bind:contextMenuPos={contextMenuPos}
  bind:payload={contextMenuPayload}
/>

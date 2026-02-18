// @ts-nocheck
/**
 * Map Editor Utilities — coordinate transforms, type constants, colors.
 * Shared between admin map editor and public map edit mode.
 */

// ─── Location / Area Type Constants ───────────────────────────────────────────

export const LOCATION_TYPES = [
  'Teleporter', 'Npc', 'Interactable', 'Outpost', 'Camp', 'City',
  'WaveEvent', 'RevivalPoint', 'InstanceEntrance', 'Vendor', 'Estate'
];

export const AREA_TYPES = [
  'MobArea', 'LandArea', 'PvpArea', 'PvpLootArea',
  'ZoneArea', 'CityArea', 'EstateArea', 'EventArea'
];

export const SHAPES = ['Circle', 'Rectangle', 'Polygon'];

// ─── Type Colors (matches Map.svelte getColorByType) ─────────────────────────

export const TYPE_COLORS = {
  Teleporter:     '#00ffff',
  Npc:            '#ff69b4',
  Interactable:   '#dda0dd',
  Outpost:        '#87ceeb',
  Camp:           '#f0e68c',
  City:           '#90ee90',
  WaveEvent:      '#da70d6',
  RevivalPoint:   '#98fb98',
  InstanceEntrance:'#b0c4de',
  Vendor:         '#ffa07a',
  Estate:         '#deb887',
  // Area types
  LandArea:       '#00ff00',
  MobArea:        '#ffff00',
  PvpArea:        '#ffa500',
  PvpLootArea:    '#ff0000',
  ZoneArea:       '#4169e1',
  CityArea:       '#90ee90',
  EstateArea:     '#deb887',
  EventArea:      '#ffffff'
};

export function getTypeColor(type) {
  return TYPE_COLORS[type] || '#aaaaaa';
}

/**
 * Get the effective "type key" for a location, preferring AreaType for areas.
 */
export function getEffectiveType(loc) {
  if (loc?.Properties?.Type === 'Area' || loc?.Properties?.AreaType || loc?.Properties?.Shape) {
    return loc.Properties.AreaType || loc.Properties.Type || 'Area';
  }
  return loc?.Properties?.Type || 'Unknown';
}

/**
 * Whether a location is a shape (area) vs. a point location.
 */
export function isArea(loc) {
  return !!(loc?.Properties?.Shape && loc?.Properties?.Data);
}

// ─── Coordinate Transforms ───────────────────────────────────────────────────

/**
 * Build coordinate transform functions for a given planet and image dimensions.
 * @param {object} planet  — planet object with Properties.Map.{X,Y,Width,Height}
 * @param {number} imgWidth  — natural image width in pixels
 * @param {number} imgHeight — natural image height in pixels
 * @returns {{ entropiaToLeaflet, leafletToEntropia, ratio }}
 */
export function buildCoordTransforms(planet, imgWidth, imgHeight) {
  const mapInfo = planet?.Properties?.Map;
  if (!mapInfo) throw new Error('Planet missing Map properties');

  const imageTileSize = imgWidth / mapInfo.Width;
  const ratio = 8192 / imageTileSize;
  const offsetX = mapInfo.X * 8192;
  const offsetY = mapInfo.Y * 8192;
  const planetHeightE = mapInfo.Height * 8192;

  function entropiaToLeaflet(eX, eY) {
    const imgX = (eX - offsetX) / ratio;
    const imgY = (planetHeightE - (eY - offsetY)) / ratio;
    return [imgHeight - imgY, imgX]; // [lat, lng]
  }

  function leafletToEntropia(lat, lng) {
    const imgX = lng;
    const imgY = imgHeight - lat;
    return {
      x: Math.round(imgX * ratio + offsetX),
      y: Math.round(planetHeightE - imgY * ratio + offsetY)
    };
  }

  return { entropiaToLeaflet, leafletToEntropia, ratio };
}

// ─── Pole of Inaccessibility (polylabel) ────────────────────────────────────
// Finds the point inside a polygon with maximum distance to the boundary.
// Based on Mapbox's polylabel algorithm (ISC license).

/**
 * Find the pole of inaccessibility for a polygon.
 * @param {number[]} vertices — flat array [x0, y0, x1, y1, ...]
 * @param {number} [precision=1] — stop when cell size < precision
 * @returns {{ x: number, y: number }}
 */
export function poleOfInaccessibility(vertices, precision = 1) {
  if (!vertices || vertices.length < 6) {
    // Degenerate — fall back to centroid
    return polygonCentroid(vertices);
  }

  // Convert flat array to ring of [x,y] pairs
  const ring = [];
  for (let i = 0; i < vertices.length; i += 2) {
    ring.push([vertices[i], vertices[i + 1]]);
  }

  // Bounding box
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const [x, y] of ring) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }

  const width = maxX - minX;
  const height = maxY - minY;
  const cellSize = Math.max(width, height);

  if (cellSize === 0) return { x: Math.round(minX), y: Math.round(minY) };

  const halfCell = cellSize / 2;

  // Priority queue (simple sorted-insert array — polygons are small)
  const queue = [];

  function enqueue(cell) {
    // Binary insert by max potential (descending)
    let lo = 0, hi = queue.length;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (queue[mid].max > cell.max) lo = mid + 1; else hi = mid;
    }
    queue.splice(lo, 0, cell);
  }

  function makeCell(cx, cy, h) {
    const d = pointToPolygonDist(cx, cy, ring);
    return { x: cx, y: cy, h, d, max: d + h * Math.SQRT2 };
  }

  // Seed the queue with initial cells covering the bounding box
  for (let x = minX; x < maxX; x += cellSize) {
    for (let y = minY; y < maxY; y += cellSize) {
      enqueue(makeCell(x + halfCell, y + halfCell, halfCell));
    }
  }

  // Best result = centroid as starting guess
  const centroid = polygonCentroid(vertices);
  let bestCell = makeCell(centroid.x, centroid.y, 0);

  while (queue.length) {
    const cell = queue.shift(); // highest potential

    // Update best if this cell's center is better
    if (cell.d > bestCell.d) bestCell = cell;

    // Prune: can't improve beyond precision
    if (cell.max - bestCell.d <= precision) continue;

    // Subdivide into 4
    const h = cell.h / 2;
    enqueue(makeCell(cell.x - h, cell.y - h, h));
    enqueue(makeCell(cell.x + h, cell.y - h, h));
    enqueue(makeCell(cell.x - h, cell.y + h, h));
    enqueue(makeCell(cell.x + h, cell.y + h, h));
  }

  return { x: Math.round(bestCell.x), y: Math.round(bestCell.y) };
}

/** Signed distance from point to polygon boundary (positive = inside). */
function pointToPolygonDist(px, py, ring) {
  let inside = false;
  let minDistSq = Infinity;

  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [ax, ay] = ring[i];
    const [bx, by] = ring[j];

    // Ray-casting for inside/outside
    if ((ay > py) !== (by > py) && (px < (bx - ax) * (py - ay) / (by - ay) + ax)) {
      inside = !inside;
    }

    // Squared distance to segment
    minDistSq = Math.min(minDistSq, segmentDistSq(px, py, ax, ay, bx, by));
  }

  return (inside ? 1 : -1) * Math.sqrt(minDistSq);
}

/** Squared distance from point (px,py) to line segment (ax,ay)-(bx,by). */
function segmentDistSq(px, py, ax, ay, bx, by) {
  let dx = bx - ax, dy = by - ay;
  if (dx !== 0 || dy !== 0) {
    const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)));
    ax += t * dx;
    ay += t * dy;
  }
  dx = px - ax;
  dy = py - ay;
  return dx * dx + dy * dy;
}

/** Simple centroid (average of vertices). */
function polygonCentroid(vertices) {
  if (!vertices || vertices.length < 2) return { x: 0, y: 0 };
  let sx = 0, sy = 0, n = 0;
  for (let i = 0; i < vertices.length; i += 2) {
    sx += vertices[i]; sy += vertices[i + 1]; n++;
  }
  return { x: Math.round(sx / n), y: Math.round(sy / n) };
}

// ─── Mob Area Name Generation ────────────────────────────────────────────────

/**
 * Generate a mob area name from selected mobs and their maturities.
 * Pattern: "Mob1 - Mat1/Mat2/Mat3, Mob2 - Mat1/Mat2"
 * Maturities are sorted by Health ascending.
 * @param {Array<{ mobName: string, maturities: Array<{ name: string, health: number }> }>} mobEntries
 */
export function generateMobAreaName(mobEntries) {
  if (!mobEntries?.length) return '';
  return mobEntries.map(entry => {
    const sortedMats = [...entry.maturities].sort((a, b) => (a.health || 0) - (b.health || 0));
    const matNames = sortedMats.map(m => m.name).join('/');
    return matNames ? `${entry.mobName} - ${matNames}` : entry.mobName;
  }).join(', ');
}

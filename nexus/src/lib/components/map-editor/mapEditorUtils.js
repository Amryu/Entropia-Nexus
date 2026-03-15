// @ts-nocheck
/**
 * Map Editor Utilities — coordinate transforms, type constants, colors.
 * Shared between admin map editor and public map edit mode.
 */

// ─── Location / Area Type Constants ───────────────────────────────────────────

export const LOCATION_TYPES = [
  'Teleporter', 'Npc', 'Interactable', 'Outpost', 'Camp', 'City',
  'RevivalPoint', 'InstanceEntrance', 'Vendor', 'Estate'
];

export const AREA_TYPES = [
  'MobArea', 'LandArea', 'WaveEventArea', 'PvpArea', 'PvpLootArea',
  'ZoneArea', 'CityArea', 'EstateArea', 'EventArea'
];

export const SHAPES = ['Circle', 'Rectangle', 'Polygon'];

export const DEFAULT_ALTITUDE = 100;

// ─── Type Colors (matches Map.svelte getColorByType) ─────────────────────────

export const TYPE_COLORS = {
  Teleporter:     '#00ffff',
  Npc:            '#ff69b4',
  Interactable:   '#dda0dd',
  Outpost:        '#87ceeb',
  Camp:           '#f0e68c',
  City:           '#90ee90',
  RevivalPoint:   '#98fb98',
  InstanceEntrance:'#b0c4de',
  Vendor:         '#ffa07a',
  Estate:         '#deb887',
  // Area types
  WaveEventArea:  '#da70d6',
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

/**
 * Project point (px,py) onto line segment (ax,ay)-(bx,by).
 * Returns the projection point, clamped parameter t ∈ [0,1], and squared distance.
 * @returns {{ projX: number, projY: number, t: number, distSq: number }}
 */
export function projectPointOnSegment(px, py, ax, ay, bx, by) {
  const edx = bx - ax, edy = by - ay;
  let t = 0;
  if (edx !== 0 || edy !== 0) {
    t = Math.max(0, Math.min(1, ((px - ax) * edx + (py - ay) * edy) / (edx * edx + edy * edy)));
  }
  const projX = ax + t * edx;
  const projY = ay + t * edy;
  const dx = px - projX, dy = py - projY;
  return { projX, projY, t, distSq: dx * dx + dy * dy };
}

/** Project point onto infinite line through A-B. Same as projectPointOnSegment but t is NOT clamped. */
export function projectPointOnLine(px, py, ax, ay, bx, by) {
  const edx = bx - ax, edy = by - ay;
  let t = 0;
  if (edx !== 0 || edy !== 0) {
    t = ((px - ax) * edx + (py - ay) * edy) / (edx * edx + edy * edy);
  }
  const projX = ax + t * edx;
  const projY = ay + t * edy;
  const dx = px - projX, dy = py - projY;
  return { projX, projY, t, distSq: dx * dx + dy * dy };
}

/** Squared distance from point (px,py) to line segment (ax,ay)-(bx,by). */
function segmentDistSq(px, py, ax, ay, bx, by) {
  return projectPointOnSegment(px, py, ax, ay, bx, by).distSq;
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

// ─── Snap Constants ─────────────────────────────────────────────────────────

export const SERVER_TILE_SIZE = 8192;
export const VERTEX_SNAP_THRESHOLD_PX = 10;
export const VERTEX_SNAP_THRESHOLD_MAX_EU = 100; // Max snap range for vertex editing
export const MIN_GRID_DISPLAY_PX = 50; // Minimum pixel spacing between displayed grid lines

/**
 * Compute the finest grid spacing (power of 2) that keeps lines ≥ MIN_GRID_DISPLAY_PX apart.
 * Returns a power of 2 from 1 to SERVER_TILE_SIZE.
 * @param {number} zoom — current map zoom level
 * @param {number} ratio — EU per image pixel (transforms.ratio)
 * @returns {number} grid spacing in Entropia units
 */
export function getGridSpacing(zoom, ratio) {
  const scale = Math.pow(2, zoom);
  const euPerPixel = ratio / scale;
  const minSpacing = euPerPixel * MIN_GRID_DISPLAY_PX;
  let spacing = 1;
  while (spacing < minSpacing) spacing *= 2;
  return Math.min(spacing, SERVER_TILE_SIZE);
}

// ─── Snap Utilities ─────────────────────────────────────────────────────────

/**
 * Get bounding box of a location's shape in Entropia coordinates.
 * Works with the location object directly (reads Properties.Shape + Properties.Data).
 * @param {object} loc — location object with Properties.Shape and Properties.Data
 * @returns {{ minX: number, maxX: number, minY: number, maxY: number } | null}
 */
export function getShapeBounds(loc) {
  const data = loc?.Properties?.Data;
  const shape = loc?.Properties?.Shape;
  if (!data || !shape) return null;

  if (shape === 'Circle') {
    const r = data.radius || 0;
    return { minX: data.x - r, maxX: data.x + r, minY: data.y - r, maxY: data.y + r };
  } else if (shape === 'Rectangle') {
    return { minX: data.x, maxX: data.x + data.width, minY: data.y, maxY: data.y + data.height };
  } else if (shape === 'Polygon' && data.vertices?.length >= 6) {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (let i = 0; i < data.vertices.length; i += 2) {
      const vx = data.vertices[i], vy = data.vertices[i + 1];
      if (vx < minX) minX = vx;
      if (vx > maxX) maxX = vx;
      if (vy < minY) minY = vy;
      if (vy > maxY) maxY = vy;
    }
    return { minX, maxX, minY, maxY };
  }
  return null;
}

/**
 * Get server tile border positions for a planet.
 * @param {object} planet — planet with Properties.Map.{X, Y, Width, Height}
 * @returns {{ xLines: number[], yLines: number[] }}
 */
export function getServerGridLines(planet) {
  const mapInfo = planet?.Properties?.Map;
  if (!mapInfo) return { xLines: [], yLines: [] };

  const offsetX = mapInfo.X * SERVER_TILE_SIZE;
  const offsetY = mapInfo.Y * SERVER_TILE_SIZE;
  const xLines = [];
  const yLines = [];

  for (let i = 0; i <= mapInfo.Width; i++) {
    xLines.push(offsetX + i * SERVER_TILE_SIZE);
  }
  for (let i = 0; i <= mapInfo.Height; i++) {
    yLines.push(offsetY + i * SERVER_TILE_SIZE);
  }

  return { xLines, yLines };
}

/**
 * Snap an angle to the nearest 22.5° increment (16 directions).
 * @param {number} angle — angle in radians
 * @returns {number} snapped angle in radians
 */
export function snapAngleToDirection(angle) {
  const step = Math.PI / 8; // 22.5°
  return Math.round(angle / step) * step;
}

// ─── Vertex Snap Utilities ───────────────────────────────────────────────────

/**
 * Extract vertices in Entropia coordinates from a location's shape.
 * @param {object} loc — location object with Properties.Shape and Properties.Data
 * @returns {Array<{ x: number, y: number }>}
 */
/**
 * Parse raw vertices from a location's shape data.
 * Strips duplicate closing vertex from polygons (first == last).
 */
function parseShapeVertices(loc) {
  const data = loc?.Properties?.Data;
  const shape = loc?.Properties?.Shape;
  if (!data || !shape) return [];

  if (shape === 'Rectangle') {
    return [
      { x: data.x, y: data.y },
      { x: data.x + data.width, y: data.y },
      { x: data.x + data.width, y: data.y + data.height },
      { x: data.x, y: data.y + data.height },
    ];
  } else if (shape === 'Polygon' && data.vertices?.length >= 6) {
    const rawVerts = [];
    for (let i = 0; i < data.vertices.length; i += 2) {
      rawVerts.push({ x: data.vertices[i], y: data.vertices[i + 1] });
    }
    // Strip duplicate closing vertex (polygon ring: first == last)
    if (rawVerts.length > 1) {
      const first = rawVerts[0], last = rawVerts[rawVerts.length - 1];
      if (first.x === last.x && first.y === last.y) rawVerts.pop();
    }
    return rawVerts;
  }
  return [];
}

export function getShapeVertices(loc) {
  const rawVerts = parseShapeVertices(loc);
  if (rawVerts.length === 0) return [];

  // Include neighbor vertices for bisector computation at each corner
  const n = rawVerts.length;
  return rawVerts.map((v, i) => ({
    x: v.x, y: v.y,
    prevX: rawVerts[(i - 1 + n) % n].x, prevY: rawVerts[(i - 1 + n) % n].y,
    nextX: rawVerts[(i + 1) % n].x,     nextY: rawVerts[(i + 1) % n].y,
  }));
}

/**
 * Extract edges (line segments) from a location's shape.
 * @param {object} loc — location object with Properties.Shape and Properties.Data
 * @returns {Array<{ ax: number, ay: number, bx: number, by: number }>}
 */
export function getShapeEdges(loc) {
  const rawVerts = parseShapeVertices(loc);
  if (rawVerts.length < 2) return [];

  const edges = [];
  for (let i = 0; i < rawVerts.length; i++) {
    const a = rawVerts[i];
    const b = rawVerts[(i + 1) % rawVerts.length];
    edges.push({ ax: a.x, ay: a.y, bx: b.x, by: b.y });
  }
  return edges;
}

/**
 * Compute snap offset for a single vertex against candidate edges (as infinite construction lines),
 * grid lines, and angle bisectors. All phases compete on 2D displacement — smallest wins.
 * @param {number} vx — vertex X in Entropia coords
 * @param {number} vy — vertex Y in Entropia coords
 * @param {Array<{ x: number, y: number, prevX?: number, prevY?: number, nextX?: number, nextY?: number }>} candidateVertices — vertices from same-type areas (used for bisector)
 * @param {{ xLines: number[], yLines: number[] } | null} gridLines — server grid
 * @param {number} gap — desired gap (Entropia units)
 * @param {number} threshold — max snap distance (Entropia units)
 * @param {Array<{ ax: number, ay: number, bx: number, by: number }>} candidateEdges — edges from same-type areas
 * @returns {{ dx: number, dy: number, guideX: number|null, guideY: number|null, bisector: object|null, edge: object|null, gap: number }}
 */
export function computeVertexSnap(vx, vy, candidateVertices, gridLines, gap, threshold, candidateEdges = []) {
  let bestDx = 0, bestDy = 0;
  let bestDisp = Infinity;
  let guideX = null, guideY = null;
  let bisector = null;
  let edge = null;
  const proximity = threshold * 2;
  const proximitySq = proximity * proximity;
  const EPS = 0.001; // endpoint skip epsilon for t values

  // --- Phase 1: Grid snap (per-axis, optional) ---
  let bestAbsDx = threshold + 1, bestAbsDy = threshold + 1;
  if (gridLines) {
    for (const gx of gridLines.xLines) {
      const dx = gx - vx;
      const adx = Math.abs(dx);
      if (adx <= threshold && adx < bestAbsDx) {
        bestAbsDx = adx; guideX = gx;
      }
    }
    for (const gy of gridLines.yLines) {
      const dy = gy - vy;
      const ady = Math.abs(dy);
      if (ady <= threshold && ady < bestAbsDy) {
        bestAbsDy = ady; guideY = gy;
      }
    }
    // Compute grid snap displacement
    const gridDx = bestAbsDx <= threshold ? (guideX - vx) : 0;
    const gridDy = bestAbsDy <= threshold ? (guideY - vy) : 0;
    if (bestAbsDx <= threshold || bestAbsDy <= threshold) {
      const gridDisp = Math.sqrt(gridDx * gridDx + gridDy * gridDy);
      bestDx = gridDx;
      bestDy = gridDy;
      bestDisp = gridDisp;
    }
  }

  // --- Phase 2a: Bounded edge snap (sliding along segment, t clamped [0,1]) ---
  for (const e of candidateEdges) {
    // Compute edge length early (needed for dead zone)
    const edx = e.bx - e.ax, edy = e.by - e.ay;
    const eLen = Math.sqrt(edx * edx + edy * edy);
    if (eLen < 1) continue;

    // Proximity filter: skip if midpoint of edge is far from vertex
    const midX = (e.ax + e.bx) / 2, midY = (e.ay + e.by) / 2;
    const midDist = Math.sqrt((midX - vx) ** 2 + (midY - vy) ** 2);
    if (midDist > eLen / 2 + proximity) continue;

    const proj = projectPointOnSegment(vx, vy, e.ax, e.ay, e.bx, e.by);
    // Dead zone at endpoints — proportional to threshold/edgeLength; bisector handles corners
    const endpointEps = threshold / eLen;
    if (proj.t <= endpointEps || proj.t >= 1 - endpointEps) continue;

    const perpDist = Math.sqrt(proj.distSq);
    if (perpDist > threshold) continue;

    // Edge normal (perpendicular, pointing toward vertex)
    let nx = -edy / eLen, ny = edx / eLen;
    const dotToVertex = (vx - e.ax) * nx + (vy - e.ay) * ny;
    if (dotToVertex < 0) { nx = -nx; ny = -ny; }

    // Gap-offset edge snap: project onto parallel bounded segment at gap distance
    if (gap > 0) {
      const offsetAx = e.ax + nx * gap, offsetAy = e.ay + ny * gap;
      const offsetBx = e.bx + nx * gap, offsetBy = e.by + ny * gap;
      const gapProj = projectPointOnSegment(vx, vy, offsetAx, offsetAy, offsetBx, offsetBy);
      if (gapProj.t > endpointEps && gapProj.t < 1 - endpointEps) {
        const gapDx = gapProj.projX - vx, gapDy = gapProj.projY - vy;
        const gapDisp = Math.sqrt(gapDx * gapDx + gapDy * gapDy);
        if (gapDisp <= threshold && gapDisp < bestDisp) {
          bestDx = gapDx; bestDy = gapDy; bestDisp = gapDisp;
          bisector = null; guideX = null; guideY = null;
          edge = { ax: e.ax, ay: e.ay, bx: e.bx, by: e.by, projX: gapProj.projX, projY: gapProj.projY, isGap: true, isExtension: false };
          continue;
        }
      }
    }

    // Direct edge snap (no gap)
    const snapDx = proj.projX - vx, snapDy = proj.projY - vy;
    const snapDisp = Math.sqrt(snapDx * snapDx + snapDy * snapDy);
    if (snapDisp <= threshold && snapDisp < bestDisp) {
      bestDx = snapDx; bestDy = snapDy; bestDisp = snapDisp;
      bisector = null; guideX = null; guideY = null;
      edge = { ax: e.ax, ay: e.ay, bx: e.bx, by: e.by, projX: proj.projX, projY: proj.projY, isGap: false, isExtension: false };
    }
  }

  // --- Phase 2b: Extension magnetic snap points (gap distance from endpoints) ---
  if (gap > 0) {
    for (const e of candidateEdges) {
      const edx = e.bx - e.ax, edy = e.by - e.ay;
      const eLen = Math.sqrt(edx * edx + edy * edy);
      if (eLen < 1) continue;
      const udx = edx / eLen, udy = edy / eLen;

      // 2 magnetic points on direct line extension (gap distance from each endpoint)
      const magneticPoints = [
        { x: e.ax - gap * udx, y: e.ay - gap * udy },
        { x: e.bx + gap * udx, y: e.by + gap * udy },
      ];

      for (const mp of magneticPoints) {
        const mpDx = mp.x - vx, mpDy = mp.y - vy;
        const mpDisp = Math.sqrt(mpDx * mpDx + mpDy * mpDy);
        if (mpDisp <= threshold && mpDisp < bestDisp) {
          bestDx = mpDx; bestDy = mpDy; bestDisp = mpDisp;
          bisector = null; guideX = null; guideY = null;
          edge = { ax: e.ax, ay: e.ay, bx: e.bx, by: e.by, projX: mp.x, projY: mp.y, isGap: false, isExtension: true };
        }
      }
    }
  }

  // --- Phase 3: Bisector snap (angle bisector of corner vertices) ---
  for (const cv of candidateVertices) {
    if (cv.prevX === undefined || cv.nextX === undefined) continue;

    // Proximity filter
    const pdx = cv.x - vx, pdy = cv.y - vy;
    if (pdx * pdx + pdy * pdy > proximitySq) continue;

    // Edge directions from corner vertex
    const e1x = cv.prevX - cv.x, e1y = cv.prevY - cv.y;
    const e2x = cv.nextX - cv.x, e2y = cv.nextY - cv.y;
    const len1 = Math.sqrt(e1x * e1x + e1y * e1y);
    const len2 = Math.sqrt(e2x * e2x + e2y * e2y);
    if (len1 < 1 || len2 < 1) continue;

    // Bisector direction = normalize(normalize(e1) + normalize(e2))
    const bx = e1x / len1 + e2x / len2;
    const by = e1y / len1 + e2y / len2;
    const bLen = Math.sqrt(bx * bx + by * by);
    if (bLen < 0.01) continue; // nearly 180° angle

    const bdx = bx / bLen, bdy = by / bLen;

    // Project vertex onto bisector line through cv
    const vRelX = vx - cv.x, vRelY = vy - cv.y;
    const t = vRelX * bdx + vRelY * bdy;
    const projX = cv.x + t * bdx;
    const projY = cv.y + t * bdy;
    const perpDx = vx - projX, perpDy = vy - projY;
    const perpDist = Math.sqrt(perpDx * perpDx + perpDy * perpDy);

    if (perpDist > threshold) continue;

    // Bisector gap snap: snap to distance=gap from corner along bisector
    if (gap > 0) {
      const tSign = t >= 0 ? 1 : -1;
      const gapProjX = cv.x + tSign * gap * bdx;
      const gapProjY = cv.y + tSign * gap * bdy;
      const gapSnapDx = gapProjX - vx, gapSnapDy = gapProjY - vy;
      const gapTotalDisp = Math.sqrt(gapSnapDx * gapSnapDx + gapSnapDy * gapSnapDy);
      if (gapTotalDisp <= threshold && gapTotalDisp < bestDisp) {
        bestDx = gapSnapDx; bestDy = gapSnapDy; bestDisp = gapTotalDisp;
        edge = null; guideX = null; guideY = null;
        bisector = { cx: cv.x, cy: cv.y, dirX: bdx, dirY: bdy };
        continue;
      }
    }

    const snapDx = projX - vx, snapDy = projY - vy;
    const totalDisp = Math.sqrt(snapDx * snapDx + snapDy * snapDy);
    if (totalDisp < bestDisp) {
      bestDx = snapDx; bestDy = snapDy; bestDisp = totalDisp;
      edge = null; guideX = null; guideY = null;
      bisector = { cx: cv.x, cy: cv.y, dirX: bdx, dirY: bdy };
    }
  }

  return { dx: bestDx, dy: bestDy, guideX, guideY, bisector, edge, gap };
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

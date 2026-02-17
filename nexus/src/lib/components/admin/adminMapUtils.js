// @ts-nocheck
/**
 * Admin Map Utilities — coordinate transforms, SQL generation, constants.
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

// ─── SQL Generation ──────────────────────────────────────────────────────────

function escSql(v) {
  if (v === null || v === undefined) return 'NULL';
  return `'${String(v).replace(/'/g, "''")}'`;
}

function escJsonb(obj) {
  return `'${JSON.stringify(obj).replace(/'/g, "''")}'::jsonb`;
}

/**
 * Generate DELETE SQL for a location (cascade through extension tables).
 */
export function generateDeleteSql(locationId) {
  const id = Number(locationId);
  return [
    `-- Delete location ${id} and all related data`,
    `DELETE FROM ONLY "MobSpawnMaturities" WHERE "LocationId" = ${id};`,
    `DELETE FROM ONLY "MobSpawns" WHERE "LocationId" = ${id};`,
    `DELETE FROM ONLY "LandAreas" WHERE "LocationId" = ${id};`,
    `DELETE FROM ONLY "LandAreaMinerals" WHERE "LocationId" = ${id};`,
    `DELETE FROM ONLY "Areas" WHERE "LocationId" = ${id};`,
    `DELETE FROM ONLY "LocationFacilities" WHERE "LocationId" = ${id};`,
    `DELETE FROM ONLY "EstateSections" WHERE "LocationId" = ${id};`,
    `DELETE FROM ONLY "Estates" WHERE "LocationId" = ${id};`,
    `DELETE FROM ONLY "WaveEventWaves" WHERE "LocationId" = ${id};`,
    `DELETE FROM ONLY "Locations" WHERE "Id" = ${id};`,
    ''
  ].join('\n');
}

/**
 * Generate INSERT SQL for a new location (+ optional area + mob spawn data).
 * Uses DO $$ block with a variable for the new ID.
 */
export function generateInsertSql(location, planetId) {
  const lines = [];
  const name = escSql(location.name);
  const type = escSql(location.locationType || 'Area');
  const lon = location.longitude ?? 'NULL';
  const lat = location.latitude ?? 'NULL';
  const alt = location.altitude ?? 'NULL';

  lines.push(`-- Insert new location: ${location.name}`);
  lines.push(`DO $$`);
  lines.push(`DECLARE new_id INTEGER;`);
  lines.push(`BEGIN`);
  lines.push(`  INSERT INTO ONLY "Locations" ("Name", "Type", "PlanetId", "Longitude", "Latitude", "Altitude")`);
  lines.push(`  VALUES (${name}, ${type}, ${planetId}, ${lon}, ${lat}, ${alt})`);
  lines.push(`  RETURNING "Id" INTO new_id;`);

  // Area insert
  if (location.areaType && location.shape && location.shapeData) {
    const areaType = escSql(location.areaType);
    const shape = escSql(location.shape);
    const data = escJsonb(location.shapeData);
    lines.push('');
    lines.push(`  INSERT INTO ONLY "Areas" ("LocationId", "Type", "Shape", "Data")`);
    lines.push(`  VALUES (new_id, ${areaType}, ${shape}, ${data});`);
  }

  // MobSpawn insert
  if (location.areaType === 'MobArea' && location.mobData) {
    const density = location.mobData.density ?? 3;
    lines.push('');
    lines.push(`  INSERT INTO ONLY "MobSpawns" ("LocationId", "Density")`);
    lines.push(`  VALUES (new_id, ${density});`);

    if (location.mobData.maturities?.length) {
      lines.push('');
      for (const mat of location.mobData.maturities) {
        const isRare = mat.isRare ? 1 : 0;
        lines.push(`  INSERT INTO ONLY "MobSpawnMaturities" ("LocationId", "MaturityId", "IsRare")`);
        lines.push(`  VALUES (new_id, ${mat.maturityId}, ${isRare});`);
      }
    }
  }

  lines.push(`END $$;`);
  lines.push('');
  return lines.join('\n');
}

/**
 * Generate UPDATE SQL for an existing location.
 * Only includes changed fields.
 */
export function generateUpdateSql(original, modified) {
  const id = original.Id;
  const lines = [];

  // Location table updates
  const locSets = [];
  if (modified.name !== undefined && modified.name !== original.Name) {
    locSets.push(`"Name" = ${escSql(modified.name)}`);
  }
  if (modified.longitude !== undefined && modified.longitude !== original.Properties?.Coordinates?.Longitude) {
    locSets.push(`"Longitude" = ${modified.longitude}`);
  }
  if (modified.latitude !== undefined && modified.latitude !== original.Properties?.Coordinates?.Latitude) {
    locSets.push(`"Latitude" = ${modified.latitude}`);
  }
  if (modified.altitude !== undefined && modified.altitude !== original.Properties?.Coordinates?.Altitude) {
    locSets.push(`"Altitude" = ${modified.altitude}`);
  }

  if (locSets.length) {
    lines.push(`-- Update location ${id}: ${original.Name}`);
    lines.push(`UPDATE ONLY "Locations" SET ${locSets.join(', ')} WHERE "Id" = ${id};`);
  }

  // Area table updates
  if (modified.areaType || modified.shape || modified.shapeData) {
    const areaSets = [];
    if (modified.areaType) areaSets.push(`"Type" = ${escSql(modified.areaType)}`);
    if (modified.shape) areaSets.push(`"Shape" = ${escSql(modified.shape)}`);
    if (modified.shapeData) areaSets.push(`"Data" = ${escJsonb(modified.shapeData)}`);
    if (areaSets.length) {
      lines.push(`UPDATE ONLY "Areas" SET ${areaSets.join(', ')} WHERE "LocationId" = ${id};`);
    }
  }

  // MobSpawn updates (replace strategy: delete old, insert new)
  if (modified.mobData) {
    lines.push('');
    lines.push(`-- Replace mob spawn data for location ${id}`);
    lines.push(`DELETE FROM ONLY "MobSpawnMaturities" WHERE "LocationId" = ${id};`);
    lines.push(`DELETE FROM ONLY "MobSpawns" WHERE "LocationId" = ${id};`);
    const density = modified.mobData.density ?? 3;
    lines.push(`INSERT INTO ONLY "MobSpawns" ("LocationId", "Density") VALUES (${id}, ${density});`);
    if (modified.mobData.maturities?.length) {
      for (const mat of modified.mobData.maturities) {
        const isRare = mat.isRare ? 1 : 0;
        lines.push(`INSERT INTO ONLY "MobSpawnMaturities" ("LocationId", "MaturityId", "IsRare") VALUES (${id}, ${mat.maturityId}, ${isRare});`);
      }
    }
  }

  if (lines.length) lines.push('');
  return lines.join('\n');
}

/**
 * Generate all SQL from pending changes map.
 * @param {Map} pendingChanges — Map of id → { action, original, modified }
 * @param {number} planetId
 * @returns {string} Combined SQL
 */
export function generateAllSql(pendingChanges, planetId) {
  const deletes = [];
  const inserts = [];
  const updates = [];

  for (const [, change] of pendingChanges) {
    if (change.action === 'delete') {
      deletes.push(generateDeleteSql(change.original.Id));
    } else if (change.action === 'add') {
      inserts.push(generateInsertSql(change.modified, planetId));
    } else if (change.action === 'edit') {
      updates.push(generateUpdateSql(change.original, change.modified));
    }
  }

  const sections = [];
  if (deletes.length) {
    sections.push(`-- ═══════════════════════════════════════\n-- DELETES (${deletes.length})\n-- ═══════════════════════════════════════\n\n${deletes.join('\n')}`);
  }
  if (inserts.length) {
    sections.push(`-- ═══════════════════════════════════════\n-- INSERTS (${inserts.length})\n-- ═══════════════════════════════════════\n\n${inserts.join('\n')}`);
  }
  if (updates.length) {
    sections.push(`-- ═══════════════════════════════════════\n-- UPDATES (${updates.length})\n-- ═══════════════════════════════════════\n\n${updates.join('\n')}`);
  }

  return sections.join('\n\n') || '-- No pending changes';
}

// @ts-nocheck
/**
 * Admin Map Utilities — re-exports shared utilities + SQL generation.
 */

// Re-export all shared constants and functions
export {
  LOCATION_TYPES,
  AREA_TYPES,
  SHAPES,
  TYPE_COLORS,
  getTypeColor,
  getEffectiveType,
  isArea,
  buildCoordTransforms,
  generateMobAreaName
} from '../map-editor/mapEditorUtils.js';

// ─── SQL Generation (admin-only) ────────────────────────────────────────────

function escSql(v) {
  if (v === null || v === undefined) return 'NULL';
  return `'${String(v).replace(/'/g, "''")}'`;
}

function escJsonb(obj) {
  return `'${JSON.stringify(obj).replace(/'/g, "''")}'::jsonb`;
}

/**
 * Ensure polygon vertices form a closed ring (first vertex = last vertex).
 * PostGIS requires closed rings for ST_MakePolygon.
 */
function closePolygon(shapeData) {
  if (!shapeData?.vertices || shapeData.vertices.length < 6) return shapeData;
  const v = shapeData.vertices;
  if (v[0] !== v[v.length - 2] || v[1] !== v[v.length - 1]) {
    return { ...shapeData, vertices: [...v, v[0], v[1]] };
  }
  return shapeData;
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
  lines.push(`  INSERT INTO "Locations" ("Name", "Type", "PlanetId", "Longitude", "Latitude", "Altitude")`);
  lines.push(`  VALUES (${name}, ${type}, ${planetId}, ${lon}, ${lat}, ${alt})`);
  lines.push(`  RETURNING "Id" INTO new_id;`);

  // Area insert
  if (location.areaType && location.shape && location.shapeData) {
    const areaType = escSql(location.areaType);
    const shape = escSql(location.shape);
    const shapeData = location.shape === 'Polygon' ? closePolygon(location.shapeData) : location.shapeData;
    const data = escJsonb(shapeData);
    lines.push('');
    lines.push(`  INSERT INTO "Areas" ("LocationId", "Type", "Shape", "Data")`);
    lines.push(`  VALUES (new_id, ${areaType}, ${shape}, ${data});`);
  }

  // MobSpawn insert
  if (location.areaType === 'MobArea' && location.mobData) {
    const density = location.mobData.density ?? 3;
    lines.push('');
    lines.push(`  INSERT INTO "MobSpawns" ("LocationId", "Density")`);
    lines.push(`  VALUES (new_id, ${density});`);

    if (location.mobData.maturities?.length) {
      lines.push('');
      for (const mat of location.mobData.maturities) {
        const isRare = mat.isRare ? 1 : 0;
        lines.push(`  INSERT INTO "MobSpawnMaturities" ("LocationId", "MaturityId", "IsRare")`);
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
    if (modified.shapeData) {
      const effectiveShape = modified.shape || original.Properties?.Shape;
      const sd = effectiveShape === 'Polygon' ? closePolygon(modified.shapeData) : modified.shapeData;
      areaSets.push(`"Data" = ${escJsonb(sd)}`);
    }
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
    lines.push(`INSERT INTO "MobSpawns" ("LocationId", "Density") VALUES (${id}, ${density});`);
    if (modified.mobData.maturities?.length) {
      for (const mat of modified.mobData.maturities) {
        const isRare = mat.isRare ? 1 : 0;
        lines.push(`INSERT INTO "MobSpawnMaturities" ("LocationId", "MaturityId", "IsRare") VALUES (${id}, ${mat.maturityId}, ${isRare});`);
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

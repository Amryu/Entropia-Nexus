/**
 * Audit Endpoint API
 *
 * Provides access to historical versions of entities from audit tables.
 * Reuses the queries and formatters from existing endpoints to ensure
 * consistent data formatting.
 *
 * ## Timestamp Matching Strategy
 * For joined/related data, uses this priority:
 * 1. Find record at exact same timestamp as main record
 * 2. Find most recent record BEFORE the main record's timestamp
 * 3. If no record before, use the earliest available record
 *
 * ## Usage
 * - GET /audit/types - List all supported entity types
 * - GET /audit/:entityType/:entityId - Get full audit history
 * - GET /audit/:entityType/:entityId/original - Get original version
 * - GET /audit/:entityType/:entityId/at?timestamp=... - Get version at/before timestamp
 */

const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');

// Import formatters from existing endpoints
const { formatWeapon } = require('./weapons');
const { formatMob, ensureInvestigatorCache } = require('./mobs');
const { formatMaterial } = require('./materials');
const { formatRefiner } = require('./refiners');
const { formatScanner } = require('./scanners');
const { formatFinder } = require('./finders');
const { formatExcavator } = require('./excavators');
const { formatAbsorber } = require('./absorbers');
const { formatFinderAmplifier } = require('./finderamplifiers');
const { formatArmorPlating } = require('./armorplatings');
const { formatDecoration } = require('./decorations');
const { formatFurniture } = require('./furniture');
const { formatStorageContainer } = require('./storagecontainers');
const { formatSign } = require('./signs');
const { formatMiscTool } = require('./misctools');
const { formatTeleportationChip } = require('./teleportationchips');
const { formatEffectChip } = require('./effectchips');
const { formatWeaponAmplifier } = require('./weaponamplifiers');
const { formatWeaponVisionAttachment } = require('./weaponvisionattachments');
const { formatMindforceImplant } = require('./mindforce');
const { formatCapsule } = require('./capsules');
const { formatVehicle } = require('./vehicles');
const { formatClothing } = require('./clothings');
const { formatMedicalTool } = require('./medicaltools');
const { formatMedicalChip } = require('./medicalchips');
// Note: formatPet, formatConsumable, formatBlueprint, formatVendor, formatArmorSetsResponse
// are not imported because they need specialized related data loaders not yet implemented in audit

// ============================================================================
// ENTITY TYPE CONFIGURATION
// Maps entity types to their table names and configurations
// ============================================================================

const entityConfigs = {
  Weapon: {
    mainTable: 'Weapons',
    idOffsetKey: 'Weapons',
    // Lookup tables that are joined in the main query
    lookupJoins: [
      { table: 'VehicleAttachmentTypes', localKey: 'AttachmentTypeId', foreignKey: 'Id', as: 'AttachmentType', selectFields: ['"Name"'] },
      { table: 'Materials', localKey: 'AmmoId', foreignKey: 'Id', as: 'Ammo', selectFields: ['"Name"'] },
      { table: 'Professions', localKey: 'ProfessionHitId', foreignKey: 'Id', as: 'ProfessionHit', selectFields: ['"Name"'] },
      { table: 'Professions', localKey: 'ProfessionDmgId', foreignKey: 'Id', as: 'ProfessionDmg', selectFields: ['"Name"'] },
    ],
    // Related data that needs separate queries (effects, tiers)
    relatedData: ['EffectsOnEquip', 'EffectsOnUse', 'Tiers'],
  },
  ArmorSet: {
    mainTable: 'ArmorSets',
    idOffsetKey: 'ArmorSets',
    lookupJoins: [
      { table: 'Professions', localKey: 'DefensiveProfessionId', foreignKey: 'Id', as: 'DefensiveProfession', selectFields: ['"Name"'] },
    ],
    relatedData: ['EffectsOnEquip', 'Tiers'],
  },
  Material: {
    mainTable: 'Materials',
    idOffsetKey: 'Materials',
    lookupJoins: [],
    relatedData: [],
  },
  MedicalTool: {
    mainTable: 'MedicalTools',
    idOffsetKey: 'MedicalTools',
    lookupJoins: [
      { table: 'Professions', localKey: 'ProfessionId', foreignKey: 'Id', as: 'Profession', selectFields: ['"Name"'] },
    ],
    relatedData: ['EffectsOnEquip', 'EffectsOnUse'],
  },
  MedicalChip: {
    mainTable: 'MedicalChips',
    idOffsetKey: 'MedicalChips',
    lookupJoins: [
      { table: 'Professions', localKey: 'ProfessionId', foreignKey: 'Id', as: 'Profession', selectFields: ['"Name"'] },
    ],
    relatedData: ['EffectsOnEquip', 'EffectsOnUse'],
  },
  Refiner: { mainTable: 'Refiners', idOffsetKey: 'Refiners', lookupJoins: [], relatedData: [] },
  Scanner: {
    mainTable: 'Scanners',
    idOffsetKey: 'Scanners',
    lookupJoins: [
      { table: 'Professions', localKey: 'ProfessionId', foreignKey: 'Id', as: 'ScanningProfession', selectFields: ['"Name"'] },
    ],
    relatedData: [],
  },
  Finder: { mainTable: 'Finders', idOffsetKey: 'Finders', lookupJoins: [], relatedData: [] },
  Excavator: { mainTable: 'Excavators', idOffsetKey: 'Excavators', lookupJoins: [], relatedData: [] },
  TeleportChip: { mainTable: 'TeleportationChips', idOffsetKey: 'TeleportationChips', lookupJoins: [], relatedData: [] },
  EffectChip: { mainTable: 'EffectChips', idOffsetKey: 'EffectChips', lookupJoins: [], relatedData: [] },
  MiscTool: { mainTable: 'MiscTools', idOffsetKey: 'MiscTools', lookupJoins: [], relatedData: [] },
  WeaponAmplifier: { mainTable: 'WeaponAmplifiers', idOffsetKey: 'WeaponAmplifiers', lookupJoins: [], relatedData: [] },
  WeaponVisionAttachment: { mainTable: 'WeaponVisionAttachments', idOffsetKey: 'WeaponVisionAttachments', lookupJoins: [], relatedData: [] },
  Absorber: { mainTable: 'Absorbers', idOffsetKey: 'Absorbers', lookupJoins: [], relatedData: [] },
  FinderAmplifier: { mainTable: 'FinderAmplifiers', idOffsetKey: 'FinderAmplifiers', lookupJoins: [], relatedData: [] },
  ArmorPlating: { mainTable: 'ArmorPlatings', idOffsetKey: 'ArmorPlatings', lookupJoins: [], relatedData: [] },
  MindforceImplant: { mainTable: 'MindforceImplants', idOffsetKey: 'MindforceImplants', lookupJoins: [], relatedData: [] },
  Blueprint: { mainTable: 'Blueprints', idOffsetKey: 'Blueprints', lookupJoins: [], relatedData: ['BlueprintMaterials'] },
  Pet: { mainTable: 'Pets', idOffsetKey: 'Pets', lookupJoins: [], relatedData: ['PetEffects'] },
  Mob: {
    mainTable: 'Mobs',
    idOffsetKey: null,
    lookupJoins: [
      { table: 'MobSpecies', localKey: 'SpeciesId', foreignKey: 'Id', as: 'Species', selectFields: ['"Name"'] },
      { table: 'Professions', localKey: 'DefensiveProfessionId', foreignKey: 'Id', as: 'DefensiveProfession', selectFields: ['"Name"'] },
      { table: 'Planets', localKey: 'PlanetId', foreignKey: 'Id', as: 'Planet', selectFields: ['"Name"'] },
    ],
    relatedData: ['MobLoots', 'MobMaturities'],
  },
  Consumable: { mainTable: 'Consumables', idOffsetKey: 'Consumables', lookupJoins: [], relatedData: ['EffectsOnConsume'] },
  CreatureControlCapsule: { mainTable: 'CreatureControlCapsules', idOffsetKey: 'CreatureControlCapsules', lookupJoins: [], relatedData: [] },
  Vehicle: { mainTable: 'Vehicles', idOffsetKey: 'Vehicles', lookupJoins: [], relatedData: [] },
  Furniture: { mainTable: 'Furniture', idOffsetKey: 'Furniture', lookupJoins: [], relatedData: [] },
  Decoration: { mainTable: 'Decorations', idOffsetKey: 'Decorations', lookupJoins: [], relatedData: [] },
  StorageContainer: { mainTable: 'StorageContainers', idOffsetKey: 'StorageContainers', lookupJoins: [], relatedData: [] },
  Sign: { mainTable: 'Signs', idOffsetKey: 'Signs', lookupJoins: [], relatedData: [] },
  Clothing: { mainTable: 'Clothes', idOffsetKey: 'Clothes', lookupJoins: [], relatedData: ['EffectsOnEquip'] },
  Vendor: { mainTable: 'Vendors', idOffsetKey: null, lookupJoins: [], relatedData: ['VendorOffers'] },
};

const validEntityTypes = Object.keys(entityConfigs);

// ============================================================================
// QUERY BUILDING
// Builds audit queries with timestamp-aware LATERAL joins
// ============================================================================

/**
 * Build an audit query with timestamp-aware LATERAL joins for lookups
 *
 * @param {Object} config - Entity configuration
 * @param {number} entityId - The entity ID
 * @param {string} timestampCondition - SQL condition for timestamp ('stamp = $2' or 'stamp <= $2')
 * @param {string} orderDir - 'ASC' for original, 'DESC' for latest
 * @returns {string} SQL query
 */
function buildAuditQuery(config, timestampCondition = null, orderDir = 'DESC') {
  const mainTable = `"${config.mainTable}_audit"`;
  const mainAlias = 'main';

  // Build SELECT clause
  let selectParts = [`${mainAlias}.*`];

  // Build LATERAL joins for lookups
  let joinParts = [];
  let joinIndex = 0;

  for (const join of config.lookupJoins) {
    const joinAlias = `j${joinIndex}`;
    const auditTable = `"${join.table}_audit"`;

    // Select the fields we need from this join
    for (const field of join.selectFields) {
      selectParts.push(`${joinAlias}.${field} AS "${join.as}"`);
    }

    // Build LATERAL subquery to find the right audit version
    // Priority: exact timestamp match > before timestamp > earliest after
    joinParts.push(`
      LEFT JOIN LATERAL (
        SELECT ${join.selectFields.join(', ')}
        FROM ${auditTable}
        WHERE "${join.foreignKey}" = ${mainAlias}."${join.localKey}"
          AND (
            stamp = ${mainAlias}.stamp
            OR stamp < ${mainAlias}.stamp
            OR stamp > ${mainAlias}.stamp
          )
        ORDER BY
          CASE WHEN stamp = ${mainAlias}.stamp THEN 0
               WHEN stamp < ${mainAlias}.stamp THEN 1
               ELSE 2 END,
          CASE WHEN stamp <= ${mainAlias}.stamp THEN stamp END DESC NULLS LAST,
          stamp ASC
        LIMIT 1
      ) ${joinAlias} ON true
    `);

    joinIndex++;
  }

  // Build WHERE clause
  let whereParts = [`${mainAlias}."Id" = $1`];
  if (timestampCondition) {
    whereParts.push(`${mainAlias}.${timestampCondition}`);
  }

  // Build full query
  const query = `
    SELECT ${selectParts.join(', ')}
    FROM ${mainTable} ${mainAlias}
    ${joinParts.join('\n')}
    WHERE ${whereParts.join(' AND ')}
    ORDER BY ${mainAlias}.stamp ${orderDir}
  `;

  return query;
}

// ============================================================================
// RELATED DATA LOADERS (Audit-aware)
// ============================================================================

/**
 * Load EffectsOnEquip from audit tables at a specific timestamp
 */
async function loadEffectsOnEquipAudit(itemId, timestamp) {
  const query = `
    SELECT e."Name", eo."Strength", e."Unit", e."Description", e."Id"
    FROM "EffectsOnEquip_audit" eo
    LEFT JOIN LATERAL (
      SELECT "Id", "Name", "Unit", "Description"
      FROM "Effects_audit"
      WHERE "Id" = eo."EffectId"
        AND (stamp = eo.stamp OR stamp < eo.stamp OR stamp > eo.stamp)
      ORDER BY
        CASE WHEN stamp = eo.stamp THEN 0
             WHEN stamp < eo.stamp THEN 1
             ELSE 2 END,
        CASE WHEN stamp <= eo.stamp THEN stamp END DESC NULLS LAST,
        stamp ASC
      LIMIT 1
    ) e ON true
    WHERE eo."ItemId" = $1
      AND (eo.stamp = $2 OR eo.stamp < $2 OR eo.stamp > $2)
    ORDER BY
      CASE WHEN eo.stamp = $2 THEN 0
           WHEN eo.stamp < $2 THEN 1
           ELSE 2 END,
      CASE WHEN eo.stamp <= $2 THEN eo.stamp END DESC NULLS LAST
  `;

  try {
    const { rows } = await pool.query(query, [itemId, timestamp]);
    // Deduplicate by effect name (take the first/best match for each)
    const seen = new Set();
    return rows.filter(r => {
      if (seen.has(r.Name)) return false;
      seen.add(r.Name);
      return true;
    }).map(r => ({
      Name: r.Name,
      Values: {
        Strength: r.Strength != null ? Number(r.Strength) : null,
        Unit: r.Unit,
        Description: r.Description,
      },
      Links: { "$Url": `/effects/${r.Id}` },
    }));
  } catch (err) {
    console.warn('[audit] Failed to load EffectsOnEquip:', err.message);
    return [];
  }
}

/**
 * Load EffectsOnUse from audit tables at a specific timestamp
 */
async function loadEffectsOnUseAudit(itemId, timestamp) {
  const query = `
    SELECT e."Name", eu."Strength", eu."DurationSeconds", e."Unit", e."Description", e."Id"
    FROM "EffectsOnUse_audit" eu
    LEFT JOIN LATERAL (
      SELECT "Id", "Name", "Unit", "Description"
      FROM "Effects_audit"
      WHERE "Id" = eu."EffectId"
        AND (stamp = eu.stamp OR stamp < eu.stamp OR stamp > eu.stamp)
      ORDER BY
        CASE WHEN stamp = eu.stamp THEN 0
             WHEN stamp < eu.stamp THEN 1
             ELSE 2 END,
        CASE WHEN stamp <= eu.stamp THEN stamp END DESC NULLS LAST,
        stamp ASC
      LIMIT 1
    ) e ON true
    WHERE eu."ItemId" = $1
      AND (eu.stamp = $2 OR eu.stamp < $2 OR eu.stamp > $2)
    ORDER BY
      CASE WHEN eu.stamp = $2 THEN 0
           WHEN eu.stamp < $2 THEN 1
           ELSE 2 END,
      CASE WHEN eu.stamp <= $2 THEN eu.stamp END DESC NULLS LAST
  `;

  try {
    const { rows } = await pool.query(query, [itemId, timestamp]);
    const seen = new Set();
    return rows.filter(r => {
      if (seen.has(r.Name)) return false;
      seen.add(r.Name);
      return true;
    }).map(r => ({
      Name: r.Name,
      Values: {
        Strength: r.Strength != null ? Number(r.Strength) : null,
        DurationSeconds: r.DurationSeconds != null ? Number(r.DurationSeconds) : null,
        Unit: r.Unit,
        Description: r.Description,
      },
      Links: { "$Url": `/effects/${r.Id}` },
    }));
  } catch (err) {
    console.warn('[audit] Failed to load EffectsOnUse:', err.message);
    return [];
  }
}

/**
 * Load Tiers from audit tables at a specific timestamp
 */
async function loadTiersAudit(itemId, isArmorSet, timestamp) {
  const query = `
    SELECT t."Id" AS "TierId", t."Tier", t."ItemId", t."IsArmorSet",
           tm."MaterialId", tm."Amount",
           m."Name" AS "MaterialName", m."Value", m."Weight", m."Type"
    FROM "Tiers_audit" t
    LEFT JOIN LATERAL (
      SELECT "TierId", "MaterialId", "Amount"
      FROM "TierMaterials_audit"
      WHERE "TierId" = t."Id"
        AND (stamp = t.stamp OR stamp < t.stamp OR stamp > t.stamp)
      ORDER BY
        CASE WHEN stamp = t.stamp THEN 0
             WHEN stamp < t.stamp THEN 1
             ELSE 2 END,
        CASE WHEN stamp <= t.stamp THEN stamp END DESC NULLS LAST,
        stamp ASC
    ) tm ON true
    LEFT JOIN LATERAL (
      SELECT "Id", "Name", "Value", "Weight", "Type"
      FROM "Materials_audit"
      WHERE "Id" = tm."MaterialId"
        AND (stamp = t.stamp OR stamp < t.stamp OR stamp > t.stamp)
      ORDER BY
        CASE WHEN stamp = t.stamp THEN 0
             WHEN stamp < t.stamp THEN 1
             ELSE 2 END,
        CASE WHEN stamp <= t.stamp THEN stamp END DESC NULLS LAST,
        stamp ASC
      LIMIT 1
    ) m ON true
    WHERE t."ItemId" = $1 AND t."IsArmorSet" = $2
      AND (t.stamp = $3 OR t.stamp < $3 OR t.stamp > $3)
    ORDER BY
      CASE WHEN t.stamp = $3 THEN 0
           WHEN t.stamp < $3 THEN 1
           ELSE 2 END,
      CASE WHEN t.stamp <= $3 THEN t.stamp END DESC NULLS LAST,
      t."Tier"
  `;

  try {
    const { rows } = await pool.query(query, [itemId, isArmorSet, timestamp]);
    if (rows.length === 0) return [];

    // Group by tier
    const byTier = {};
    for (const r of rows) {
      const key = r.Tier;
      if (!byTier[key]) byTier[key] = [];
      byTier[key].push(r);
    }

    return Object.values(byTier).map(group => {
      const t = group[0];
      return {
        Name: `Tier ${t.Tier}`,
        Properties: { Tier: t.Tier, IsArmorSet: t.IsArmorSet === 1 },
        Materials: group.filter(g => g.MaterialId).map(g => ({
          Amount: g.Amount != null ? Number(g.Amount) : null,
          Material: {
            Name: g.MaterialName,
            Properties: {
              Weight: g.Weight != null ? Number(g.Weight) : null,
              Type: g.Type,
              Economy: { MaxTT: g.Value != null ? Number(g.Value) : null }
            },
            Links: { "$Url": `/materials/${g.MaterialId}` }
          }
        })),
        Links: { "$Url": `/tiers?ItemId=${t.ItemId}&IsArmorSet=${t.IsArmorSet}&Tier=${t.Tier}` }
      };
    });
  } catch (err) {
    console.warn('[audit] Failed to load Tiers:', err.message);
    return [];
  }
}

// ============================================================================
// ITEM AUDIT LOOKUP HELPER
// Resolves item names from appropriate audit tables based on ItemId offset
// ============================================================================

/**
 * Determine source table and original ID from ItemId
 * Returns { table, originalId } or null if unknown
 */
function getItemSourceFromId(itemId) {
  // Check ranges from highest to lowest to handle overlapping prefixes correctly
  if (itemId >= 12000000) return { table: 'Strongboxes', originalId: itemId - 12000000 };
  if (itemId >= 11000000) return { table: 'Pets', originalId: itemId - 11000000 };
  if (itemId >= 10100000) return { table: 'CreatureControlCapsules', originalId: itemId - 10100000 };
  if (itemId >= 10000000) return { table: 'Consumables', originalId: itemId - 10000000 };
  if (itemId >= 9400000) return { table: 'Signs', originalId: itemId - 9400000 };
  if (itemId >= 9300000) return { table: 'StorageContainers', originalId: itemId - 9300000 };
  if (itemId >= 9200000) return { table: 'Decorations', originalId: itemId - 9200000 };
  if (itemId >= 9100000) return { table: 'Furniture', originalId: itemId - 9100000 };
  if (itemId >= 9000000) return { table: 'Furniture', originalId: itemId - 9000000 }; // Furnishings -> Furniture
  if (itemId >= 8000000) return { table: 'Clothes', originalId: itemId - 8000000 };
  if (itemId >= 7000000) return { table: 'Vehicles', originalId: itemId - 7000000 };
  if (itemId >= 6000000) return { table: 'Blueprints', originalId: itemId - 6000000 };
  if (itemId >= 5700000) return { table: 'MindforceImplants', originalId: itemId - 5700000 };
  if (itemId >= 5600000) return { table: 'Enhancers', originalId: itemId - 5600000 };
  if (itemId >= 5500000) return { table: 'ArmorPlatings', originalId: itemId - 5500000 };
  if (itemId >= 5400000) return { table: 'FinderAmplifiers', originalId: itemId - 5400000 };
  if (itemId >= 5300000) return { table: 'Absorbers', originalId: itemId - 5300000 };
  if (itemId >= 5200000) return { table: 'WeaponVisionAttachments', originalId: itemId - 5200000 };
  if (itemId >= 5100000) return { table: 'WeaponAmplifiers', originalId: itemId - 5100000 };
  if (itemId >= 5000000) return { table: 'WeaponAmplifiers', originalId: itemId - 5000000 }; // Attachments -> WeaponAmplifiers
  if (itemId >= 4820000) return { table: 'EffectChips', originalId: itemId - 4820000 };
  if (itemId >= 4810000) return { table: 'TeleportationChips', originalId: itemId - 4810000 };
  if (itemId >= 4800000) return { table: 'MedicalChips', originalId: itemId - 4800000 };
  if (itemId >= 4700000) return { table: 'BlueprintBooks', originalId: itemId - 4700000 };
  if (itemId >= 4600000) return { table: 'Excavators', originalId: itemId - 4600000 };
  if (itemId >= 4500000) return { table: 'Finders', originalId: itemId - 4500000 };
  if (itemId >= 4400000) return { table: 'Scanners', originalId: itemId - 4400000 };
  if (itemId >= 4300000) return { table: 'Refiners', originalId: itemId - 4300000 };
  if (itemId >= 4200000) return { table: 'MiscTools', originalId: itemId - 4200000 };
  if (itemId >= 4100000) return { table: 'MedicalTools', originalId: itemId - 4100000 };
  if (itemId >= 4000000) return { table: 'MiscTools', originalId: itemId - 4000000 }; // Tools -> MiscTools
  if (itemId >= 3000000) return { table: 'Armors', originalId: itemId - 3000000 };
  if (itemId >= 2000000) return { table: 'Weapons', originalId: itemId - 2000000 };
  if (itemId >= 1000000) return { table: 'Materials', originalId: itemId - 1000000 };
  return null;
}

/**
 * Get item type string from table name (matches Items view Type column)
 */
function getItemTypeFromTable(table) {
  const typeMap = {
    Materials: 'Material',
    Weapons: 'Weapon',
    Armors: 'Armor',
    MiscTools: 'MiscTool',
    MedicalTools: 'MedicalTool',
    Refiners: 'Refiner',
    Scanners: 'Scanner',
    Finders: 'Finder',
    Excavators: 'Excavator',
    BlueprintBooks: 'BlueprintBook',
    MedicalChips: 'MedicalChip',
    TeleportationChips: 'TeleportChip',
    EffectChips: 'EffectChip',
    WeaponAmplifiers: 'WeaponAmplifier',
    WeaponVisionAttachments: 'WeaponVisionAttachment',
    Absorbers: 'Absorber',
    FinderAmplifiers: 'FinderAmplifier',
    ArmorPlatings: 'ArmorPlating',
    Enhancers: 'Enhancer',
    MindforceImplants: 'MindforceImplant',
    Blueprints: 'Blueprint',
    Vehicles: 'Vehicle',
    Clothes: 'Clothing',
    Furniture: 'Furniture',
    Decorations: 'Decoration',
    StorageContainers: 'StorageContainer',
    Signs: 'Sign',
    Consumables: 'Consumable',
    CreatureControlCapsules: 'CreatureControlCapsule',
    Pets: 'Pet',
    Strongboxes: 'Strongbox',
  };
  return typeMap[table] || table;
}

/**
 * Load item names from audit tables for a batch of ItemIds
 * Returns { [itemId]: { Name, Type } }
 */
async function loadItemNamesFromAudit(itemIds, timestamp) {
  if (!itemIds || itemIds.length === 0) return {};

  // Group items by source table
  const byTable = {};
  for (const itemId of itemIds) {
    const source = getItemSourceFromId(itemId);
    if (!source) continue;
    if (!byTable[source.table]) byTable[source.table] = [];
    byTable[source.table].push({ itemId, originalId: source.originalId });
  }

  const results = {};

  // Query each audit table
  for (const [table, items] of Object.entries(byTable)) {
    const originalIds = items.map(i => i.originalId);
    const query = `
      SELECT DISTINCT ON ("Id") "Id", "Name"
      FROM "${table}_audit"
      WHERE "Id" = ANY($2::int[])
        AND (stamp = $1 OR stamp < $1 OR stamp > $1)
      ORDER BY "Id",
        CASE WHEN stamp = $1 THEN 0 WHEN stamp < $1 THEN 1 ELSE 2 END,
        CASE WHEN stamp <= $1 THEN stamp END DESC NULLS LAST,
        stamp ASC
    `;

    try {
      const { rows } = await pool.query(query, [timestamp, originalIds]);
      const itemType = getItemTypeFromTable(table);
      for (const row of rows) {
        // Find the itemId that maps to this originalId
        const item = items.find(i => i.originalId === row.Id);
        if (item) {
          results[item.itemId] = { Name: row.Name, Type: itemType };
        }
      }
    } catch (err) {
      console.warn(`[audit] Failed to load items from ${table}_audit:`, err.message);
    }
  }

  return results;
}

// ============================================================================
// MOB-SPECIFIC AUDIT LOADERS
// Returns raw rows in the same format as regular endpoint loaders
// so formatMob can be used directly
// ============================================================================

/**
 * Load mob attacks from audit tables, grouped by MaturityId
 */
async function loadMobAttacksAudit(maturityIds, timestamp) {
  if (!maturityIds || maturityIds.length === 0) return {};

  const query = `
    SELECT ma.*
    FROM "MobAttacks_audit" ma
    WHERE ma."MaturityId" = ANY($2::int[])
      AND (ma.stamp = $1 OR ma.stamp < $1 OR ma.stamp > $1)
    ORDER BY
      CASE WHEN ma.stamp = $1 THEN 0
           WHEN ma.stamp < $1 THEN 1
           ELSE 2 END,
      CASE WHEN ma.stamp <= $1 THEN ma.stamp END DESC NULLS LAST
  `;

  try {
    const { rows } = await pool.query(query, [timestamp, maturityIds]);
    // Group by MaturityId, dedupe by attack Id
    const grouped = {};
    const seen = {};
    for (const r of rows) {
      if (!grouped[r.MaturityId]) {
        grouped[r.MaturityId] = [];
        seen[r.MaturityId] = new Set();
      }
      if (!seen[r.MaturityId].has(r.Id)) {
        seen[r.MaturityId].add(r.Id);
        grouped[r.MaturityId].push(r);
      }
    }
    return grouped;
  } catch (err) {
    console.warn('[audit] Failed to load MobAttacks:', err.message);
    return {};
  }
}

/**
 * Load mob maturities from audit tables - returns raw rows with Attacks attached
 * Format: { [mobId]: [row1, row2, ...] } where each row has .Attacks array
 */
async function loadMobMaturitiesAudit(mobId, timestamp) {
  const query = `
    SELECT mm.*
    FROM "MobMaturities_audit" mm
    WHERE mm."MobId" = $1
      AND (mm.stamp = $2 OR mm.stamp < $2 OR mm.stamp > $2)
    ORDER BY
      CASE WHEN mm.stamp = $2 THEN 0
           WHEN mm.stamp < $2 THEN 1
           ELSE 2 END,
      CASE WHEN mm.stamp <= $2 THEN mm.stamp END DESC NULLS LAST
  `;

  try {
    const { rows } = await pool.query(query, [mobId, timestamp]);
    // Dedupe by maturity Id
    const seen = new Set();
    const unique = rows.filter(r => {
      if (seen.has(r.Id)) return false;
      seen.add(r.Id);
      return true;
    });

    // Load attacks for these maturities
    const maturityIds = unique.map(m => m.Id);
    const attacks = maturityIds.length > 0 ? await loadMobAttacksAudit(maturityIds, timestamp) : {};

    // Attach attacks to each maturity row (same as regular loader)
    unique.forEach(r => { r.Attacks = attacks[r.Id] || []; });

    // Return grouped by MobId
    return { [mobId]: unique };
  } catch (err) {
    console.warn('[audit] Failed to load MobMaturities:', err.message);
    return {};
  }
}

/**
 * Load mob loots from audit tables - returns raw rows
 * Format: { [mobId]: [row1, row2, ...] } matching formatMobLoot expectations
 *
 * Items is a VIEW aggregating multiple tables, so we resolve item names
 * from the appropriate audit table based on ItemId offset ranges.
 */
async function loadMobLootsAudit(mobId, timestamp) {
  const query = `
    SELECT ml.*,
           mob."Name" AS "Mob",
           mob."PlanetId",
           mat."Name" AS "Maturity",
           planet."Name" AS "Planet"
    FROM "MobLoots_audit" ml
    LEFT JOIN LATERAL (
      SELECT "Name", "PlanetId" FROM "Mobs_audit"
      WHERE "Id" = ml."MobId"
        AND (stamp = ml.stamp OR stamp < ml.stamp OR stamp > ml.stamp)
      ORDER BY CASE WHEN stamp = ml.stamp THEN 0 WHEN stamp < ml.stamp THEN 1 ELSE 2 END,
               CASE WHEN stamp <= ml.stamp THEN stamp END DESC NULLS LAST, stamp ASC
      LIMIT 1
    ) mob ON true
    LEFT JOIN LATERAL (
      SELECT "Name" FROM "MobMaturities_audit"
      WHERE "Id" = ml."MaturityId"
        AND (stamp = ml.stamp OR stamp < ml.stamp OR stamp > ml.stamp)
      ORDER BY CASE WHEN stamp = ml.stamp THEN 0 WHEN stamp < ml.stamp THEN 1 ELSE 2 END,
               CASE WHEN stamp <= ml.stamp THEN stamp END DESC NULLS LAST, stamp ASC
      LIMIT 1
    ) mat ON true
    LEFT JOIN LATERAL (
      SELECT "Name" FROM "Planets_audit"
      WHERE "Id" = mob."PlanetId"
        AND (stamp = ml.stamp OR stamp < ml.stamp OR stamp > ml.stamp)
      ORDER BY CASE WHEN stamp = ml.stamp THEN 0 WHEN stamp < ml.stamp THEN 1 ELSE 2 END,
               CASE WHEN stamp <= ml.stamp THEN stamp END DESC NULLS LAST, stamp ASC
      LIMIT 1
    ) planet ON true
    WHERE ml."MobId" = $1
      AND (ml.stamp = $2 OR ml.stamp < $2 OR ml.stamp > $2)
    ORDER BY
      CASE WHEN ml.stamp = $2 THEN 0
           WHEN ml.stamp < $2 THEN 1
           ELSE 2 END,
      CASE WHEN ml.stamp <= $2 THEN ml.stamp END DESC NULLS LAST
  `;

  try {
    const { rows } = await pool.query(query, [mobId, timestamp]);

    // Dedupe by ItemId + MaturityId combo
    const seen = new Set();
    const unique = rows.filter(r => {
      const key = `${r.ItemId}-${r.MaturityId}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    // Load item names from appropriate audit tables
    const itemIds = [...new Set(unique.map(r => r.ItemId))];
    const itemInfo = await loadItemNamesFromAudit(itemIds, timestamp);

    // Attach item info to each row
    for (const row of unique) {
      const info = itemInfo[row.ItemId];
      row.Item = info?.Name || null;
      row.ItemType = info?.Type || null;
    }

    return { [mobId]: unique };
  } catch (err) {
    console.warn('[audit] Failed to load MobLoots:', err.message);
    return {};
  }
}

/**
 * Load related data for a Mob entity from audit tables
 * Returns in the same format as mobs.js loadRelated()
 */
async function loadMobRelatedAudit(mobId, timestamp) {
  const [maturities, loots] = await Promise.all([
    loadMobMaturitiesAudit(mobId, timestamp),
    loadMobLootsAudit(mobId, timestamp),
  ]);

  return {
    Maturities: maturities,
    Loots: loots,
    Spawns: {}, // Spawns not loaded from audit for now
  };
}

/**
 * Load all related data for an entity at a specific timestamp
 * Returns data keyed by itemId to match the format expected by existing formatters
 */
async function loadRelatedDataAudit(config, entityId, timestamp) {
  const itemId = config.idOffsetKey ? entityId + (idOffsets[config.idOffsetKey] || 0) : entityId;
  const isArmorSet = config.mainTable === 'ArmorSets' ? 1 : 0;

  // Data structure keyed by itemId to match existing formatter expectations
  const data = {
    EffectsOnEquip: {},
    EffectsOnUse: {},
    Tiers: {},
  };

  if (!config.relatedData || config.relatedData.length === 0) {
    return data;
  }

  const promises = [];

  if (config.relatedData.includes('EffectsOnEquip')) {
    promises.push(
      loadEffectsOnEquipAudit(itemId, timestamp).then(r => { data.EffectsOnEquip[itemId] = r; })
    );
  }

  if (config.relatedData.includes('EffectsOnUse')) {
    promises.push(
      loadEffectsOnUseAudit(itemId, timestamp).then(r => { data.EffectsOnUse[itemId] = r; })
    );
  }

  if (config.relatedData.includes('Tiers')) {
    promises.push(
      loadTiersAudit(itemId, isArmorSet, timestamp).then(r => { data.Tiers[itemId] = r; })
    );
  }

  await Promise.all(promises);
  return data;
}

// ============================================================================
// FORMATTERS
// Uses existing formatters where possible, generic formatter as fallback
// ============================================================================

function toNumberOrNull(v) {
  return v === null || v === undefined ? null : Number(v);
}

/**
 * Generic formatter that formats any entity row to API format
 * Used as fallback when no specific formatter is available
 */
function formatGenericEntity(row, config, relatedData = {}) {
  const result = {
    Id: row.Id,
    Name: row.Name,
    Properties: {},
  };

  // Add ItemId if applicable
  const itemId = config.idOffsetKey ? row.Id + (idOffsets[config.idOffsetKey] || 0) : row.Id;
  if (config.idOffsetKey) {
    result.ItemId = itemId;
  }

  // Add common properties
  if (row.Description !== undefined) result.Properties.Description = row.Description;
  if (row.Weight !== undefined) result.Properties.Weight = toNumberOrNull(row.Weight);
  if (row.Type !== undefined) result.Properties.Type = row.Type;
  if (row.Category !== undefined) result.Properties.Category = row.Category;

  // Add economy properties if they exist
  const economyProps = ['MaxTT', 'MinTT', 'Decay', 'Efficiency', 'AmmoBurn'];
  const economy = {};
  for (const prop of economyProps) {
    if (row[prop] !== undefined) {
      economy[prop] = toNumberOrNull(row[prop]);
    }
  }
  if (Object.keys(economy).length > 0) {
    result.Properties.Economy = economy;
  }

  // Add lookup join results
  for (const join of config.lookupJoins) {
    if (row[join.as]) {
      result[join.as] = { Name: row[join.as] };
    }
  }

  // Add related data (now keyed by itemId)
  const equipEffects = relatedData.EffectsOnEquip?.[itemId] || [];
  const useEffects = relatedData.EffectsOnUse?.[itemId] || [];
  const tiers = relatedData.Tiers?.[itemId] || [];

  if (equipEffects.length > 0) {
    result.EffectsOnEquip = equipEffects;
  }
  if (useEffects.length > 0) {
    result.EffectsOnUse = useEffects;
  }
  if (tiers.length > 0) {
    result.Tiers = tiers;
  }

  return result;
}

// ============================================================================
// MAIN API FUNCTIONS
// ============================================================================

/**
 * Format entity data using specific formatter if available, otherwise generic
 * For most entities this is synchronous, but Mob requires async loading
 */
function formatEntityData(row, entityType, config, relatedData) {
  // Use specific formatters when available
  switch (entityType) {
    // Weapon - uses imported formatter with relatedData
    case 'Weapon':
      return formatWeapon(row, relatedData);

    // Simple formatters (just row)
    case 'Material':
      return formatMaterial(row);
    case 'Refiner':
      return formatRefiner(row);
    case 'Scanner':
      return formatScanner(row);
    case 'Finder':
      return formatFinder(row);
    case 'Excavator':
      return formatExcavator(row);
    case 'Absorber':
      return formatAbsorber(row);
    case 'FinderAmplifier':
      return formatFinderAmplifier(row);
    case 'ArmorPlating':
      return formatArmorPlating(row);
    case 'Decoration':
      return formatDecoration(row);
    case 'Furniture':
      return formatFurniture(row);
    case 'StorageContainer':
      return formatStorageContainer(row);
    case 'Sign':
      return formatSign(row);
    case 'MiscTool':
      return formatMiscTool(row);
    case 'TeleportChip':
      return formatTeleportationChip(row);
    case 'EffectChip':
      return formatEffectChip(row);
    case 'WeaponAmplifier':
      return formatWeaponAmplifier(row);
    case 'WeaponVisionAttachment':
      return formatWeaponVisionAttachment(row);
    case 'MindforceImplant':
      return formatMindforceImplant(row);
    case 'CreatureControlCapsule':
      return formatCapsule(row);
    case 'Vehicle':
      return formatVehicle(row);

    // Formatters with compatible relatedData structure
    case 'MedicalTool':
      return formatMedicalTool(row, relatedData);
    case 'MedicalChip':
      return formatMedicalChip(row, relatedData);
    case 'Clothing':
      // formatClothing expects (row, effectsByItemId, setEffectsByItemId)
      // We have EffectsOnEquip but no set effects in audit
      return formatClothing(row, relatedData.EffectsOnEquip || {}, {});

    // Entities needing specialized related data not yet loaded in audit
    // Use generic formatter for now: ArmorSet, Blueprint, Pet, Consumable, Vendor
    default:
      return formatGenericEntity(row, config, relatedData);
  }
}

/**
 * Format an audit record for API response
 * Async because some entities (Mob) require loading related data
 */
async function formatAuditRecord(row, config, entityType, timestamp) {
  const { operation, stamp, userid, ...entityData } = row;

  let formattedData;

  // Mob needs special handling - load related data and use formatMob
  if (entityType === 'Mob') {
    await ensureInvestigatorCache();
    const rel = await loadMobRelatedAudit(entityData.Id, timestamp);
    formattedData = formatMob(entityData, rel);
  } else {
    // For other entities, load standard related data
    const relatedData = await loadRelatedDataAudit(config, entityData.Id, timestamp);
    formattedData = formatEntityData(entityData, entityType, config, relatedData);
  }

  return {
    Operation: operation === 'I' ? 'Insert' : operation === 'U' ? 'Update' : operation === 'D' ? 'Delete' : operation,
    Timestamp: stamp,
    UserId: userid,
    Data: formattedData
  };
}

/**
 * Get audit history for an entity
 */
async function getAuditHistory(entityType, entityId) {
  const config = entityConfigs[entityType];
  if (!config) {
    throw new Error(`Unknown entity type: ${entityType}`);
  }

  const query = buildAuditQuery(config, null, 'DESC') + ' LIMIT 100';

  const { rows } = await pool.query(query, [entityId]);

  // Format each record with its related data
  const results = [];
  for (const row of rows) {
    results.push(await formatAuditRecord(row, config, entityType, row.stamp));
  }

  return results;
}

/**
 * Get the original (first INSERT) version of an entity
 */
async function getOriginalVersion(entityType, entityId) {
  const config = entityConfigs[entityType];
  if (!config) {
    throw new Error(`Unknown entity type: ${entityType}`);
  }

  // Try to find INSERT record first
  let query = buildAuditQuery(config, "operation = 'I'", 'ASC') + ' LIMIT 1';
  let { rows } = await pool.query(query, [entityId]);

  // Fall back to earliest record if no INSERT found
  if (rows.length === 0) {
    query = buildAuditQuery(config, null, 'ASC') + ' LIMIT 1';
    const result = await pool.query(query, [entityId]);
    rows = result.rows;
  }

  if (rows.length === 0) return null;

  const row = rows[0];
  return await formatAuditRecord(row, config, entityType, row.stamp);
}

/**
 * Get a version at or before a specific timestamp
 */
async function getVersionAtOrBefore(entityType, entityId, timestamp) {
  const config = entityConfigs[entityType];
  if (!config) {
    throw new Error(`Unknown entity type: ${entityType}`);
  }

  // First try at or before
  let query = buildAuditQuery(config, 'stamp <= $2', 'DESC') + ' LIMIT 1';
  let { rows } = await pool.query(query, [entityId, timestamp]);

  // Fall back to earliest if nothing before
  if (rows.length === 0) {
    query = buildAuditQuery(config, null, 'ASC') + ' LIMIT 1';
    const result = await pool.query(query, [entityId]);
    rows = result.rows;
  }

  if (rows.length === 0) return null;

  const row = rows[0];
  return await formatAuditRecord(row, config, entityType, row.stamp);
}

// ============================================================================
// EXPRESS ROUTES
// ============================================================================

function register(app) {
  app.get('/audit/types', (req, res) => {
    res.json({ types: validEntityTypes });
  });

  app.get('/audit/:entityType/:entityId', async (req, res) => {
    const { entityType, entityId } = req.params;

    if (!entityConfigs[entityType]) {
      return res.status(400).json({ error: `Invalid entity type: ${entityType}`, validTypes: validEntityTypes });
    }

    const id = parseInt(entityId, 10);
    if (isNaN(id)) {
      return res.status(400).json({ error: 'Invalid entity ID' });
    }

    try {
      const history = await getAuditHistory(entityType, id);
      if (history.length === 0) {
        return res.status(404).json({ error: 'No audit records found' });
      }
      res.json({ entityType, entityId: id, history });
    } catch (err) {
      console.error('[audit] Error fetching history:', err);
      res.status(500).json({ error: 'Failed to fetch audit history' });
    }
  });

  app.get('/audit/:entityType/:entityId/original', async (req, res) => {
    const { entityType, entityId } = req.params;

    if (!entityConfigs[entityType]) {
      return res.status(400).json({ error: `Invalid entity type: ${entityType}`, validTypes: validEntityTypes });
    }

    const id = parseInt(entityId, 10);
    if (isNaN(id)) {
      return res.status(400).json({ error: 'Invalid entity ID' });
    }

    try {
      const original = await getOriginalVersion(entityType, id);
      if (!original) {
        return res.status(404).json({ error: 'No audit records found' });
      }
      res.json({ entityType, entityId: id, original });
    } catch (err) {
      console.error('[audit] Error fetching original:', err);
      res.status(500).json({ error: 'Failed to fetch original version' });
    }
  });

  app.get('/audit/:entityType/:entityId/at', async (req, res) => {
    const { entityType, entityId } = req.params;
    const { timestamp } = req.query;

    if (!entityConfigs[entityType]) {
      return res.status(400).json({ error: `Invalid entity type: ${entityType}`, validTypes: validEntityTypes });
    }

    const id = parseInt(entityId, 10);
    if (isNaN(id)) {
      return res.status(400).json({ error: 'Invalid entity ID' });
    }

    if (!timestamp) {
      return res.status(400).json({ error: 'Missing required query parameter: timestamp' });
    }

    try {
      const version = await getVersionAtOrBefore(entityType, id, timestamp);
      if (!version) {
        return res.status(404).json({ error: 'No audit records found' });
      }
      res.json({ entityType, entityId: id, version });
    } catch (err) {
      console.error('[audit] Error fetching version:', err);
      res.status(500).json({ error: 'Failed to fetch version' });
    }
  });
}

module.exports = {
  register,
  getAuditHistory,
  getOriginalVersion,
  getVersionAtOrBefore,
  entityConfigs,
  validEntityTypes
};

const pgp = require('pg-promise')();
const { pool } = require('./dbClient');

function groupBy(arr, key) {
  return arr.reduce((acc, row) => {
    if (!acc[row[key]]) acc[row[key]] = [];
    acc[row[key]].push(row);
    return acc;
  }, {});
}

function toNumberOrNull(v) {
  return v === null || v === undefined ? null : Number(v);
}

// Formatters
function formatEffectOnEquip(row) {
  return {
    Name: row.Name,
    Values: {
      Strength: toNumberOrNull(row.Strength),
      Unit: row.Unit,
      Description: row.Description,
    },
    Links: { "$Url": `/effects/${row.Id}` },
  };
}

function formatEffectOnUse(row) {
  return {
    Name: row.Name,
    Values: {
      Strength: toNumberOrNull(row.Strength),
      DurationSeconds: toNumberOrNull(row.DurationSeconds),
      Unit: row.Unit,
      Description: row.Description,
    },
    Links: { "$Url": `/effects/${row.Id}` },
  };
}

function formatEffectOnSetEquip(row) {
  return {
    Name: row.Name,
    Values: {
      Strength: toNumberOrNull(row.Strength),
      MinSetPieces: toNumberOrNull(row.MinSetPieces),
      Unit: row.Unit,
      Description: row.Description,
    },
    Links: { "$Url": `/effects/${row.EffectId}` },
  };
}

// Queries
const queries = {
  EffectsOnEquip: `
    SELECT
      e."Id",
      e."Name",
      e."Unit",
      e."Description",
      eo."Strength",
      eo."ItemId"
    FROM ONLY "EffectsOnEquip" eo
    INNER JOIN ONLY "Effects" e ON eo."EffectId" = e."Id"
    WHERE eo."ItemId" IN ($1:csv)
  `,
  EffectsOnUse: `
    SELECT
      e."Id",
      e."Name",
      e."Unit",
      e."Description",
      eu."Strength",
      eu."DurationSeconds",
      eu."ItemId"
    FROM ONLY "EffectsOnUse" eu
    INNER JOIN ONLY "Effects" e ON eu."EffectId" = e."Id"
    WHERE eu."ItemId" IN ($1:csv)
  `,
  EffectsOnSetEquip: `
    SELECT
      ese."SetId",
      e."Id" AS "EffectId",
      e."Name",
      e."Unit",
      e."Description",
      ese."Strength",
      ese."MinSetPieces"
    FROM ONLY "EffectsOnSetEquip" ese
    INNER JOIN ONLY "Effects" e ON ese."EffectId" = e."Id"
    WHERE ese."SetId" IN ($1:csv)
  `,
  // Set effects resolved by ItemId via EquipSetItems; includes SetName and non-offset SetId
  EffectsOnSetEquipByItemId: `
    SELECT
      esi."ItemId",
      es."Name" AS "SetName",
      es."Id"   AS "SetId",
      e."Id"    AS "EffectId",
      e."Name",
      e."Unit",
      e."Description",
      ese."Strength",
      ese."MinSetPieces"
    FROM ONLY "EquipSetItems" esi
    INNER JOIN ONLY "EffectsOnSetEquip" ese ON ese."SetId" = esi."EquipSetId" + 100000
    INNER JOIN ONLY "EquipSets" es         ON es."Id" + 100000 = ese."SetId"
    INNER JOIN ONLY "Effects" e            ON e."Id" = ese."EffectId"
    WHERE esi."ItemId" IN ($1:csv)
  `,
};

// Loaders
async function loadEffectsOnEquipByItemIds(itemIds) {
  if (!itemIds || itemIds.length === 0) return {};
  const res = await pool.query(pgp.as.format(queries.EffectsOnEquip, [itemIds]));
  const grouped = groupBy(res.rows, 'ItemId');
  const formatted = {};
  for (const [k, v] of Object.entries(grouped)) {
    formatted[k] = v.map(formatEffectOnEquip);
  }
  return formatted;
}

async function loadEffectsOnUseByItemIds(itemIds) {
  if (!itemIds || itemIds.length === 0) return {};
  const res = await pool.query(pgp.as.format(queries.EffectsOnUse, [itemIds]));
  const grouped = groupBy(res.rows, 'ItemId');
  const formatted = {};
  for (const [k, v] of Object.entries(grouped)) {
    formatted[k] = v.map(formatEffectOnUse);
  }
  return formatted;
}

async function loadSetEffectsBySetIds(setIds) {
  if (!setIds || setIds.length === 0) return {};
  const res = await pool.query(pgp.as.format(queries.EffectsOnSetEquip, [setIds]));
  const grouped = groupBy(res.rows, 'SetId');
  const formatted = {};
  for (const [k, v] of Object.entries(grouped)) {
    formatted[k] = v.map(formatEffectOnSetEquip);
  }
  return formatted;
}

// Load set effects for items that belong to equip sets, grouped by ItemId.
// Rows include SetName and non-offset SetId for the clothing/armor links.
async function loadSetEffectsByItemIdsFromEquipSets(itemIds) {
  if (!itemIds || itemIds.length === 0) return {};
  const res = await pool.query(pgp.as.format(queries.EffectsOnSetEquipByItemId, [itemIds]));
  const grouped = groupBy(res.rows, 'ItemId');
  // Do NOT apply formatEffectOnSetEquip here, as callers may need SetName/SetId.
  return grouped;
}

module.exports = {
  // formatters
  formatEffectOnEquip,
  formatEffectOnUse,
  formatEffectOnSetEquip,
  // loaders
  loadEffectsOnEquipByItemIds,
  loadEffectsOnUseByItemIds,
  loadSetEffectsBySetIds,
  loadSetEffectsByItemIdsFromEquipSets,
};

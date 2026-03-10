const { pool } = require('./dbClient');

/**
 * Find all missions that reward the given items.
 *
 * MissionRewards.Items JSONB has two shapes:
 *   Flat:    [{itemId, itemName?, quantity?, rarity?, pedValue?}, ...]
 *   Choices: [{Items: [...], Skills: [...], Unlocks: [...]}, ...]
 *
 * We match by itemId (resolved from item names) and by itemName (for entries
 * that lack an itemId).  Both flat and choices formats are handled.
 *
 * @param {string[]} itemNames — item names to search for
 * @returns {Promise<Array>} formatted mission-reward entries
 */
async function getMissionRewardsForItems(itemNames) {
  if (!itemNames || !itemNames.length) return [];

  // Resolve names → ids
  const { rows: itemRows } = await pool.query(
    'SELECT "Id", "Name" FROM ONLY "Items" WHERE "Name" = ANY($1)',
    [itemNames]
  );

  const itemIds = itemRows.map(r => r.Id);
  const nameSet = new Set(itemNames.map(n => n.toLowerCase()));
  const idSet = new Set(itemIds);

  // Nothing in the Items table matched — still try matching by itemName in JSONB
  const conditions = [];
  const params = [];

  // Condition 1: flat entries matching by itemId
  if (itemIds.length) {
    params.push(itemIds);
    conditions.push(`EXISTS (
      SELECT 1 FROM jsonb_array_elements(mr."Items") elem
      WHERE (elem->>'itemId')::int = ANY($${params.length})
    )`);
  }

  // Condition 2: flat entries matching by itemName (case-insensitive)
  params.push(itemNames);
  conditions.push(`EXISTS (
    SELECT 1 FROM jsonb_array_elements(mr."Items") elem
    WHERE LOWER(elem->>'itemName') = ANY(SELECT LOWER(unnest($${params.length}::text[])))
  )`);

  // Condition 3: choices format — nested Items arrays matching by itemId
  if (itemIds.length) {
    params.push(itemIds);
    conditions.push(`EXISTS (
      SELECT 1 FROM jsonb_array_elements(mr."Items") pkg,
        jsonb_array_elements(COALESCE(pkg->'Items', '[]'::jsonb)) sub
      WHERE (sub->>'itemId')::int = ANY($${params.length})
    )`);
  }

  // Condition 4: choices format — nested matching by itemName
  params.push(itemNames);
  conditions.push(`EXISTS (
    SELECT 1 FROM jsonb_array_elements(mr."Items") pkg,
      jsonb_array_elements(COALESCE(pkg->'Items', '[]'::jsonb)) sub
    WHERE LOWER(sub->>'itemName') = ANY(SELECT LOWER(unnest($${params.length}::text[])))
  )`);

  const sql = `
    SELECT m."Id", m."Name", m."Type", p."Name" AS "Planet",
           mr."Items" AS "RewardItems"
    FROM ONLY "MissionRewards" mr
    JOIN ONLY "Missions" m ON mr."MissionId" = m."Id"
    LEFT JOIN ONLY "Planets" p ON m."PlanetId" = p."Id"
    WHERE mr."Items" IS NOT NULL
      AND jsonb_array_length(mr."Items") > 0
      AND (${conditions.join(' OR ')})
  `;

  const { rows } = await pool.query(sql, params);

  // Extract the matching reward entries from each mission
  const results = [];
  for (const row of rows) {
    const rewardItems = row.RewardItems || [];
    for (const entry of rewardItems) {
      // Flat format entry
      if (matchesItem(entry, idSet, nameSet)) {
        results.push(formatResult(row, entry, false));
      }
      // Choices format — entry is a package with nested Items
      if (Array.isArray(entry.Items)) {
        for (const sub of entry.Items) {
          if (matchesItem(sub, idSet, nameSet)) {
            results.push(formatResult(row, sub, true));
          }
        }
      }
    }
  }

  return results;
}

function matchesItem(entry, idSet, nameSet) {
  if (entry.itemId && idSet.has(entry.itemId)) return true;
  if (entry.itemName && nameSet.has(entry.itemName.toLowerCase())) return true;
  return false;
}

function formatResult(row, entry, isChoice) {
  return {
    Mission: {
      Id: row.Id,
      Name: row.Name,
      Type: row.Type ?? null,
      Planet: row.Planet ? { Name: row.Planet } : null,
      Links: { "$Url": `/missions/${row.Id}` }
    },
    Quantity: entry.quantity ?? null,
    MinQuantity: entry.minQuantity ?? null,
    MaxQuantity: entry.maxQuantity ?? null,
    Rarity: entry.rarity ?? null,
    PedValue: entry.pedValue ?? null,
    IsChoice: isChoice
  };
}

module.exports = { getMissionRewardsForItems };

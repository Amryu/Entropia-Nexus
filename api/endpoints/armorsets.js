const pgp = require('pg-promise')();
const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName, loadClassIds } = require('./utils');
const { loadEffectsOnEquipByItemIds, loadSetEffectsBySetIds } = require('./effects-utils');
const { getTiersByItemIds } = require('./tiers');
const { withCache, withCachedLookup } = require('./responseCache');

// Queries (formatted, parameterized)
const queries = {
  ArmorSets: `
    SELECT
      "ArmorSets"."Id",
      "ArmorSets"."Name",
      "ArmorSets"."Description",
      "Durability",
      "Stab",
      "Cut",
      "Impact",
      "Penetration",
      "Shrapnel",
      "Burn",
      "Cold",
      "Acid",
      "Electric"
    FROM ONLY "ArmorSets"
  `,

  ArmorsBySet: `
    SELECT *
    FROM ONLY "Armors"
    WHERE "SetId" IN ($1:csv)
  `,

  // effect queries moved to effects-utils

  TiersArmorSet: `
    SELECT
      t."Tier",
      t."ItemId",
      t."IsArmorSet",
      s."Name" AS "ItemName",
      tm.*,
      m."Name"   AS "MaterialName",
      m."Value"  AS "Value",
      m."Weight" AS "Weight",
      m."Type"   AS "Type"
    FROM ONLY "Tiers" t
    INNER JOIN ONLY "TierMaterials" tm ON t."Id" = tm."TierId"
    INNER JOIN ONLY "Materials" m      ON tm."MaterialId" = m."Id"
    INNER JOIN ONLY "ArmorSets" s      ON t."ItemId" = s."Id"
    WHERE t."ItemId" IN ($1:csv) AND t."IsArmorSet" = 1
  `,
};

function groupBy(arr, key) {
  return arr.reduce((acc, row) => {
    if (!acc[row[key]]) {
      acc[row[key]] = [];
    }
    acc[row[key]].push(row);
    return acc;
  }, {});
}

function toNumberOrNull(v) {
  return v === null || v === undefined ? null : Number(v);
}

// effect formatters provided by shared utils

function formatTierMaterial(row) {
  return {
    Amount: toNumberOrNull(row.Amount),
    Material: {
      Name: row.MaterialName,
      Properties: {
        Weight: toNumberOrNull(row.Weight),
        Type: row.Type,
        Economy: {
          MaxTT: toNumberOrNull(row.Value),
        },
      },
      Links: {
        "$Url": `/materials/${row.MaterialId}`,
      },
    },
  };
}

function formatTier(group) {
  const head = group[0];

  return {
    Name: `${head.ItemName} Tier ${head.Tier}`,
    Properties: {
      Tier: head.Tier,
      IsArmorSet: head.IsArmorSet === 1,
    },
    Materials: group.map(formatTierMaterial),
    Links: {
      "$Url": `/tiers?ItemId=${head.ItemId}&IsArmorSet=${head.IsArmorSet}&Tier=${head.Tier}`,
    },
  };
}

function formatArmorPiece(row, effectsByItemId) {
  const itemId = row.Id + idOffsets.Armors;
  const equipEffects = effectsByItemId[itemId] || [];

  return {
    ItemId: itemId,
    Name: row.Name,
    Properties: {
      Description: row.Description,
      Weight: toNumberOrNull(row.Weight),
      Gender: row.Gender,
      Slot: row.Slot,
      Economy: {
        MaxTT: toNumberOrNull(row.MaxTT),
        MinTT: toNumberOrNull(row.MinTT),
      },
    },
    EffectsOnEquip: equipEffects,
    Links: {
      "$Url": `/armors/${row.Id}`,
    },
  };
}

async function collectArmorSetData(setIds) {
  if (!setIds || setIds.length === 0) {
    return {
      armorsBySetId: {},
      equipEffectsByItemId: {},
      setEffectsBySetId: {},
      tiersBySetId: {},
      classIds: {},
    };
  }

  // Armors belonging to the sets
  const armorsResult = await pool.query(
    pgp.as.format(queries.ArmorsBySet, [setIds])
  );
  const armors = armorsResult.rows;
  const armorsBySetId = groupBy(armors, 'SetId');

  // Effects on equip for each armor piece (by ItemId = Armor.Id + offset)
  const itemIds = armors.map(a => a.Id + idOffsets.Armors);
  const equipEffectsByItemId = await loadEffectsOnEquipByItemIds(itemIds);

  // Set effects (by SetId)
  const setEffectsBySetId = await loadSetEffectsBySetIds(setIds);

  // Tiers for armor sets (grouped by ItemId and Tier) via shared helper
  const [tiersBySetId, classIds] = await Promise.all([
    getTiersByItemIds(setIds, 1),
    loadClassIds('ArmorSet', setIds)
  ]);

  return {
    armorsBySetId,
    equipEffectsByItemId,
    setEffectsBySetId,
    tiersBySetId,
    classIds,
  };
}

function formatArmorSetsResponse(row, data) {
  const piecesRaw = data.armorsBySetId[row.Id] || [];

  const pieces = piecesRaw.map(piece =>
    formatArmorPiece(piece, data.equipEffectsByItemId)
  );

  // Aggregate only the male/both pieces for totals
  const aggregateCandidates = pieces.filter(p =>
    p.Properties.Gender === 'Male' || p.Properties.Gender === 'Both'
  );

  const sum = (arr, selector) => {
    const total = arr.reduce((acc, item) => {
      const v = selector(item);
      return acc + (typeof v === 'number' ? v : 0);
    }, 0);
    return Number(total.toFixed(8));
  };

  const totalWeight = sum(aggregateCandidates, p => p.Properties.Weight);
  const totalMaxTT = sum(aggregateCandidates, p => p.Properties.Economy.MaxTT);
  const totalMinTT = sum(aggregateCandidates, p => p.Properties.Economy.MinTT);

  const setEffects = data.setEffectsBySetId[row.Id] || [];
  const tiers = data.tiersBySetId[row.Id] || [];

  // Group pieces by slot and return as an array of arrays (preserving prior behavior)
  const bySlot = pieces.reduce((acc, piece) => {
    const slot = piece.Properties.Slot;
    if (!acc[slot]) acc[slot] = [];
    acc[slot].push(piece);
    return acc;
  }, {});

  const piecesGrouped = Object.values(bySlot);

  return {
    Id: row.Id,
    ClassId: data.classIds[row.Id] || null,
    ItemId: row.Id + idOffsets.ArmorSets,
    Name: row.Name,
    Properties: {
      Description: row.Description,
      Weight: aggregateCandidates.length ? totalWeight : null,
      Economy: {
        MaxTT: aggregateCandidates.length ? totalMaxTT : null,
        MinTT: aggregateCandidates.length ? totalMinTT : null,
        Durability: toNumberOrNull(row.Durability),
      },
      Defense: {
        Stab: toNumberOrNull(row.Stab),
        Cut: toNumberOrNull(row.Cut),
        Impact: toNumberOrNull(row.Impact),
        Penetration: toNumberOrNull(row.Penetration),
        Shrapnel: toNumberOrNull(row.Shrapnel),
        Burn: toNumberOrNull(row.Burn),
        Cold: toNumberOrNull(row.Cold),
        Acid: toNumberOrNull(row.Acid),
        Electric: toNumberOrNull(row.Electric),
      },
    },
    EffectsOnSetEquip: setEffects,
    Armors: piecesGrouped,
    Tiers: tiers,
    Links: {
      "$Url": `/armorsets/${row.Id}`,
    },
  };
}

async function getArmorSets() {
  const { rows } = await pool.query(queries.ArmorSets);
  const setIds = rows.map(r => r.Id);
  const data = await collectArmorSetData(setIds);
  return rows.map(r => formatArmorSetsResponse(r, data));
}

async function getArmorSet(idOrName) {
  const row = await getObjectByIdOrName(queries.ArmorSets, 'ArmorSets', idOrName);
  if (!row) {
    return null;
  }
  const data = await collectArmorSetData([row.Id]);
  return formatArmorSetsResponse(row, data);
}

function register(app){
  /**
   * @swagger
   * /armorsets:
   *  get:
   *    description: Get all armor sets
   *    responses:
   *      '200':
   *        description: A list of armor sets
   */
  app.get('/armorsets', async (req,res) => { res.json(await withCache('/armorsets', ['ArmorSets', 'Armors', 'EffectsOnEquip', 'EffectsOnSetEquip', 'Effects', 'Tiers', 'TierMaterials', 'ClassIds'], getArmorSets)); });
  /**
   * @swagger
   * /armorsets/{armorset}:
   *  get:
   *    description: Get an armor set by name or id
   *    parameters:
   *      - in: path
   *        name: armorset
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the armor set
   *    responses:
   *      '200':
   *        description: The armor set
   *      '404':
   *        description: Armor set not found
   */
  app.get('/armorsets/:armorset', async (req,res) => { const r = await withCachedLookup('/armorsets', ['ArmorSets', 'Armors', 'EffectsOnEquip', 'EffectsOnSetEquip', 'Effects', 'Tiers', 'TierMaterials', 'ClassIds'], getArmorSets, req.params.armorset); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getArmorSets, getArmorSet, formatArmorSetsResponse, queries };

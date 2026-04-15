const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');

// Items.Type -> API path segment overrides for types whose lowercased+s
// form doesn't match the API endpoint. Keep in sync with
// api/endpoints/items.js TYPE_URL_OVERRIDES.
const TYPE_URL_OVERRIDES = {
  Fish: 'fishes',
  Food: 'consumables',
  FishingRod: 'fishingrods',
  FishingReel: 'fishingreels',
  FishingBlank: 'fishingblanks',
  FishingLine: 'fishinglines',
  FishingLure: 'fishinglures',
};

function itemTypeToPath(type) {
  if (!type) return 'items';
  return TYPE_URL_OVERRIDES[type] || `${String(type).toLowerCase()}s`;
}

// Fish is the info-side row. Every Fish references an Items row (Material)
// and a MobSpecies row. This endpoint exposes the info entity joined with
// the item, species, and junction data.

const baseQuery = `
  SELECT f.*,
         ms."Name" AS "SpeciesName",
         ms."CodexBaseCost" AS "SpeciesCodexBaseCost",
         ms."CodexType" AS "SpeciesCodexType",
         item_t."Name" AS "ItemName",
         item_t."Type" AS "ItemType",
         lure_t."Name" AS "PreferredLureName"
    FROM ONLY "Fish" f
    LEFT JOIN ONLY "MobSpecies" ms ON ms."Id" = f."SpeciesId"
    LEFT JOIN "Items" item_t ON item_t."Id" = f."ItemId"
    LEFT JOIN "Items" lure_t ON lure_t."Id" = f."PreferredLureId"
`;

async function loadRelated(fishRows) {
  const ids = fishRows.map(r => r.Id);
  if (ids.length === 0) return { planetsByFish: {}, rodTypesByFish: {} };

  const [planetsRes, rodRes] = await Promise.all([
    pool.query(
      `SELECT fp."FishId", p."Id" AS "PlanetId", p."Name" AS "PlanetName"
       FROM ONLY "FishPlanets" fp
       JOIN ONLY "Planets" p ON p."Id" = fp."PlanetId"
       WHERE fp."FishId" = ANY($1::int[])`,
      [ids]
    ),
    pool.query(
      `SELECT "FishId", "RodType" FROM ONLY "FishRodTypes" WHERE "FishId" = ANY($1::int[])`,
      [ids]
    ),
  ]);

  const planetsByFish = {};
  for (const r of planetsRes.rows) {
    (planetsByFish[r.FishId] ||= []).push({
      Name: r.PlanetName,
      Links: { "$Url": `/planets/${r.PlanetId}` }
    });
  }

  const rodTypesByFish = {};
  for (const r of rodRes.rows) {
    (rodTypesByFish[r.FishId] ||= []).push(r.RodType);
  }

  return { planetsByFish, rodTypesByFish };
}

function formatFish(f, rel) {
  return {
    Id: f.Id,
    Name: f.Name,
    Properties: {
      Description: f.Description,
      Biome: f.Biome,
      Size: f.Size != null ? Number(f.Size) : null,
      Strength: f.Strength != null ? Number(f.Strength) : null,
      Difficulty: f.Difficulty,
      MinDepth: f.MinDepth != null ? Number(f.MinDepth) : null,
      TimeOfDay: f.TimeOfDay,
      RodTypes: rel.rodTypesByFish[f.Id] || [],
    },
    Item: f.ItemName ? {
      Name: f.ItemName,
      Properties: { Type: f.ItemType },
      Links: { "$Url": `/${itemTypeToPath(f.ItemType)}/${f.ItemId}` }
    } : null,
    Species: f.SpeciesName ? {
      Name: f.SpeciesName,
      Properties: {
        CodexBaseCost: f.SpeciesCodexBaseCost != null ? Number(f.SpeciesCodexBaseCost) : null,
        CodexType: f.SpeciesCodexType ?? null
      },
      Links: { "$Url": `/mobspecies/${f.SpeciesId}` }
    } : null,
    PreferredLure: f.PreferredLureName ? {
      Name: f.PreferredLureName,
      Links: { "$Url": `/items/${f.PreferredLureId}` }
    } : null,
    Planets: rel.planetsByFish[f.Id] || [],
    Links: { "$Url": `/fishes/${f.Id}` }
  };
}

async function getAllFish() {
  const { rows } = await pool.query(baseQuery);
  const rel = await loadRelated(rows);
  return rows.map(r => formatFish(r, rel));
}

async function getFish(idOrName) {
  const row = await getObjectByIdOrName(baseQuery, 'Fish', idOrName);
  if (!row) return null;
  const rel = await loadRelated([row]);
  return formatFish(row, rel);
}

const CACHE_KEYS = ['Fish', 'FishPlanets', 'FishRodTypes', 'MobSpecies', 'Planets', 'Materials'];

function register(app) {
  /**
   * @swagger
   * /fishes:
   *  get:
   *    description: Get all fishes
   *    responses:
   *      '200':
   *        description: A list of fish info entries
   */
  app.get('/fishes', async (req, res) => {
    try {
      const data = await withCache('/fishes', CACHE_KEYS, getAllFish);
      res.json(data);
    } catch (e) {
      console.error('Failed to fetch fishes', e);
      res.status(500).json({ error: 'Failed to fetch fishes' });
    }
  });

  /**
   * @swagger
   * /fishes/{fish}:
   *  get:
   *    description: Get a fish by name or id
   *    parameters:
   *      - in: path
   *        name: fish
   *        schema:
   *          type: string
   *        required: true
   *    responses:
   *      '200':
   *        description: The fish
   *      '404':
   *        description: Not found
   */
  app.get('/fishes/:fish', async (req, res) => {
    try {
      const r = await withCachedLookup('/fishes', CACHE_KEYS, getAllFish, req.params.fish);
      if (r) res.json(r); else res.status(404).send();
    } catch (e) {
      console.error('Failed to fetch fish', e);
      res.status(500).json({ error: 'Failed to fetch fish' });
    }
  });
}

module.exports = { register, getAllFish, getFish, formatFish };

const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');

// Fish IS the material (not a foreign reference to one). Weight and TT
// value come from the backing Materials row; Fish.ItemId is just the
// Items-view-offset form of Materials.Id. The preferred lure is looked up
// via the Items view (it's a FishingLure, not a material).

const baseQuery = `
  SELECT f.*,
         ms."Name" AS "SpeciesName",
         ms."CodexBaseCost" AS "SpeciesCodexBaseCost",
         ms."CodexType" AS "SpeciesCodexType",
         mat."Weight" AS "MatWeight",
         mat."Value" AS "MatValue",
         lure_t."Name" AS "PreferredLureName",
         oil_t."Name" AS "FishOilName"
    FROM ONLY "Fish" f
    LEFT JOIN ONLY "MobSpecies" ms ON ms."Id" = f."SpeciesId"
    LEFT JOIN ONLY "Materials" mat ON mat."Id" = f."ItemId" - 1000000
    LEFT JOIN "Items" lure_t ON lure_t."Id" = f."PreferredLureId"
    LEFT JOIN "Items" oil_t ON oil_t."Id" = f."FishOilItemId"
`;

async function loadRelated(fishRows) {
  const ids = fishRows.map(r => r.Id);
  if (ids.length === 0) return { planetsByFish: {}, rodTypesByFish: {}, sizesByFish: {}, biomesByFish: {} };

  const [planetsRes, rodRes, sizesRes, biomesRes] = await Promise.all([
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
    pool.query(
      `SELECT "FishId", "Name", "Strength", "ScrapsToRefine"
       FROM ONLY "FishSizes"
       WHERE "FishId" = ANY($1::int[])
       ORDER BY "Id"`,
      [ids]
    ),
    pool.query(
      `SELECT "FishId", "Biome" FROM ONLY "FishBiomes" WHERE "FishId" = ANY($1::int[])`,
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

  const sizesByFish = {};
  for (const r of sizesRes.rows) {
    (sizesByFish[r.FishId] ||= []).push({
      Name: r.Name,
      Strength: r.Strength != null ? Number(r.Strength) : null,
      ScrapsToRefine: r.ScrapsToRefine != null ? Number(r.ScrapsToRefine) : null,
    });
  }

  const biomesByFish = {};
  for (const r of biomesRes.rows) {
    (biomesByFish[r.FishId] ||= []).push(r.Biome);
  }

  return { planetsByFish, rodTypesByFish, sizesByFish, biomesByFish };
}

function formatFish(f, rel) {
  return {
    Id: f.Id,
    Name: f.Name,
    Properties: {
      Description: f.Description,
      Difficulty: f.Difficulty,
      MinDepth: f.MinDepth != null ? Number(f.MinDepth) : null,
      TimeOfDay: f.TimeOfDay,
      Weight: f.MatWeight != null ? Number(f.MatWeight) : null,
      Economy: {
        MaxTT: f.MatValue != null ? Number(f.MatValue) : null,
      },
      Biomes: rel.biomesByFish[f.Id] || [],
      RodTypes: rel.rodTypesByFish[f.Id] || [],
    },
    Sizes: rel.sizesByFish[f.Id] || [],
    Species: f.SpeciesName ? {
      Name: f.SpeciesName,
      Properties: {
        CodexBaseCost: f.SpeciesCodexBaseCost != null ? Number(f.SpeciesCodexBaseCost) : null,
        CodexType: f.SpeciesCodexType ?? null
      },
      Links: { "$Url": `/mobspecies/${f.SpeciesId}` }
    } : null,
    FishOil: f.FishOilName ? {
      Name: f.FishOilName,
      Links: { "$Url": `/items/${f.FishOilItemId}` }
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

const CACHE_KEYS = ['Fish', 'FishSizes', 'FishBiomes', 'FishPlanets', 'FishRodTypes', 'MobSpecies', 'Planets', 'Materials'];

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

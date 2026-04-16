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
  if (ids.length === 0) return { planetsByFish: {}, rodTypesByFish: {}, sizesByFish: {}, biomesByFish: {}, locationsByFish: {} };

  const [planetsRes, rodRes, sizesRes, biomesRes, sectorsRes] = await Promise.all([
    pool.query(
      `SELECT fp."FishId", p."Id" AS "PlanetId", p."Name" AS "PlanetName",
              p."Width" AS "PlanetWidth", p."Height" AS "PlanetHeight"
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
    pool.query(
      `SELECT fsl."FishId", fsl."PlanetId", p."Name" AS "PlanetName",
              p."Width" AS "PlanetWidth", p."Height" AS "PlanetHeight",
              fsl."SectorCol", fsl."SectorRow", fsl."Rarity", fsl."Note"
       FROM ONLY "FishSectorLocations" fsl
       JOIN ONLY "Planets" p ON p."Id" = fsl."PlanetId"
       WHERE fsl."FishId" = ANY($1::int[])`,
      [ids]
    ),
  ]);

  const planetsByFish = {};
  for (const r of planetsRes.rows) {
    (planetsByFish[r.FishId] ||= []).push({
      Name: r.PlanetName,
      Width: r.PlanetWidth,
      Height: r.PlanetHeight,
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

  const locationsByFish = {};
  for (const r of sectorsRes.rows) {
    const fishLocs = (locationsByFish[r.FishId] ||= []);
    let planet = fishLocs.find(p => p.PlanetName === r.PlanetName);
    if (!planet) {
      planet = { PlanetName: r.PlanetName, Width: r.PlanetWidth, Height: r.PlanetHeight, Sectors: [] };
      fishLocs.push(planet);
    }
    planet.Sectors.push({
      Col: r.SectorCol,
      Row: r.SectorRow,
      Rarity: r.Rarity,
      Note: r.Note || null,
    });
  }

  return { planetsByFish, rodTypesByFish, sizesByFish, biomesByFish, locationsByFish };
}

function formatFish(f, rel) {
  return {
    Id: f.Id,
    Name: f.Name,
    Properties: {
      Description: f.Description,
      Difficulty: f.Difficulty,
      MinDepth: f.MinDepth != null ? Number(f.MinDepth) : null,
      TimesOfDay: Array.isArray(f.TimeOfDay) ? f.TimeOfDay : (f.TimeOfDay ? f.TimeOfDay.replace(/[{}]/g, '').split(',').filter(Boolean) : []),
      Weight: 0.01,
      Economy: {
        MaxTT: 0.01,
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
    Locations: rel.locationsByFish[f.Id] || [],
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

const FISH_LOCATION_CACHE_KEYS = ['Fish', 'FishSectorLocations', 'FishPlanets', 'Planets'];

async function getFishLocationsByPlanet(planetName) {
  const { rows } = await pool.query(`
    SELECT fsl."FishId", fsl."SectorCol" AS "Col", fsl."SectorRow" AS "Row",
           fsl."Rarity", fsl."Note",
           f."Name" AS "FishName", f."Difficulty" AS "FishDifficulty",
           p."Width" AS "PlanetWidth", p."Height" AS "PlanetHeight"
    FROM ONLY "FishSectorLocations" fsl
    JOIN ONLY "Fish" f ON f."Id" = fsl."FishId"
    JOIN ONLY "Planets" p ON p."Id" = fsl."PlanetId"
    WHERE p."Name" = $1
    ORDER BY fsl."SectorCol", fsl."SectorRow", f."Name"
  `, [planetName]);

  const sectors = {};
  let planetWidth = 0, planetHeight = 0;
  for (const r of rows) {
    const key = `${r.Col},${r.Row}`;
    if (!sectors[key]) {
      sectors[key] = { Col: r.Col, Row: r.Row, Fish: [] };
    }
    sectors[key].Fish.push({
      Id: r.FishId,
      Name: r.FishName,
      Rarity: r.Rarity,
      Difficulty: r.FishDifficulty,
      Note: r.Note || null,
      Links: { "$Url": `/fishes/${r.FishId}` }
    });
    planetWidth = r.PlanetWidth;
    planetHeight = r.PlanetHeight;
  }

  return {
    Width: planetWidth,
    Height: planetHeight,
    Sectors: Object.values(sectors)
  };
}

async function getAllFishLocations() {
  const { rows } = await pool.query(`
    SELECT fsl."FishId", fsl."PlanetId", fsl."SectorCol" AS "Col", fsl."SectorRow" AS "Row",
           fsl."Rarity", fsl."Note",
           f."Name" AS "FishName", f."Difficulty" AS "FishDifficulty",
           p."Name" AS "PlanetName", p."Width" AS "PlanetWidth", p."Height" AS "PlanetHeight"
    FROM ONLY "FishSectorLocations" fsl
    JOIN ONLY "Fish" f ON f."Id" = fsl."FishId"
    JOIN ONLY "Planets" p ON p."Id" = fsl."PlanetId"
    ORDER BY p."Name", fsl."SectorCol", fsl."SectorRow", f."Name"
  `);

  const byPlanet = {};
  for (const r of rows) {
    if (!byPlanet[r.PlanetName]) {
      byPlanet[r.PlanetName] = { Width: r.PlanetWidth, Height: r.PlanetHeight, Sectors: {} };
    }
    const planet = byPlanet[r.PlanetName];
    const key = `${r.Col},${r.Row}`;
    if (!planet.Sectors[key]) {
      planet.Sectors[key] = { Col: r.Col, Row: r.Row, Fish: [] };
    }
    planet.Sectors[key].Fish.push({
      Id: r.FishId,
      Name: r.FishName,
      Rarity: r.Rarity,
      Difficulty: r.FishDifficulty,
      Note: r.Note || null,
      Links: { "$Url": `/fishes/${r.FishId}` }
    });
  }

  const result = {};
  for (const [name, data] of Object.entries(byPlanet)) {
    result[name] = { Width: data.Width, Height: data.Height, Sectors: Object.values(data.Sectors) };
  }
  return result;
}

const CACHE_KEYS = ['Fish', 'FishSizes', 'FishBiomes', 'FishSectorLocations', 'FishPlanets', 'FishRodTypes', 'MobSpecies', 'Planets', 'Materials'];

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

  app.get('/fish-locations', async (req, res) => {
    try {
      const planet = req.query.planet;
      if (planet) {
        const data = await withCache(`/fish-locations/${planet}`, FISH_LOCATION_CACHE_KEYS, () => getFishLocationsByPlanet(planet));
        res.json(data);
      } else {
        const data = await withCache('/fish-locations', FISH_LOCATION_CACHE_KEYS, getAllFishLocations);
        res.json(data);
      }
    } catch (e) {
      console.error('Failed to fetch fish locations', e);
      res.status(500).json({ error: 'Failed to fetch fish locations' });
    }
  });
}

module.exports = { register, getAllFish, getFish, formatFish };

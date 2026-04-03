const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds } = require('./utils');
const { getMobLoots, formatMobLoot } = require('./mobloots');
const { getMobMaturities, formatMobMaturity } = require('./mobmaturities');
const { getLocations } = require('./locations');
const { ITEM_TABLES } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

// Match legacy query to include species and profession names; CodexType replaces IsCat4Codex
const baseQuery = 'SELECT "Mobs".*, "MobSpecies"."Name" AS "Species", "MobSpecies"."CodexBaseCost" AS "CodexBaseCost", "MobSpecies"."CodexType" AS "CodexType", "Planets"."Name" AS "Planet", d."Name" AS "DefensiveProfession" FROM ONLY "Mobs" LEFT JOIN ONLY "Planets" ON "Mobs"."PlanetId" = "Planets"."Id" LEFT JOIN ONLY "MobSpecies" ON "Mobs"."SpeciesId" = "MobSpecies"."Id" LEFT JOIN ONLY "Professions" d ON "Mobs"."DefensiveProfessionId" = d."Id"';

// Cache Investigator professions to restore ScanningProfession links without reading ScanningProfessionId from Mobs
let investigatorCache = null; // { [Name]: { Id, Name } }
async function ensureInvestigatorCache() {
  if (investigatorCache) return investigatorCache;
  const names = ['Animal Investigator', 'Mutant Investigator', 'Robot Investigator'];
  const { rows } = await pool.query(
    'SELECT "Id", "Name" FROM ONLY "Professions" WHERE "Name" IN ($1,$2,$3)',
    names
  );
  investigatorCache = {};
  for (const r of rows) investigatorCache[r.Name] = { Id: r.Id, Name: r.Name };
  return investigatorCache;
}

async function loadRelated(mobs){
  const ids = mobs.map(m => m.Id);
  const mobIdSet = new Set(ids);

  async function getMobSpawnsFromLocations() {
    if (ids.length === 0) return {};

    const locations = await getLocations({
      types: ['Area'],
      areaTypes: ['MobArea'],
    });
    if (!Array.isArray(locations) || locations.length === 0) return {};

    const byMob = {};
    for (const location of locations) {
      const maturities = Array.isArray(location?.Maturities) ? location.Maturities : [];
      if (maturities.length === 0) continue;

      const coordinates = location?.Properties?.Coordinates || {};
      const planetName = typeof location?.Planet?.Name === 'string' ? location.Planet.Name : null;
      const planetTechnicalName = typeof location?.Planet?.Properties?.TechnicalName === 'string'
        ? location.Planet.Properties.TechnicalName
        : null;
      const spawn = {
        Id: location.Id,
        Name: location.Name,
        Properties: {
          Description: location?.Properties?.Description ?? null,
          Density: location?.Properties?.Density ?? null,
          IsShared: location?.Properties?.IsShared === true || location?.Properties?.IsShared === 1,
          IsEvent: location?.Properties?.IsEvent === true || location?.Properties?.IsEvent === 1,
          RecurringEventId: location?.Properties?.RecurringEventId ?? null,
          Notes: location?.Properties?.Notes ?? null,
          Type: location?.Properties?.AreaType ?? null,
          Shape: location?.Properties?.Shape ?? null,
          Data: location?.Properties?.Data ?? null,
          Coordinates: {
            Longitude: coordinates.Longitude ?? null,
            Latitude: coordinates.Latitude ?? null,
            Altitude: coordinates.Altitude ?? null
          }
        },
        Planet: location?.Planet ? {
          Name: planetName,
          Properties: {
            TechnicalName: planetTechnicalName
          },
          Links: location.Planet.Links || { "$Url": null }
        } : null,
        Maturities: maturities,
        // Keep legacy link for response contract compatibility.
        Links: { "$Url": `/mobspawns/${location.Id}` }
      };

      const seenMobIds = new Set();
      for (const entry of maturities) {
        const url = entry?.Maturity?.Mob?.Links?.$Url;
        const match = typeof url === 'string' ? url.match(/\/mobs\/(\d+)$/) : null;
        const mobId = match ? Number(match[1]) : null;
        if (!Number.isFinite(mobId) || !mobIdSet.has(mobId) || seenMobIds.has(mobId)) continue;
        seenMobIds.add(mobId);
        (byMob[mobId] ||= []).push(spawn);
      }
    }
    return byMob;
  }

  return {
    Loots: await getMobLoots(ids),
    Maturities: await getMobMaturities(ids),
    Spawns: await getMobSpawnsFromLocations()
  };
}

function getScanningProfessionFromType(type) {
  if (!type) return null;
  const t = String(type).toLowerCase();
  if (t === 'animal') return 'Animal Investigator';
  if (t === 'mutant') return 'Mutant Investigator';
  if (t === 'robot') return 'Robot Investigator';
  if (t === 'asteroid') return null;
  return null; // Unknown types do not map to a scanning profession
}

function formatMob(m, rel, classIds){
  const scanningName = getScanningProfessionFromType(m.Type);
  const investigators = investigatorCache || {};
  const investigator = scanningName ? investigators[scanningName] : null;
  return {
    Id: m.Id,
    ClassId: classIds[m.Id] || null,
    Name: m.Name,
    Type: m.Type ?? null,
    Properties: {
      Description: m.Description,
      AttackRange: m.AttackRange != null ? Number(m.AttackRange) : null,
      AggressionRange: m.AggressionRange != null ? Number(m.AggressionRange) : null,
      AggressionTimer: m.AggressionTimer || null,
      AttacksPerMinute: m.AttacksPerMinute != null ? Number(m.AttacksPerMinute) : null,
      IsSweatable: m.Sweatable === 1,
    },
    DefensiveProfession: m.DefensiveProfession ? { Name: m.DefensiveProfession, Links: { "$Url": `/professions/${m.DefensiveProfessionId}` } } : null,
    // Keep ScanningProfession in the response for compatibility, now derived from Type and without links
    ScanningProfession: (() => {
      if (!scanningName) return null;
      const sp = { Name: scanningName };
      if (investigator) sp.Links = { "$Url": `/professions/${investigator.Id}` };
      return sp;
    })(),
    Planet: m.Planet ? { Name: m.Planet, Links: { "$Url": `/planets/${m.PlanetId}` } } : null,
    Species: m.Species ? { Name: m.Species, Properties: { CodexBaseCost: m.CodexBaseCost != null ? Number(m.CodexBaseCost) : null, CodexType: m.CodexType ?? null }, Links: { "$Url": `/mobspecies/${m.SpeciesId}` } } : null,
    Maturities: (rel.Maturities[m.Id]||[]).map(formatMobMaturity),
    Spawns: (rel.Spawns[m.Id]||[]).map(sp => ({
      Id: sp.Id,
      Name: sp.Name,
      Properties: {
        Description: sp?.Properties?.Description ?? null,
        Density: sp?.Properties?.Density ?? null,
        IsShared: sp?.Properties?.IsShared === true || sp?.Properties?.IsShared === 1,
        IsEvent: sp?.Properties?.IsEvent === true || sp?.Properties?.IsEvent === 1,
        RecurringEventId: sp?.Properties?.RecurringEventId ?? null,
        Notes: sp?.Properties?.Notes ?? null,
        Type: sp?.Properties?.Type ?? null,
        Shape: sp?.Properties?.Shape ?? null,
        Data: sp?.Properties?.Data ?? null,
        Coordinates: {
          Longitude: sp?.Properties?.Coordinates?.Longitude ?? null,
          Latitude: sp?.Properties?.Coordinates?.Latitude ?? null,
          Altitude: sp?.Properties?.Coordinates?.Altitude ?? null
        }
      },
      Planet: sp.Planet ? {
        Name: typeof sp.Planet?.Name === 'string' ? sp.Planet.Name : null,
        Properties: {
          TechnicalName: typeof sp.Planet?.Properties?.TechnicalName === 'string' ? sp.Planet.Properties.TechnicalName : null
        },
        Links: sp.Planet?.Links || { "$Url": null }
      } : null,
      Maturities: Array.isArray(sp.Maturities) ? sp.Maturities : [],
      Links: { "$Url": `/mobspawns/${sp.Id}` }
    })),
    Loots: (rel.Loots[m.Id]||[]).map(formatMobLoot),
    Links: { "$Url": `/mobs/${m.Id}` }
  };
}

async function getMobs(){ await ensureInvestigatorCache(); const { rows } = await pool.query(baseQuery); const [rel, classIds] = await Promise.all([loadRelated(rows), loadClassIds('Mob', rows.map(r=>r.Id))]); return rows.map(r=>formatMob(r,rel,classIds)); }
async function getMob(idOrName){ await ensureInvestigatorCache(); const row = await getObjectByIdOrName(baseQuery,'Mobs',idOrName); if(!row) return null; const [rel, classIds] = await Promise.all([loadRelated([row]), loadClassIds('Mob', [row.Id])]); return formatMob(row,rel,classIds); }
function register(app){
  /**
   * @swagger
   * /mobs:
   *  get:
   *    description: Get all mobs
   *    responses:
   *      '200':
   *        description: A list of mobs
   */
  app.get('/mobs', async (req,res)=>{
    try {
      if (res.headersSent || res.writableEnded) return;
      const data = await withCache('/mobs', ['Mobs', 'MobSpecies', 'Planets', 'Professions', 'MobLoots', 'MobMaturities', 'MobSpawns', 'Locations', 'Areas', 'MobSpawnMaturities', 'ClassIds', ...ITEM_TABLES], getMobs);
      if (!res.headersSent) res.json(data);
    } catch (e) {
      if (!res.headersSent) res.status(500).json({ error: 'Failed to fetch mobs' });
    }
  });
  /**
   * @swagger
   * /mobs/{mob}:
   *  get:
   *    description: Get a mob by name or id
   *    parameters:
   *      - in: path
   *        name: mob
   *        schema:
   *          type: string
   *        required: true
   *    responses:
   *      '200':
   *        description: The mob
   *      '404':
   *        description: Mob not found
   */
  app.get('/mobs/:mob', async (req,res)=>{
    try {
      if (res.headersSent || res.writableEnded) return;
      const r = await withCachedLookup('/mobs', ['Mobs', 'MobSpecies', 'Planets', 'Professions', 'MobLoots', 'MobMaturities', 'MobSpawns', 'Locations', 'Areas', 'MobSpawnMaturities', 'ClassIds', ...ITEM_TABLES], getMobs, req.params.mob);
      if (r) {
        if (!res.headersSent) res.json(r);
      } else {
        if (!res.headersSent) res.status(404).send();
      }
    } catch (e) {
      if (!res.headersSent) res.status(500).json({ error: 'Failed to fetch mob' });
    }
  });
}
module.exports = { register, getMobs, getMob, formatMob, loadRelated, ensureInvestigatorCache };

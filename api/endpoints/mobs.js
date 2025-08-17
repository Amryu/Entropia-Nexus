const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { getMobLoots, formatMobLoot } = require('./mobloots');
const { getMobMaturities, formatMobMaturity } = require('./mobmaturities');
const { getMobSpawns } = require('./mobspawns');

// Match legacy query to include species and profession names
const baseQuery = 'SELECT "Mobs".*, "MobSpecies"."Name" AS "Species", "MobSpecies"."CodexBaseCost" AS "CodexBaseCost", "MobSpecies"."IsCat4Codex" AS "IsCat4Codex", "Planets"."Name" AS "Planet", d."Name" AS "DefensiveProfession", s."Name" AS "ScanningProfession" FROM ONLY "Mobs" LEFT JOIN ONLY "Planets" ON "Mobs"."PlanetId" = "Planets"."Id" LEFT JOIN ONLY "MobSpecies" ON "Mobs"."SpeciesId" = "MobSpecies"."Id" LEFT JOIN ONLY "Professions" d ON "Mobs"."DefensiveProfessionId" = d."Id" LEFT JOIN ONLY "Professions" s ON "Mobs"."ScanningProfessionId" = s."Id"';

async function loadRelated(mobs){
  const ids = mobs.map(m=>m.Id);
  return {
    Loots: await getMobLoots(ids),
    Maturities: await getMobMaturities(ids),
    Spawns: await getMobSpawns(ids)
  };
}

function formatMob(m, rel){
  return {
    Id: m.Id,
    Name: m.Name,
    Properties: {
      Description: m.Description,
      AttackRange: m.AttackRange != null ? Number(m.AttackRange) : null,
      AggressionRange: m.AggressionRange,
      IsSweatable: m.Sweatable === 1,
    },
    DefensiveProfession: m.DefensiveProfession ? { Name: m.DefensiveProfession, Links: { "$Url": `/professions/${m.DefensiveProfessionId}` } } : null,
    ScanningProfession: m.ScanningProfession ? { Name: m.ScanningProfession, Links: { "$Url": `/professions/${m.ScanningProfessionId}` } } : null,
    Planet: m.Planet ? { Name: m.Planet, Links: { "$Url": `/planets/${m.PlanetId}` } } : null,
    Species: m.Species ? { Name: m.Species, Properties: { CodexBaseCost: m.CodexBaseCost != null ? Number(m.CodexBaseCost) : null, IsCat4Codex: m.IsCat4Codex === 1 }, Links: { "$Url": `/mobspecies/${m.SpeciesId}` } } : null,
    Maturities: (rel.Maturities[m.Id]||[]).map(formatMobMaturity),
    Spawns: (rel.Spawns[m.Id]||[]).map(sp=>({
      Id: sp.Id,
      Name: sp.Name,
      Properties: {
        Description: sp.Description,
        Density: sp.Density,
        IsShared: sp.IsShared === 1 || sp.IsShared === true,
        IsEvent: sp.IsEvent === 1 || sp.IsEvent === true,
        Notes: sp.Notes,
        Type: sp.AreaType,
        Shape: sp.Shape,
        Data: sp.Data,
        Coordinates: { Longitude: sp.Longitude, Latitude: sp.Latitude, Altitude: sp.Altitude }
      },
      Planet: sp.Planet ? { 
        Name: sp.Planet, 
        Properties: { TechnicalName: sp.TechnicalName },
        Links: { "$Url": `/planets/${sp.PlanetId}` } 
      } : null,
      Maturities: Array.isArray(sp.Maturities) ? sp.Maturities : [],
      Links: { "$Url": `/mobspawns/${sp.Id}` }
    })),
  Loots: (rel.Loots[m.Id]||[]).map(formatMobLoot),
    Links: { "$Url": `/mobs/${m.Id}` }
  };
}

async function getMobs(){ const { rows } = await pool.query(baseQuery); const rel = await loadRelated(rows); return rows.map(r=>formatMob(r,rel)); }
async function getMob(idOrName){ const row = await getObjectByIdOrName(baseQuery,'Mobs',idOrName); if(!row) return null; const rel = await loadRelated([row]); return formatMob(row,rel); }
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
      const data = await getMobs();
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
      const r = await getMob(req.params.mob);
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
module.exports = { register, getMobs, getMob };

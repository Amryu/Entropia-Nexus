const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { getMobLoots, formatLoot } = require('./mobloots');
const { getMobMaturities } = require('./mobmaturities');
const { getMobSpawns } = require('./mobspawns');

// Match legacy query to include species and profession names
const baseQuery = 'SELECT "Mobs".*, "MobSpecies"."Name" AS "Species", "MobSpecies"."CodexBaseCost" AS "CodexBaseCost", "MobSpecies"."IsCat4Codex" AS "IsCat4Codex", "Planets"."Name" AS "Planet", d."Name" AS "DefensiveProfession", s."Name" AS "ScanningProfession" FROM ONLY "Mobs" LEFT JOIN ONLY "Planets" ON "Mobs"."PlanetId" = "Planets"."Id" LEFT JOIN ONLY "MobSpecies" ON "Mobs"."SpeciesId" = "MobSpecies"."Id" LEFT JOIN ONLY "Professions" d ON "Mobs"."DefensiveProfessionId" = d."Id" LEFT JOIN ONLY "Professions" s ON "Mobs"."ScanningProfessionId" = s."Id"';

async function loadRelated(mobs){ const ids = mobs.map(m=>m.Id); return { Loots: await getMobLoots(ids), Maturities: await getMobMaturities(ids), Spawns: await getMobSpawns(ids) }; }

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
    Maturities: (rel.Maturities[m.Id]||[]).map(mat=>({ Name: mat.Maturity, Properties: { Health: mat.Health != null ? Number(mat.Health) : null, Damage: mat.Damage != null ? Number(mat.Damage) : null, Level: mat.Level != null ? Number(mat.Level) : null } })),
    Spawns: (rel.Spawns[m.Id]||[]).map(sp=>({ Area: sp.AreaName ? { Name: sp.AreaName, Links: { "$Url": `/areas/${sp.AreaId}` } } : null, Planet: sp.Planet ? { Name: sp.Planet, Links: { "$Url": `/planets/${sp.PlanetId}` } } : null, Density: sp.Density })),
    Loots: (rel.Loots[m.Id]||[]).map(formatLoot),
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
  app.get('/mobs', async (req,res)=>{ res.json(await getMobs()); });
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
  app.get('/mobs/:mob', async (req,res)=>{ const r = await getMob(req.params.mob); if(r) res.json(r); else res.status(404).send(); });
}
module.exports = { register, getMobs, getMob };

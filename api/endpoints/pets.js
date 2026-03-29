const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');

// Use legacy query fields (Planet join); Mount mission isn't in legacy, so omit it for now
const query = 'SELECT "Pets".*, "Planets"."Name" AS "Planet" FROM ONLY "Pets" LEFT JOIN ONLY "Planets" ON "Pets"."PlanetId" = "Planets"."Id"';

async function getEffects(ids){ if(ids.length===0) return {}; const { rows } = await pool.query(`SELECT "PetEffects".*, "Effects"."Id" AS "EffectId", "Effects"."Name" AS "EffectName", "Effects"."Unit" AS "Unit", "Effects"."Description" AS "Description" FROM ONLY "PetEffects" INNER JOIN ONLY "Effects" ON "PetEffects"."EffectId" = "Effects"."Id" WHERE "PetEffects"."PetId" = ANY($1::int[])`, [ids]); return rows.reduce((a,r)=>{ (a[r.PetId] ||= []).push(r); return a; },{}); }

function formatEffect(x){ return { Id: x.EffectId, Name: x.EffectName, Properties: { Strength: x.Strength != null ? Number(x.Strength) : null, Unit: x.Unit, Description: x.Description, NutrioConsumptionPerHour: x.Consumption != null ? Number(x.Consumption) : null, Unlock: { Level: x.UnlockLevel != null ? Number(x.UnlockLevel) : null, CostPED: x.UnlockPED != null ? Number(x.UnlockPED) : null, CostEssence: x.UnlockEssence != null ? Number(x.UnlockEssence) : null, CostRareEssence: x.UnlockRareEssence != null ? Number(x.UnlockRareEssence) : null, Criteria: x.UnlockCriteria, CriteriaValue: x.UnlockCriteriaValue != null ? Number(x.UnlockCriteriaValue) : null } }, Links: { "$Url": `/effects/${x.EffectId}` } }; }

function formatPet(p, data){
  const effects = (data.Effects[p.Id]||[]).map(formatEffect);
  const itemId = p.Id + idOffsets.Pets;
  const props = data.ItemProps[itemId];
  return {
    Id: p.Id,
    ClassId: data.ClassIds[p.Id] || null,
    ItemId: itemId,
    Name: p.Name,
    Properties: {
      Description: p.Description,
      Rarity: p.Rarity,
      TrainingDifficulty: p.Training,
      NutrioCapacity: p.NutrioCapacity != null ? Number(p.NutrioCapacity) : null,
      NutrioConsumptionPerHour: p.NutrioConsumption != null ? Number(p.NutrioConsumption) : null,
      ExportableLevel: p.Exportable != null ? Number(p.Exportable) : null,
      TamingLevel: p.TamingLevel != null ? Number(p.TamingLevel) : null,
      Description: p.Description,
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Planet: p.Planet ? { Name: p.Planet, Links: { "$Url": `/planets/${p.PlanetId}` } } : null,
    Effects: effects,
    Links: { "$Url": `/pets/${p.Id}` },
  };
}

async function getPets(){ const { rows } = await pool.query(query); const itemIds = rows.map(r => r.Id + idOffsets.Pets); const [effects, classIds, itemProps] = await Promise.all([getEffects(rows.map(r=>r.Id)), loadClassIds('Pet', rows.map(r=>r.Id)), loadItemProperties(itemIds)]); const data = { Effects: effects, ClassIds: classIds, ItemProps: itemProps }; return rows.map(r=>formatPet(r,data)); }
async function getPet(idOrName){ const row = await getObjectByIdOrName(query,'Pets',idOrName); if(!row) return null; const itemId = row.Id + idOffsets.Pets; const [effects, classIds, itemProps] = await Promise.all([getEffects([row.Id]), loadClassIds('Pet', [row.Id]), loadItemProperties([itemId])]); const data = { Effects: effects, ClassIds: classIds, ItemProps: itemProps }; return formatPet(row,data); }
function register(app){
  /**
   * @swagger
   * /pets:
   *  get:
   *    description: Get all pets
   *    responses:
   *      '200':
   *        description: A list of pets
   */
  app.get('/pets', async (req,res)=>{ res.json(await withCache('/pets', ['Pets', 'ClassIds', 'ItemProperties'], getPets)); });
  /**
   * @swagger
   * /pets/{pet}:
   *  get:
   *    description: Get a pet by name or id
   *    parameters:
   *      - in: path
   *        name: pet
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the pet
   *    responses:
   *      '200':
   *        description: The pet
   *      '404':
   *        description: Pet not found
   */
  app.get('/pets/:pet', async (req,res)=>{ const r = await withCachedLookup('/pets', ['Pets', 'ClassIds', 'ItemProperties'], getPets, req.params.pet); if(r) res.json(r); else res.status(404).send(); });
}
module.exports = { register, getPets, getPet, formatPet };

const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');
const {
  loadEffectsOnEquipByItemIds,
  loadEffectsOnUseByItemIds,
} = require('./effects-utils');
const { getTiersByItemIds } = require('./tiers');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { MedicalTools: 'SELECT * FROM ONLY "MedicalTools"' };

// Tiers are loaded via shared helper from tiers.js

function formatMedicalTool(x, data){
  const itemId = x.Id + idOffsets.MedicalTools;
  const effectsOnUse = data.EffectsOnUse[itemId] || [];
  const effectsOnEquip = data.EffectsOnEquip[itemId] || [];
  const tiers = data.Tiers[itemId] || [];
  return {
    Id: x.Id,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight != null ? Number(x.Weight) : null,
      MaxHeal: x.Heal != null ? Number(x.Heal) : null,
      MinHeal: x.StartInterval != null ? Number(x.StartInterval) : null,
      UsesPerMinute: x.Uses != null ? Number(x.Uses) : null,
      Economy: {
        MaxTT: x.MaxTT != null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT != null ? Number(x.MinTT) : null,
        Decay: x.Decay != null ? Number(x.Decay) : null,
      },
      Skill: {
        LearningIntervalStart: x.MinLvl != null ? Number(x.MinLvl) : null,
        LearningIntervalEnd: x.MaxLvl != null ? Number(x.MaxLvl) : null,
        IsSiB: (x.SIB === 1) || (x.SiB === 1),
      },
    },
    EffectsOnUse: effectsOnUse,
    EffectsOnEquip: effectsOnEquip,
    Tiers: tiers,
    Links: { "$Url": `/medicaltools/${x.Id}` },
  };
}

async function getMedicalTools(){
  const { rows } = await pool.query(queries.MedicalTools);
  const ids = rows.map(r=>r.Id);
  const itemIds = ids.map(id => id + idOffsets.MedicalTools);
  const data = {
    EffectsOnUse: await loadEffectsOnUseByItemIds(itemIds),
    EffectsOnEquip: await loadEffectsOnEquipByItemIds(itemIds),
    Tiers: await getTiersByItemIds(itemIds, 0)
  };
  return rows.map(r => formatMedicalTool(r, data));
}
async function getMedicalTool(idOrName){
  const row = await getObjectByIdOrName(queries.MedicalTools, 'MedicalTools', idOrName);
  if (!row) return null;
  const id = row.Id;
  const itemIds = [id + idOffsets.MedicalTools];
  const data = {
    EffectsOnUse: await loadEffectsOnUseByItemIds(itemIds),
    EffectsOnEquip: await loadEffectsOnEquipByItemIds(itemIds),
    Tiers: await getTiersByItemIds(itemIds, 0)
  };
  return formatMedicalTool(row, data);
}

function register(app){
  /**
   * @swagger
   * /medicaltools:
   *  get:
   *    description: Get all medical tools
   *    responses:
   *      '200':
   *        description: A list of medical tools
   */
  app.get('/medicaltools', async (req,res) => { res.json(await withCache('/medicaltools', ['MedicalTools', 'EffectsOnEquip', 'EffectsOnUse', 'Effects', 'Tiers', 'TierMaterials'], getMedicalTools)); });
  /**
   * @swagger
   * /medicaltools/{medicalTool}:
   *  get:
   *    description: Get a medical tool by name or id
   *    parameters:
   *      - in: path
   *        name: medicalTool
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the medical tool
   *    responses:
   *      '200':
   *        description: The medical tool
   *      '404':
   *        description: Medical tool not found
   */
  app.get('/medicaltools/:medicalTool', async (req,res) => { const r = await withCachedLookup('/medicaltools', ['MedicalTools', 'EffectsOnEquip', 'EffectsOnUse', 'Effects', 'Tiers', 'TierMaterials'], getMedicalTools, req.params.medicalTool); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getMedicalTools, getMedicalTool, formatMedicalTool };

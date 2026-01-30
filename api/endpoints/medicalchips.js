const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');
const {
  loadEffectsOnEquipByItemIds,
  loadEffectsOnUseByItemIds,
} = require('./effects-utils');

const queries = {
  MedicalChips: 'SELECT "MedicalChips".*, "Materials"."Name" AS "Ammo" FROM ONLY "MedicalChips" LEFT JOIN ONLY "Materials" ON "MedicalChips"."AmmoId" = "Materials"."Id"',
};



function formatMedicalChip(x, data){
  const itemId = x.Id + idOffsets.MedicalChips;
  const effectsOnUse = data.EffectsOnUse[itemId] || [];
  const effectsOnEquip = data.EffectsOnEquip[itemId] || [];
  return {
    Id: x.Id,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Range: x.Range != null ? Number(x.Range) : null,
      Weight: x.Weight != null ? Number(x.Weight) : null,
      MaxHeal: x.Heal != null ? Number(x.Heal) : null,
      MinHeal: x.StartInterval != null ? Number(x.StartInterval) : null,
      UsesPerMinute: x.Uses != null ? Number(x.Uses) : null,
      Skill: {
        LearningIntervalStart: x.MinLvl != null ? Number(x.MinLvl) : null,
        LearningIntervalEnd: x.MaxLvl != null ? Number(x.MaxLvl) : null,
        IsSiB: (x.SIB === 1) || (x.SiB === 1) || (x.IsSib === 1),
      },
      Mindforce: {
        Level: x.Level != null ? Number(x.Level) : null,
        Concentration: x.Concentration != null ? Number(x.Concentration) : null,
        Cooldown: x.Cooldown != null ? Number(x.Cooldown) : null,
        CooldownGroup: x.CooldownGroup != null ? Number(x.CooldownGroup) : null,
      },
      Economy: {
        MaxTT: x.MaxTT != null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT != null ? Number(x.MinTT) : null,
        Decay: x.Decay != null ? Number(x.Decay) : null,
        AmmoBurn: x.AmmoBurn != null ? Number(x.AmmoBurn) : null,
      },
    },
    EffectsOnUse: effectsOnUse,
    EffectsOnEquip: effectsOnEquip,
    Ammo: x.AmmoId ? { Name: x.Ammo, Links: { "$Url": `/materials/${x.AmmoId}` } } : null,
    Links: { "$Url": `/medicalchips/${x.Id}` },
  };
}

async function getMedicalChips(){
  const { rows } = await pool.query(queries.MedicalChips);
  const ids = rows.map(r=>r.Id);
  const itemIds = ids.map(id => id + idOffsets.MedicalChips);
  const data = { EffectsOnUse: await loadEffectsOnUseByItemIds(itemIds), EffectsOnEquip: await loadEffectsOnEquipByItemIds(itemIds) };
  return rows.map(r => formatMedicalChip(r, data));
}

async function getMedicalChip(idOrName){
  const row = await getObjectByIdOrName(queries.MedicalChips, 'MedicalChips', idOrName);
  if (!row) return null;
  const id = row.Id;
  const itemIds = [id + idOffsets.MedicalChips];
  const data = { EffectsOnUse: await loadEffectsOnUseByItemIds(itemIds), EffectsOnEquip: await loadEffectsOnEquipByItemIds(itemIds) };
  return formatMedicalChip(row, data);
}

function register(app){
  /**
   * @swagger
   * /medicalchips:
   *  get:
   *    description: Get all medical chips
   *    responses:
   *      '200':
   *        description: A list of medical chips
   */
  app.get('/medicalchips', async (req,res) => { res.json(await getMedicalChips()); });
  /**
   * @swagger
   * /medicalchips/{medicalChip}:
   *  get:
   *    description: Get a medical chip by name or id
   *    parameters:
   *      - in: path
   *        name: medicalChip
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the medical chip
   *    responses:
   *      '200':
   *        description: The medical chip
   *      '404':
   *        description: Medical chip not found
   */
  app.get('/medicalchips/:medicalChip', async (req,res) => { const r = await getMedicalChip(req.params.medicalChip); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getMedicalChips, getMedicalChip, formatMedicalChip };

const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName } = require('./utils');
const { loadEffectsOnEquipByItemIds } = require('./effects-utils');

const queries = { WeaponVisionAttachments: 'SELECT * FROM ONLY "WeaponVisionAttachments"' };

function formatWeaponVisionAttachment(x, effectsMap){
  const itemId = x.Id + idOffsets.WeaponVisionAttachments;
  const effects = effectsMap[itemId] ?? [];
  return {
    Id: x.Id,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Type: x.Type,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      SkillModification: x.SkillMod !== null ? Number(x.SkillMod) : null,
      SkillBonus: x.SkillBonus !== null ? Number(x.SkillBonus) : null,
      Zoom: x.Zoom !== null ? Number(x.Zoom) : null,
      Economy: {
        Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      }
    },
    EffectsOnEquip: effects,
    Links: { "$Url": `/weaponvisionattachments/${x.Id}` },
  };
}

async function getWeaponVisionAttachments(){
  const { rows } = await pool.query(queries.WeaponVisionAttachments);
  const itemIds = rows.map(r => r.Id + idOffsets.WeaponVisionAttachments);
  const effects = await loadEffectsOnEquipByItemIds(itemIds);
  return rows.map(r => formatWeaponVisionAttachment(r, effects));
}

async function getWeaponVisionAttachment(idOrName){
  const row = await getObjectByIdOrName(queries.WeaponVisionAttachments,'WeaponVisionAttachments',idOrName);
  if(!row) return null;
  const itemId = row.Id + idOffsets.WeaponVisionAttachments;
  const effects = await loadEffectsOnEquipByItemIds([itemId]);
  return formatWeaponVisionAttachment(row, effects);
}

function register(app){
  /**
   * @swagger
   * /weaponvisionattachments:
   *  get:
   *    description: Get all weapon vision attachments
   *    responses:
   *      '200':
   *        description: A list of weapon vision attachments
   */
  app.get('/weaponvisionattachments', async (req,res)=>{
    res.json(await getWeaponVisionAttachments());
  });
  /**
   * @swagger
   * /weaponvisionattachments/{weaponVisionAttachment}:
   *  get:
   *    description: Get a weapon vision attachment by name or id
   *    parameters:
   *      - in: path
   *        name: weaponVisionAttachment
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the weapon vision attachment
   *    responses:
   *      '200':
   *        description: The weapon vision attachment
   *      '404':
   *        description: Weapon vision attachment not found
   */
  app.get('/weaponvisionattachments/:weaponVisionAttachment', async (req,res)=>{
    const r = await getWeaponVisionAttachment(req.params.weaponVisionAttachment);
    if(r) res.json(r); else res.status(404).send();
  });
}
module.exports = { register, getWeaponVisionAttachments, getWeaponVisionAttachment, formatWeaponVisionAttachment };

const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { loadEffectsOnEquipByItemIds } = require('./effects-utils');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { WeaponVisionAttachments: 'SELECT * FROM ONLY "WeaponVisionAttachments"' };

function formatWeaponVisionAttachment(x, effectsMap, classIds, itemProps){
  const itemId = x.Id + idOffsets.WeaponVisionAttachments;
  const effects = effectsMap[itemId] ?? [];
  const props = itemProps[itemId];
  return {
    Id: x.Id,
    ClassId: classIds[x.Id] || null,
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
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    EffectsOnEquip: effects,
    Links: { "$Url": `/weaponvisionattachments/${x.Id}` },
  };
}

async function getWeaponVisionAttachments(){
  const { rows } = await pool.query(queries.WeaponVisionAttachments);
  const itemIds = rows.map(r => r.Id + idOffsets.WeaponVisionAttachments);
  const [effects, classIds, itemProps] = await Promise.all([
    loadEffectsOnEquipByItemIds(itemIds),
    loadClassIds('WeaponVisionAttachment', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  return rows.map(r => formatWeaponVisionAttachment(r, effects, classIds, itemProps));
}

async function getWeaponVisionAttachment(idOrName){
  const row = await getObjectByIdOrName(queries.WeaponVisionAttachments,'WeaponVisionAttachments',idOrName);
  if(!row) return null;
  const itemId = row.Id + idOffsets.WeaponVisionAttachments;
  const [effects, classIds, itemProps] = await Promise.all([
    loadEffectsOnEquipByItemIds([itemId]),
    loadClassIds('WeaponVisionAttachment', [row.Id]),
    loadItemProperties([itemId])
  ]);
  return formatWeaponVisionAttachment(row, effects, classIds, itemProps);
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
    res.json(await withCache('/weaponvisionattachments', ['WeaponVisionAttachments', 'ClassIds', 'ItemProperties'], getWeaponVisionAttachments));
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
    const r = await withCachedLookup('/weaponvisionattachments', ['WeaponVisionAttachments', 'ClassIds', 'ItemProperties'], getWeaponVisionAttachments, req.params.weaponVisionAttachment);
    if(r) res.json(r); else res.status(404).send();
  });
}
module.exports = { register, getWeaponVisionAttachments, getWeaponVisionAttachment, formatWeaponVisionAttachment };

const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName, getObjects } = require('./utils');

const queries = { WeaponVisionAttachments: 'SELECT * FROM ONLY "WeaponVisionAttachments"' };

async function getEffectsOnEquip(ids){
  if(ids.length===0) return {};
  const { rows } = await pool.query(`SELECT "EffectsOnEquip".*, "Effects"."Name", "Effects"."Unit" FROM ONLY "EffectsOnEquip" INNER JOIN ONLY "Effects" ON "EffectsOnEquip"."EffectId" = "Effects"."Id" WHERE "EffectsOnEquip"."ItemId" IN (${ids.map(x=>x+idOffsets.WeaponVisionAttachments).join(',')})`);
  return rows.reduce((a,r)=>{ (a[r.ItemId] ||= []).push(r); return a; },{});
}
function formatEffectOnEquip(x){ return { Effect: { Name: x.Name, Properties: { Unit: x.Unit }, Links: { "$Url": `/effects/${x.EffectId}` } }, Strength: x.Strength != null ? Number(x.Strength) : null }; }
function formatWeaponVisionAttachment(x,data){
  const effects = (data[x.Id + idOffsets.WeaponVisionAttachments]||[]).map(formatEffectOnEquip);
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.WeaponVisionAttachments,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Type: x.Type,
      Weight: x.Weight != null ? Number(x.Weight) : null,
      SkillModification: x.SkillMod != null ? Number(x.SkillMod) : null,
      SkillBonus: x.SkillBonus != null ? Number(x.SkillBonus) : null,
      Zoom: x.Zoom != null ? Number(x.Zoom) : null,
      Economy: {
        Efficiency: x.Efficiency != null ? Number(x.Efficiency) : null,
        MaxTT: x.MaxTT != null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT != null ? Number(x.MinTT) : null,
        Decay: x.Decay != null ? Number(x.Decay) : null,
      }
    },
    EffectsOnEquip: effects,
    Links: { "$Url": `/weaponvisionattachments/${x.Id}` },
  };
}
async function getWeaponVisionAttachments(){ const rows = await getObjects(queries.WeaponVisionAttachments,x=>x); const data = await getEffectsOnEquip(rows.map(r=>r.Id)); return rows.map(r=>formatWeaponVisionAttachment(r,data)); }
async function getWeaponVisionAttachment(idOrName){ const row = await getObjectByIdOrName(queries.WeaponVisionAttachments,'WeaponVisionAttachments',idOrName); if(!row) return null; const data = await getEffectsOnEquip([row.Id]); return formatWeaponVisionAttachment(row,data); }
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
module.exports = { register, getWeaponVisionAttachments, getWeaponVisionAttachment };

const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName } = require('./utils');
const { loadEffectsOnEquipByItemIds, loadEffectsOnUseByItemIds } = require('./effects-utils');
const { getTiersByItemIds } = require('./tiers');

const queries = { Weapons: 'SELECT "Weapons".*, "VehicleAttachmentTypes"."Name" AS "AttachmentType", "Materials"."Name" AS "Ammo", hit."Name" AS "ProfessionHit", dmg."Name" AS "ProfessionDmg" FROM ONLY "Weapons" LEFT JOIN ONLY "VehicleAttachmentTypes" ON "Weapons"."AttachmentTypeId" = "VehicleAttachmentTypes"."Id" LEFT JOIN ONLY "Materials" ON "Weapons"."AmmoId" = "Materials"."Id" LEFT JOIN ONLY "Professions" hit ON "Weapons"."ProfessionHitId" = hit."Id" LEFT JOIN ONLY "Professions" dmg ON "Weapons"."ProfessionDmgId" = dmg."Id"' };

function formatWeapon(x,data){
  const itemId = x.Id + idOffsets.Weapons;
  const equip = data.EffectsOnEquip[itemId] || [];
  const use = data.EffectsOnUse[itemId] || [];
  const tiers = data.Tiers[itemId] || [];
  return {
    Id: x.Id,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight != null ? Number(x.Weight) : null,
      Type: x.Type,
      Category: x.Category,
      Class: x.Class,
      UsesPerMinute: x.Attacks != null ? Number(x.Attacks) : null,
      Range: x.Range != null ? Number(x.Range) : null,
      ImpactRadius: x.ImpactRadius != null ? Number(x.ImpactRadius) : null,
      Mindforce: x.Class === 'Mindforce' ? {
        Level: x.MFLevel != null ? Number(x.MFLevel) : null,
        Concentration: x.Concentration != null ? Number(x.Concentration) : null,
        Cooldown: x.Cooldown != null ? Number(x.Cooldown) : null,
        CooldownGroup: x.CooldownGroup != null ? Number(x.CooldownGroup) : null,
      } : null,
      Economy: {
        Efficiency: x.Efficiency != null ? Number(x.Efficiency) : null,
        MaxTT: x.MaxTT != null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT != null ? Number(x.MinTT) : null,
        Decay: x.Decay != null ? Number(x.Decay) : null,
        AmmoBurn: x.AmmoBurn != null ? Number(x.AmmoBurn) : null,
      },
      Damage: {
        Stab: x.Stab != null ? Number(x.Stab) : null,
        Cut: x.Cut != null ? Number(x.Cut) : null,
        Impact: x.Impact != null ? Number(x.Impact) : null,
        Penetration: x.Penetration != null ? Number(x.Penetration) : null,
        Shrapnel: x.Shrapnel != null ? Number(x.Shrapnel) : null,
        Burn: x.Burn != null ? Number(x.Burn) : null,
        Cold: x.Cold != null ? Number(x.Cold) : null,
        Acid: x.Acid != null ? Number(x.Acid) : null,
        Electric: x.Electric != null ? Number(x.Electric) : null,
      },
      Skill: {
        Hit: { LearningIntervalStart: x.MinHit != null ? Number(x.MinHit) : null, LearningIntervalEnd: x.MaxHit != null ? Number(x.MaxHit) : null },
        Dmg: { LearningIntervalStart: x.MinDmg != null ? Number(x.MinDmg) : null, LearningIntervalEnd: x.MaxDmg != null ? Number(x.MaxDmg) : null },
        IsSiB: x.SIB === 1,
      },
    },
    Ammo: x.Ammo ? { Name: x.Ammo, Links: { "$Url": `/materials/${x.AmmoId}` } } : null,
    ProfessionHit: { Name: x.ProfessionHit, Links: { "$Url": `/professions/${x.ProfessionHitId}` } },
    ProfessionDmg: { Name: x.ProfessionDmg, Links: { "$Url": `/professions/${x.ProfessionDmgId}` } },
  AttachmentType: { Name: x.AttachmentType, Links: { "$Url": x.AttachmentTypeId ? `/vehicleattachmenttypes/${x.AttachmentTypeId}` : null } },
    EffectsOnEquip: equip,
    EffectsOnUse: use,
    Tiers: tiers,
    Links: { "$Url": `/weapons/${x.Id}` },
  };
}
async function getWeapons(){
  const { rows } = await pool.query(queries.Weapons);
  const itemIds = rows.map(r => r.Id + idOffsets.Weapons);
  const [equip, use, tiers] = await Promise.all([
    loadEffectsOnEquipByItemIds(itemIds),
    loadEffectsOnUseByItemIds(itemIds),
    getTiersByItemIds(itemIds, 0)
  ]);
  const data = { EffectsOnEquip: equip, EffectsOnUse: use, Tiers: tiers };
  return rows.map(r=>formatWeapon(r,data));
}
async function getWeapon(idOrName){
  const row = await getObjectByIdOrName(queries.Weapons,'Weapons',idOrName); if(!row) return null;
  const itemId = row.Id + idOffsets.Weapons;
  const [equip, use, tiers] = await Promise.all([
    loadEffectsOnEquipByItemIds([itemId]),
    loadEffectsOnUseByItemIds([itemId]),
    getTiersByItemIds([itemId], 0)
  ]);
  const data = { EffectsOnEquip: equip, EffectsOnUse: use, Tiers: tiers };
  return formatWeapon(row,data);
}
function register(app){
  /**
   * @swagger
   * /weapons:
   *  get:
   *    description: Get all weapons
   *    responses:
   *      '200':
   *        description: A list of weapons
   */
  app.get('/weapons', async (req,res)=>{ res.json(await getWeapons()); });
  /**
   * @swagger
   * /weapons/{weapon}:
   *  get:
   *    description: Get a weapon by name or id
   *    parameters:
   *      - in: path
   *        name: weapon
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the weapon
   *    responses:
   *      '200':
   *        description: The weapon
   *      '404':
   *        description: Weapon not found
   */
  app.get('/weapons/:weapon', async (req,res)=>{ const r = await getWeapon(req.params.weapon); if(r) res.json(r); else res.status(404).send(); });
}
module.exports = { register, getWeapons, getWeapon };

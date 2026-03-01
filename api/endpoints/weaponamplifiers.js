const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName, loadClassIds } = require('./utils');
const { loadEffectsOnEquipByItemIds } = require('./effects-utils');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  WeaponAmplifiers: 'SELECT * FROM ONLY "WeaponAmplifiers"',
};

function formatWeaponAmplifier(x, effectsMap, classIds){
  const itemId = x.Id + idOffsets.WeaponAmplifiers;
  const effects = effectsMap[itemId] ?? [];
  return {
    Id: x.Id,
    ClassId: classIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Economy: {
        Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
        AmmoBurn: x.Ammo !== null ? Number(x.Ammo) : null
      },
      Damage: {
        Stab: x.Stab !== null ? Number(x.Stab) : null,
        Cut: x.Cut !== null ? Number(x.Cut) : null,
        Impact: x.Impact !== null ? Number(x.Impact) : null,
        Penetration: x.Penetration !== null ? Number(x.Penetration) : null,
        Shrapnel: x.Shrapnel !== null ? Number(x.Shrapnel) : null,
        Burn: x.Burn !== null ? Number(x.Burn) : null,
        Cold: x.Cold !== null ? Number(x.Cold) : null,
        Acid: x.Acid !== null ? Number(x.Acid) : null,
        Electric: x.Electric !== null ? Number(x.Electric) : null,
      }
    },
    EffectsOnEquip: effects,
    Links: { "$Url": `/weaponamplifiers/${x.Id}` }
  };
}

async function getWeaponAmplifiers(){
  const { rows } = await pool.query(queries.WeaponAmplifiers);
  const itemIds = rows.map(r => r.Id + idOffsets.WeaponAmplifiers);
  const [effects, classIds] = await Promise.all([
    loadEffectsOnEquipByItemIds(itemIds),
    loadClassIds('WeaponAmplifier', rows.map(r => r.Id))
  ]);
  return rows.map(r => formatWeaponAmplifier(r, effects, classIds));
}

async function getWeaponAmplifier(idOrName){
  const row = await getObjectByIdOrName(queries.WeaponAmplifiers, 'WeaponAmplifiers', idOrName);
  if (!row) return null;
  const itemId = row.Id + idOffsets.WeaponAmplifiers;
  const [effects, classIds] = await Promise.all([
    loadEffectsOnEquipByItemIds([itemId]),
    loadClassIds('WeaponAmplifier', [row.Id])
  ]);
  return formatWeaponAmplifier(row, effects, classIds);
}

function register(app){
  /**
   * @swagger
   * /weaponamplifiers:
   *  get:
   *    description: Get all weapon amplifiers
   *    responses:
   *      '200':
   *        description: A list of weapon amplifiers
   */
  app.get('/weaponamplifiers', async (req,res) => {
    res.json(await withCache('/weaponamplifiers', ['WeaponAmplifiers', 'ClassIds'], getWeaponAmplifiers));
  });
  /**
   * @swagger
   * /weaponamplifiers/{weaponAmplifier}:
   *  get:
   *    description: Get a weapon amplifier by name or id
   *    parameters:
   *      - in: path
   *        name: weaponAmplifier
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the weapon amplifier
   *    responses:
   *      '200':
   *        description: The weapon amplifier
   *      '404':
   *        description: Weapon amplifier not found
   */
  app.get('/weaponamplifiers/:weaponAmplifier', async (req,res) => {
    const r = await withCachedLookup('/weaponamplifiers', ['WeaponAmplifiers', 'ClassIds'], getWeaponAmplifiers, req.params.weaponAmplifier);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getWeaponAmplifiers, getWeaponAmplifier, formatWeaponAmplifier };

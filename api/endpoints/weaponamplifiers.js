const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName } = require('./utils');

const queries = {
  WeaponAmplifiers: 'SELECT * FROM ONLY "WeaponAmplifiers"',
  EffectsOnEquip: 'SELECT * FROM ONLY "EffectsOnEquip" WHERE "ItemId" IN ($1:csv)'
};

function _formatEffectOnEquip(x){
  return { Property: x.Property, Amount: x.Amount !== null ? Number(x.Amount) : null };
}

function formatWeaponAmplifier(x, effects){
  const list = (effects[x.Id + idOffsets.WeaponAmplifiers] ?? []).map(_formatEffectOnEquip);
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.WeaponAmplifiers,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Economy: { Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null, MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null, MinTT: x.MinTT !== null ? Number(x.MinTT) : null, Decay: x.Decay !== null ? Number(x.Decay) : null, AmmoBurn: x.Ammo !== null ? Number(x.Ammo) : null },
      Damage: { Stab: x.Stab, Cut: x.Cut, Impact: x.Impact, Penetration: x.Penetration, Shrapnel: x.Shrapnel, Burn: x.Burn, Cold: x.Cold, Acid: x.Acid, Electric: x.Electric }
    },
    EffectsOnEquip: list,
    Links: { "$Url": `/weaponamplifiers/${x.Id}` }
  };
}

async function _getEffectsOnEquip(ids){
  if (ids.length === 0) return {};
  const pgp = require('pg-promise')();
  const { rows } = await pool.query(pgp.as.format(queries.EffectsOnEquip, [ids.map(x => x + idOffsets.WeaponAmplifiers)]));
  return rows.reduce((acc,r)=> { (acc[r.ItemId] ||= []).push(r); return acc; }, {});
}

async function getWeaponAmplifiers(){
  const { rows } = await pool.query(queries.WeaponAmplifiers);
  const effects = await _getEffectsOnEquip(rows.map(r=>r.Id));
  return rows.map(r => formatWeaponAmplifier(r, effects));
}

async function getWeaponAmplifier(idOrName){
  const row = await getObjectByIdOrName(queries.WeaponAmplifiers, 'WeaponAmplifiers', idOrName);
  if (!row) return null;
  const effects = await _getEffectsOnEquip([row.Id]);
  return formatWeaponAmplifier(row, effects);
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
    res.json(await getWeaponAmplifiers());
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
    const r = await getWeaponAmplifier(req.params.weaponAmplifier);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getWeaponAmplifiers, getWeaponAmplifier };

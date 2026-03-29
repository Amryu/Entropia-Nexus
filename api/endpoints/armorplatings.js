const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  ArmorPlatings: 'SELECT * FROM ONLY "ArmorPlatings"',
};

function toNumberOrNull(v) {
  return v === null || v === undefined ? null : Number(v);
}

function formatArmorPlating(x, data){
  const itemId = x.Id + idOffsets.ArmorPlatings;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: toNumberOrNull(x.Weight),
      Economy: {
        MaxTT: toNumberOrNull(x.MaxTT),
        MinTT: toNumberOrNull(x.MinTT),
        Durability: toNumberOrNull(x.Durability),
      },
      Defense: {
        Block: toNumberOrNull(x.Block),
        Stab: toNumberOrNull(x.Stab),
        Cut: toNumberOrNull(x.Cut),
        Impact: toNumberOrNull(x.Impact),
        Penetration: toNumberOrNull(x.Penetration),
        Shrapnel: toNumberOrNull(x.Shrapnel),
        Burn: toNumberOrNull(x.Burn),
        Cold: toNumberOrNull(x.Cold),
        Acid: toNumberOrNull(x.Acid),
        Electric: toNumberOrNull(x.Electric),
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Links: { "$Url": `/armorplatings/${x.Id}` }
  };
}

async function getArmorPlatings() {
  const { rows } = await pool.query(queries.ArmorPlatings);
  const classIds = await loadClassIds('ArmorPlating', rows.map(r => r.Id));
  return rows.map(r => formatArmorPlating(r, classIds));
}
const getArmorPlating = async (idOrName) => { const row = await getObjectByIdOrName(queries.ArmorPlatings, 'ArmorPlatings', idOrName); if (!row) return null; const classIds = await loadClassIds('ArmorPlating', [row.Id]); return formatArmorPlating(row, classIds); };

function register(app){
  /**
   * @swagger
   * /armorplatings:
   *  get:
   *    description: Get all armor platings
   *    responses:
   *      '200':
   *        description: A list of armor platings
   */
  app.get('/armorplatings', async (req,res) => { res.json(await withCache('/armorplatings', ['ArmorPlatings', 'ClassIds'], getArmorPlatings)); });
  /**
   * @swagger
   * /armorplatings/{armorPlating}:
   *  get:
   *    description: Get an armor plating by name or id
   *    parameters:
   *      - in: path
   *        name: armorPlating
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the armor plating
   *    responses:
   *      '200':
   *        description: The armor plating
   *      '404':
   *        description: Armor plating not found
   */
  app.get('/armorplatings/:armorPlating', async (req,res) => { const r = await withCachedLookup('/armorplatings', ['ArmorPlatings', 'ClassIds'], getArmorPlatings, req.params.armorPlating); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getArmorPlatings, getArmorPlating, formatArmorPlating };

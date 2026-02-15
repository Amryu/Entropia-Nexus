const { getObjects, getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  ArmorPlatings: 'SELECT * FROM ONLY "ArmorPlatings"',
};

function toNumberOrNull(v) {
  return v === null || v === undefined ? null : Number(v);
}

function formatArmorPlating(x){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.ArmorPlatings,
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
      }
    },
    Links: { "$Url": `/armorplatings/${x.Id}` }
  };
}

const getArmorPlatings = () => getObjects(queries.ArmorPlatings, formatArmorPlating);
const getArmorPlating = async (idOrName) => { const row = await getObjectByIdOrName(queries.ArmorPlatings, 'ArmorPlatings', idOrName); return row ? formatArmorPlating(row) : null; };

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
  app.get('/armorplatings', async (req,res) => { res.json(await withCache('/armorplatings', ['ArmorPlatings'], getArmorPlatings)); });
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
  app.get('/armorplatings/:armorPlating', async (req,res) => { const r = await withCachedLookup('/armorplatings', ['ArmorPlatings'], getArmorPlatings, req.params.armorPlating); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getArmorPlatings, getArmorPlating, formatArmorPlating };

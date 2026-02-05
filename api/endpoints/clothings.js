const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName, generateGenderAliases } = require('./utils');
const { loadEffectsOnEquipByItemIds, loadSetEffectsByItemIdsFromEquipSets, formatEffectOnSetEquip } = require('./effects-utils');

const queries = { Clothings: 'SELECT * FROM ONLY "Clothes"' };

function toNumberOrNull(v){ return v === null || v === undefined ? null : Number(v); }

function formatClothing(x, effectsByItemId, setEffectsByItemId){
  const itemId = x.Id + idOffsets.Clothings;
  const onEquip = effectsByItemId[itemId] || [];
  const onSetRaw = setEffectsByItemId[itemId] || [];
  const setBlock = onSetRaw.length ? {
    Name: onSetRaw[0].SetName,
    EffectsOnSetEquip: onSetRaw.map(formatEffectOnSetEquip),
    Links: { "$Url": `/equipsets/${onSetRaw[0].SetId}` }
  } : null;
  const aliases = generateGenderAliases(x.Name, x.Gender);

  return {
    Id: x.Id,
    ItemId: itemId,
    Name: x.Name,
    Aliases: aliases.length > 0 ? aliases : undefined,
    Properties: {
      Description: x.Description,
      Weight: toNumberOrNull(x.Weight),
      Gender: x.Gender,
      Type: x.Type,
      Slot: x.Slot,
      Economy: {
        MaxTT: toNumberOrNull(x.MaxTT),
        MinTT: toNumberOrNull(x.MinTT),
      }
    },
    Set: setBlock,
    EffectsOnEquip: onEquip,
    Links: { "$Url": `/clothings/${x.Id}` }
  };
}

async function getClothings(){
  const { rows } = await pool.query(queries.Clothings);
  const itemIds = rows.map(r => r.Id + idOffsets.Clothings);
  const [effectsByItemId, setEffectsByItemId] = await Promise.all([
    loadEffectsOnEquipByItemIds(itemIds),
    loadSetEffectsByItemIdsFromEquipSets(itemIds)
  ]);
  return rows.map(r => formatClothing(r, effectsByItemId, setEffectsByItemId));
}

async function getClothing(idOrName){
  const row = await getObjectByIdOrName(queries.Clothings, 'Clothes', idOrName);
  if (!row) return null;
  const itemId = row.Id + idOffsets.Clothings;
  const [effectsByItemId, setEffectsByItemId] = await Promise.all([
    loadEffectsOnEquipByItemIds([itemId]),
    loadSetEffectsByItemIdsFromEquipSets([itemId])
  ]);
  return formatClothing(row, effectsByItemId, setEffectsByItemId);
}

function register(app){
  /**
   * @swagger
   * /clothings:
   *  get:
   *    description: Get all clothings
   *    responses:
   *      '200':
   *        description: A list of clothings
   */
  app.get('/clothings', async (req,res) => { res.json(await getClothings()); });
  /**
   * @swagger
   * /clothings/{clothing}:
   *  get:
   *    description: Get a clothing by name or id
   *    parameters:
   *      - in: path
   *        name: clothing
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the clothing
   *    responses:
   *      '200':
   *        description: The clothing
   *      '404':
   *        description: Clothing not found
   */
  app.get('/clothings/:clothing', async (req,res) => { const r = await getClothing(req.params.clothing); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getClothings, getClothing, formatClothing };

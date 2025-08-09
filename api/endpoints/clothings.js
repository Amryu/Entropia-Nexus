const pgp = require('pg-promise')();
const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');

const ID_OFFSET = 8000000;

const queries = {
  Clothings: 'SELECT * FROM ONLY "Clothes"',
  EffectsOnEquip: `SELECT e."Id", e."Name", e."Unit", e."Description", eo."Strength", eo."ItemId" FROM ONLY "EffectsOnEquip" eo INNER JOIN ONLY "Effects" e ON eo."EffectId" = e."Id" WHERE eo."ItemId" IN ($1:csv)`,
  EffectsOnSetEquip: `SELECT e."Id", e."Name", e."Unit", ese."Strength", ese."MinSetPieces", esi."EquipSetId" + 100000 AS "SetId", es."Name" AS "SetName", esi."ItemId"
                     FROM ONLY "EffectsOnSetEquip" ese
                     INNER JOIN ONLY "EquipSetItems" esi ON ese."SetId" = esi."EquipSetId" + 100000
                     INNER JOIN ONLY "EquipSets" es ON ese."SetId" = es."Id" + 100000
                     INNER JOIN ONLY "Effects" e ON ese."EffectId" = e."Id"
                     WHERE esi."ItemId" IN ($1:csv)`,
};

function formatEffectOnEquip(x){ return { Name: x.Name, Values: { Strength: x.Strength !== null ? Number(x.Strength) : null, Unit: x.Unit, Description: x.Description }, Links: { "$Url": `/effects/${x.Id}` } }; }
function formatEffectOnSetEquip(x){ return { Name: x.Name, Values: { Strength: x.Strength !== null ? Number(x.Strength) : null, MinSetPieces: x.MinSetPieces !== null ? Number(x.MinSetPieces) : null, Unit: x.Unit }, Links: { "$Url": `/effects/${x.Id}` } }; }

function formatClothing(x, effects, effectsOnSet){
  const itemId = x.Id + ID_OFFSET;
  return {
    Id: x.Id,
    ItemId: itemId,
    Name: x.Name,
    Properties: { Description: x.Description, Weight: x.Weight !== null ? Number(x.Weight) : null, Gender: x.Gender, Type: x.Type, Slot: x.Slot, Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null, MinTT: x.MinTT !== null ? Number(x.MinTT) : null } },
    Set: (effectsOnSet[itemId]?.length ? { Name: effectsOnSet[itemId][0].SetName, EffectsOnSetEquip: effectsOnSet[itemId].map(formatEffectOnSetEquip), Links: { "$Url": `/equipsets/${effectsOnSet[itemId][0].SetId - 100000}` } } : null),
    EffectsOnEquip: (effects[itemId] || []).map(formatEffectOnEquip),
    Links: { "$Url": `/clothings/${x.Id}` }
  };
}

async function _getEffects(ids){ if (!ids.length) return [{},{}]; const itemIds = ids.map(id => id + ID_OFFSET); const [{ rows: equip }, { rows: set } ] = await Promise.all([
  pool.query(pgp.as.format(queries.EffectsOnEquip, [itemIds])), pool.query(pgp.as.format(queries.EffectsOnSetEquip, [ids]))
]); return [equip.reduce((a,r)=>{(a[r.ItemId] ||= []).push(r); return a;},{}), set.reduce((a,r)=>{(a[r.ItemId] ||= []).push(r); return a;},{} )]; }

async function getClothings(){ const { rows } = await pool.query(queries.Clothings); const [onEquip, onSet] = await _getEffects(rows.map(r=>r.Id)); return rows.map(r => formatClothing(r, onEquip, onSet)); }
async function getClothing(idOrName){ const row = await getObjectByIdOrName(queries.Clothings, 'Clothes', idOrName); if (!row) return null; const [onEquip, onSet] = await _getEffects([row.Id]); return formatClothing(row, onEquip, onSet); }

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

module.exports = { register, getClothings, getClothing };

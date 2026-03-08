const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { ITEM_TABLES } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  EquipSets: 'SELECT * FROM ONLY "EquipSets"',
  EquipSetItems: 'SELECT esi."EquipSetId" AS "EquipSetId", i.* FROM ONLY "EquipSetItems" esi INNER JOIN ONLY "Items" i ON esi."ItemId" = i."Id" WHERE esi."EquipSetId" = ANY($1::int[])',
  EffectsOnSetEquip: 'SELECT ese."SetId", e."Id" AS "EffectId", e."Name", e."Unit", ese."Strength", ese."MinSetPieces" FROM ONLY "EffectsOnSetEquip" ese INNER JOIN ONLY "Effects" e ON ese."EffectId" = e."Id" WHERE ese."SetId" = ANY($1::int[])',
};

function formatItem(x){
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: { Type: x.Type, Economy: { MaxTT: x.Value !== null ? Number(x.Value) : null } },
    Links: { "$Url": `/${x.Type.toLowerCase()}s/${x.Id % 100000}` }
  };
}

function formatEffectOnSetEquip(x){
  return { Name: x.Name, Values: { Strength: x.Strength !== null ? Number(x.Strength) : null, MinSetPieces: x.MinSetPieces !== null ? Number(x.MinSetPieces) : null, Unit: x.Unit }, Links: { "$Url": `/effects/${x.EffectId}` } };
}

function formatEquipSet(x, items, effects){
  return { Id: x.Id, Name: x.Name, Items: (items[x.Id]||[]).map(formatItem), EffectsOnSetEquip: (effects[x.Id+100000]||[]).map(formatEffectOnSetEquip), Links: { "$Url": `/equipsets/${x.Id}` } };
}

async function _getData(ids){
  if (!ids.length) return { items:{}, effects:{} };
  const setIds = ids.map(id=>id+100000);
  const [itemsRes, effRes] = await Promise.all([
    pool.query(queries.EquipSetItems, [ids]),
    pool.query(queries.EffectsOnSetEquip, [setIds])
  ]);
  const items = itemsRes.rows.reduce((acc,r)=>{ (acc[r.EquipSetId] ||= []).push(r); return acc; },{});
  const eff = effRes.rows.reduce((acc,r)=>{ (acc[r.SetId] ||= []).push(r); return acc; },{});
  return { items, effects: eff };
}

async function getEquipSets(){
  const { rows } = await pool.query(queries.EquipSets);
  const data = await _getData(rows.map(r=>r.Id));
  return rows.map(r => formatEquipSet(r, data.items, data.effects));
}

async function getEquipSet(idOrName){
  const row = await getObjectByIdOrName(queries.EquipSets, 'EquipSets', idOrName);
  if (!row) return null;
  const data = await _getData([row.Id]);
  return formatEquipSet(row, data.items, data.effects);
}

function register(app){
  /**
   * @swagger
   * /equipsets:
   *  get:
   *    description: Get all equip sets
   *    responses:
   *      '200':
   *        description: A list of equip sets
   */
  app.get('/equipsets', async (req,res) => { res.json(await withCache('/equipsets', ['EquipSets', 'EquipSetItems', ...ITEM_TABLES, 'EffectsOnSetEquip', 'Effects'], getEquipSets)); });
  /**
   * @swagger
   * /equipsets/{equipSet}:
   *  get:
   *    description: Get an equip set by name or id
   *    parameters:
   *      - in: path
   *        name: equipSet
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the equip set
   *    responses:
   *      '200':
   *        description: The equip set
   *      '404':
   *        description: Equip set not found
   */
  app.get('/equipsets/:equipSet', async (req,res) => { const r = await withCachedLookup('/equipsets', ['EquipSets', 'EquipSetItems', ...ITEM_TABLES, 'EffectsOnSetEquip', 'Effects'], getEquipSets, req.params.equipSet); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getEquipSets, getEquipSet };

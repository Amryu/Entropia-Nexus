const { getObjectByIdOrName, loadClassIds } = require('./utils');
const { idOffsets } = require('./constants');
const { pool } = require('./dbClient');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { Strongboxes: 'SELECT * FROM ONLY "Strongboxes"' };

function groupBy(arr,key){ return arr.reduce((a,r)=>{ (a[r[key]] ||= []).push(r); return a; },{}); }
async function getLoots(ids){
  if(ids.length===0) return { Loots:{} };
  const { rows } = await pool.query(`SELECT "StrongboxLoots".*, "Items"."Name" AS "Name", "Items"."Type" AS "Type", "Items"."Value" AS "Value" FROM "StrongboxLoots" INNER JOIN ONLY "Items" ON "StrongboxLoots"."ItemId" = "Items"."Id" WHERE "StrongboxId" IN (${ids.join(',')})`);
  return { Loots: groupBy(rows,'StrongboxId') };
}
function formatLoot(x){ return { Rarity: x.Rarity, AvailableFrom: x.AvailableFrom, AvailableUntil: x.AvailableUntil, Item: { Name: x.Name, Properties: { Type: x.Type, Economy: { MaxTT: x.Value != null ? Number(x.Value) : null } }, Links: { "$Url": `/${x.Type.toLowerCase()}s/${x.ItemId % 100000}` } } }; }
function formatStrongbox(x,data){
  const loots = (data.Loots[x.Id]||[]).map(formatLoot);
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: x.Id + idOffsets.Strongboxes,
    Name: x.Name,
    Properties: { Description: x.Description },
    Loots: loots,
    Links: { "$Url": `/strongboxes/${x.Id}` },
  };
}
async function getStrongboxes(){ const { rows } = await pool.query(queries.Strongboxes); const [loots, classIds] = await Promise.all([getLoots(rows.map(r=>r.Id)), loadClassIds('Strongbox', rows.map(r=>r.Id))]); const data = { ...loots, ClassIds: classIds }; return rows.map(r=>formatStrongbox(r,data)); }
async function getStrongbox(idOrName){ const row = await getObjectByIdOrName(queries.Strongboxes,'Strongboxes',idOrName); if(!row) return null; const [loots, classIds] = await Promise.all([getLoots([row.Id]), loadClassIds('Strongbox', [row.Id])]); const data = { ...loots, ClassIds: classIds }; return formatStrongbox(row,data); }
function register(app){
  /**
   * @swagger
   * /strongboxes:
   *  get:
   *    description: Get all strongboxes
   *    responses:
   *      '200':
   *        description: A list of strongboxes
   */
  app.get('/strongboxes', async (req,res)=>{ res.json(await withCache('/strongboxes', ['Strongboxes', 'ClassIds'], getStrongboxes)); });
  /**
   * @swagger
   * /strongboxes/{strongbox}:
   *  get:
   *    description: Get a strongbox by name or id
   *    parameters:
   *      - in: path
   *        name: strongbox
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the strongbox
   *    responses:
   *      '200':
   *        description: The strongbox
   *      '404':
   *        description: Strongbox not found
   */
  app.get('/strongboxes/:strongbox', async (req,res)=>{ const r = await withCachedLookup('/strongboxes', ['Strongboxes', 'ClassIds'], getStrongboxes, req.params.strongbox); if(r) res.json(r); else res.status(404).send(); });
}
module.exports = { register, getStrongboxes, getStrongbox };

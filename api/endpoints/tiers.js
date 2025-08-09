const { pool } = require('./dbClient');
const { isId } = require('./utils');

async function getTiers(filters){
  const clauses = [];
  if(filters.ItemId){ clauses.push(`t."ItemId" = ${Number(filters.ItemId)}`); }
  if(filters.IsArmorSet != null){ clauses.push(`t."IsArmorSet" = ${Number(filters.IsArmorSet)}`); }
  if(filters.Tier != null){ clauses.push(`t."Tier" = ${Number(filters.Tier)}`); }
  const where = clauses.length ? 'WHERE '+clauses.join(' AND ') : '';
  const { rows } = await pool.query(`SELECT t.*, i."Name" AS "ItemName" FROM ONLY "Tiers" t INNER JOIN ONLY "Items" i ON t."ItemId" = i."Id" ${where}`);
  return rows.map(formatTier);
}
function formatTier(x){ return { Name: `${x.ItemName} Tier ${x.Tier}`, Properties: { Tier: x.Tier, IsArmorSet: x.IsArmorSet === 1 }, Links: { "$Url": `/tiers?ItemId=${x.ItemId}&IsArmorSet=${x.IsArmorSet}&Tier=${x.Tier}` } }; }
function validateQuery(q){ if(q.ItemId && !isId(q.ItemId)) return 'ItemId must be an integer'; if(q.IsArmorSet != null && !['0','1',0,1].includes(q.IsArmorSet)) return 'IsArmorSet must be 0 or 1'; if(q.Tier != null && !isId(q.Tier)) return 'Tier must be an integer'; return null; }
function register(app){
  /**
   * @swagger
   * /tiers:
   *  get:
   *    description: Get tiers filtered by ItemId, IsArmorSet, and Tier
   *    parameters:
   *      - in: query
   *        name: ItemId
   *        schema:
   *          type: integer
   *      - in: query
   *        name: IsArmorSet
   *        schema:
   *          type: integer
   *          enum: [0,1]
   *      - in: query
   *        name: Tier
   *        schema:
   *          type: integer
   *    responses:
   *      '200':
   *        description: A list of tiers
   */
  app.get('/tiers', async (req,res)=>{ const err = validateQuery(req.query); if(err) return res.status(400).json({ error: err }); res.json(await getTiers(req.query)); });
}
module.exports = { register, getTiers };

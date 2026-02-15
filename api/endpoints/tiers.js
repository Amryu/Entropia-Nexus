const { pool } = require('./dbClient');
const { isId } = require('./utils');
const { withCache } = require('./responseCache');

const TIER_TABLES = ['Tiers', 'TierMaterials', 'Materials', 'Items', 'ArmorSets'];

// Shared formatting helpers
function formatTierMaterial(x){
  return {
    Amount: x.Amount !== null ? Number(x.Amount) : null,
    Material: {
      Name: x.MaterialName,
      Properties: {
        Weight: x.Weight !== null ? Number(x.Weight) : null,
        Type: x.Type,
        Economy: { MaxTT: x.Value !== null ? Number(x.Value) : null }
      },
      Links: { "$Url": `/materials/${x.MaterialId}` }
    }
  };
}

function formatTierGroup(group, { includeId = false, linkStyle = 'byId' } = {}){
  const t = group[0];
  const base = {
    Name: `${t.ItemName} Tier ${t.Tier}`,
    Properties: { Tier: t.Tier, IsArmorSet: t.IsArmorSet === 1 },
    Materials: group.map(formatTierMaterial)
  };
  const withId = includeId ? { Id: t.TierId, ...base } : base;
  const link = linkStyle === 'byQuery'
    ? { "$Url": `/tiers?ItemId=${t.ItemId}&IsArmorSet=${t.IsArmorSet}&Tier=${t.Tier}` }
    : { "$Url": `/tiers/${t.TierId}` };
  return { ...withId, Links: link };
}

// Load all tier rows once — served from cache on subsequent calls
async function loadAllTierRows() {
  const sql = `SELECT t."Id" AS "TierId", t."Tier", t."ItemId", t."IsArmorSet",
                      COALESCE(s."Name", i."Name") AS "ItemName",
                      tm."MaterialId", tm."Amount",
                      m."Name" AS "MaterialName", m."Value" AS "Value", m."Weight" AS "Weight", m."Type" AS "Type"
               FROM ONLY "Tiers" t
               INNER JOIN ONLY "TierMaterials" tm ON t."Id" = tm."TierId"
               INNER JOIN ONLY "Materials" m ON tm."MaterialId" = m."Id"
               LEFT JOIN ONLY "Items" i ON t."ItemId" = i."Id"
               LEFT JOIN ONLY "ArmorSets" s ON t."ItemId" = s."Id"`;
  const { rows } = await pool.query(sql);
  return rows;
}

async function getAllTierRows() {
  return withCache('_tiers', TIER_TABLES, loadAllTierRows);
}

// Filter rows in-memory
function filterRows(allRows, filters) {
  const itemIds = Array.isArray(filters.itemIds) ? new Set(filters.itemIds.map(Number).filter(Number.isFinite)) : null;
  const ItemId = filters.ItemId != null ? Number(filters.ItemId) : undefined;
  const IsArmorSet = filters.IsArmorSet != null ? Number(filters.IsArmorSet) : undefined;
  const Tier = filters.Tier != null ? Number(filters.Tier) : undefined;

  return allRows.filter(r => {
    if (itemIds && !itemIds.has(r.ItemId)) return false;
    if (ItemId != null && r.ItemId !== ItemId) return false;
    if (IsArmorSet != null && r.IsArmorSet !== IsArmorSet) return false;
    if (Tier != null && r.Tier !== Tier) return false;
    return true;
  });
}

async function getTiers(filters){
  const allRows = await getAllTierRows();
  const rows = filterRows(allRows, filters);
  const byTier = rows.reduce((acc, r) => { (acc[r.TierId] ||= []).push(r); return acc; }, {});
  return Object.values(byTier).map(group => formatTierGroup(group, { includeId: true, linkStyle: 'byId' }));
}

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

// Helper for other endpoints: fetch tiers for multiple ItemIds and return grouped, formatted per item
async function getTiersByItemIds(itemIds, isArmorSet = 0){
  if (!Array.isArray(itemIds) || itemIds.length === 0) return {};
  const ids = itemIds.map(Number).filter(Number.isFinite);
  if (ids.length === 0) return {};
  const allRows = await getAllTierRows();
  const idSet = new Set(ids);
  const rows = allRows.filter(r => idSet.has(r.ItemId) && r.IsArmorSet === isArmorSet);
  const byItem = rows.reduce((acc,r)=>{ (acc[r.ItemId] ||= []).push(r); return acc; },{});
  const result = {};
  for (const [itemId, list] of Object.entries(byItem)){
    const byTier = list.reduce((a,r)=>{ (a[r.Tier] ||= []); a[r.Tier].push(r); return a; },{});
    result[itemId] = Object.values(byTier).map(group => formatTierGroup(group, { includeId: false, linkStyle: 'byQuery' }));
  }
  return result;
}

module.exports.getTiersByItemIds = getTiersByItemIds;

const { pool, usersPool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');

const queries = {
  Shops: 'SELECT "Estates".*, "Planets"."Name" AS "Planet", "Planets"."TechnicalName" FROM ONLY "Estates" LEFT JOIN ONLY "Planets" ON "Estates"."PlanetId" = "Planets"."Id" WHERE "Estates"."Type" = \'Shop\'',
};

async function _fetchShopOwners(ownerIds) {
  if (!ownerIds || ownerIds.length === 0) return {};
  try {
    const { rows } = await usersPool.query('SELECT id, eu_name FROM users WHERE id = ANY($1) AND verified = true', [ownerIds]);
    const map = {}; rows.forEach(r => map[r.id] = { Name: r.eu_name }); return map;
  } catch { return {}; }
}

async function _fetchEstateSections(estateIds){
  if (!estateIds || estateIds.length===0) return {};
  try {
  const { rows } = await pool.query('SELECT "EstateId", "Name", "ItemPoints" FROM ONLY "EstateSections" WHERE "EstateId" = ANY($1) ORDER BY "EstateId", "Name"', [estateIds]);
    const m = {}; for (const r of rows){ if (!m[r.EstateId]) m[r.EstateId]=[]; m[r.EstateId].push({ Name:r.Name, MaxItemPoints:r.ItemPoints }); } return m;
  } catch { return {}; }
}

async function _fetchItemNames(itemIds){
  if (!itemIds || itemIds.length===0) return {};
  const valid = [...new Set(itemIds.filter(id=>id!=null))]; if (valid.length===0) return {};
  try {
    const { rows } = await pool.query('SELECT "Id","Name" FROM ONLY "Items" WHERE "Id" = ANY($1)', [valid]);
    const m = {}; rows.forEach(r => m[r.Id] = r.Name); return m;
  } catch { return {}; }
}

async function _processInventoryRows(rows){
  const itemIds = rows.map(r=>r.item_id).filter(id=>id!=null);
  const itemNames = await _fetchItemNames(itemIds);
  const groups = new Map();
  for (const r of rows){
    if (!groups.has(r.group_id)) groups.set(r.group_id, { id:r.group_id, name:r.group_name, sort_order:r.group_sort_order, Items: [] });
    if (r.item_id){
      const name = itemNames[r.item_id] || `Item ${r.item_id}`;
      groups.get(r.group_id).Items.push({ id:r.item_table_id, item_id:r.item_id, stack_size:r.stack_size, markup:r.markup, sort_order:r.item_sort_order, Item:{ Name:name } });
    }
  }
  return Array.from(groups.values());
}

async function _fetchShopInventory(estateId){
  try {
    const { rows } = await usersPool.query(`
      SELECT g.id as group_id, g.name as group_name, g.sort_order as group_sort_order,
             i.id as item_table_id, i.item_id, i.stack_size, i.markup, i.sort_order as item_sort_order
      FROM shop_inventory_groups g
      LEFT JOIN shop_inventory_items i ON g.id = i.group_id
      WHERE g.shop_id = $1
      ORDER BY g.sort_order, i.sort_order`, [estateId]);
    return await _processInventoryRows(rows);
  } catch { return []; }
}

async function _fetchMultipleShopInventories(estateIds){
  if (!estateIds || estateIds.length===0) return {};
  try {
    const { rows } = await usersPool.query(`
      SELECT g.shop_id, g.id as group_id, g.name as group_name, g.sort_order as group_sort_order,
             i.id as item_table_id, i.item_id, i.stack_size, i.markup, i.sort_order as item_sort_order
      FROM shop_inventory_groups g
      LEFT JOIN shop_inventory_items i ON g.id = i.group_id
      WHERE g.shop_id = ANY($1)
      ORDER BY g.shop_id, g.sort_order, i.sort_order`, [estateIds]);
    const byShop = {}; for (const r of rows){ if (!byShop[r.shop_id]) byShop[r.shop_id]=[]; byShop[r.shop_id].push(r); }
    const data = {}; for (const [id, r] of Object.entries(byShop)) data[id] = await _processInventoryRows(r);
    return data;
  } catch { return {}; }
}

function formatShop(x, add = {}) {
  const out = {
    Id: x.Id,
    Name: x.Name,
    Description: x.Description,
    MaxGuests: x.MaxGuests != null ? Number(x.MaxGuests) : null,
    Coordinates: {
      Longitude: x.Longitude != null ? Number(x.Longitude) : null,
      Latitude: x.Latitude != null ? Number(x.Latitude) : null,
      Altitude: x.Altitude != null ? Number(x.Altitude) : null,
    },
    Planet: x.Planet ? { Name: x.Planet, Properties: { TechnicalName: x.TechnicalName }, Links: { "$Url": `/planets/${x.PlanetId}` } } : null,
    Owner: null,
    InventoryGroups: [],
    Sections: [],
    Links: { "$Url": `/shops/${x.Id}` }
  };
  if (add.owner) out.Owner = add.owner;
  if (add.inventory) out.InventoryGroups = add.inventory;
  if (add.sections) {
    out.Sections = add.sections;
    out.HasAdditionalArea = add.sections.some(s => s.Name === 'Additional');
  }
  if (add.managers) out.Managers = add.managers;
  return out;
}

// DB methods
async function getShops(){
  const { rows } = await pool.query(queries.Shops);
  const ownerIds = [...new Set(rows.map(s => s.OwnerId).filter(id => id!=null))];
  const estateIds = rows.map(s => s.Id);
  const [owners, inventories, sections] = await Promise.all([
    _fetchShopOwners(ownerIds), _fetchMultipleShopInventories(estateIds), _fetchEstateSections(estateIds)
  ]);
  return rows.map(x => formatShop(x, { owner: owners[x.OwnerId] || null, inventory: inventories[x.Id] || [], sections: sections[x.Id] || [] }));
}

async function getShop(idOrName){
  const byId = /^(\d+)$/.test(String(idOrName));
  const sql = byId ? `${queries.Shops} AND "Estates"."Id" = $1` : `${queries.Shops} AND "Estates"."Name" = $1`;
  const { rows } = await pool.query(sql, [idOrName]);
  if (rows.length !== 1) return null;
  const shop = rows[0];
  const [inventory, owners, sections] = await Promise.all([
    _fetchShopInventory(shop.Id), shop.OwnerId ? _fetchShopOwners([shop.OwnerId]) : Promise.resolve({}), _fetchEstateSections([shop.Id])
  ]);
  return formatShop(shop, { inventory, owner: owners[shop.OwnerId] || null, sections: sections[shop.Id] || [] });
}

// Endpoint wiring
function register(app){
  /**
   * @swagger
   * /shops:
   *  get:
   *    description: Get all shops
   *    responses:
   *      '200':
   *        description: A list of shops
   */
  app.get('/shops', async (req,res) => { res.json(await getShops()); });
  app.get('/shops/:shop', async (req,res) => {
    /**
     * @swagger
     * /shops/{shop}:
     *  get:
     *    description: Get a shop by name or id
     *    parameters:
     *      - in: path
     *        name: shop
     *        schema:
     *          type: string
     *        required: true
     *        description: The name or id of the shop
     *    responses:
     *      '200':
     *        description: The shop
     *      '404':
     *        description: Shop not found
     */
    const shop = await getShop(req.params.shop);
    if (shop) res.json(shop); else res.status(404).send();
  });
}

module.exports = { register, getShops, getShop };

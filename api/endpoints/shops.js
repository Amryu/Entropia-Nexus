const { pool, usersPool } = require('./dbClient');
const { withCache } = require('./responseCache');

const queries = {
  Shops: `
    SELECT l.*,
           p."Name" AS "Planet",
           p."TechnicalName",
           e."Type" AS "EstateType",
           e."OwnerId",
           e."OwnerName",
           e."ItemTradeAvailable",
           e."MaxGuests"
    FROM ONLY "Locations" l
    LEFT JOIN ONLY "Planets" p ON l."PlanetId" = p."Id"
    JOIN ONLY "Estates" e ON l."Id" = e."LocationId"
    WHERE l."Type" = 'Estate' AND e."Type" = 'Shop'
  `,
};

async function _fetchShopOwners(ownerIds) {
  if (!ownerIds || ownerIds.length === 0) return {};
  try {
    const { rows } = await usersPool.query('SELECT id, eu_name FROM users WHERE id = ANY($1) AND verified = true', [ownerIds]);
    const map = {}; rows.forEach(r => map[r.id] = { Name: r.eu_name }); return map;
  } catch { return {}; }
}

async function _fetchEstateSections(locationIds) {
  if (!locationIds || locationIds.length === 0) return {};
  try {
    const { rows } = await pool.query('SELECT "LocationId", "Name", "Description", "ItemPoints" FROM ONLY "EstateSections" WHERE "LocationId" = ANY($1) ORDER BY "LocationId", "Name"', [locationIds]);
    const m = {};
    for (const r of rows) {
      if (!m[r.LocationId]) m[r.LocationId] = [];
      m[r.LocationId].push({
        Name: r.Name,
        Description: r.Description ?? null,
        ItemPoints: r.ItemPoints != null ? Number(r.ItemPoints) : null,
        MaxItemPoints: r.ItemPoints != null ? Number(r.ItemPoints) : null
      });
    }
    return m;
  } catch { return {}; }
}

async function _fetchShopManagers(locationIds) {
  if (!locationIds || locationIds.length === 0) return {};
  try {
    const { rows } = await usersPool.query(`
      SELECT sm.shop_id, sm.user_id, u.eu_name
      FROM shop_managers sm
      INNER JOIN users u ON sm.user_id = u.id
      WHERE sm.shop_id = ANY($1) AND u.verified = true
      ORDER BY sm.shop_id, sm.added_at
    `, [locationIds]);
    const m = {};
    for (const r of rows) {
      if (!m[r.shop_id]) m[r.shop_id] = [];
      m[r.shop_id].push({ user_id: r.user_id, User: { Name: r.eu_name } });
    }
    return m;
  } catch { return {}; }
}

async function _fetchItemNames(itemIds) {
  if (!itemIds || itemIds.length === 0) return {};
  const valid = [...new Set(itemIds.filter(id => id != null))]; if (valid.length === 0) return {};
  try {
    const { rows } = await pool.query('SELECT "Id","Name" FROM ONLY "Items" WHERE "Id" = ANY($1)', [valid]);
    const m = {}; rows.forEach(r => m[r.Id] = r.Name); return m;
  } catch { return {}; }
}

async function _processInventoryRows(rows) {
  const itemIds = rows.map(r => r.item_id).filter(id => id != null);
  const itemNames = await _fetchItemNames(itemIds);
  const groups = new Map();
  for (const r of rows) {
    if (!groups.has(r.group_id)) groups.set(r.group_id, { id: r.group_id, name: r.group_name, sort_order: r.group_sort_order, Items: [] });
    if (r.item_id) {
      const name = itemNames[r.item_id] || `Item ${r.item_id}`;
      groups.get(r.group_id).Items.push({ id: r.item_table_id, item_id: r.item_id, stack_size: r.stack_size, markup: r.markup, sort_order: r.item_sort_order, Item: { Name: name } });
    }
  }
  return Array.from(groups.values());
}

async function _fetchShopInventory(locationId) {
  try {
    const { rows } = await usersPool.query(`
      SELECT g.id as group_id, g.name as group_name, g.sort_order as group_sort_order,
             i.id as item_table_id, i.item_id, i.stack_size, i.markup, i.sort_order as item_sort_order
      FROM shop_inventory_groups g
      LEFT JOIN shop_inventory_items i ON g.id = i.group_id
      WHERE g.shop_id = $1
      ORDER BY g.sort_order, i.sort_order`, [locationId]);
    return await _processInventoryRows(rows);
  } catch { return []; }
}

async function _fetchMultipleShopInventories(locationIds) {
  if (!locationIds || locationIds.length === 0) return {};
  try {
    const { rows } = await usersPool.query(`
      SELECT g.shop_id, g.id as group_id, g.name as group_name, g.sort_order as group_sort_order,
             i.id as item_table_id, i.item_id, i.stack_size, i.markup, i.sort_order as item_sort_order
      FROM shop_inventory_groups g
      LEFT JOIN shop_inventory_items i ON g.id = i.group_id
      WHERE g.shop_id = ANY($1)
      ORDER BY g.shop_id, g.sort_order, i.sort_order`, [locationIds]);
    const byShop = {}; for (const r of rows) { if (!byShop[r.shop_id]) byShop[r.shop_id] = []; byShop[r.shop_id].push(r); }
    const data = {}; for (const [id, r] of Object.entries(byShop)) data[id] = await _processInventoryRows(r);
    return data;
  } catch { return {}; }
}

function formatShop(x, add = {}) {
  // Build Owner: resolved from users DB, or direct OwnerName, or null
  const ownerName = add.owner?.Name || x.OwnerName || null;
  const owner = (x.OwnerId || ownerName) ? { Id: x.OwnerId ?? null, Name: ownerName } : null;
  const out = {
    Id: x.Id,
    Name: x.Name,
    OwnerId: x.OwnerId ?? null,
    Description: x.Description,
    MaxGuests: x.MaxGuests != null ? Number(x.MaxGuests) : null,
    Coordinates: {
      Longitude: x.Longitude != null ? Number(x.Longitude) : null,
      Latitude: x.Latitude != null ? Number(x.Latitude) : null,
      Altitude: x.Altitude != null ? Number(x.Altitude) : null,
    },
    Planet: x.Planet ? { Name: x.Planet, Properties: { TechnicalName: x.TechnicalName }, Links: { "$Url": `/planets/${x.PlanetId}` } } : null,
    Owner: owner,
    InventoryGroups: [],
    Sections: [],
    Links: { "$Url": `/shops/${x.Id}` }
  };
  if (add.inventory) out.InventoryGroups = add.inventory;
  if (add.sections) {
    out.Sections = add.sections;
    out.HasAdditionalArea = add.sections.some(s => s.Name === 'Additional');
  }
  if (add.managers) out.Managers = add.managers;
  return out;
}

// DB methods
async function getShops(ownerId = null) {
  const sql = ownerId != null ? `${queries.Shops} AND e."OwnerId" = $1` : queries.Shops;
  const params = ownerId != null ? [ownerId] : [];
  const { rows } = await pool.query(sql + ' ORDER BY l."Name"', params);
  const ownerIds = [...new Set(rows.map(s => s.OwnerId).filter(id => id != null))];
  const locationIds = rows.map(s => s.Id);
  const [owners, inventories, sections, managers] = await Promise.all([
    _fetchShopOwners(ownerIds), _fetchMultipleShopInventories(locationIds), _fetchEstateSections(locationIds), _fetchShopManagers(locationIds)
  ]);
  return rows.map(x => formatShop(x, { owner: owners[x.OwnerId] || null, inventory: inventories[x.Id] || [], sections: sections[x.Id] || [], managers: managers[x.Id] || [] }));
}

async function getShop(idOrName) {
  const byId = /^(\d+)$/.test(String(idOrName));
  const sql = byId ? `${queries.Shops} AND l."Id" = $1` : `${queries.Shops} AND l."Name" = $1`;
  const { rows } = await pool.query(sql, [idOrName]);
  if (rows.length !== 1) return null;
  const shop = rows[0];
  const [inventory, owners, sections, managers] = await Promise.all([
    _fetchShopInventory(shop.Id), shop.OwnerId ? _fetchShopOwners([shop.OwnerId]) : Promise.resolve({}), _fetchEstateSections([shop.Id]), _fetchShopManagers([shop.Id])
  ]);
  return formatShop(shop, { inventory, owner: owners[shop.OwnerId] || null, sections: sections[shop.Id] || [], managers: managers[shop.Id] || [] });
}

// Endpoint wiring
function register(app) {
  /**
   * @swagger
   * /shops:
   *  get:
   *    description: Get all shops
   *    responses:
   *      '200':
   *        description: A list of shops
   */
  app.get('/shops', async (req, res) => {
    const ownerId = req.query.OwnerId != null ? Number(req.query.OwnerId) : null;
    if (req.query.OwnerId != null && !Number.isFinite(ownerId)) {
      return res.status(400).json({ error: 'OwnerId must be a number.' });
    }
    if (Number.isFinite(ownerId)) {
      res.json(await getShops(ownerId));
    } else {
      res.json(await withCache('/shops', ['Locations', 'Planets', 'Estates', 'EstateSections'], getShops));
    }
  });
  app.get('/shops/:shop', async (req, res) => {
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
    // Use getShop directly — withCachedLookup serves from the list cache which
    // can't track inventory table changes (they live in the users DB, outside
    // the nexus TableChanges mechanism), so inventory would appear stale.
    const shop = await getShop(req.params.shop);
    if (shop) res.json(shop); else res.status(404).send();
  });
}

module.exports = { register, getShops, getShop };

// Minimal listings for Acquisition: only fetch what's needed for display
async function getShopListings(items) {
  // Resolve input which may be numeric IDs or exact item names
  const nums = new Set();
  const names = new Set();
  for (const v of (items || [])) {
    const n = Number(v);
    if (Number.isFinite(n)) nums.add(n);
    else if (typeof v === 'string' && v.trim().length > 0) names.add(v.trim());
  }

  let nameIds = [];
  if (names.size > 0) {
    const { rows } = await pool.query('SELECT "Id", "Name" FROM ONLY "Items" WHERE "Name" = ANY($1)', [Array.from(names)]);
    nameIds = rows.map(r => Number(r.Id)).filter(Number.isFinite);
  }

  const ids = Array.from(new Set([...nums, ...nameIds]));
  if (ids.length === 0) return [];

  // 1) From users DB: find all (shop_id, group_name, item_id, stack_size, markup)
  const { rows: invRows } = await usersPool.query(`
    SELECT g.shop_id, g.name AS group_name, i.item_id, i.stack_size, i.markup
    FROM shop_inventory_groups g
    INNER JOIN shop_inventory_items i ON i.group_id = g.id
    WHERE i.item_id = ANY($1)
    ORDER BY g.shop_id, g.name
  `, [ids]);
  if (!invRows || invRows.length === 0) return [];

  // 2) From main DB: fetch basic shop and planet info
  const shopIds = Array.from(new Set(invRows.map(r => r.shop_id).filter(Boolean)));
  const { rows: shopRows } = await pool.query(`
    SELECT l."Id", l."Name", l."Longitude", l."Latitude", l."Altitude",
           p."Id" AS "PlanetId", p."Name" AS "Planet", p."TechnicalName"
    FROM ONLY "Locations" l
    JOIN ONLY "Estates" e ON l."Id" = e."LocationId"
    LEFT JOIN ONLY "Planets" p ON l."PlanetId" = p."Id"
    WHERE l."Id" = ANY($1) AND l."Type" = 'Estate' AND e."Type" = 'Shop'
  `, [shopIds]);
  const shopMap = new Map(shopRows.map(r => [r.Id, {
    Id: r.Id,
    Name: r.Name,
    Coordinates: {
      Longitude: r.Longitude != null ? Number(r.Longitude) : null,
      Latitude: r.Latitude != null ? Number(r.Latitude) : null,
      Altitude: r.Altitude != null ? Number(r.Altitude) : null,
    },
    Planet: r.Planet ? { Name: r.Planet, Properties: { TechnicalName: r.TechnicalName } } : null,
  }]));

  // 3) Build minimal listing entries
  const out = [];
  for (const r of invRows) {
    const shop = shopMap.get(r.shop_id);
    if (!shop) continue;
    out.push({
      Shop: shop,
      Group: { Name: r.group_name },
      ItemId: Number(r.item_id),
      StackSize: r.stack_size != null ? Number(r.stack_size) : null,
      Markup: r.markup != null ? Number(r.markup) : null,
    });
  }
  return out;
}

module.exports.getShopListings = getShopListings;

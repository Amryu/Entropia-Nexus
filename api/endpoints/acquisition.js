const { parseItemList } = require('./utils');
const blueprints = require('./blueprints');
const refining = require('./refining');
const vendoroffers = require('./vendoroffers');
const { getMobLootsForItemsOrMobs } = require('./mobloots');
const { getShopListings } = require('./shops');
const { getItemCached } = require('./itemsCache');
const { getBlueprintDropRows } = require('./blueprintdrops');

async function hydrateShopItems(list) {
  const uniqueIds = Array.from(new Set(list.map(x => x.ItemId).filter(Boolean)));
  const idToItem = {};
  await Promise.all(uniqueIds.map(async (id) => { idToItem[id] = await getItemCached(id); }));
  return list.map(x => ({ ...x, Item: idToItem[x.ItemId] || { Id: x.ItemId, Name: `Item ${x.ItemId}`, Links: { "$Url": `/items/${x.ItemId}` } } }));
}

function register(app){
  /**
   * @swagger
   * /acquisition:
   *  get:
   *    description: Get all acquisition methods for multiple items
   *    parameters:
   *      - in: query
   *        name: items
   *        schema:
   *          type: string
   *        required: true
   *        description: Comma-separated list of item names or ids
   *    responses:
   *      '200':
   *        description: Acquisition methods for the items
   *      '400':
   *        description: Invalid input
   *      '404':
   *        description: One or more items not found
   */
  app.get('/acquisition', async (req,res,next) => {
    try {
      const raw = req.query.items || '';
      const items = parseItemList(raw);
      if (!items || items.length === 0) return res.status(400).send('Items cannot be empty');
      const [blueprintList, lootList, offersList, recipesList, listings] = await Promise.all([
        blueprints.getBlueprints(items),
        getMobLootsForItemsOrMobs(items, null),
        vendoroffers.getVendorOffers(items),
        refining.getRefiningRecipes(items),
        getShopListings(items),
      ]);
      const hydrated = await hydrateShopItems(listings);
      // If any requested items are blueprint names, also include their computed drop blueprints (Blueprint Discovery)
      let blueprintDrops = [];
      try {
        const rows = await getBlueprintDropRows({ sources: items });
        if (rows && rows.length) {
          const seen = new Set();
          for (const r of rows) {
            if (seen.has(r.DropId)) continue;
            seen.add(r.DropId);
            const level = r.DropLevel != null ? Number(r.DropLevel) : null;
            blueprintDrops.push({ Name: r.DropName, Properties: { Level: level, DropRarity: r.DropRarity || null } });
          }
        }
      } catch {}
      res.status(200).json({ Blueprints: blueprintList, Loots: lootList, VendorOffers: offersList, RefiningRecipes: recipesList, ShopListings: hydrated, BlueprintDrops: blueprintDrops });
    } catch (e){ next(e); }
  });

  /**
   * @swagger
   * /acquisition/{item}:
   *  get:
   *    description: Get all acquisition methods for an item
   *    parameters:
   *      - in: path
   *        name: item
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the item
   *    responses:
   *      '200':
   *        description: Acquisition methods for the item
   *      '404':
   *        description: Item not found
   */
  app.get('/acquisition/:item', (req,res) => {
    const item = req.params.item;
    if (!item || String(item).trim().length === 0) return res.status(400).send('Item cannot be empty');
    res.redirect(`/acquisition?items=${encodeURIComponent(item)}`);
  });

  // usage endpoints moved to ./usage.js
}

module.exports = { register };

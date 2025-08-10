const { parseItemList } = require('./utils');
const blueprints = require('./blueprints');
const refining = require('./refining');
const vendoroffers = require('./vendoroffers');
const { getMobLootsForItemsOrMobs } = require('./mobloots');

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
      const [blueprintList, lootList, offersList, recipesList] = await Promise.all([
        blueprints.getBlueprints(items),
        getMobLootsForItemsOrMobs(items, null),
  vendoroffers.getVendorOffers(items),
        refining.getRefiningRecipes(items),
      ]);
      res.status(200).json({ Blueprints: blueprintList, Loots: lootList, VendorOffers: offersList, RefiningRecipes: recipesList });
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

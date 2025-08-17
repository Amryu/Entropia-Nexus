const { parseItemList } = require('./utils');
const blueprints = require('./blueprints');
const refining = require('./refining');
const vendoroffers = require('./vendoroffers');

function register(app){
  /**
   * @swagger
   * /usage:
   *  get:
   *    description: Get all usage methods for one or multiple items
   *    parameters:
   *      - in: query
   *        name: items
   *        schema:
   *          type: string
   *        required: true
   *        description: Comma-separated list of item names or ids
   *    responses:
   *      '200':
   *        description: Usage methods for the items
   *      '400':
   *        description: Invalid input
   *      '404':
   *        description: One or more items not found
   */
  app.get('/usage', async (req,res,next) => {
    try {
      const raw = req.query.items || '';
      const items = parseItemList(raw);
      if (!items || items.length === 0) return res.status(400).send('Items cannot be empty');
      const [blueprintList, recipesList, offersList] = await Promise.all([
        blueprints.getBlueprints(null, items),
        refining.getRefiningRecipes(null, items),
        vendoroffers.getVendorOffers(null, items),
      ]);

      // For the usage endpoint we don't need to send full material objects.
      // Replace the Materials array with a single MaterialAmount property that
      // represents the amount of the queried item used by the blueprint. This
      // reduces payload size for clients that only need the amount for usage.
      const sanitizedBlueprints = (blueprintList || []).map(bp => {
        const mats = bp.Materials || [];
        // find any material that matches one of the requested item names
        const matched = mats.find(m => m?.Item?.Name && items.includes(m.Item.Name));
        return Object.assign({}, bp, { Materials: undefined, MaterialAmount: matched ? matched.Amount : null });
      });

      res.status(200).json({ Blueprints: sanitizedBlueprints, RefiningRecipes: recipesList, VendorOffers: offersList });
    } catch (e){ next(e); }
  });

  /**
   * @swagger
   * /usage/{item}:
   *  get:
   *    description: Get all usage methods for a single item
   *    parameters:
   *      - in: path
   *        name: item
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the item
   *    responses:
   *      '200':
   *        description: Usage methods for the item
   *      '404':
   *        description: Item not found
   */
  app.get('/usage/:item', (req,res) => {
    const item = req.params.item;
    if (!item || String(item).trim().length === 0) return res.status(400).send('Item cannot be empty');
    res.redirect(`/usage?items=${encodeURIComponent(item)}`);
  });
}

module.exports = { register };

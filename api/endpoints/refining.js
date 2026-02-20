const pgp = require('pg-promise')();
const { getObjectByIdOrName, parseItemList } = require('./utils');
const { ITEM_TABLES } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  RefiningRecipes: 'SELECT "RefiningRecipes".*, "Items"."Name" AS "Product", "Items"."Type" AS "ProductType", "Items"."Value" AS "ProductValue" FROM ONLY "RefiningRecipes" INNER JOIN ONLY "Items" ON "RefiningRecipes"."ProductId" = "Items"."Id"',
};

function formatRefiningIngredient(x){
  return { Amount: x.Amount !== null ? Number(x.Amount) : null, Item: { Name: x.ItemName, Properties: { Type: x.ItemType, Economy: { MaxTT: x.ItemValue !== null ? Number(x.ItemValue) : null } }, Links: { "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}` } } };
}

function formatRefiningRecipe(x, ingredients){
  const ing = (ingredients[x.Id] ?? []).map(formatRefiningIngredient);
  return {
    Id: x.Id,
    Ingredients: ing,
    Amount: x.Amount !== null ? Number(x.Amount) : null,
    Product: { Name: x.Product, Properties: { Type: x.ProductType, Economy: { MaxTT: x.ProductValue !== null ? Number(x.ProductValue) : null } }, Links: { "$Url": `/${x.ProductType.toLowerCase()}s/${x.ProductId % 100000}` } },
    Links: { "$Url": `/refiningrecipes/${x.Id}` }
  };
}

async function _getRefiningRecipeIngredients(ids){
  if (ids.length === 0) return {};
  const { pool } = require('./dbClient');
  const { rows } = await pool.query('SELECT "RefiningIngredients"."RecipeId", "RefiningIngredients"."Amount", "Items"."Id" AS "ItemId", "Items"."Name" AS "ItemName", "Items"."Type" AS "ItemType", "Items"."Value" AS "ItemValue" FROM ONLY "RefiningIngredients" INNER JOIN ONLY "Items" ON "RefiningIngredients"."ItemId" = "Items"."Id" WHERE "RefiningIngredients"."RecipeId" IN ('+ids.join(',')+')');
  return rows.reduce((acc,r)=>{ (acc[r.RecipeId] ||= []).push(r); return acc; },{});
}

async function getRefiningRecipes(products = null, ingredients = null){
  let where = '';
  if (products !== null) where = pgp.as.format(' WHERE "Items"."Name" IN ($1:csv)', [products.map(x => `${x}`)]);
  else if (ingredients !== null) where = pgp.as.format(' WHERE "RefiningRecipes"."Id" IN (SELECT DISTINCT "RecipeId" FROM ONLY "RefiningIngredients" INNER JOIN ONLY "Items" ON "RefiningIngredients"."ItemId" = "Items"."Id" WHERE "Items"."Name" IN ($1:csv))', [ingredients.map(x => `${x}`)]);
  const { pool } = require('./dbClient');
  const { rows } = await pool.query(queries.RefiningRecipes + where);
  const ing = await _getRefiningRecipeIngredients(rows.map(r=>r.Id));
  return rows.map(r => formatRefiningRecipe(r, ing));
}

async function getRefiningRecipe(idOrName){
  const row = await getObjectByIdOrName(queries.RefiningRecipes, 'RefiningRecipes', idOrName);
  if (!row) return null;
  const ing = await _getRefiningRecipeIngredients([row.Id]);
  return formatRefiningRecipe(row, ing);
}

function register(app){
  /**
   * @swagger
   * /refiningrecipes:
   *  get:
   *    description: Get all refining recipes
   *    parameters:
   *      - in: query
   *        name: Product
   *        schema:
   *          type: string
   *        description: The product to filter refining recipes by
   *      - in: query
   *        name: Products
   *        schema:
   *          type: string
   *        description: A comma-separated list of products to filter refining recipes by
   *    responses:
   *      '200':
   *        description: A list of refining recipes
   *      '400':
   *        description: Cannot specify both Product and Products
   */
  app.get('/refiningrecipes', async (req,res,next) => {
    try {
      if (req.query.Product && req.query.Products) return res.status(400).send('Cannot specify both Product and Products');
      if (req.query.Product || req.query.Products){
        const products = req.query.Products ? parseItemList(req.query.Products) : [req.query.Product];
        if (products.length === 0) return res.status(400).send('Products cannot be empty');
        res.json(await getRefiningRecipes(products));
      } else {
        res.json(await withCache('/refiningrecipes', ['RefiningRecipes', 'RefiningIngredients', ...ITEM_TABLES], getRefiningRecipes));
      }
    } catch (e){ next(e); }
  });

  /**
   * @swagger
   * /refiningrecipes/{refiningRecipe}:
   *  get:
   *    description: Get a refining recipe by name or id
   *    parameters:
   *      - in: path
   *        name: refiningRecipe
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the refining recipe
   *    responses:
   *      '200':
   *        description: The refining recipe
   *      '404':
   *        description: Refining recipe not found
   */
  app.get('/refiningrecipes/:refiningRecipe', async (req,res,next) => {
    try {
      const result = await withCachedLookup('/refiningrecipes', ['RefiningRecipes', 'RefiningIngredients', ...ITEM_TABLES], getRefiningRecipes, req.params.refiningRecipe);
      if (result) res.json(result); else res.status(404).send();
    } catch (e){ next(e); }
  });
}

module.exports = { register, getRefiningRecipes, getRefiningRecipe };

const pgp = require('pg-promise')();
const { idOffsets } = require('./constants');
const { getObjects, getObjectByIdOrName, parseItemList } = require('./utils');

const queries = {
  Blueprints: 'SELECT "Blueprints".*, "BlueprintBooks"."Name" AS "Book", "Professions"."Name" AS "Profession", "Items"."Type" AS "ItemType", "Items"."Name" AS "Item" FROM ONLY "Blueprints" LEFT JOIN ONLY "BlueprintBooks" ON "Blueprints"."BookId" = "BlueprintBooks"."Id" LEFT JOIN ONLY "Items" ON "Blueprints"."ItemId" = "Items"."Id" LEFT JOIN ONLY "Professions" ON "Professions"."Id" = "Blueprints"."ProfessionId"',
};

// blueprint book endpoints moved to ./blueprintbooks.js

function _formatBlueprintMaterial(x){
  return {
    Amount: x.Amount,
    Item: {
      Name: x.Name,
      Properties: { Type: x.ItemType, Economy: { MaxTT: x.Value } },
      Links: { "$Url": `/${x.Type.toLowerCase()}s/${x.ItemId % 100000}` },
    },
  };
}

function formatBlueprint(x, materials){
  const mats = (materials[x.Id] ?? []).map(_formatBlueprintMaterial);
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Blueprints,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Type: x.Type,
      Level: x.Level !== null ? Number(x.Level) : null,
      IsBoosted: x.IsBoosted == 1,
      MinimumCraftAmount: x.MinimumCraftAmount !== null ? Number(x.MinimumCraftAmount) : null,
      MaximumCraftAmount: x.MaximumCraftAmount !== null ? Number(x.MaximumCraftAmount) : null,
      Skill: {
        LearningIntervalStart: x.MinLvl !== null ? Number(x.MinLvl) : null,
        LearningIntervalEnd: x.MaxLvl !== null ? Number(x.MaxLvl) : null,
        IsSiB: x.IsSib === 1,
      },
    },
    Profession: { Name: x.Profession, Links: { "$Url": `/professions/${x.ProfessionId}` } },
    Book: { Name: x.Book, Links: { "$Url": `/blueprintbooks/${x.BookId}` } },
    Product: x.Item != null ? { Name: x.Item, Properties: { Type: x.ItemType }, Links: { "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}` } } : null,
    Materials: mats,
    Links: { "$Url": `/blueprints/${x.Id}` },
  };
}

async function getBlueprintIngredients(ids){
  if (ids.length === 0) return {};
  const { pool } = require('./dbClient');
  const { rows } = await pool.query('SELECT "BlueprintId", "Name", "Amount", "ItemId", "Type", "Items"."Value" AS "Value", "Items"."Type" AS "ItemType" FROM ONLY "BlueprintMaterials" INNER JOIN ONLY "Items" ON "Items"."Id" = "BlueprintMaterials"."ItemId" WHERE "BlueprintId" IN ('+ids.join(',')+')');
  return rows.reduce((acc,r) => { (acc[r.BlueprintId] ||= []).push(r); return acc; }, {});
}

function normalizeProductNames(names){
  if (!Array.isArray(names)) return [];
  const TAG_PATTERN = /^(.+?) \(([MFCLP](?:,\s*[MFCLP])*)\)$/; // Only strip known single-letter UI tags
  const out = new Set();
  for (const raw of names) {
    const name = `${raw}`.trim();
    if (!name) continue;
    out.add(name);
    const m = name.match(TAG_PATTERN);
    if (m) {
      const base = m[1].trim();
      if (base) out.add(base);
    }
  }
  return Array.from(out);
}

async function getBlueprints(products = null, materials = null){
  let where = '';
  if (products !== null) {
    const normalized = normalizeProductNames(products);
    where = pgp.as.format(' WHERE "Items"."Name" IN ($1:csv)', [normalized]);
  }
  else if (materials !== null) where = pgp.as.format(' WHERE "Blueprints"."Id" IN (SELECT DISTINCT "BlueprintId" FROM ONLY "BlueprintMaterials" INNER JOIN ONLY "Items" ON "Items"."Id" = "BlueprintMaterials"."ItemId" WHERE "Items"."Name" IN ($1:csv))', [materials.map(x => `${x}`)]);
  const { pool } = require('./dbClient');
  const { rows } = await pool.query(queries.Blueprints + where);
  const ingredients = await getBlueprintIngredients(rows.map(r=>r.Id));
  return rows.map(r => formatBlueprint(r, ingredients));
}

async function getBlueprint(idOrName){
  const row = await getObjectByIdOrName(queries.Blueprints, 'Blueprints', idOrName);
  if (!row) return null;
  const ingredients = await getBlueprintIngredients([row.Id]);
  return formatBlueprint(row, ingredients);
}

// Endpoints
function register(app){
  /**
   * @swagger
   * /blueprints:
   *  get:
   *    description: Get all blueprints (filterable)
   *    parameters:
   *      - in: query
   *        name: Product
   *        schema:
   *          type: string
   *        description: The product to filter blueprints by
   *      - in: query
   *        name: Products
   *        schema:
   *          type: string
   *        description: A comma-separated list of products to filter blueprints by
   *    responses:
   *      '200':
   *        description: A list of blueprints
   *      '400':
   *        description: Cannot specify both Product and Products
   */
  app.get('/blueprints', async (req,res,next) => {
    try {
      if (req.query.Product && req.query.Products) return res.status(400).send('Cannot specify both Product and Products');
      if (req.query.Product || req.query.Products){
        const products = req.query.Products ? parseItemList(req.query.Products) : [req.query.Product];
        if (products.length === 0) return res.status(400).send('Products cannot be empty');
        res.json(await getBlueprints(products));
      } else {
        res.json(await getBlueprints());
      }
    } catch (e){ next(e); }
  });

  /**
   * @swagger
   * /blueprints/{blueprint}:
   *  get:
   *    description: Get a blueprint by name or id
   *    parameters:
   *      - in: path
   *        name: blueprint
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the blueprint
   *    responses:
   *      '200':
   *        description: The blueprint
   *      '404':
   *        description: Blueprint not found
   */
  app.get('/blueprints/:blueprint', async (req,res) => {
    const result = await getBlueprint(req.params.blueprint);
    if (result) res.json(result); else res.status(404).send('Blueprint not found');
  });
}

module.exports = { register, getBlueprints, getBlueprint };

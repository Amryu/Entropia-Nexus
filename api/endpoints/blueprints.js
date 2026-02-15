const pgp = require('pg-promise')();
const { idOffsets } = require('./constants');
const { parseItemList } = require('./utils');
const { pool } = require('./dbClient');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Blueprints: 'SELECT "Blueprints".*, "BlueprintBooks"."Name" AS "Book", "Professions"."Name" AS "Profession", "Items"."Type" AS "ItemType", "Items"."Name" AS "Item", "Items"."Value" AS "ProductValue" FROM ONLY "Blueprints" LEFT JOIN ONLY "BlueprintBooks" ON "Blueprints"."BookId" = "BlueprintBooks"."Id" LEFT JOIN ONLY "Items" ON "Blueprints"."ItemId" = "Items"."Id" LEFT JOIN ONLY "Professions" ON "Professions"."Id" = "Blueprints"."ProfessionId"',
};

// blueprint book endpoints moved to ./blueprintbooks.js

function _formatBlueprintMaterial(x){
  return {
    Amount: x.Amount,
    Item: {
      Id: x.ItemId,
      Name: x.Name,
      Properties: { Type: x.ItemType, Economy: { MaxTT: x.Value } },
      Links: { "$Url": `/${x.Type.toLowerCase()}s/${x.ItemId % 100000}` },
    },
  };
}

function formatBlueprint(x, materials, dropsBySource){
  const mats = (materials[x.Id] ?? []).map(_formatBlueprintMaterial);
  const drops = (dropsBySource?.[x.Id] ?? []).map(d => ({
    Id: d.DropId,
    ItemId: d.DropId + idOffsets.Blueprints,
    Name: d.DropName,
    Links: { "$Url": `/blueprints/${d.DropId}` },
  }));
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
    Product: x.Item != null ? { Id: x.ItemId, Name: x.Item, Properties: { Type: x.ItemType, Economy: { MaxTT: x.ProductValue } }, Links: { "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}` } } : null,
    Materials: mats,
    Drops: drops,
    Links: { "$Url": `/blueprints/${x.Id}` },
  };
}

// Shared helpers to build and process the combined blueprint + materials query
function buildCombinedBlueprintQuery(baseSql){
  return `
    SELECT bp.*,
           bm."Amount" AS "MatAmount",
           "MatItems"."Name" AS "MatName",
           bm."ItemId" AS "MatItemId",
           "MatItems"."Value" AS "MatValue",
           "MatItems"."Type" AS "MatItemType"
    FROM (${baseSql}) AS bp
    LEFT JOIN ONLY "BlueprintMaterials" bm ON bp."Id" = bm."BlueprintId"
    LEFT JOIN ONLY "Items" AS "MatItems" ON "MatItems"."Id" = bm."ItemId"
  `;
}

function reduceBlueprintJoinRows(rows){
  const seen = new Set();
  const uniqueRows = [];
  const materialsMap = {};
  for (const r of rows) {
    if (!seen.has(r.Id)) { seen.add(r.Id); uniqueRows.push(r); }
    if (r.MatItemId != null && r.MatItemType && r.MatName) {
      (materialsMap[r.Id] ||= []).push({
        Amount: r.MatAmount,
        Name: r.MatName,
        ItemId: r.MatItemId,
        Type: r.MatItemType,
        Value: r.MatValue,
        ItemType: r.MatItemType,
      });
    }
  }
  return { uniqueRows, materialsMap };
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
  // Build the base blueprint query with optional filters, then join materials in one shot
  let where = '';
  if (products !== null) {
    const normalized = normalizeProductNames(products);
    where = pgp.as.format(' WHERE "Items"."Name" IN ($1:csv)', [normalized]);
  } else if (materials !== null) {
    where = pgp.as.format(' WHERE "Blueprints"."Id" IN (SELECT DISTINCT "BlueprintId" FROM ONLY "BlueprintMaterials" INNER JOIN ONLY "Items" ON "Items"."Id" = "BlueprintMaterials"."ItemId" WHERE "Items"."Name" IN ($1:csv))', [materials.map(x => `${x}`)]);
  }

  const baseSql = queries.Blueprints + where;
  const combinedSql = buildCombinedBlueprintQuery(baseSql);

  const { pool } = require('./dbClient');
  const { rows } = await pool.query(combinedSql);
  const { uniqueRows, materialsMap } = reduceBlueprintJoinRows(rows);
  const dropsBySource = await getDropsForBlueprintIds(uniqueRows.map(r => r.Id));
  return uniqueRows.map(r => formatBlueprint(r, materialsMap, dropsBySource));
}

async function getBlueprint(idOrName){
  // Build a filtered blueprint subquery by id or name, then join materials and reduce
  let where;
  const isNumeric = String(idOrName).match(/^\d+$/);
  if (isNumeric) {
    where = pgp.as.format(' WHERE "Blueprints"."Id" = $1', [Number(idOrName)]);
  } else {
    where = pgp.as.format(' WHERE "Blueprints"."Name" = $1', [String(idOrName)]);
  }

  const baseSql = queries.Blueprints + where;
  const combinedSql = buildCombinedBlueprintQuery(baseSql);

  const { pool } = require('./dbClient');
  const { rows } = await pool.query(combinedSql);
  if (!rows || rows.length === 0) return null;
  const { uniqueRows, materialsMap } = reduceBlueprintJoinRows(rows);
  const dropsBySource = await getDropsForBlueprintIds([uniqueRows[0].Id]);
  return formatBlueprint(uniqueRows[0], materialsMap, dropsBySource);
}

// Fetch drops mapping for a set of blueprint Ids
async function getDropsForBlueprintIds(ids){
  const map = {};
  if (!ids || ids.length === 0) return map;
  const { rows } = await pool.query(
    `SELECT bd."SourceId", bd."DropId", d."Name" AS "DropName"
     FROM ONLY "BlueprintDrops" bd
     INNER JOIN ONLY "Blueprints" d ON d."Id" = bd."DropId"
     WHERE bd."SourceId" IN (${ids.join(',')})`
  );
  for (const r of rows){ (map[r.SourceId] ||= []).push(r); }
  return map;
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
        res.json(await withCache('/blueprints', ['Blueprints', 'BlueprintBooks', 'Items', 'Professions', 'BlueprintMaterials', 'BlueprintDrops'], getBlueprints));
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
    const result = await withCachedLookup('/blueprints', ['Blueprints', 'BlueprintBooks', 'Items', 'Professions', 'BlueprintMaterials', 'BlueprintDrops'], getBlueprints, req.params.blueprint);
    if (result) res.json(result); else res.status(404).send('Blueprint not found');
  });
}

module.exports = { register, getBlueprints, getBlueprint, formatBlueprint };

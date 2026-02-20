const { getObjects, getObjectByIdOrName, generateGenderAliases } = require('./utils');
const { pool } = require('./dbClient');
const { idOffsets, ITEM_TABLES } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Items: `SELECT i.*,
    CASE
      WHEN i."Type" = 'Armor' THEN a."Gender"
      WHEN i."Type" = 'Clothing' THEN c."Gender"
      ELSE NULL
    END AS "Gender"
  FROM ONLY "Items" i
  LEFT JOIN ONLY "Armors" a ON i."Type" = 'Armor' AND i."Id" = a."Id" + ${idOffsets.Armors}
  LEFT JOIN ONLY "Clothes" c ON i."Type" = 'Clothing' AND i."Id" = c."Id" + ${idOffsets.Clothings}`
};

function formatItem(x){
  const aliases = (x.Type === 'Armor' || x.Type === 'Clothing')
    ? generateGenderAliases(x.Name, x.Gender)
    : [];
  return {
    Id: x.Id,
    Name: x.Name,
    Aliases: aliases.length > 0 ? aliases : undefined,
    Properties: {
      Type: x.Type,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: { Value: x.Value !== null ? Number(x.Value) : null },
      ...(x.Gender != null && { Gender: x.Gender })
    },
    Links: { "$Url": `/${x.Type.toLowerCase()}s/${x.Id % 100000}` }
  };
}

async function _getObjects(query, formatFn){ return getObjects(query, formatFn); }
async function _getObject(idOrName, query){ const row = await getObjectByIdOrName(query, 'Items', idOrName); return row ? formatItem(row) : null; }

const getItems = () => _getObjects(queries.Items, formatItem);
const getItem = (idOrName) => _getObject(idOrName, queries.Items);

async function getItemsByIds(ids) {
  if (!Array.isArray(ids) || ids.length === 0) return [];
  const validIds = ids.filter(id => Number.isInteger(Number(id))).map(Number);
  if (validIds.length === 0) return [];

  const sql = `SELECT i.*,
    CASE
      WHEN i."Type" = 'Armor' THEN a."Gender"
      WHEN i."Type" = 'Clothing' THEN c."Gender"
      ELSE NULL
    END AS "Gender"
  FROM ONLY "Items" i
  LEFT JOIN ONLY "Armors" a ON i."Type" = 'Armor' AND i."Id" = a."Id" + ${idOffsets.Armors}
  LEFT JOIN ONLY "Clothes" c ON i."Type" = 'Clothing' AND i."Id" = c."Id" + ${idOffsets.Clothings}
  WHERE i."Id" = ANY($1)`;
  const { rows } = await pool.query(sql, [validIds]);
  return rows.map(formatItem);
}

function register(app){
  /**
   * @swagger
   * /items:
   *  get:
   *    description: Get all items or batch fetch by IDs
   *    parameters:
   *      - in: query
   *        name: Ids
   *        schema:
   *          type: string
   *        required: false
   *        description: Comma-separated list of item IDs for batch fetch
   *    responses:
   *      '200':
   *        description: A list of items
   */
  app.get('/items', async (req,res) => {
    if (req.query.Ids) {
      const ids = req.query.Ids.split(',').map(s => s.trim()).filter(Boolean);
      res.json(await getItemsByIds(ids));
    } else {
      res.json(await withCache('/items', ITEM_TABLES, getItems));
    }
  });
  app.get('/items/:item', async (req,res) => {
    /**
     * @swagger
     * /items/{item}:
     *  get:
     *    description: Get an item by name or id
     *    parameters:
     *      - in: path
     *        name: item
     *        schema:
     *          type: string
     *        required: true
     *        description: The name or id of the item
     *    responses:
     *      '200':
     *        description: The item
     *      '404':
     *        description: Item not found
     */
    const it = await withCachedLookup('/items', ITEM_TABLES, getItems, req.params.item);
    if (it) res.json(it); else res.status(404).send('Item not found');
  });
}

module.exports = { register, getItems, getItem, getItemsByIds };

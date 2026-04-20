const { getObjects, getObjectByIdOrName, isClassId, loadClassIds, loadItemProperties, generateGenderAliases } = require('./utils');
const { pool } = require('./dbClient');
const { idOffsets, ITEM_TABLES, TABLE_TO_ENTITY_TYPE } = require('./constants');
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
  LEFT JOIN ONLY "Clothes" c ON i."Type" = 'Clothing' AND i."Id" = c."Id" + ${idOffsets.Clothings}`,
  UndiscoveredFishItemIds: 'SELECT "Id" FROM "UndiscoveredFishItemIds"',
};

async function loadHiddenItemIds() {
  const { rows } = await pool.query(queries.UndiscoveredFishItemIds);
  return new Set(rows.map(r => r.Id));
}

// Non-default `Type.toLowerCase() + 's'` URL paths. Each entry maps an
// Items.Type value to the API path segment used in the item's `$Url`.
// Types not listed here fall back to `${type.toLowerCase()}s`.
const TYPE_URL_OVERRIDES = {
  Fish: 'fishes',              // Info-side; promoted from Materials
  Food: 'consumables',         // Food shares the Consumables table
  FishingRod: 'fishingrods',
  FishingReel: 'fishingreels',
  FishingBlank: 'fishingblanks',
  FishingLine: 'fishinglines',
  FishingLure: 'fishinglures',
};

function formatItem(x, classIdMap, itemProps){
  const rawId = x.Id % 100000;
  const classId = classIdMap ? (classIdMap[`${x.Type}:${rawId}`] || null) : null;
  const props = itemProps ? itemProps[x.Id] : undefined;
  const aliases = (x.Type === 'Armor' || x.Type === 'Clothing')
    ? generateGenderAliases(x.Name, x.Gender)
    : [];
  const urlPath = TYPE_URL_OVERRIDES[x.Type] || `${x.Type.toLowerCase()}s`;
  return {
    Id: x.Id,
    ClassId: classId,
    Name: x.Name,
    Aliases: aliases.length > 0 ? aliases : undefined,
    Properties: {
      Type: x.Type,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: { Value: x.Value !== null ? Number(x.Value) : null },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
      ...(x.Gender != null && { Gender: x.Gender })
    },
    Links: { "$Url": `/${urlPath}/${x.Id % 100000}` }
  };
}

async function getItems() {
  const [{ rows }, { rows: classIdRows }, hidden] = await Promise.all([
    pool.query(queries.Items),
    pool.query('SELECT "EntityType", "EntityId", "ClassId" FROM ONLY "ClassIds"'),
    loadHiddenItemIds(),
  ]);
  const visible = rows.filter(r => !hidden.has(r.Id));
  const classIdMap = {};
  for (const r of classIdRows) classIdMap[`${r.EntityType}:${r.EntityId}`] = String(r.ClassId);
  const itemProps = await loadItemProperties(visible.map(r => r.Id));
  return visible.map(r => formatItem(r, classIdMap, itemProps));
}

async function getItem(idOrName) {
  let row;
  if (isClassId(idOrName)) {
    const classIdValue = String(idOrName).substring(1);
    const { rows: ciRows } = await pool.query(
      'SELECT "EntityType", "EntityId" FROM ONLY "ClassIds" WHERE "ClassId" = $1', [classIdValue]
    );
    if (ciRows.length !== 1) return null;
    const { EntityType, EntityId } = ciRows[0];
    const offsetKey = Object.entries(TABLE_TO_ENTITY_TYPE).find(([_, v]) => v === EntityType)?.[0];
    if (!offsetKey || idOffsets[offsetKey] == null) return null;
    row = await getObjectByIdOrName(queries.Items, 'Items', String(EntityId + idOffsets[offsetKey]));
  } else {
    row = await getObjectByIdOrName(queries.Items, 'Items', idOrName);
  }
  if (!row) return null;
  const hidden = await loadHiddenItemIds();
  if (hidden.has(row.Id)) return null;
  const rawId = row.Id % 100000;
  const [classIds, itemProps] = await Promise.all([
    loadClassIds(row.Type, [rawId]),
    loadItemProperties([row.Id]),
  ]);
  const classIdMap = {};
  if (classIds[rawId]) classIdMap[`${row.Type}:${rawId}`] = classIds[rawId];
  return formatItem(row, classIdMap, itemProps);
}

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
  WHERE i."Id" = ANY($1)
    AND i."Id" NOT IN (SELECT "Id" FROM "UndiscoveredFishItemIds")`;
  const { rows } = await pool.query(sql, [validIds]);

  // Load ClassIds grouped by entity type
  const byType = {};
  for (const r of rows) (byType[r.Type] ||= []).push(r.Id % 100000);
  const typeEntries = Object.entries(byType);
  const classIdArrays = await Promise.all(typeEntries.map(([type, eids]) => loadClassIds(type, eids)));
  const classIdMap = {};
  for (let i = 0; i < typeEntries.length; i++) {
    for (const [eid, cid] of Object.entries(classIdArrays[i])) {
      classIdMap[`${typeEntries[i][0]}:${eid}`] = cid;
    }
  }
  const itemProps = await loadItemProperties(rows.map(r => r.Id));
  return rows.map(r => formatItem(r, classIdMap, itemProps));
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
      res.json(await withCache('/items', [...ITEM_TABLES, 'ClassIds', 'ItemProperties', 'FishDiscoveries'], getItems));
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
    const it = await withCachedLookup('/items', [...ITEM_TABLES, 'ClassIds', 'ItemProperties', 'FishDiscoveries'], getItems, req.params.item);
    if (it) res.json(it); else res.status(404).send('Item not found');
  });
}

module.exports = { register, getItems, getItem, getItemsByIds };

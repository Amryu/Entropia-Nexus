const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');
const { idOffsets } = require('./constants');

const queries = {
  Materials: 'SELECT * FROM ONLY "Materials"',
  // Items.Id values that belong to an undiscovered fish (oil + sizes).
  // Subtracting idOffsets.Materials from each recovers the Materials.Id to
  // filter out of list and single-item responses.
  UndiscoveredFishItemIds: 'SELECT "Id" FROM "UndiscoveredFishItemIds"',
};

async function loadHiddenMaterialIds() {
  const { rows } = await pool.query(queries.UndiscoveredFishItemIds);
  const ids = new Set();
  for (const r of rows) ids.add(r.Id - idOffsets.Materials);
  return ids;
}

function formatMaterial(x, data){
  const itemId = x.Id + idOffsets.Materials;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ItemId: itemId,
    ClassId: data.ClassIds[x.Id] || null,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Type: x.Type,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: { MaxTT: x.Value !== null ? Number(x.Value) : null },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Links: { "$Url": `/materials/${x.Id}` }
  };
}

// DB methods
async function getMaterials() {
  const [{ rows }, hidden] = await Promise.all([
    pool.query(queries.Materials),
    loadHiddenMaterialIds(),
  ]);
  const visible = rows.filter(r => !hidden.has(r.Id));
  const itemIds = visible.map(r => r.Id + idOffsets.Materials);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('Material', visible.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  const data = { ClassIds: classIds, ItemProps: itemProps };
  return visible.map(r => formatMaterial(r, data));
}
const getMaterial = async (idOrName) => {
  const row = await getObjectByIdOrName(queries.Materials, 'Materials', idOrName);
  if (!row) return null;
  const hidden = await loadHiddenMaterialIds();
  if (hidden.has(row.Id)) return null;
  const itemId = row.Id + idOffsets.Materials;
  const [classIds, itemProps] = await Promise.all([loadClassIds('Material', [row.Id]), loadItemProperties([itemId])]);
  const data = { ClassIds: classIds, ItemProps: itemProps };
  return formatMaterial(row, data);
};

// Endpoints
function register(app){
  /**
   * @swagger
   * /materials:
   *  get:
   *    description: Get all materials
   *    responses:
   *      '200':
   *        description: A list of materials
   */
  app.get('/materials', async (req,res) => { res.json(await withCache('/materials', ['Materials', 'ClassIds', 'ItemProperties', 'FishDiscoveries'], getMaterials)); });

  /**
   * @swagger
   * /materials/{material}:
   *  get:
   *    description: Get a material by name or id
   *    parameters:
   *      - in: path
   *        name: material
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the material
   *    responses:
   *      '200':
   *        description: The material
   *      '404':
   *        description: Material not found
   */
  app.get('/materials/:material', async (req,res) => { const r = await withCachedLookup('/materials', ['Materials', 'ClassIds', 'ItemProperties', 'FishDiscoveries'], getMaterials, req.params.material); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getMaterials, getMaterial, formatMaterial };

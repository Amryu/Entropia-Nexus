const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');
const { idOffsets } = require('./constants');

const queries = {
  Materials: 'SELECT * FROM ONLY "Materials"',
};

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
  const { rows } = await pool.query(queries.Materials);
  const itemIds = rows.map(r => r.Id + idOffsets.Materials);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('Material', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  const data = { ClassIds: classIds, ItemProps: itemProps };
  return rows.map(r => formatMaterial(r, data));
}
const getMaterial = async (idOrName) => { const row = await getObjectByIdOrName(queries.Materials, 'Materials', idOrName); if (!row) return null; const itemId = row.Id + idOffsets.Materials; const [classIds, itemProps] = await Promise.all([loadClassIds('Material', [row.Id]), loadItemProperties([itemId])]); const data = { ClassIds: classIds, ItemProps: itemProps }; return formatMaterial(row, data); };

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
  app.get('/materials', async (req,res) => { res.json(await withCache('/materials', ['Materials', 'ClassIds', 'ItemProperties'], getMaterials)); });

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
  app.get('/materials/:material', async (req,res) => { const r = await withCachedLookup('/materials', ['Materials', 'ClassIds', 'ItemProperties'], getMaterials, req.params.material); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getMaterials, getMaterial, formatMaterial };

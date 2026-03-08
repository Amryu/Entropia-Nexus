const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');
const { idOffsets } = require('./constants');

const queries = {
  Materials: 'SELECT * FROM ONLY "Materials"',
};

function formatMaterial(x, classIds){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Materials,
    ClassId: classIds[x.Id] || null,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Type: x.Type,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: { MaxTT: x.Value !== null ? Number(x.Value) : null }
    },
    Links: { "$Url": `/materials/${x.Id}` }
  };
}

// DB methods
async function getMaterials() {
  const { rows } = await pool.query(queries.Materials);
  const classIds = await loadClassIds('Material', rows.map(r => r.Id));
  return rows.map(r => formatMaterial(r, classIds));
}
const getMaterial = async (idOrName) => { const row = await getObjectByIdOrName(queries.Materials, 'Materials', idOrName); if (!row) return null; const classIds = await loadClassIds('Material', [row.Id]); return formatMaterial(row, classIds); };

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
  app.get('/materials', async (req,res) => { res.json(await withCache('/materials', ['Materials', 'ClassIds'], getMaterials)); });

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
  app.get('/materials/:material', async (req,res) => { const r = await withCachedLookup('/materials', ['Materials', 'ClassIds'], getMaterials, req.params.material); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getMaterials, getMaterial, formatMaterial };

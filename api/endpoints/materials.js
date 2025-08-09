const { getObjects, getObjectByIdOrName } = require('./utils');

const queries = {
  Materials: 'SELECT * FROM ONLY "Materials"',
};

function formatMaterial(x){
  return {
    Id: x.Id,
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
const getMaterials = () => getObjects(queries.Materials, formatMaterial);
const getMaterial = async (idOrName) => { const row = await getObjectByIdOrName(queries.Materials, 'Materials', idOrName); return row ? formatMaterial(row) : null; };

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
  app.get('/materials', async (req,res) => { res.json(await getMaterials()); });

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
  app.get('/materials/:material', async (req,res) => { const r = await getMaterial(req.params.material); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getMaterials, getMaterial };

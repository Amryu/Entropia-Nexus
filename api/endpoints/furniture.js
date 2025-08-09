const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');

const ID_OFFSET = 9100000;

const queries = {
  Furniture: 'SELECT f.*, p."Name" AS "Planet" FROM ONLY "Furniture" f LEFT JOIN ONLY "Planets" p ON f."PlanetId" = p."Id"',
};

function formatFurniture(x){
  return { Id: x.Id, ItemId: x.Id + ID_OFFSET, Name: x.Name, Properties: { Description: x.Description, Weight: x.Weight !== null ? Number(x.Weight) : null, Type: x.Type, Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null } }, Planet: { Name: x.Planet, Links: { "$Url": `/planets/${x.PlanetId}` } }, Links: { "$Url": `/furniture/${x.Id}` } };
}

async function getFurnitures(){ const { rows } = await pool.query(queries.Furniture); return rows.map(formatFurniture); }
async function getFurniture(idOrName){ const row = await getObjectByIdOrName(queries.Furniture, 'Furniture', idOrName); return row ? formatFurniture(row) : null; }

function register(app){
  /**
   * @swagger
   * /furniture:
   *  get:
   *    description: Get all furniture
   *    responses:
   *      '200':
   *        description: A list of furniture
   */
  app.get('/furniture', async (req,res) => { res.json(await getFurnitures()); });
  /**
   * @swagger
   * /furniture/{furniture}:
   *  get:
   *    description: Get a furniture by name or id
   *    parameters:
   *      - in: path
   *        name: furniture
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the furniture
   *    responses:
   *      '200':
   *        description: The furniture
   *      '404':
   *        description: Furniture not found
   */
  app.get('/furniture/:furniture', async (req,res) => { const r = await getFurniture(req.params.furniture); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getFurnitures, getFurniture };

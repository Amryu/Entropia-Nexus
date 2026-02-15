const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  ProfessionCategories: 'SELECT * FROM ONLY "ProfessionCategories"',
};

function formatProfessionCategory(x){ return { Id: x.Id, Name: x.Name, Links: { "$Url": `/professioncategories/${x.Id}` } }; }

async function getProfessionCategories(){ const { rows } = await pool.query(queries.ProfessionCategories); return rows.map(formatProfessionCategory); }
async function getProfessionCategory(idOrName){ const row = await getObjectByIdOrName(queries.ProfessionCategories, 'ProfessionCategories', idOrName); return row ? formatProfessionCategory(row) : null; }

function register(app){
  /**
   * @swagger
   * /professioncategories:
   *  get:
   *    description: Get all profession categories
   *    responses:
   *      '200':
   *        description: A list of profession categories
   */
  app.get('/professioncategories', async (req,res) => { res.json(await withCache('/professioncategories', ['ProfessionCategories'], getProfessionCategories)); });
  /**
   * @swagger
   * /professioncategories/{professionCategory}:
   *  get:
   *    description: Get a profession category by name or id
   *    parameters:
   *      - in: path
   *        name: professionCategory
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the profession category
   *    responses:
   *      '200':
   *        description: The profession category
   *      '404':
   *        description: Profession category not found
   */
  app.get('/professioncategories/:professionCategory', async (req,res) => { const r = await withCachedLookup('/professioncategories', ['ProfessionCategories'], getProfessionCategories, req.params.professionCategory); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getProfessionCategories, getProfessionCategory };

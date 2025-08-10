const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');

const queries = {
  SkillCategories: 'SELECT * FROM ONLY "SkillCategories"',
};

function formatSkillCategory(x){ return { Id: x.Id, Name: x.Name, Links: { "$Url": `/skillcategories/${x.Id}` } }; }

async function getSkillCategories(){ const { rows } = await pool.query(queries.SkillCategories); return rows.map(formatSkillCategory); }
async function getSkillCategory(idOrName){ const row = await getObjectByIdOrName(queries.SkillCategories, 'SkillCategories', idOrName); return row ? formatSkillCategory(row) : null; }

function register(app){
  /**
   * @swagger
   * /skillcategories:
   *  get:
   *    description: Get all skill categories
   *    responses:
   *      '200':
   *        description: A list of skill categories
   */
  app.get('/skillcategories', async (req,res) => { res.json(await getSkillCategories()); });
  /**
   * @swagger
   * /skillcategories/{skillCategory}:
   *  get:
   *    description: Get a skill category by name or id
   *    parameters:
   *      - in: path
   *        name: skillCategory
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the skill category
   *    responses:
   *      '200':
   *        description: The skill category
   *      '404':
   *        description: Skill category not found
   */
  app.get('/skillcategories/:skillCategory', async (req,res) => { const r = await getSkillCategory(req.params.skillCategory); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getSkillCategories, getSkillCategory };

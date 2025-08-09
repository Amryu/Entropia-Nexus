const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');

const queries = {
  SkillCategories: 'SELECT * FROM ONLY "SkillCategories"',
  Skills: 'SELECT "Skills".*, "SkillCategories"."Name" AS "Category" FROM ONLY "Skills" INNER JOIN ONLY "SkillCategories" ON "Skills"."CategoryId" = "SkillCategories"."Id"',
};

function formatSkillCategory(x){ return { Id: x.Id, Name: x.Name, Links: { "$Url": `/skillcategories/${x.Id}` } }; }
function _groupBy(arr, key){ return arr.reduce((acc, r) => { (acc[r[key]] ||= []).push(r); return acc; }, {}); }

function _formatSkillProfession(x){
  return { Weight: x.Weight !== null ? Number(x.Weight) : null, Profession: { Name: x.ProfessionName, Properties: { Category: x.Category }, Links: { "$Url": `/professions/${x.ProfessionId}` } } };
}
function _formatSkillUnlock(x){
  return { Level: x.Level !== null ? Number(x.Level) : null, Profession: { Name: x.ProfessionName, Links: { "$Url": `/professions/${x.ProfessionId}` } } };
}

async function _getSkillUnlocks(ids){
  const { rows: skillProfessions } = await pool.query(`SELECT "ProfessionSkills".*, "Professions"."Name" AS "ProfessionName", "ProfessionCategories"."Name" AS "Category" FROM ONLY "ProfessionSkills" INNER JOIN ONLY "Professions" ON "ProfessionSkills"."ProfessionId" = "Professions"."Id" INNER JOIN ONLY "ProfessionCategories" ON "Professions"."CategoryId" = "ProfessionCategories"."Id" WHERE "ProfessionSkills"."SkillId" IN (${ids.join(',')})`);
  const { rows: skillUnlocks } = await pool.query(`SELECT "SkillUnlocks".*, "Professions"."Name" AS "ProfessionName", "ProfessionCategories"."Name" AS "Category" FROM ONLY "SkillUnlocks" INNER JOIN ONLY "Professions" ON "SkillUnlocks"."ProfessionId" = "Professions"."Id" INNER JOIN ONLY "ProfessionCategories" ON "Professions"."CategoryId" = "ProfessionCategories"."Id" WHERE "SkillUnlocks"."SkillId" IN (${ids.join(',')})`);
  return { SkillProfessions: _groupBy(skillProfessions, 'SkillId'), SkillUnlocks: _groupBy(skillUnlocks, 'SkillId') };
}

function formatSkill(x, data){
  const professionSkills = (data.SkillProfessions[x.Id] ?? []).map(_formatSkillProfession);
  const unlocks = (data.SkillUnlocks[x.Id] ?? []).map(_formatSkillUnlock);
  return { Id: x.Id, Name: x.Name, Properties: { Description: x.Description, HpIncrease: x.HPIncrease !== null ? Number(x.HPIncrease) : null, IsHidden: unlocks !== null && unlocks.length > 0 }, Professions: professionSkills, Unlocks: unlocks.length > 0 ? unlocks : null, Category: { Name: x.Category, Links: { "$Url": `/skillcategories/${x.CategoryId}` } }, Links: { "$Url": `/skills/${x.Id}` } };
}

async function getSkillCategories(){ const { rows } = await pool.query(queries.SkillCategories); return rows.map(formatSkillCategory); }
async function getSkillCategory(idOrName){ const row = await getObjectByIdOrName(queries.SkillCategories, 'SkillCategories', idOrName); return row ? formatSkillCategory(row) : null; }

async function getSkills(){ const { rows } = await pool.query(queries.Skills); const data = await _getSkillUnlocks(rows.map(r=>r.Id)); return rows.map(r => formatSkill(r, data)); }
async function getSkill(idOrName){ const row = await getObjectByIdOrName(queries.Skills, 'Skills', idOrName); if (!row) return null; const data = await _getSkillUnlocks([row.Id]); return formatSkill(row, data); }

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

  /**
   * @swagger
   * /skills:
   *  get:
   *    description: Get all skills
   *    responses:
   *      '200':
   *        description: A list of skills
   */
  app.get('/skills', async (req,res) => { res.json(await getSkills()); });
  /**
   * @swagger
   * /skills/{skill}:
   *  get:
   *    description: Get a skill by name or id
   *    parameters:
   *      - in: path
   *        name: skill
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the skill
   *    responses:
   *      '200':
   *        description: The skill
   *      '404':
   *        description: Skill not found
   */
  app.get('/skills/:skill', async (req,res) => { const r = await getSkill(req.params.skill); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getSkillCategories, getSkillCategory, getSkills, getSkill };

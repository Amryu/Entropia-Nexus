const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');

const queries = {
  ProfessionCategories: 'SELECT * FROM ONLY "ProfessionCategories"',
  Professions: 'SELECT "Professions".*, "ProfessionCategories"."Name" AS "Category" FROM ONLY "Professions" INNER JOIN ONLY "ProfessionCategories" ON "Professions"."CategoryId" = "ProfessionCategories"."Id"',
};

function formatProfessionCategory(x){ return { Id: x.Id, Name: x.Name, Links: { "$Url": `/professioncategories/${x.Id}` } }; }

function _groupBy(arr, key){ return arr.reduce((acc, r) => { (acc[r[key]] ||= []).push(r); return acc; }, {}); }

function _formatProfessionSkill(x){
  return { Weight: x.Weight !== null ? Number(x.Weight) : null, Skill: { Name: x.SkillName, Properties: { HpIncrease: x.HPIncrease !== null ? Number(x.HPIncrease) : null, IsHidden: x.Hidden === 1 }, Links: { "$Url": `/skills/${x.SkillId}` } } };
}

function _formatProfessionSkillUnlock(x){
  return { Level: x.Level !== null ? Number(x.Level) : null, Skill: { Name: x.Skill, Properties: { HpIncrease: x.HPIncrease !== null ? Number(x.HPIncrease) : null, IsHidden: x.Hidden === 1 }, Links: { "$Url": `/skills/${x.SkillId}` } } };
}

async function _getProfessionSkillsAndUnlocks(ids){
  const { rows: professionSkills } = await pool.query(`SELECT "ProfessionSkills"."Weight", "Skills"."Id" AS "SkillId", "Skills"."Name" AS "SkillName", "Skills"."HPIncrease" AS "HPIncrease", "Skills"."Hidden" AS "Hidden", "ProfessionId" FROM ONLY "ProfessionSkills" INNER JOIN ONLY "Skills" ON "ProfessionSkills"."SkillId" = "Skills"."Id" WHERE "ProfessionId" IN (${ids.join(',')})`);
  const { rows: skillUnlocks } = await pool.query(`SELECT "SkillUnlocks".*, "Skills"."Name" AS "Skill", "Skills"."HPIncrease" AS "HPIncrease", "Skills"."Hidden" AS "Hidden", "SkillUnlocks"."ProfessionId" FROM ONLY "SkillUnlocks" INNER JOIN ONLY "Skills" ON "SkillUnlocks"."SkillId" = "Skills"."Id" WHERE "SkillUnlocks"."ProfessionId" IN (${ids.join(',')})`);
  return { ProfessionSkills: _groupBy(professionSkills, 'ProfessionId'), SkillUnlocks: _groupBy(skillUnlocks, 'ProfessionId') };
}

function formatProfession(x, data){
  const skills = (data.ProfessionSkills[x.Id] ?? []).map(_formatProfessionSkill);
  const unlocks = (data.SkillUnlocks[x.Id] ?? []).map(_formatProfessionSkillUnlock);
  return { Id: x.Id, Name: x.Name, Category: { Name: x.Category, Links: { "$Url": `/professioncategories/${x.CategoryId}` } }, Skills: skills, Unlocks: unlocks, Links: { "$Url": `/professions/${x.Id}` } };
}

async function getProfessionCategories(){ const { rows } = await pool.query(queries.ProfessionCategories); return rows.map(formatProfessionCategory); }
async function getProfessionCategory(idOrName){ const row = await getObjectByIdOrName(queries.ProfessionCategories, 'ProfessionCategories', idOrName); return row ? formatProfessionCategory(row) : null; }

async function getProfessions(){ const { rows } = await pool.query(queries.Professions); const data = await _getProfessionSkillsAndUnlocks(rows.map(r=>r.Id)); return rows.map(r => formatProfession(r, data)); }
async function getProfession(idOrName){ const row = await getObjectByIdOrName(queries.Professions, 'Professions', idOrName); if (!row) return null; const data = await _getProfessionSkillsAndUnlocks([row.Id]); return formatProfession(row, data); }

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
  app.get('/professioncategories', async (req,res) => { res.json(await getProfessionCategories()); });
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
  app.get('/professioncategories/:professionCategory', async (req,res) => { const r = await getProfessionCategory(req.params.professionCategory); if (r) res.json(r); else res.status(404).send(); });

  /**
   * @swagger
   * /professions:
   *  get:
   *    description: Get all professions
   *    responses:
   *      '200':
   *        description: A list of professions
   */
  app.get('/professions', async (req,res) => { res.json(await getProfessions()); });
  /**
   * @swagger
   * /professions/{profession}:
   *  get:
   *    description: Get a profession by name or id
   *    parameters:
   *      - in: path
   *        name: profession
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the profession
   *    responses:
   *      '200':
   *        description: The profession
   *      '404':
   *        description: Profession not found
   */
  app.get('/professions/:profession', async (req,res) => { const r = await getProfession(req.params.profession); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getProfessionCategories, getProfessionCategory, getProfessions, getProfession };

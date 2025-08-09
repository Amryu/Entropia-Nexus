const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName, getObjects } = require('./utils');

const queries = {
  EffectChips:
    'SELECT "EffectChips".*,\
            "Professions"."Name" AS "Profession",\
            "Materials"."Name" AS "Ammo"\
       FROM ONLY "EffectChips"\
  LEFT JOIN ONLY "Professions" ON "EffectChips"."ProfessionId" = "Professions"."Id"\
  LEFT JOIN ONLY "Materials"   ON "EffectChips"."AmmoId" = "Materials"."Id"',
  EffectsOnUse: `SELECT "EffectsOnUse".*, e."Name" AS "Effect", e."IsPositive" AS "IsPositive" FROM ONLY "EffectsOnUse" LEFT JOIN ONLY "Effects" e ON e."Id" = "EffectsOnUse"."EffectId" WHERE "EffectsOnUse"."ItemId" IN ($1:csv)`
};

async function _getEffectsOnUse(ids){
  if (ids.length === 0) return {};
  const pgp = require('pg-promise')();
  const { rows } = await pool.query(pgp.as.format(queries.EffectsOnUse, [ids]));
  return rows.reduce((acc,r)=>{ (acc[r.ItemId] ||= []).push(r); return acc; },{});
}

function _formatEffect(x){ return { Name: x.Effect, IsPositive: x.IsPositive === 1, Amount: x.Amount !== null ? Number(x.Amount) : null, Duration: x.Duration !== null ? Number(x.Duration) : null }; }

function formatEffectChip(x, effects){
  const list = (effects[x.Id] ?? []).map(_formatEffect);
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.EffectChips,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Profession: x.Profession,
      Ammo: x.Ammo,
      Skill: { LearningIntervalStart: x.MinLvl !== null ? Number(x.MinLvl) : null, LearningIntervalEnd: x.MaxLvl !== null ? Number(x.MaxLvl) : null, IsSiB: x.IsSib === 1 }
    },
    EffectsOnUse: list,
    Links: { "$Url": `/effectchips/${x.Id}` }
  };
}

async function getEffectChips(){
  const { rows } = await pool.query(queries.EffectChips);
  const effects = await _getEffectsOnUse(rows.map(r=>r.Id));
  return rows.map(r => formatEffectChip(r, effects));
}

async function getEffectChip(idOrName){
  const row = await getObjectByIdOrName(queries.EffectChips, 'EffectChips', idOrName);
  if (!row) return null;
  const effects = await _getEffectsOnUse([row.Id]);
  return formatEffectChip(row, effects);
}

function register(app){
  /**
   * @swagger
   * /effectchips:
   *  get:
   *    description: Get all effect chips
   *    responses:
   *      '200':
   *        description: A list of effect chips
   */
  app.get('/effectchips', async (req,res) => { res.json(await getEffectChips()); });
  /**
   * @swagger
   * /effectchips/{effectChip}:
   *  get:
   *    description: Get an effect chip by name or id
   *    parameters:
   *      - in: path
   *        name: effectChip
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the effect chip
   *    responses:
   *      '200':
   *        description: The effect chip
   *      '404':
   *        description: Effect chip not found
   */
  app.get('/effectchips/:effectChip', async (req,res) => { const r = await getEffectChip(req.params.effectChip); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getEffectChips, getEffectChip };

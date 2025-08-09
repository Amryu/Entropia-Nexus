const pgp = require('pg-promise')();
const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');

const ID_OFFSET = 10000000;

const queries = {
  Consumables: 'SELECT * FROM ONLY "Consumables"',
  EffectsOnConsume: `SELECT e."Id", e."Name", e."Unit", e."Description", e."IsPositive", ec."DurationSeconds", ec."Strength", ec."ConsumableId"
                     FROM ONLY "EffectsOnConsume" ec INNER JOIN ONLY "Effects" e ON ec."EffectId" = e."Id" WHERE ec."ConsumableId" IN ($1:csv)`
};

function formatEffectOnConsume(x){ return { Name: x.Name, Values: { DurationSeconds: x.DurationSeconds !== null ? Number(x.DurationSeconds) : null, Strength: x.Strength !== null ? Number(x.Strength) : null, Unit: x.Unit, IsPositive: x.IsPositive === 1 }, Links: { "$Url": `/effects/${x.Id}` } }; }

function formatConsumable(x, effects){
  return {
    Id: x.Id,
    ItemId: x.Id + ID_OFFSET,
    Name: x.Name,
    Properties: { Description: x.Description, Weight: x.Weight !== null ? Number(x.Weight) : null, Type: x.Type, Economy: { MaxTT: x.Value !== null ? Number(x.Value) : null } },
    EffectsOnConsume: (effects[x.Id]||[]).map(formatEffectOnConsume),
    Links: { "$Url": `/stimulants/${x.Id}` }
  };
}

async function _getEffects(ids){ if (!ids.length) return {}; const { rows } = await pool.query(pgp.as.format(queries.EffectsOnConsume, [ids])); return rows.reduce((acc,r)=>{ (acc[r.ConsumableId] ||= []).push(r); return acc; },{}); }

async function getConsumables(){ const { rows } = await pool.query(queries.Consumables); const effects = await _getEffects(rows.map(r=>r.Id)); return rows.map(r => formatConsumable(r, effects)); }
async function getConsumable(idOrName){ const row = await getObjectByIdOrName(queries.Consumables, 'Consumables', idOrName); if (!row) return null; const effects = await _getEffects([row.Id]); return formatConsumable(row, effects); }

function register(app){
  /**
   * @swagger
   * /stimulants:
   *  get:
   *    description: Get all stimulants
   *    responses:
   *      '200':
   *        description: A list of stimulants
   */
  app.get('/stimulants', async (req,res) => { res.json(await getConsumables()); });
  /**
   * @swagger
   * /stimulants/{stimulant}:
   *  get:
   *    description: Get a stimulant by name or id
   *    parameters:
   *      - in: path
   *        name: stimulant
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the stimulant
   *    responses:
   *      '200':
   *        description: The stimulant
   *      '404':
   *        description: Stimulant not found
   */
  app.get('/stimulants/:stimulant', async (req,res) => { const r = await getConsumable(req.params.stimulant); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getConsumables, getConsumable };

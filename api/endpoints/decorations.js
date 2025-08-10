const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');

const queries = {
  Decorations: 'SELECT * FROM ONLY "Decorations"',
};

function formatDecoration(x){
  return { Id: x.Id, ItemId: x.Id + idOffsets.Decorations, Name: x.Name, Properties: { Description: x.Description, Weight: x.Weight !== null ? Number(x.Weight) : null, Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null } }, Links: { "$Url": `/decorations/${x.Id}` } };
}

async function getDecorations(){ const { rows } = await pool.query(queries.Decorations); return rows.map(formatDecoration); }
async function getDecoration(idOrName){ const row = await getObjectByIdOrName(queries.Decorations, 'Decorations', idOrName); return row ? formatDecoration(row) : null; }

function register(app){
  /**
   * @swagger
   * /decorations:
   *  get:
   *    description: Get all decorations
   *    responses:
   *      '200':
   *        description: A list of decorations
   */
  app.get('/decorations', async (req,res) => { res.json(await getDecorations()); });
  /**
   * @swagger
   * /decorations/{decoration}:
   *  get:
   *    description: Get a decoration by name or id
   *    parameters:
   *      - in: path
   *        name: decoration
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the decoration
   *    responses:
   *      '200':
   *        description: The decoration
   *      '404':
   *        description: Decoration not found
   */
  app.get('/decorations/:decoration', async (req,res) => { const r = await getDecoration(req.params.decoration); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getDecorations, getDecoration };

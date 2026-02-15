const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Scanners: 'SELECT * FROM ONLY "Scanners"',
};

function formatScanner(x){
  return {
    Id: x.Id,
  ItemId: x.Id + idOffsets.Scanners,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Range: x.Range !== null ? Number(x.Range) : null,
      Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null, MinTT: x.MinTT !== null ? Number(x.MinTT) : null, Decay: x.Decay !== null ? Number(x.Decay) : null }
    },
    Links: { "$Url": `/scanners/${x.Id}` }
  };
}

async function getScanners(){ const { rows } = await pool.query(queries.Scanners); return rows.map(formatScanner); }
async function getScanner(idOrName){ const row = await getObjectByIdOrName(queries.Scanners, 'Scanners', idOrName); return row ? formatScanner(row) : null; }

function register(app){
  /**
   * @swagger
   * /scanners:
   *  get:
   *    description: Get all scanners
   *    responses:
   *      '200':
   *        description: A list of scanners
   */
  app.get('/scanners', async (req,res) => { res.json(await withCache('/scanners', ['Scanners'], getScanners)); });
  /**
   * @swagger
   * /scanners/{scanner}:
   *  get:
   *    description: Get a scanner by name or id
   *    parameters:
   *      - in: path
   *        name: scanner
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the scanner
   *    responses:
   *      '200':
   *        description: The scanner
   *      '404':
   *        description: Scanner not found
   */
  app.get('/scanners/:scanner', async (req,res) => { const r = await withCachedLookup('/scanners', ['Scanners'], getScanners, req.params.scanner); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getScanners, getScanner, formatScanner };

const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { Absorbers: 'SELECT * FROM ONLY "Absorbers"' };

function formatAbsorber(x, classIds) {
  // Parity with legacy db.js formatAbsorber (field names, numeric coercion, Link path)
  return {
    Id: x.Id,
    ClassId: classIds[x.Id] || null,
    ItemId: x.Id + idOffsets.Absorbers,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: {
        Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Absorption: x.Absorption !== null ? Number(x.Absorption) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      }
    },
    Links: { "$Url": `/absorbers/${x.Id}` }
  };
}

async function getAbsorbers() {
  const { rows } = await pool.query(queries.Absorbers);
  const classIds = await loadClassIds('Absorber', rows.map(r => r.Id));
  return rows.map(r => formatAbsorber(r, classIds));
}
const getAbsorber = async(idOrName) => { const row = await getObjectByIdOrName(queries.Absorbers,'Absorbers',idOrName); if (!row) return null; const classIds = await loadClassIds('Absorber', [row.Id]); return formatAbsorber(row, classIds); };

function register(app){
  /**
   * @swagger
   * /absorbers:
   *  get:
   *    description: Get all absorbers
   *    responses:
   *      '200':
   *        description: A list of absorbers
   */
  app.get('/absorbers', async (req,res)=>{ res.json(await withCache('/absorbers', ['Absorbers', 'ClassIds'], getAbsorbers)); });
  /**
   * @swagger
   * /absorbers/{absorber}:
   *  get:
   *    description: Get an absorber by name or id
   *    parameters:
   *      - in: path
   *        name: absorber
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the absorber
   *    responses:
   *      '200':
   *        description: The absorber
   *      '404':
   *        description: Absorber not found
   */
  app.get('/absorbers/:absorber', async (req,res)=>{ const r = await withCachedLookup('/absorbers', ['Absorbers', 'ClassIds'], getAbsorbers, req.params.absorber); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getAbsorbers, getAbsorber, formatAbsorber };

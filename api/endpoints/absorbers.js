const { getObjects, getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { Absorbers: 'SELECT * FROM ONLY "Absorbers"' };

function formatAbsorber(x) {
  // Parity with legacy db.js formatAbsorber (field names, numeric coercion, Link path)
  return {
    Id: x.Id,
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
      }
    },
    Links: { "$Url": `/absorbers/${x.Id}` }
  };
}

const getAbsorbers = () => getObjects(queries.Absorbers, formatAbsorber);
const getAbsorber = async(idOrName) => { const row = await getObjectByIdOrName(queries.Absorbers,'Absorbers',idOrName); return row ? formatAbsorber(row) : null; };

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
  app.get('/absorbers', async (req,res)=>{ res.json(await withCache('/absorbers', ['Absorbers'], getAbsorbers)); });
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
  app.get('/absorbers/:absorber', async (req,res)=>{ const r = await withCachedLookup('/absorbers', ['Absorbers'], getAbsorbers, req.params.absorber); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getAbsorbers, getAbsorber, formatAbsorber };

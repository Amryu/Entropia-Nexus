const { getObjects, getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');

const queries = { Refiners: 'SELECT * FROM ONLY "Refiners"' };

function formatRefiner(x){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Refiners,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
    },
    Links: { "$Url": `/refiners/${x.Id}` },
  };
}

const getRefiners = () => getObjects(queries.Refiners, formatRefiner);
const getRefiner = async (idOrName) => { const row = await getObjectByIdOrName(queries.Refiners, 'Refiners', idOrName); return row ? formatRefiner(row) : null; };

function register(app){
  /**
   * @swagger
   * /refiners:
   *  get:
   *    description: Get all refiners
   *    responses:
   *      '200':
   *        description: A list of refiners
   */
  app.get('/refiners', async (req,res) => {
    res.json(await getRefiners());
  });
  /**
   * @swagger
   * /refiners/{refiner}:
   *  get:
   *    description: Get a refiner by name or id
   *    parameters:
   *      - in: path
   *        name: refiner
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the refiner
   *    responses:
   *      '200':
   *        description: The refiner
   *      '404':
   *        description: Refiner not found
   */
  app.get('/refiners/:refiner', async (req,res) => {
    const r = await getRefiner(req.params.refiner);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getRefiners, getRefiner, formatRefiner };

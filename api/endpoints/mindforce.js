const { getObjects, getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');

const queries = { MindforceImplants: 'SELECT * FROM ONLY "MindforceImplants"' };

function formatMindforceImplant(x){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MindforceImplants,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      MaxProfessionLevel: x.MaxLvl !== null ? Number(x.MaxLvl) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Absorption: x.Absorption !== null ? Number(x.Absorption) : null,
      }
    },
    Links: { "$Url": `/mindforceimplants/${x.Id}` }
  };
}

// DB methods
const getMindforceImplants = () => getObjects(queries.MindforceImplants, formatMindforceImplant);
const getMindforceImplant = async (idOrName) => { const row = await getObjectByIdOrName(queries.MindforceImplants, 'MindforceImplants', idOrName); return row ? formatMindforceImplant(row) : null; };

function register(app){
  /**
   * @swagger
   * /mindforceimplants:
   *  get:
   *    description: Get all Mindforce implants
   *    responses:
   *      '200':
   *        description: A list of Mindforce implants
   */
  app.get('/mindforceimplants', async (req,res) => { res.json(await getMindforceImplants()); });

  /**
   * @swagger
   * /mindforceimplants/{mindforceImplant}:
   *  get:
   *    description: Get a Mindforce implant by name or id
   *    parameters:
   *      - in: path
   *        name: mindforceImplant
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the Mindforce implant
   *    responses:
   *      '200':
   *        description: The Mindforce implant
   *      '404':
   *        description: Mindforce implant not found
   */
  app.get('/mindforceimplants/:mindforceImplant', async (req,res) => { const r = await getMindforceImplant(req.params.mindforceImplant); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getMindforceImplants, getMindforceImplant, formatMindforceImplant };

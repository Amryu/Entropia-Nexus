const { getObjects, getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Enhancers: 'SELECT "Enhancers".*, "EnhancerType"."Name" AS "Type", "EnhancerType"."Tool" AS "Tool" FROM ONLY "Enhancers" LEFT JOIN ONLY "EnhancerType" ON "Enhancers"."TypeId" = "EnhancerType"."Id"',
};

function formatEnhancer(x){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Enhancers,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Socket: x.Socket !== null ? Number(x.Socket) : null,
      Tool: x.Tool,
      Type: x.Type,
      Economy: {
        MaxTT: x.Value !== null ? Number(x.Value) : null,
      }
    },
    Links: { "$Url": `/enhancers/${x.Id}` }
  };
}

const getEnhancers = () => getObjects(queries.Enhancers, formatEnhancer);
const getEnhancer = async (idOrName) => { const row = await getObjectByIdOrName(queries.Enhancers, 'Enhancers', idOrName); return row ? formatEnhancer(row) : null; };

function register(app){
  /**
   * @swagger
   * /enhancers:
   *  get:
   *    description: Get all enhancers
   *    responses:
   *      '200':
   *        description: A list of enhancers
   */
  app.get('/enhancers', async (req,res) => { res.json(await withCache('/enhancers', ['Enhancers'], getEnhancers)); });
  /**
   * @swagger
   * /enhancers/{enhancer}:
   *  get:
   *    description: Get an enhancer by name or id
   *    parameters:
   *      - in: path
   *        name: enhancer
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the enhancer
   *    responses:
   *      '200':
   *        description: The enhancer
   *      '404':
   *        description: Enhancer not found
   */
  app.get('/enhancers/:enhancer', async (req,res) => { const r = await withCachedLookup('/enhancers', ['Enhancers'], getEnhancers, req.params.enhancer); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getEnhancers, getEnhancer };

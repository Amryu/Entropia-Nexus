const { getObjects, getObjectByIdOrName } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Effects: 'SELECT * FROM ONLY "Effects"',
};

function formatEffect(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    CanonicalName: x.CanonicalName || null,
    Properties: {
      Description: x.Description,
      IsPositive: x.IsPositive === 1,
      Unit: x.Unit,
      Limits: {
        Item: x.LimitItem,
        Action: x.LimitAction,
        Total: x.LimitTotal,
      }
    },
    Links: { "$Url": `/effects/${x.Id}` },
  };
}

const getEffects = () => getObjects(queries.Effects, formatEffect);

async function getEffect(idOrName) {
  const row = await getObjectByIdOrName(queries.Effects, 'Effects', idOrName);
  return row ? formatEffect(row) : null;
}

function register(app) {
  /**
   * @swagger
   * /effects:
   *  get:
   *    description: Get all effects
   *    responses:
   *      '200':
   *        description: A list of effects
   */
  app.get('/effects', async (req, res) => {
    res.json(await withCache('/effects', ['Effects'], getEffects));
  });

  /**
   * @swagger
   * /effects/{effect}:
   *  get:
   *    description: Get an effect by name or id
   *    parameters:
   *      - in: path
   *        name: effect
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the effect
   *    responses:
   *      '200':
   *        description: The effect
   *      '404':
   *        description: Effect not found
   */
  app.get('/effects/:effect', async (req, res) => {
    const r = await withCachedLookup('/effects', ['Effects'], getEffects, req.params.effect);
    if (r) res.json(r);
    else res.status(404).send();
  });
}

module.exports = { register, getEffects, getEffect };

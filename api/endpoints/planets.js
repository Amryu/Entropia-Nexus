const { getObjects, getObjectByIdOrName } = require('./utils');

const queries = { Planets: 'SELECT * FROM ONLY "Planets"' };

function formatPlanet(x){
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      TechnicalName: x.TechnicalName,
      Map: { X: x.X, Y: x.Y, Width: x.Width, Height: x.Height }
    },
    Links: { "$Url": `/planets/${x.Id}` }
  };
}

async function _getObjects(query, formatFn){ return getObjects(query, formatFn); }
async function _getObject(idOrName, query){ const row = await getObjectByIdOrName(query, 'Planets', idOrName); return row ? formatPlanet(row) : null; }

// DB methods
const getPlanets = () => _getObjects(queries.Planets, formatPlanet);
const getPlanet = (idOrName) => _getObject(idOrName, queries.Planets);

// Endpoint wiring
function register(app){
  /**
   * @swagger
   * /planets:
   *  get:
   *    description: Get all planets
   *    responses:
   *      '200':
   *        description: A list of planets
   */
  app.get('/planets', async (req,res) => { res.json(await getPlanets()); });
  app.get('/planets/:planet', async (req,res) => {
    /**
     * @swagger
     * /planets/{planet}:
     *  get:
     *    description: Get a planet by name or id
     *    parameters:
     *      - in: path
     *        name: planet
     *        schema:
     *          type: string
     *        required: true
     *        description: The name or id of the planet
     *    responses:
     *      '200':
     *        description: The planet
     *      '404':
     *        description: Planet not found
     */
    const result = await getPlanet(req.params.planet);
    if (result) res.json(result); else res.status(404).send();
  });
}

module.exports = { register, getPlanets, getPlanet };

const { getObjects, getObjectByIdOrName } = require('./utils');

const queries = {
  Teleporters: 'SELECT "Teleporters".*, "Planets"."Name" AS "Planet", "Planets"."TechnicalName" FROM ONLY "Teleporters" LEFT JOIN ONLY "Planets" ON "Teleporters"."PlanetId" = "Planets"."Id"',
};

function formatTeleporter(x){
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Coordinates: { Longitude: x.Longitude, Latitude: x.Latitude, Altitude: x.Altitude }
    },
    Planet: { Name: x.Planet, Properties: { TechnicalName: x.TechnicalName }, Links: { "$Url": `/planets/${x.PlanetId}` } },
    Links: { "$Url": `/teleporters/${x.Id}` }
  };
}

async function _getObjects(query, fmt){ return getObjects(query, fmt); }
async function _getObject(idOrName, query){ const row = await getObjectByIdOrName(query, 'Teleporters', idOrName); return row ? formatTeleporter(row) : null; }

const getTeleporters = () => _getObjects(queries.Teleporters, formatTeleporter);
const getTeleporter = (idOrName) => _getObject(idOrName, queries.Teleporters);

function register(app){
  /**
   * @swagger
   * /teleporters:
   *  get:
   *    description: Get all teleporters
   *    responses:
   *      '200':
   *        description: A list of teleporters
   */
  app.get('/teleporters', async (req,res) => { res.json(await getTeleporters()); });
  app.get('/teleporters/:teleporter', async (req,res) => {
    /**
     * @swagger
     * /teleporters/{teleporter}:
     *  get:
     *    description: Get a teleporter by name or id
     *    parameters:
     *      - in: path
     *        name: teleporter
     *        schema:
     *          type: string
     *        required: true
     *        description: The name or id of the teleporter
     *    responses:
     *      '200':
     *        description: The teleporter
     *      '404':
     *        description: Teleporter not found
     */
    const t = await getTeleporter(req.params.teleporter);
    if (t) res.json(t); else res.status(404).send();
  });
}

module.exports = { register, getTeleporters, getTeleporter };

const pgp = require('pg-promise')();
const { getObjects, getObjectByIdOrName, parseItemList } = require('./utils');

const queries = {
  Locations: 'SELECT "Locations".*, "Planets"."Name" AS "Planet", "Planets"."TechnicalName" FROM ONLY "Locations" LEFT JOIN ONLY "Planets" ON "Locations"."PlanetId" = "Planets"."Id"',
};

function formatLocation(x){
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Type: x.Type,
      Coordinates: { Longitude: x.Longitude, Latitude: x.Latitude, Altitude: x.Altitude }
    },
    Planet: {
      Name: x.Planet,
      Properties: { TechnicalName: x.TechnicalName },
      Links: { "$Url": `/planets/${x.PlanetId}` }
    },
    Links: { "$Url": `/locations/${x.Id}` }
  };
}

async function _getObjects(query, formatFn) { return getObjects(query, formatFn); }
async function _getObject(idOrName, query) { const row = await getObjectByIdOrName(query, 'Locations', idOrName); return row ? formatLocation(row) : null; }

// DB methods
async function getLocations(planets = null){
  let where = '';
  if (planets && planets.length) {
    where = pgp.as.format(' WHERE "Planets"."Name" IN ($1:csv)', [planets]);
  }
  return _getObjects(queries.Locations + where, formatLocation);
}

async function getLocation(idOrName){ return _getObject(idOrName, queries.Locations); }

// Endpoint wiring
function register(app){
  /**
   * @swagger
   * /locations:
   *  get:
   *    description: Get all locations
   *    parameters:
   *      - in: query
   *        name: Planet
   *        schema:
   *          type: string
   *        description: The planet to filter locations by
   *      - in: query
   *        name: Planets
   *        schema:
   *          type: string
   *        description: A comma-separated list of planets to filter locations by
   *    responses:
   *      '200':
   *        description: A list of locations
   *      '400':
   *        description: Cannot specify both Planet and Planets
   */
  app.get('/locations', async (req, res) => {
    try {
      if (req.query.Planet && req.query.Planets) return res.status(400).send('Cannot specify both Planet and Planets');
      if (req.query.Planet || req.query.Planets) {
        const planets = req.query.Planets ? parseItemList(req.query.Planets) : [req.query.Planet];
        if (planets.length === 0) return res.status(400).send('Planets cannot be empty');
        res.json(await getLocations(planets));
      } else {
        res.json(await getLocations());
      }
    } catch(e) { res.status(500).send('Internal server error'); }
  });

  /**
   * @swagger
   * /locations/{location}:
   *  get:
   *    description: Get a location by name or id
   *    parameters:
   *      - in: path
   *        name: location
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the location
   *    responses:
   *      '200':
   *        description: The location
   *      '404':
   *        description: Location not found
   */
  app.get('/locations/:location', async (req,res) => {
    const result = await getLocation(req.params.location);
    if (result) res.json(result); else res.status(404).send();
  });
}

module.exports = { register, getLocations, getLocation };

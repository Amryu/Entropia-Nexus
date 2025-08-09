const pgp = require('pg-promise')();
const { getObjects, getObjectByIdOrName, parseItemList } = require('./utils');

const queries = {
  Areas: 'SELECT "Areas".*, "Planets"."Name" AS "Planet", "Planets"."TechnicalName" FROM ONLY "Areas" LEFT JOIN ONLY "Planets" ON "Areas"."PlanetId" = "Planets"."Id"',
};

function formatArea(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Type: x.Type,
      Shape: x.Shape,
      Data: x.Data,
      Coordinates: { Longitude: x.Longitude, Latitude: x.Latitude, Altitude: x.Altitude }
    },
    Planet: {
      Name: x.Planet,
      Properties: { TechnicalName: x.TechnicalName },
      Links: { "$Url": `/planets/${x.PlanetId}` }
    },
    Links: { "$Url": `/areas/${x.Id}` }
  };
}

async function _getObjects(query, formatFn) { return getObjects(query, formatFn); }
async function _getObject(idOrName, query) { const row = await getObjectByIdOrName(query, 'Areas', idOrName); return row ? formatArea(row) : null; }

// DB methods
async function getAreas(planets = null) {
  let where = '';
  if (planets && planets.length) {
    where = pgp.as.format(' WHERE "Planets"."Name" IN ($1:csv)', [planets]);
  }
  return _getObjects(queries.Areas + where, formatArea);
}

async function getArea(idOrName) { return _getObject(idOrName, queries.Areas); }

// Endpoint wiring
function register(app) {
  /**
   * @swagger
   * /areas:
   *  get:
   *    description: Get all areas
   *    parameters:
   *      - in: query
   *        name: Planet
   *        schema:
   *          type: string
   *        description: The planet to filter areas by
   *      - in: query
   *        name: Planets
   *        schema:
   *          type: string
   *        description: A comma-separated list of planets to filter areas by
   *    responses:
   *      '200':
   *        description: A list of areas
   *      '400':
   *        description: Cannot specify both Planet and Planets
   */
  app.get('/areas', async (req, res) => {
    try {
      if (req.query.Planet && req.query.Planets) return res.status(400).send('Cannot specify both Planet and Planets');
      if (req.query.Planet || req.query.Planets) {
        const planets = req.query.Planets ? parseItemList(req.query.Planets) : [req.query.Planet];
        if (planets.length === 0) return res.status(400).send('Planets cannot be empty');
        res.json(await getAreas(planets));
      } else {
        res.json(await getAreas());
      }
    } catch (e) { res.status(500).send('Internal server error'); }
  });

  /**
   * @swagger
   * /areas/{area}:
   *  get:
   *    description: Get an area by name or id
   *    parameters:
   *      - in: path
   *        name: area
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the area
   *    responses:
   *      '200':
   *        description: The area
   *      '404':
   *        description: Area not found
   */
  app.get('/areas/:area', async (req, res) => {
    const result = await getArea(req.params.area);
    if (result) res.json(result); else res.status(404).send('Area not found');
  });
}

module.exports = { register, getAreas, getArea };

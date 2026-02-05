const pgp = require('pg-promise')();
const { pool } = require('./dbClient');
const { parseItemList } = require('./utils');

const queries = {
  Areas: `
    SELECT l.*,
           p."Name" AS "Planet",
           p."TechnicalName",
           a."Type" AS "AreaType",
           a."Shape",
           a."Data"
    FROM ONLY "Locations" l
    LEFT JOIN ONLY "Planets" p ON l."PlanetId" = p."Id"
    JOIN ONLY "Areas" a ON l."Id" = a."LocationId"
    WHERE l."Type" = 'Area'
  `,
};

function formatArea(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Type: x.AreaType,
      Shape: x.Shape,
      Data: x.Data,
      Coordinates: { Longitude: x.Longitude, Latitude: x.Latitude, Altitude: x.Altitude }
    },
    Planet: x.Planet ? {
      Name: x.Planet,
      Properties: { TechnicalName: x.TechnicalName },
      Links: { "$Url": `/planets/${x.PlanetId}` }
    } : null,
    Links: { "$Url": `/areas/${x.Id}` }
  };
}

// DB methods
async function getAreas(planets = null, areaTypes = null) {
  let where = [];
  let params = [];
  let paramIndex = 1;

  if (planets && planets.length) {
    where.push(`p."Name" IN (${planets.map(() => `$${paramIndex++}`).join(', ')})`);
    params.push(...planets);
  }

  if (areaTypes && areaTypes.length) {
    where.push(`a."Type"::text IN (${areaTypes.map(() => `$${paramIndex++}`).join(', ')})`);
    params.push(...areaTypes);
  }

  const whereClause = where.length > 0 ? ` AND ${where.join(' AND ')}` : '';
  const sql = queries.Areas + whereClause + ' ORDER BY l."Name"';

  const { rows } = await pool.query(sql, params);
  return rows.map(formatArea);
}

async function getArea(idOrName) {
  const byId = /^(\d+)$/.test(String(idOrName));
  const whereClause = byId ? ' AND l."Id" = $1' : ' AND l."Name" = $1';
  const { rows } = await pool.query(queries.Areas + whereClause, [idOrName]);
  return rows.length === 1 ? formatArea(rows[0]) : null;
}

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
   *      - in: query
   *        name: Type
   *        schema:
   *          type: string
   *        description: Area type to filter by (MobArea, LandArea, etc.)
   *      - in: query
   *        name: Types
   *        schema:
   *          type: string
   *        description: Comma-separated list of area types
   *    responses:
   *      '200':
   *        description: A list of areas
   *      '400':
   *        description: Cannot specify both Planet and Planets
   */
  app.get('/areas', async (req, res) => {
    try {
      if (req.query.Planet && req.query.Planets) {
        return res.status(400).send('Cannot specify both Planet and Planets');
      }
      if (req.query.Type && req.query.Types) {
        return res.status(400).send('Cannot specify both Type and Types');
      }

      let planets = null;
      let areaTypes = null;

      if (req.query.Planet || req.query.Planets) {
        planets = req.query.Planets ? parseItemList(req.query.Planets) : [req.query.Planet];
        if (planets.length === 0) return res.status(400).send('Planets cannot be empty');
      }

      if (req.query.Type || req.query.Types) {
        areaTypes = req.query.Types ? parseItemList(req.query.Types) : [req.query.Type];
      }

      res.json(await getAreas(planets, areaTypes));
    } catch (e) {
      console.error('Error fetching areas:', e);
      res.status(500).send('Internal server error');
    }
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

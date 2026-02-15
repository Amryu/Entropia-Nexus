const { pool } = require('./dbClient');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Teleporters: `
    SELECT l.*,
           p."Name" AS "Planet",
           p."TechnicalName"
    FROM ONLY "Locations" l
    LEFT JOIN ONLY "Planets" p ON l."PlanetId" = p."Id"
    WHERE l."Type" = 'Teleporter'
  `,
};

function formatTeleporter(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Coordinates: { Longitude: x.Longitude, Latitude: x.Latitude, Altitude: x.Altitude }
    },
    Planet: x.Planet ? {
      Name: x.Planet,
      Properties: { TechnicalName: x.TechnicalName },
      Links: { "$Url": `/planets/${x.PlanetId}` }
    } : null,
    Links: { "$Url": `/teleporters/${x.Id}` }
  };
}

async function getTeleporters() {
  const { rows } = await pool.query(queries.Teleporters + ' ORDER BY l."Name"');
  return rows.map(formatTeleporter);
}

async function getTeleporter(idOrName) {
  const byId = /^(\d+)$/.test(String(idOrName));
  const whereClause = byId ? ' AND l."Id" = $1' : ' AND l."Name" = $1';
  const { rows } = await pool.query(queries.Teleporters + whereClause, [idOrName]);
  return rows.length === 1 ? formatTeleporter(rows[0]) : null;
}

function register(app) {
  /**
   * @swagger
   * /teleporters:
   *  get:
   *    description: Get all teleporters
   *    responses:
   *      '200':
   *        description: A list of teleporters
   */
  app.get('/teleporters', async (req, res) => { res.json(await withCache('/teleporters', ['Locations', 'Planets'], getTeleporters)); });

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
  app.get('/teleporters/:teleporter', async (req, res) => {
    const t = await withCachedLookup('/teleporters', ['Locations', 'Planets'], getTeleporters, req.params.teleporter);
    if (t) res.json(t); else res.status(404).send('Teleporter not found');
  });
}

module.exports = { register, getTeleporters, getTeleporter };

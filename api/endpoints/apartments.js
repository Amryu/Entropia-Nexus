const { pool, usersPool } = require('./dbClient');

const queries = {
  Apartments: 'SELECT "Estates".*, "Planets"."Name" AS "Planet", "Planets"."TechnicalName" FROM ONLY "Estates" LEFT JOIN ONLY "Planets" ON "Estates"."PlanetId" = "Planets"."Id" WHERE "Estates"."Type" = \'Apartment\'',
};

async function _fetchEstateOwners(ownerIds) {
  if (!ownerIds || ownerIds.length === 0) return {};
  try {
    const { rows } = await usersPool.query('SELECT id, eu_name FROM users WHERE id = ANY($1) AND verified = true', [ownerIds]);
    const map = {};
    rows.forEach(r => map[r.id] = { Name: r.eu_name });
    return map;
  } catch {
    return {};
  }
}

async function _fetchEstateSections(estateIds){
  if (!estateIds || estateIds.length === 0) return {};
  try {
    const { rows } = await pool.query('SELECT "EstateId", "Name", "Description", "ItemPoints" FROM ONLY "EstateSections" WHERE "EstateId" = ANY($1) ORDER BY "EstateId", "Name"', [estateIds]);
    const m = {};
    for (const r of rows) {
      if (!m[r.EstateId]) m[r.EstateId] = [];
      m[r.EstateId].push({
        Name: r.Name,
        Description: r.Description ?? null,
        ItemPoints: r.ItemPoints != null ? Number(r.ItemPoints) : null,
        MaxItemPoints: r.ItemPoints != null ? Number(r.ItemPoints) : null
      });
    }
    return m;
  } catch {
    return {};
  }
}

function formatApartment(x, add = {}) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description ?? null,
      Type: x.Type ?? 'Apartment',
      Coordinates: {
        Longitude: x.Longitude != null ? Number(x.Longitude) : null,
        Latitude: x.Latitude != null ? Number(x.Latitude) : null,
        Altitude: x.Altitude != null ? Number(x.Altitude) : null,
      }
    },
    Planet: x.Planet ? { Name: x.Planet, Properties: { TechnicalName: x.TechnicalName }, Links: { "$Url": `/planets/${x.PlanetId}` } } : null,
    OwnerId: x.OwnerId ?? null,
    Owner: add.owner || null,
    MaxGuests: x.MaxGuests != null ? Number(x.MaxGuests) : null,
    Sections: add.sections || [],
    Links: { "$Url": `/apartments/${x.Id}` }
  };
}

// DB methods
async function getApartments(){
  const { rows } = await pool.query(queries.Apartments);
  const ownerIds = [...new Set(rows.map(s => s.OwnerId).filter(id => id != null))];
  const estateIds = rows.map(s => s.Id);
  const [owners, sections] = await Promise.all([
    _fetchEstateOwners(ownerIds),
    _fetchEstateSections(estateIds)
  ]);
  return rows.map(x => formatApartment(x, { owner: owners[x.OwnerId] || null, sections: sections[x.Id] || [] }));
}

async function getApartment(idOrName){
  const byId = /^(\d+)$/.test(String(idOrName));
  const sql = byId ? `${queries.Apartments} AND "Estates"."Id" = $1` : `${queries.Apartments} AND "Estates"."Name" = $1`;
  const { rows } = await pool.query(sql, [idOrName]);
  if (rows.length !== 1) return null;
  const apartment = rows[0];
  const [owners, sections] = await Promise.all([
    apartment.OwnerId ? _fetchEstateOwners([apartment.OwnerId]) : Promise.resolve({}),
    _fetchEstateSections([apartment.Id])
  ]);
  return formatApartment(apartment, { owner: owners[apartment.OwnerId] || null, sections: sections[apartment.Id] || [] });
}

// Endpoint wiring
function register(app){
  /**
   * @swagger
   * /apartments:
   *  get:
   *    description: Get all apartments
   *    responses:
   *      '200':
   *        description: A list of apartments
   */
  app.get('/apartments', async (req, res) => { res.json(await getApartments()); });

  /**
   * @swagger
   * /apartments/{apartment}:
   *  get:
   *    description: Get an apartment by name or id
   *    parameters:
   *      - in: path
   *        name: apartment
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the apartment
   *    responses:
   *      '200':
   *        description: The apartment
   *      '404':
   *        description: Apartment not found
   */
  app.get('/apartments/:apartment', async (req, res) => {
    const apartment = await getApartment(req.params.apartment);
    if (apartment) res.json(apartment); else res.status(404).send();
  });
}

module.exports = { register, getApartments, getApartment };

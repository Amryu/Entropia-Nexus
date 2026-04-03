const pgp = require('pg-promise')();
const { pool, usersPool } = require('./dbClient');
const { getObjects, parseItemList } = require('./utils');
const { withCache } = require('./responseCache');
const { formatMobMaturity } = require('./mobmaturities');

// Location types for filtering
const LOCATION_TYPES = {
  Teleporter: 'Teleporter',
  Npc: 'Npc',
  Interactable: 'Interactable',
  Area: 'Area',
  Estate: 'Estate',
  Outpost: 'Outpost',
  Camp: 'Camp',
  City: 'City',

  RevivalPoint: 'RevivalPoint',
  InstanceEntrance: 'InstanceEntrance',
  Vendor: 'Vendor'
};

// Base query for locations
const queries = {
  Locations: `
    SELECT l.*,
           p."Name" AS "Planet",
           p."TechnicalName" AS "PlanetTechnicalName",
           parent."Name" AS "ParentLocationName",
           parent."Type"::text AS "ParentLocationType",
           -- Area extension data
           a."Type"::text AS "AreaType",
           a."Shape"::text AS "AreaShape",
           a."Data" AS "AreaData",
           -- Estate extension data
           e."Type"::text AS "EstateType",
           e."OwnerId" AS "EstateOwnerId",
           e."OwnerName" AS "EstateOwnerName",
           e."ItemTradeAvailable" AS "EstateItemTradeAvailable",
           e."MaxGuests" AS "EstateMaxGuests",
           -- LandArea extension data
           la."TaxRateHunting" AS "LandAreaTaxRateHunting",
           la."TaxRateMining" AS "LandAreaTaxRateMining",
           la."TaxRateShops" AS "LandAreaTaxRateShops",
           la."OwnerId" AS "LandAreaOwnerId",
           la."OwnerName" AS "LandAreaOwnerName",
           -- MobSpawn extension data
           ms."Density" AS "MobSpawnDensity",
           ms."IsShared" AS "MobSpawnIsShared",
           ms."IsEvent" AS "MobSpawnIsEvent",
           ms."Notes" AS "MobSpawnNotes",
           ms."RecurringEventId" AS "MobSpawnRecurringEventId",
           re."Name" AS "MobSpawnRecurringEventName",
           re."Color" AS "MobSpawnRecurringEventColor"
    FROM ONLY "Locations" l
    LEFT JOIN ONLY "Planets" p ON l."PlanetId" = p."Id"
    LEFT JOIN ONLY "Locations" parent ON l."ParentLocationId" = parent."Id"
    LEFT JOIN ONLY "Areas" a ON l."Id" = a."LocationId"
    LEFT JOIN ONLY "Estates" e ON l."Id" = e."LocationId"
    LEFT JOIN ONLY "LandAreas" la ON l."Id" = la."LocationId"
    LEFT JOIN ONLY "MobSpawns" ms ON l."Id" = ms."LocationId"
    LEFT JOIN ONLY "RecurringEvents" re ON ms."RecurringEventId" = re."Id"
  `,
  Facilities: `
    SELECT lf."LocationId", f."Id" AS "FacilityId", f."Name", f."Description", f."Icon"
    FROM ONLY "LocationFacilities" lf
    JOIN ONLY "Facilities" f ON lf."FacilityId" = f."Id"
  `,
  WaveEventWaves: `
    SELECT w."LocationId", w."Id", w."WaveIndex", w."TimeToComplete", w."MobMaturities"
    FROM ONLY "WaveEventWaves" w
  `
};

// Fetch facilities for a set of location IDs
async function _fetchFacilities(locationIds) {
  if (!locationIds || locationIds.length === 0) return {};
  try {
    const { rows } = await pool.query(
      `${queries.Facilities} WHERE lf."LocationId" = ANY($1) ORDER BY f."Name"`,
      [locationIds]
    );
    const map = {};
    for (const r of rows) {
      if (!map[r.LocationId]) map[r.LocationId] = [];
      map[r.LocationId].push({
        Id: r.FacilityId,
        Name: r.Name,
        Description: r.Description,
        Icon: r.Icon
      });
    }
    return map;
  } catch {
    return {};
  }
}

// Fetch wave event waves for a set of location IDs, resolving maturity IDs to full objects
async function _fetchWaveEventWaves(locationIds) {
  if (!locationIds || locationIds.length === 0) return {};
  try {
    const { rows } = await pool.query(
      `${queries.WaveEventWaves} WHERE w."LocationId" = ANY($1) ORDER BY w."LocationId", w."WaveIndex"`,
      [locationIds]
    );

    // Collect all unique maturity IDs across all waves
    const allMaturityIds = new Set();
    for (const r of rows) {
      for (const id of (r.MobMaturities || [])) {
        allMaturityIds.add(id);
      }
    }

    // Resolve maturity IDs to full maturity objects
    let maturityMap = {};
    if (allMaturityIds.size > 0) {
      const { rows: matRows } = await pool.query(
        `SELECT mm.*, m."Name" AS "Mob", m."Id" AS "MobId"
         FROM ONLY "MobMaturities" mm
         INNER JOIN ONLY "Mobs" m ON mm."MobId" = m."Id"
         WHERE mm."Id" = ANY($1::int[])`,
        [Array.from(allMaturityIds)]
      );
      for (const r of matRows) {
        maturityMap[r.Id] = {
          IsRare: false,
          Maturity: formatMobMaturity(r)
        };
      }
    }

    const map = {};
    for (const r of rows) {
      if (!map[r.LocationId]) map[r.LocationId] = [];
      const ids = r.MobMaturities || [];
      map[r.LocationId].push({
        Id: r.Id,
        WaveIndex: r.WaveIndex,
        TimeToComplete: r.TimeToComplete,
        MobMaturities: ids,
        Maturities: ids.map(id => maturityMap[id]).filter(Boolean)
      });
    }
    return map;
  } catch (e) {
    console.error('Error fetching wave event waves:', e);
    return {};
  }
}

// Fetch mob spawn maturities for a set of MobArea location IDs
async function _fetchMobSpawnMaturities(locationIds) {
  if (!locationIds || locationIds.length === 0) return {};
  try {
    const { rows } = await pool.query(
      `SELECT msm."LocationId", msm."IsRare", mm.*, m."Name" AS "Mob", m."Id" AS "MobId"
       FROM ONLY "MobSpawnMaturities" msm
       INNER JOIN ONLY "MobMaturities" mm ON msm."MaturityId" = mm."Id"
       INNER JOIN ONLY "Mobs" m ON mm."MobId" = m."Id"
       WHERE msm."LocationId" = ANY($1::int[])`,
      [locationIds]
    );
    const map = {};
    for (const r of rows) {
      if (!map[r.LocationId]) map[r.LocationId] = [];
      map[r.LocationId].push({
        IsRare: r.IsRare === 1 || r.IsRare === true,
        Maturity: formatMobMaturity(r)
      });
    }
    return map;
  } catch (e) {
    console.error('Error fetching mob spawn maturities:', e);
    return {};
  }
}

// Resolve OwnerId values to eu_names from the users database
async function _fetchOwnerNames(ownerIds) {
  if (!ownerIds || ownerIds.length === 0) return {};
  try {
    const { rows } = await usersPool.query(
      'SELECT id, eu_name FROM users WHERE id = ANY($1) AND verified = true',
      [ownerIds]
    );
    const map = {};
    for (const r of rows) map[r.id] = r.eu_name;
    return map;
  } catch {
    return {};
  }
}

function formatLocation(x, add = {}) {
  const result = {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Type: x.Type,
      Description: x.Description,
      Coordinates: {
        Longitude: x.Longitude,
        Latitude: x.Latitude,
        Altitude: x.Altitude
      },
      TechnicalId: x.TechnicalId
    },
    Planet: x.Planet ? {
      Name: x.Planet,
      Properties: { TechnicalName: x.PlanetTechnicalName },
      Links: { "$Url": `/planets/${x.PlanetId}` }
    } : null,
    ParentLocation: x.ParentLocationId ? {
      Id: x.ParentLocationId,
      Name: x.ParentLocationName,
      Type: x.ParentLocationType,
      Links: { "$Url": `/locations/${x.ParentLocationId}` }
    } : null,
    Facilities: add.facilities || [],
    Links: { "$Url": `/locations/${x.Id}` }
  };

  // Add type-specific extension data
  if (x.Type === 'Area' && x.AreaType) {
    result.Properties.AreaType = x.AreaType;
    result.Properties.Shape = x.AreaShape;
    result.Properties.Data = x.AreaData;
    if (x.AreaType === 'MobArea') {
      result.Properties.Density = x.MobSpawnDensity ?? null;
      result.Properties.IsShared = x.MobSpawnIsShared === 1 || x.MobSpawnIsShared === true;
      result.Properties.IsEvent = x.MobSpawnIsEvent === 1 || x.MobSpawnIsEvent === true;
      result.Properties.Notes = x.MobSpawnNotes ?? null;
      result.Properties.RecurringEventId = x.MobSpawnRecurringEventId ?? null;
      result.Properties.RecurringEventName = x.MobSpawnRecurringEventName ?? null;
      result.Properties.RecurringEventColor = x.MobSpawnRecurringEventColor ?? null;
    }
    if (x.AreaType === 'LandArea') {
      result.Properties.TaxRateHunting = x.LandAreaTaxRateHunting ?? null;
      result.Properties.TaxRateMining = x.LandAreaTaxRateMining ?? null;
      result.Properties.TaxRateShops = x.LandAreaTaxRateShops ?? null;
      // Owner as top-level NamedEntity: { Id, Name }
      const ownerName = (x.LandAreaOwnerId && add.ownerNames?.[x.LandAreaOwnerId])
        || x.LandAreaOwnerName
        || null;
      if (x.LandAreaOwnerId || ownerName) {
        result.Owner = {
          Id: x.LandAreaOwnerId ?? null,
          Name: ownerName
        };
      }
    }
  }

  if (x.Type === 'Estate' && x.EstateType) {
    result.Properties.EstateType = x.EstateType;
    result.Properties.ItemTradeAvailable = x.EstateItemTradeAvailable;
    result.Properties.MaxGuests = x.EstateMaxGuests;
    // Owner as top-level NamedEntity
    const estateOwnerName = (x.EstateOwnerId && add.ownerNames?.[x.EstateOwnerId])
      || x.EstateOwnerName
      || null;
    if (x.EstateOwnerId || estateOwnerName) {
      result.Owner = {
        Id: x.EstateOwnerId ?? null,
        Name: estateOwnerName
      };
    }
  }

  if (x.AreaType === 'WaveEventArea' && add.waves) {
    result.Waves = add.waves;
  }

  if (add.maturities) {
    result.Maturities = add.maturities;
  }

  return result;
}

// DB methods
async function getLocations(options = {}) {
  const { planets, types, areaTypes, estateTypes, facilities, parentId } = options;

  let where = [];
  let params = [];
  let paramIndex = 1;

  if (planets && planets.length) {
    where.push(`p."Name" IN (${planets.map(() => `$${paramIndex++}`).join(', ')})`);
    params.push(...planets);
  }

  if (types && types.length) {
    where.push(`l."Type"::text IN (${types.map(() => `$${paramIndex++}`).join(', ')})`);
    params.push(...types);
  }

  if (areaTypes && areaTypes.length) {
    where.push(`a."Type"::text IN (${areaTypes.map(() => `$${paramIndex++}`).join(', ')})`);
    params.push(...areaTypes);
  }

  if (estateTypes && estateTypes.length) {
    where.push(`e."Type"::text IN (${estateTypes.map(() => `$${paramIndex++}`).join(', ')})`);
    params.push(...estateTypes);
  }

  if (parentId != null) {
    where.push(`l."ParentLocationId" = $${paramIndex++}`);
    params.push(parentId);
  }

  const whereClause = where.length > 0 ? ` WHERE ${where.join(' AND ')}` : '';
  const sql = queries.Locations + whereClause + ' ORDER BY l."Name"';

  const { rows } = await pool.query(sql, params);

  // Get location IDs for fetching related data
  const locationIds = rows.map(r => r.Id);

  // Fetch facilities
  const facilitiesMap = await _fetchFacilities(locationIds);

  // Filter by facilities if specified
  let filteredRows = rows;
  if (facilities && facilities.length) {
    filteredRows = rows.filter(r => {
      const locFacilities = facilitiesMap[r.Id] || [];
      return facilities.some(f => locFacilities.some(lf => lf.Name.toLowerCase() === f.toLowerCase()));
    });
  }

  // Fetch wave event waves, mob spawn maturities, and owner names
  const waveEventIds = filteredRows.filter(r => r.AreaType === 'WaveEventArea').map(r => r.Id);
  const mobAreaIds = filteredRows.filter(r => r.AreaType === 'MobArea').map(r => r.Id);
  const ownerIds = [...new Set(filteredRows.map(r => r.LandAreaOwnerId || r.EstateOwnerId).filter(Boolean))];
  const [wavesMap, maturitiesMap, ownerNames] = await Promise.all([
    _fetchWaveEventWaves(waveEventIds),
    _fetchMobSpawnMaturities(mobAreaIds),
    _fetchOwnerNames(ownerIds)
  ]);

  return filteredRows.map(x => formatLocation(x, {
    facilities: facilitiesMap[x.Id] || [],
    waves: wavesMap[x.Id] || null,
    maturities: maturitiesMap[x.Id] || null,
    ownerNames
  }));
}

async function getLocation(idOrName) {
  const byId = /^(\d+)$/.test(String(idOrName));
  const whereClause = byId ? ' WHERE l."Id" = $1' : ' WHERE l."Name" = $1';
  const sql = queries.Locations + whereClause;

  const { rows } = await pool.query(sql, [idOrName]);
  if (rows.length === 0) return null;

  // If fetching by name and multiple matches found, return them all for disambiguation
  if (!byId && rows.length > 1) {
    const locationIds = rows.map(r => r.Id);
    const ownerIds = [...new Set(rows.map(r => r.LandAreaOwnerId || r.EstateOwnerId).filter(Boolean))];
    const [facilitiesMap, wavesMap, maturitiesMap, ownerNames] = await Promise.all([
      _fetchFacilities(locationIds),
      _fetchWaveEventWaves(rows.filter(r => r.AreaType === 'WaveEventArea').map(r => r.Id)),
      _fetchMobSpawnMaturities(rows.filter(r => r.AreaType === 'MobArea').map(r => r.Id)),
      _fetchOwnerNames(ownerIds)
    ]);

    return {
      disambiguation: true,
      matches: rows.map(x => formatLocation(x, {
        facilities: facilitiesMap[x.Id] || [],
        waves: wavesMap[x.Id] || null,
        maturities: maturitiesMap[x.Id] || null,
        ownerNames
      }))
    };
  }

  const location = rows[0];
  const [facilities, waves, maturities, ownerNames] = await Promise.all([
    _fetchFacilities([location.Id]),
    location.AreaType === 'WaveEventArea' ? _fetchWaveEventWaves([location.Id]) : Promise.resolve({}),
    location.AreaType === 'MobArea' ? _fetchMobSpawnMaturities([location.Id]) : Promise.resolve({}),
    (location.LandAreaOwnerId || location.EstateOwnerId) ? _fetchOwnerNames([location.LandAreaOwnerId || location.EstateOwnerId].filter(Boolean)) : Promise.resolve({})
  ]);

  return formatLocation(location, {
    facilities: facilities[location.Id] || [],
    waves: waves[location.Id] || null,
    maturities: maturities[location.Id] || null,
    ownerNames
  });
}

// Get all facilities
async function getFacilities() {
  const { rows } = await pool.query('SELECT * FROM ONLY "Facilities" ORDER BY "Name"');
  return rows.map(f => ({
    Id: f.Id,
    Name: f.Name,
    Description: f.Description,
    Icon: f.Icon
  }));
}

// Endpoint wiring
function register(app) {
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
   *      - in: query
   *        name: Type
   *        schema:
   *          type: string
   *        description: Location type to filter by (Teleporter, Npc, Interactable, Area, Estate, Outpost, Camp, City)
   *      - in: query
   *        name: Types
   *        schema:
   *          type: string
   *        description: Comma-separated list of location types
   *      - in: query
   *        name: AreaType
   *        schema:
   *          type: string
   *        description: Area subtype to filter by (only for Area type)
   *      - in: query
   *        name: EstateType
   *        schema:
   *          type: string
   *        description: Estate subtype to filter by (Shop, Apartment)
   *      - in: query
   *        name: Facilities
   *        schema:
   *          type: string
   *        description: Comma-separated list of facility names to filter by
   *      - in: query
   *        name: ParentId
   *        schema:
   *          type: integer
   *        description: Parent location ID to filter by
   *    responses:
   *      '200':
   *        description: A list of locations
   *      '400':
   *        description: Invalid parameters
   */
  app.get('/locations', async (req, res) => {
    try {
      if (req.query.Planet && req.query.Planets) {
        return res.status(400).send('Cannot specify both Planet and Planets');
      }
      if (req.query.Type && req.query.Types) {
        return res.status(400).send('Cannot specify both Type and Types');
      }

      const options = {};

      // Planet filtering
      if (req.query.Planet || req.query.Planets) {
        options.planets = req.query.Planets ? parseItemList(req.query.Planets) : [req.query.Planet];
        if (options.planets.length === 0) return res.status(400).send('Planets cannot be empty');
      }

      // Type filtering
      if (req.query.Type || req.query.Types) {
        options.types = req.query.Types ? parseItemList(req.query.Types) : [req.query.Type];
      }

      // Area subtype filtering
      if (req.query.AreaType || req.query.AreaTypes) {
        options.areaTypes = req.query.AreaTypes ? parseItemList(req.query.AreaTypes) : [req.query.AreaType];
        // Automatically filter to Area type
        if (!options.types) options.types = ['Area'];
      }

      // Estate subtype filtering
      if (req.query.EstateType || req.query.EstateTypes) {
        options.estateTypes = req.query.EstateTypes ? parseItemList(req.query.EstateTypes) : [req.query.EstateType];
        // Automatically filter to Estate type
        if (!options.types) options.types = ['Estate'];
      }

      // Facility filtering
      if (req.query.Facilities) {
        options.facilities = parseItemList(req.query.Facilities);
      }

      // Parent location filtering
      if (req.query.ParentId) {
        options.parentId = Number(req.query.ParentId);
        if (!Number.isFinite(options.parentId)) {
          return res.status(400).send('ParentId must be a number');
        }
      }

      const hasFilters = Object.keys(options).length > 0;
      if (hasFilters) {
        res.json(await getLocations(options));
      } else {
        res.json(await withCache('/locations', ['Locations', 'Planets', 'Areas', 'Estates', 'LandAreas', 'LocationFacilities', 'Facilities', 'WaveEventWaves', 'MobSpawns', 'MobSpawnMaturities', 'MobMaturities', 'Mobs', 'RecurringEvents'], getLocations));
      }
    } catch (e) {
      console.error('Error fetching locations:', e);
      res.status(500).send('Internal server error');
    }
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
  app.get('/locations/:location', async (req, res) => {
    const result = await getLocation(req.params.location);
    if (result) res.json(result); else res.status(404).send('Location not found');
  });

  /**
   * @swagger
   * /facilities:
   *  get:
   *    description: Get all facilities
   *    responses:
   *      '200':
   *        description: A list of facilities
   */
  app.get('/facilities', async (req, res) => {
    try {
      res.json(await getFacilities());
    } catch (e) {
      console.error('Error fetching facilities:', e);
      res.status(500).send('Internal server error');
    }
  });
}

module.exports = {
  register,
  getLocations,
  getLocation,
  getFacilities,
  LOCATION_TYPES
};

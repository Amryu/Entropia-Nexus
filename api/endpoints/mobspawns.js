const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { formatMobMaturity } = require('./mobmaturities');

// Base query for mob spawns: one row per Area (MobArea), joined to MobSpawns and Planets only
const baseQuery = `
	SELECT 
		"Areas"."Id" AS "Id",
		COALESCE("MobSpawns"."Name", "Areas"."Name") AS "Name",
		"MobSpawns"."Description",
		"MobSpawns"."Density",
		"MobSpawns"."IsShared",
		"MobSpawns"."IsEvent",
		"MobSpawns"."Notes",
		"Areas"."Type" AS "Type",
		"Areas"."Type" AS "AreaType",
		"Areas"."Shape",
		"Areas"."Data",
		"Areas"."Longitude",
		"Areas"."Latitude",
		"Areas"."Altitude",
		"Areas"."PlanetId",
		"Planets"."Name" AS "Planet",
		"Planets"."TechnicalName"
	FROM ONLY "Areas"
	INNER JOIN ONLY "MobSpawns" ON "MobSpawns"."AreaId" = "Areas"."Id"
	INNER JOIN ONLY "Planets" ON "Areas"."PlanetId" = "Planets"."Id"
	WHERE "Areas"."Type" = 'MobArea'
`;

function getBaseWrappedQuery() {
  return `SELECT * FROM (${baseQuery}) AS base`;
}

function formatSpawn(x) {
	return {
		Id: x.Id,
		Name: x.Name,
		Properties: {
			Description: x.Description,
			Density: x.Density,
			IsShared: x.IsShared === 1 || x.IsShared === true,
			IsEvent: x.IsEvent === 1 || x.IsEvent === true,
			Notes: x.Notes,
			Type: x.Type,
			Shape: x.Shape,
			Data: x.Data,
			Coordinates: {
				Longitude: x.Longitude,
				Latitude: x.Latitude,
				Altitude: x.Altitude
			}
		},
		Planet: {
			Name: x.Planet,
			Properties: {
				TechnicalName: x.TechnicalName
			},
			Links: {
				"$Url": `/planets/${x.PlanetId}`
			}
		},
		Maturities: Array.isArray(x.Maturities) ? x.Maturities : [],
		Links: {
			"$Url": `/mobspawns/${x.Id}`
		}
	};
}

function _formatMobSpawnMaturity(x) {
	return {
		IsRare: x.IsRare === 1 || x.IsRare === true,
		Maturity: formatMobMaturity(x, [])
	};
}

// Helper for attaching spawns per mob (optionally filter by planet)
async function getMobSpawns(mobIds, planet) {
	if (!mobIds || mobIds.length === 0) return {};
	// Filter by mobIds via EXISTS to avoid row explosion
	let sql = getBaseWrappedQuery() +
		' WHERE EXISTS (\
			SELECT 1 FROM ONLY "MobSpawnMaturities" msm\
			INNER JOIN ONLY "MobMaturities" mm ON msm."MaturityId" = mm."Id"\
			WHERE msm."AreaId" = base."Id" AND mm."MobId" = ANY($1::int[])\
		)';
	const params = [mobIds];
	if (planet) {
		// Push planet filter on actual columns (Areas/Planets). We have Planet name in base.
		sql += ' AND base."Planet" = $2';
		params.push(planet);
	}
	const { rows } = await pool.query(sql, params);
	if (!rows.length) return {};

	// Deduplicate rows by Area Id (one spawn per area) and seed container
	const spawnsById = {};
	for (const row of rows) {
		if (!spawnsById[row.Id]) {
			spawnsById[row.Id] = { ...row, Maturities: [] };
		}
	}
		const Ids = Object.keys(spawnsById).map(x => parseInt(x,10)).filter(Number.isFinite);
		const maturitiesSql = `
			SELECT msm.*, mm.*, m."Name" AS "Mob", m."Id" AS "MobId", p."Name" AS "Planet", p."TechnicalName"
			FROM ONLY "MobSpawnMaturities" msm
			INNER JOIN ONLY "MobMaturities" mm ON msm."MaturityId" = mm."Id"
			INNER JOIN ONLY "Mobs" m ON mm."MobId" = m."Id"
			INNER JOIN ONLY "Planets" p ON m."PlanetId" = p."Id"
			WHERE msm."AreaId" = ANY($1::int[])
		`;
			const { rows: smRows } = await pool.query(maturitiesSql, [Ids]);
			// Group maturities by AreaId so we can attach them to each spawn (Area)
			const grouped = smRows.reduce((a, r) => { (a[r.AreaId] ||= []).push(r); return a; }, {});
			// Also collect MobIds per Area to enable grouping by Mob later
			const mobIdsByArea = smRows.reduce((a, r) => {
				(a[r.AreaId] ||= new Set()).add(r.MobId);
				return a;
			}, {});
	for (const id of Ids) {
		const spawn = spawnsById[id];
				spawn.Maturities = (grouped[id] || []).map(_formatMobSpawnMaturity);
				spawn._MobIds = Array.from(mobIdsByArea[id] || []);
	}

		const uniqueSpawns = Object.values(spawnsById);
		// Group by MobId(s) based on maturities attached to each spawn
		const byMob = {};
			for (const spawn of uniqueSpawns) {
				const mobIds = Array.isArray(spawn._MobIds) ? spawn._MobIds : [];
				if (mobIds.length === 0) continue; // should not happen due to EXISTS
				for (const mid of mobIds) {
					(byMob[mid] ||= []).push(spawn);
				}
				delete spawn._MobIds;
			}
		return byMob;
}

async function listMobSpawns(planet) {
	let sql = getBaseWrappedQuery();
	let params = [];
	if (planet) {
		// Filter on real column alias from base (Planet name is selected there). Alternatively use PlanetId if available.
		sql += ' WHERE "Planet" = $1';
		params = [planet];
	}
	const { rows } = await pool.query(sql, params);
	if (!rows.length) return [];

	// Group all rows by Id (MobSpawn is 1:1 with Area)
	const spawnsById = {};
	for (const row of rows) {
		if (!spawnsById[row.Id]) {
			spawnsById[row.Id] = { ...row, Maturities: [] };
		}
	}

	// Get all maturities for these spawns
		const Ids = Object.keys(spawnsById).map(x => parseInt(x,10)).filter(Number.isFinite);
		const maturitiesSql = `
			SELECT msm.*, mm.*, m."Name" AS "Mob", m."Id" AS "MobId"
			FROM ONLY "MobSpawnMaturities" msm
			INNER JOIN ONLY "MobMaturities" mm ON msm."MaturityId" = mm."Id"
			INNER JOIN ONLY "Mobs" m ON mm."MobId" = m."Id"
			WHERE msm."AreaId" = ANY($1::int[])
		`;
		const { rows: smRows } = await pool.query(maturitiesSql, [Ids]);
	for (const mat of smRows) {
		const areaId = mat.AreaId;
		if (spawnsById[areaId]) {
			spawnsById[areaId].Maturities.push({ IsRare: mat.IsRare === 1 || mat.IsRare === true, Maturity: formatMobMaturity(mat) });
		}
	}

	// Return one object per MobSpawn (Area), with all maturities grouped
	return Object.values(spawnsById).map(formatSpawn);
}

async function getMobSpawn(idOrName) {
	// Use Id as the identifier
	const row = await getObjectByIdOrName(getBaseWrappedQuery(), 'base', idOrName);
	if (!row) return null;
	const { rows: smRows } = await pool.query(`
		SELECT msm.*, mm.*, m."Name" AS "Mob", m."Id" AS "MobId"
		FROM ONLY "MobSpawnMaturities" msm
		INNER JOIN ONLY "MobMaturities" mm ON msm."MaturityId" = mm."Id"
		INNER JOIN ONLY "Mobs" m ON mm."MobId" = m."Id"
		WHERE msm."AreaId" = $1
	`, [row.Id]);
	row.Maturities = smRows.map(x => ({ IsRare: x.IsRare === 1 || x.IsRare === true, Maturity: formatMobMaturity(x) }));
	return formatSpawn(row);
}

function register(app) {
	/**
	 * @swagger
	 * /mobspawns:
	 *  get:
	 *    description: Get all mob spawns
	 *    parameters:
	 *      - in: query
	 *        name: planet
	 *        schema:
	 *          type: string
	 *        required: false
	 *        description: Filter by planet name
	 *    responses:
	 *      '200':
	 *        description: A list of mob spawns
	 */
	app.get('/mobspawns', async (req, res) => {
		const planet = req.query.Planet;
		res.json(await listMobSpawns(planet));
	});

	/**
	 * @swagger
	 * /mobspawns/{mobSpawn}:
	 *  get:
	 *    description: Get a mob spawn by name or id
	 *    parameters:
	 *      - in: path
	 *        name: mobSpawn
	 *        schema:
	 *          type: string
	 *        required: true
	 *        description: The name or id of the mob spawn
	 *    responses:
	 *      '200':
	 *        description: The mob spawn
	 *      '404':
	 *        description: Mob spawn not found
	 */
	app.get('/mobspawns/:mobSpawn', async (req, res) => {
		const r = await getMobSpawn(req.params.mobSpawn);
		if (r) res.json(r);
		else res.status(404).send();
	});
}

module.exports = { register, getMobSpawns };

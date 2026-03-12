const { pool } = require('./dbClient');
const { formatMobMaturity } = require('./mobmaturities');

// Base query for mob spawns: one row per Location (MobArea), joined to MobSpawns and Planets
const baseQuery = `
	SELECT
		l."Id" AS "Id",
		l."Name" AS "Name",
		l."Description",
		"MobSpawns"."Density",
		"MobSpawns"."IsShared",
		"MobSpawns"."IsEvent",
		"MobSpawns"."Notes",
		a."Type" AS "Type",
		a."Type" AS "AreaType",
		a."Shape",
		a."Data",
		l."Longitude",
		l."Latitude",
		l."Altitude",
		l."PlanetId",
		p."Name" AS "Planet",
		p."TechnicalName"
	FROM ONLY "Locations" l
	INNER JOIN ONLY "Areas" a ON l."Id" = a."LocationId"
	INNER JOIN ONLY "MobSpawns" ON "MobSpawns"."LocationId" = l."Id"
	INNER JOIN ONLY "Planets" p ON l."PlanetId" = p."Id"
	WHERE l."Type" = 'Area' AND a."Type" = 'MobArea'
`;

function _getBaseWrappedQuery() {
  return `SELECT * FROM (${baseQuery}) AS base`;
}

function _formatSpawn(x) {
	return {
		Id: x.Id,
		Name: x.Name,
		Properties: {
			Description: x.Description,
			Density: x.Density,
			IsShared: x.IsShared === 1 || x.IsShared === true,
			IsEvent: x.IsEvent === 1 || x.IsEvent === true,
			Notes: x.Notes,
			Type: 'Area',
			AreaType: x.AreaType,
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
			"$Url": `/locations/${x.Id}`
		}
	};
}

function _formatMobSpawnMaturity(x) {
	return {
		IsRare: x.IsRare === 1 || x.IsRare === true,
		Maturity: formatMobMaturity(x, [])
	};
}

// Internal helper for attaching spawns per mob (used by mobs.js)
async function getMobSpawns(mobIds, planet) {
	if (!mobIds || mobIds.length === 0) return {};
	let sql = _getBaseWrappedQuery() +
		' WHERE EXISTS (\
			SELECT 1 FROM ONLY "MobSpawnMaturities" msm\
			INNER JOIN ONLY "MobMaturities" mm ON msm."MaturityId" = mm."Id"\
			WHERE msm."LocationId" = base."Id" AND mm."MobId" = ANY($1::int[])\
		)';
	const params = [mobIds];
	if (planet) {
		sql += ' AND base."Planet" = $2';
		params.push(planet);
	}
	const { rows } = await pool.query(sql, params);
	if (!rows.length) return {};

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
			WHERE msm."LocationId" = ANY($1::int[])
		`;
			const { rows: smRows } = await pool.query(maturitiesSql, [Ids]);
			const grouped = smRows.reduce((a, r) => { (a[r.LocationId] ||= []).push(r); return a; }, {});
			const mobIdsByArea = smRows.reduce((a, r) => {
				(a[r.LocationId] ||= new Set()).add(r.MobId);
				return a;
			}, {});
	for (const id of Ids) {
		const spawn = spawnsById[id];
				spawn.Maturities = (grouped[id] || []).map(_formatMobSpawnMaturity);
				spawn._MobIds = Array.from(mobIdsByArea[id] || []);
	}

		const uniqueSpawns = Object.values(spawnsById);
		const byMob = {};
			for (const spawn of uniqueSpawns) {
				const mobIds = Array.isArray(spawn._MobIds) ? spawn._MobIds : [];
				if (mobIds.length === 0) continue;
				for (const mid of mobIds) {
					(byMob[mid] ||= []).push(_formatSpawn(spawn));
				}
				delete spawn._MobIds;
			}
		return byMob;
}

module.exports = { getMobSpawns };

const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { formatMobMaturity } = require('./mobmaturities');

// Lightweight helper used by mobs endpoint to attach spawns per mob
async function getMobSpawns(mobIds){
	if(!mobIds || mobIds.length===0) return {};
	const sql = `
		SELECT DISTINCT ms.*, mm."MobId", a."Name" AS "AreaName", a."Type" AS "AreaType", a."Shape", a."Data",
			a."Longitude", a."Latitude", a."Altitude", a."PlanetId", p."Name" AS "Planet", p."TechnicalName"
		FROM ONLY "MobSpawns" ms
		INNER JOIN ONLY "Areas" a ON ms."AreaId" = a."Id"
		INNER JOIN ONLY "Planets" p ON a."PlanetId" = p."Id"
		INNER JOIN ONLY "MobSpawnMaturities" msm ON ms."Id" = msm."SpawnId"
		INNER JOIN ONLY "MobMaturities" mm ON msm."MaturityId" = mm."Id"
		WHERE mm."MobId" IN (${mobIds.join(',')})`;
	const { rows } = await pool.query(sql);
	// Attach spawn maturities expanded akin to legacy
	const { rows: smRows } = await pool.query(`
		SELECT msm.*, mm.*, m."Name" AS "Mob", m."Id" AS "MobId"
		FROM ONLY "MobSpawnMaturities" msm
		INNER JOIN ONLY "MobMaturities" mm ON msm."MaturityId" = mm."Id"
		INNER JOIN ONLY "Mobs" m ON mm."MobId" = m."Id"
		WHERE msm."SpawnId" IN (${rows.map(r=>r.Id).join(',') || 'NULL'})`);
	const grouped = smRows.reduce((a,r)=>{ (a[r.SpawnId] ||= []).push(r); return a; }, {});
	rows.forEach(r => { r.Maturities = (grouped[r.Id]||[]).map(x => ({ IsRare: x.IsRare === 1 || x.IsRare === true, Maturity: formatMobMaturity(x) })); });
	return rows.reduce((a,r)=>{ (a[r.MobId] ||= []).push(r); return a; },{});
}

// Base query for direct mobspawns endpoints (matches legacy shape approximately)
const baseQuery = `SELECT ms.*, a."Name" AS "AreaName", a."Type" AS "AreaType", a."Shape", a."Data", a."Longitude", a."Latitude", a."Altitude",
	p."Id" AS "PlanetId", p."Name" AS "Planet", p."TechnicalName"
	FROM ONLY "MobSpawns" ms
	INNER JOIN ONLY "Areas" a ON ms."AreaId" = a."Id"
	INNER JOIN ONLY "Planets" p ON a."PlanetId" = p."Id"`;

function formatSpawn(x){
	return {
		Id: x.Id,
		Name: x.Name,
		Properties: {
			Description: x.Description,
			Density: x.Density,
			IsShared: x.IsShared === 1,
			IsEvent: x.IsEvent === 1,
			Notes: x.Notes,
			Type: x.AreaType,
			Shape: x.Shape,
			Data: x.Data,
			Coordinates: {
				Longitude: x.Longitude,
				Latitude: x.Latitude,
				Altitude: x.Altitude
			}
		},
		Planet: x.Planet ? {
			Name: x.Planet,
			Properties: {
				TechnicalName: x.TechnicalName
			},
			Links: {
				"$Url": `/planets/${x.PlanetId}`
			}
		} : null,
		Maturities: Array.isArray(x.Maturities) ? x.Maturities : [],
		Links: {
			"$Url": `/mobspawns/${x.Id}`
		}
	};
}

async function listMobSpawns(){
	const { rows } = await pool.query(baseQuery);
	if (rows.length){
		const { rows: smRows } = await pool.query(`
			SELECT msm.*, mm.*, m."Name" AS "Mob", m."Id" AS "MobId"
			FROM ONLY "MobSpawnMaturities" msm
			INNER JOIN ONLY "MobMaturities" mm ON msm."MaturityId" = mm."Id"
			INNER JOIN ONLY "Mobs" m ON mm."MobId" = m."Id"
			WHERE msm."SpawnId" IN (${rows.map(r=>r.Id).join(',')})`);
		const grouped = smRows.reduce((a,r)=>{ (a[r.SpawnId] ||= []).push(r); return a; }, {});
		rows.forEach(r => { r.Maturities = (grouped[r.Id]||[]).map(x => ({ IsRare: x.IsRare === 1 || x.IsRare === true, Maturity: formatMobMaturity(x) })); });
	}
	return rows.map(formatSpawn);
}
async function getMobSpawn(idOrName){
	const row = await getObjectByIdOrName(baseQuery,'MobSpawns',idOrName);
	if (!row) return null;
	const { rows: smRows } = await pool.query(`
		SELECT msm.*, mm.*, m."Name" AS "Mob", m."Id" AS "MobId"
		FROM ONLY "MobSpawnMaturities" msm
		INNER JOIN ONLY "MobMaturities" mm ON msm."MaturityId" = mm."Id"
		INNER JOIN ONLY "Mobs" m ON mm."MobId" = m."Id"
		WHERE msm."SpawnId" = $1`, [row.Id]);
	row.Maturities = smRows.map(x => ({ IsRare: x.IsRare === 1 || x.IsRare === true, Maturity: formatMobMaturity(x) }));
	return formatSpawn(row);
}

function register(app){
	/**
	 * @swagger
	 * /mobspawns:
	 *  get:
	 *    description: Get all mob spawns
	 *    responses:
	 *      '200':
	 *        description: A list of mob spawns
	 */
	app.get('/mobspawns', async (req,res) => { res.json(await listMobSpawns()); });
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
	app.get('/mobspawns/:mobSpawn', async (req,res) => { const r = await getMobSpawn(req.params.mobSpawn); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getMobSpawns };

const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');

// Lightweight helper used by mobs endpoint to attach spawns per mob
async function getMobSpawns(mobIds){
	if(mobIds.length===0) return {};
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
			IsShared: x.IsShared === 1 || x.IsShared === true,
			IsEvent: x.IsEvent === 1 || x.IsEvent === true,
			Notes: x.Notes,
	Type: x.AreaType,
			Shape: x.Shape,
			Data: x.Data,
			Coordinates: { Longitude: x.Longitude, Latitude: x.Latitude, Altitude: x.Altitude }
		},
		Planet: x.Planet ? { Name: x.Planet, Properties: { TechnicalName: x.TechnicalName }, Links: { "$Url": `/planets/${x.PlanetId}` } } : null,
		Links: { "$Url": `/mobspawns/${x.Id}` }
	};
}

async function listMobSpawns(){ const { rows } = await pool.query(baseQuery); return rows.map(formatSpawn); }
async function getMobSpawn(idOrName){ const row = await getObjectByIdOrName(baseQuery,'MobSpawns',idOrName); return row ? formatSpawn(row) : null; }

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

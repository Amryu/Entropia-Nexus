const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');

async function getMobSpecies(ids){
	if(!ids || ids.length===0) return {};
	const { rows } = await pool.query(`SELECT ms.* FROM ONLY "MobSpecies" ms WHERE ms."MobId" = ANY($1::int[])`, [ids]);
	return rows.reduce((a,r)=>{ (a[r.MobId] ||= []).push(r); return a; },{});
}

const baseQuery = 'SELECT * FROM ONLY "MobSpecies"';

function formatMobSpecies(x){
	return {
		Id: x.Id,
		Name: x.Name,
		Properties: {
			CodexBaseCost: x.CodexBaseCost != null ? Number(x.CodexBaseCost) : null,
			CodexType: x.CodexType ?? null
		},
		Links: { "$Url": `/mobspecies/${x.Id}` }
	};
}

async function getAllMobSpecies() {
	const { rows } = await pool.query(baseQuery);
	return rows.map(formatMobSpecies);
}

function register(app){
	/**
	 * @swagger
	 * /mobspecies:
	 *  get:
	 *    description: Get all mob species
	 *    responses:
	 *      '200':
	 *        description: A list of mob species
	 */
	app.get('/mobspecies', async (req,res)=>{
		res.json(await withCache('/mobspecies', ['MobSpecies'], getAllMobSpecies));
	});

	/**
	 * @swagger
	 * /mobspecies/{species}:
	 *  get:
	 *    description: Get a mob species by name or id
	 *    parameters:
	 *      - in: path
	 *        name: species
	 *        schema:
	 *          type: string
	 *        required: true
	 *    responses:
	 *      '200':
	 *        description: The mob species
	 *      '404':
	 *        description: Not found
	 */
	app.get('/mobspecies/:species', async (req,res)=>{
		const r = await withCachedLookup('/mobspecies', ['MobSpecies'], getAllMobSpecies, req.params.species);
		if (r) res.json(r); else res.status(404).send();
	});
}

module.exports = { register, getMobSpecies };

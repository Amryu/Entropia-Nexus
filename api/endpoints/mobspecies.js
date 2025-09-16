const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');

async function getMobSpecies(ids){
	if(!ids || ids.length===0) return {};
	const { rows } = await pool.query(`SELECT ms.* FROM ONLY "MobSpecies" ms WHERE ms."MobId" IN (${ids.join(',')})`);
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
		const { rows } = await pool.query(baseQuery);
		res.json(rows.map(formatMobSpecies));
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
		const row = await getObjectByIdOrName(baseQuery, 'MobSpecies', req.params.species);
		if (!row) return res.status(404).send();
		res.json(formatMobSpecies(row));
	});
}

module.exports = { register, getMobSpecies };

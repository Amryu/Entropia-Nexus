const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');

// Internal: fetch attacks per maturity id and group
async function getMobAttacks(maturityIds){
	if(!maturityIds || maturityIds.length===0) return {};
	const { rows } = await pool.query(`SELECT * FROM ONLY "MobAttacks" WHERE "MaturityId" IN (${maturityIds.join(',')})`);
	return rows.reduce((a,r)=>{ (a[r.MaturityId] ||= []).push(r); return a; }, {});
}

// Shared: fetch maturities for given Mob IDs, attach attacks, group by MobId
async function getMobMaturities(mobIds){
	if(!mobIds || mobIds.length===0) return {};
	const { rows } = await pool.query(
		`SELECT mm.*, m."Name" AS "Mob", m."Id" AS "MobId" 
		 FROM ONLY "MobMaturities" mm 
		 INNER JOIN ONLY "Mobs" m ON mm."MobId" = m."Id"
		 WHERE mm."MobId" IN (${mobIds.join(',')})`
	);
	const attacks = await getMobAttacks(rows.map(r=>r.Id));
	rows.forEach(r => { r.Attacks = attacks[r.Id] || []; });
	return rows.reduce((a,r)=>{ (a[r.MobId] ||= []).push(r); return a; }, {});
}

// Base query for standalone listing/detail
const baseQuery = 'SELECT "MobMaturities".*, "Mobs"."Name" AS "Mob", "Mobs"."Id" AS "MobId" FROM ONLY "MobMaturities" INNER JOIN ONLY "Mobs" ON "MobMaturities"."MobId" = "Mobs"."Id"';

function formatMobAttack(x){
	return {
		Name: x.Name,
		Damage: {
			Stab: x.Stab != null ? Number(x.Stab) : null,
			Cut: x.Cut != null ? Number(x.Cut) : null,
			Impact: x.Impact != null ? Number(x.Impact) : null,
			Penetration: x.Penetration != null ? Number(x.Penetration) : null,
			Shrapnel: x.Shrapnel != null ? Number(x.Shrapnel) : null,
			Burn: x.Burn != null ? Number(x.Burn) : null,
			Cold: x.Cold != null ? Number(x.Cold) : null,
			Acid: x.Acid != null ? Number(x.Acid) : null,
			Electric: x.Electric != null ? Number(x.Electric) : null,
		},
		TotalDamage: x.Damage != null ? Number(x.Damage) : null,
		IsAoE: x.IsAoE === 1 || x.IsAoE === true,
	};
}

function formatMobMaturity(x){
	const attacks = (x.Attacks || []).map(formatMobAttack);
	return {
		Id: x.Id,
		Name: x.Name,
		NameMode: x.NameMode || null,
		Properties: {
			Description: x.Description,
			Health: x.Health != null ? Number(x.Health) : null,
			AttacksPerMinute: x.AttackSpeed != null ? Number(x.AttackSpeed) : null,
			Level: x.DangerLevel != null ? Number(x.DangerLevel) : null,
			RegenerationInterval: x.RegenerationInterval != null ? Number(x.RegenerationInterval) : null,
			RegenerationAmount: x.RegenerationAmount != null ? Number(x.RegenerationAmount) : null,
			MissChance: x.MissChance != null ? Number(x.MissChance) : null,
			Boss: x.Boss === true,
			Taming: {
				IsTameable: x.TamingLevel != null,
				TamingLevel: x.TamingLevel != null ? Number(x.TamingLevel) : null,
			},
			Attributes: {
				Strength: x.Strength != null ? Number(x.Strength) : null,
				Agility: x.Agility != null ? Number(x.Agility) : null,
				Intelligence: x.Intelligence != null ? Number(x.Intelligence) : null,
				Psyche: x.Psyche != null ? Number(x.Psyche) : null,
				Stamina: x.Stamina != null ? Number(x.Stamina) : null,
			},
			Defense: {
				Stab: x.ResistanceStab != null ? Number(x.ResistanceStab) : null,
				Cut: x.ResistanceCut != null ? Number(x.ResistanceCut) : null,
				Impact: x.ResistanceImpact != null ? Number(x.ResistanceImpact) : null,
				Penetration: x.ResistancePenetration != null ? Number(x.ResistancePenetration) : null,
				Shrapnel: x.ResistanceShrapnel != null ? Number(x.ResistanceShrapnel) : null,
				Burn: x.ResistanceBurn != null ? Number(x.ResistanceBurn) : null,
				Cold: x.ResistanceCold != null ? Number(x.ResistanceCold) : null,
				Acid: x.ResistanceAcid != null ? Number(x.ResistanceAcid) : null,
				Electric: x.ResistanceElectric != null ? Number(x.ResistanceElectric) : null,
			}
		},
		Attacks: attacks,
		Mob: { Name: x.Mob, Links: { "$Url": `/mobs/${x.MobId}` } },
		Links: { "$Url": `/mobmaturities/${x.Id}` }
	};
}

async function listMobMaturities(){
	const { rows } = await pool.query(baseQuery);
	const attacks = await getMobAttacks(rows.map(r=>r.Id));
	rows.forEach(r => r.Attacks = attacks[r.Id] || []);
	return rows.map(formatMobMaturity);
}

async function getMobMaturity(idOrName){
	const row = await getObjectByIdOrName(baseQuery, 'MobMaturities', idOrName);
	if(!row) return null;
	const attacks = await getMobAttacks([row.Id]);
	row.Attacks = attacks[row.Id] || [];
	return formatMobMaturity(row);
}

function register(app){
	/**
	 * @swagger
	 * /mobmaturities:
	 *  get:
	 *    description: Get all mob maturities
	 *    responses:
	 *      '200':
	 *        description: A list of mob maturities
	 */
	app.get('/mobmaturities', async (req,res)=>{
		res.json(await listMobMaturities());
	});

	/**
	 * @swagger
	 * /mobmaturities/{maturity}:
	 *  get:
	 *    description: Get a mob maturity by name or id
	 *    parameters:
	 *      - in: path
	 *        name: maturity
	 *        schema:
	 *          type: string
	 *        required: true
	 *    responses:
	 *      '200':
	 *        description: The mob maturity
	 *      '404':
	 *        description: Not found
	 */
	app.get('/mobmaturities/:maturity', async (req,res)=>{
		const r = await getMobMaturity(req.params.maturity);
		if (!r) return res.status(404).send();
		res.json(r);
	});
}

module.exports = { register, getMobMaturities, formatMobMaturity };

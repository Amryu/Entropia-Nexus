const { pool } = require('./dbClient');
const pgp = require('pg-promise')();

// Helper used by mobs endpoint to prefetch loots for given mob IDs (full join like legacy)
async function getMobLoots(mobIds){
	if(!mobIds || mobIds.length===0) return {};
	const { rows } = await pool.query(buildBaseQuery() + ` WHERE "MobLoots"."MobId" = ANY($1::int[])`, [mobIds]);
	return rows.reduce((a,r)=>{ (a[r.MobId] ||= []).push(r); return a; },{});
}

// Simple formatter for the nested Loots array on /mobs
function formatLoot(x){
	return {
		Item: { Name: x.ItemName, Links: { "$Url": `/items/${x.ItemId}` } },
		DropRate: x.DropRate != null ? Number(x.DropRate) : null,
		MinStackSize: x.MinStackSize != null ? Number(x.MinStackSize) : null,
		MaxStackSize: x.MaxStackSize != null ? Number(x.MaxStackSize) : null
	};
}

// Full-format for standalone /mobloots (parity with legacy db.js format)
function formatMobLoot(x){
	return {
		Mob: {
			Name: x.Mob,
			Planet: {
				Name: x.Planet,
				Links: { "$Url": `/planets/${x.PlanetId}` }
			},
			Links: { "$Url": `/mobs/${x.MobId}` }
		},
		Maturity: {
			Name: x.Maturity,
			Links: { "$Url": `/mobmaturities/${x.MaturityId}` }
		},
		Item: {
			Name: x.Item,
			Properties: { Type: x.ItemType },
			Links: { "$Url": `/${(x.ItemType||'item').toLowerCase()}s/${x.ItemId % 100000}` }
		},
		Frequency: x.Frequency,
		LastVU: x.LastVU,
		IsEvent: x.IsEvent === 1,
		IsDropping: x.IsDropping === 1
	};
}

function buildBaseQuery(){
	return `SELECT "MobLoots".*, "Mobs"."Name" AS "Mob", "Mobs"."PlanetId", "MobMaturities"."Name" AS "Maturity", "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Planets"."Name" AS "Planet"
					FROM ONLY "MobLoots"
					INNER JOIN ONLY "Mobs" ON "MobLoots"."MobId" = "Mobs"."Id"
					INNER JOIN ONLY "Items" ON "MobLoots"."ItemId" = "Items"."Id"
					LEFT JOIN ONLY "MobMaturities" ON "MobLoots"."MaturityId" = "MobMaturities"."Id"
					LEFT JOIN ONLY "Planets" ON "Mobs"."PlanetId" = "Planets"."Id"`;
}

// Reusable query for acquisition/usage: filter by item names and/or mob names
async function getMobLootsForItemsOrMobs(items = null, mobs = null){
	let where = '';
	const params = [];
	if (items && items.length){
		where += params.length ? ' AND' : ' WHERE';
		where += ' "Items"."Name" IN (' + items.map((_,i)=>`$${i+1}`).join(',') + ')';
		params.push(...items.map(x=>`${x}`));
	}
	if (mobs && mobs.length){
		where += params.length ? ' AND' : ' WHERE';
		where += ' "Mobs"."Name" IN (' + mobs.map((_,i)=>`$${params.length+i+1}`).join(',') + ')';
		params.push(...mobs.map(x=>`${x}`));
	}
	const { rows } = await pool.query(buildBaseQuery() + where, params);
	return rows.map(formatMobLoot);
}

function register(app){
	/**
	 * @swagger
	 * /mobloots:
	 *  get:
	 *    description: Get mob loot table entries, optionally filtered by Item or Mob name
	 *    parameters:
	 *      - in: query
	 *        name: Item
	 *        schema:
	 *          type: string
	 *      - in: query
	 *        name: Mob
	 *        schema:
	 *          type: string
	 *    responses:
	 *      '200':
	 *        description: A list of mob loot entries
	 */
	app.get('/mobloots', async (req,res)=>{
		const { Item, Mob } = req.query;
		let where = '';
		let params = [];
		if (Item) { where = ' WHERE "Items"."Name" = $1'; params = [Item]; }
		else if (Mob) { where = ' WHERE "Mobs"."Name" = $1'; params = [Mob]; }
		const { rows } = await pool.query(buildBaseQuery() + where, params);
		res.json(rows.map(formatMobLoot));
	});
}

	module.exports = { register, getMobLoots, formatLoot, getMobLootsForItemsOrMobs };
	// also export the full formatter for nested usage in /mobs
	module.exports.formatMobLoot = formatMobLoot;

const { pool } = require('./dbClient');

async function getMobLoots(mobIds){ if(mobIds.length===0) return {}; const { rows } = await pool.query(`SELECT ml.*, i."Name" AS "ItemName" FROM ONLY "MobLoots" ml INNER JOIN ONLY "Items" i ON ml."ItemId" = i."Id" WHERE ml."MobId" IN (${mobIds.join(',')})`); return rows.reduce((a,r)=>{ (a[r.MobId] ||= []).push(r); return a; },{}); }
function formatLoot(x){ return { Item: { Name: x.ItemName, Links: { "$Url": `/items/${x.ItemId}` } }, DropRate: x.DropRate != null ? Number(x.DropRate) : null, MinStackSize: x.MinStackSize != null ? Number(x.MinStackSize) : null, MaxStackSize: x.MaxStackSize != null ? Number(x.MaxStackSize) : null }; }
function register(){ /* no direct routes; used by mobs module */ }
module.exports = { register, getMobLoots, formatLoot };

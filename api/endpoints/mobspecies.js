const { pool } = require('./dbClient');

async function getMobSpecies(ids){ if(ids.length===0) return {}; const { rows } = await pool.query(`SELECT ms.* FROM ONLY "MobSpecies" ms WHERE ms."MobId" IN (${ids.join(',')})`); return rows.reduce((a,r)=>{ (a[r.MobId] ||= []).push(r); return a; },{}); }
function register(){ }
module.exports = { register, getMobSpecies };

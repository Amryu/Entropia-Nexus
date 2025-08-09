const { pool } = require('./dbClient');

async function getMobMaturities(mobIds){ if(mobIds.length===0) return {}; const { rows } = await pool.query(`SELECT mm.* FROM ONLY "MobMaturities" mm WHERE mm."MobId" IN (${mobIds.join(',')})`); return rows.reduce((a,r)=>{ (a[r.MobId] ||= []).push(r); return a; },{}); }
function register(){ }
module.exports = { register, getMobMaturities };

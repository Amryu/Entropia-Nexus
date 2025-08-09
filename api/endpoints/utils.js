const { pool } = require('./dbClient');

function isId(value){ return /^(\d+)$/.test(String(value)); }

async function getObjects(query, formatFn){
  const { rows } = await pool.query(query);
  return rows.map(formatFn);
}

function resolveQualifier(query, table){
  if (!table) return '';
  // Detect a lowercase alias token immediately following the table in FROM
  // e.g., FROM ONLY "Table" t ... or FROM "Table" m ...
  const re = new RegExp(`FROM\\s+(?:ONLY\\s+)?"${table}"\\s+([a-z][a-z0-9_]*)\\b`);
  const m = query.match(re);
  if (m && m[1]) {
    return `${m[1]}.`;
  }
  return `"${table}".`;
}

async function getObjectByIdOrName(query, table, idOrName){
  const qualifier = resolveQualifier(query, table);
  const sql = isId(idOrName)
    ? `${query} WHERE ${table ? qualifier: ''}"Id" = $1`
    : `${query} WHERE ${table ? qualifier: ''}"Name" = $1`;
  const { rows } = await pool.query(sql, [idOrName]);
  return rows.length === 1 ? rows[0] : null;
}

// Parse a CSV-like list supporting quoted items (matches previous app.js behavior)
function parseItemList(list){
  if (!list || typeof list !== 'string') return [];
  const matches = list.match(/(".*?"|[^",]+)(?=\s*,|\s*$)/g) || [];
  return matches.map(item => item.trim().replace(/^"(.*)"$/, '$1').replace(/""/g, '"')).filter(Boolean);
}

module.exports = { isId, getObjects, getObjectByIdOrName, parseItemList };

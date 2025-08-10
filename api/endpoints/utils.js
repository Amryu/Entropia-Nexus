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

// Parse a CSV-like list supporting quoted items and ignoring commas inside parentheses
// Examples:
//  - 'Item A, Item B' => ['Item A','Item B']
//  - 'Vehicle X (C, L)' => ['Vehicle X (C, L)']
//  - '"Weird, Name" (M), Other' => ['Weird, Name (M)','Other']
function parseItemList(list){
  if (!list || typeof list !== 'string') return [];
  const result = [];
  let buf = '';
  let inQuotes = false;
  let parenDepth = 0;
  for (let i = 0; i < list.length; i++) {
    const ch = list[i];
    if (ch === '"') {
      // Toggle quotes; support doubling inside quotes by looking ahead
      if (inQuotes && list[i + 1] === '"') {
        buf += '"';
        i++; // skip the escaped quote
        continue;
      }
      inQuotes = !inQuotes;
      buf += ch;
      continue;
    }
    if (!inQuotes) {
      if (ch === '(') { parenDepth++; }
      else if (ch === ')' && parenDepth > 0) { parenDepth--; }
      else if (ch === ',' && parenDepth === 0) {
        const token = buf.trim();
        if (token.length) result.push(token);
        buf = '';
        continue;
      }
    }
    buf += ch;
  }
  const last = buf.trim();
  if (last.length) result.push(last);

  // Strip surrounding quotes and un-escape doubled quotes
  return result
    .map(item => item.replace(/^\"([\s\S]*)\"$/, '$1').replace(/\"\"/g, '"').trim())
    .filter(Boolean);
}

module.exports = { isId, getObjects, getObjectByIdOrName, parseItemList };

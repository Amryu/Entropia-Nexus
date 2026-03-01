const { pool } = require('./dbClient');
const { TABLE_TO_ENTITY_TYPE } = require('./constants');

function isId(value){ return /^(\d+)$/.test(String(value)); }
function isClassId(value){ return /^[Cc]\d+$/.test(String(value)); }

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

  if (isClassId(idOrName)) {
    const classIdValue = String(idOrName).substring(1);
    const entityType = TABLE_TO_ENTITY_TYPE[table] || table;
    const sql = `${query} WHERE ${table ? qualifier : ''}"Id" = (SELECT "EntityId" FROM ONLY "ClassIds" WHERE "ClassId" = $1 AND "EntityType" = $2)`;
    const { rows } = await pool.query(sql, [classIdValue, entityType]);
    return rows.length === 1 ? rows[0] : null;
  }

  const sql = isId(idOrName)
    ? `${query} WHERE ${table ? qualifier: ''}"Id" = $1`
    : `${query} WHERE ${table ? qualifier: ''}"Name" = $1`;
  const { rows } = await pool.query(sql, [idOrName]);
  return rows.length === 1 ? rows[0] : null;
}

async function loadClassIds(entityType, entityIds) {
  if (!entityIds.length) return {};
  const { rows } = await pool.query(
    'SELECT "EntityId", "ClassId" FROM ONLY "ClassIds" WHERE "EntityType" = $1 AND "EntityId" = ANY($2)',
    [entityType, entityIds]
  );
  const map = {};
  for (const r of rows) map[r.EntityId] = String(r.ClassId);
  return map;
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

/**
 * Generate gender-specific aliases for armor/clothing items.
 * If an item doesn't have a gender tag (M) or (F) in its name and is marked as "Both" or null gender,
 * generate aliases with both (M) and (F) variants.
 * @param {string} name - The item name
 * @param {string|null} gender - The gender property: "Male", "Female", "Both", or null
 * @returns {string[]} Array of alias names (empty if no aliases needed)
 */
function generateGenderAliases(name, gender) {
  if (!name) return [];

  // Check if name already has a gender tag
  const hasGenderTag = /\((M|F)\)/.test(name) || /\(M,/.test(name) || /,\s*M\)/.test(name) || /\(F,/.test(name) || /,\s*F\)/.test(name);
  if (hasGenderTag) return [];

  // Only generate aliases for items with both genders or unspecified
  if (gender !== 'Both' && gender !== null) return [];

  // Check if name ends with a tag like (L), (C), etc.
  const tagMatch = name.match(/^(.+?)(\s*\([^)]+\))$/);
  if (tagMatch) {
    // Insert M/F before existing tag: "Bear (L)" -> "Bear (M) (L)", "Bear (F) (L)"
    // Actually, the convention is typically: "Bear (M, L)" or just "Bear (M)"
    // Let's use the simpler form: add (M) and (F) before existing tags
    const baseName = tagMatch[1].trim();
    const existingTag = tagMatch[2].trim();
    // Extract content inside parentheses
    const tagContent = existingTag.slice(1, -1); // Remove ( and )
    return [
      `${baseName} (M, ${tagContent})`,
      `${baseName} (F, ${tagContent})`
    ];
  } else {
    // No existing tag, just add (M) and (F)
    return [`${name} (M)`, `${name} (F)`];
  }
}

module.exports = { isId, isClassId, getObjects, getObjectByIdOrName, loadClassIds, parseItemList, generateGenderAliases };

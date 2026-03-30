/**
 * Skill import/export format utilities.
 * Handles conversion between external (kebab-case) and Nexus (proper-case) formats.
 */

/**
 * Build a mapping from kebab-case names to proper DB skill names.
 * @param {Array<{Name: string}>} skills - skills from the API
 * @returns {Map<string, string>} kebabName → properName
 */
function buildKebabToNameMap(skills) {
  const map = new Map();
  for (const skill of skills) {
    const kebab = skill.Name.toLowerCase().replace(/\s+/g, '-');
    map.set(kebab, skill.Name);
  }
  return map;
}

/**
 * Build a mapping from proper skill names to kebab-case.
 * @param {Array<{Name: string}>} skills - skills from the API
 * @returns {Map<string, string>} properName → kebabName
 */
export function buildNameToKebabMap(skills) {
  const map = new Map();
  for (const skill of skills) {
    const kebab = skill.Name.toLowerCase().replace(/\s+/g, '-');
    map.set(skill.Name, kebab);
  }
  return map;
}

/**
 * Parse the external kebab-case format (e.g. from game export tools).
 * Keys like "electrokinesis", "animal-lore", "blp-weaponry-technology".
 * Handles the special "health" key separately.
 *
 * @param {Object} data - parsed JSON with kebab-case keys
 * @param {Map<string, string>} kebabToName - mapping from buildKebabToNameMap
 * @returns {{ skills: Object<string, number>, health: number|null, unrecognized: string[] }}
 */
function parseExternalFormat(data, kebabToName) {
  /** @type {{ [key: string]: number }} */
  const skills = {};
  let health = null;
  const unrecognized = [];

  for (const [key, value] of Object.entries(data)) {
    if (typeof value !== 'number') continue;

    if (key === 'health') {
      health = value;
      continue;
    }

    const properName = kebabToName.get(key);
    if (properName) {
      skills[properName] = value;
    } else {
      unrecognized.push(key);
    }
  }

  return { skills, health, unrecognized };
}

/**
 * Parse the Nexus format (proper-cased keys, optional metadata wrapper).
 * Accepts both bare { "Agility": 0.5, ... } and wrapped { skills: {...}, metadata: {...} }.
 *
 * @param {Object} data - parsed JSON
 * @param {Set<string>} validNames - set of valid skill names from DB
 * @returns {{ skills: Object<string, number>, health: number|null, unrecognized: string[] }}
 */
function parseNexusFormat(data, validNames) {
  const raw = data.skills || data;
  /** @type {{ [key: string]: number }} */
  const skills = {};
  let health = data.health ?? null;
  const unrecognized = [];

  for (const [key, value] of Object.entries(raw)) {
    if (typeof value !== 'number') continue;

    if (validNames.has(key)) {
      skills[key] = value;
    } else {
      unrecognized.push(key);
    }
  }

  return { skills, health, unrecognized };
}

/**
 * Auto-detect format and parse skill data from text input.
 *
 * @param {string} text - raw text input (JSON)
 * @param {Array<{Name: string}>} skillsMetadata - skills from the API
 * @returns {{ skills: Object<string, number>, health: number|null, unrecognized: string[], format: string } | { error: string }}
 */
export function detectAndParseImport(text, skillsMetadata) {
  let data;
  try {
    data = JSON.parse(text.trim());
  } catch {
    return { error: 'Invalid JSON. Please paste valid JSON skill data.' };
  }

  if (typeof data !== 'object' || data === null || Array.isArray(data)) {
    return { error: 'Expected a JSON object with skill data.' };
  }

  const kebabToName = buildKebabToNameMap(skillsMetadata);
  const validNames = new Set(skillsMetadata.map(s => s.Name));

  // Try both parsers and pick the one that recognizes more skills.
  // Single-word skills (e.g. "electrokinesis") have no hyphens, so we can't
  // rely solely on key format to distinguish external from Nexus.
  const externalResult = parseExternalFormat(data.skills || data, kebabToName);
  const nexusResult = parseNexusFormat(data, validNames);

  const externalCount = Object.keys(externalResult.skills).length;
  const nexusCount = Object.keys(nexusResult.skills).length;

  if (externalCount > nexusCount) {
    return { ...externalResult, format: 'external' };
  }
  if (nexusCount > 0) {
    return { ...nexusResult, format: 'nexus' };
  }
  // Neither recognized anything — try external as fallback (shows unrecognized keys)
  return { ...externalResult, format: 'external' };
}

/**
 * Export skills in Nexus format (proper-cased, with metadata).
 * @param {Object<string, number>} skills
 * @param {Object} [metadata] - optional metadata (health, updatedAt, etc.)
 * @returns {string} JSON string
 */
export function exportNexusFormat(skills, metadata = {}) {
  const data = {
    skills: { ...skills },
    ...metadata,
    exportedAt: new Date().toISOString(),
    source: 'Entropia Nexus'
  };
  return JSON.stringify(data, null, 2);
}

/**
 * Export skills in external kebab-case format.
 * @param {Object<string, number>} skills - proper-cased skill values
 * @param {Map<string, string>} nameToKebab - mapping from buildNameToKebabMap
 * @param {number|null} [health] - optional health value
 * @returns {string} JSON string
 */
export function exportExternalFormat(skills, nameToKebab, health = null) {
  const data = {};
  // Sort alphabetically by kebab key for consistent output
  const entries = [];
  for (const [name, value] of Object.entries(skills)) {
    const kebab = nameToKebab.get(name);
    if (kebab) entries.push([kebab, value]);
  }
  entries.sort((a, b) => /** @type {string} */ (a[0]).localeCompare(/** @type {string} */ (b[0])));
  for (const [k, v] of entries) data[k] = v;
  if (health != null) data.health = health;
  return JSON.stringify(data, null, 2);
}

/**
 * Compute diff between old and new skill values.
 * @param {Object<string, number>} oldSkills
 * @param {Object<string, number>} newSkills
 * @returns {{ changed: Array<{name: string, oldValue: number, newValue: number}>, added: number, unchanged: number }}
 */
export function computeSkillDiff(oldSkills, newSkills) {
  const changed = [];
  let added = 0;
  let unchanged = 0;

  for (const [name, newVal] of Object.entries(newSkills)) {
    const oldVal = oldSkills[name] ?? 0;
    if (oldVal !== newVal) {
      changed.push({ name, oldValue: oldVal, newValue: newVal });
      if (oldVal === 0 && newVal > 0) added++;
    } else {
      unchanged++;
    }
  }

  return { changed, added, unchanged };
}

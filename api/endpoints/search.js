const { pool, usersPool } = require('./dbClient');
const { idOffsets, ITEM_TABLES } = require('./constants');
const { withCache } = require('./responseCache');
const { getWeapons } = require('./weapons');
const { getMaterials } = require('./materials');
const { getBlueprints } = require('./blueprints');
const { getArmorSets } = require('./armorsets');
const { getVehicles } = require('./vehicles');
const { getClothings } = require('./clothings');
const { getPets } = require('./pets');
const { getMobs } = require('./mobs');
const { getSkills } = require('./skills');
const { getProfessions } = require('./professions');
const { getVendors } = require('./vendors');
const { getMedicalTools } = require('./medicaltools');
const { getConsumables } = require('./consumables');
const { getStrongboxes } = require('./strongboxes');
const { getMiscTools } = require('./misctools');
const { getMissions } = require('./missions');
const { getLocations } = require('./locations');
const { getMissionChains } = require('./missionchains');
const { getMedicalChips } = require('./medicalchips');
const { getRefiners } = require('./refiners');
const { getScanners } = require('./scanners');
const { getFinders } = require('./finders');
const { getExcavators } = require('./excavators');
const { getTeleportationChips } = require('./teleportationchips');
const { getEffectChips } = require('./effectchips');
const { getCapsules } = require('./capsules');
const { getFurnitures } = require('./furniture');
const { getDecorations } = require('./decorations');
const { getStorageContainers } = require('./storagecontainers');
const { getSigns } = require('./signs');
const { getWeaponAmplifiers } = require('./weaponamplifiers');
const { getWeaponVisionAttachments } = require('./weaponvisionattachments');
const { getAbsorbers } = require('./absorbers');
const { getArmorPlatings } = require('./armorplatings');
const { getFinderAmplifiers } = require('./finderamplifiers');
const { getEnhancers } = require('./enhancers');
const { getMindforceImplants } = require('./mindforce');
const { getBlueprintBooks } = require('./blueprintbooks');

/**
 * Score a search result against the query.
 * Higher scores = better matches.
 * @param {string} name - The name to score against (MatchedName or Name)
 * @param {string} query - The search query
 * @param {Object|null} genderedQuery - Parsed gendered query info, if applicable
 * @returns {number} Score (0 = no match, higher = better)
 */
function scoreSearchResult(name, query, genderedQuery) {
  if (!name) return 0;

  const nameLower = name.toLowerCase();
  // For gendered queries, score against the base name (without gender tag)
  // This ensures "Vain Thigh Guards (M)" matches "Vain Thigh Guards" properly
  const queryLower = genderedQuery
    ? (genderedQuery.tag ? `${genderedQuery.baseName} (${genderedQuery.tag})` : genderedQuery.baseName).toLowerCase()
    : query.toLowerCase();

  // Exact match (highest priority)
  if (nameLower === queryLower) return 1000;

  // Starts with query
  if (nameLower.startsWith(queryLower)) return 900 - nameLower.length;

  // Word starts with query (e.g., "Calypso Sword" matches "sword")
  const words = nameLower.split(/\s+/);
  for (let i = 0; i < words.length; i++) {
    if (words[i].startsWith(queryLower)) {
      return 800 - i * 5 - nameLower.length;
    }
  }

  // Contains exact substring
  const index = nameLower.indexOf(queryLower);
  if (index !== -1) {
    return 700 - Math.min(index, 50) - nameLower.length;
  }

  // Multi-word matching: score each query word against name words independently
  const queryWords = queryLower.split(/\s+/).filter(w => w.length > 0);
  if (queryWords.length > 1) {
    const mwScore = scoreMultiWord(nameLower, queryWords);
    if (mwScore > 0) return mwScore;
  }

  // For short queries (< 4 chars), only match substrings
  if (queryLower.length < 4) {
    return 0;
  }

  // Fuzzy match for longer queries
  let queryIdx = 0;
  let score = 0;
  let consecutiveBonus = 0;
  let matchPositions = [];

  for (let i = 0; i < nameLower.length && queryIdx < queryLower.length; i++) {
    if (nameLower[i] === queryLower[queryIdx]) {
      matchPositions.push(i);
      queryIdx++;
      consecutiveBonus += 10;
      score += consecutiveBonus;
      if (i === 0 || nameLower[i - 1] === ' ' || nameLower[i - 1] === '-' || nameLower[i - 1] === '_') {
        score += 30;
      }
    } else {
      consecutiveBonus = 0;
    }
  }

  if (queryIdx === queryLower.length) {
    const spread = matchPositions.length > 1
      ? matchPositions[matchPositions.length - 1] - matchPositions[0]
      : 0;

    if (spread > queryLower.length * 2) {
      return 0;
    }

    const compactBonus = Math.max(0, 50 - spread);
    return 300 + score + compactBonus;
  }

  const matchRatio = queryIdx / queryLower.length;
  if (matchRatio >= 0.95 && queryLower.length >= 5) {
    const spread = matchPositions.length > 1
      ? matchPositions[matchPositions.length - 1] - matchPositions[0]
      : 0;
    if (spread <= queryLower.length * 2) {
      return 100 + Math.floor(score * matchRatio);
    }
  }

  return 0;
}

/**
 * Score how well a single query word matches a single name word.
 */
function scoreWordPair(nameWord, queryWord) {
  if (nameWord === queryWord) return 100;
  if (nameWord.startsWith(queryWord)) return 85 - Math.min(nameWord.length - queryWord.length, 15);
  if (nameWord.includes(queryWord)) return 60;
  // Fuzzy: query chars appear in order within name word
  if (queryWord.length >= 3) {
    let qi = 0;
    for (let ni = 0; ni < nameWord.length && qi < queryWord.length; ni++) {
      if (nameWord[ni] === queryWord[qi]) qi++;
    }
    if (qi === queryWord.length) return 30;
  }
  return 0;
}

/**
 * Score multi-word query: each query word is matched against name words independently.
 * Higher scores when more words match and match quality is better.
 */
function scoreMultiWord(nameLower, queryWords) {
  const nameWords = nameLower.split(/[\s,]+/).filter(w => w.length > 0);
  let totalScore = 0;
  let matchedCount = 0;
  const usedNameWords = new Set();

  for (const qWord of queryWords) {
    let bestScore = 0;
    let bestIdx = -1;
    for (let i = 0; i < nameWords.length; i++) {
      if (usedNameWords.has(i)) continue;
      const s = scoreWordPair(nameWords[i], qWord);
      if (s > bestScore) { bestScore = s; bestIdx = i; }
    }
    if (bestScore > 0 && bestIdx >= 0) {
      usedNameWords.add(bestIdx);
      totalScore += bestScore;
      matchedCount++;
    }
  }

  if (matchedCount === 0) return 0;
  const matchRatio = matchedCount / queryWords.length;
  if (matchRatio < 0.5) return 0;

  const avgScore = totalScore / queryWords.length;
  const baseScore = 550 + avgScore * 1.5;
  const ratioBonus = matchRatio >= 1 ? 50 : 0;
  const lengthPenalty = Math.min(nameLower.length * 0.5, 30);
  return Math.round(baseScore + ratioBonus - lengthPenalty);
}

/**
 * Build SQL multi-word ILIKE condition: (column ILIKE $idx1 AND column ILIKE $idx2 AND ...)
 */
function buildMultiWordLike(column, paramIndices) {
  if (!paramIndices.length) return '';
  return '(' + paramIndices.map(i => `${column} ILIKE $${i}`).join(' AND ') + ')';
}

function formatSearchResult(x, score){
  const result = { Id: x.Id, Name: x.Name, Type: x.Type, SubType: x.SubType, Score: score };
  if (x.DisplayName) result.DisplayName = x.DisplayName;
  return result;
}

// Helper to extract base name and gender from a gendered query like "Bear Armor (M)" or "Bear (M, L)"
// Also handles incomplete queries like "Bear (M" or "Bear (M, L" (user still typing)
function parseGenderedQuery(query) {
  // Match gender tags - both complete and incomplete:
  // - "Name (M)" or "Name (F)" - complete
  // - "Name (M, L)" or "Name (F, L)" - complete with tag
  // - "Name (M" or "Name (F" - incomplete (user still typing)
  // - "Name (M," or "Name (M, L" - incomplete with partial tag
  const match = query.match(/^(.+?)\s*\((M|F)(?:,\s*([^)]*))?\)?$/i);
  if (match) {
    const tag = match[3]?.trim();
    return { baseName: match[1].trim(), gender: match[2].toUpperCase(), tag: tag || undefined };
  }
  return null;
}

// Generate the aliased name for display based on original name and requested gender
function generateAliasedName(originalName, gender) {
  // Check if name already has a tag like (L), (C), etc.
  const tagMatch = originalName.match(/^(.+?)\s*\(([^)]+)\)$/);
  if (tagMatch) {
    const baseName = tagMatch[1].trim();
    const existingTag = tagMatch[2].trim();
    return `${baseName} (${gender}, ${existingTag})`;
  }
  return `${originalName} (${gender})`;
}

// Check if pg_trgm extension is available (cached)
let trgmAvailable = null;
async function checkTrgmAvailable() {
  if (trgmAvailable !== null) return trgmAvailable;
  try {
    await pool.query("SELECT 'test' % 'test'");
    trgmAvailable = true;
  } catch (e) {
    trgmAvailable = false;
  }
  return trgmAvailable;
}

// Check if optional tables exist (cached)
const tableExistsCache = {};
async function checkTableExists(tableName) {
  if (tableExistsCache[tableName] !== undefined) return tableExistsCache[tableName];
  try {
    const { rows } = await pool.query(
      `SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = $1)`,
      [tableName]
    );
    tableExistsCache[tableName] = rows[0].exists;
  } catch (e) {
    tableExistsCache[tableName] = false;
  }
  return tableExistsCache[tableName];
}

async function search(query, fuzzy = false, perType = 5, totalLimit = 50){
  query = query.trim(); // Trim whitespace to avoid matching issues
  const useFuzzy = fuzzy && await checkTrgmAvailable();

  // Check for optional tables
  const [missionsExist, missionChainsExist, locationsExist] = await Promise.all([
    checkTableExists('Missions'),
    checkTableExists('MissionChains'),
    checkTableExists('Locations')
  ]);

  // Check if query is searching for a gendered variant
  const genderedQuery = parseGenderedQuery(query);
  // If searching for gendered variant, also search by base name (with original tag if present)
  const searchName = genderedQuery
    ? (genderedQuery.tag ? `${genderedQuery.baseName} (${genderedQuery.tag})` : genderedQuery.baseName)
    : query;

  // Multi-word search: split query for individual word matching
  const searchWords = searchName.split(/\s+/).filter(w => w.length >= 2 || /^\d+$/.test(w));
  const isMultiWord = searchWords.length > 1;
  // Fuzzy params: $1=name, $2=%name%, $3=name%, $4+=mw  Non-fuzzy: $1=%name%, $2=name%, $3+=mw
  const mwStart = useFuzzy ? 4 : 3;
  const mwIdx = isMultiWord ? searchWords.map((_, i) => mwStart + i) : [];
  const mwParams = isMultiWord ? searchWords.map(w => `%${w}%`) : [];
  const mwName = isMultiWord ? ' OR ' + buildMultiWordLike('"Name"', mwIdx) : '';
  const mwArmorSet = isMultiWord ? ' OR ' + buildMultiWordLike('"ArmorSets"."Name"', mwIdx) : '';
  const mwArmor = isMultiWord ? ' OR ' + buildMultiWordLike('"Armors"."Name"', mwIdx) : '';

  // Use a lower similarity threshold (0.1) for better short query matching
  // Also prioritize prefix matches over general similarity
  // ArmorSets are pre-filtered (with piece name matching), so skip outer WHERE for them
  const whereClause = useFuzzy
    ? `WHERE "_prefiltered" OR similarity("Name", $1) >= 0.1 OR "Name" ILIKE $2${mwName}`
    : `WHERE "_prefiltered" OR "Name" ILIKE $1${mwName}`;

  // Order by: prefix match first, then by name length (shorter = more relevant), then alphabetically
  const orderClause = useFuzzy
    ? `ORDER BY (CASE WHEN "Name" ILIKE $3 THEN 0 ELSE 1 END), similarity("Name", $1) DESC, "Name" ASC`
    : `ORDER BY (CASE WHEN "Name" ILIKE $2 THEN 0 ELSE 1 END), length("Name") ASC, "Name" ASC`;

  // Build optional UNION parts for tables that may not exist
  let optionalUnions = '';
  if (missionsExist) {
    optionalUnions += `
        UNION ALL
        SELECT "Missions"."Id" + 6000000000 AS "Id", "Missions"."Name" AS "Name", 'Mission' AS "Type", "Planets"."Name" AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName"
        FROM ONLY "Missions"
        LEFT JOIN ONLY "Planets" ON "Missions"."PlanetId" = "Planets"."Id"`;
  }
  if (missionChainsExist) {
    optionalUnions += `
        UNION ALL
        SELECT "MissionChains"."Id" + 7000000000 AS "Id", "MissionChains"."Name" AS "Name", 'MissionChain' AS "Type", "Planets"."Name" AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName"
        FROM ONLY "MissionChains"
        LEFT JOIN ONLY "Planets" ON "MissionChains"."PlanetId" = "Planets"."Id"`;
  }
  if (locationsExist) {
    optionalUnions += `
        UNION ALL
        SELECT "Locations"."Id" + 8000000000 AS "Id", "Locations"."Name" AS "Name", 'Location' AS "Type", "Planets"."Name" AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName"
        FROM ONLY "Locations"
        INNER JOIN ONLY "Planets" ON "Locations"."PlanetId" = "Planets"."Id"
        WHERE "Locations"."Type" != 'Vendor'`;
  }

  // Build WHERE clause for armor piece name matching (used in EXISTS subquery)
  // This allows searching for individual armor piece names but returning the parent set
  const armorPieceWhereClause = useFuzzy
    ? `similarity("Armors"."Name", $1) >= 0.1 OR "Armors"."Name" ILIKE $2${mwArmor}`
    : `"Armors"."Name" ILIKE $1${mwArmor}`;

  // Subquery to get a matching armor piece name for the set (if found via piece matching)
  // Order by similarity to return the best matching piece name
  const armorMatchedPieceSubquery = useFuzzy
    ? `(SELECT "Armors"."Name" FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND (similarity("Armors"."Name", $1) >= 0.1 OR "Armors"."Name" ILIKE $2${mwArmor}) ORDER BY similarity("Armors"."Name", $1) DESC LIMIT 1)`
    : `(SELECT "Armors"."Name" FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND ("Armors"."Name" ILIKE $1${mwArmor}) LIMIT 1)`;

  const sql = `
    SELECT * FROM (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY "Type" ${orderClause}) as rn
      FROM (
        SELECT "Items"."Id" AS "Id", "Items"."Name" AS "Name", "Items"."Type" AS "Type",
          CASE WHEN "Items"."Type" = 'Weapon' THEN "Weapons"."Class" ELSE NULL END AS "SubType",
          CASE WHEN "Items"."Type" = 'Clothing' THEN "Clothes"."Gender" ELSE NULL END AS "Gender",
          FALSE AS "_prefiltered",
          NULL AS "MatchedName"
        FROM ONLY "Items"
        LEFT JOIN ONLY "Weapons" ON "Items"."Id" - ${idOffsets.Weapons} = "Weapons"."Id"
        LEFT JOIN ONLY "Clothes" ON "Items"."Type" = 'Clothing' AND "Items"."Id" - ${idOffsets.Clothings} = "Clothes"."Id"
        WHERE "Items"."Type" != 'Armor'
        UNION ALL
        SELECT "ArmorSets"."Id" + 1000000000 AS "Id", "ArmorSets"."Name" AS "Name", 'ArmorSet' AS "Type", NULL AS "SubType", NULL AS "Gender", TRUE AS "_prefiltered",
          ${armorMatchedPieceSubquery} AS "MatchedName"
        FROM ONLY "ArmorSets"
        WHERE ${useFuzzy ? `similarity("ArmorSets"."Name", $1) >= 0.1 OR "ArmorSets"."Name" ILIKE $2${mwArmorSet}` : `"ArmorSets"."Name" ILIKE $1${mwArmorSet}`}
           OR EXISTS (SELECT 1 FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND (${armorPieceWhereClause}))
        UNION ALL
        SELECT "Mobs"."Id" + 2000000000 AS "Id", "Mobs"."Name" AS "Name", 'Mob' AS "Type", "Planets"."Name" AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName" FROM ONLY "Mobs" INNER JOIN ONLY "Planets" ON "Mobs"."PlanetId" = "Planets"."Id"
        UNION ALL
        SELECT "Skills"."Id" + 3000000000 AS "Id", "Skills"."Name" AS "Name", 'Skill' AS "Type", NULL AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName" FROM ONLY "Skills"
        UNION ALL
        SELECT "Professions"."Id" + 4000000000 AS "Id", "Professions"."Name" AS "Name", 'Profession' AS "Type", NULL AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName" FROM ONLY "Professions"
        UNION ALL
        SELECT "Locations"."Id" + 5000000000 AS "Id", "Locations"."Name" AS "Name", 'Vendor' AS "Type", NULL AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName" FROM ONLY "Locations" WHERE "Locations"."Type" = 'Vendor'${optionalUnions}
      )
      ${whereClause}
    ) x
    WHERE rn <= ${parseInt(perType) || 5}
    ORDER BY rn, "Type"
    LIMIT ${parseInt(totalLimit) || 50}`;

  // Fuzzy: $1=name, $2=%name%, $3=name%  Non-fuzzy: $1=%name%, $2=name%
  const params = useFuzzy ? [searchName, `%${searchName}%`, `${searchName}%`, ...mwParams] : [`%${searchName}%`, `${searchName}%`, ...mwParams];

  // Query users and societies from nexus-users DB (separate database, parallel query)
  const userMwParams = isMultiWord ? searchWords.map(w => `%${w}%`) : [];
  const userMwIdx = isMultiWord ? searchWords.map((_, i) => 3 + i) : [];
  const userMwEuName = isMultiWord ? ' OR ' + buildMultiWordLike('eu_name', userMwIdx) : '';
  const userMwSocName = isMultiWord ? ' OR ' + buildMultiWordLike('name', userMwIdx) : '';
  const usersSql = `
    SELECT * FROM (
      (SELECT id + 9000000000 AS "Id", eu_name AS "Name", 'User' AS "Type",
        NULL AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName"
      FROM users
      WHERE verified = true AND eu_name IS NOT NULL
        AND (eu_name ILIKE $1${userMwEuName})
      ORDER BY (CASE WHEN eu_name ILIKE $2 THEN 0 ELSE 1 END), length(eu_name) ASC
      LIMIT 5)
      UNION ALL
      (SELECT id + 10000000000 AS "Id", name AS "Name", 'Society' AS "Type",
        abbreviation AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName"
      FROM societies
      WHERE name ILIKE $1 OR abbreviation ILIKE $1${userMwSocName}
      ORDER BY (CASE WHEN name ILIKE $2 OR abbreviation ILIKE $2 THEN 0 ELSE 1 END), length(name) ASC
      LIMIT 5)
    ) combined`;
  const usersParams = [`%${searchName}%`, `${searchName}%`, ...userMwParams];

  // Run both queries in parallel; if the users query fails, degrade gracefully
  let rows, userRows = [];
  try {
    [{ rows }, { rows: userRows }] = await Promise.all([
      pool.query(sql, params),
      usersPool.query(usersSql, usersParams)
    ]);
  } catch (err) {
    // If the users query fails, fall back to nexus-only results
    console.error('User/society search failed, falling back:', err.message);
    ({ rows } = await pool.query(sql, params));
  }
  const allRows = [...rows, ...userRows];

  // Post-process results: apply scoring, filter, and sort
  const scoredResults = allRows.map(row => {
    let displayName = null;
    // If searching for a gendered variant and this is a clothing item with 'Both' or null gender,
    // generate a display name with the gender tag (but keep Name as the original for URL linking)
    if (genderedQuery && row.Type === 'Clothing' && (row.Gender === 'Both' || row.Gender === null)) {
      // Check if the item name doesn't already have a gender tag
      if (!/\((M|F)\)/.test(row.Name) && !/\(M,/.test(row.Name) && !/,\s*M\)/.test(row.Name) && !/\(F,/.test(row.Name) && !/,\s*F\)/.test(row.Name)) {
        displayName = generateAliasedName(row.Name, genderedQuery.gender);
      }
    }
    // Score using MatchedName if available (e.g., armor sets matched via piece name)
    const nameToScore = row.MatchedName || row.Name;
    let score = scoreSearchResult(nameToScore, query, genderedQuery);
    // For societies, also score against abbreviation (stored in SubType)
    if (row.Type === 'Society' && row.SubType) {
      score = Math.max(score, scoreSearchResult(row.SubType, query, genderedQuery));
    }
    return { ...row, DisplayName: displayName, _score: score };
  });

  // Filter out zero-score results and sort by score descending
  return scoredResults
    .filter(r => r._score > 0)
    .sort((a, b) => {
      if (b._score !== a._score) return b._score - a._score;
      return a.Name.length - b.Name.length;
    })
    .map(r => formatSearchResult(r, r._score));
}

// Valid item types for filtering (prevents SQL injection)
const VALID_ITEM_TYPES = ['Weapon', 'Armor', 'Clothing', 'Tool', 'Material', 'Blueprint', 'Component', 'Furniture', 'Enhancer', 'Attachment', 'ArmorSet', 'Consumable', 'Mining', 'Amplifier', 'Vehicle'];

async function searchItems(query, fuzzy = false, options = {}){
  query = query.trim(); // Trim whitespace to avoid matching issues
  const useFuzzy = fuzzy && await checkTrgmAvailable();
  let { type: filterType, limit: resultLimit = 50 } = options;

  // Validate type filter to prevent SQL injection
  if (filterType && !VALID_ITEM_TYPES.includes(filterType)) {
    filterType = null;
  }

  // Check if query is searching for a gendered variant
  const genderedQuery = parseGenderedQuery(query);
  // If searching for gendered variant, also search by base name (with original tag if present)
  const searchName = genderedQuery
    ? (genderedQuery.tag ? `${genderedQuery.baseName} (${genderedQuery.tag})` : genderedQuery.baseName)
    : query;

  // Multi-word search: split query for individual word matching
  const searchWords = searchName.split(/\s+/).filter(w => w.length >= 2 || /^\d+$/.test(w));
  const isMultiWord = searchWords.length > 1;
  // Fuzzy params: $1=name, $2=%name%, $3=name%, $4+=mw  Non-fuzzy: $1=%name%, $2=name%, $3+=mw
  const mwStart = useFuzzy ? 4 : 3;
  const mwIdx = isMultiWord ? searchWords.map((_, i) => mwStart + i) : [];
  const mwParams = isMultiWord ? searchWords.map(w => `%${w}%`) : [];
  const mwName = isMultiWord ? ' OR ' + buildMultiWordLike('"Name"', mwIdx) : '';
  const mwArmorSet = isMultiWord ? ' OR ' + buildMultiWordLike('"ArmorSets"."Name"', mwIdx) : '';
  const mwArmor = isMultiWord ? ' OR ' + buildMultiWordLike('"Armors"."Name"', mwIdx) : '';

  // Use a lower similarity threshold (0.1) for better short query matching
  // Also prioritize prefix matches over general similarity
  // ArmorSets are pre-filtered (with piece name matching), so skip outer WHERE for them
  const whereClause = useFuzzy
    ? `WHERE "_prefiltered" OR similarity("Name", $1) >= 0.1 OR "Name" ILIKE $2${mwName}`
    : `WHERE "_prefiltered" OR "Name" ILIKE $1${mwName}`;

  // Order by: prefix match first, then by name length (shorter = more relevant), then alphabetically
  const orderClause = useFuzzy
    ? `ORDER BY (CASE WHEN "Name" ILIKE $3 THEN 0 ELSE 1 END), similarity("Name", $1) DESC, "Name" ASC`
    : `ORDER BY (CASE WHEN "Name" ILIKE $2 THEN 0 ELSE 1 END), length("Name") ASC, "Name" ASC`;

  // Build WHERE clause for armor piece name matching (used in EXISTS subquery)
  const armorPieceWhereClause = useFuzzy
    ? `similarity("Armors"."Name", $1) >= 0.1 OR "Armors"."Name" ILIKE $2${mwArmor}`
    : `"Armors"."Name" ILIKE $1${mwArmor}`;

  // Subquery to get a matching armor piece name for the set (if found via piece matching)
  // Order by similarity to return the best matching piece name
  const armorMatchedPieceSubquery = useFuzzy
    ? `(SELECT "Armors"."Name" FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND (similarity("Armors"."Name", $1) >= 0.1 OR "Armors"."Name" ILIKE $2${mwArmor}) ORDER BY similarity("Armors"."Name", $1) DESC LIMIT 1)`
    : `(SELECT "Armors"."Name" FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND ("Armors"."Name" ILIKE $1${mwArmor}) LIMIT 1)`;

  // When filtering by a specific type, skip per-category partitioning
  // and return up to resultLimit results of that type
  let sql;
  if (filterType) {
    // Direct search for a specific type without per-category limiting
    sql = `
      SELECT * FROM (
        SELECT "Items"."Id" AS "Id", "Items"."Name" AS "Name", "Items"."Type" AS "Type",
          CASE WHEN "Items"."Type" = 'Weapon' THEN "Weapons"."Class" ELSE NULL END AS "SubType",
          CASE WHEN "Items"."Type" = 'Clothing' THEN "Clothes"."Gender" ELSE NULL END AS "Gender",
          FALSE AS "_prefiltered",
          NULL AS "MatchedName"
        FROM ONLY "Items"
        LEFT JOIN ONLY "Weapons" ON "Items"."Id" - ${idOffsets.Weapons} = "Weapons"."Id"
        LEFT JOIN ONLY "Clothes" ON "Items"."Type" = 'Clothing' AND "Items"."Id" - ${idOffsets.Clothings} = "Clothes"."Id"
        WHERE "Items"."Type" = '${filterType}'
        UNION ALL
        SELECT "ArmorSets"."Id" + 1000000000 AS "Id", "ArmorSets"."Name" AS "Name", 'ArmorSet' AS "Type", NULL AS "SubType", NULL AS "Gender", TRUE AS "_prefiltered",
          ${armorMatchedPieceSubquery} AS "MatchedName"
        FROM ONLY "ArmorSets"
        WHERE 'ArmorSet' = '${filterType}' AND (
          ${useFuzzy ? `similarity("ArmorSets"."Name", $1) >= 0.1 OR "ArmorSets"."Name" ILIKE $2${mwArmorSet}` : `"ArmorSets"."Name" ILIKE $1${mwArmorSet}`}
          OR EXISTS (SELECT 1 FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND (${armorPieceWhereClause}))
        )
      )
      ${whereClause}
      ${orderClause}
      LIMIT ${parseInt(resultLimit) || 50}`;
  } else {
    // Original behavior with per-category limiting
    sql = `
      SELECT * FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY "Type" ${orderClause}) as rn
        FROM (
          SELECT "Items"."Id" AS "Id", "Items"."Name" AS "Name", "Items"."Type" AS "Type",
            CASE WHEN "Items"."Type" = 'Weapon' THEN "Weapons"."Class" ELSE NULL END AS "SubType",
            CASE WHEN "Items"."Type" = 'Clothing' THEN "Clothes"."Gender" ELSE NULL END AS "Gender",
            FALSE AS "_prefiltered",
            NULL AS "MatchedName"
          FROM ONLY "Items"
          LEFT JOIN ONLY "Weapons" ON "Items"."Id" - ${idOffsets.Weapons} = "Weapons"."Id"
          LEFT JOIN ONLY "Clothes" ON "Items"."Type" = 'Clothing' AND "Items"."Id" - ${idOffsets.Clothings} = "Clothes"."Id"
          WHERE "Items"."Type" != 'Armor'
          UNION ALL
          SELECT "ArmorSets"."Id" + 1000000000 AS "Id", "ArmorSets"."Name" AS "Name", 'ArmorSet' AS "Type", NULL AS "SubType", NULL AS "Gender", TRUE AS "_prefiltered",
            ${armorMatchedPieceSubquery} AS "MatchedName"
          FROM ONLY "ArmorSets"
          WHERE ${useFuzzy ? `similarity("ArmorSets"."Name", $1) >= 0.1 OR "ArmorSets"."Name" ILIKE $2${mwArmorSet}` : `"ArmorSets"."Name" ILIKE $1${mwArmorSet}`}
            OR EXISTS (SELECT 1 FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND (${armorPieceWhereClause}))
        )
        ${whereClause}
      ) x
      WHERE rn <= 5
      ORDER BY rn, "Type"
      LIMIT ${parseInt(resultLimit) || 50}`;
  }

  // Fuzzy: $1=name, $2=%name%, $3=name%  Non-fuzzy: $1=%name%, $2=name%
  const params = useFuzzy ? [searchName, `%${searchName}%`, `${searchName}%`, ...mwParams] : [`%${searchName}%`, `${searchName}%`, ...mwParams];
  const { rows } = await pool.query(sql, params);

  // Post-process results: apply scoring, filter, and sort
  const scoredResults = rows.map(row => {
    let displayName = null;
    // If searching for a gendered variant and this is a clothing item with 'Both' or null gender,
    // generate a display name with the gender tag (but keep Name as the original for URL linking)
    if (genderedQuery && row.Type === 'Clothing' && (row.Gender === 'Both' || row.Gender === null)) {
      // Check if the item name doesn't already have a gender tag
      if (!/\((M|F)\)/.test(row.Name) && !/\(M,/.test(row.Name) && !/,\s*M\)/.test(row.Name) && !/\(F,/.test(row.Name) && !/,\s*F\)/.test(row.Name)) {
        displayName = generateAliasedName(row.Name, genderedQuery.gender);
      }
    }
    // Score using MatchedName if available (e.g., armor sets matched via piece name)
    const nameToScore = row.MatchedName || row.Name;
    const score = scoreSearchResult(nameToScore, query, genderedQuery);
    return { ...row, DisplayName: displayName, _score: score };
  });

  // Filter out zero-score results and sort by score descending
  return scoredResults
    .filter(r => r._score > 0)
    .sort((a, b) => {
      if (b._score !== a._score) return b._score - a._score;
      return a.Name.length - b.Name.length;
    })
    .map(r => formatSearchResult(r, r._score));
}

// --- Detailed search with entity enrichment ---

// Map search result Type to cache config for enrichment
const ENRICHMENT_MAP = {
  Weapon:       { route: '/weapons',      tables: ['Weapons', 'VehicleAttachmentTypes', 'Materials', 'Professions', 'EffectsOnEquip', 'EffectsOnUse', 'Effects', 'Tiers', 'TierMaterials'], getter: getWeapons },
  Material:     { route: '/materials',     tables: ['Materials'], getter: getMaterials },
  Blueprint:    { route: '/blueprints',    tables: ['Blueprints', 'BlueprintBooks', ...ITEM_TABLES, 'Professions', 'BlueprintMaterials', 'BlueprintDrops'], getter: getBlueprints },
  ArmorSet:     { route: '/armorsets',     tables: ['ArmorSets', 'Armors', 'EffectsOnEquip', 'EffectsOnSetEquip', 'Effects', 'Tiers', 'TierMaterials'], getter: getArmorSets },
  Vehicle:      { route: '/vehicles',      tables: ['Vehicles'], getter: getVehicles },
  Clothing:     { route: '/clothings',     tables: ['Clothes', 'EffectsOnEquip', 'EffectsOnSetEquip', 'Effects', 'EquipSets'], getter: getClothings },
  Pet:          { route: '/pets',          tables: ['Pets'], getter: getPets },
  Mob:          { route: '/mobs',          tables: ['Mobs', 'MobSpecies', 'Planets', 'Professions', 'MobLoots', 'MobMaturities', 'MobSpawns', ...ITEM_TABLES], getter: getMobs },
  Skill:        { route: '/skills',        tables: ['Skills', 'SkillCategories', 'ProfessionSkills', 'SkillUnlocks', 'Professions', 'ProfessionCategories'], getter: getSkills },
  Profession:   { route: '/professions',   tables: ['Professions', 'ProfessionCategories', 'ProfessionSkills', 'SkillUnlocks', 'Skills'], getter: getProfessions },
  Vendor:       { route: '/vendors',       tables: ['Locations', 'Planets', 'VendorOffers', 'VendorOfferPrices', ...ITEM_TABLES], getter: getVendors },
  MedicalTool:  { route: '/medicaltools',  tables: ['MedicalTools', 'EffectsOnEquip', 'EffectsOnUse', 'Effects', 'Tiers', 'TierMaterials'], getter: getMedicalTools },
  Consumable:   { route: '/consumables',   tables: ['Consumables', 'EffectsOnConsume', 'Effects'], getter: getConsumables },
  Strongbox:    { route: '/strongboxes',   tables: ['Strongboxes'], getter: getStrongboxes },
  MiscTool:     { route: '/misctools',     tables: ['MiscTools'], getter: getMiscTools },
  Mission:      { route: '/missions',     tables: ['Missions', 'Planets', 'MissionChains', 'Events', 'Locations'], getter: getMissions },
  MissionChain: { route: '/missionchains', tables: ['MissionChains', 'Planets'], getter: getMissionChains },
  Location:     { route: '/locations',    tables: ['Locations', 'Planets', 'Areas', 'Estates', 'LandAreas', 'LocationFacilities', 'Facilities', 'WaveEventWaves'], getter: getLocations },
  MedicalChip:           { route: '/medicalchips',           tables: ['MedicalChips', 'Materials', 'EffectsOnEquip', 'EffectsOnUse', 'Effects'], getter: getMedicalChips },
  Refiner:               { route: '/refiners',               tables: ['Refiners'], getter: getRefiners },
  Scanner:               { route: '/scanners',               tables: ['Scanners'], getter: getScanners },
  Finder:                { route: '/finders',                tables: ['Finders', 'EffectsOnEquip', 'Effects', 'Tiers', 'TierMaterials'], getter: getFinders },
  Excavator:             { route: '/excavators',             tables: ['Excavators', 'EffectsOnEquip', 'Effects', 'Tiers', 'TierMaterials'], getter: getExcavators },
  TeleportationChip:     { route: '/teleportationchips',     tables: ['TeleportationChips', 'Professions', 'Materials'], getter: getTeleportationChips },
  EffectChip:            { route: '/effectchips',            tables: ['EffectChips', 'Professions', 'Materials', 'EffectsOnUse', 'Effects'], getter: getEffectChips },
  CreatureControlCapsule: { route: '/capsules',              tables: ['CreatureControlCapsules'], getter: getCapsules },
  Furniture:             { route: '/furniture',              tables: ['Furniture'], getter: getFurnitures },
  Decoration:            { route: '/decorations',            tables: ['Decorations'], getter: getDecorations },
  StorageContainer:      { route: '/storagecontainers',      tables: ['StorageContainers'], getter: getStorageContainers },
  Sign:                  { route: '/signs',                  tables: ['Signs'], getter: getSigns },
  WeaponAmplifier:       { route: '/weaponamplifiers',       tables: ['WeaponAmplifiers'], getter: getWeaponAmplifiers },
  WeaponVisionAttachment: { route: '/weaponvisionattachments', tables: ['WeaponVisionAttachments'], getter: getWeaponVisionAttachments },
  Absorber:              { route: '/absorbers',              tables: ['Absorbers'], getter: getAbsorbers },
  ArmorPlating:          { route: '/armorplatings',          tables: ['ArmorPlatings'], getter: getArmorPlatings },
  FinderAmplifier:       { route: '/finderamplifiers',       tables: ['FinderAmplifiers'], getter: getFinderAmplifiers },
  Enhancer:              { route: '/enhancers',              tables: ['Enhancers', 'EnhancerType'], getter: getEnhancers },
  MindforceImplant:      { route: '/mindforceimplants',      tables: ['MindforceImplants'], getter: getMindforceImplants },
  BlueprintBook:         { route: '/blueprintbooks',         tables: ['BlueprintBooks', 'Planets'], getter: getBlueprintBooks },
};

/**
 * Build name-lookup maps from cached entity lists.
 * Only fetches caches for types present in the search results.
 */
async function buildEntityCaches(types) {
  const caches = {};
  const uniqueTypes = [...new Set(types)];
  await Promise.all(uniqueTypes.map(async (type) => {
    const config = ENRICHMENT_MAP[type];
    if (!config) return;
    try {
      const list = await withCache(config.route, config.tables, config.getter);
      if (Array.isArray(list)) {
        caches[type] = new Map(list.map(item => [item.Name, item]));
      }
    } catch (e) {
      console.warn(`[search/detailed] Failed to load cache for ${type}:`, e.message);
    }
  }));
  return caches;
}

// Fields to exclude when merging full entity data (already present from search result or internal)
const ENRICHMENT_EXCLUDE = new Set(['Id', 'Name', 'Type', 'SubType', 'Score', 'Links']);

/**
 * Detailed search: runs search then enriches each result with full entity data
 * from the cached entity data (Properties, Maturities, Planet, Profession, etc.).
 */
async function searchDetailed(query, fuzzy = false, perType = 100, totalLimit = 300) {
  const results = await search(query, fuzzy, perType, totalLimit);

  // Build caches only for types that appear in results
  const resultTypes = results.map(r => r.Type);
  const caches = await buildEntityCaches(resultTypes);

  // Enrich each result with all top-level fields from the full entity
  const enriched = results.map(result => {
    const cache = caches[result.Type];
    if (!cache) return result;
    const fullEntity = cache.get(result.Name);
    if (!fullEntity) return result;
    const merged = { ...result };
    for (const key of Object.keys(fullEntity)) {
      if (!ENRICHMENT_EXCLUDE.has(key)) {
        merged[key] = fullEntity[key];
      }
    }
    // Preserve the entity's own Type (e.g. "Animal" for mobs) under EntityType
    if (fullEntity.Type && fullEntity.Type !== result.Type) {
      merged.EntityType = fullEntity.Type;
    }
    return merged;
  });

  return enriched;
}

function register(app){
  /**
   * @swagger
   * /search:
   *  get:
   *    description: Search for entities by name. Returns up to 30 results. Supports fuzzy matching via pg_trgm if available.
   *    parameters:
   *      - in: query
   *        name: query
   *        schema:
   *          type: string
   *        required: true
   *        description: The search query
   *      - in: query
   *        name: fuzzy
   *        schema:
   *          type: boolean
   *        required: false
   *        description: Enable fuzzy matching (requires pg_trgm extension)
   *    responses:
   *      '200':
   *        description: A list of entities matching the search query
   *      '400':
   *        description: Query cannot be empty
   */
  app.get('/search', async (req,res) => {
    if (!req.query.query || req.query.query.trim().length===0) return res.status(400).send('Query cannot be empty');
    const fuzzy = req.query.fuzzy === 'true' || req.query.fuzzy === '1';
    res.json(await search(req.query.query, fuzzy));
  });
  /**
   * @swagger
   * /search/detailed:
   *  get:
   *    description: Search with enriched results. Returns full Properties for each result from cached entity data.
   *    parameters:
   *      - in: query
   *        name: query
   *        schema:
   *          type: string
   *        required: true
   *        description: The search query
   *      - in: query
   *        name: fuzzy
   *        schema:
   *          type: boolean
   *        required: false
   *        description: Enable fuzzy matching (requires pg_trgm extension)
   *    responses:
   *      '200':
   *        description: A list of enriched entities matching the search query
   *      '400':
   *        description: Query cannot be empty
   */
  app.get('/search/detailed', async (req, res) => {
    if (!req.query.query || req.query.query.trim().length === 0) return res.status(400).send('Query cannot be empty');
    const fuzzy = req.query.fuzzy === 'true' || req.query.fuzzy === '1';
    res.json(await searchDetailed(req.query.query, fuzzy));
  });
  /**
   * @swagger
   * /search/items:
   *  get:
   *    description: Search for items by name. Returns up to 50 results. Supports fuzzy matching via pg_trgm if available.
   *    parameters:
   *      - in: query
   *        name: query
   *        schema:
   *          type: string
   *        required: true
   *        description: The search query
   *      - in: query
   *        name: fuzzy
   *        schema:
   *          type: boolean
   *        required: false
   *        description: Enable fuzzy matching (requires pg_trgm extension)
   *      - in: query
   *        name: type
   *        schema:
   *          type: string
   *        required: false
   *        description: Filter to a specific item type (e.g., Blueprint, Weapon). When specified, removes per-category result limit.
   *      - in: query
   *        name: limit
   *        schema:
   *          type: integer
   *        required: false
   *        description: Maximum number of results to return (default 50)
   *    responses:
   *      '200':
   *        description: A list of items matching the search query
   *      '400':
   *        description: Query cannot be empty
   */
  app.get('/search/items', async (req,res) => {
    if (!req.query.query || req.query.query.trim().length===0) return res.status(400).send('Query cannot be empty');
    const fuzzy = req.query.fuzzy === 'true' || req.query.fuzzy === '1';
    const options = {
      type: req.query.type,
      limit: parseInt(req.query.limit) || 50
    };
    res.json(await searchItems(req.query.query, fuzzy, options));
  });
}

module.exports = { register, search, searchItems, searchDetailed };

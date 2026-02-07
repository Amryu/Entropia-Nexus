const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');

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

function formatSearchResult(x, score){
  const result = { Id: x.Id, Name: x.Name, Type: x.Type, SubType: x.SubType, Score: score };
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

async function search(query, fuzzy = false){
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

  // Use a lower similarity threshold (0.1) for better short query matching
  // Also prioritize prefix matches over general similarity
  // ArmorSets are pre-filtered (with piece name matching), so skip outer WHERE for them
  const whereClause = useFuzzy
    ? `WHERE "_prefiltered" OR similarity("Name", $1) >= 0.1 OR "Name" ILIKE $2`
    : `WHERE "_prefiltered" OR "Name" ILIKE $1`;

  // Order by: prefix match first, then similarity, then alphabetically
  const orderClause = useFuzzy
    ? `ORDER BY (CASE WHEN "Name" ILIKE $3 THEN 0 ELSE 1 END), similarity("Name", $1) DESC, "Name" ASC`
    : `ORDER BY "Id"`;

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
        SELECT "Locations"."Id" + 8000000000 AS "Id", "Locations"."Name" AS "Name", 'Location' AS "Type", "Locations"."Type"::text AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName"
        FROM ONLY "Locations"
        LEFT JOIN ONLY "Planets" ON "Locations"."PlanetId" = "Planets"."Id"`;
  }

  // Build WHERE clause for armor piece name matching (used in EXISTS subquery)
  // This allows searching for individual armor piece names but returning the parent set
  const armorPieceWhereClause = useFuzzy
    ? `similarity("Armors"."Name", $1) >= 0.1 OR "Armors"."Name" ILIKE $2`
    : `"Armors"."Name" ILIKE $1`;

  // Subquery to get a matching armor piece name for the set (if found via piece matching)
  // Order by similarity to return the best matching piece name
  const armorMatchedPieceSubquery = useFuzzy
    ? `(SELECT "Armors"."Name" FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND (similarity("Armors"."Name", $1) >= 0.1 OR "Armors"."Name" ILIKE $2) ORDER BY similarity("Armors"."Name", $1) DESC LIMIT 1)`
    : `(SELECT "Armors"."Name" FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND "Armors"."Name" ILIKE $1 LIMIT 1)`;

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
        WHERE ${useFuzzy ? `similarity("ArmorSets"."Name", $1) >= 0.1 OR "ArmorSets"."Name" ILIKE $2` : `"ArmorSets"."Name" ILIKE $1`}
           OR EXISTS (SELECT 1 FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND (${armorPieceWhereClause}))
        UNION ALL
        SELECT "Mobs"."Id" + 2000000000 AS "Id", "Mobs"."Name" AS "Name", 'Mob' AS "Type", "Planets"."Name" AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName" FROM ONLY "Mobs" INNER JOIN ONLY "Planets" ON "Mobs"."PlanetId" = "Planets"."Id"
        UNION ALL
        SELECT "Skills"."Id" + 3000000000 AS "Id", "Skills"."Name" AS "Name", 'Skill' AS "Type", NULL AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName" FROM ONLY "Skills"
        UNION ALL
        SELECT "Professions"."Id" + 4000000000 AS "Id", "Professions"."Name" AS "Name", 'Profession' AS "Type", NULL AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName" FROM ONLY "Professions"
        UNION ALL
        SELECT "Vendors"."Id" + 5000000000 AS "Id", "Vendors"."Name" AS "Name", 'Vendor' AS "Type", NULL AS "SubType", NULL AS "Gender", FALSE AS "_prefiltered", NULL AS "MatchedName" FROM ONLY "Vendors"${optionalUnions}
      )
      ${whereClause}
    ) x
    WHERE rn <= 5
    ORDER BY rn, "Type"
    LIMIT 50`;

  // $3 is for prefix match check in ordering (query%)
  const params = useFuzzy ? [searchName, `%${searchName}%`, `${searchName}%`] : [`%${searchName}%`];
  const { rows } = await pool.query(sql, params);

  // Post-process results: apply scoring, filter, and sort
  const scoredResults = rows.map(row => {
    let displayName = row.Name;
    // If searching for a gendered variant and this is a clothing item with 'Both' or null gender
    if (genderedQuery && row.Type === 'Clothing' && (row.Gender === 'Both' || row.Gender === null)) {
      // Check if the item name doesn't already have a gender tag
      if (!/\((M|F)\)/.test(row.Name) && !/\(M,/.test(row.Name) && !/,\s*M\)/.test(row.Name) && !/\(F,/.test(row.Name) && !/,\s*F\)/.test(row.Name)) {
        displayName = generateAliasedName(row.Name, genderedQuery.gender);
      }
    }
    // Score using MatchedName if available (e.g., armor sets matched via piece name)
    const nameToScore = row.MatchedName || row.Name;
    const score = scoreSearchResult(nameToScore, query, genderedQuery);
    return { ...row, Name: displayName, _score: score };
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

  // Use a lower similarity threshold (0.1) for better short query matching
  // Also prioritize prefix matches over general similarity
  // ArmorSets are pre-filtered (with piece name matching), so skip outer WHERE for them
  const whereClause = useFuzzy
    ? `WHERE "_prefiltered" OR similarity("Name", $1) >= 0.1 OR "Name" ILIKE $2`
    : `WHERE "_prefiltered" OR "Name" ILIKE $1`;

  // Order by: prefix match first, then similarity, then alphabetically
  const orderClause = useFuzzy
    ? `ORDER BY (CASE WHEN "Name" ILIKE $3 THEN 0 ELSE 1 END), similarity("Name", $1) DESC, "Name" ASC`
    : `ORDER BY "Id"`;

  // Build WHERE clause for armor piece name matching (used in EXISTS subquery)
  const armorPieceWhereClause = useFuzzy
    ? `similarity("Armors"."Name", $1) >= 0.1 OR "Armors"."Name" ILIKE $2`
    : `"Armors"."Name" ILIKE $1`;

  // Subquery to get a matching armor piece name for the set (if found via piece matching)
  // Order by similarity to return the best matching piece name
  const armorMatchedPieceSubquery = useFuzzy
    ? `(SELECT "Armors"."Name" FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND (similarity("Armors"."Name", $1) >= 0.1 OR "Armors"."Name" ILIKE $2) ORDER BY similarity("Armors"."Name", $1) DESC LIMIT 1)`
    : `(SELECT "Armors"."Name" FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND "Armors"."Name" ILIKE $1 LIMIT 1)`;

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
          ${useFuzzy ? `similarity("ArmorSets"."Name", $1) >= 0.1 OR "ArmorSets"."Name" ILIKE $2` : `"ArmorSets"."Name" ILIKE $1`}
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
          WHERE ${useFuzzy ? `similarity("ArmorSets"."Name", $1) >= 0.1 OR "ArmorSets"."Name" ILIKE $2` : `"ArmorSets"."Name" ILIKE $1`}
            OR EXISTS (SELECT 1 FROM ONLY "Armors" WHERE "Armors"."SetId" = "ArmorSets"."Id" AND (${armorPieceWhereClause}))
        )
        ${whereClause}
      ) x
      WHERE rn <= 5
      ORDER BY rn, "Type"
      LIMIT ${parseInt(resultLimit) || 50}`;
  }

  // $3 is for prefix match check in ordering (query%)
  const params = useFuzzy ? [searchName, `%${searchName}%`, `${searchName}%`] : [`%${searchName}%`];
  const { rows } = await pool.query(sql, params);

  // Post-process results: apply scoring, filter, and sort
  const scoredResults = rows.map(row => {
    let displayName = row.Name;
    // If searching for a gendered variant and this is a clothing item with 'Both' or null gender
    if (genderedQuery && row.Type === 'Clothing' && (row.Gender === 'Both' || row.Gender === null)) {
      // Check if the item name doesn't already have a gender tag
      if (!/\((M|F)\)/.test(row.Name) && !/\(M,/.test(row.Name) && !/,\s*M\)/.test(row.Name) && !/\(F,/.test(row.Name) && !/,\s*F\)/.test(row.Name)) {
        displayName = generateAliasedName(row.Name, genderedQuery.gender);
      }
    }
    // Score using MatchedName if available (e.g., armor sets matched via piece name)
    const nameToScore = row.MatchedName || row.Name;
    const score = scoreSearchResult(nameToScore, query, genderedQuery);
    return { ...row, Name: displayName, _score: score };
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

module.exports = { register, search, searchItems };

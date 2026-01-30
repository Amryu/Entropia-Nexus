const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');

function formatSearchResult(x){ return { Name: x.Name, Type: x.Type, SubType: x.SubType }; }

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

async function search(query, fuzzy = false){
  const useFuzzy = fuzzy && await checkTrgmAvailable();

  // For fuzzy search, use trigram similarity; otherwise use ILIKE
  const whereClause = useFuzzy
    ? `WHERE "Name" % $1 OR "Name" ILIKE $2`
    : `WHERE "Name" ILIKE $1`;

  const orderClause = useFuzzy
    ? `ORDER BY similarity("Name", $1) DESC, "Name" ASC`
    : `ORDER BY "Id"`;

  const sql = `
    SELECT * FROM (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY "Type" ${orderClause}) as rn
      FROM (
        SELECT "Items"."Id" AS "Id", "Items"."Name" AS "Name", "Items"."Type" AS "Type",
          CASE WHEN "Items"."Type" = 'Weapon' THEN "Weapons"."Class" ELSE NULL END AS "SubType"
        FROM ONLY "Items"
        LEFT JOIN ONLY "Weapons" ON "Items"."Id" - ${idOffsets.Weapons} = "Weapons"."Id"
        WHERE "Items"."Type" != 'Armor'
        UNION ALL
        SELECT "ArmorSets"."Id" + 1000000000 AS "Id", "ArmorSets"."Name" AS "Name", 'Armor' AS "Type", NULL AS "SubType" FROM ONLY "ArmorSets"
        UNION ALL
        SELECT "Mobs"."Id" + 2000000000 AS "Id", "Mobs"."Name" AS "Name", 'Mob' AS "Type", "Planets"."Name" AS "SubType" FROM ONLY "Mobs" INNER JOIN ONLY "Planets" ON "Mobs"."PlanetId" = "Planets"."Id"
        UNION ALL
        SELECT "Skills"."Id" + 3000000000 AS "Id", "Skills"."Name" AS "Name", 'Skill' AS "Type", NULL AS "SubType" FROM ONLY "Skills"
        UNION ALL
        SELECT "Professions"."Id" + 4000000000 AS "Id", "Professions"."Name" AS "Name", 'Profession' AS "Type", NULL AS "SubType" FROM ONLY "Professions"
        UNION ALL
        SELECT "Vendors"."Id" + 5000000000 AS "Id", "Vendors"."Name" AS "Name", 'Vendor' AS "Type", NULL AS "SubType" FROM ONLY "Vendors"
      )
      ${whereClause}
    ) x
    WHERE rn <= 5
    LIMIT 30`;

  const params = useFuzzy ? [query, `%${query}%`] : [`%${query}%`];
  const { rows } = await pool.query(sql, params);
  return rows.map(formatSearchResult);
}

async function searchItems(query, fuzzy = false){
  const useFuzzy = fuzzy && await checkTrgmAvailable();

  const whereClause = useFuzzy
    ? `WHERE "Name" % $1 OR "Name" ILIKE $2`
    : `WHERE "Name" ILIKE $1`;

  const orderClause = useFuzzy
    ? `ORDER BY similarity("Name", $1) DESC, "Name" ASC`
    : `ORDER BY "Id"`;

  const sql = `
    SELECT * FROM (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY "Type" ${orderClause}) as rn
      FROM (
        SELECT "Items"."Id" AS "Id", "Items"."Name" AS "Name", "Items"."Type" AS "Type",
          CASE WHEN "Items"."Type" = 'Weapon' THEN "Weapons"."Class" ELSE NULL END AS "SubType"
        FROM ONLY "Items"
        LEFT JOIN ONLY "Weapons" ON "Items"."Id" - ${idOffsets.Weapons} = "Weapons"."Id"
        WHERE "Items"."Type" != 'Armor'
        UNION ALL
        SELECT "ArmorSets"."Id" + 1000000000 AS "Id", "ArmorSets"."Name" AS "Name", 'Armor' AS "Type", NULL AS "SubType" FROM ONLY "ArmorSets"
      )
      ${whereClause}
    ) x
    WHERE rn <= 5
    LIMIT 30`;

  const params = useFuzzy ? [query, `%${query}%`] : [`%${query}%`];
  const { rows } = await pool.query(sql, params);
  return rows.map(formatSearchResult);
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
   *    description: Search for items by name. Returns up to 30 results. Supports fuzzy matching via pg_trgm if available.
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
   *        description: A list of items matching the search query
   *      '400':
   *        description: Query cannot be empty
   */
  app.get('/search/items', async (req,res) => {
    if (!req.query.query || req.query.query.trim().length===0) return res.status(400).send('Query cannot be empty');
    const fuzzy = req.query.fuzzy === 'true' || req.query.fuzzy === '1';
    res.json(await searchItems(req.query.query, fuzzy));
  });
}

module.exports = { register, search, searchItems };

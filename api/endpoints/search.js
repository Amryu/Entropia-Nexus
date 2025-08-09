const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');

function formatSearchResult(x){ return { Name: x.Name, Type: x.Type, SubType: x.SubType }; }

async function search(query){
  const sql = `
    SELECT * FROM (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY "Type" ORDER BY "Id") as rn
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
      WHERE "Name" ILIKE $1
    ) x
    WHERE rn <= 5
    LIMIT 20`;
  const { rows } = await pool.query(sql, [`%${query}%`]);
  return rows.map(formatSearchResult);
}

async function searchItems(query){
  const { rows } = await pool.query(`
    SELECT * FROM (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY "Type" ORDER BY "Id") as rn
      FROM (
        SELECT "Items"."Id" AS "Id", "Items"."Name" AS "Name", "Items"."Type" AS "Type",
          CASE WHEN "Items"."Type" = 'Weapon' THEN "Weapons"."Class" ELSE NULL END AS "SubType"
        FROM ONLY "Items"
        LEFT JOIN ONLY "Weapons" ON "Items"."Id" - ${idOffsets.Weapons} = "Weapons"."Id"
        WHERE "Items"."Type" != 'Armor' AND "Items"."Name" ILIKE $1
        UNION ALL
        SELECT "ArmorSets"."Id" + 1000000000 AS "Id", "ArmorSets"."Name" AS "Name", 'Armor' AS "Type", NULL AS "SubType" FROM ONLY "ArmorSets"
        )
      WHERE "Name" ILIKE $1
    ) x
    WHERE rn <= 5
    LIMIT 20`, [`%${query}%`]);
  return rows.map(formatSearchResult);
}

function register(app){
  /**
   * @swagger
   * /search:
   *  get:
   *    description: Search for entities by name. Returns up to 20 results.
   *    parameters:
   *      - in: query
   *        name: query
   *        schema:
   *          type: string
   *        required: true
   *        description: The search query
   *    responses:
   *      '200':
   *        description: A list of entities matching the search query
   *      '400':
   *        description: Query cannot be empty
   */
  app.get('/search', async (req,res) => {
    if (!req.query.query || req.query.query.trim().length===0) return res.status(400).send('Query cannot be empty');
    res.json(await search(req.query.query));
  });
  /**
   * @swagger
   * /search/items:
   *  get:
   *    description: Search for items by name. Returns up to 20 results.
   *    parameters:
   *      - in: query
   *        name: query
   *        schema:
   *          type: string
   *        required: true
   *        description: The search query
   *    responses:
   *      '200':
   *        description: A list of items matching the search query
   *      '400':
   *        description: Query cannot be empty
   */
  app.get('/search/items', async (req,res) => {
    if (!req.query.query || req.query.query.trim().length===0) return res.status(400).send('Query cannot be empty');
    res.json(await searchItems(req.query.query));
  });
}

module.exports = { register, search, searchItems };

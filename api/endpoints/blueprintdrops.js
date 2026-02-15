const pgp = require('pg-promise')();
const { pool } = require('./dbClient');
const { parseItemList } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache } = require('./responseCache');

const queries = {
  BlueprintDrops: `
    SELECT bd."SourceId", s."Name" AS "SourceName",
           bd."DropId",   d."Name" AS "DropName",
           d."Level"       AS "DropLevel"
    FROM ONLY "BlueprintDrops" bd
    INNER JOIN ONLY "Blueprints" s ON s."Id" = bd."SourceId"
    INNER JOIN ONLY "Blueprints" d ON d."Id" = bd."DropId"
  `,
};

function formatBlueprintRef(id, name){
  return {
    Id: id,
    ItemId: id + idOffsets.Blueprints,
    Name: name,
    Links: { "$Url": `/blueprints/${id}` },
  };
}

function formatBlueprintDrop(row){
  return {
    Source: formatBlueprintRef(row.SourceId, row.SourceName),
    Drop: formatBlueprintRef(row.DropId, row.DropName),
  };
}

async function getBlueprintDrops({ sources = null, drops = null } = {}){
  let where = '';
  const params = [];
  if (sources && sources.length){
    where = pgp.as.format(' WHERE s."Name" IN ($1:csv)', [sources.map(x => `${x}`)]);
  } else if (drops && drops.length){
    where = pgp.as.format(' WHERE d."Name" IN ($1:csv)', [drops.map(x => `${x}`)]);
  }
  const { rows } = await pool.query(queries.BlueprintDrops + where);
  return rows.map(formatBlueprintDrop);
}

// Internal helper for other modules that need raw details (e.g., DropLevel)
async function getBlueprintDropRows({ sources = null, drops = null } = {}){
  let where = '';
  if (sources && sources.length){
    where = pgp.as.format(' WHERE s."Name" IN ($1:csv)', [sources.map(x => `${x}`)]);
  } else if (drops && drops.length){
    where = pgp.as.format(' WHERE d."Name" IN ($1:csv)', [drops.map(x => `${x}`)]);
  }
  const { rows } = await pool.query(queries.BlueprintDrops + where);
  return rows; // { SourceId, SourceName, DropId, DropName, DropLevel }
}

function register(app){
  /**
   * @swagger
   * /blueprintdrops:
   *  get:
   *    description: Get blueprint drop relations. Optionally filter by Source or Drops (names).
   *    parameters:
   *      - in: query
   *        name: Source
   *        schema:
   *          type: string
   *        description: Source blueprint name
   *      - in: query
   *        name: Sources
   *        schema:
   *          type: string
   *        description: Comma-separated source blueprint names
   *      - in: query
   *        name: Drop
   *        schema:
   *          type: string
   *        description: Drop blueprint name
   *      - in: query
   *        name: Drops
   *        schema:
   *          type: string
   *        description: Comma-separated drop blueprint names
   *    responses:
   *      '200':
   *        description: A list of blueprint drops, or a list of Sources/Drops when filtered
   *      '400':
   *        description: Invalid or conflicting parameters
   */
  app.get('/blueprintdrops', async (req,res,next) => {
    try {
      const { Source, Sources, Drop, Drops } = req.query;
      // validate mutual exclusivity
      if ((Source && Sources) || (Drop && Drops))
        return res.status(400).send('Cannot specify both singular and plural of the same parameter');
      const usingSource = Source || Sources;
      const usingDrop = Drop || Drops;
      if (usingSource && usingDrop)
        return res.status(400).send('Source/Sources and Drop/Drops are mutually exclusive');

      let sources = null, drops = null;
      if (Source) sources = [Source];
      else if (Sources) {
        sources = parseItemList(Sources);
        if (sources.length === 0) return res.status(400).send('Sources cannot be empty');
      }
      if (Drop) drops = [Drop];
      else if (Drops) {
        drops = parseItemList(Drops);
        if (drops.length === 0) return res.status(400).send('Drops cannot be empty');
      }

      if (sources || drops) {
        const rows = await getBlueprintDrops({ sources, drops });
        if (sources) {
          return res.json(rows.map(r => r.Drop));
        }
        if (drops) {
          return res.json(rows.map(r => r.Source));
        }
        res.json(rows);
      } else {
        res.json(await withCache('/blueprintdrops', ['BlueprintDrops', 'Blueprints'], getBlueprintDrops));
      }
    } catch (e){ next(e); }
  });
}

module.exports = { register, getBlueprintDrops, getBlueprintDropRows };

const pgp = require('pg-promise')();
const { pool } = require('./dbClient');
const { parseItemList } = require('./utils');
const { idOffsets, BLUEPRINT_DROP_CATEGORIES, BLUEPRINT_DROP_LEVEL_RANGE } = require('./constants');
const { withCache } = require('./responseCache');

// Get all blueprint types that share a category with the given type
function getTypesInCategory(type) {
  const category = BLUEPRINT_DROP_CATEGORIES[type];
  if (!category) return [];
  return Object.entries(BLUEPRINT_DROP_CATEGORIES)
    .filter(([, cat]) => cat === category)
    .map(([t]) => t);
}

// Compute drops for source blueprints (what can drop when crafting them)
async function computeDropsForSources(sourceNames) {
  // Look up source blueprints
  const { rows: sources } = await pool.query(
    `SELECT "Id", "Name", "Level", "Type"
     FROM ONLY "Blueprints"
     WHERE "Name" IN (${sourceNames.map((_, i) => `$${i + 1}`).join(', ')})`,
    sourceNames
  );
  if (!sources.length) return [];

  const results = [];
  for (const src of sources) {
    if (src.Level == null || !src.Type) continue;
    const typesInCategory = getTypesInCategory(src.Type);
    if (!typesInCategory.length) continue;
    const minLevel = src.Level - BLUEPRINT_DROP_LEVEL_RANGE.below;
    const maxLevel = src.Level + BLUEPRINT_DROP_LEVEL_RANGE.above;
    const { rows: drops } = await pool.query(
      `SELECT "Id", "Name", "Level", "DropRarity"
       FROM ONLY "Blueprints"
       WHERE "IsDroppable" = true
         AND "Type" = ANY($1::text[])
         AND "Level" BETWEEN $2 AND $3
         AND "Id" != $4
       ORDER BY "Level", "Name"`,
      [typesInCategory, minLevel, maxLevel, src.Id]
    );
    for (const d of drops) {
      results.push({
        Id: d.Id,
        ItemId: d.Id + idOffsets.Blueprints,
        Name: d.Name,
        Level: d.Level != null ? Number(d.Level) : null,
        DropRarity: d.DropRarity || null,
        Links: { "$Url": `/blueprints/${d.Id}` },
      });
    }
  }

  // Deduplicate by Id
  const seen = new Set();
  return results.filter(r => {
    if (seen.has(r.Id)) return false;
    seen.add(r.Id);
    return true;
  });
}

// Compute sources for drop blueprints (what blueprints, when crafted, can yield them)
async function computeSourcesForDrops(dropNames) {
  const { rows: drops } = await pool.query(
    `SELECT "Id", "Name", "Level", "Type", "IsDroppable"
     FROM ONLY "Blueprints"
     WHERE "Name" IN (${dropNames.map((_, i) => `$${i + 1}`).join(', ')})`,
    dropNames
  );
  if (!drops.length) return [];

  const results = [];
  for (const drop of drops) {
    if (!drop.IsDroppable || drop.Level == null || !drop.Type) continue;
    const typesInCategory = getTypesInCategory(drop.Type);
    if (!typesInCategory.length) continue;
    // Reverse the level range: which source levels would include this drop?
    // A source at level S drops levels S-below to S+above
    // So this drop (level D) is in range when S-below <= D <= S+above
    // i.e. D-above <= S <= D+below
    const minSourceLevel = drop.Level - BLUEPRINT_DROP_LEVEL_RANGE.above;
    const maxSourceLevel = drop.Level + BLUEPRINT_DROP_LEVEL_RANGE.below;
    const { rows: sources } = await pool.query(
      `SELECT "Id", "Name", "Level"
       FROM ONLY "Blueprints"
       WHERE "Type" = ANY($1::text[])
         AND "Level" BETWEEN $2 AND $3
         AND "Id" != $4
       ORDER BY "Level", "Name"`,
      [typesInCategory, minSourceLevel, maxSourceLevel, drop.Id]
    );
    for (const s of sources) {
      results.push({
        Id: s.Id,
        ItemId: s.Id + idOffsets.Blueprints,
        Name: s.Name,
        Level: s.Level != null ? Number(s.Level) : null,
        Links: { "$Url": `/blueprints/${s.Id}` },
      });
    }
  }

  const seen = new Set();
  return results.filter(r => {
    if (seen.has(r.Id)) return false;
    seen.add(r.Id);
    return true;
  });
}

// Get all droppable blueprints (unfiltered endpoint)
async function getAllDroppableBlueprints() {
  const { rows } = await pool.query(
    `SELECT "Id", "Name", "Type", "Level", "DropRarity"
     FROM ONLY "Blueprints"
     WHERE "IsDroppable" = true
     ORDER BY "Type", "Level", "Name"`
  );
  return rows.map(r => ({
    Id: r.Id,
    ItemId: r.Id + idOffsets.Blueprints,
    Name: r.Name,
    Type: r.Type,
    Level: r.Level != null ? Number(r.Level) : null,
    DropRarity: r.DropRarity || null,
    Links: { "$Url": `/blueprints/${r.Id}` },
  }));
}

// Internal helper for acquisition.js — returns rows compatible with old format
async function getBlueprintDropRows({ sources = null } = {}) {
  if (!sources || !sources.length) return [];
  const results = [];
  const { rows: sourceBps } = await pool.query(
    `SELECT "Id", "Name", "Level", "Type"
     FROM ONLY "Blueprints"
     WHERE "Name" IN (${sources.map((_, i) => `$${i + 1}`).join(', ')})`,
    sources
  );
  for (const src of sourceBps) {
    if (src.Level == null || !src.Type) continue;
    const typesInCategory = getTypesInCategory(src.Type);
    if (!typesInCategory.length) continue;
    const minLevel = src.Level - BLUEPRINT_DROP_LEVEL_RANGE.below;
    const maxLevel = src.Level + BLUEPRINT_DROP_LEVEL_RANGE.above;
    const { rows: drops } = await pool.query(
      `SELECT "Id", "Name", "Level", "DropRarity"
       FROM ONLY "Blueprints"
       WHERE "IsDroppable" = true
         AND "Type" = ANY($1::text[])
         AND "Level" BETWEEN $2 AND $3
         AND "Id" != $4
       ORDER BY "Level", "Name"`,
      [typesInCategory, minLevel, maxLevel, src.Id]
    );
    for (const d of drops) {
      results.push({
        SourceId: src.Id,
        SourceName: src.Name,
        DropId: d.Id,
        DropName: d.Name,
        DropLevel: d.Level,
        DropRarity: d.DropRarity || null,
      });
    }
  }
  return results;
}

function register(app) {
  /**
   * @swagger
   * /blueprintdrops:
   *  get:
   *    description: Get blueprint drop relations (computed by level range and category). Optionally filter by Source or Drop names.
   *    parameters:
   *      - in: query
   *        name: Source
   *        schema:
   *          type: string
   *        description: Source blueprint name (what can drop when crafting this)
   *      - in: query
   *        name: Sources
   *        schema:
   *          type: string
   *        description: Comma-separated source blueprint names
   *      - in: query
   *        name: Drop
   *        schema:
   *          type: string
   *        description: Drop blueprint name (what can yield this drop)
   *      - in: query
   *        name: Drops
   *        schema:
   *          type: string
   *        description: Comma-separated drop blueprint names
   *    responses:
   *      '200':
   *        description: A list of droppable blueprints, or computed drop/source results when filtered
   *      '400':
   *        description: Invalid or conflicting parameters
   */
  app.get('/blueprintdrops', async (req, res, next) => {
    try {
      const { Source, Sources, Drop, Drops } = req.query;
      if ((Source && Sources) || (Drop && Drops))
        return res.status(400).send('Cannot specify both singular and plural of the same parameter');
      const usingSource = Source || Sources;
      const usingDrop = Drop || Drops;
      if (usingSource && usingDrop)
        return res.status(400).send('Source/Sources and Drop/Drops are mutually exclusive');

      if (usingSource) {
        const sources = Sources ? parseItemList(Sources) : [Source];
        if (sources.length === 0) return res.status(400).send('Sources cannot be empty');
        return res.json(await computeDropsForSources(sources));
      }

      if (usingDrop) {
        const drops = Drops ? parseItemList(Drops) : [Drop];
        if (drops.length === 0) return res.status(400).send('Drops cannot be empty');
        return res.json(await computeSourcesForDrops(drops));
      }

      res.json(await withCache('/blueprintdrops', ['Blueprints'], getAllDroppableBlueprints));
    } catch (e) { next(e); }
  });
}

module.exports = { register, getBlueprintDropRows };

const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  FishingRods: 'SELECT "FishingRods".*, "Professions"."Name" AS "Profession" FROM ONLY "FishingRods" LEFT JOIN ONLY "Professions" ON "FishingRods"."ProfessionId" = "Professions"."Id"'
};

function formatFishingRod(x, data) {
  const itemId = x.Id + idOffsets.FishingRods;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      RodType: x.RodType,
      Strength: x.Strength !== null ? Number(x.Strength) : null,
      Flexibility: x.Flexibility !== null ? Number(x.Flexibility) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
      Skill: {
        LearningIntervalStart: x.MinLevel !== null ? Number(x.MinLevel) : null,
        LearningIntervalEnd: x.MaxLevel !== null ? Number(x.MaxLevel) : null,
        IsSiB: x.IsSib === 1
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Profession: {
      Name: x.Profession,
      Links: { "$Url": x.ProfessionId !== null ? `/professions/${x.ProfessionId}` : null }
    },
    Links: { "$Url": `/fishingrods/${x.Id}` },
  };
}

async function getFishingRods() {
  const { rows } = await pool.query(queries.FishingRods);
  const itemIds = rows.map(r => r.Id + idOffsets.FishingRods);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('FishingRod', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  const data = { ClassIds: classIds, ItemProps: itemProps };
  return rows.map(r => formatFishingRod(r, data));
}

async function getFishingRod(idOrName) {
  const row = await getObjectByIdOrName(queries.FishingRods, 'FishingRods', idOrName);
  if (!row) return null;
  const itemId = row.Id + idOffsets.FishingRods;
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('FishingRod', [row.Id]),
    loadItemProperties([itemId])
  ]);
  return formatFishingRod(row, { ClassIds: classIds, ItemProps: itemProps });
}

function register(app) {
  /**
   * @swagger
   * /fishingrods:
   *  get:
   *    description: Get all fishing rods
   *    responses:
   *      '200':
   *        description: A list of fishing rods
   */
  app.get('/fishingrods', async (req, res) => {
    res.json(await withCache('/fishingrods', ['FishingRods', 'ClassIds', 'ItemProperties'], getFishingRods));
  });

  /**
   * @swagger
   * /fishingrods/{fishingRod}:
   *  get:
   *    description: Get a fishing rod by name or id
   *    parameters:
   *      - in: path
   *        name: fishingRod
   *        schema:
   *          type: string
   *        required: true
   *    responses:
   *      '200':
   *        description: The fishing rod
   *      '404':
   *        description: Not found
   */
  app.get('/fishingrods/:fishingRod', async (req, res) => {
    const r = await withCachedLookup('/fishingrods', ['FishingRods', 'ClassIds', 'ItemProperties'], getFishingRods, req.params.fishingRod);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getFishingRods, getFishingRod, formatFishingRod };

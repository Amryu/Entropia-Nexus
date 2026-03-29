const { loadEffectsOnEquipByItemIds } = require('./effects-utils');
const { getTiersByItemIds } = require('./tiers');
const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { Finders: 'SELECT * FROM ONLY "Finders"' };

async function getEffectsOnEquip(ids) {
  if (!ids.length) return {};
  const itemIds = ids.map(id => id + idOffsets.Finders);
  return await loadEffectsOnEquipByItemIds(itemIds);
}

async function getTiers(ids) {
  if (!ids.length) return {};
  const itemIds = ids.map(id => id + idOffsets.Finders);
  return await getTiersByItemIds(itemIds, 0);
}

function formatFinder(x, effectsMap, tiersMap, classIds, itemProps){
  const itemId = x.Id + idOffsets.Finders;
  const effects = effectsMap[itemId] ?? [];
  const tiers = tiersMap[itemId] ?? [];
  const props = itemProps[itemId];
  return {
    Id: x.Id,
    ClassId: classIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Depth: x.Depth !== null ? Number(x.Depth) : null,
      Range: x.Range !== null ? Number(x.Range) : null,
      Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null, MinTT: x.MinTT !== null ? Number(x.MinTT) : null, Decay: x.Decay !== null ? Number(x.Decay) : null, AmmoBurn: x.Probes !== null ? Number(x.Probes) : null },
      Skill: { LearningIntervalStart: x.IntervalStart !== null ? Number(x.IntervalStart) : null, LearningIntervalEnd: x.IntervalEnd !== null ? Number(x.IntervalEnd) : null, IsSiB: true },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    EffectsOnEquip: effects,
    Tiers: tiers,
    Links: { "$Url": `/finders/${x.Id}` }
  };
}

async function getFinders(){
  const { rows } = await pool.query(queries.Finders);
  const itemIds = rows.map(r => r.Id + idOffsets.Finders);
  const [effects, tiers, classIds, itemProps] = await Promise.all([
    getEffectsOnEquip(rows.map(r=>r.Id)),
    getTiers(rows.map(r=>r.Id)),
    loadClassIds('Finder', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  return rows.map(r => formatFinder(r, effects, tiers, classIds, itemProps));
}

async function getFinder(idOrName){
  const row = await getObjectByIdOrName(queries.Finders, 'Finders', idOrName);
  if (!row) return null;
  const itemId = row.Id + idOffsets.Finders;
  const [effects, tiers, classIds, itemProps] = await Promise.all([
    getEffectsOnEquip([row.Id]),
    getTiers([row.Id]),
    loadClassIds('Finder', [row.Id]),
    loadItemProperties([itemId])
  ]);
  return formatFinder(row, effects, tiers, classIds, itemProps);
}

function register(app){
  /**
   * @swagger
   * /finders:
   *  get:
   *    description: Get all finders
   *    responses:
   *      '200':
   *        description: A list of finders
   */
  app.get('/finders', async (req,res) => { res.json(await withCache('/finders', ['Finders', 'EffectsOnEquip', 'Effects', 'Tiers', 'TierMaterials', 'ClassIds', 'ItemProperties'], getFinders)); });
  /**
   * @swagger
   * /finders/{finder}:
   *  get:
   *    description: Get a finder by name or id
   *    parameters:
   *      - in: path
   *        name: finder
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the finder
   *    responses:
   *      '200':
   *        description: The finder
   *      '404':
   *        description: Finder not found
   */
  app.get('/finders/:finder', async (req,res) => { const r = await withCachedLookup('/finders', ['Finders', 'EffectsOnEquip', 'Effects', 'Tiers', 'TierMaterials', 'ClassIds', 'ItemProperties'], getFinders, req.params.finder); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getFinders, getFinder, formatFinder };

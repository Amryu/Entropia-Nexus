const pgp = require('pg-promise')();
const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { loadEffectsOnEquipByItemIds } = require('./effects-utils');
const { getTiersByItemIds } = require('./tiers');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Excavators: 'SELECT * FROM ONLY "Excavators"',
};

async function getEffectsOnEquip(ids) {
  if (!ids.length) return {};
  const itemIds = ids.map(id => id + idOffsets.Excavators);
  return await loadEffectsOnEquipByItemIds(itemIds);
}
async function getTiers(ids) {
  if (!ids.length) return {};
  const itemIds = ids.map(id => id + idOffsets.Excavators);
  return await getTiersByItemIds(itemIds, 0);
}

function formatExcavator(x, effectsMap, tiersMap, classIds, itemProps){
  const itemId = x.Id + idOffsets.Excavators;
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
      Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
      Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null, MinTT: x.MinTT !== null ? Number(x.MinTT) : null, Decay: x.Decay !== null ? Number(x.Decay) : null },
      Skill: { LearningIntervalStart: x.IntervalStart !== null ? Number(x.IntervalStart) : null, LearningIntervalEnd: x.IntervalEnd !== null ? Number(x.IntervalEnd) : null, IsSiB: true },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    EffectsOnEquip: effects,
    Tiers: tiers,
    Links: { "$Url": `/excavators/${x.Id}` }
  };
}

async function getExcavators(){
  const { rows } = await pool.query(queries.Excavators);
  const itemIds = rows.map(r => r.Id + idOffsets.Excavators);
  const [effects, tiers, classIds, itemProps] = await Promise.all([
    getEffectsOnEquip(rows.map(r=>r.Id)),
    getTiers(rows.map(r=>r.Id)),
    loadClassIds('Excavator', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  return rows.map(r => formatExcavator(r, effects, tiers, classIds, itemProps));
}
async function getExcavator(idOrName){
  const row = await getObjectByIdOrName(queries.Excavators, 'Excavators', idOrName);
  if (!row) return null;
  const itemId = row.Id + idOffsets.Excavators;
  const [effects, tiers, classIds, itemProps] = await Promise.all([
    getEffectsOnEquip([row.Id]),
    getTiers([row.Id]),
    loadClassIds('Excavator', [row.Id]),
    loadItemProperties([itemId])
  ]);
  return formatExcavator(row, effects, tiers, classIds, itemProps);
}

function register(app){
  /**
   * @swagger
   * /excavators:
   *  get:
   *    description: Get all excavators
   *    responses:
   *      '200':
   *        description: A list of excavators
   */
  app.get('/excavators', async (req,res) => { res.json(await withCache('/excavators', ['Excavators', 'EffectsOnEquip', 'Effects', 'Tiers', 'TierMaterials', 'ClassIds', 'ItemProperties'], getExcavators)); });
  /**
   * @swagger
   * /excavators/{excavator}:
   *  get:
   *    description: Get an excavator by name or id
   *    parameters:
   *      - in: path
   *        name: excavator
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the excavator
   *    responses:
   *      '200':
   *        description: The excavator
   *      '404':
   *        description: Excavator not found
   */
  app.get('/excavators/:excavator', async (req,res) => { const r = await withCachedLookup('/excavators', ['Excavators', 'EffectsOnEquip', 'Effects', 'Tiers', 'TierMaterials', 'ClassIds', 'ItemProperties'], getExcavators, req.params.excavator); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getExcavators, getExcavator, formatExcavator };

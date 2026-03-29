const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { loadEffectsOnEquipByItemIds } = require('./effects-utils');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { MindforceImplants: 'SELECT * FROM ONLY "MindforceImplants"' };

function formatMindforceImplant(x, effectsMap, classIds, itemProps){
  const itemId = x.Id + idOffsets.MindforceImplants;
  const effects = effectsMap?.[itemId] ?? [];
  const props = itemProps[itemId];
  return {
    Id: x.Id,
    ClassId: classIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      MaxProfessionLevel: x.MaxLvl !== null ? Number(x.MaxLvl) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Absorption: x.Absorption !== null ? Number(x.Absorption) : null,
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    EffectsOnEquip: effects,
    Links: { "$Url": `/mindforceimplants/${x.Id}` }
  };
}

async function getMindforceImplants(){
  const { rows } = await pool.query(queries.MindforceImplants);
  const itemIds = rows.map(r => r.Id + idOffsets.MindforceImplants);
  const [effects, classIds, itemProps] = await Promise.all([
    loadEffectsOnEquipByItemIds(itemIds),
    loadClassIds('MindforceImplant', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  return rows.map(r => formatMindforceImplant(r, effects, classIds, itemProps));
}

async function getMindforceImplant(idOrName){
  const row = await getObjectByIdOrName(queries.MindforceImplants, 'MindforceImplants', idOrName);
  if (!row) return null;
  const itemId = row.Id + idOffsets.MindforceImplants;
  const [effects, classIds, itemProps] = await Promise.all([
    loadEffectsOnEquipByItemIds([itemId]),
    loadClassIds('MindforceImplant', [row.Id]),
    loadItemProperties([itemId])
  ]);
  return formatMindforceImplant(row, effects, classIds, itemProps);
}

function register(app){
  /**
   * @swagger
   * /mindforceimplants:
   *  get:
   *    description: Get all Mindforce implants
   *    responses:
   *      '200':
   *        description: A list of Mindforce implants
   */
  app.get('/mindforceimplants', async (req,res) => { res.json(await withCache('/mindforce', ['MindforceImplants', 'EffectsOnEquip', 'ClassIds', 'ItemProperties'], getMindforceImplants)); });

  /**
   * @swagger
   * /mindforceimplants/{mindforceImplant}:
   *  get:
   *    description: Get a Mindforce implant by name or id
   *    parameters:
   *      - in: path
   *        name: mindforceImplant
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the Mindforce implant
   *    responses:
   *      '200':
   *        description: The Mindforce implant
   *      '404':
   *        description: Mindforce implant not found
   */
  app.get('/mindforceimplants/:mindforceImplant', async (req,res) => {
    const r = await withCachedLookup('/mindforce', ['MindforceImplants', 'EffectsOnEquip', 'ClassIds', 'ItemProperties'], getMindforceImplants, req.params.mindforceImplant);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getMindforceImplants, getMindforceImplant, formatMindforceImplant };

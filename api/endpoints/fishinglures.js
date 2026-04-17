const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { FishingLures: 'SELECT * FROM ONLY "FishingLures"' };

function formatFishingLure(x, data) {
  const itemId = x.Id + idOffsets.FishingLures;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      LureType: x.LureType ?? null,
      Depth: x.Depth !== null ? Number(x.Depth) : null,
      Quality: x.Quality !== null ? Number(x.Quality) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Links: { "$Url": `/fishinglures/${x.Id}` }
  };
}

async function getFishingLures() {
  const { rows } = await pool.query(queries.FishingLures);
  const itemIds = rows.map(r => r.Id + idOffsets.FishingLures);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('FishingLure', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  return rows.map(r => formatFishingLure(r, { ClassIds: classIds, ItemProps: itemProps }));
}

async function getFishingLure(idOrName) {
  const row = await getObjectByIdOrName(queries.FishingLures, 'FishingLures', idOrName);
  if (!row) return null;
  const itemId = row.Id + idOffsets.FishingLures;
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('FishingLure', [row.Id]),
    loadItemProperties([itemId])
  ]);
  return formatFishingLure(row, { ClassIds: classIds, ItemProps: itemProps });
}

function register(app) {
  app.get('/fishinglures', async (req, res) => {
    res.json(await withCache('/fishinglures', ['FishingLures', 'ClassIds', 'ItemProperties'], getFishingLures));
  });
  app.get('/fishinglures/:fishingLure', async (req, res) => {
    const r = await withCachedLookup('/fishinglures', ['FishingLures', 'ClassIds', 'ItemProperties'], getFishingLures, req.params.fishingLure);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getFishingLures, getFishingLure, formatFishingLure };

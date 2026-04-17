const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { FishingBlanks: 'SELECT * FROM ONLY "FishingBlanks"' };

function formatFishingBlank(x, data) {
  const itemId = x.Id + idOffsets.FishingBlanks;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      RodCategory: x.RodCategory ?? 'Regular',
      Strength: x.Strength !== null ? Number(x.Strength) : null,
      Flexibility: x.Flexibility !== null ? Number(x.Flexibility) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Links: { "$Url": `/fishingblanks/${x.Id}` }
  };
}

async function getFishingBlanks() {
  const { rows } = await pool.query(queries.FishingBlanks);
  const itemIds = rows.map(r => r.Id + idOffsets.FishingBlanks);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('FishingBlank', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  return rows.map(r => formatFishingBlank(r, { ClassIds: classIds, ItemProps: itemProps }));
}

async function getFishingBlank(idOrName) {
  const row = await getObjectByIdOrName(queries.FishingBlanks, 'FishingBlanks', idOrName);
  if (!row) return null;
  const itemId = row.Id + idOffsets.FishingBlanks;
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('FishingBlank', [row.Id]),
    loadItemProperties([itemId])
  ]);
  return formatFishingBlank(row, { ClassIds: classIds, ItemProps: itemProps });
}

function register(app) {
  app.get('/fishingblanks', async (req, res) => {
    res.json(await withCache('/fishingblanks', ['FishingBlanks', 'ClassIds', 'ItemProperties'], getFishingBlanks));
  });
  app.get('/fishingblanks/:fishingBlank', async (req, res) => {
    const r = await withCachedLookup('/fishingblanks', ['FishingBlanks', 'ClassIds', 'ItemProperties'], getFishingBlanks, req.params.fishingBlank);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getFishingBlanks, getFishingBlank, formatFishingBlank };

const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { FishingReels: 'SELECT * FROM ONLY "FishingReels"' };

function formatFishingReel(x, data) {
  const itemId = x.Id + idOffsets.FishingReels;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Strength: x.Strength !== null ? Number(x.Strength) : null,
      Speed: x.Speed !== null ? Number(x.Speed) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Links: { "$Url": `/fishingreels/${x.Id}` }
  };
}

async function getFishingReels() {
  const { rows } = await pool.query(queries.FishingReels);
  const itemIds = rows.map(r => r.Id + idOffsets.FishingReels);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('FishingReel', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  return rows.map(r => formatFishingReel(r, { ClassIds: classIds, ItemProps: itemProps }));
}

async function getFishingReel(idOrName) {
  const row = await getObjectByIdOrName(queries.FishingReels, 'FishingReels', idOrName);
  if (!row) return null;
  const itemId = row.Id + idOffsets.FishingReels;
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('FishingReel', [row.Id]),
    loadItemProperties([itemId])
  ]);
  return formatFishingReel(row, { ClassIds: classIds, ItemProps: itemProps });
}

function register(app) {
  app.get('/fishingreels', async (req, res) => {
    res.json(await withCache('/fishingreels', ['FishingReels', 'ClassIds', 'ItemProperties'], getFishingReels));
  });
  app.get('/fishingreels/:fishingReel', async (req, res) => {
    const r = await withCachedLookup('/fishingreels', ['FishingReels', 'ClassIds', 'ItemProperties'], getFishingReels, req.params.fishingReel);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getFishingReels, getFishingReel, formatFishingReel };

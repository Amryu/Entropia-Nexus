const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { FishingLines: 'SELECT * FROM ONLY "FishingLines"' };

function formatFishingLine(x, data) {
  const itemId = x.Id + idOffsets.FishingLines;
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
      Flexibility: x.Flexibility !== null ? Number(x.Flexibility) : null,
      Strength: x.Strength !== null ? Number(x.Strength) : null,
      Length: x.Length !== null ? Number(x.Length) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Links: { "$Url": `/fishinglines/${x.Id}` }
  };
}

async function getFishingLines() {
  const { rows } = await pool.query(queries.FishingLines);
  const itemIds = rows.map(r => r.Id + idOffsets.FishingLines);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('FishingLine', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  return rows.map(r => formatFishingLine(r, { ClassIds: classIds, ItemProps: itemProps }));
}

async function getFishingLine(idOrName) {
  const row = await getObjectByIdOrName(queries.FishingLines, 'FishingLines', idOrName);
  if (!row) return null;
  const itemId = row.Id + idOffsets.FishingLines;
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('FishingLine', [row.Id]),
    loadItemProperties([itemId])
  ]);
  return formatFishingLine(row, { ClassIds: classIds, ItemProps: itemProps });
}

function register(app) {
  app.get('/fishinglines', async (req, res) => {
    res.json(await withCache('/fishinglines', ['FishingLines', 'ClassIds', 'ItemProperties'], getFishingLines));
  });
  app.get('/fishinglines/:fishingLine', async (req, res) => {
    const r = await withCachedLookup('/fishinglines', ['FishingLines', 'ClassIds', 'ItemProperties'], getFishingLines, req.params.fishingLine);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getFishingLines, getFishingLine, formatFishingLine };

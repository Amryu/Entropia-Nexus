const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { Refiners: 'SELECT * FROM ONLY "Refiners"' };

function formatRefiner(x, data){
  const itemId = x.Id + idOffsets.Refiners;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Links: { "$Url": `/refiners/${x.Id}` },
  };
}

async function getRefiners() {
  const { rows } = await pool.query(queries.Refiners);
  const itemIds = rows.map(r => r.Id + idOffsets.Refiners);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('Refiner', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  const data = { ClassIds: classIds, ItemProps: itemProps };
  return rows.map(r => formatRefiner(r, data));
}
const getRefiner = async (idOrName) => { const row = await getObjectByIdOrName(queries.Refiners, 'Refiners', idOrName); if (!row) return null; const itemId = row.Id + idOffsets.Refiners; const [classIds, itemProps] = await Promise.all([loadClassIds('Refiner', [row.Id]), loadItemProperties([itemId])]); const data = { ClassIds: classIds, ItemProps: itemProps }; return formatRefiner(row, data); };

function register(app){
  /**
   * @swagger
   * /refiners:
   *  get:
   *    description: Get all refiners
   *    responses:
   *      '200':
   *        description: A list of refiners
   */
  app.get('/refiners', async (req,res) => {
    res.json(await withCache('/refiners', ['Refiners', 'ClassIds', 'ItemProperties'], getRefiners));
  });
  /**
   * @swagger
   * /refiners/{refiner}:
   *  get:
   *    description: Get a refiner by name or id
   *    parameters:
   *      - in: path
   *        name: refiner
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the refiner
   *    responses:
   *      '200':
   *        description: The refiner
   *      '404':
   *        description: Refiner not found
   */
  app.get('/refiners/:refiner', async (req,res) => {
    const r = await withCachedLookup('/refiners', ['Refiners', 'ClassIds', 'ItemProperties'], getRefiners, req.params.refiner);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getRefiners, getRefiner, formatRefiner };

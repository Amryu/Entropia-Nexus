const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { Absorbers: 'SELECT * FROM ONLY "Absorbers"' };

function formatAbsorber(x, data) {
  const itemId = x.Id + idOffsets.Absorbers;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: {
        Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Absorption: x.Absorption !== null ? Number(x.Absorption) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Links: { "$Url": `/absorbers/${x.Id}` }
  };
}

async function getAbsorbers() {
  const { rows } = await pool.query(queries.Absorbers);
  const itemIds = rows.map(r => r.Id + idOffsets.Absorbers);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('Absorber', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  const data = { ClassIds: classIds, ItemProps: itemProps };
  return rows.map(r => formatAbsorber(r, data));
}
const getAbsorber = async(idOrName) => { const row = await getObjectByIdOrName(queries.Absorbers,'Absorbers',idOrName); if (!row) return null; const itemId = row.Id + idOffsets.Absorbers; const [classIds, itemProps] = await Promise.all([loadClassIds('Absorber', [row.Id]), loadItemProperties([itemId])]); const data = { ClassIds: classIds, ItemProps: itemProps }; return formatAbsorber(row, data); };

function register(app){
  /**
   * @swagger
   * /absorbers:
   *  get:
   *    description: Get all absorbers
   *    responses:
   *      '200':
   *        description: A list of absorbers
   */
  app.get('/absorbers', async (req,res)=>{ res.json(await withCache('/absorbers', ['Absorbers', 'ClassIds', 'ItemProperties'], getAbsorbers)); });
  /**
   * @swagger
   * /absorbers/{absorber}:
   *  get:
   *    description: Get an absorber by name or id
   *    parameters:
   *      - in: path
   *        name: absorber
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the absorber
   *    responses:
   *      '200':
   *        description: The absorber
   *      '404':
   *        description: Absorber not found
   */
  app.get('/absorbers/:absorber', async (req,res)=>{ const r = await withCachedLookup('/absorbers', ['Absorbers', 'ClassIds', 'ItemProperties'], getAbsorbers, req.params.absorber); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getAbsorbers, getAbsorber, formatAbsorber };

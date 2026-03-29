const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Decorations: 'SELECT * FROM ONLY "Decorations"',
};

function formatDecoration(x, data){
  const itemId = x.Id + idOffsets.Decorations;
  const props = data.ItemProps[itemId];
  return { Id: x.Id, ClassId: data.ClassIds[x.Id] || null, ItemId: itemId, Name: x.Name, Properties: { Description: x.Description, Weight: x.Weight !== null ? Number(x.Weight) : null, Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null }, IsUntradeable: props?.IsUntradeable || false, IsRare: props?.IsRare || false }, Links: { "$Url": `/decorations/${x.Id}` } };
}

async function getDecorations(){ const { rows } = await pool.query(queries.Decorations); const itemIds = rows.map(r => r.Id + idOffsets.Decorations); const [classIds, itemProps] = await Promise.all([loadClassIds('Decoration', rows.map(r => r.Id)), loadItemProperties(itemIds)]); const data = { ClassIds: classIds, ItemProps: itemProps }; return rows.map(r => formatDecoration(r, data)); }
async function getDecoration(idOrName){ const row = await getObjectByIdOrName(queries.Decorations, 'Decorations', idOrName); if (!row) return null; const itemId = row.Id + idOffsets.Decorations; const [classIds, itemProps] = await Promise.all([loadClassIds('Decoration', [row.Id]), loadItemProperties([itemId])]); const data = { ClassIds: classIds, ItemProps: itemProps }; return formatDecoration(row, data); }

function register(app){
  /**
   * @swagger
   * /decorations:
   *  get:
   *    description: Get all decorations
   *    responses:
   *      '200':
   *        description: A list of decorations
   */
  app.get('/decorations', async (req,res) => { res.json(await withCache('/decorations', ['Decorations', 'ClassIds', 'ItemProperties'], getDecorations)); });
  /**
   * @swagger
   * /decorations/{decoration}:
   *  get:
   *    description: Get a decoration by name or id
   *    parameters:
   *      - in: path
   *        name: decoration
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the decoration
   *    responses:
   *      '200':
   *        description: The decoration
   *      '404':
   *        description: Decoration not found
   */
  app.get('/decorations/:decoration', async (req,res) => { const r = await withCachedLookup('/decorations', ['Decorations', 'ClassIds', 'ItemProperties'], getDecorations, req.params.decoration); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getDecorations, getDecoration, formatDecoration };

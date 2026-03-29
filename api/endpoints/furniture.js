const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Furniture: 'SELECT f.*, p."Name" AS "Planet" FROM ONLY "Furniture" f LEFT JOIN ONLY "Planets" p ON f."PlanetId" = p."Id"',
};

function formatFurniture(x, data){
  const itemId = x.Id + idOffsets.Furniture;
  const props = data.ItemProps[itemId];
  return { Id: x.Id, ClassId: data.ClassIds[x.Id] || null, ItemId: itemId, Name: x.Name, Properties: { Description: x.Description, Weight: x.Weight !== null ? Number(x.Weight) : null, Type: x.Type, Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null }, IsUntradeable: props?.IsUntradeable || false, IsRare: props?.IsRare || false }, Planet: { Name: x.Planet, Links: { "$Url": `/planets/${x.PlanetId}` } }, Links: { "$Url": `/furniture/${x.Id}` } };
}

async function getFurnitures(){ const { rows } = await pool.query(queries.Furniture); const itemIds = rows.map(r => r.Id + idOffsets.Furniture); const [classIds, itemProps] = await Promise.all([loadClassIds('Furniture', rows.map(r => r.Id)), loadItemProperties(itemIds)]); const data = { ClassIds: classIds, ItemProps: itemProps }; return rows.map(r => formatFurniture(r, data)); }
async function getFurniture(idOrName){ const row = await getObjectByIdOrName(queries.Furniture, 'Furniture', idOrName); if (!row) return null; const itemId = row.Id + idOffsets.Furniture; const [classIds, itemProps] = await Promise.all([loadClassIds('Furniture', [row.Id]), loadItemProperties([itemId])]); const data = { ClassIds: classIds, ItemProps: itemProps }; return formatFurniture(row, data); }

function register(app){
  /**
   * @swagger
   * /furniture:
   *  get:
   *    description: Get all furniture
   *    responses:
   *      '200':
   *        description: A list of furniture
   */
  app.get('/furniture', async (req,res) => { res.json(await withCache('/furniture', ['Furniture', 'ClassIds', 'ItemProperties'], getFurnitures)); });
  /**
   * @swagger
   * /furniture/{furniture}:
   *  get:
   *    description: Get a furniture by name or id
   *    parameters:
   *      - in: path
   *        name: furniture
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the furniture
   *    responses:
   *      '200':
   *        description: The furniture
   *      '404':
   *        description: Furniture not found
   */
  app.get('/furniture/:furniture', async (req,res) => { const r = await withCachedLookup('/furniture', ['Furniture', 'ClassIds', 'ItemProperties'], getFurnitures, req.params.furniture); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getFurnitures, getFurniture, formatFurniture };

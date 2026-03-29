const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Scanners: 'SELECT * FROM ONLY "Scanners"',
};

function formatScanner(x, data){
  const itemId = x.Id + idOffsets.Scanners;
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
      Range: x.Range !== null ? Number(x.Range) : null,
      Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null, MinTT: x.MinTT !== null ? Number(x.MinTT) : null, Decay: x.Decay !== null ? Number(x.Decay) : null },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Links: { "$Url": `/scanners/${x.Id}` }
  };
}

async function getScanners(){ const { rows } = await pool.query(queries.Scanners); const itemIds = rows.map(r => r.Id + idOffsets.Scanners); const [classIds, itemProps] = await Promise.all([loadClassIds('Scanner', rows.map(r => r.Id)), loadItemProperties(itemIds)]); const data = { ClassIds: classIds, ItemProps: itemProps }; return rows.map(r => formatScanner(r, data)); }
async function getScanner(idOrName){ const row = await getObjectByIdOrName(queries.Scanners, 'Scanners', idOrName); if (!row) return null; const itemId = row.Id + idOffsets.Scanners; const [classIds, itemProps] = await Promise.all([loadClassIds('Scanner', [row.Id]), loadItemProperties([itemId])]); const data = { ClassIds: classIds, ItemProps: itemProps }; return formatScanner(row, data); }

function register(app){
  /**
   * @swagger
   * /scanners:
   *  get:
   *    description: Get all scanners
   *    responses:
   *      '200':
   *        description: A list of scanners
   */
  app.get('/scanners', async (req,res) => { res.json(await withCache('/scanners', ['Scanners', 'ClassIds', 'ItemProperties'], getScanners)); });
  /**
   * @swagger
   * /scanners/{scanner}:
   *  get:
   *    description: Get a scanner by name or id
   *    parameters:
   *      - in: path
   *        name: scanner
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the scanner
   *    responses:
   *      '200':
   *        description: The scanner
   *      '404':
   *        description: Scanner not found
   */
  app.get('/scanners/:scanner', async (req,res) => { const r = await withCachedLookup('/scanners', ['Scanners', 'ClassIds', 'ItemProperties'], getScanners, req.params.scanner); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getScanners, getScanner, formatScanner };

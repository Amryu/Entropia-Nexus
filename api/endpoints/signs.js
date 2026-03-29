const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { Signs: 'SELECT * FROM ONLY "Signs"' };

function formatSign(x, data){
  const itemId = x.Id + idOffsets.Signs;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight != null ? Number(x.Weight) : null,
      ItemPoints: x.ItemPoints != null ? Number(x.ItemPoints) : null,
      Display: {
        AspectRatio: x.AspectRatio,
        CanShowLocalContentScreen: x.LocalContentScreen === 1,
        CanShowImagesAndText: x.ImagesAndText === 1,
        CanShowEffects: x.Effects === 1,
        CanShowMultimedia: x.Multimedia === 1,
        CanShowParticipantContent: x.ParticipantContent === 1,
      },
      Economy: { MaxTT: x.MaxTT != null ? Number(x.MaxTT) : null, Cost: x.Cost != null ? Number(x.Cost) : null },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Links: { "$Url": `/signs/${x.Id}` },
  };
}

async function getSigns() {
  const { rows } = await pool.query(queries.Signs);
  const itemIds = rows.map(r => r.Id + idOffsets.Signs);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('Sign', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  const data = { ClassIds: classIds, ItemProps: itemProps };
  return rows.map(r => formatSign(r, data));
}
const getSign = async(idOrName) => { const row = await getObjectByIdOrName(queries.Signs,'Signs',idOrName); if (!row) return null; const itemId = row.Id + idOffsets.Signs; const [classIds, itemProps] = await Promise.all([loadClassIds('Sign', [row.Id]), loadItemProperties([itemId])]); const data = { ClassIds: classIds, ItemProps: itemProps }; return formatSign(row, data); };

function register(app){
  /**
   * @swagger
   * /signs:
   *  get:
   *    description: Get all signs
   *    responses:
   *      '200':
   *        description: A list of signs
   */
  app.get('/signs', async (req,res)=>{ res.json(await withCache('/signs', ['Signs', 'ClassIds', 'ItemProperties'], getSigns)); });
  /**
   * @swagger
   * /signs/{sign}:
   *  get:
   *    description: Get a sign by name or id
   *    parameters:
   *      - in: path
   *        name: sign
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the sign
   *    responses:
   *      '200':
   *        description: The sign
   *      '404':
   *        description: Sign not found
   */
  app.get('/signs/:sign', async (req,res)=>{ const r = await withCachedLookup('/signs', ['Signs', 'ClassIds', 'ItemProperties'], getSigns, req.params.sign); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getSigns, getSign, formatSign };

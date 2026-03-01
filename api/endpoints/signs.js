const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { Signs: 'SELECT * FROM ONLY "Signs"' };

function formatSign(x, classIds){
  return {
    Id: x.Id,
    ClassId: classIds[x.Id] || null,
    ItemId: x.Id + idOffsets.Signs,
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
    },
    Links: { "$Url": `/signs/${x.Id}` },
  };
}

async function getSigns() {
  const { rows } = await pool.query(queries.Signs);
  const classIds = await loadClassIds('Sign', rows.map(r => r.Id));
  return rows.map(r => formatSign(r, classIds));
}
const getSign = async(idOrName) => { const row = await getObjectByIdOrName(queries.Signs,'Signs',idOrName); if (!row) return null; const classIds = await loadClassIds('Sign', [row.Id]); return formatSign(row, classIds); };

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
  app.get('/signs', async (req,res)=>{ res.json(await withCache('/signs', ['Signs', 'ClassIds'], getSigns)); });
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
  app.get('/signs/:sign', async (req,res)=>{ const r = await withCachedLookup('/signs', ['Signs', 'ClassIds'], getSigns, req.params.sign); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getSigns, getSign, formatSign };

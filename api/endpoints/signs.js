const { getObjects, getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');

const queries = { Signs: 'SELECT * FROM ONLY "Signs"' };

function formatSign(x){
  return {
    Id: x.Id,
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

const getSigns = () => getObjects(queries.Signs, formatSign);
const getSign = async(idOrName) => { const row = await getObjectByIdOrName(queries.Signs,'Signs',idOrName); return row ? formatSign(row) : null; };

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
  app.get('/signs', async (req,res)=>{ res.json(await getSigns()); });
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
  app.get('/signs/:sign', async (req,res)=>{ const r = await getSign(req.params.sign); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getSigns, getSign };

const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');
const { loadEffectsOnEquipByItemIds } = require('./effects-utils');

const queries = {
  FinderAmplifiers: 'SELECT * FROM ONLY "FinderAmplifiers"',
};

function formatFinderAmplifier(x, effectsMap){
  const itemId = x.Id + idOffsets.FinderAmplifiers;
  const effects = effectsMap[itemId] ?? [];
  return {
    Id: x.Id,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
      MinProfessionLevel: x.ProfessionMinimum !== null ? Number(x.ProfessionMinimum) : null,
      Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null, MinTT: x.MinTT !== null ? Number(x.MinTT) : null, Decay: x.Decay !== null ? Number(x.Decay) : null }
    },
    EffectsOnEquip: effects,
    Links: { "$Url": `/finderamplifiers/${x.Id}` }
  };
}

async function _getEffectsOnEquip(ids){
  if (!ids.length) return {};
  const itemIds = ids.map(id => id + idOffsets.FinderAmplifiers);
  return await loadEffectsOnEquipByItemIds(itemIds);
}

async function getFinderAmplifiers(){
  const { rows } = await pool.query(queries.FinderAmplifiers);
  const effects = await _getEffectsOnEquip(rows.map(r=>r.Id));
  return rows.map(r => formatFinderAmplifier(r, effects));
}

async function getFinderAmplifier(idOrName){
  const row = await getObjectByIdOrName(queries.FinderAmplifiers, 'FinderAmplifiers', idOrName);
  if (!row) return null;
  const effects = await _getEffectsOnEquip([row.Id]);
  return formatFinderAmplifier(row, effects);
}

function register(app){
  /**
   * @swagger
   * /finderamplifiers:
   *  get:
   *    description: Get all finders
   *    responses:
   *      '200':
   *        description: A list of finders
   */
  app.get('/finderamplifiers', async (req,res) => { res.json(await getFinderAmplifiers()); });
  /**
   * @swagger
   * /finderamplifiers/{finderAmplifier}:
   *  get:
   *    description: Get a finder amplifier by name or id
   *    parameters:
   *      - in: path
   *        name: finderAmplifier
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the finder amplifier
   *    responses:
   *      '200':
   *        description: The finder amplifier
   *      '404':
   *        description: Finder amplifier not found
   */
  app.get('/finderamplifiers/:finderAmplifier', async (req,res) => { const r = await getFinderAmplifier(req.params.finderAmplifier); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getFinderAmplifiers, getFinderAmplifier, formatFinderAmplifier };

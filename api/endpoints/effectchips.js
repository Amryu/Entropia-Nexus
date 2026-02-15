const { pool } = require('./dbClient');
const pgp = require('pg-promise')();
const { idOffsets } = require('./constants');
const { getObjectByIdOrName } = require('./utils');
const { loadEffectsOnUseByItemIds } = require('./effects-utils');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  EffectChips:
    'SELECT "EffectChips".*,\
            "Professions"."Name" AS "Profession",\
            "Materials"."Name" AS "Ammo"\
       FROM ONLY "EffectChips"\
  LEFT JOIN ONLY "Professions" ON "EffectChips"."ProfessionId" = "Professions"."Id"\
  LEFT JOIN ONLY "Materials"   ON "EffectChips"."AmmoId" = "Materials"."Id"',
  // EffectsOnUse loaded via shared helper
};

function formatEffectChip(x, effectsMap){
  const itemId = x.Id + idOffsets.EffectChips;
  const effects = effectsMap[itemId] ?? [];
  return {
    Id: x.Id,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Range: x.Range !== null ? Number(x.Range) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Mindforce: {
        Level: x.Level !== null ? Number(x.Level) : null,
        Concentration: x.Concentration !== null ? Number(x.Concentration) : null,
        Cooldown: null,
        CooldownGroup: x.CooldownGroup !== null ? Number(x.CooldownGroup) : null,
      },
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
        AmmoBurn: x.AmmoBurn !== null ? Number(x.AmmoBurn) : null,
      },
      Skill: {
        LearningIntervalStart: (x.MinLevel ?? x.MinLvl) !== null ? Number(x.MinLevel ?? x.MinLvl) : null,
        LearningIntervalEnd: (x.MaxLevel ?? x.MaxLvl) !== null ? Number(x.MaxLevel ?? x.MaxLvl) : null,
        IsSiB: (x.IsSib === 1) || (x.SiB === 1)
      }
    },
    Ammo: x.AmmoId ? { Name: x.Ammo, Links: { "$Url": `/materials/${x.AmmoId}` } } : null,
    Profession: x.ProfessionId ? { Name: x.Profession, Links: { "$Url": `/professions/${x.ProfessionId}` } } : null,
    EffectsOnUse: effects,
    Links: { "$Url": `/effectchips/${x.Id}` }
  };
}

async function getEffectChips(){
  const { rows } = await pool.query(queries.EffectChips);
  const itemIds = rows.map(r => r.Id + idOffsets.EffectChips);
  const effects = await loadEffectsOnUseByItemIds(itemIds);
  return rows.map(r => formatEffectChip(r, effects));
}

async function getEffectChip(idOrName){
  const row = await getObjectByIdOrName(queries.EffectChips, 'EffectChips', idOrName);
  if (!row) return null;
  const itemIds = [row.Id + idOffsets.EffectChips];
  const effects = await loadEffectsOnUseByItemIds(itemIds);
  return formatEffectChip(row, effects);
}

function register(app){
  /**
   * @swagger
   * /effectchips:
   *  get:
   *    description: Get all effect chips
   *    responses:
   *      '200':
   *        description: A list of effect chips
   */
  app.get('/effectchips', async (req,res) => { res.json(await withCache('/effectchips', ['EffectChips', 'Professions', 'Materials', 'EffectsOnUse', 'Effects'], getEffectChips)); });
  /**
   * @swagger
   * /effectchips/{effectChip}:
   *  get:
   *    description: Get an effect chip by name or id
   *    parameters:
   *      - in: path
   *        name: effectChip
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the effect chip
   *    responses:
   *      '200':
   *        description: The effect chip
   *      '404':
   *        description: Effect chip not found
   */
  app.get('/effectchips/:effectChip', async (req,res) => { const r = await withCachedLookup('/effectchips', ['EffectChips', 'Professions', 'Materials', 'EffectsOnUse', 'Effects'], getEffectChips, req.params.effectChip); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getEffectChips, getEffectChip, formatEffectChip };

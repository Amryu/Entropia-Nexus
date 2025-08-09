const pgp = require('pg-promise')();
const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');

const ID_OFFSET = 4500000;

const queries = {
  Finders: 'SELECT * FROM ONLY "Finders"',
  EffectsOnEquip: `SELECT e."Id", e."Name", e."Unit", e."Description", eo."Strength", eo."ItemId"
                   FROM ONLY "EffectsOnEquip" eo
                   INNER JOIN ONLY "Effects" e ON eo."EffectId" = e."Id"
                   WHERE eo."ItemId" IN ($1:csv)`,
  Tiers: `SELECT t."Tier", t."ItemId", t."IsArmorSet", i."Name" AS "ItemName", tm.*, m."Name" AS "MaterialName", m."Value" AS "Value", m."Weight" AS "Weight", m."Type" AS "Type"
          FROM ONLY "Tiers" t
          INNER JOIN ONLY "TierMaterials" tm ON t."Id" = tm."TierId"
          INNER JOIN ONLY "Materials" m ON tm."MaterialId" = m."Id"
          INNER JOIN ONLY "Items" i ON t."ItemId" = i."Id"
          WHERE t."ItemId" IN ($1:csv) AND t."IsArmorSet" = 0`,
};

function formatEffectOnEquip(x){
  return { Name: x.Name, Values: { Strength: x.Strength !== null ? Number(x.Strength) : null, Unit: x.Unit, Description: x.Description }, Links: { "$Url": `/effects/${x.Id}` } };
}

function formatTierMaterial(x){
  return { Amount: x.Amount !== null ? Number(x.Amount) : null, Material: { Name: x.MaterialName, Properties: { Weight: x.Weight !== null ? Number(x.Weight) : null, Type: x.Type, Economy: { MaxTT: x.Value !== null ? Number(x.Value) : null } }, Links: { "$Url": `/materials/${x.MaterialId}` } } };
}

function formatTier(group){
  const tier = group[0];
  return { Name: `${tier.ItemName} Tier ${tier.Tier}`, Properties: { Tier: tier.Tier, IsArmorSet: tier.IsArmorSet === 1 }, Materials: group.map(formatTierMaterial), Links: { "$Url": `/tiers?ItemId=${tier.ItemId}&IsArmorSet=${tier.IsArmorSet}&Tier=${tier.Tier}` } };
}

async function _getEffectsOnEquip(ids){
  if (!ids.length) return {};
  const { rows } = await pool.query(pgp.as.format(queries.EffectsOnEquip, [ids.map(id => id + ID_OFFSET)]));
  return rows.reduce((acc,r)=>{ (acc[r.ItemId] ||= []).push(r); return acc; },{});
}

async function _getTiers(ids){
  if (!ids.length) return {};
  const itemIds = ids.map(id => id + ID_OFFSET);
  const { rows } = await pool.query(pgp.as.format(queries.Tiers, [itemIds]));
  const byItem = rows.reduce((acc,r)=>{ (acc[r.ItemId] ||= []); acc[r.ItemId].push(r); return acc; },{});
  // group by tier number per item
  const grouped = {};
  for (const [itemId, list] of Object.entries(byItem)){
    const byTier = list.reduce((a,r)=>{ (a[r.Tier] ||= []); a[r.Tier].push(r); return a; },{});
    grouped[itemId] = Object.values(byTier).map(formatTier);
  }
  return grouped;
}

function formatFinder(x, effectsMap, tiersMap){
  const itemId = x.Id + ID_OFFSET;
  const effects = (effectsMap[itemId] ?? []).map(formatEffectOnEquip);
  const tiers = tiersMap[itemId] ?? [];
  return {
    Id: x.Id,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Depth: x.Depth !== null ? Number(x.Depth) : null,
      Range: x.Range !== null ? Number(x.Range) : null,
      Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null, MinTT: x.MinTT !== null ? Number(x.MinTT) : null, Decay: x.Decay !== null ? Number(x.Decay) : null, AmmoBurn: x.Probes !== null ? Number(x.Probes) : null },
      Skill: { LearningIntervalStart: x.IntervalStart !== null ? Number(x.IntervalStart) : null, LearningIntervalEnd: x.IntervalEnd !== null ? Number(x.IntervalEnd) : null, IsSiB: true }
    },
    EffectsOnEquip: effects,
    Tiers: tiers,
    Links: { "$Url": `/finders/${x.Id}` }
  };
}

async function getFinders(){
  const { rows } = await pool.query(queries.Finders);
  const [effects, tiers] = await Promise.all([_getEffectsOnEquip(rows.map(r=>r.Id)), _getTiers(rows.map(r=>r.Id))]);
  return rows.map(r => formatFinder(r, effects, tiers));
}

async function getFinder(idOrName){
  const row = await getObjectByIdOrName(queries.Finders, 'Finders', idOrName);
  if (!row) return null;
  const [effects, tiers] = await Promise.all([_getEffectsOnEquip([row.Id]), _getTiers([row.Id])]);
  return formatFinder(row, effects, tiers);
}

function register(app){
  /**
   * @swagger
   * /finders:
   *  get:
   *    description: Get all finders
   *    responses:
   *      '200':
   *        description: A list of finders
   */
  app.get('/finders', async (req,res) => { res.json(await getFinders()); });
  /**
   * @swagger
   * /finders/{finder}:
   *  get:
   *    description: Get a finder by name or id
   *    parameters:
   *      - in: path
   *        name: finder
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the finder
   *    responses:
   *      '200':
   *        description: The finder
   *      '404':
   *        description: Finder not found
   */
  app.get('/finders/:finder', async (req,res) => { const r = await getFinder(req.params.finder); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getFinders, getFinder };

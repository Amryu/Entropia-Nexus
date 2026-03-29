const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { pool } = require('./dbClient');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  TeleportationChips:
    'SELECT "TeleportationChips".*,\
            "Professions"."Name" AS "Profession",\
            "Materials"."Name" AS "Ammo",\
            "Materials"."Id" AS "AmmoId"\
       FROM ONLY "TeleportationChips"\
  LEFT JOIN ONLY "Professions" ON "TeleportationChips"."ProfessionId" = "Professions"."Id"\
  LEFT JOIN ONLY "Materials"   ON "TeleportationChips"."AmmoId" = "Materials"."Id"',
};

function formatTeleportationChip(x, data){
  const itemId = x.Id + idOffsets.TeleportationChips;
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
      Mindforce: {
        Level: x.Level !== null ? Number(x.Level) : null,
        Concentration: x.Concentration !== null ? Number(x.Concentration) : null,
        Cooldown: x.Cooldown !== null ? Number(x.Cooldown) : null,
        CooldownGroup: x.CooldownGroup !== null ? Number(x.CooldownGroup) : null,
      },
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
        AmmoBurn: x.AmmoBurn !== null ? Number(x.AmmoBurn) : null,
      },
      Skill: {
        LearningIntervalStart: (x.MinLvl ?? x.MinLevel) !== null ? Number(x.MinLvl ?? x.MinLevel) : null,
        LearningIntervalEnd: (x.MaxLvl ?? x.MaxLevel) !== null ? Number(x.MaxLvl ?? x.MaxLevel) : null,
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Ammo: {
      Name: x.Ammo,
      Links: { "$Url": `/materials/${x.AmmoId}` },
    },
    Profession: {
      Name: x.Profession,
      Links: { "$Url": `/professions/${x.ProfessionId}` },
    },
    Links: { "$Url": `/teleportationchips/${x.Id}` }
  };
}

async function getTeleportationChips(){
  const { rows } = await pool.query(queries.TeleportationChips);
  const itemIds = rows.map(r => r.Id + idOffsets.TeleportationChips);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('TeleportationChip', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  const data = { ClassIds: classIds, ItemProps: itemProps };
  return rows.map(r => formatTeleportationChip(r, data));
}

async function getTeleportationChip(idOrName){
  const row = await getObjectByIdOrName(queries.TeleportationChips, 'TeleportationChips', idOrName);
  if (!row) return null;
  const itemId = row.Id + idOffsets.TeleportationChips;
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('TeleportationChip', [row.Id]),
    loadItemProperties([itemId])
  ]);
  const data = { ClassIds: classIds, ItemProps: itemProps };
  return formatTeleportationChip(row, data);
}

function register(app){
  /**
   * @swagger
   * /teleportationchips:
   *  get:
   *    description: Get all teleportation chips
   *    responses:
   *      '200':
   *        description: A list of teleportation chips
   */
  app.get('/teleportationchips', async (req,res) => {
    res.json(await withCache('/teleportationchips', ['TeleportationChips', 'Professions', 'Materials', 'ClassIds', 'ItemProperties'], getTeleportationChips));
  });
  /**
   * @swagger
   * /teleportationchips/{teleportationChip}:
   *  get:
   *    description: Get a teleportation chip by name or id
   *    parameters:
   *      - in: path
   *        name: teleportationChip
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the teleportation chip
   *    responses:
   *      '200':
   *        description: The teleportation chip
   *      '404':
   *        description: Teleportation chip not found
   */
  app.get('/teleportationchips/:teleportationChip', async (req,res) => {
    const r = await withCachedLookup('/teleportationchips', ['TeleportationChips', 'Professions', 'Materials', 'ClassIds', 'ItemProperties'], getTeleportationChips, req.params.teleportationChip);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getTeleportationChips, getTeleportationChip, formatTeleportationChip };

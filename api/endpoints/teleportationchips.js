const { getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');
const { pool } = require('./dbClient');

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

function formatTeleportationChip(x){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.TeleportationChips,
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
      }
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
  return rows.map(formatTeleportationChip);
}

async function getTeleportationChip(idOrName){
  const row = await getObjectByIdOrName(queries.TeleportationChips, 'TeleportationChips', idOrName);
  return row ? formatTeleportationChip(row) : null;
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
    res.json(await getTeleportationChips());
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
    const r = await getTeleportationChip(req.params.teleportationChip);
    if (r) res.json(r); else res.status(404).send();
  });
}

module.exports = { register, getTeleportationChips, getTeleportationChip, formatTeleportationChip };

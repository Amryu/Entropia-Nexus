const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');

const queries = {
  Capsules: 'SELECT cc.*, p."Name" AS "Profession", m."Name" AS "Mob" FROM ONLY "CreatureControlCapsules" cc LEFT JOIN ONLY "Professions" p ON cc."ScanningProfessionId" = p."Id" LEFT JOIN ONLY "Mobs" m ON cc."MobId" = m."Id"',
};

function formatCapsule(x){
  return {
    Id: x.Id,
  ItemId: x.Id + idOffsets.Capsules,
    Name: x.Name,
    Properties: { Description: x.Description, Weight: x.Weight !== null ? Number(x.Weight) : null, MinProfessionLevel: x.ProfessionLevel !== null ? Number(x.ProfessionLevel) : null, Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null } },
    Profession: { Name: x.Profession, Links: { "$Url": `/professions/${x.ScanningProfessionId}` } },
    Mob: { Name: x.Mob, Links: { "$Url": `/mobs/${x.MobId}` } },
    Links: { "$Url": `/capsules/${x.Id}` }
  };
}

async function getCapsules(){ const { rows } = await pool.query(queries.Capsules); return rows.map(formatCapsule); }
async function getCapsule(idOrName){ const row = await getObjectByIdOrName(queries.Capsules, 'CreatureControlCapsules', idOrName); return row ? formatCapsule(row) : null; }

function register(app){
  /**
   * @swagger
   * /capsules:
   *  get:
   *    description: Get all creature control capsules
   *    responses:
   *      '200':
   *        description: A list of creature control capsules
   */
  app.get('/capsules', async (req,res) => { res.json(await getCapsules()); });
  /**
   * @swagger
   * /capsules/{capsule}:
   *  get:
   *    description: Get a creature control capsule by name or id
   *    parameters:
   *      - in: path
   *        name: capsule
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the creature control capsule
   *    responses:
   *      '200':
   *        description: The creature control capsule
   *      '404':
   *        description: Creature control capsule not found
   */
  app.get('/capsules/:capsule', async (req,res) => { const r = await getCapsule(req.params.capsule); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getCapsules, getCapsule };

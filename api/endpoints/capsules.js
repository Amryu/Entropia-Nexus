const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Capsules: 'SELECT cc.*, p."Name" AS "Profession", m."Name" AS "Mob" FROM ONLY "CreatureControlCapsules" cc LEFT JOIN ONLY "Professions" p ON cc."ScanningProfessionId" = p."Id" LEFT JOIN ONLY "Mobs" m ON cc."MobId" = m."Id"',
};

function formatCapsule(x, data){
  const itemId = x.Id + idOffsets.Capsules;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: { Description: x.Description, Weight: x.Weight !== null ? Number(x.Weight) : null, MinProfessionLevel: x.ProfessionLevel !== null ? Number(x.ProfessionLevel) : null, Economy: { MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null }, IsUntradeable: props?.IsUntradeable || false, IsRare: props?.IsRare || false },
    Profession: { Name: x.Profession, Links: { "$Url": `/professions/${x.ScanningProfessionId}` } },
    Mob: { Name: x.Mob, Links: { "$Url": `/mobs/${x.MobId}` } },
    Links: { "$Url": `/capsules/${x.Id}` }
  };
}

async function getCapsules(){ const { rows } = await pool.query(queries.Capsules); const itemIds = rows.map(r => r.Id + idOffsets.Capsules); const [classIds, itemProps] = await Promise.all([loadClassIds('Capsule', rows.map(r => r.Id)), loadItemProperties(itemIds)]); const data = { ClassIds: classIds, ItemProps: itemProps }; return rows.map(r => formatCapsule(r, data)); }
async function getCapsule(idOrName){ const row = await getObjectByIdOrName(queries.Capsules, 'CreatureControlCapsules', idOrName); if (!row) return null; const itemId = row.Id + idOffsets.Capsules; const [classIds, itemProps] = await Promise.all([loadClassIds('Capsule', [row.Id]), loadItemProperties([itemId])]); const data = { ClassIds: classIds, ItemProps: itemProps }; return formatCapsule(row, data); }

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
  app.get('/capsules', async (req,res) => { res.json(await withCache('/capsules', ['Capsules', 'ClassIds', 'ItemProperties'], getCapsules)); });
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
  app.get('/capsules/:capsule', async (req,res) => { const r = await withCachedLookup('/capsules', ['Capsules', 'ClassIds', 'ItemProperties'], getCapsules, req.params.capsule); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getCapsules, getCapsule, formatCapsule };

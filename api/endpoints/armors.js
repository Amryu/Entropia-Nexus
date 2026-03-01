const { pool } = require('./dbClient');
const { getObjectByIdOrName, generateGenderAliases, loadClassIds } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Armors: 'SELECT "Armors"."Id", "Armors"."Name", "Armors"."Description", "ArmorSets"."Name" AS "Set", "Gender", "Slot", "SetId", "Weight", "MaxTT", "MinTT", "Durability", "Stab", "Cut", "Impact", "Penetration", "Shrapnel", "Burn", "Cold", "Acid", "Electric" FROM ONLY "Armors" LEFT JOIN ONLY "ArmorSets" ON "Armors"."SetId" = "ArmorSets"."Id"',
};

function toNumberOrNull(v) {
  return v === null || v === undefined ? null : Number(v);
}

function formatArmor(x, classIds){
  const aliases = generateGenderAliases(x.Name, x.Gender);
  return {
    Id: x.Id,
    ClassId: classIds[x.Id] || null,
    ItemId: x.Id + idOffsets.Armors,
    Name: x.Name,
    Aliases: aliases.length > 0 ? aliases : undefined,
    Properties: {
      Description: x.Description,
      Weight: toNumberOrNull(x.Weight),
      Gender: x.Gender,
      Slot: x.Slot,
      Economy: {
        MaxTT: toNumberOrNull(x.MaxTT),
        MinTT: toNumberOrNull(x.MinTT),
        Durability: toNumberOrNull(x.Durability),
      },
      Defense: {
        Stab: toNumberOrNull(x.Stab),
        Cut: toNumberOrNull(x.Cut),
        Impact: toNumberOrNull(x.Impact),
        Penetration: toNumberOrNull(x.Penetration),
        Shrapnel: toNumberOrNull(x.Shrapnel),
        Burn: toNumberOrNull(x.Burn),
        Cold: toNumberOrNull(x.Cold),
        Acid: toNumberOrNull(x.Acid),
        Electric: toNumberOrNull(x.Electric),
      },
    },
    Set: { Name: x.Set, Links: { "$Url": `/armorsets/${x.SetId}` } },
    Links: { "$Url": `/armors/${x.Id}` },
  };
}

async function getArmors() {
  const { rows } = await pool.query(queries.Armors);
  const classIds = await loadClassIds('Armor', rows.map(r => r.Id));
  return rows.map(r => formatArmor(r, classIds));
}
const getArmor = async (idOrName) => { const row = await getObjectByIdOrName(queries.Armors, 'Armors', idOrName); if (!row) return null; const classIds = await loadClassIds('Armor', [row.Id]); return formatArmor(row, classIds); };

function register(app){
  /**
   * @swagger
   * /armors:
   *  get:
   *    description: Get all armors
   *    responses:
   *      '200':
   *        description: A list of armors
   */
  app.get('/armors', async (req,res) => { res.json(await withCache('/armors', ['Armors', 'ArmorSets', 'ClassIds'], getArmors)); });
  /**
   * @swagger
   * /armors/{armor}:
   *  get:
   *    description: Get an armor by name or id
   *    parameters:
   *      - in: path
   *        name: armor
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the armor
   *    responses:
   *      '200':
   *        description: The armor
   *      '404':
   *        description: Armor not found
   */
  app.get('/armors/:armor', async (req,res) => { const r = await withCachedLookup('/armors', ['Armors', 'ArmorSets', 'ClassIds'], getArmors, req.params.armor); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getArmors, getArmor };

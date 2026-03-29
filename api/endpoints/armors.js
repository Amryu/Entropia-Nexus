const { pool } = require('./dbClient');
const { getObjectByIdOrName, generateGenderAliases, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Armors: 'SELECT "Armors"."Id", "Armors"."Name", "Armors"."Description", "ArmorSets"."Name" AS "Set", "Gender", "Slot", "SetId", "Weight", "MaxTT", "MinTT", "Durability", "Stab", "Cut", "Impact", "Penetration", "Shrapnel", "Burn", "Cold", "Acid", "Electric" FROM ONLY "Armors" LEFT JOIN ONLY "ArmorSets" ON "Armors"."SetId" = "ArmorSets"."Id"',
};

function toNumberOrNull(v) {
  return v === null || v === undefined ? null : Number(v);
}

function formatArmor(x, data){
  const aliases = generateGenderAliases(x.Name, x.Gender);
  const itemId = x.Id + idOffsets.Armors;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: itemId,
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
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Set: { Name: x.Set, Links: { "$Url": `/armorsets/${x.SetId}` } },
    Links: { "$Url": `/armors/${x.Id}` },
  };
}

async function getArmors() {
  const { rows } = await pool.query(queries.Armors);
  const itemIds = rows.map(r => r.Id + idOffsets.Armors);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('Armor', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  const data = { ClassIds: classIds, ItemProps: itemProps };
  return rows.map(r => formatArmor(r, data));
}
const getArmor = async (idOrName) => { const row = await getObjectByIdOrName(queries.Armors, 'Armors', idOrName); if (!row) return null; const itemId = row.Id + idOffsets.Armors; const [classIds, itemProps] = await Promise.all([loadClassIds('Armor', [row.Id]), loadItemProperties([itemId])]); const data = { ClassIds: classIds, ItemProps: itemProps }; return formatArmor(row, data); };

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
  app.get('/armors', async (req,res) => { res.json(await withCache('/armors', ['Armors', 'ArmorSets', 'ClassIds', 'ItemProperties'], getArmors)); });
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
  app.get('/armors/:armor', async (req,res) => { const r = await withCachedLookup('/armors', ['Armors', 'ArmorSets', 'ClassIds', 'ItemProperties'], getArmors, req.params.armor); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getArmors, getArmor };

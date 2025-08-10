const { getObjects, getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');

const queries = {
  Armors: 'SELECT "Armors"."Id", "Armors"."Name", "Armors"."Description", "ArmorSets"."Name" AS "Set", "Gender", "Slot", "SetId", "Weight", "MaxTT", "MinTT", "Durability", "Stab", "Cut", "Impact", "Penetration", "Shrapnel", "Burn", "Cold", "Acid", "Electric" FROM ONLY "Armors" LEFT JOIN ONLY "ArmorSets" ON "Armors"."SetId" = "ArmorSets"."Id"',
};

function toNumberOrNull(v) {
  return v === null || v === undefined ? null : Number(v);
}

function formatArmor(x){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Armors,
    Name: x.Name,
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

const getArmors = () => getObjects(queries.Armors, formatArmor);
const getArmor = async (idOrName) => { const row = await getObjectByIdOrName(queries.Armors, 'Armors', idOrName); return row ? formatArmor(row) : null; };

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
  app.get('/armors', async (req,res) => { res.json(await getArmors()); });
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
  app.get('/armors/:armor', async (req,res) => { const r = await getArmor(req.params.armor); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getArmors, getArmor };

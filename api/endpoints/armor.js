const { getObjects, getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');

const queries = {
  ArmorPlatings: 'SELECT * FROM ONLY "ArmorPlatings"',
  ArmorSets: 'SELECT "ArmorSets"."Id", "ArmorSets"."Name", "ArmorSets"."Description", "Durability", "Stab", "Cut", "Impact", "Penetration", "Shrapnel", "Burn", "Cold", "Acid", "Electric" FROM ONLY "ArmorSets"',
  Armors: 'SELECT "Armors"."Id", "Armors"."Name", "Armors"."Description", "ArmorSets"."Name" AS "Set", "Gender", "Slot", "SetId", "Weight", "MaxTT", "MinTT", "Durability", "Stab", "Cut", "Impact", "Penetration", "Shrapnel", "Burn", "Cold", "Acid", "Electric" FROM ONLY "Armors" LEFT JOIN ONLY "ArmorSets" ON "Armors"."SetId" = "ArmorSets"."Id"',
};

function formatResists(x){
  return { Stab: x.Stab, Cut: x.Cut, Impact: x.Impact, Penetration: x.Penetration, Shrapnel: x.Shrapnel, Burn: x.Burn, Cold: x.Cold, Acid: x.Acid, Electric: x.Electric };
}

function formatArmorPlating(x){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.ArmorPlatings,
    Name: x.Name,
    Properties: { Description: x.Description, Durability: x.Durability },
    Links: { "$Url": `/armorplatings/${x.Id}` }
  };
}

function formatArmorSet(x){
  return { Id: x.Id, Name: x.Name, Properties: { Description: x.Description, Durability: x.Durability, Resistances: formatResists(x) }, Links: { "$Url": `/armorsets/${x.Id}` } };
}

function formatArmor(x){
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Gender: x.Gender,
      Slot: x.Slot,
      Weight: x.Weight,
      Economy: { MaxTT: x.MaxTT, MinTT: x.MinTT },
      Durability: x.Durability,
      Resistances: formatResists(x),
    },
    Set: { Name: x.Set, Links: { "$Url": `/armorsets/${x.SetId}` } },
    Links: { "$Url": `/armors/${x.Id}` },
  };
}

const getArmorPlatings = () => getObjects(queries.ArmorPlatings, formatArmorPlating);
const getArmorPlating = async (idOrName) => { const row = await getObjectByIdOrName(queries.ArmorPlatings, 'ArmorPlatings', idOrName); return row ? formatArmorPlating(row) : null; };

const getArmorSets = () => getObjects(queries.ArmorSets, formatArmorSet);
const getArmorSet = async (idOrName) => { const row = await getObjectByIdOrName(queries.ArmorSets, 'ArmorSets', idOrName); return row ? formatArmorSet(row) : null; };

const getArmors = () => getObjects(queries.Armors, formatArmor);
const getArmor = async (idOrName) => { const row = await getObjectByIdOrName(queries.Armors, 'Armors', idOrName); return row ? formatArmor(row) : null; };

function register(app){
  // Armor Platings
  /**
   * @swagger
   * /armorplatings:
   *  get:
   *    description: Get all armor platings
   *    responses:
   *      '200':
   *        description: A list of armor platings
   */
  app.get('/armorplatings', async (req,res) => { res.json(await getArmorPlatings()); });
  /**
   * @swagger
   * /armorplatings/{armorPlating}:
   *  get:
   *    description: Get an armor plating by name or id
   *    parameters:
   *      - in: path
   *        name: armorPlating
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the armor plating
   *    responses:
   *      '200':
   *        description: The armor plating
   *      '404':
   *        description: Armor plating not found
   */
  app.get('/armorplatings/:armorPlating', async (req,res) => { const r = await getArmorPlating(req.params.armorPlating); if (r) res.json(r); else res.status(404).send(); });

  // Armor Sets
  /**
   * @swagger
   * /armorsets:
   *  get:
   *    description: Get all armor sets
   *    responses:
   *      '200':
   *        description: A list of armor sets
   */
  app.get('/armorsets', async (req,res) => { res.json(await getArmorSets()); });
  /**
   * @swagger
   * /armorsets/{armorset}:
   *  get:
   *    description: Get an armor set by name or id
   *    parameters:
   *      - in: path
   *        name: armorset
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the armor set
   *    responses:
   *      '200':
   *        description: The armor set
   *      '404':
   *        description: Armor set not found
   */
  app.get('/armorsets/:armorset', async (req,res) => { const r = await getArmorSet(req.params.armorset); if (r) res.json(r); else res.status(404).send(); });

  // Armors
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

module.exports = { register, getArmorPlatings, getArmorPlating, getArmorSets, getArmorSet, getArmors, getArmor };

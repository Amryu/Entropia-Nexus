const express = require('express');
const cors = require('cors');
const db = require('./db');
const app = express();
const port = 3000;

app.use(cors());
app.use(express.json());

app.listen(port, () => {
  console.log(`App running on port ${port}.`);
});

function parseItemList(list) {
  return list.match(/(".*?"|[^",]+)(?=\s*,|\s*$)/g).map(item => item.trim().replace(/^"(.*)"$/, '$1').replace(/""/g, '"'));
}

// Utility
app.get('/search', async (req, res) => {
  if (!req.query.query || req.query.query.trim().length === 0) return res.status(400).send('Query cannot be empty');

  res.json(await db.search(req.query.query));
});

// Maps & Locations
// Areas
app.get('/areas', async (req, res) => {
  if (req.query.Planet && req.query.Planets) return res.status(400).send('Cannot specify both Planet and Planets');

  if (req.query.Planet || req.query.Planets) {
    let planets = req.query.Planets
      ? parseItemList(req.query.Planets)
      : [req.query.Planet];

    if (planets.length === 0) return res.status(400).send('Planets cannot be empty');

    res.json(await db.getAreas(planets));
  }
  else {
    res.json(await db.getAreas());
  }
});

app.get('/areas/:area', async (req, res) => {
  let result = await db.getArea(req.params.area);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

// Locations
app.get('/locations', async (req, res) => {
  if (req.query.Planet && req.query.Planets) return res.status(400).send('Cannot specify both Planet and Planets');

  if (req.query.Planet || req.query.Planets) {
    let planets = req.query.Planets
      ? parseItemList(req.query.Planets)
      : [req.query.Planet];

    if (planets.length === 0) return res.status(400).send('Planets cannot be empty');

    res.json(await db.getLocations(planets));
    }
    else {
      res.json(await db.getLocations());
    }
});

app.get('/locations/:location', async (req, res) => {
  let result = await db.getLocation(req.params.location);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

// Planets
app.get('/planets', async (req, res) => {
  res.json(await db.getPlanets());
});

app.get('/planets/:planet', async (req, res) => {
  let result = await db.getPlanet(req.params.planet);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

// Teleporters
app.get('/teleporters', async (req, res) => {
  res.json(await db.getTeleporters());
});

app.get('/teleporters/:teleporter', async (req, res) => {
  let result = await db.getTeleporter(req.params.teleporter);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

// Items
app.get('/items', async (req, res) => {
  res.json(await db.getItems());
});

app.get('/items/:item', async (req, res) => {
  let result = await db.getItem(req.params.item);

  if (result) { 
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/absorbers', async (req, res) => {
  res.json(await db.getAbsorbers());
});

app.get('/absorbers/:absorber', async (req, res) => {
  let result = await db.getAbsorber(req.params.absorber);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/armorplatings', async (req, res) => {
  res.json(await db.getArmorPlatings());
});

app.get('/armorplatings/:armorPlating', async (req, res) => {
  let result = await db.getArmorPlating(req.params.armorPlating);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/armorsets', async (req, res) => {
  res.json(await db.getArmorSets());
});

app.get('/armorsets/:armorset', async (req, res) => {
  let result = await db.getArmorSet(req.params.armorset);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/armors', async (req, res) => {
  res.json(await db.getArmors());
});

app.get('/armors/:armor', async (req, res) => {
  let result = await db.getArmor(req.params.armor);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/blueprintbooks', async (req, res) => {
  res.json(await db.getBlueprintBooks());
});

app.get('/blueprintbooks/:blueprintBook', async (req, res) => {
  let result = await db.getBlueprintBook(req.params.blueprintBook);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/blueprints', async (req, res) => {
  if (req.query.Product && req.query.Products) return res.status(400).send('Cannot specify both Product and Products');

  if (req.query.Product || req.query.Products) {
    let products = req.query.Products
      ? parseItemList(req.query.Products)
      : [req.query.Product];

    if (products.length === 0) return res.status(400).send('Products cannot be empty');

    res.json(await db.getBlueprints(products));
  }
  else {
    res.json(await db.getBlueprints());
  }
});

app.get('/blueprints/:blueprint', async (req, res) => {
  let result = await db.getBlueprint(req.params.blueprint);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/clothes', async (req, res) => {
  res.json(await db.getClothes());
});

app.get('/clothes/:clothing', async (req, res) => {
  let result = await db.getClothes(req.params.clothing);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/consumables', async (req, res) => {
  res.json(await db.getConsumables());
});

app.get('/consumables/:consumable', async (req, res) => {
  let result = await db.getConsumable(req.params.consumable);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/creaturecontrolcapsules', async (req, res) => {
  res.json(await db.getCreatureControlCapsules());
});

app.get('/creaturecontrolcapsules/:capsule', async (req, res) => {
  let result = await db.getCreatureControlCapsule(req.params.capsule);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/decorations', async (req, res) => {
  res.json(await db.getDecorations());
});

app.get('/decorations/:decoration', async (req, res) => {
  let result = await db.getDecoration(req.params.decoration);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/effectchips', async (req, res) => {
  res.json(await db.getEffectChips());
});

app.get('/effectchips/:effectchip', async (req, res) => {
  let result = await db.getEffectChip(req.params.effectchip);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/effects', async (req, res) => {
  res.json(await db.getEffects());
});

app.get('/effects/:effect', async (req, res) => {
  let result = await db.getEffect(req.params.effect);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/enhancers', async (req, res) => { 
  res.json(await db.getEnhancers());
});

app.get('/enhancers/:enhancer', async (req, res) => {
  let result = await db.getEnhancer(req.params.enhancer);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/excavators', async (req, res) => {
  res.json(await db.getExcavators());
});

app.get('/excavators/:excavator', async (req, res) => {
  let result = await db.getExcavator(req.params.excavator);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/finderamplifiers', async (req, res) => {
  res.json(await db.getFinderAmplifiers());
});

app.get('/finderamplifiers/:finderAmplifier', async (req, res) => {
  let result = await db.getFinderAmplifier(req.params.finderAmplifier);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/finders', async (req, res) => {
  res.json(await db.getFinders());
});

app.get('/finders/:finder', async (req, res) => {
  let result = await db.getFinder(req.params.finder);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/furniture', async (req, res) => {
  res.json(await db.getFurniture());
});

app.get('/furniture/:furniture', async (req, res) => {
  let result = await db.getFurniture(req.params.furniture);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/planets', async (req, res) => {
  res.json(await db.getPlanets());
});

app.get('/planets/:planet', async (req, res) => {
  let result = await db.getPlanet(req.params.planet);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/materials', async (req, res) => {
  res.json(await db.getMaterials());
});

app.get('/materials/:material', async (req, res) => {
  let result = await db.getMaterial(req.params.material);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/medicalchips', async (req, res) => {
  res.json(await db.getMedicalChips());
});

app.get('/medicalchips/:medicalChip', async (req, res) => {
  let result = await db.getMedicalChip(req.params.medicalChip);

  if (result) {
    res.json(result); 
  }
  else {
    res.status(404).send();
  }
});

app.get('/medicaltools', async (req, res) => {
  res.json(await db.getMedicalTools());
});

app.get('/medicaltools/:medicalTool', async (req, res) => {
  let result = await db.getMedicalTool(req.params.medicalTool);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/mindforceimplants', async (req, res) => {
  res.json(await db.getMindforceImplants());
});

app.get('/mindforceimplants/:mindforceImplant', async (req, res) => {
  let result = await db.getMindforceImplant(req.params.mindforceImplant);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/misctools', async (req, res) => {
  res.json(await db.getMiscTools());
});

app.get('/misctools/:miscTool', async (req, res) => {
  let result = await db.getMiscTool(req.params.miscTool);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/mobloots', async (req, res) => {
  let items = null;
  let mobs = null;

  if (req.query.Item && req.query.Items) return res.status(400).send('Cannot specify both Item and Items');

  if (req.query.Item || req.query.Items) {
    items = req.query.Items
      ? parseItemList(req.query.Items)
      : [req.query.Item];

    if (items.length === 0) return res.status(400).send('Items cannot be empty');
  }

  if (req.query.Mob && req.query.Mobs) return res.status(400).send('Cannot specify both Mob and Mobs');

  if (req.query.Mob || req.query.Mobs) {
    mobs = req.query.Mobs
      ? parseItemList(req.query.Mobs)
      : [req.query.Mob];

    if (mobs.length === 0) return res.status(400).send('Mobs cannot be empty');
  }

  res.json(await db.getMobLoots(items, mobs));
});

app.get('/mobmaturities', async (req, res) => { 
  res.json(await db.getMobMaturities(req.query.Mob ?? null));
});

app.get('/mobmaturities/:mobMaturity', async (req, res) => {
  let result = await db.getMobMaturity(req.params.mobMaturity);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/mobspawns', async (req, res) => {
  res.json(await db.getMobSpawns());
});

app.get('/mobspawns/:mobSpawn', async (req, res) => {
  let result = await db.getMobSpawn(req.params.mobSpawn);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/mobspecies', async (req, res) => {
  res.json(await db.getMobSpecies());
});

app.get('/mobspecies/:mobSpecies', async (req, res) => {
  let result = await db.getMobSpecies(req.params.mobSpecies);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/mobs', async (req, res) => {
  res.json(await db.getMobs());
});

app.get('/mobs/:mob', async (req, res) => {
  let result = await db.getMob(req.params.mob);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/pets', async (req, res) => {
  res.json(await db.getPets());
});

app.get('/pets/:pet', async (req, res) => {
  let result = await db.getPet(req.params.pet);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/professioncategories', async (req, res) => {
  res.json(await db.getProfessionCategories());
});

app.get('/professioncategories/:professionCategory', async (req, res) => {
  let result = await db.getProfessionCategory(req.params.professionCategory);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/professions', async (req, res) => {
  res.json(await db.getProfessions());
});

app.get('/professions/:profession', async (req, res) => {
  let result = await db.getProfession(req.params.profession);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/refiners', async (req, res) => {
  res.json(await db.getRefiners());
});

app.get('/refiners/:refiner', async (req, res) => {
  let result = await db.getRefiner(req.params.refiner);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/refiningrecipes', async (req, res) => {
  if (req.query.Product && req.query.Products) return res.status(400).send('Cannot specify both Product and Products');

  if (req.query.Product || req.query.Products) {
    let products = req.query.Products
      ? parseItemList(req.query.Products)
      : [req.query.Product];

    if (products.length === 0) return res.status(400).send('Products cannot be empty');

    res.json(await db.getRefiningRecipes(products));
  }
  else {
    res.json(await db.getRefiningRecipes());
  }
});

app.get('/refiningrecipes/:refiningRecipe', async (req, res) => {
  let result = await db.getRefiningRecipe(req.params.refiningRecipe);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/scanners', async (req, res) => {
  res.json(await db.getScanners());
});

app.get('/scanners/:scanner', async (req, res) => {
  let result = await db.getScanner(req.params.scanner);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/signs', async (req, res) => {
  res.json(await db.getSigns());
});

app.get('/signs/:sign', async (req, res) => {
  let result = await db.getSign(req.params.sign);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/skillcategories', async (req, res) => {
  res.json(await db.getSkillCategories());
});

app.get('/skillcategories/:skillCategory', async (req, res) => {
  let result = await db.getSkillCategory(req.params.skillCategory);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/skills', async (req, res) => {
  res.json(await db.getSkills());
});

app.get('/skills/:skill', async (req, res) => {
  let result = await db.getSkill(req.params.skill);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/storagecontainers', async (req, res) => {
  res.json(await db.getStorageContainers());
});

app.get('/storagecontainers/:storageContainer', async (req, res) => {
  let result = await db.getStorageContainer(req.params.storageContainer);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/teleportationchips', async (req, res) => {
  res.json(await db.getTeleportationChips());
});

app.get('/teleportationchips/:teleportationChip', async (req, res) => {
  let result = await db.getTeleportationChip(req.params.teleportationChip);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/tiers', async (req, res) => {
  if (req.query.IsArmorSet == null || (req.query.IsArmorSet != 0 && req.query.IsArmorSet != 1)) return res.status(400).send('IsArmorSet must be 0 or 1');

  if (!Number.isInteger(Number(req.query.ItemId))) return res.status(400).send('ItemId must be an integer');

  res.json(await db.getTiers(req.query.ItemId ?? null, req.query.IsArmorSet ?? null));
});

app.get('/tiers/:tier', async (req, res) => {
  let result = await db.getTier(req.params.tier);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/vehicleattachmenttypes', async (req, res) => {
  res.json(await db.getVehicleAttachmentTypes());
});

app.get('/vehicleattachmenttypes/:vehicleAttachmentType', async (req, res) => {
  let result = await db.getVehicleAttachmentType(req.params.vehicleAttachmentType);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/vehicles', async (req, res) => {
  res.json(await db.getVehicles());
});

app.get('/vehicles/:vehicle', async (req, res) => {
  let result = await db.getVehicle(req.params.vehicle);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/vendors', async (req, res) => {
  res.json(await db.getVendors());
});

app.get('/vendors/:vendor', async (req, res) => {
  let result = await db.getVendor(req.params.vendor);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/vendoroffers', async (req, res) => {
  let items = null;

  if (req.query.Item && req.query.Items) return res.status(400).send('Cannot specify both Item and Items');

  if (req.query.Item || req.query.Items) {
    items = req.query.Items
      ? parseItemList(req.query.Items)
      : [req.query.Item];

    if (items.length === 0) return res.status(400).send('Items cannot be empty');
  }

  res.json(await db.getVendorOffers(items));
});

app.get('/vendoroffers/:vendorOffer', async (req, res) => {
  let result = await db.getVendorOffer(req.params.vendorOffer);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/weaponamplifiers', async (req, res) => {
  res.json(await db.getWeaponAmplifiers());
});

app.get('/weaponamplifiers/:weaponAmplifier', async (req, res) => {
  let result = await db.getWeaponAmplifier(req.params.weaponAmplifier);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/weaponvisionattachments', async (req, res) => {
  res.json(await db.getWeaponVisionAttachments());
});

app.get('/weaponvisionattachments/:weaponVisionAttachment', async (req, res) => {
  let result = await db.getWeaponVisionAttachment(req.params.weaponVisionAttachment);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

app.get('/weapons', async (req, res) => {
  res.json(await db.getWeapons());
});

app.get('/weapons/:weapon', async (req, res) => {
  let result = await db.getWeapon(req.params.weapon);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});
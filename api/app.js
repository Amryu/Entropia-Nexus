const express = require('express');
const cors = require('cors');
const swaggerJsDoc = require('swagger-jsdoc');
const swaggerUi = require('swagger-ui-express');

const db = require('./db');
const app = express();
const port = 3000;

const swaggerOptions = {
  definition: {
    openapi: '3.0.0',
    info: {
      title: 'Entropia Nexus API',
      version: '1.0.0',
      description: 'Serves all entities from the Entropia Nexus database.',
    },
  },
  // Path to the API docs
  apis: ['./app.js'],
};

const swaggerDocs = swaggerJsDoc(swaggerOptions);

app.use('/docs', swaggerUi.serve, swaggerUi.setup(swaggerDocs, { explorer: true, customCss: '.swagger-ui .topbar { display: none }', customSiteTitle: 'Entropia Nexus API', apisSorter: 'alpha', operationsSorter: 'alpha' }));

app.use(cors());
app.use(express.json());

app.listen(port, () => {
  console.log(`App running on port ${port}.`);
});

function parseItemList(list) {
  return list.match(/(".*?"|[^",]+)(?=\s*,|\s*$)/g).map(item => item.trim().replace(/^"(.*)"$/, '$1').replace(/""/g, '"'));
}

// Utility
/**
 * @swagger
 * /search:
 *  get:
 *    description: Search for entities by name. Returns up to 20 results.
 *    parameters:
 *      - in: query
 *        name: query
 *        schema:
 *          type: string
 *        required: true
 *        description: The search query
 *    responses:
 *      '200':
 *        description: A list of entities matching the search query
 *      '400':
 *        description: Query cannot be empty
 */
app.get('/search', async (req, res) => {
  if (!req.query.query || req.query.query.trim().length === 0) return res.status(400).send('Query cannot be empty');

  res.json(await db.search(req.query.query));
});

// Maps & Locations
/**
 * @swagger
 * /areas:
 *  get:
 *    description: Get all areas
 *    parameters:
 *      - in: query
 *        name: Planet
 *        schema:
 *          type: string
 *        description: The planet to filter areas by
 *      - in: query
 *        name: Planets
 *        schema:
 *          type: string
 *        description: A comma-separated list of planets to filter areas by
 *    responses:
 *      '200':
 *        description: A list of areas
 *      '400':
 *        description: Cannot specify both Planet and Planets
 */
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

/**
 * @swagger
 * /areas/{area}:
 *  get:
 *    description: Get an area by name or id
 *    parameters:
 *      - in: path
 *        name: area
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the area
 *    responses:
 *      '200':
 *        description: The area
 *      '404':
 *        description: Area not found
 */
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
/**
 * @swagger
 * /locations:
 *  get:
 *    description: Get all locations
 *    parameters:
 *      - in: query
 *        name: Planet
 *        schema:
 *          type: string
 *        description: The planet to filter locations by
 *      - in: query
 *        name: Planets
 *        schema:
 *          type: string
 *        description: A comma-separated list of planets to filter locations by
 *    responses:
 *      '200':
 *        description: A list of locations
 *      '400':
 *        description: Cannot specify both Planet and Planets
 */
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

/**
 * @swagger
 * /locations/{location}:
 *  get:
 *    description: Get a location by name or id
 *    parameters:
 *      - in: path
 *        name: location
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the location
 *    responses:
 *      '200':
 *        description: The location
 *      '404':
 *        description: Location not found
 */
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

/**
 * @swagger
 * /planets:
 *  get:
 *    description: Get all planets
 *    responses:
 *      '200':
 *        description: A list of planets
 */
app.get('/planets', async (req, res) => {
  res.json(await db.getPlanets());
});

/**
 * @swagger
 * /planets/{planet}:
 *  get:
 *    description: Get a planet by name or id
 *    parameters:
 *      - in: path
 *        name: planet
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the planet
 *    responses:
 *      '200':
 *        description: The planet
 *      '404':
 *        description: Planet not found
 */
app.get('/planets/:planet', async (req, res) => {
  let result = await db.getPlanet(req.params.planet);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /teleporters:
 *  get:
 *    description: Get all teleporters
 *    responses:
 *      '200':
 *        description: A list of teleporters
 */
app.get('/teleporters', async (req, res) => {
  res.json(await db.getTeleporters());
});

/**
 * @swagger
 * /teleporters/{teleporter}:
 *  get:
 *    description: Get a teleporter by name or id
 *    parameters:
 *      - in: path
 *        name: teleporter
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the teleporter
 *    responses:
 *      '200':
 *        description: The teleporter
 *      '404':
 *        description: Teleporter not found
 */
app.get('/teleporters/:teleporter', async (req, res) => {
  let result = await db.getTeleporter(req.params.teleporter);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /items:
 *  get:
 *    description: Get all items
 *    responses:
 *      '200':
 *        description: A list of items
 */
app.get('/items', async (req, res) => {
  res.json(await db.getItems());
});

/**
 * @swagger
 * /items/{item}:
 *  get:
 *    description: Get an item by name or id
 *    parameters:
 *      - in: path
 *        name: item
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the item
 *    responses:
 *      '200':
 *        description: The item
 *      '404':
 *        description: Item not found
 */
app.get('/items/:item', async (req, res) => {
  let result = await db.getItem(req.params.item);

  if (result) { 
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /weapons:
 *  get:
 *    description: Get all weapons
 *    responses:
 *      '200':
 *        description: A list of weapons
 */
app.get('/absorbers', async (req, res) => {
  res.json(await db.getAbsorbers());
});

/**
 * @swagger
 * /absorbers/{absorber}:
 *  get:
 *    description: Get an absorber by name or id
 *    parameters:
 *      - in: path
 *        name: absorber
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the absorber
 *    responses:
 *      '200':
 *        description: The absorber
 *      '404':
 *        description: Absorber not found
 */
app.get('/absorbers/:absorber', async (req, res) => {
  let result = await db.getAbsorber(req.params.absorber);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /armorplatings:
 *  get:
 *    description: Get all armor platings
 *    responses:
 *      '200':
 *        description: A list of armor platings
 */
app.get('/armorplatings', async (req, res) => {
  res.json(await db.getArmorPlatings());
});

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
app.get('/armorplatings/:armorPlating', async (req, res) => {
  let result = await db.getArmorPlating(req.params.armorPlating);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /armorsets:
 *  get:
 *    description: Get all armor sets
 *    responses:
 *      '200':
 *        description: A list of armor sets
 */
app.get('/armorsets', async (req, res) => {
  res.json(await db.getArmorSets());
});

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
app.get('/armorsets/:armorset', async (req, res) => {
  let result = await db.getArmorSet(req.params.armorset);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /weapons:
 *  get:
 *    description: Get all weapons
 *    responses:
 *      '200':
 *        description: A list of weapons
 */
app.get('/armors', async (req, res) => {
  res.json(await db.getArmors());
});

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
app.get('/armors/:armor', async (req, res) => {
  let result = await db.getArmor(req.params.armor);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /attachments:
 *  get:
 *    description: Get all attachments
 *    responses:
 *      '200':
 *        description: A list of attachments
 */
app.get('/blueprintbooks', async (req, res) => {
  res.json(await db.getBlueprintBooks());
});

// Document this entity with swagger jsdoc. Don't write a function
/**
 * @swagger
 * /blueprintbooks/{blueprintBook}:
 *  get:
 *    description: Get a blueprint book by name or id
 *    parameters:
 *      - in: path
 *        name: blueprintBook
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the blueprint book
 *    responses:
 *      '200':
 *        description: The blueprint book
 *      '404':
 *        description: Blueprint book not found
 */
app.get('/blueprintbooks/:blueprintBook', async (req, res) => {
  let result = await db.getBlueprintBook(req.params.blueprintBook);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /blueprints:
 *  get:
 *    description: Get all blueprints
 *    parameters:
 *      - in: query
 *        name: Product
 *        schema:
 *          type: string
 *        description: The product to filter blueprints by
 *      - in: query
 *        name: Products
 *        schema:
 *          type: string
 *        description: A comma-separated list of products to filter blueprints by
 *    responses:
 *      '200':
 *        description: A list of blueprints
 *      '400':
 *        description: Cannot specify both Product and Products
 */
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

/**
 * @swagger
 * /blueprints/{blueprint}:
 *  get:
 *    description: Get a blueprint by name or id
 *    parameters:
 *      - in: path
 *        name: blueprint
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the blueprint
 *    responses:
 *      '200':
 *        description: The blueprint
 *      '404':
 *        description: Blueprint not found
 */
app.get('/blueprints/:blueprint', async (req, res) => {
  let result = await db.getBlueprint(req.params.blueprint);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /books:
 *  get:
 *    description: Get all books
 *    responses:
 *      '200':
 *        description: A list of books
 */
app.get('/clothes', async (req, res) => {
  res.json(await db.getClothes());
});

/**
 * @swagger
 * /clothes/{clothing}:
 *  get:
 *    description: Get a clothing by name or id
 *    parameters:
 *      - in: path
 *        name: clothing
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the clothing
 *    responses:
 *      '200':
 *        description: The clothing
 *      '404':
 *        description: Clothing not found
 */
app.get('/clothes/:clothing', async (req, res) => {
  let result = await db.getClothes(req.params.clothing);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /components:
 *  get:
 *    description: Get all components
 *    responses:
 *      '200':
 *        description: A list of components
 */
app.get('/consumables', async (req, res) => {
  res.json(await db.getConsumables());
});

/**
 * @swagger
 * /consumables/{consumable}:
 *  get:
 *    description: Get a consumable by name or id
 *    parameters:
 *      - in: path
 *        name: consumable
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the consumable
 *    responses:
 *      '200':
 *        description: The consumable
 *      '404':
 *        description: Consumable not found
 */
app.get('/consumables/:consumable', async (req, res) => {
  let result = await db.getConsumable(req.params.consumable);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /containers:
 *  get:
 *    description: Get all containers
 *    responses:
 *      '200':
 *        description: A list of containers
 */
app.get('/creaturecontrolcapsules', async (req, res) => {
  res.json(await db.getCreatureControlCapsules());
});

/**
 * @swagger
 * /creaturecontrolcapsules/{capsule}:
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
app.get('/creaturecontrolcapsules/:capsule', async (req, res) => {
  let result = await db.getCreatureControlCapsule(req.params.capsule);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /creaturecontroldevices:
 *  get:
 *    description: Get all creature control devices
 *    responses:
 *      '200':
 *        description: A list of creature control devices
 */
app.get('/decorations', async (req, res) => {
  res.json(await db.getDecorations());
});

/**
 * @swagger
 * /decorations/{decoration}:
 *  get:
 *    description: Get a decoration by name or id
 *    parameters:
 *      - in: path
 *        name: decoration
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the decoration
 *    responses:
 *      '200':
 *        description: The decoration
 *      '404':
 *        description: Decoration not found
 */
app.get('/decorations/:decoration', async (req, res) => {
  let result = await db.getDecoration(req.params.decoration);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /devices:
 *  get:
 *    description: Get all devices
 *    responses:
 *      '200':
 *        description: A list of devices
 */
app.get('/effectchips', async (req, res) => {
  res.json(await db.getEffectChips());
});

/**
 * @swagger
 * /effectchips/{effectchip}:
 *  get:
 *    description: Get an effect chip by name or id
 *    parameters:
 *      - in: path
 *        name: effectchip
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the effect chip
 *    responses:
 *      '200':
 *        description: The effect chip
 *      '404':
 *        description: Effect chip not found
 */
app.get('/effectchips/:effectchip', async (req, res) => {
  let result = await db.getEffectChip(req.params.effectchip);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /effects:
 *  get:
 *    description: Get all effects
 *    responses:
 *      '200':
 *        description: A list of effects
 */
app.get('/effects', async (req, res) => {
  res.json(await db.getEffects());
});

/**
 * @swagger
 * /effects/{effect}:
 *  get:
 *    description: Get an effect by name or id
 *    parameters:
 *      - in: path
 *        name: effect
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the effect
 *    responses:
 *      '200':
 *        description: The effect
 *      '404':
 *        description: Effect not found
 */
app.get('/effects/:effect', async (req, res) => {
  let result = await db.getEffect(req.params.effect);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /enhancers:
 *  get:
 *    description: Get all enhancers
 *    responses:
 *      '200':
 *        description: A list of enhancers
 */
app.get('/enhancers', async (req, res) => { 
  res.json(await db.getEnhancers());
});

/**
 * @swagger
 * /enhancers/{enhancer}:
 *  get:
 *    description: Get an enhancer by name or id
 *    parameters:
 *      - in: path
 *        name: enhancer
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the enhancer
 *    responses:
 *      '200':
 *        description: The enhancer
 *      '404':
 *        description: Enhancer not found
 */
app.get('/enhancers/:enhancer', async (req, res) => {
  let result = await db.getEnhancer(req.params.enhancer);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /equipsets:
 *  get:
 *    description: Get all equip sets
 *    responses:
 *      '200':
 *        description: A list of equip sets
 */
app.get('/equipsets', async (req, res) => {
  res.json(await db.getEquipSets());
});

/**
 * @swagger
 * /equipsets/{equipSet}:
 *  get:
 *    description: Get an equip set by name or id
 *    parameters:
 *      - in: path
 *        name: equipSet
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the equip set
 *    responses:
 *      '200':
 *        description: The equip set
 *      '404':
 *        description: Equip set not found
 */
app.get('/equipsets/:equipSet', async (req, res) => {
  let result = await db.getEquipSet(req.params.equipSet);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /entropianpets:
 *  get:
 *    description: Get all Entropian pets
 *    responses:
 *      '200':
 *        description: A list of Entropian pets
 */
app.get('/excavators', async (req, res) => {
  res.json(await db.getExcavators());
});

/**
 * @swagger
 * /excavators/{excavator}:
 *  get:
 *    description: Get an excavator by name or id
 *    parameters:
 *      - in: path
 *        name: excavator
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the excavator
 *    responses:
 *      '200':
 *        description: The excavator
 *      '404':
 *        description: Excavator not found
 */
app.get('/excavators/:excavator', async (req, res) => {
  let result = await db.getExcavator(req.params.excavator);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /finders:
 *  get:
 *    description: Get all finders
 *    responses:
 *      '200':
 *        description: A list of finders
 */
app.get('/finderamplifiers', async (req, res) => {
  res.json(await db.getFinderAmplifiers());
});

/**
 * @swagger
 * /finderamplifiers/{finderAmplifier}:
 *  get:
 *    description: Get a finder amplifier by name or id
 *    parameters:
 *      - in: path
 *        name: finderAmplifier
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the finder amplifier
 *    responses:
 *      '200':
 *        description: The finder amplifier
 *      '404':
 *        description: Finder amplifier not found
 */
app.get('/finderamplifiers/:finderAmplifier', async (req, res) => {
  let result = await db.getFinderAmplifier(req.params.finderAmplifier);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /finders:
 *  get:
 *    description: Get all finders
 *    responses:
 *      '200':
 *        description: A list of finders
 */
app.get('/finders', async (req, res) => {
  res.json(await db.getFinders());
});

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
app.get('/finders/:finder', async (req, res) => {
  let result = await db.getFinder(req.params.finder);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /furniture:
 *  get:
 *    description: Get all furniture
 *    responses:
 *      '200':
 *        description: A list of furniture
 */
app.get('/furniture', async (req, res) => {
  res.json(await db.getFurniture());
});

/**
 * @swagger
 * /furniture/{furniture}:
 *  get:
 *    description: Get a furniture by name or id
 *    parameters:
 *      - in: path
 *        name: furniture
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the furniture
 *    responses:
 *      '200':
 *        description: The furniture
 *      '404':
 *        description: Furniture not found
 */
app.get('/furniture/:furniture', async (req, res) => {
  let result = await db.getFurniture(req.params.furniture);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /planets:
 *  get:
 *    description: Get all planets
 *    responses:
 *      '200':
 *        description: A list of planets
 */
app.get('/planets', async (req, res) => {
  res.json(await db.getPlanets());
});

/**
 * @swagger
 * /planets/{planet}:
 *  get:
 *    description: Get a planet by name or id
 *    parameters:
 *      - in: path
 *        name: planet
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the planet
 *    responses:
 *      '200':
 *        description: The planet
 *      '404':
 *        description: Planet not found
 */
app.get('/planets/:planet', async (req, res) => {
  let result = await db.getPlanet(req.params.planet);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /materials:
 *  get:
 *    description: Get all materials
 *    responses:
 *      '200':
 *        description: A list of materials
 */
app.get('/materials', async (req, res) => {
  res.json(await db.getMaterials());
});

/**
 * @swagger
 * /materials/{material}:
 *  get:
 *    description: Get a material by name or id
 *    parameters:
 *      - in: path
 *        name: material
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the material
 *    responses:
 *      '200':
 *        description: The material
 *      '404':
 *        description: Material not found
 */
app.get('/materials/:material', async (req, res) => {
  let result = await db.getMaterial(req.params.material);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /medicalchips:
 *  get:
 *    description: Get all medical chips
 *    responses:
 *      '200':
 *        description: A list of medical chips
 */
app.get('/medicalchips', async (req, res) => {
  res.json(await db.getMedicalChips());
});

/**
 * @swagger
 * /medicalchips/{medicalChip}:
 *  get:
 *    description: Get a medical chip by name or id
 *    parameters:
 *      - in: path
 *        name: medicalChip
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the medical chip
 *    responses:
 *      '200':
 *        description: The medical chip
 *      '404':
 *        description: Medical chip not found
 */
app.get('/medicalchips/:medicalChip', async (req, res) => {
  let result = await db.getMedicalChip(req.params.medicalChip);

  if (result) {
    res.json(result); 
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /medicaltools:
 *  get:
 *    description: Get all medical tools
 *    responses:
 *      '200':
 *        description: A list of medical tools
 */
app.get('/medicaltools', async (req, res) => {
  res.json(await db.getMedicalTools());
});

/**
 * @swagger
 * /medicaltools/{medicalTool}:
 *  get:
 *    description: Get a medical tool by name or id
 *    parameters:
 *      - in: path
 *        name: medicalTool
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the medical tool
 *    responses:
 *      '200':
 *        description: The medical tool
 *      '404':
 *        description: Medical tool not found
 */
app.get('/medicaltools/:medicalTool', async (req, res) => {
  let result = await db.getMedicalTool(req.params.medicalTool);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /mindforceimplants:
 *  get:
 *    description: Get all Mindforce implants
 *    responses:
 *      '200':
 *        description: A list of Mindforce implants
 */
app.get('/mindforceimplants', async (req, res) => {
  res.json(await db.getMindforceImplants());
});

/**
 * @swagger
 * /mindforceimplants/{mindforceImplant}:
 *  get:
 *    description: Get a Mindforce implant by name or id
 *    parameters:
 *      - in: path
 *        name: mindforceImplant
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the Mindforce implant
 *    responses:
 *      '200':
 *        description: The Mindforce implant
 *      '404':
 *        description: Mindforce implant not found
 */
app.get('/mindforceimplants/:mindforceImplant', async (req, res) => {
  let result = await db.getMindforceImplant(req.params.mindforceImplant);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /misctools:
 *  get:
 *    description: Get all misc. tools
 *    responses:
 *      '200':
 *        description: A list of misc. tools
 */
app.get('/misctools', async (req, res) => {
  res.json(await db.getMiscTools());
});

/**
 * @swagger
 * /misctools/{miscTool}:
 *  get:
 *    description: Get a misc. tool by name or id
 *    parameters:
 *      - in: path
 *        name: miscTool
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the misc. tool
 *    responses:
 *      '200':
 *        description: The misc. tool
 *      '404':
 *        description: Misc. tool not found
 */
app.get('/misctools/:miscTool', async (req, res) => {
  let result = await db.getMiscTool(req.params.miscTool);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

// Document this entity with swagger jsdoc. Don't write a function. MobLoots
/**
 * @swagger
 * /mobloots:
 *  get:
 *    description: Get all mob loots
 *    parameters:
 *      - in: query
 *        name: Item
 *        schema:
 *          type: string
 *        description: The item to filter mob loots by
 *      - in: query
 *        name: Items
 *        schema:
 *          type: string
 *        description: A comma-separated list of items to filter mob loots by
 *      - in: query
 *        name: Mob
 *        schema:
 *          type: string
 *        description: The mob to filter mob loots by
 *      - in: query
 *        name: Mobs
 *        schema:
 *          type: string
 *        description: A comma-separated list of mobs to filter mob loots by
 *    responses:
 *      '200':
 *        description: A list of mob loots
 *      '400':
 *        description: Cannot specify both Item and Items or Mob and Mobs
 */
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

/**
 * @swagger
 * /mobmaturities:
 *  get:
 *    description: Get all mob maturities
 *    parameters:
 *      - in: query
 *        name: Mob
 *        schema:
 *          type: string
 *        description: The mob to filter mob maturities by
 *    responses:
 *      '200':
 *        description: A list of mob maturities
 */
app.get('/mobmaturities', async (req, res) => { 
  res.json(await db.getMobMaturities(req.query.Mob ?? null));
});

/**
 * @swagger
 * /mobmaturities/{mobMaturity}:
 *  get:
 *    description: Get a mob maturity by name or id
 *    parameters:
 *      - in: path
 *        name: mobMaturity
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the mob maturity
 *    responses:
 *      '200':
 *        description: The mob maturity
 *      '404':
 *        description: Mob maturity not found
 */
app.get('/mobmaturities/:mobMaturity', async (req, res) => {
  let result = await db.getMobMaturity(req.params.mobMaturity);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /mobspawns:
 *  get:
 *    description: Get all mob spawns
 *    responses:
 *      '200':
 *        description: A list of mob spawns
 */
app.get('/mobspawns', async (req, res) => {
  res.json(await db.getMobSpawns());
});

/**
 * @swagger
 * /mobspawns/{mobSpawn}:
 *  get:
 *    description: Get a mob spawn by name or id
 *    parameters:
 *      - in: path
 *        name: mobSpawn
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the mob spawn
 *    responses:
 *      '200':
 *        description: The mob spawn
 *      '404':
 *        description: Mob spawn not found
 */
app.get('/mobspawns/:mobSpawn', async (req, res) => {
  let result = await db.getMobSpawn(req.params.mobSpawn);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /mobspecies:
 *  get:
 *    description: Get all mob species
 *    responses:
 *      '200':
 *        description: A list of mob species
 */
app.get('/mobspecies', async (req, res) => {
  res.json(await db.getMobSpecies());
});

/**
 * @swagger
 * /mobspecies/{mobSpecies}:
 *  get:
 *    description: Get a mob species by name or id
 *    parameters:
 *      - in: path
 *        name: mobSpecies
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the mob species
 *    responses:
 *      '200':
 *        description: The mob species
 *      '404':
 *        description: Mob species not found
 */
app.get('/mobspecies/:mobSpecies', async (req, res) => {
  let result = await db.getMobSpecies(req.params.mobSpecies);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /mobs:
 *  get:
 *    description: Get all mobs
 *    responses:
 *      '200':
 *        description: A list of mobs
 */
app.get('/mobs', async (req, res) => {
  res.json(await db.getMobs());
});

/**
 * @swagger
 * /mobs/{mob}:
 *  get:
 *    description: Get a mob by name or id
 *    parameters:
 *      - in: path
 *        name: mob
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the mob
 *    responses:
 *      '200':
 *        description: The mob
 *      '404':
 *        description: Mob not found
 */
app.get('/mobs/:mob', async (req, res) => {
  let result = await db.getMob(req.params.mob);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /pets:
 *  get:
 *    description: Get all pets
 *    responses:
 *      '200':
 *        description: A list of pets
 */
app.get('/pets', async (req, res) => {
  res.json(await db.getPets());
});

/**
 * @swagger
 * /pets/{pet}:
 *  get:
 *    description: Get a pet by name or id
 *    parameters:
 *      - in: path
 *        name: pet
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the pet
 *    responses:
 *      '200':
 *        description: The pet
 *      '404':
 *        description: Pet not found
 */
app.get('/pets/:pet', async (req, res) => {
  let result = await db.getPet(req.params.pet);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /professioncategories:
 *  get:
 *    description: Get all profession categories
 *    responses:
 *      '200':
 *        description: A list of profession categories
 */
app.get('/professioncategories', async (req, res) => {
  res.json(await db.getProfessionCategories());
});

/**
 * @swagger
 * /professioncategories/{professionCategory}:
 *  get:
 *    description: Get a profession category by name or id
 *    parameters:
 *      - in: path
 *        name: professionCategory
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the profession category
 *    responses:
 *      '200':
 *        description: The profession category
 *      '404':
 *        description: Profession category not found
 */
app.get('/professioncategories/:professionCategory', async (req, res) => {
  let result = await db.getProfessionCategory(req.params.professionCategory);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /professions:
 *  get:
 *    description: Get all professions
 *    responses:
 *      '200':
 *        description: A list of professions
 */
app.get('/professions', async (req, res) => {
  res.json(await db.getProfessions());
});

/**
 * @swagger
 * /professions/{profession}:
 *  get:
 *    description: Get a profession by name or id
 *    parameters:
 *      - in: path
 *        name: profession
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the profession
 *    responses:
 *      '200':
 *        description: The profession
 *      '404':
 *        description: Profession not found
 */
app.get('/professions/:profession', async (req, res) => {
  let result = await db.getProfession(req.params.profession);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /refiners:
 *  get:
 *    description: Get all refiners
 *    responses:
 *      '200':
 *        description: A list of refiners
 */
app.get('/refiners', async (req, res) => {
  res.json(await db.getRefiners());
});

/**
 * @swagger
 * /refiners/{refiner}:
 *  get:
 *    description: Get a refiner by name or id
 *    parameters:
 *      - in: path
 *        name: refiner
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the refiner
 *    responses:
 *      '200':
 *        description: The refiner
 *      '404':
 *        description: Refiner not found
 */
app.get('/refiners/:refiner', async (req, res) => {
  let result = await db.getRefiner(req.params.refiner);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /refiningrecipes:
 *  get:
 *    description: Get all refining recipes
 *    parameters:
 *      - in: query
 *        name: Product
 *        schema:
 *          type: string
 *        description: The product to filter refining recipes by
 *      - in: query
 *        name: Products
 *        schema:
 *          type: string
 *        description: A comma-separated list of products to filter refining recipes by
 *    responses:
 *      '200':
 *        description: A list of refining recipes
 *      '400':
 *        description: Cannot specify both Product and Products
 */
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

/**
 * @swagger
 * /refiningrecipes/{refiningRecipe}:
 *  get:
 *    description: Get a refining recipe by name or id
 *    parameters:
 *      - in: path
 *        name: refiningRecipe
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the refining recipe
 *    responses:
 *      '200':
 *        description: The refining recipe
 *      '404':
 *        description: Refining recipe not found
 */
app.get('/refiningrecipes/:refiningRecipe', async (req, res) => {
  let result = await db.getRefiningRecipe(req.params.refiningRecipe);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /scanners:
 *  get:
 *    description: Get all scanners
 *    responses:
 *      '200':
 *        description: A list of scanners
 */
app.get('/scanners', async (req, res) => {
  res.json(await db.getScanners());
});

/**
 * @swagger
 * /scanners/{scanner}:
 *  get:
 *    description: Get a scanner by name or id
 *    parameters:
 *      - in: path
 *        name: scanner
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the scanner
 *    responses:
 *      '200':
 *        description: The scanner
 *      '404':
 *        description: Scanner not found
 */
app.get('/scanners/:scanner', async (req, res) => {
  let result = await db.getScanner(req.params.scanner);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /signs:
 *  get:
 *    description: Get all signs
 *    responses:
 *      '200':
 *        description: A list of signs
 */
app.get('/signs', async (req, res) => {
  res.json(await db.getSigns());
});

/**
 * @swagger
 * /signs/{sign}:
 *  get:
 *    description: Get a sign by name or id
 *    parameters:
 *      - in: path
 *        name: sign
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the sign
 *    responses:
 *      '200':
 *        description: The sign
 *      '404':
 *        description: Sign not found
 */
app.get('/signs/:sign', async (req, res) => {
  let result = await db.getSign(req.params.sign);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /skillcategories:
 *  get:
 *    description: Get all skill categories
 *    responses:
 *      '200':
 *        description: A list of skill categories
 */
app.get('/skillcategories', async (req, res) => {
  res.json(await db.getSkillCategories());
});

/**
 * @swagger
 * /skillcategories/{skillCategory}:
 *  get:
 *    description: Get a skill category by name or id
 *    parameters:
 *      - in: path
 *        name: skillCategory
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the skill category
 *    responses:
 *      '200':
 *        description: The skill category
 *      '404':
 *        description: Skill category not found
 */
app.get('/skillcategories/:skillCategory', async (req, res) => {
  let result = await db.getSkillCategory(req.params.skillCategory);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /skills:
 *  get:
 *    description: Get all skills
 *    responses:
 *      '200':
 *        description: A list of skills
 */
app.get('/skills', async (req, res) => {
  res.json(await db.getSkills());
});

/**
 * @swagger
 * /skills/{skill}:
 *  get:
 *    description: Get a skill by name or id
 *    parameters:
 *      - in: path
 *        name: skill
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the skill
 *    responses:
 *      '200':
 *        description: The skill
 *      '404':
 *        description: Skill not found
 */
app.get('/skills/:skill', async (req, res) => {
  let result = await db.getSkill(req.params.skill);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /storagecontainers:
 *  get:
 *    description: Get all storage containers
 *    responses:
 *      '200':
 *        description: A list of storage containers
 */
app.get('/storagecontainers', async (req, res) => {
  res.json(await db.getStorageContainers());
});

/**
 * @swagger
 * /storagecontainers/{storageContainer}:
 *  get:
 *    description: Get a storage container by name or id
 *    parameters:
 *      - in: path
 *        name: storageContainer
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the storage container
 *    responses:
 *      '200':
 *        description: The storage container
 *      '404':
 *        description: Storage container not found
 */
app.get('/storagecontainers/:storageContainer', async (req, res) => {
  let result = await db.getStorageContainer(req.params.storageContainer);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /teleportationchips:
 *  get:
 *    description: Get all teleportation chips
 *    responses:
 *      '200':
 *        description: A list of teleportation chips
 */
app.get('/teleportationchips', async (req, res) => {
  res.json(await db.getTeleportationChips());
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
app.get('/teleportationchips/:teleportationChip', async (req, res) => {
  let result = await db.getTeleportationChip(req.params.teleportationChip);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /tiers:
 *  get:
 *    description: Get all tiers
 *    parameters:
 *      - in: query
 *        name: ItemId
 *        schema:
 *          type: integer
 *        description: The item id to filter tiers by
 *      - in: query
 *        name: IsArmorSet
 *        schema:
 *          type: integer
 *        description: Whether the item is an armor set
 *    responses:
 *      '200':
 *        description: A list of tiers
 *      '400':
 *        description: IsArmorSet must be 0 or 1
 */
app.get('/tiers', async (req, res) => {
  if (req.query.IsArmorSet == null || (req.query.IsArmorSet != 0 && req.query.IsArmorSet != 1)) return res.status(400).send('IsArmorSet must be 0 or 1');

  if (!Number.isInteger(Number(req.query.ItemId))) return res.status(400).send('ItemId must be an integer');

  res.json(await db.getTiers(req.query.ItemId ?? null, req.query.IsArmorSet ?? null));
});

/**
 * @swagger
 * /tiers/{tier}:
 *  get:
 *    description: Get a tier by name or id
 *    parameters:
 *      - in: path
 *        name: tier
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the tier
 *    responses:
 *      '200':
 *        description: The tier
 *      '404':
 *        description: Tier not found
 */
app.get('/tiers/:tier', async (req, res) => {
  let result = await db.getTier(req.params.tier);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /vehicleattachmenttypes:
 *  get:
 *    description: Get all vehicle attachment types
 *    responses:
 *      '200':
 *        description: A list of vehicle attachment types
 */
app.get('/vehicleattachmenttypes', async (req, res) => {
  res.json(await db.getVehicleAttachmentTypes());
});

/**
 * @swagger
 * /vehicleattachmenttypes/{vehicleAttachmentType}:
 *  get:
 *    description: Get a vehicle attachment type by name or id
 *    parameters:
 *      - in: path
 *        name: vehicleAttachmentType
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the vehicle attachment type
 *    responses:
 *      '200':
 *        description: The vehicle attachment type
 *      '404':
 *        description: Vehicle attachment type not found
 */
app.get('/vehicleattachmenttypes/:vehicleAttachmentType', async (req, res) => {
  let result = await db.getVehicleAttachmentType(req.params.vehicleAttachmentType);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /vehicles:
 *  get:
 *    description: Get all vehicles
 *    responses:
 *      '200':
 *        description: A list of vehicles
 */
app.get('/vehicles', async (req, res) => {
  res.json(await db.getVehicles());
});

/**
 * @swagger
 * /vehicles/{vehicle}:
 *  get:
 *    description: Get a vehicle by name or id
 *    parameters:
 *      - in: path
 *        name: vehicle
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the vehicle
 *    responses:
 *      '200':
 *        description: The vehicle
 *      '404':
 *        description: Vehicle not found
 */
app.get('/vehicles/:vehicle', async (req, res) => {
  let result = await db.getVehicle(req.params.vehicle);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /vendors:
 *  get:
 *    description: Get all vendors
 *    responses:
 *      '200':
 *        description: A list of vendors
 */
app.get('/vendors', async (req, res) => {
  res.json(await db.getVendors());
});

/**
 * @swagger
 * /vendors/{vendor}:
 *  get:
 *    description: Get a vendor by name or id
 *    parameters:
 *      - in: path
 *        name: vendor
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the vendor
 *    responses:
 *      '200':
 *        description: The vendor
 *      '404':
 *        description: Vendor not found
 */
app.get('/vendors/:vendor', async (req, res) => {
  let result = await db.getVendor(req.params.vendor);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /vendoroffers:
 *  get:
 *    description: Get all vendor offers
 *    parameters:
 *      - in: query
 *        name: Item
 *        schema:
 *          type: string
 *        description: The item to filter vendor offers by
 *      - in: query
 *        name: Items
 *        schema:
 *          type: string
 *        description: A comma-separated list of items to filter vendor offers by
 *    responses:
 *      '200':
 *        description: A list of vendor offers
 *      '400':
 *        description: Cannot specify both Item and Items
 */
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

/**
 * @swagger
 * /vendoroffers/{vendorOffer}:
 *  get:
 *    description: Get a vendor offer by name or id
 *    parameters:
 *      - in: path
 *        name: vendorOffer
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the vendor offer
 *    responses:
 *      '200':
 *        description: The vendor offer
 *      '404':
 *        description: Vendor offer not found
 */
app.get('/vendoroffers/:vendorOffer', async (req, res) => {
  let result = await db.getVendorOffer(req.params.vendorOffer);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /weaponamplifiers:
 *  get:
 *    description: Get all weapon amplifiers
 *    responses:
 *      '200':
 *        description: A list of weapon amplifiers
 */
app.get('/weaponamplifiers', async (req, res) => {
  res.json(await db.getWeaponAmplifiers());
});

/**
 * @swagger
 * /weaponamplifiers/{weaponAmplifier}:
 *  get:
 *    description: Get a weapon amplifier by name or id
 *    parameters:
 *      - in: path
 *        name: weaponAmplifier
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the weapon amplifier
 *    responses:
 *      '200':
 *        description: The weapon amplifier
 *      '404':
 *        description: Weapon amplifier not found
 */
app.get('/weaponamplifiers/:weaponAmplifier', async (req, res) => {
  let result = await db.getWeaponAmplifier(req.params.weaponAmplifier);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /weaponvisionattachments:
 *  get:
 *    description: Get all weapon vision attachments
 *    responses:
 *      '200':
 *        description: A list of weapon vision attachments
 */
app.get('/weaponvisionattachments', async (req, res) => {
  res.json(await db.getWeaponVisionAttachments());
});

/**
 * @swagger
 * /weaponvisionattachments:
 *  get:
 *    description: Get all weapon vision attachments
 *    responses:
 *      '200':
 *        description: A list of weapon vision attachments
 */
app.get('/weaponvisionattachments/:weaponVisionAttachment', async (req, res) => {
  let result = await db.getWeaponVisionAttachment(req.params.weaponVisionAttachment);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});

/**
 * @swagger
 * /weapons:
 *  get:
 *    description: Get all weapons
 *    responses:
 *      '200':
 *        description: A list of weapons
 */
app.get('/weapons', async (req, res) => {
  res.json(await db.getWeapons());
});

/**
 * @swagger
 * /weapons/{weapon}:
 *  get:
 *    description: Get a weapon by name or id
 *    parameters:
 *      - in: path
 *        name: weapon
 *        schema:
 *          type: string
 *        required: true
 *        description: The name or id of the weapon
 *    responses:
 *      '200':
 *        description: The weapon
 *      '404':
 *        description: Weapon not found
 */
app.get('/weapons/:weapon', async (req, res) => {
  let result = await db.getWeapon(req.params.weapon);

  if (result) {
    res.json(result);
  }
  else {
    res.status(404).send();
  }
});
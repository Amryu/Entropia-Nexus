// Compose all endpoint registrars here
const locations = require('./locations');
const planets = require('./planets');
const apartments = require('./apartments');
const shops = require('./shops');
const items = require('./items');
const teleporters = require('./teleporters');
const search = require('./search');
const blueprintbooks = require('./blueprintbooks');
const blueprints = require('./blueprints');
const refining = require('./refining');
const vendors = require('./vendors');
const vendoroffers = require('./vendoroffers');
const missions = require('./missions');
const missionchains = require('./missionchains');
const events = require('./events');
const blueprintdrops = require('./blueprintdrops');
const materials = require('./materials');
const medicalchips = require('./medicalchips');
const medicaltools = require('./medicaltools');
const mindforce = require('./mindforce');
const effects = require('./effects');
const enhancers = require('./enhancers');
const effectchips = require('./effectchips');
const finders = require('./finders');
const finderamplifiers = require('./finderamplifiers');
const scanners = require('./scanners');
const excavators = require('./excavators');
const equipsets = require('./equipsets');
const clothings = require('./clothings');
const consumables = require('./consumables');
const capsules = require('./capsules');
const decorations = require('./decorations');
const furniture = require('./furniture');
const armorplatings = require('./armorplatings');
const armorsets = require('./armorsets');
const armors = require('./armors');
const weaponamplifiers = require('./weaponamplifiers');
const teleportationchips = require('./teleportationchips');
const professions = require('./professions');
const professioncategories = require('./professioncategories');
const skills = require('./skills');
const skillcategories = require('./skillcategories');
const refiners = require('./refiners');
const acquisition = require('./acquisition');
const usage = require('./usage');
const enumerations = require('./enumerations');
const audit = require('./audit');
const entitychanges = require('./entitychanges');
const recurringevents = require('./recurringevents');
// Newly added (migration phase 3)
let absorbers, misctools, signs, strongboxes, storagecontainers, vehicleattachmenttypes, vehicles, weaponvisionattachments, weapons, tiers, pets, mobloots, mobmaturities, mobspecies, mobs, fish, fishingrods, fishingreels, fishingblanks, fishinglines, fishinglures;
try { absorbers = require('./absorbers'); } catch {}
try { misctools = require('./misctools'); } catch {}
try { signs = require('./signs'); } catch {}
try { strongboxes = require('./strongboxes'); } catch {}
try { storagecontainers = require('./storagecontainers'); } catch {}
try { vehicleattachmenttypes = require('./vehicleattachmenttypes'); } catch {}
try { vehicles = require('./vehicles'); } catch {}
try { weaponvisionattachments = require('./weaponvisionattachments'); } catch {}
try { weapons = require('./weapons'); } catch {}
try { tiers = require('./tiers'); } catch {}
try { pets = require('./pets'); } catch {}
try { mobloots = require('./mobloots'); } catch {}
try { mobmaturities = require('./mobmaturities'); } catch {}
try { mobspecies = require('./mobspecies'); } catch {}
try { mobs = require('./mobs'); } catch {}
try { fish = require('./fish'); } catch {}
try { fishingrods = require('./fishingrods'); } catch {}
try { fishingreels = require('./fishingreels'); } catch {}
try { fishingblanks = require('./fishingblanks'); } catch {}
try { fishinglines = require('./fishinglines'); } catch {}
try { fishinglures = require('./fishinglures'); } catch {}

function registerAll(app){
  // Order can matter for overlapping paths; keep generic last
  locations.register(app);
  planets.register(app);
  apartments.register(app);
  shops.register(app);
  teleporters.register(app);
  search.register(app);
  items.register(app);
  blueprintbooks.register(app);
  blueprints.register(app);
  refining.register(app);
  vendors.register(app);
  vendoroffers.register(app);
  missions.register(app);
  missionchains.register(app);
  events.register(app);
  blueprintdrops.register(app);
  materials.register(app);
  medicalchips.register(app);
  medicaltools.register(app);
  mindforce.register(app);
  effects.register(app);
  enhancers.register(app);
  effectchips.register(app);
  finders.register(app);
  finderamplifiers.register(app);
  scanners.register(app);
  excavators.register(app);
  equipsets.register(app);
  clothings.register(app);
  consumables.register(app);
  capsules.register(app);
  decorations.register(app);
  furniture.register(app);
  // register split armor endpoints
  armorplatings.register(app);
  armorsets.register(app);
  armors.register(app);
  weaponamplifiers.register(app);
  teleportationchips.register(app);
  professioncategories.register(app);
  professions.register(app);
  skillcategories.register(app);
  skills.register(app);
  refiners.register(app);
  acquisition.register(app);
  usage.register(app);
  enumerations.register(app);
  audit.register(app);
  entitychanges.register(app);
  recurringevents.register(app);
  // Conditionally register new modules if present
  absorbers?.register(app);
  misctools?.register(app);
  signs?.register(app);
  strongboxes?.register(app);
  storagecontainers?.register(app);
  vehicleattachmenttypes?.register(app);
  vehicles?.register(app);
  weaponvisionattachments?.register(app);
  weapons?.register(app);
  tiers?.register(app);
  pets?.register(app);
  mobloots?.register(app);
  mobmaturities?.register(app);
  mobspecies?.register(app);
  mobs?.register(app);
  fish?.register(app);
  fishingrods?.register(app);
  fishingreels?.register(app);
  fishingblanks?.register(app);
  fishinglines?.register(app);
  fishinglures?.register(app);
}

module.exports = { registerAll };

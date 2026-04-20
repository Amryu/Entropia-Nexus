// 101-fish catalog, extracted from the in-game files via
// `Entropia Universe - Fish Catalog.md`. Consumed by
// `seed-fish-catalog.mjs`.
//
// Field key:
//   name       — fish name (Fish.Name, also used as Materials name)
//   family     — MobSpecies.Name (Cod, Carp, Eel, Tuna, Pike, Bass,
//                Catfish, Salmon, Sturgeon, Swordfish)
//
// The source catalog also lists a "Baitfish" row with family "(misc)".
// It isn't a fish species — it's a bait/junk catch item shared across
// all tools — and it's intentionally excluded from the seed here.
//   tier       — catalog tier 0..3, mapped to Difficulty enum:
//                0=Easy, 1=Medium, 2=Hard, 3=Very Hard
//   weight     — rarity weight (all catches of a fish share the same
//                weight in the source data, so one column is enough)
//   minDepth   — min lure depth in metres (catalog "min lure depth")
//   strength   — catalog "fish strength"
//   timeStart/End — spawn window fractions of the day cycle, or null
//                for "all day" (we map "all day" to [0,1])
//   rods       — DB FishingRodType values (catalog tools remapped:
//                Deep Ocean -> Deep Ocean Fishing)
//   waters     — DB FishBiome values (catalog waters remapped:
//                Ocean -> Sea, DeepOcean -> Deep Ocean)
//   planets    — planet Names (matched against Planets.Name)

export const CATALOG = [
  { name: "Juvenile Calypsocod",           family: "Cod",       tier: 0, weight: 1,     minDepth: 5,   strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Blue Snapper",                  family: "Cod",       tier: 0, weight: 0.75,  minDepth: 8,   strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso","Setesh","ARIS","Rocktropia"] },
  { name: "Chud's Snapper",                family: "Cod",       tier: 0, weight: 0.75,  minDepth: 12,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Deep Ocean Fishing"],              waters: ["Deep Ocean"],            planets: ["Calypso"] },
  { name: "Rusty's Shortfin",              family: "Cod",       tier: 0, weight: 0.7,   minDepth: 10,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Pulsing Snapper",               family: "Cod",       tier: 0, weight: 0.5,   minDepth: 20,  strength: 2,    timeStart: 0.25, timeEnd: 0.75, rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Half Moon Longmouth",           family: "Cod",       tier: 1, weight: 0.4,   minDepth: 25,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Coastal Hookmouth",             family: "Cod",       tier: 1, weight: 0.4,   minDepth: 30,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["Calypso"] },
  { name: "Mutated Blue Snapper",          family: "Cod",       tier: 1, weight: 0.25,  minDepth: 45,  strength: 2.5,  timeStart: 0.75, timeEnd: 0.25, rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Electroscale Longmouth",        family: "Cod",       tier: 2, weight: 0.1,   minDepth: 55,  strength: 2.5,  timeStart: 0.25, timeEnd: 0.75, rods: ["Deep Ocean Fishing"],              waters: ["Deep Ocean"],            planets: ["Calypso"] },
  { name: "Atlantis Cod",                  family: "Cod",       tier: 3, weight: 0.05,  minDepth: 85,  strength: 3,    timeStart: 0,    timeEnd: 1,    rods: ["Deep Ocean Fishing"],              waters: ["Deep Ocean"],            planets: ["Calypso"] },

  { name: "Dullshine Floaty",              family: "Carp",      tier: 0, weight: 0.6,   minDepth: 5,   strength: 1.5,  timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso","Setesh","ARIS","Rocktropia"] },
  { name: "Juvenile Crystal Grouper",      family: "Carp",      tier: 0, weight: 0.4,   minDepth: 15,  strength: 1.5,  timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Bluescale Carp",                family: "Carp",      tier: 0, weight: 0.25,  minDepth: 25,  strength: 1.5,  timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Sapphire Carp",                 family: "Carp",      tier: 1, weight: 0.2,   minDepth: 35,  strength: 1.5,  timeStart: 0.25, timeEnd: 0.75, rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Emerald Carp",                  family: "Carp",      tier: 1, weight: 0.12,  minDepth: 35,  strength: 1.5,  timeStart: 0,    timeEnd: 0.25, rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Ruby Carp",                     family: "Carp",      tier: 1, weight: 0.12,  minDepth: 40,  strength: 1.5,  timeStart: 0.75, timeEnd: 0,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Crystal Grouper",               family: "Carp",      tier: 2, weight: 0.1,   minDepth: 70,  strength: 1.5,  timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Bloodscale Hunter",             family: "Carp",      tier: 2, weight: 0.1,   minDepth: 75,  strength: 1.5,  timeStart: 0.85, timeEnd: 0.15, rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["ARIS"] },
  { name: "Whirlpool Swallower",           family: "Carp",      tier: 3, weight: 0.05,  minDepth: 80,  strength: 1.75, timeStart: 0.4,  timeEnd: 0.6,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Ancient Crystal Grouper",       family: "Carp",      tier: 3, weight: 0.02,  minDepth: 90,  strength: 1.75, timeStart: 0.3,  timeEnd: 0.8,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },

  { name: "Sweatsucker",                   family: "Eel",       tier: 0, weight: 0.5,   minDepth: 3,   strength: 1.5,  timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["River"],                 planets: ["Calypso","Next Island"] },
  { name: "Mutated Blooddrinker",          family: "Eel",       tier: 0, weight: 0.35,  minDepth: 20,  strength: 1.5,  timeStart: 0.7,  timeEnd: 0.2,  rods: ["Angling","Fly Fishing"],           waters: ["River","Lake"],          planets: ["Setesh"] },
  { name: "Terrormouth Youngling",         family: "Eel",       tier: 0, weight: 0.5,   minDepth: 10,  strength: 1.5,  timeStart: 0.7,  timeEnd: 0.2,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Chemscale Stalker",             family: "Eel",       tier: 0, weight: 0.2,   minDepth: 35,  strength: 1.5,  timeStart: 0.7,  timeEnd: 0.2,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Rocktropia"] },
  { name: "Ghostfin Ringmouth",            family: "Eel",       tier: 1, weight: 0.35,  minDepth: 30,  strength: 1.5,  timeStart: 0.7,  timeEnd: 0.2,  rods: ["Angling"],                         waters: ["River"],                 planets: ["ARIS"] },
  { name: "Scyllian Eel",                  family: "Eel",       tier: 1, weight: 0.1,   minDepth: 30,  strength: 1.5,  timeStart: 0.7,  timeEnd: 0.2,  rods: ["Angling","Fly Fishing"],           waters: ["River","Lake"],          planets: ["Calypso"] },
  { name: "Stalking Terrormouth",          family: "Eel",       tier: 1, weight: 0.15,  minDepth: 45,  strength: 1.5,  timeStart: 0.7,  timeEnd: 0.2,  rods: ["Angling"],                         waters: ["River"],                 planets: ["Calypso"] },
  { name: "Spawn of Jormungandr",          family: "Eel",       tier: 1, weight: 0.08,  minDepth: 60,  strength: 1.25, timeStart: 0.7,  timeEnd: 0.2,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Charybdis Eel",                 family: "Eel",       tier: 1, weight: 0.01,  minDepth: 95,  strength: 1.5,  timeStart: 0.8,  timeEnd: 0.2,  rods: ["Angling"],                         waters: ["River"],                 planets: ["Calypso"] },
  { name: "Jormungandr Eel",               family: "Eel",       tier: 3, weight: 0.005, minDepth: 90,  strength: 1.5,  timeStart: 0.9,  timeEnd: 0.1,  rods: ["Deep Ocean Fishing"],              waters: ["Deep Ocean"],            planets: ["Calypso"] },

  { name: "Twin-Eyed Broadfin",            family: "Tuna",      tier: 1, weight: 0.3,   minDepth: 25,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Jetfin Tuna",                   family: "Tuna",      tier: 1, weight: 0.35,  minDepth: 30,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["ARIS"] },
  { name: "Shoal Stalker Tuna",            family: "Tuna",      tier: 1, weight: 0.2,   minDepth: 35,  strength: 2,    timeStart: 0.2,  timeEnd: 0.7,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["ARIS"] },
  { name: "Snapjaw Tuna",                  family: "Tuna",      tier: 1, weight: 0.25,  minDepth: 45,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["Calypso"] },
  { name: "Thunderfin Tuna",               family: "Tuna",      tier: 1, weight: 0.2,   minDepth: 45,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["Calypso"] },
  { name: "Emberbelly Shortfin",           family: "Tuna",      tier: 2, weight: 0.1,   minDepth: 60,  strength: 2,    timeStart: 0.25, timeEnd: 0.8,  rods: ["Deep Ocean Fishing"],              waters: ["Deep Ocean"],            planets: ["Rocktropia"] },
  { name: "Swiftstrike Tuna",              family: "Tuna",      tier: 2, weight: 0.1,   minDepth: 50,  strength: 2.25, timeStart: 0.25, timeEnd: 0.8,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Rocktropia"] },
  { name: "Lurebane Striker",              family: "Tuna",      tier: 1, weight: 0.05,  minDepth: 75,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["Calypso"] },
  { name: "Whiplash Bigjaw",               family: "Tuna",      tier: 3, weight: 0.01,  minDepth: 90,  strength: 2,    timeStart: 0.25, timeEnd: 0.5,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Shoalswallower Tuna",           family: "Tuna",      tier: 3, weight: 0.01,  minDepth: 95,  strength: 2,    timeStart: 0,    timeEnd: 0.2,  rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["Calypso"] },

  { name: "Spawnhunter Longtooth",         family: "Pike",      tier: 0, weight: 0.5,   minDepth: 5,   strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso","Setesh","Next Island"] },
  { name: "Siltscale Pike",                family: "Pike",      tier: 0, weight: 0.3,   minDepth: 15,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Young Daggertooth",             family: "Pike",      tier: 0, weight: 0.3,   minDepth: 20,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Reedstalker Pike",              family: "Pike",      tier: 0, weight: 0.3,   minDepth: 20,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso","ARIS"] },
  { name: "Rusty's Pike",                  family: "Pike",      tier: 1, weight: 0.2,   minDepth: 25,  strength: 2,    timeStart: 0.25, timeEnd: 0.5,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Adult Longtooth",               family: "Pike",      tier: 1, weight: 0.2,   minDepth: 40,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso","Setesh"] },
  { name: "Mutated Longtooth",             family: "Pike",      tier: 1, weight: 0.1,   minDepth: 50,  strength: 2,    timeStart: 0.2,  timeEnd: 0.7,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Setesh"] },
  { name: "Old Daggertooth",               family: "Pike",      tier: 1, weight: 0.1,   minDepth: 60,  strength: 2,    timeStart: 0.2,  timeEnd: 0.7,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Ironscale Pike",                family: "Pike",      tier: 1, weight: 0.01,  minDepth: 75,  strength: 3,    timeStart: 0.2,  timeEnd: 0.7,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso","Rocktropia"] },
  { name: "Ol' Toothy",                    family: "Pike",      tier: 2, weight: 0.005, minDepth: 100, strength: 3,    timeStart: 0.3,  timeEnd: 0.5,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },

  { name: "Drainwater Bassling",           family: "Bass",      tier: 0, weight: 1,     minDepth: 1,   strength: 3,    timeStart: 0,    timeEnd: 1,    rods: ["Angling"],                         waters: ["River"],                 planets: ["Calypso","Setesh","ARIS","Rocktropia","Next Island"] },
  { name: "Juvenile Striped Basil Bass",   family: "Bass",      tier: 0, weight: 0.8,   minDepth: 6,   strength: 3,    timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso","Next Island"] },
  { name: "Calypso Smallmouth",            family: "Bass",      tier: 0, weight: 0.6,   minDepth: 8,   strength: 3,    timeStart: 0,    timeEnd: 1,    rods: ["Angling"],                         waters: ["River"],                 planets: ["Calypso"] },
  { name: "Striped Basil Bass",            family: "Bass",      tier: 0, weight: 0.6,   minDepth: 12,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Juvenile Largemouth",           family: "Bass",      tier: 0, weight: 0.6,   minDepth: 14,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Angling"],                         waters: ["River"],                 planets: ["Calypso"] },
  { name: "Lumiscale Bass",                family: "Bass",      tier: 1, weight: 0.4,   minDepth: 25,  strength: 2,    timeStart: 0.25, timeEnd: 0.8,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Adult Drainwater Bass",         family: "Bass",      tier: 1, weight: 0.4,   minDepth: 30,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Angling"],                         waters: ["River"],                 planets: ["Calypso","Setesh","ARIS","Rocktropia"] },
  { name: "Old Striped Basil Bass",        family: "Bass",      tier: 1, weight: 0.3,   minDepth: 30,  strength: 2,    timeStart: 0.3,  timeEnd: 0.7,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Upwater Largemouth",            family: "Bass",      tier: 2, weight: 0.1,   minDepth: 60,  strength: 2,    timeStart: 0.1,  timeEnd: 0.4,  rods: ["Angling"],                         waters: ["River"],                 planets: ["Calypso"] },
  { name: "Ancient Lumiscale Bass",        family: "Bass",      tier: 2, weight: 0.1,   minDepth: 75,  strength: 2,    timeStart: 0,    timeEnd: 1,    rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },

  { name: "Juvenile Spikefin Catfish",     family: "Catfish",   tier: 0, weight: 0.2,   minDepth: 20,  strength: 2,    timeStart: 0.75, timeEnd: 0.25, rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Mudstalking Lynxfish",          family: "Catfish",   tier: 1, weight: 0.15,  minDepth: 25,  strength: 2,    timeStart: 0.75, timeEnd: 0.25, rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Deep Sea Catfish",              family: "Catfish",   tier: 1, weight: 0.15,  minDepth: 50,  strength: 2,    timeStart: 0.75, timeEnd: 0.25, rods: ["Deep Ocean Fishing"],              waters: ["Deep Ocean"],            planets: ["Calypso"] },
  { name: "Spikefin Catfish",              family: "Catfish",   tier: 2, weight: 0.08,  minDepth: 50,  strength: 1.5,  timeStart: 0.75, timeEnd: 0.25, rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Corinthian Lynxfish",           family: "Catfish",   tier: 2, weight: 0.08,  minDepth: 55,  strength: 1.5,  timeStart: 0.75, timeEnd: 0.25, rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Longwhisker Catfish",           family: "Catfish",   tier: 2, weight: 0.08,  minDepth: 65,  strength: 1.5,  timeStart: 0.75, timeEnd: 0.25, rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Sea Leopardfish",               family: "Catfish",   tier: 2, weight: 0.05,  minDepth: 85,  strength: 1.5,  timeStart: 0.75, timeEnd: 0.25, rods: ["Deep Ocean Fishing"],              waters: ["Deep Ocean"],            planets: ["Calypso"] },
  { name: "Charybdis Catfish",             family: "Catfish",   tier: 1, weight: 0.05,  minDepth: 70,  strength: 1.5,  timeStart: 0.75, timeEnd: 0.25, rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "King Tigerfish",                family: "Catfish",   tier: 3, weight: 0.007, minDepth: 75,  strength: 2,    timeStart: 0.75, timeEnd: 0.25, rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Midnight Jaguarfish",           family: "Catfish",   tier: 3, weight: 0.002, minDepth: 100, strength: 2,    timeStart: 0.9,  timeEnd: 0.1,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },

  { name: "Juvenile Siltswimmer",          family: "Salmon",    tier: 0, weight: 0.6,   minDepth: 20,  strength: 2,    timeStart: 0.2,  timeEnd: 0.6,  rods: ["Angling"],                         waters: ["River"],                 planets: ["Calypso"] },
  { name: "Young Calypso Salmon",          family: "Salmon",    tier: 0, weight: 0.6,   minDepth: 25,  strength: 2,    timeStart: 0.2,  timeEnd: 0.6,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Juvenile Predatorfish",         family: "Salmon",    tier: 0, weight: 0.35,  minDepth: 35,  strength: 2,    timeStart: 0.2,  timeEnd: 0.6,  rods: ["Angling"],                         waters: ["River"],                 planets: ["Calypso"] },
  { name: "Seabed Salmon",                 family: "Salmon",    tier: 1, weight: 0.35,  minDepth: 40,  strength: 2,    timeStart: 0.2,  timeEnd: 0.6,  rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["Calypso"] },
  { name: "Adult Siltswimmer",             family: "Salmon",    tier: 1, weight: 0.25,  minDepth: 45,  strength: 2,    timeStart: 0.2,  timeEnd: 0.6,  rods: ["Angling"],                         waters: ["River"],                 planets: ["Calypso"] },
  { name: "Migrating Calypso Salmon",      family: "Salmon",    tier: 1, weight: 0.25,  minDepth: 50,  strength: 2,    timeStart: 0.2,  timeEnd: 0.6,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Abyssal Salmon",                family: "Salmon",    tier: 2, weight: 0.15,  minDepth: 65,  strength: 2,    timeStart: 0.2,  timeEnd: 0.6,  rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["ARIS"] },
  { name: "Seabed Stalker Salmon",         family: "Salmon",    tier: 1, weight: 0.15,  minDepth: 60,  strength: 2,    timeStart: 0.2,  timeEnd: 0.6,  rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["Calypso"] },
  { name: "Riverterror Predatorfish",      family: "Salmon",    tier: 3, weight: 0.005, minDepth: 85,  strength: 2,    timeStart: 0.2,  timeEnd: 0.6,  rods: ["Angling"],                         waters: ["River"],                 planets: ["Calypso"] },
  { name: "Hadesscale Salmon",             family: "Salmon",    tier: 3, weight: 0.01,  minDepth: 90,  strength: 2,    timeStart: 0.2,  timeEnd: 0.6,  rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["Calypso"] },

  { name: "Juvenile Calypso Sturgeon",     family: "Sturgeon",  tier: 1, weight: 0.15,  minDepth: 30,  strength: 1.5,  timeStart: 0.1,  timeEnd: 0.4,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Juvenile Saltscale Sturgeon",   family: "Sturgeon",  tier: 1, weight: 0.15,  minDepth: 35,  strength: 1.5,  timeStart: 0.5,  timeEnd: 0.8,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Atlantian Sturgeon",            family: "Sturgeon",  tier: 1, weight: 0.1,   minDepth: 35,  strength: 1.5,  timeStart: 0.1,  timeEnd: 0.4,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Glimmerroe Sturgeon",           family: "Sturgeon",  tier: 1, weight: 0.1,   minDepth: 45,  strength: 1.5,  timeStart: 0.5,  timeEnd: 0.8,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Calypso Sturgeon",              family: "Sturgeon",  tier: 2, weight: 0.05,  minDepth: 50,  strength: 1.5,  timeStart: 0.1,  timeEnd: 0.4,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Adult Saltscale Sturgeon",      family: "Sturgeon",  tier: 2, weight: 0.05,  minDepth: 60,  strength: 1.5,  timeStart: 0.5,  timeEnd: 0.8,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Mutated Atlantian Sturgeon",    family: "Sturgeon",  tier: 1, weight: 0.05,  minDepth: 60,  strength: 1.5,  timeStart: 0.1,  timeEnd: 0.4,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Ancient Calypso Sturgeon",      family: "Sturgeon",  tier: 2, weight: 0.025, minDepth: 70,  strength: 1.5,  timeStart: 0.1,  timeEnd: 0.4,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },
  { name: "Depthstalker Sturgeon",         family: "Sturgeon",  tier: 3, weight: 0.005, minDepth: 90,  strength: 2,    timeStart: 0.5,  timeEnd: 0.8,  rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["Setesh"] },
  { name: "Monstrous Diamondscale Sturgeon", family: "Sturgeon",tier: 3, weight: 0.001, minDepth: 100, strength: 2,    timeStart: 0.1,  timeEnd: 0.4,  rods: ["Fly Fishing"],                     waters: ["Lake"],                  planets: ["Calypso"] },

  { name: "Calypso Swordfish",             family: "Swordfish", tier: 2, weight: 0.08,  minDepth: 50,  strength: 2,    timeStart: 0.2,  timeEnd: 0.7,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Whetstone Swordfish",           family: "Swordfish", tier: 2, weight: 0.07,  minDepth: 55,  strength: 2,    timeStart: 0.3,  timeEnd: 0.8,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Deep Sea Swordfish",            family: "Swordfish", tier: 1, weight: 0.05,  minDepth: 70,  strength: 2,    timeStart: 0,    timeEnd: 0.5,  rods: ["Deep Ocean Fishing"],              waters: ["Deep Ocean"],            planets: ["Calypso"] },
  { name: "Striped Stilletosnout",         family: "Swordfish", tier: 2, weight: 0.04,  minDepth: 65,  strength: 2,    timeStart: 0.4,  timeEnd: 0.9,  rods: ["Casting","Deep Ocean Fishing"],    waters: ["Sea","Deep Ocean"],      planets: ["Setesh"] },
  { name: "Stygian Swordfish",             family: "Swordfish", tier: 2, weight: 0.04,  minDepth: 80,  strength: 2,    timeStart: 0.7,  timeEnd: 0.2,  rods: ["Deep Ocean Fishing"],              waters: ["Deep Ocean"],            planets: ["Calypso"] },
  { name: "Pyrotip Swordfish",             family: "Swordfish", tier: 2, weight: 0.02,  minDepth: 70,  strength: 2,    timeStart: 0.5,  timeEnd: 0,    rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Rocktropia"] },
  { name: "Brightspear Swordfish",         family: "Swordfish", tier: 3, weight: 0.005, minDepth: 80,  strength: 3,    timeStart: 0.2,  timeEnd: 0.7,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Monstrous Calypso Swordfish",   family: "Swordfish", tier: 3, weight: 0.005, minDepth: 85,  strength: 3,    timeStart: 0.6,  timeEnd: 0.1,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Calypso"] },
  { name: "Fencer of the Sea",             family: "Swordfish", tier: 3, weight: 0.003, minDepth: 90,  strength: 3,    timeStart: 0.8,  timeEnd: 0.3,  rods: ["Casting"],                         waters: ["Sea"],                   planets: ["Rocktropia"] },
  { name: "Exscaleibur Swordfish",         family: "Swordfish", tier: 3, weight: 0.001, minDepth: 100, strength: 3,    timeStart: 0.9,  timeEnd: 0.4,  rods: ["Deep Ocean Fishing"],              waters: ["Deep Ocean"],            planets: ["Calypso"] },

];

export const FAMILIES = [
  'Cod','Carp','Eel','Tuna','Pike','Bass','Catfish','Salmon',
  'Sturgeon','Swordfish'
];

export function tierToDifficulty(tier) {
  switch (tier) {
    case 0: return 'Easy';
    case 1: return 'Medium';
    case 2: return 'Hard';
    case 3: return 'Very Hard';
    default: return null;
  }
}

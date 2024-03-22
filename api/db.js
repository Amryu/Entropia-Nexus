const { Pool } = require('pg');
const pgp = require('pg-promise')();
const dbCredentials = require('./credentials');

const pool = new Pool(dbCredentials);

const idOffsets = {
  Materials:                1000000,
  Weapons:                  2000000,
  Armors:                   3000000,
  Tools:                    4000000,
  MedicalTools:             4100000,
  MiscTools:                4200000,
  Refiners:                 4300000,
  Scanners:                 4400000,
  Finders:                  4500000,
  Excavators:               4600000,
  BlueprintBooks:           4700000,
  MedicalChips:             4800000,
  TeleportationChips:       4810000,
  EffectChips:              4820000,
  Attachments:              5000000,
  WeaponAmplifiers:         5100000,
  WeaponVisionAttachments:  5200000,
  Absorbers:                5300000,
  FinderAmplifiers:         5400000,
  ArmorPlatings:            5500000,
  Enhancers:                5600000,
  MindforceImplants:        5700000,
  Blueprints:               6000000,
  Vehicles:                 7000000,
  Clothes:                  8000000,
  Furnishings:              9000000,
  Furniture:                9100000,
  Decorations:              9200000,
  StorageContainers:        9300000,
  Signs:                    9400000,
  Consumables:              10000000,
  Capsules:                 10100000,
  Pets:                     11000000
}

const queries = {
  // Maps & Locations
  Areas: 'SELECT "Areas".*, "Planets"."Name" AS "Planet" FROM "Areas" INNER JOIN "Planets" ON "Areas"."PlanetId" = "Planets"."Id"',
  Locations: 'SELECT "Locations".*, "Planets"."Name" AS "Planet" FROM "Locations" INNER JOIN "Planets" ON "Locations"."PlanetId" = "Planets"."Id"',
  Planets: 'SELECT * FROM "Planets"',
  Teleporters: 'SELECT "Teleporters".*, "Planets"."Name" AS "Planet" FROM "Teleporters" INNER JOIN "Planets" ON "Teleporters"."PlanetId" = "Planets"."Id"',

  // Items
  Items: 'SELECT * FROM "Items"',
  Absorbers: 'SELECT * FROM "Absorbers"',
  ArmorPlatings: 'SELECT * FROM "ArmorPlatings"',
  ArmorSets: 'SELECT "ArmorSets"."Id", "ArmorSets"."Name", "Durability", "Stab", "Cut", "Impact", "Penetration", "Shrapnel", "Burn", "Cold", "Acid", "Electric" FROM "ArmorSets"',
  Armors: 'SELECT "Armors"."Id", "Armors"."Name", "ArmorSets"."Name" AS "Set", "Gender", "Slot", "SetId", "Weight", "MaxTT", "MinTT", "Durability", "Stab", "Cut", "Impact", "Penetration", "Shrapnel", "Burn", "Cold", "Acid", "Electric" FROM "Armors" INNER JOIN "ArmorSets" ON "Armors"."SetId" = "ArmorSets"."Id"',
  BlueprintBooks: 'SELECT "BlueprintBooks"."Id", "BlueprintBooks"."Name", "PlanetId", "Planets"."Name" AS "Planet", "Weight", "Value" FROM "BlueprintBooks" INNER JOIN "Planets" ON "BlueprintBooks"."PlanetId" = "Planets"."Id"',
  Blueprints: 'SELECT "Blueprints".*, "BlueprintBooks"."Name" AS "Book", "BlueprintTypes"."Name" AS "Type", "Professions"."Name" AS "Profession", "Items"."Type" AS "ItemType", "Items"."Name" AS "Item" FROM "Blueprints" INNER JOIN "BlueprintBooks" ON "Blueprints"."BookId" = "BlueprintBooks"."Id" INNER JOIN "BlueprintTypes" ON "Blueprints"."TypeId" = "BlueprintTypes"."Id" INNER JOIN "Items" ON "Blueprints"."ItemId" = "Items"."Id" LEFT JOIN "Professions" ON "Professions"."Id" = "Blueprints"."ProfessionId"',
  Clothes: 'SELECT * FROM "Clothes"',
  Consumables: 'SELECT * FROM "Consumables"',
  CreatureControlCapsules: 'SELECT "CreatureControlCapsules".*, "Mobs"."Name" AS "Mob", "Professions"."Name" AS "Profession" FROM "CreatureControlCapsules" INNER JOIN "Mobs" ON "CreatureControlCapsules"."MobId" = "Mobs"."Id" INNER JOIN "Professions" ON "CreatureControlCapsules"."ScanningProfessionId" = "Professions"."Id"',
  Decorations: 'SELECT * FROM "Decorations"',
  EffectChips: 'SELECT "EffectChips".*, "Professions"."Name" AS "Profession", "Materials"."Name" AS "Ammo" FROM "EffectChips" INNER JOIN "Professions" ON "EffectChips"."ProfessionId" = "Professions"."Id" INNER JOIN "Materials" ON "EffectChips"."AmmoId" = "Materials"."Id"',
  Effects: 'SELECT * FROM "Effects"',
  Enhancers: 'SELECT "Enhancers".*, "EnhancerType"."Name" AS "Type", "EnhancerType"."Tool" AS "Tool" FROM "Enhancers" INNER JOIN "EnhancerType" ON "Enhancers"."TypeId" = "EnhancerType"."Id"',
  Excavators: 'SELECT * FROM "Excavators"',
  FinderAmplifiers: 'SELECT * FROM "FinderAmplifiers"',
  Finders: 'SELECT * FROM "Finders"',
  Furniture: 'SELECT "Furniture".*, "Planets"."Name" AS "Planet" FROM "Furniture" INNER JOIN "Planets" ON "Furniture"."PlanetId" = "Planets"."Id"',
  Materials: 'SELECT * FROM "Materials"',
  MedicalChips: 'SELECT "MedicalChips".*, "Materials"."Name" AS "Ammo" FROM "MedicalChips" INNER JOIN "Materials" ON "MedicalChips"."AmmoId" = "Materials"."Id"',
  MedicalTools: 'SELECT * FROM "MedicalTools"',
  MindforceImplants: 'SELECT * FROM "MindforceImplants"',
  MiscTools: 'SELECT "MiscTools".*, "Professions"."Name" AS "Profession" FROM "MiscTools" LEFT JOIN "Professions" ON "MiscTools"."ProfessionId" = "Professions"."Id"',
  MobLoots: 'SELECT "MobLoots".*, "Mobs"."Name" AS "Mob", "Mobs"."PlanetId", "MobMaturities"."Name" AS "Maturity", "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Planets"."Name" AS "Planet" FROM "MobLoots" INNER JOIN "Mobs" ON "MobLoots"."MobId" = "Mobs"."Id" INNER JOIN "Items" ON "MobLoots"."ItemId" = "Items"."Id" LEFT JOIN "MobMaturities" ON "MobLoots"."MaturityId" = "MobMaturities"."Id" LEFT JOIN "Planets" ON "Mobs"."PlanetId" = "Planets"."Id"',
  MobMaturities: 'SELECT "MobMaturities".*, "Mobs"."Name" AS "Mob" FROM "MobMaturities" INNER JOIN "Mobs" ON "MobMaturities"."MobId" = "Mobs"."Id"',
  MobSpawns: 'SELECT "MobSpawns".*, "Mobs"."Name" AS "Mob", "Locations"."Longitude" AS "Longitude", "Locations"."Latitude" AS "Latitude", "Locations"."Altitude" AS "Altitude" FROM "MobSpawns" INNER JOIN "Mobs" ON "MobSpawns"."MobId" = "Mobs"."Id" INNER JOIN "Locations" ON "MobSpawns"."LocationId" = "Locations"."Id"',
  MobSpecies: 'SELECT * FROM "MobSpecies"',
  Mobs: 'SELECT "Mobs".*, "MobSpecies"."Name" AS "Species", "Planets"."Name" AS "Planet", d."Name" AS "DefensiveProfession", s."Name" AS "ScanningProfession" FROM "Mobs" INNER JOIN "Planets" ON "Mobs"."PlanetId" = "Planets"."Id" LEFT JOIN "MobSpecies" ON "Mobs"."SpeciesId" = "MobSpecies"."Id" LEFT JOIN "Professions" d ON "Mobs"."DefensiveProfessionId" = d."Id" LEFT JOIN "Professions" s ON "Mobs"."ScanningProfessionId" = s."Id"',
  Pets: 'SELECT "Pets".*, "Planets"."Name" AS "Planet" FROM "Pets" INNER JOIN "Planets" ON "Pets"."PlanetId" = "Planets"."Id"',
  ProfessionCategories: 'SELECT * FROM "ProfessionCategories"',
  Professions: 'SELECT "Professions".*, "ProfessionCategories"."Name" AS "Category" FROM "Professions" INNER JOIN "ProfessionCategories" ON "Professions"."CategoryId" = "ProfessionCategories"."Id"',
  Refiners: 'SELECT * FROM "Refiners"',
  RefiningRecipes: 'SELECT "RefiningRecipes".*, "Items"."Name" AS "Product", "Items"."Type" AS "ProductType", "Items"."Value" AS "ProductValue" FROM "RefiningRecipes" INNER JOIN "Items" ON "RefiningRecipes"."ProductId" = "Items"."Id"',
  Scanners: 'SELECT * FROM "Scanners"',
  Signs: 'SELECT * FROM "Signs"',
  SkillCategories: 'SELECT * FROM "SkillCategories"',
  Skills: 'SELECT "Skills".*, "SkillCategories"."Name" AS "Category" FROM "Skills" INNER JOIN "SkillCategories" ON "Skills"."CategoryId" = "SkillCategories"."Id"',
  StorageContainers: 'SELECT "StorageContainers".*, "Planets"."Name" AS "Planet" FROM "StorageContainers" INNER JOIN "Planets" ON "StorageContainers"."PlanetId" = "Planets"."Id"',
  TeleportationChips: 'SELECT "TeleportationChips".*, "Professions"."Name" AS "Profession", "Materials"."Name" AS "Ammo" FROM "TeleportationChips" INNER JOIN "Professions" ON "TeleportationChips"."ProfessionId" = "Professions"."Id" INNER JOIN "Materials" ON "TeleportationChips"."AmmoId" = "Materials"."Id"',
  Tiers: 'SELECT * FROM (SELECT "Tiers".*, "Items"."Name" || \' Tier \' || "Tiers"."Tier" AS "Name", "Items"."Name" AS "Item" FROM "Tiers" INNER JOIN "Items" ON "Tiers"."ItemId" = "Items"."Id" WHERE "IsArmorSet" = 0 UNION ALL SELECT "Tiers".*, "ArmorSets"."Name" || \' Tier \' || "Tiers"."Tier" AS "Name", "ArmorSets"."Name" AS "Item" FROM "Tiers" INNER JOIN "ArmorSets" ON "Tiers"."ItemId" = "ArmorSets"."Id" WHERE "IsArmorSet" = 1)',
  VehicleAttachmentTypes: 'SELECT * FROM "VehicleAttachmentTypes"',
  Vehicles: 'SELECT "Vehicles".*, "Materials"."Name" AS "Fuel" FROM "Vehicles" INNER JOIN "Materials" ON "Vehicles"."FuelMaterialId" = "Materials"."Id"',
  Vendors: 'SELECT "Vendors".*, "Planets"."Name" AS "Planet" FROM "Vendors" INNER JOIN "Planets" ON "Vendors"."PlanetId" = "Planets"."Id"',
  VendorOffers: 'SELECT "VendorOffers".*, "Items"."Name" AS "Item", "Items"."Value" AS "ItemValue", "Items"."Type" AS "ItemType", "Vendors"."Name" AS "Vendor", "Vendors"."PlanetId" AS "PlanetId", "Planets"."Name" AS "Planet" FROM "VendorOffers" INNER JOIN "Items" ON "VendorOffers"."ItemId" = "Items"."Id" INNER JOIN "Vendors" ON "VendorOffers"."VendorId" = "Vendors"."Id" INNER JOIN "Planets" ON "Vendors"."PlanetId" = "Planets"."Id"',
  WeaponAmplifiers: 'SELECT * FROM "WeaponAmplifiers"',
  WeaponVisionAttachments: 'SELECT * FROM "WeaponVisionAttachments"',
  Weapons: 'SELECT "Weapons".*, "VehicleAttachmentTypes"."Name" AS "AttachmentType", "Materials"."Name" AS "Ammo", hit."Name" AS "ProfessionHit", dmg."Name" AS "ProfessionDmg" FROM "Weapons" LEFT JOIN "VehicleAttachmentTypes" ON "Weapons"."AttachmentTypeId" = "VehicleAttachmentTypes"."Id" LEFT JOIN "Materials" ON "Weapons"."AmmoId" = "Materials"."Id" LEFT JOIN "Professions" hit ON "Weapons"."ProfessionHitId" = hit."Id" LEFT JOIN "Professions" dmg ON "Weapons"."ProfessionDmgId" = dmg."Id"',
}

async function _getObject(idOrName, query, tableName, formatFunction, additionalDataFunction = null, idOffset = 0) {
  let { rows } = idOrName.match(/^\d+$/)
    ? await pool.query(`${query} WHERE ${tableName ? `"${tableName}".` : ''}"Id" = $1`, [idOrName])
    : await pool.query(`${query} WHERE ${tableName ? `"${tableName}".` : ''}"Name" = $1`, [idOrName]);

  return rows.length === 1
    ? additionalDataFunction !== null 
    ? Promise.resolve(formatFunction(rows[0], await additionalDataFunction([rows[0].Id + idOffset]))) 
    : Promise.resolve(formatFunction(rows[0]))
    : Promise.resolve(null);
}

async function _getObjects(query, formatFunction, additionalDataFunction = null, idOffset = 0) {
  let { rows } = await pool.query(query);

  let data = additionalDataFunction !== null
    ? await additionalDataFunction(rows.map(x => x.Id + idOffset))
    : null;

  return Promise.all(rows.map(x => data !== null
    ? Promise.resolve(formatFunction(x, data))
    : Promise.resolve(formatFunction(x))));
}

function _groupBy(arr, key) {
  return arr.reduce((acc, obj) => {
    let keyVal = obj[key];
    if (!acc[keyVal]) {
      acc[keyVal] = [];
    }
    acc[keyVal].push(obj);
    return acc;
  }, {});
}

async function _getEffectsOnUse(ids) {
  let { rows } = await pool.query(`SELECT "Effects"."Id", "Effects"."Name", "Effects"."Unit", "EffectsOnUse"."DurationSeconds", "EffectsOnUse"."Strength", "EffectsOnUse"."ItemId" FROM "EffectsOnUse" INNER JOIN "Effects" ON "EffectsOnUse"."EffectId" = "Effects"."Id" WHERE "EffectsOnUse"."ItemId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'ItemId');
}

async function _getEffectsOnEquip(ids) {
  let { rows } = await pool.query(`SELECT "Effects"."Id", "Effects"."Name", "Effects"."Unit", "EffectsOnEquip"."Strength", "EffectsOnEquip"."ItemId" FROM "EffectsOnEquip" INNER JOIN "Effects" ON "EffectsOnEquip"."EffectId" = "Effects"."Id" WHERE "EffectsOnEquip"."ItemId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'ItemId');
}

async function _getEffectsOnSetEquip(ids) {
  ids.map(x => x - idOffsets.Armors);

  let { rows } = await pool.query(`SELECT "Effects"."Id", "Effects"."Name", "Effects"."Unit", "EffectsOnSetEquip"."Strength", "EffectsOnSetEquip"."MinSetPieces", "Armors"."Id" AS "ItemId" FROM "EffectsOnSetEquip" INNER JOIN "Armors" ON "EffectsOnSetEquip"."SetId" = "Armors"."SetId" INNER JOIN "Effects" ON "EffectsOnSetEquip"."EffectId" = "Effects"."Id" WHERE "Armors"."Id" IN (${ids.join(',')})`);

  return _groupBy(rows, 'ItemId');
}

async function _getEffectsAll(ids) {
  return {
    OnUse: await _getEffectsOnUse(ids),
    OnEquip: await _getEffectsOnEquip(ids),
    OnSetEquip: await _getEffectsOnSetEquip(ids)
  }
}

function _formatEffectOnUse(x) {
  return {
    Name: x.Name,
    Values: {
      DurationSeconds: x.DurationSeconds !== null ? Number(x.DurationSeconds) : null,
      Strength: x.Strength !== null ? Number(x.Strength) : null,
      Unit: x.Unit
    },
    Links: {
      "$Url": `/effects/${x.Id}`
    }
  }
}

function _formatEffectOnEquip(x) {
  return {
    Name: x.Name,
    Values: {
      Strength: x.Strength !== null ? Number(x.Strength) : null,
      Unit: x.Unit
    },
    Links: {
      "$Url": `/effects/${x.Id}`
    }
  }
}

function _formatEffectOnSetEquip(x) {
  return {
    Name: x.Name,
    Values: {
      Strength: x.Strength !== null ? Number(x.Strength) : null,
      MinSetPieces: x.MinSetPieces !== null ? Number(x.MinSetPieces) : null,
      Unit: x.Unit
    },
    Links: {
      "$Url": `/effects/${x.Id}`
    }
  }
}

async function search(search) {
  let query = `
    SELECT * FROM (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY "Type" ORDER BY "Id") as rn
      FROM (
        SELECT "Items"."Id" AS "Id", "Items"."Name" AS "Name", "Items"."Type" AS "Type",
          CASE
            WHEN "Items"."Type" = 'Weapon' THEN "Weapons"."Class"
            ELSE NULL
          END AS "SubType"
        FROM "Items"
        LEFT JOIN "Weapons" ON "Items"."Id" - ${idOffsets.Weapons} = "Weapons"."Id"
        UNION ALL
        SELECT "Mobs"."Id" + 1000000000 AS "Id", "Mobs"."Name" AS "Name", 'Mob' AS "Type", "Planets"."Name" AS "SubType" FROM "Mobs" INNER JOIN "Planets" ON "Mobs"."PlanetId" = "Planets"."Id")
      WHERE "Name" ILIKE $1
    ) x
    WHERE rn <= 5
    LIMIT 20
  `;

  let { rows } = await pool.query(query, [`%${search}%`]);

  return rows.map(formatSearchResult);
}

function formatSearchResult(x) {
  return {
    Name: x.Name,
    Type: x.Type,
    SubType: x.SubType
  }
}

// Areas
async function getAreas(planets = null) {
  let whereClause = '';

  if (planets != null && planets.length > 0) {
    whereClause = pgp.as.format('WHERE "Planets"."Name" IN ($1:csv)', [planets]);
  }

  return _getObjects(queries.Areas + whereClause, formatArea);
}

async function getArea(idOrName) {
  return _getObject(idOrName, queries.Areas, 'Areas', formatArea);
}

function formatArea(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Type: x.Type,
      Shape: x.Shape,
      Data: x.Data,
      Coordinates: {
        Longitude: x.Longitude,
        Latitude: x.Latitude,
        Altitude: x.Altitude
      }
    },
    Planet: {
      Name: x.Planet,
      Links: {
        "$Url": `/planets/${x.PlanetId}`
      }
    },
    Links: {
      "$Url": `/areas/${x.Id}`
    }
  }
}

// Locations
async function getLocations(planets = null) {
  let whereClause = '';

  if (planets != null && planets.length > 0) {
    whereClause = pgp.as.format('WHERE "Planets"."Name" IN ($1:csv)', [planets]);
  }

  return _getObjects(queries.Locations + whereClause, formatLocation);
}

async function getLocation(idOrName) {
  return _getObject(idOrName, queries.Locations, 'Locations', formatLocation);
}

function formatLocation(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Type: x.Type,
      Coordinates: {
        Longitude: x.Longitude,
        Latitude: x.Latitude,
        Altitude: x.Altitude
      }
    },
    Planet: {
      Name: x.Planet,
      Links: {
        "$Url": `/planets/${x.PlanetId}`
      }
    },
    Links: {
      "$Url": `/locations/${x.Id}`
    }
  }
}

// Planets
async function getPlanets() {
  return _getObjects(queries.Planets, formatPlanet);
}

async function getPlanet(idOrName) {
  return _getObject(idOrName, queries.Planets, 'Planets', formatPlanet);
}

function formatPlanet(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      TechnicalName: x.TechnicalName,
      Map: {
        X: x.X,
        Y: x.Y,
        Width: x.Width,
        Height: x.Height
      }
    },
    Links: {
      "$Url": `/planets/${x.Id}`
    }
  }
}

// Teleporters
async function getTeleporters() {
  return _getObjects(queries.Teleporters, formatTeleporter);
}

async function getTeleporter(idOrName) {
  return _getObject(idOrName, queries.Teleporters, 'Teleporters', formatTeleporter);
}

function formatTeleporter(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Coordinates: {
        Longitude: x.Longitude,
        Latitude: x.Latitude,
        Altitude: x.Altitude
      }
    },
    Planet: {
      Name: x.Planet,
      Links: {
        "$Url": `/planets/${x.PlanetId}`
      }
    },
    Links: {
      "$Url": `/teleporters/${x.Id}`
    }
  }
}

// Items
async function getItems() {
  let { rows } = await pool.query(queries.Items);

  return rows.map(formatItem);
}

async function getItem(idOrName) {
  return _getObject(idOrName, queries.Items, 'Items', formatItem);
}

function formatItem(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Type: x.Type,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: {
        Value: x.MaxTT !== null ? Number(x.MaxTT) : null,
      }
    },
    Links: {
      "$Url": `/${x.Type.toLowerCase()}s/${x.Id % 100000}`
    }
  }
}

// Absorbers
async function getAbsorbers() {
  let { rows } = await pool.query(queries.Absorbers);

  return rows.map(formatAbsorber);
}

async function getAbsorber(idOrName) {
  return _getObject(idOrName, queries.Absorbers, 'Absorbers', formatAbsorber);
}

function formatAbsorber(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Absorbers,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: {
        Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Absorption: x.Absorption !== null ? Number(x.Absorption) : null,
      }
    },
    Links: {
      "$Url": `/absorbers/${x.Id}`
    }
  }
}

// ArmorPlatings
async function getArmorPlatings() {
  return _getObjects(queries.ArmorPlatings, formatArmorPlating);
}

async function getArmorPlating(idOrName) {
  return _getObject(idOrName, queries.ArmorPlatings, 'ArmorPlatings', formatArmorPlating);
}

function formatArmorPlating(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.ArmorPlatings,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Durability: x.Durability !== null ? Number(x.Durability) : null,
      },
      Defense: {
        Block: x.Block !== null ? Number(x.Block) : null,
        Stab: x.Stab !== null ? Number(x.Stab) : null,
        Cut: x.Cut !== null ? Number(x.Cut) : null,
        Impact: x.Impact !== null ? Number(x.Impact) : null,
        Penetration: x.Penetration !== null ? Number(x.Penetration) : null,
        Shrapnel: x.Shrapnel !== null ? Number(x.Shrapnel) : null,
        Burn: x.Burn !== null ? Number(x.Burn) : null,
        Cold: x.Cold !== null ? Number(x.Cold) : null,
        Acid: x.Acid !== null ? Number(x.Acid) : null,
        Electric: x.Electric !== null ? Number(x.Electric) : null,
      }
    },
    Links: {
      "$Url": `/armorplatings/${x.Id}`
    }
  }
}

// ArmorSets
async function getArmorSets() {
  return _getObjects(queries.ArmorSets, formatArmorSet, _getArmorSetPiecesAndEffects);
}

async function getArmorSet(idOrName) {
  return _getObject(idOrName, queries.ArmorSets, 'ArmorSets', formatArmorSet, _getArmorSetPiecesAndEffects);
}
 
async function _getArmorSetPiecesAndEffects(setIds) {
  let { rows: armors } = await pool.query(`SELECT * FROM "Armors" WHERE "SetId" IN (${setIds.join(',')})`);
  let { rows: effects } = await pool.query(`SELECT "Effects"."Id", "Effects"."Name", "Effects"."Unit", "EffectsOnSetEquip"."Strength", "EffectsOnSetEquip"."MinSetPieces", "EffectsOnSetEquip"."SetId" FROM "EffectsOnSetEquip" INNER JOIN "Effects" ON "EffectsOnSetEquip"."EffectId" = "Effects"."Id" WHERE "EffectsOnSetEquip"."SetId" IN (${setIds.join(',')})`);

  return {
    Armors: _groupBy(armors, 'SetId'),
    Effects: _groupBy(effects, 'SetId'),
  }
}

async function formatArmorSet(x, data) {
  let armorPieces = (data.Armors[x.Id] ?? []).map(_formatArmorSmall);

  let maleSet = armorPieces.filter(y => y.Properties.Gender === 'Male' || y.Properties.Gender === 'Both');

  let effects = (data.Effects[x.Id] ?? []).map(_formatEffectOnSetEquip);

  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Weight: maleSet.map(y => y.Properties.Weight).reduce((a, b) => a + Number(b), 0) ?? null,
      Economy: {
        MaxTT: maleSet.map(y => y.Properties.Economy.MaxTT).reduce((a, b) => a + Number(b), 0) ?? null,
        MinTT: maleSet.map(y => y.Properties.Economy.MinTT).reduce((a, b) => a + Number(b), 0) ?? null,
        Durability: x.Durability !== null ? Number(x.Durability) : null,
      },
      Defense: {
        Stab: x.Stab !== null ? Number(x.Stab) : null,
        Cut: x.Cut !== null ? Number(x.Cut) : null,
        Impact: x.Impact !== null ? Number(x.Impact) : null,
        Penetration: x.Penetration !== null ? Number(x.Penetration) : null,
        Shrapnel: x.Shrapnel !== null ? Number(x.Shrapnel) : null,
        Burn: x.Burn !== null ? Number(x.Burn) : null,
        Cold: x.Cold !== null ? Number(x.Cold) : null,
        Acid: x.Acid !== null ? Number(x.Acid) : null,
        Electric: x.Electric !== null ? Number(x.Electric) : null,
      }
    },
    EffectsOnSetEquip: effects,
    Armors: armorPieces,
    Links: {
      "$Url": `/armorsets/${x.Id}`
    }
  }
}

function _formatArmorSmall(x) {
  return {
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Gender: x.Gender,
      Slot: x.Slot,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
      }
    },
    Links: {
      "$Url": `/armors/${x.Id}`
    }
  }
}

// Armors
async function getArmors() {
  return _getObjects(queries.Armors, formatArmor);
}

async function getArmor(idOrName) {
  return _getObject(idOrName, queries.Armors, 'Armors', formatArmor);
}

function formatArmor(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Armors,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Gender: x.Gender,
      Slot: x.Slot,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Durability: x.Durability !== null ? Number(x.Durability) : null,
      },
      Defense: {
        Stab: x.Stab !== null ? Number(x.Stab) : null,
        Cut: x.Cut !== null ? Number(x.Cut) : null,
        Impact: x.Impact !== null ? Number(x.Impact) : null,
        Penetration: x.Penetration !== null ? Number(x.Penetration) : null,
        Shrapnel: x.Shrapnel !== null ? Number(x.Shrapnel) : null,
        Burn: x.Burn !== null ? Number(x.Burn) : null,
        Cold: x.Cold !== null ? Number(x.Cold) : null,
        Acid: x.Acid !== null ? Number(x.Acid) : null,
        Electric: x.Electric !== null ? Number(x.Electric) : null,
      }
    },
    Set: {
      Name: x.Set,
      Links: {
        "$Url": `/armorsets/${x.SetId}`
      }
    },
    Links: {
      "$Url": `/armors/${x.Id}`,
    }
  }
}

// BlueprintBooks
async function getBlueprintBooks() {
  return _getObjects(queries.BlueprintBooks, formatBlueprintBook);
}

async function getBlueprintBook(idOrName) {
  return _getObject(idOrName, queries.BlueprintBooks, 'BlueprintBooks', formatBlueprintBook);
}

function formatBlueprintBook(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.BlueprintBooks,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: {
        Value: x.Value !== null ? Number(x.Value) : null,
      }
    },
    Planet: {
      Name: x.Planet,
      Links: {
        "$Url": `/planets/${x.PlanetId}`
      }
    },
    Links: {
      "$Url": `/blueprintbooks/${x.Id}`
    }
  }
}

// Blueprints
async function getBlueprints(products = null) {
  let whereClause = '';

  if (products !== null) {
    whereClause = pgp.as.format(' WHERE "Items"."Name" IN ($1:csv)', [products.map(x => `${x}`)]);
  }

  return _getObjects(queries.Blueprints + whereClause, formatBlueprint, getBlueprintIngredients);
}

async function getBlueprint(idOrName) {
  return _getObject(idOrName, queries.Blueprints, 'Blueprints', formatBlueprint, getBlueprintIngredients);
}

async function getBlueprintIngredients(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "BlueprintId", "Name", "Amount", "ItemId", "Type", "Items"."Value" AS "Value", "Items"."Type" AS "ItemType" FROM "BlueprintMaterials" INNER JOIN "Items" ON "Items"."Id" = "BlueprintMaterials"."ItemId" WHERE "BlueprintId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'BlueprintId');
}

function formatBlueprint(x, ingredients) {
  let materials = (ingredients[x.Id] ?? []).map(_formatBlueprintMaterial);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Blueprints,
    Name: x.Name,
    Properties: {
      Type: x.Type,
      Level: x.Level !== null ? Number(x.Level) : null,
      IsBoosted: x.IsBoosted == 1,
      MinimumCraftAmount: x.MinimumCraftAmount !== null ? Number(x.MinimumCraftAmount) : null,
      MaximumCraftAmount: x.MaximumCraftAmount !== null ? Number(x.MaximumCraftAmount) : null,
      Skill: {
        LearningIntervalStart: x.MinLvl !== null ? Number(x.MinLvl) : null,
        LearningIntervalEnd:x.MaxLvl !== null ? Number(x.MaxLvl) : null,
        SiB: x.IsSib,
      }
    },
    Profession: {
      Name: x.Profession,
      Links: {
        "$Url": `/professions/${x.ProfessionId}`
      }
    },
    Book: {
      Name: x.Book,
      Links: {
        "$Url": `/blueprintbooks/${x.BookId}`
      }
    },
    Product: {
      Name: x.Item,
      Links: {
        "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}`
      }
    },
    Materials: materials,
    Links: {
      "$Url": `/blueprints/${x.Id}`,
    }
  }
}

function _formatBlueprintMaterial(x) {
  return {
    Amount: x.Amount,
    Item: {
      Name: x.Name,
      Properties: {
        Type: x.ItemType,
        Economy: {
          MaxTT: x.Value,
        }
      },
      Links: {
        "$Url": `/${x.Type.toLowerCase()}s/${x.ItemId % 100000}`
      }
    },
    Links: {
      "$Url": `/${x.Type.toLowerCase()}s/${x.ItemId % 100000}`
    }
  }
}

// Clothes
async function getClothes(idOrName = null) {
  if (idOrName !== null) {
    return _getObject(idOrName, queries.Clothes, 'Clothes', formatClothes);
  }
  else {
    return _getObjects(queries.Clothes, formatClothes);
  }
}

function formatClothes(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Clothes,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Gender: x.Gender,
      Type: x.Type,
      Slot: x.Slot,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null
      }
    },
    Links: {
      "$Url": `/clothes/${x.Id}`
    }
  }
}

// Consumables
async function getConsumables() {
  return _getObjects(queries.Consumables, formatConsumable, _getConsumableEffects);
}

async function getConsumable(idOrName) {
  return _getObject(idOrName, queries.Consumables, 'Consumables', formatConsumable, _getConsumableEffects);
}

async function _getConsumableEffects(ids) {
  let { rows } = await pool.query(`SELECT "Id", "Effects"."Name", "Effects"."Unit", "EffectsOnConsume"."DurationSeconds", "EffectsOnConsume"."Strength", "EffectsOnConsume"."ConsumableId", "Effects"."IsPositive" FROM "EffectsOnConsume" INNER JOIN "Effects" ON "EffectsOnConsume"."EffectId" = "Effects"."Id" WHERE "EffectsOnConsume"."ConsumableId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'ConsumableId');
}

async function formatConsumable(x, effects) {
  let formattedEffects = effects[x.Id].map(_formatEffectOnConsume);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Consumables,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Economy: {
        MaxTT: x.Value !== null ? Number(x.Value) : null,
      }
    },
    EffectsOnConsume: formattedEffects,
    Links: {
      "$Url": `/consumables/${x.Id}`
    }
  }
}

function _formatEffectOnConsume(x) {
  return {
    Name: x.Name,
    Values: {
      DurationSeconds: x.DurationSeconds !== null ? Number(x.DurationSeconds) : null,
      Strength: x.Strength !== null ? Number(x.Strength) : null,
      Unit: x.Unit,
      IsPositive: x.IsPositive === 1
    },
    Links: {
      "$Url": `/effects/${x.Id}`
    }
  }
}

// CreatureControlCapsules
async function getCreatureControlCapsules() {
  return _getObjects(queries.CreatureControlCapsules, formatCreatureControlCapsule);
}

async function getCreatureControlCapsule(idOrName) {
  return _getObject(idOrName, queries.CreatureControlCapsules, 'CreatureControlCapsules', formatCreatureControlCapsule);
}

function formatCreatureControlCapsule(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Capsules,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
      }
    },
    Profession: {
      Name: x.Profession,
      Links: {
        "$Url": `/professions/${x.ScanningProfessionId}`
      }
    },
    Mob: {
      Name: x.Mob,
      Links: {
        "$Url": `/mobs/${x.MobId}`,
      }
    },
    Links: {
      "$Url": `/creaturecontrolcapsules/${x.Id}`,
    }
  }
}

// Decorations
async function getDecorations() {
  return _getObjects(queries.Decorations, formatDecoration);
}

async function getDecoration(idOrName) {
  return _getObject(idOrName, queries.Decorations, 'Decorations', formatDecoration);
}

function formatDecoration(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Decorations,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
      }
    },
    Links: {
      "$Url": `/decorations/${x.Id}`
    }
  }
}

// EffectChips
async function getEffectChips() {
  return _getObjects(queries.EffectChips, formatEffectChip, _getEffectsOnUse);
}

async function getEffectChip(idOrName) {
  return _getObject(idOrName, queries.EffectChips, 'EffectChips', formatEffectChip, _getEffectsOnUse);
}

async function formatEffectChip(x, data) {
  let effects = (data[x.Id] ?? []).map(_formatEffectOnUse);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.EffectChips,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Range: x.Range !== null ? Number(x.Range) : null,
      Uses: x.Uses !== null ? Number(x.Uses) : null,
      Mindforce: {
        Level: x.Level !== null ? Number(x.Level) : null,
        Concentration: x.Concentration !== null ? Number(x.Concentration) : null,
        Cooldown: null,
        CooldownGroup: x.CooldownGroup !== null ? Number(x.CooldownGroup) : null,
      },
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null, 
        AmmoBurn: x.AmmoBurn !== null ? Number(x.AmmoBurn) : null,
      },
      Skill: {
        LearningIntervalStart: x.MinLevel !== null ? Number(x.MinLevel) : null,
        LearningIntervalEnd: x.MaxLevel !== null ? Number(x.MaxLevel) : null,
        IsSiB: true,
      }
    },
    Ammo: {
      Name: x.Ammo,
      Links: {
        "$Url": `/materials/${x.AmmoId}`
      }
    },
    Profession: {
      Name: x.Profession,
      Links: {
        "$Url": `/professions/${x.ProfessionId}`
      }
    },
    Effects: effects,
    Links: {
      "$Url": `/effectchips/${x.Id}`,
    }
  }
}

// Effects
async function getEffects() {
  return _getObjects(queries.Effects, formatEffect);
}

async function getEffect(idOrName) {
  return _getObject(idOrName, queries.Effects, 'Effects', formatEffect);
}

function formatEffect(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      IsPositive: x.IsPositive === 1
    },
    Links: {
      "$Url": `/effects/${x.Id}`
    }
  }
}

// Enhancers
async function getEnhancers() {
  return _getObjects(queries.Enhancers, formatEnhancer);
}

async function getEnhancer(idOrName) {
  return _getObject(idOrName, queries.Enhancers, 'Enhancers', formatEnhancer);
}

function formatEnhancer(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Enhancers,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Socket: x.Socket !== null ? Number(x.Socket) : null,
      Tool: x.Tool,
      Type: x.Type,
      Economy: {
        MaxTT: x.Value !== null ? Number(x.Value) : null,
      }
    },
    Links: {
      "$Url": `/enhancers/${x.Id}`
    }
  }
}

// Excavators
async function getExcavators() {
  return _getObjects(queries.Excavators, formatExcavator);
}

async function getExcavator(idOrName) {
  return _getObject(idOrName, queries.Excavators, 'Excavators', formatExcavator);
}

function formatExcavator(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Excavators,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
      Skill: {
        LearningIntervalStart: x.IntervalStart !== null ? Number(x.IntervalStart) : null,
        LearningIntervalEnd: x.IntervalEnd !== null ? Number(x.IntervalEnd) : null,
        IsSiB: true,
      }
    },
    Links: {
      "$Url": `/excavators/${x.Id}`,
    }
  }
}

// FinderAmplifiers
async function getFinderAmplifiers() {
  return _getObjects(queries.FinderAmplifiers, formatFinderAmplifier);
}

async function getFinderAmplifier(idOrName) {
  return _getObject(idOrName, queries.FinderAmplifiers, 'FinderAmplifiers', formatFinderAmplifier);
}

function formatFinderAmplifier(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.FinderAmplifiers,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: {
        Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
      Skill: {
        LearningIntervalStart: x.ProfessionMinimum !== null ? Number(x.ProfessionMinimum) : null,
        LearningIntervalEnd: x.ProfessionMinimum !== null ? Number(x.ProfessionMinimum) : null,
        IsSiB: false
      }
    },
    Links: {
      "$Url": `/finderamplifiers/${x.Id}`
    }
  }
}

// Finders
async function getFinders() {
  return _getObjects(queries.Finders, formatFinder);
}

async function getFinder(idOrName) {
  return _getObject(idOrName, queries.Finders, 'Finders', formatFinder);
}

function formatFinder(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Finders,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Depth: x.Depth !== null ? Number(x.Depth) : null,
      Range: x.Range !== null ? Number(x.Range) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
        AmmoBurn: x.Probes !== null ? Number(x.Probes) : null
      },
      Skill: {
        LearningIntervalStart: x.IntervalStart !== null ? Number(x.IntervalStart) : null,
        LearningIntervalEnd: x.IntervalEnd !== null ? Number(x.IntervalEnd) : null,
        IsSiB: true
      }
    },
    Links: {
      "$Url": `/finders/${x.Id}`
    }
  }
}

// Furniture
async function getFurniture(idOrName = null) {
  if (idOrName !== null) {
    return _getObject(idOrName, queries.Furniture, 'Furniture', formatFurniture);
  }
  else {
    return _getObjects(queries.Furniture, formatFurniture);
  }
}

function formatFurniture(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Furniture,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
      }
    },
    Planet: {
      Name: x.Planet,
      Links: {
        "$Url": `/planets/${x.PlanetId}`
      }
    },
    Links: {
      "$Url": `/furniture/${x.Id}`
    }
  }
}

// Materials
async function getMaterials() {
  return _getObjects(queries.Materials, formatMaterial);
}

async function getMaterial(idOrName) {
  return _getObject(idOrName, queries.Materials, 'Materials', formatMaterial);
}

function formatMaterial(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Type: x.Type,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: {
        MaxTT: x.Value !== null ? Number(x.Value) : null,
      }
    },
    Links: {
      "$Url": `/materials/${x.Id}`
    }
  }
}

// MedicalChips
async function getMedicalChips() {
  return _getObjects(queries.MedicalChips, formatMedicalChip, _getEffectsOnUse, idOffsets.MedicalChips);
}

async function getMedicalChip(idOrName) {
  return _getObject(idOrName, queries.MedicalChips, 'MedicalChips', formatMedicalChip, _getEffectsOnUse, idOffsets.MedicalChips);
}

function formatMedicalChip(x, data) {
  let effects = (data[x.Id + idOffsets.MedicalChips] ?? []).map(_formatEffectOnUse);
  
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MedicalChips,
    Name: x.Name,
    Properties: {
      Level: x.Level !== null ? Number(x.Level) : null,
      Range: x.Range !== null ? Number(x.Range) : null,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      MaxHeal: x.Heal !== null ? Number(x.Heal) : null,
      MinHeal: x.StartInterval !== null ? Number(x.StartInterval) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Concentration: x.Concentration !== null ? Number(x.Concentration) : null,
      Cooldown: x.Cooldown !== null ? Number(x.Cooldown) : null,
      CooldownGroup: x.CooldownGroup !== null ? Number(x.CooldownGroup) : null,
      Type: x.Type,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
        AmmoBurn: x.AmmoBurn !== null ? Number(x.AmmoBurn) : null
      },
      Skill: {
        LearningIntervalStart: x.MinLvl !== null ? Number(x.MinLvl) : null,
        LearningIntervalEnd: x.MaxLvl !== null ? Number(x.MaxLvl) : null,
        IsSiB: x.SiB === 1
      },
    },
    EffectsOnUse: effects,
    Ammo: {
      Name: x.Ammo,
      Links: {
        "$Url": `/materials/${x.AmmoId}`
      }
    },
    Links: {
      "$Url": `/medicalchips/${x.Id}`
    }
  }
}

// MedicalTools
async function getMedicalTools() {
  return _getObjects(queries.MedicalTools, formatMedicalTool, _getEffectsAll, idOffsets.MedicalTools);
}

async function getMedicalTool(idOrName) {
  return _getObject(idOrName, queries.MedicalTools, 'MedicalTools', formatMedicalTool, _getEffectsAll, idOffsets.MedicalTools);
}

function formatMedicalTool(x, data) {
  let effectsOnUse = (data.OnUse[x.Id + idOffsets.MedicalTools] ?? []).map(_formatEffectOnUse);
  let effectsOnEquip = (data.OnEquip[x.Id + idOffsets.MedicalTools] ?? []).map(_formatEffectOnEquip);
  let effectsOnSetEquip = (data.OnSetEquip[x.Id + idOffsets.MedicalTools] ?? []).map(_formatEffectOnSetEquip);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MedicalTools,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      MaxHeal: x.Heal !== null ? Number(x.Heal) : null,
      MinHeal: x.StartInterval !== null ? Number(x.StartInterval) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
      Skill: {
        LearningIntervalStart: x.MinLvl !== null ? Number(x.MinLvl) : null,
        LearningIntervalEnd: x.MaxLvl !== null ? Number(x.MaxLvl) : null,
        IsSiB: x.SIB === 1
      },
    },
    EffectsOnUse: effectsOnUse,
    EffectsOnEquip: effectsOnEquip,
    EffectsOnSetEquip: effectsOnSetEquip,
    Links: {
      "$Url": `/medicaltools/${x.Id}`
    }
  }
}

// MindforceImplants
async function getMindforceImplants() {
  return _getObjects(queries.MindforceImplants, formatMindforceImplant);
}

async function getMindforceImplant(idOrName) {
  return _getObject(idOrName, queries.MindforceImplants, 'MindforceImplants', formatMindforceImplant);
}

function formatMindforceImplant(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MindforceImplants,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      MaxProfessionLevel: x.MaxLvl !== null ? Number(x.MaxLvl) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Absorption: x.Absorption !== null ? Number(x.Absorption) : null,
      }
    },
    Links: {
      "$Url": `/mindforceimplants/${x.Id}`
    }
  }
}

// MiscTools
async function getMiscTools() {
  return _getObjects(queries.MiscTools, formatMiscTool);
}

async function getMiscTool(idOrName) {
  return _getObject(idOrName, queries.MiscTools, 'MiscTools', formatMiscTool);
}

function formatMiscTool(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MiscTools,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      }
    },
    Profession: {
      Name: x.Profession,
      Links: {
        "$Url": x.ProfessionId !== null ? `/professions/${x.ProfessionId}` : null
      }
    },
    Links: {
      "$Url": `/misctools/${x.Id}`
    }
  }
}

// MobLoots
async function getMobLoots(items = null, mobs = null) {
  let whereClause = '';

  if (items !== null) {
    whereClause += pgp.as.format(' WHERE "Items"."Name" IN ($1:csv)', [items.map(x => `${x}`)]);
  }

  if (mobs !== null) {
    whereClause += whereClause === '' ? ' WHERE' : ' AND';
    whereClause += pgp.as.format(' "Mobs"."Name" IN ($1:csv)', [mobs.map(x => `${x}`)]);
  }

  return _getObjects(queries.MobLoots + whereClause, formatMobLoot);
}

function formatMobLoot(x) {
  return {
    Mob: {
      Name: x.Mob,
      Planet: {
        Name: x.Planet,
        Links: {
          "$Url": `/planets/${x.PlanetId}`
        }
      },
      Links: {
        "$Url": `/mobs/${x.MobId}`
      }
    },
    Maturity: {
      Name: x.Maturity,
      Links: {
        "$Url": `/mobmaturities/${x.MaturityId}`
      }
    },
    Item: {
      Name: x.Item,
      Properties: {
        Type: x.ItemType,
      },
      Links: {
        "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}`
      }
    },
    Frequency: x.Frequency,
    LastVU: x.LastVU,
    IsEvent: x.IsEvent === 1,
    IsDropping: x.IsDropping === 1
  }
}

// MobMaturities
async function getMobMaturities(mob = null) {
  let whereClause = '';

  if (mob !== null) {
    whereClause = pgp.as.format(' WHERE "Mobs"."Name" = $1', mob);
  }

  return _getObjects(queries.MobMaturities + whereClause, formatMobMaturity, _getMobAttacks);
}

async function getMobMaturity(idOrName) {
  return _getObject(idOrName, queries.MobMaturities, 'MobMaturities', formatMobMaturity, _getMobAttacks);
}

async function _getMobAttacks(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT * FROM "MobAttacks" WHERE "MaturityId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'MaturityId');
}

function formatMobMaturity(x, data) {
  let attacks = (data[x.Id] ?? []).map(_formatMobAttack);

  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Health: x.Health !== null ? Number(x.Health) : null,
      AttacksPerMinute: x.AttackSpeed !== null ? Number(x.AttackSpeed) : null,
      Level: x.DangerLevel !== null ? Number(x.DangerLevel) : null,
      RegenerationInterval: x.RegenerationInterval !== null ? Number(x.RegenerationInterval) : null,
      RegenerationAmount: x.RegenerationAmount !== null ? Number(x.RegenerationAmount) : null,
      CriticalChance: x.CriticalChance !== null ? Number(x.CriticalChance) : null,
      Taming: {
        IsTameable: x.TamingLevel !== null,
        TamingLevel: x.TamingLevel !== null ? Number(x.TamingLevel) : null,
      },
      Attributes: {
        Strength: x.Strength !== null ? Number(x.Strength) : null,
        Agility: x.Agility !== null ? Number(x.Agility) : null,
        Intelligence: x.Intelligence !== null ? Number(x.Intelligence) : null,
        Psyche: x.Psyche !== null ? Number(x.Psyche) : null,
        Stamina: x.Stamina !== null ? Number(x.Stamina) : null,
      },
      Defenses: {
        Stab: x.ResistanceStab !== null ? Number(x.ResistanceStab) : null,
        Cut: x.ResistanceCut !== null ? Number(x.ResistanceCut) : null,
        Impact: x.ResistanceImpact !== null ? Number(x.ResistanceImpact) : null,
        Penetration: x.ResistancePenetration !== null ? Number(x.ResistancePenetration) : null,
        Shrapnel: x.ResistanceShrapnel !== null ? Number(x.ResistanceShrapnel) : null,
        Burn: x.ResistanceBurn !== null ? Number(x.ResistanceBurn) : null,
        Cold: x.ResistanceCold !== null ? Number(x.ResistanceCold) : null,
        Acid: x.ResistanceAcid !== null ? Number(x.ResistanceAcid) : null,
        Electric: x.ResistanceElectric !== null ? Number(x.ResistanceElectric) : null,
      }
    },
    Attacks: attacks,
    Mob: {
      Name: x.Mob,
      Links: {
        "$Url": `/mobs/${x.MobId}`
      }
    },
    Links: {
      "$Url": `/mobmaturities/${x.Id}`
    }
  }
}

function _formatMobAttack(x) {
  return {
    Name: x.Name,
    Stab: x.Stab !== null ? Number(x.Stab) : null,
    Cut: x.Cut !== null ? Number(x.Cut) : null,
    Impact: x.Impact !== null ? Number(x.Impact) : null,
    Penetration: x.Penetration !== null ? Number(x.Penetration) : null,
    Shrapnel: x.Shrapnel !== null ? Number(x.Shrapnel) : null,
    Burn: x.Burn !== null ? Number(x.Burn) : null,
    Cold: x.Cold !== null ? Number(x.Cold) : null,
    Acid: x.Acid !== null ? Number(x.Acid) : null,
    Electric: x.Electric !== null ? Number(x.Electric) : null,
    IsAoE: x.IsAoE === 1,
  }
}

// MobSpawns
async function getMobSpawns() {
  return _getObjects(queries.MobSpawns, formatMobSpawn);
}

function formatMobSpawn(x) {
  return {
    Id: x.Id,
    Description: x.Notes,
    Mob: {
      Name: x.Mob,
      Links: {
        "$Url": `/mobs/${x.MobId}`
      }
    },
    Location: {
      Longitude: x.Longitude !== null ? Number(x.Longitude) : null,
      Latitude: x.Latitude !== null ? Number(x.Latitude) : null,
      Altitude: x.Altitude !== null ? Number(x.Altitude) : null,
      Links: {
        "$Url": `/locations/${x.LocationId}`
      }
    },
    Maturity: {
      Name: x.Maturity,
      Links: {
        "$Url": `/mobmaturities/${x.MaturityId}`
      }
    },
    Density: x.Density,
    IsShared: x.IsShared === 1, 
    IsEvent: x.IsEvent === 1,
    Links: {
      "$Url": `/mobspawns/${x.Id}`
    }
  }
}

// MobSpecies
async function getMobSpecies(idOrName = null) {
  return idOrName !== null
    ? _getObject(idOrName, queries.MobSpecies, 'MobSpecies', formatMobSpecies)
    : _getObjects(queries.MobSpecies, formatMobSpecies);
}

function formatMobSpecies(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
        CodexBaseCost: x.CodexBaseCost !== null ? Number(x.CodexBaseCost) : null,
        IsCat4Codex: x.IsCat4Codex === 1,
    },
    Links: {
      "$Url": `/mobspecies/${x.Id}`
    }
  }
}

// Mobs
async function getMobs() {
  return _getObjects(queries.Mobs, formatMob);
}

async function getMob(idOrName) {
  return _getObject(idOrName, queries.Mobs, 'Mobs', formatMob);
}

function formatMob(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      AttacksPerMinute: x.AttackSpeed !== null ? Number(x.AttackSpeed) : null,
      AttackRange: x.Range !== null ? Number(x.Range) : null,
      AggressionRange: x.AggressionRange,
      IsSweatable: x.Sweatable === 1,
    },
    DefensiveProfession: {
      Name: x.DefensiveProfession,
      Links: {
        "$Url": `/professions/${x.DefensiveProfessionId}`
      }
    },
    ScanningProfession: {
      Name: x.ScanningProfession,
      Links: {
        "$Url": `/professions/${x.ScanningProfessionId}`
      }
    },
    Planet: {
      Name: x.Planet,
      Links: {
        "$Url": `/planets/${x.PlanetId}`
      }
    },
    Species: {
      Name: x.Species,
      Links: {
        "$Url": `/mobspecies/${x.SpeciesId}`
      }
    },
    Links: {
      "$Url": `/mobs/${x.Id}`
    }
  }
}

// Pets
async function getPets() {
  return _getObjects(queries.Pets, formatPet, _getPetEffects);
}

async function getPet(idOrName) {
  return _getObject(idOrName, queries.Pets, 'Pets', formatPet, _getPetEffects);
}

async function _getPetEffects(ids) {
  let { rows } = await pool.query(`SELECT "PetEffects".*, "Effects"."Id" AS "EffectId", "Effects"."Name" AS "EffectName", "Effects"."Unit" AS "Unit" FROM "PetEffects" INNER JOIN "Effects" ON "PetEffects"."EffectId" = "Effects"."Id" WHERE "PetEffects"."PetId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'PetId');
}

function formatPet(x, data) {
  let effects = (data[x.Id] ?? []).map(_formatPetEffect);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Pets,
    Name: x.Name,
    Properties: {
      Rarity: x.Rarity,
      TrainingDifficulty: x.Training,
      NutrioCapacity: x.NutrioCapacity !== null ? Number(x.NutrioCapacity) : null,
      NutrioConsumptionPerHour: x.NutrioConsumption !== null ? Number(x.NutrioConsumption) : null,
      ExportableLevel: x.Exportable !== null ? Number(x.Exportable) : null,
      TamingLevel: x.TamingLevel !== null ? Number(x.TamingLevel) : null,
      Description: x.Description
    },
    Planet: {
      Name: x.Planet,
      Links: {
        "$Url": `/planets/${x.PlanetId}`
      }
    },
    Effects: effects,
    Links: {
      "$Url": `/pets/${x.Id}`
    }
  }
}

function _formatPetEffect(x) {
  return {
    Id: x.EffectId,
    Name: x.EffectName,
    Properties: {
      Strength: x.Strength !== null ? Number(x.Strength) : null,
      Unit: x.Unit,
      NutrioConsumptionPerHour: x.Consumption !== null ? Number(x.Consumption) : null,
      Unlock: {
        Level: x.UnlockLevel !== null ? Number(x.UnlockLevel) : null,
        CostPED: x.UnlockPED !== null ? Number(x.UnlockPED) : null,
        CostEssence: x.UnlockEssence !== null ? Number(x.UnlockEssence) : null,
        CostRareEssence: x.UnlockRareEssence !== null ? Number(x.UnlockRareEssence) : null,
        Criteria: x.UnlockCriteria,
        CriteriaValue: x.UnlockCriteriaValue !== null ? Number(x.UnlockCriteriaValue) : null,
      }
    },
    Links: {
      "$Url": `/effects/${x.EffectId}`
    }
  }
}

// ProfessionCategories
async function getProfessionCategories() {
  return _getObjects(queries.ProfessionCategories, formatProfessionCategory);
}

async function getProfessionCategory(idOrName) {
  return _getObject(idOrName, queries.ProfessionCategories, 'ProfessionCategories', formatProfessionCategory);
}

function formatProfessionCategory(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Links: {
      "$Url": `/professioncategories/${x.Id}`
    }
  }
}

// Professions
async function getProfessions() {
  return _getObjects(queries.Professions, formatProfession, _getProfessionSkillsAndUnlocks);
}

async function getProfession(idOrName) {
  return _getObject(idOrName, queries.Professions, 'Professions', formatProfession, _getProfessionSkillsAndUnlocks);
}

async function _getProfessionSkillsAndUnlocks(ids) {
  let { rows: professionSkills } = await pool.query(`SELECT "ProfessionSkills"."Weight", "Skills"."Id" AS "SkillId", "Skills"."Name" AS "SkillName", "ProfessionId" FROM "ProfessionSkills" INNER JOIN "Skills" ON "ProfessionSkills"."SkillId" = "Skills"."Id" WHERE "ProfessionId" IN (${ids.join(',')})`);
  let { rows: skillUnlocks } = await pool.query(`SELECT "SkillUnlocks".*, "Skills"."Name" AS "Skill", "SkillUnlocks"."ProfessionId" FROM "SkillUnlocks" INNER JOIN "Skills" ON "SkillUnlocks"."SkillId" = "Skills"."Id" WHERE "SkillUnlocks"."ProfessionId" IN (${ids.join(',')})`);

  return {
    ProfessionSkills: _groupBy(professionSkills, 'ProfessionId'),
    SkillUnlocks: _groupBy(skillUnlocks, 'ProfessionId'),
  };
}

function formatProfession(x, data) {
  let skills = (data.ProfessionSkills[x.Id] ?? []).map(_formatProfessionSkill);
  let unlocks = (data.SkillUnlocks[x.Id] ?? []).map(_formatProfessionSkillUnlock);

  return {
    Id: x.Id,
    Name: x.Name,
    Category: {
      Name: x.Category,
      Links: {
        "$Url": `/professioncategories/${x.CategoryId}`
      }
    },
    Skills: skills,
    Unlocks: unlocks,
    Links: {
      "$Url": `/professions/${x.Id}`
    }
  }
}

function _formatProfessionSkill(x) {
  return {
    Name: x.SkillName,
    Links: {
      "$Url": `/skills/${x.SkillId}`
    }
  }
}

function _formatProfessionSkillUnlock(x) {
  return {
    Level: x.Level !== null ? Number(x.Level) : null,
    Skill: {
      Name: x.Skill,
      Links: {
        "$Url": `/skills/${x.SkillId}`
      }
    }
  }
}

// Refiners
async function getRefiners() {
  return _getObjects(queries.Refiners, formatRefiner);
}

async function getRefiner(idOrName) {
  return _getObject(idOrName, queries.Refiners, 'Refiners', formatRefiner);
}

function formatRefiner(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Refiners,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      }
    },
    Links: {
      "$Url": `/refiners/${x.Id}`
    }
  }
}

// RefiningRecipes
async function getRefiningRecipes(products = null, ingredients = null) {
  let whereClause = '';

  if (products !== null) {
    whereClause = pgp.as.format(' WHERE "Items"."Name" IN ($1:csv)', [products.map(x => `${x}`)]);
  }

  return _getObjects(queries.RefiningRecipes + whereClause, formatRefiningRecipe, _getRefiningRecipeIngredients);
}

async function getRefiningRecipe(idOrName) {
  return _getObject(idOrName, queries.RefiningRecipes, 'RefiningRecipes', formatRefiningRecipe, _getRefiningRecipeIngredients);
}

async function _getRefiningRecipeIngredients(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "RefiningIngredients"."RecipeId", "RefiningIngredients"."Amount", "Items"."Id" AS "ItemId", "Items"."Name" AS "ItemName", "Items"."Type" AS "ItemType", "Items"."Value" AS "ItemValue" FROM "RefiningIngredients" INNER JOIN "Items" ON "RefiningIngredients"."ItemId" = "Items"."Id" WHERE "RefiningIngredients"."RecipeId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'RecipeId');
}

function formatRefiningRecipe(x, data) {
  let ingredients = (data[x.Id] ?? []).map(formatRefiningIngredient);

  return {
    Id: x.Id,
    Ingredients: ingredients,
    ProductAmount: x.Amount !== null ? Number(x.Amount) : null,
    Product: {
      Name: x.Product,
      Properties: {
        Type: x.ProductType,
        Economy: {
          MaxTT: x.ProductValue !== null ? Number(x.ProductValue) : null,
        }
      },
      Links: {
        "$Url": `/${x.ProductType.toLowerCase()}s/${x.ProductId % 100000}`
      }
    },
    Links: {
      "$Url": `/refiningrecipes/${x.Id}`
    }
  }
}

function formatRefiningIngredient(x) {
  return {
    Amount: x.Amount !== null ? Number(x.Amount) : null,
    Item: {
      Name: x.ItemName,
      Properties: {
        Type: x.ItemType,
        Economy: {
          MaxTT: x.ItemValue !== null ? Number(x.ItemValue) : null,
        }
      },
      Links: {
        "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}`
      }
    }
  }
}

// Scanners
async function getScanners() {
  return _getObjects(queries.Scanners, formatScanner);
}

async function getScanner(idOrName) {
  return _getObject(idOrName, queries.Scanners, 'Scanners', formatScanner);
}

function formatScanner(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Scanners,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
      Range: x.Range !== null ? Number(x.Range) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      }
    },
    Links: {
      "$Url": `/scanners/${x.Id}`
    }
  }
}

// Signs
async function getSigns() {
  return _getObjects(queries.Signs, formatSign);
}

async function getSign(idOrName) {
  return _getObject(idOrName, queries.Signs, 'Signs', formatSign);
}

function formatSign(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Signs,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      ItemPoints: x.ItemPoints !== null ? Number(x.ItemPoints) : null,
      Display: {
        AspectRatio: x.AspectRatio,
        CanShowLocalContentScreen: x.LocalContentScreen === 1,
        CanShowImagesAndText: x.ImagesAndText === 1,
        CanShowEffects: x.Effects === 1,
        CanShowMultimedia: x.Multimedia === 1,
        CanShowParticipantContent: x.ParticipantContent === 1,
      },
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        Cost: x.Cost !== null ? Number(x.Cost) : null,
      }
    },
    Links: {
      "$Url": `/signs/${x.Id}`
    }
  }
}

// SkillCategories
async function getSkillCategories() {
  return _getObjects(queries.SkillCategories, formatSkillCategory);
}

async function getSkillCategory(idOrName) {
  return _getObject(idOrName, queries.SkillCategories, 'SkillCategories', formatSkillCategory);
}

function formatSkillCategory(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Links: {
      "$Url": `/skillcategories/${x.Id}`
    }
  }
}

// Skills
async function getSkills() {
  return _getObjects(queries.Skills, formatSkill, _getSkillUnlocks);
}

async function getSkill(idOrName) {
  return _getObject(idOrName, queries.Skills, 'Skills', formatSkill, _getSkillUnlocks);
}

async function _getSkillUnlocks(ids) {
  let { rows } = await pool.query(`SELECT "SkillUnlocks".*, "Professions"."Name" AS "ProfessionName", "Skills"."Name" AS "SkillName" FROM "SkillUnlocks" INNER JOIN "Professions" ON "SkillUnlocks"."ProfessionId" = "Professions"."Id" INNER JOIN "Skills" ON "SkillUnlocks"."SkillId" = "Skills"."Id" WHERE "SkillUnlocks"."SkillId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'SkillId');
}

function formatSkill(x, data) {
  let unlocks = (data[x.Id] ?? []).map(_formatSkillUnlock);

  return {
    Id: x.Id,
    Name: x.Name,
    HpIncrease: x.HPIncrease !== null ? Number(x.HPIncrease) : null,
    Hidden: unlocks !== null && unlocks.length > 0,
    Unlock: unlocks.length > 0 ? unlocks : null,
    Category: {
      Name: x.Category,
      Links: {
        "$Url": `/skillcategories/${x.CategoryId}`
      }
    },
    Links: {
      "$Url": `/skills/${x.Id}`
    }
  }
}

function _formatSkillUnlock(x) {
  return {
    Level: x.Level !== null ? Number(x.Level) : null,
    Profession: {
      Name: x.ProfessionName,
      Links: {
        "$Url": `/professions/${x.ProfessionId}`
      }
    }
  }
}

// StorageContainers
async function getStorageContainers() {
  return _getObjects(queries.StorageContainers, formatStorageContainer);
}

async function getStorageContainer(idOrName) {
  return _getObject(idOrName, queries.StorageContainers, 'StorageContainers', formatStorageContainer);
}

function formatStorageContainer(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.StorageContainers,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      ItemCapacity: x.Capacity !== null ? Number(x.Capacity) : null,
      WeightCapacity: x.MaxWeight !== null ? Number(x.MaxWeight) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
      }
    },
    Planet: {
      Name: x.Planet,
      Links: {
        "$Url": `/planets/${x.PlanetId}`
      }
    },
    Links: {
      "$Url": `/storagecontainers/${x.Id}`
    }
  }
}

// TeleportationChips
async function getTeleportationChips() {
  return _getObjects(queries.TeleportationChips, formatTeleportationChip);
}

async function getTeleportationChip(idOrName) {
  return _getObject(idOrName, queries.TeleportationChips, 'TeleportationChips', formatTeleportationChip);
}

function formatTeleportationChip(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.TeleportationChips,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      UsesPerMinute: x.UsesPerMinute !== null ? Number(x.UsesPerMinute) : null,
      Range: x.Range !== null ? Number(x.Range) : null,
      Mindforce: {
        Level: x.Level !== null ? Number(x.Level) : null,
        Concentration: x.Concentration !== null ? Number(x.Concentration) : null,
        Cooldown: x.Cooldown !== null ? Number(x.Cooldown) : null,
        CooldownGroup: x.CooldownGroup !== null ? Number(x.CooldownGroup) : null,
      },
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
        AmmoBurn: x.AmmoBurn !== null ? Number(x.AmmoBurn) : null
      },
      Skill: {
        LearningIntervalStart: x.MinLevel !== null ? Number(x.MinLevel) : null,
        LearningIntervalEnd: x.MaxLevel !== null ? Number(x.MaxLevel) : null,
      }
    },
    Ammo: {
      Name: x.Ammo,
      Links: {
        "$Url": `/materials/${x.AmmoId}`
      }
    },
    Profession: {
      Name: x.Profession,
      Links: {
        "$Url": `/professions/${x.ProfessionId}`
      }
    },
    Links: {
      "$Url": `/teleportationchips/${x.Id}`
    }
  }
}

// Tiers
async function getTiers(itemId = null, isArmorSet = null) {
  let whereClause = '';

  if (itemId != null) {
    whereClause = pgp.as.format(`WHERE "ItemId" = $1`, itemId);
  }

  if (isArmorSet != null) {
    whereClause = pgp.as.format(whereClause.length > 0 ? `${whereClause} AND "IsArmorSet" = $1` : `WHERE "IsArmorSet" = $1`, isArmorSet);
  }

  return _getObjects(`${queries.Tiers} ${whereClause}`, formatTier, _getTierMaterials);
}

async function getTier(idOrName) {
  return _getObject(idOrName, queries.Tiers, null, formatTier, _getTierMaterials);
}

async function _getTierMaterials(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "TierMaterials".*, "Materials"."Name" AS "MaterialName", "Materials"."Value" AS "Value", "Materials"."Weight" AS "Weight", "Materials"."Type" AS "Type" FROM "TierMaterials" INNER JOIN "Materials" ON "TierMaterials"."MaterialId" = "Materials"."Id" WHERE "TierMaterials"."TierId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'TierId');
}

function formatTier(x, data) {
  let materials = (data[x.Id] ?? []).map(_formatTierMaterial);

  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Tier: x.Tier !== null ? Number(x.Tier) : null,
      IsArmorSet: x.IsArmorSet === 1,
    },
    Materials: materials,
    Links: {
      "$Url": `/tiers/${x.Id}`
    }
  }
}

function _formatTierMaterial(x) {
  return {
    Amount: x.Amount !== null ? Number(x.Amount) : null,
    Material: {
      Name: x.MaterialName,
      Properties: {
        Weight: x.Weight !== null ? Number(x.Weight) : null,
        Type: x.Type,
        Economy: {
          MaxTT: x.Value !== null ? Number(x.Value) : null,
        } 
      },
      Links: {
        "$Url": `/materials/${x.MaterialId}`
      }
    }
  }
}

// VehicleAttachmentTypes
async function getVehicleAttachmentTypes() {
  return _getObjects(queries.VehicleAttachmentTypes, formatVehicleAttachmentType);
}

async function getVehicleAttachmentType(idOrName) {
  return _getObject(idOrName, queries.VehicleAttachmentTypes, 'VehicleAttachmentTypes', formatVehicleAttachmentType);
}

function formatVehicleAttachmentType(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Links: {
      "$Url": `/vehicleattachmenttypes/${x.Id}`
    }
  }
}

// Vehicles
async function getVehicles() {
  return _getObjects(queries.Vehicles, formatVehicle, _getAttachmentSlots);
}

async function getVehicle(idOrName) {
  return _getObject(idOrName, queries.Vehicles, 'Vehicles', formatVehicle, _getAttachmentSlots);
}

async function _getAttachmentSlots(ids) {
  let { rows } = await pool.query(`SELECT "VehicleAttachmentSlots".*, "VehicleAttachmentTypes"."Name" AS "Type" FROM "VehicleAttachmentSlots" INNER JOIN "VehicleAttachmentTypes" ON "VehicleAttachmentTypes"."Id" = "VehicleAttachmentSlots"."AttachmentId" WHERE "VehicleId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'VehicleId');
}

function formatVehicle(x, data) {
  let slots = (data[x.Id] ?? []).map(_formatAttachmentSlot);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Vehicles,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      SpawnedWeight: x.SpawnedWeight !== null ? Number(x.SpawnedWeight) : null,
      PassengerCount: x.Passengers !== null ? Number(x.Passengers) : null,
      IsTexturable: x.CustomTextures === 1,
      IsColourable: x.CustomColors === 1,
      ItemCapacity: x.StorageCapacity !== null ? Number(x.StorageCapacity) : null,
      WeightCapacity: x.WeightCapacity !== null ? Number(x.WeightCapacity) : null,
      WheelGrip: x.WheelGrip !== null ? Number(x.WheelGrip) : null,
      EnginePower: x.EnginePower !== null ? Number(x.EnginePower) : null,
      MaxSpeed: x.MaxSpeed !== null ? Number(x.MaxSpeed) : null,
      MaxStructuralIntegrity: x.MaxSI !== null ? Number(x.MaxSI) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
        Durability: x.Durability !== null ? Number(x.Durability) : null,
        FuelConsumptionActive: x.FuelActive !== null ? Number(x.FuelActive) : null,
        FuelConsumptionPassive: x.FuelPassive !== null ? Number(x.FuelPassive) : null,
      },
      Defense: {
        Stab: x.Stab !== null ? Number(x.Stab) : null,
        Cut: x.Cut !== null ? Number(x.Cut) : null,
        Impact: x.Impact !== null ? Number(x.Impact) : null,
        Penetration: x.Penetration !== null ? Number(x.Penetration) : null,
        Shrapnel: x.Shrapnel !== null ? Number(x.Shrapnel) : null,
        Burn: x.Burn !== null ? Number(x.Burn) : null,
        Cold: x.Cold !== null ? Number(x.Cold) : null, 
        Acid: x.Acid !== null ? Number(x.Acid) : null,
        Electric: x.Electric !== null ? Number(x.Electric) : null,
      },
    },
    AttachmentSlots: slots,
    Fuel: {
      Name: x.Fuel,
      Links: {
        "$Url": `/materials/${x.FuelMaterialId}`
      }
    },
    Links: {
      "$Url": `/vehicles/${x.Id}`
    }
  }
}

function _formatAttachmentSlot(x) {
  return {
    Name: x.Type,
    Links: {
      "$Url": `/vehicleattachmenttypes/${x.AttachmentId}`
    }
  }
}

// Vendors
async function getVendors() {
  return _getObjects(queries.Vendors, formatVendor, _getVendorOffers);
}

async function getVendor(idOrName) {
  return _getObject(idOrName, queries.Vendors, 'Vendors', formatVendor, _getVendorOffers);
}

async function _getVendorOffers(ids) {
  if (ids.length === 0) {
    return {
      Offers: {},
      Prices: {}
    };
  }

  let { rows: offers } = await pool.query(`SELECT "VendorOffers".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" AS "Value" FROM "VendorOffers" INNER JOIN "Items" ON "VendorOffers"."ItemId" = "Items"."Id" WHERE "VendorId" IN (${ids.join(',')})`);

  let offerIds = offers.map(x => x.Id);

  let { rows: prices } = await pool.query(`SELECT "VendorOfferPrices".*, "Items"."Name" AS "Item" FROM "VendorOfferPrices" INNER JOIN "Items" ON "VendorOfferPrices"."ItemId" = "Items"."Id" WHERE "OfferId" IN (${offerIds.join(',')})`);

  return {
    Offers: _groupBy(offers, 'VendorId'),
    Prices: _groupBy(prices, 'OfferId'),
  }
}

function formatVendor(x, data) {
  let offers = (data.Offers[x.Id] ?? []).map(_formatVendorOffer);
  offers.forEach(x => x.Prices = (data.Prices[x.Id] ?? []).map(_formatVendorOfferPrice));

  return {
    Id: x.Id,
    Name: x.Name,
    Planet: {
      Name: x.Planet,
      Links: {
        "$Url": `/planets/${x.PlanetId}`
      }
    },
    Offers: offers,
    Links: {
      "$Url": `/vendors/${x.Id}`
    }
  }
}

function _formatVendorOffer(x) {
  return {
    IsLimited: x.IsLimited === 1,
    Item: {
      Name: x.Item,
      Value: x.Value !== null ? Number(x.Value) : null,
      Links: {
        "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}`
      }
    }
  }
}

function _formatVendorOfferPrice(x) {
  return {
    Amount: x.Amount !== null ? Number(x.Amount) : null,
    Item: {
      Name: x.Item,
      Links: {
        "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}`
      }
    }
  }
}

// VendorOffers
async function getVendorOffers(items) {
  let whereClause = '';

  if (items !== null) {
    whereClause += pgp.as.format(' WHERE "Items"."Name" IN ($1:csv)', [items.map(x => `${x}`)]);
  }

  return _getObjects(queries.VendorOffers + whereClause, formatVendorOffer, _getVendorOfferPrices);
}

async function getVendorOffer(idOrName) {
  return _getObject(idOrName, queries.VendorOffers, 'VendorOffers', formatVendorOffer, _getVendorOfferPrices);
}

async function _getVendorOfferPrices(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "VendorOfferPrices".*, "Items"."Name" AS "Item" FROM "VendorOfferPrices" INNER JOIN "Items" ON "VendorOfferPrices"."ItemId" = "Items"."Id" WHERE "OfferId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'OfferId');
}

function formatVendorOffer(x, data) {
  let prices = (data[x.Id] ?? []).map(_formatVendorOfferPrice);

  return {
    Id: x.Id,
    IsLimited: x.IsLimited === 1,
    Item: {
      Name: x.Item,
      Value: x.Value !== null ? Number(x.ItemValue) : null,
      Links: {
        "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}`
      }
    },
    Vendor: {
      Name: x.Vendor,
      Planet: {
        Name: x.Planet,
        Links: {
          "$Url": `/planets/${x.PlanetId}`
        }
      },
      Links: {
        "$Url": `/vendors/${x.VendorId}`
      }
    },
    Prices: prices,
    Links: {
      "$Url": `/vendoroffers/${x.Id}`
    }
  }
}

// WeaponAmplifiers
async function getWeaponAmplifiers() {
  return _getObjects(queries.WeaponAmplifiers, formatWeaponAmplifier);
}

async function getWeaponAmplifier(idOrName) {
  return _getObject(idOrName, queries.WeaponAmplifiers, 'WeaponAmplifiers', formatWeaponAmplifier);
}

function formatWeaponAmplifier(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.WeaponAmplifiers,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Economy: {
        Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
        AmmoBurn: x.Ammo !== null ? Number(x.Ammo) : null
      },
      Damage: {
        Stab: x.Stab !== null ? Number(x.Stab) : null,
        Cut: x.Cut !== null ? Number(x.Cut) : null,
        Impact: x.Impact !== null ? Number(x.Impact) : null,
        Penetration: x.Penetration !== null ? Number(x.Penetration) : null,
        Shrapnel: x.Shrapnel !== null ? Number(x.Shrapnel) : null,
        Burn: x.Burn !== null ? Number(x.Burn) : null,
        Cold: x.Cold !== null ? Number(x.Cold) : null,
        Acid: x.Acid !== null ? Number(x.Acid) : null,
        Electric: x.Electric !== null ? Number(x.Electric) : null,
      }
    },
    Links: {
      "$Url": `/weaponamplifiers/${x.Id}`
    }
  }
}

// WeaponVisionAttachments
async function getWeaponVisionAttachments() {
  return _getObjects(queries.WeaponVisionAttachments, formatWeaponVisionAttachment);
}

async function getWeaponVisionAttachment(idOrName) {
  return _getObject(idOrName, queries.WeaponVisionAttachments, 'WeaponVisionAttachments', formatWeaponVisionAttachment);
}

function formatWeaponVisionAttachment(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.WeaponVisionAttachments,
    Name: x.Name,
    Properties: {
      Type: x.Type,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      SkillModification: x.SkillMod !== null ? Number(x.SkillMod) : null,
      SkillBonus: x.SkillBonus !== null ? Number(x.SkillBonus) : null,
      Zoom: x.Zoom !== null ? Number(x.Zoom) : null,
      Economy: {
        Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },

    },
    Links: {
      "$Url": `/weaponvisionattachments/${x.Id}`
    }
  }
}

// Weapons
async function getWeapons() {
  return _getObjects(queries.Weapons, formatWeapon);
}

async function getWeapon(idOrName) {
  return _getObject(idOrName, queries.Weapons, 'Weapons', formatWeapon);
}

function formatWeapon(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Weapons,
    Name: x.Name,
    Properties: {
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Category: x.Category,
      Class: x.Class,
      UsesPerMinute: x.Attacks !== null ? Number(x.Attacks) : null,
      Range: x.Range !== null ? Number(x.Range) : null,
      ImpactRadius: x.ImpactRadius !== null ? Number(x.ImpactRadius) : null,
      Mindforce: x.Class === 'Mindforce' ? {
        Level: x.MFLevel !== null ? Number(x.MFLevel) : null,
        Concentration: x.Concentration !== null ? Number(x.Concentration) : null,
        Cooldown: x.Cooldown !== null ? Number(x.Cooldown) : null,
        CooldownGroup: x.CooldownGroup !== null ? Number(x.CooldownGroup) : null,
      } : null,
      Economy: {
        Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
        AmmoBurn: x.AmmoBurn !== null ? Number(x.AmmoBurn) : null
      },
      Damage: {
        Stab: x.Stab !== null ? Number(x.Stab) : null,
        Cut: x.Cut !== null ? Number(x.Cut) : null,
        Impact: x.Impact !== null ? Number(x.Impact) : null,
        Penetration: x.Penetration !== null ? Number(x.Penetration) : null,
        Shrapnel: x.Shrapnel !== null ? Number(x.Shrapnel) : null,
        Burn: x.Burn !== null ? Number(x.Burn) : null,
        Cold: x.Cold !== null ? Number(x.Cold) : null,
        Acid: x.Acid !== null ? Number(x.Acid) : null,
        Electric: x.Electric !== null ? Number(x.Electric) : null,
      },
      Skill: {
        Hit: {
          LearningIntervalStart: x.MinHit !== null ? Number(x.MinHit) : null,
          LearningIntervalEnd: x.MaxHit !== null ? Number(x.MaxHit) : null,
        },
        Dmg: {
          LearningIntervalStart: x.MinDmg !== null ? Number(x.MinDmg) : null,
          LearningIntervalEnd: x.MaxDmg !== null ? Number(x.MaxDmg) : null,
        },
        IsSiB: x.SIB === 1
      }
    },
    Ammo: x.Ammo ? {
      Name: x.Ammo,
      Links: {
        "$Url": `/materials/${x.AmmoId}`
      }
    } : null,
    ProfessionHit: {
      Name: x.ProfessionHit,
      Links: {
        "$Url": `/professions/${x.ProfessionHitId}`
      }
    },
    ProfessionDmg: {
      Name: x.ProfessionDmg,
      Links: {
        "$Url": `/professions/${x.ProfessionDmgId}`
      }
    },
    AttachmentType: {
      Name: x.AttachmentType,
      Links: {
        "$Url": x.AttachmentTypeId !== null ? `/weaponattachmenttypes/${x.AttachmentTypeId}` : null
      }
    },
    Links: {
      "$Url": `/weapons/${x.Id}`
    }
  }
}


module.exports = { pool,
  search,

  getAreas, getArea,
  getLocations, getLocation,
  getPlanet, getPlanets,
  getTeleporter, getTeleporters,

  getItem, getItems,
  getAbsorber, getAbsorbers,
  getArmorPlating, getArmorPlatings,
  getArmor, getArmors,
  getArmorSet, getArmorSets,
  getBlueprintBook, getBlueprintBooks,
  getBlueprint, getBlueprints,
  getClothes,
  getConsumable, getConsumables,
  getCreatureControlCapsule, getCreatureControlCapsules,
  getDecoration, getDecorations,
  getEffectChip, getEffectChips,
  getEffect, getEffects,
  getEnhancer, getEnhancers,
  getExcavator, getExcavators,
  getFinderAmplifier, getFinderAmplifiers,
  getFinder, getFinders,
  getFurniture,
  getMaterial, getMaterials,
  getMedicalChip, getMedicalChips,
  getMedicalTool, getMedicalTools,
  getMindforceImplant, getMindforceImplants,
  getMiscTool, getMiscTools,
  getMobLoots,
  getMobMaturity, getMobMaturities,
  getMobSpawns,
  getMobSpecies,
  getMob, getMobs,
  getPet, getPets,
  getProfessionCategory, getProfessionCategories,
  getProfession, getProfessions,
  getRefiner, getRefiners,
  getRefiningRecipe, getRefiningRecipes,
  getScanner, getScanners,
  getSign, getSigns,
  getSkillCategory, getSkillCategories,
  getSkill, getSkills,
  getStorageContainer, getStorageContainers,
  getTeleportationChip, getTeleportationChips,
  getTier, getTiers,
  getVehicleAttachmentType, getVehicleAttachmentTypes,
  getVehicle, getVehicles,
  getVendor, getVendors,
  getVendorOffer, getVendorOffers,
  getWeaponAmplifier, getWeaponAmplifiers,
  getWeaponVisionAttachment, getWeaponVisionAttachments,
  getWeapon, getWeapons};
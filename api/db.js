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
  Clothings:                8000000,
  Furnishings:              9000000,
  Furniture:                9100000,
  Decorations:              9200000,
  StorageContainers:        9300000,
  Signs:                    9400000,
  Consumables:              10000000,
  Capsules:                 10100000,
  Pets:                     11000000,
  Strongboxes:              12000000,

  equipSet:                 100000,
}

const queries = {
  // Maps & Locations
  Areas: 'SELECT "Areas".*, "Planets"."Name" AS "Planet", "Planets"."TechnicalName" FROM ONLY "Areas" LEFT JOIN ONLY "Planets" ON "Areas"."PlanetId" = "Planets"."Id"',
  Locations: 'SELECT "Locations".*, "Planets"."Name" AS "Planet", "Planets"."TechnicalName" FROM ONLY "Locations" LEFT JOIN ONLY "Planets" ON "Locations"."PlanetId" = "Planets"."Id"',
  Planets: 'SELECT * FROM ONLY "Planets"',
  Teleporters: 'SELECT "Teleporters".*, "Planets"."Name" AS "Planet", "Planets"."TechnicalName" FROM ONLY "Teleporters" LEFT JOIN ONLY "Planets" ON "Teleporters"."PlanetId" = "Planets"."Id"',
  MobSpawns: 'SELECT "MobSpawns".*, "MobMaturities"."MobId", "Areas"."Name", "Areas"."Type", "Areas"."Shape", "Areas"."Data", "Areas"."Longitude", "Areas"."Latitude", "Areas"."Altitude", "Areas"."PlanetId", "Planets"."Name" AS "Planet", "Planets"."TechnicalName" FROM ONLY "MobSpawns" INNER JOIN ONLY "Areas" ON "MobSpawns"."AreaId" = "Areas"."Id" INNER JOIN ONLY "Planets" ON "Areas"."PlanetId" = "Planets"."Id" INNER JOIN ONLY "MobSpawnMaturities" ON "MobSpawns"."Id" = "MobSpawnMaturities"."SpawnId" INNER JOIN ONLY "MobMaturities" ON "MobSpawnMaturities"."MaturityId" = "MobMaturities"."Id"',

  // Items
  Items: 'SELECT * FROM ONLY "Items"',
  Absorbers: 'SELECT * FROM ONLY "Absorbers"',
  ArmorPlatings: 'SELECT * FROM ONLY "ArmorPlatings"',
  ArmorSets: 'SELECT "ArmorSets"."Id", "ArmorSets"."Name", "ArmorSets"."Description", "Durability", "Stab", "Cut", "Impact", "Penetration", "Shrapnel", "Burn", "Cold", "Acid", "Electric" FROM ONLY "ArmorSets"',
  Armors: 'SELECT "Armors"."Id", "Armors"."Name", "Armors"."Description", "ArmorSets"."Name" AS "Set", "Gender", "Slot", "SetId", "Weight", "MaxTT", "MinTT", "Durability", "Stab", "Cut", "Impact", "Penetration", "Shrapnel", "Burn", "Cold", "Acid", "Electric" FROM ONLY "Armors" LEFT JOIN ONLY "ArmorSets" ON "Armors"."SetId" = "ArmorSets"."Id"',
  BlueprintBooks: 'SELECT "BlueprintBooks"."Id", "BlueprintBooks"."Name", "BlueprintBooks"."Description", "PlanetId", "Planets"."Name" AS "Planet", "Weight", "Value" FROM ONLY "BlueprintBooks" LEFT JOIN ONLY "Planets" ON "BlueprintBooks"."PlanetId" = "Planets"."Id"',
  Blueprints: 'SELECT "Blueprints".*, "BlueprintBooks"."Name" AS "Book", "Professions"."Name" AS "Profession", "Items"."Type" AS "ItemType", "Items"."Name" AS "Item" FROM ONLY "Blueprints" LEFT JOIN ONLY "BlueprintBooks" ON "Blueprints"."BookId" = "BlueprintBooks"."Id" LEFT JOIN ONLY "Items" ON "Blueprints"."ItemId" = "Items"."Id" LEFT JOIN ONLY "Professions" ON "Professions"."Id" = "Blueprints"."ProfessionId"',
  Clothings: 'SELECT * FROM ONLY "Clothes"',
  Consumables: 'SELECT * FROM ONLY "Consumables"',
  CreatureControlCapsules: 'SELECT "CreatureControlCapsules".*, "Mobs"."Name" AS "Mob", "Professions"."Name" AS "Profession" FROM ONLY "CreatureControlCapsules" LEFT JOIN ONLY "Mobs" ON "CreatureControlCapsules"."MobId" = "Mobs"."Id" LEFT JOIN ONLY "Professions" ON "CreatureControlCapsules"."ScanningProfessionId" = "Professions"."Id"',
  Decorations: 'SELECT * FROM ONLY "Decorations"',
  EffectChips: 'SELECT "EffectChips".*, "Professions"."Name" AS "Profession", "Materials"."Name" AS "Ammo" FROM ONLY "EffectChips" LEFT JOIN ONLY "Professions" ON "EffectChips"."ProfessionId" = "Professions"."Id" LEFT JOIN ONLY "Materials" ON "EffectChips"."AmmoId" = "Materials"."Id"',
  Effects: 'SELECT * FROM ONLY "Effects"',
  Enhancers: 'SELECT "Enhancers".*, "EnhancerType"."Name" AS "Type", "EnhancerType"."Tool" AS "Tool" FROM ONLY "Enhancers" LEFT JOIN ONLY "EnhancerType" ON "Enhancers"."TypeId" = "EnhancerType"."Id"',
  EquipSets: 'SELECT * FROM ONLY "EquipSets"',
  Excavators: 'SELECT * FROM ONLY "Excavators"',
  FinderAmplifiers: 'SELECT * FROM ONLY "FinderAmplifiers"',
  Finders: 'SELECT * FROM ONLY "Finders"',
  Furniture: 'SELECT "Furniture".*, "Planets"."Name" AS "Planet" FROM ONLY "Furniture" LEFT JOIN ONLY "Planets" ON "Furniture"."PlanetId" = "Planets"."Id"',
  Materials: 'SELECT * FROM ONLY "Materials"',
  MedicalChips: 'SELECT "MedicalChips".*, "Materials"."Name" AS "Ammo" FROM ONLY "MedicalChips" LEFT JOIN ONLY "Materials" ON "MedicalChips"."AmmoId" = "Materials"."Id"',
  MedicalTools: 'SELECT * FROM ONLY "MedicalTools"',
  MindforceImplants: 'SELECT * FROM ONLY "MindforceImplants"',
  MiscTools: 'SELECT "MiscTools".*, "Professions"."Name" AS "Profession" FROM ONLY "MiscTools" LEFT JOIN ONLY "Professions" ON "MiscTools"."ProfessionId" = "Professions"."Id"',
  MobLoots: 'SELECT "MobLoots".*, "Mobs"."Name" AS "Mob", "Mobs"."PlanetId", "MobMaturities"."Name" AS "Maturity", "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Planets"."Name" AS "Planet" FROM ONLY "MobLoots" INNER JOIN ONLY "Mobs" ON "MobLoots"."MobId" = "Mobs"."Id" INNER JOIN ONLY "Items" ON "MobLoots"."ItemId" = "Items"."Id" LEFT JOIN ONLY "MobMaturities" ON "MobLoots"."MaturityId" = "MobMaturities"."Id" LEFT JOIN ONLY "Planets" ON "Mobs"."PlanetId" = "Planets"."Id"',
  MobMaturities: 'SELECT "MobMaturities".*, "Mobs"."Name" AS "Mob" FROM ONLY "MobMaturities" INNER JOIN ONLY "Mobs" ON "MobMaturities"."MobId" = "Mobs"."Id"',
  MobSpecies: 'SELECT * FROM ONLY "MobSpecies"',
  Mobs: 'SELECT "Mobs".*, "MobSpecies"."Name" AS "Species", "MobSpecies"."CodexBaseCost" AS "CodexBaseCost", "MobSpecies"."IsCat4Codex" AS "IsCat4Codex", "Planets"."Name" AS "Planet", d."Name" AS "DefensiveProfession", s."Name" AS "ScanningProfession" FROM ONLY "Mobs" LEFT JOIN ONLY "Planets" ON "Mobs"."PlanetId" = "Planets"."Id" LEFT JOIN ONLY "MobSpecies" ON "Mobs"."SpeciesId" = "MobSpecies"."Id" LEFT JOIN ONLY "Professions" d ON "Mobs"."DefensiveProfessionId" = d."Id" LEFT JOIN ONLY "Professions" s ON "Mobs"."ScanningProfessionId" = s."Id"',
  Pets: 'SELECT "Pets".*, "Planets"."Name" AS "Planet" FROM ONLY "Pets" LEFT JOIN ONLY "Planets" ON "Pets"."PlanetId" = "Planets"."Id"',
  ProfessionCategories: 'SELECT * FROM ONLY "ProfessionCategories"',
  Professions: 'SELECT "Professions".*, "ProfessionCategories"."Name" AS "Category" FROM ONLY "Professions" INNER JOIN ONLY "ProfessionCategories" ON "Professions"."CategoryId" = "ProfessionCategories"."Id"',
  Refiners: 'SELECT * FROM ONLY "Refiners"',
  RefiningRecipes: 'SELECT "RefiningRecipes".*, "Items"."Name" AS "Product", "Items"."Type" AS "ProductType", "Items"."Value" AS "ProductValue" FROM ONLY "RefiningRecipes" INNER JOIN ONLY "Items" ON "RefiningRecipes"."ProductId" = "Items"."Id"',
  Scanners: 'SELECT * FROM ONLY "Scanners"',
  Signs: 'SELECT * FROM ONLY "Signs"',
  SkillCategories: 'SELECT * FROM ONLY "SkillCategories"',
  Skills: 'SELECT "Skills".*, "SkillCategories"."Name" AS "Category" FROM ONLY "Skills" INNER JOIN ONLY "SkillCategories" ON "Skills"."CategoryId" = "SkillCategories"."Id"',
  Strongboxes: 'SELECT * FROM ONLY "Strongboxes"',
  StorageContainers: 'SELECT "StorageContainers".*, "Planets"."Name" AS "Planet" FROM ONLY "StorageContainers" LEFT JOIN ONLY "Planets" ON "StorageContainers"."PlanetId" = "Planets"."Id"',
  TeleportationChips: 'SELECT "TeleportationChips".*, "Professions"."Name" AS "Profession", "Materials"."Name" AS "Ammo" FROM ONLY "TeleportationChips" LEFT JOIN ONLY "Professions" ON "TeleportationChips"."ProfessionId" = "Professions"."Id" LEFT JOIN ONLY "Materials" ON "TeleportationChips"."AmmoId" = "Materials"."Id"',
  Tiers: 'SELECT * FROM (SELECT "Tiers".*, "Items"."Name" || \' Tier \' || "Tiers"."Tier" AS "Name", "Items"."Name" AS "Item" FROM ONLY "Tiers" INNER JOIN ONLY "Items" ON "Tiers"."ItemId" = "Items"."Id" WHERE "IsArmorSet" = 0 UNION ALL SELECT "Tiers".*, "ArmorSets"."Name" || \' Tier \' || "Tiers"."Tier" AS "Name", "ArmorSets"."Name" AS "Item" FROM ONLY "Tiers" INNER JOIN ONLY "ArmorSets" ON "Tiers"."ItemId" = "ArmorSets"."Id" WHERE "IsArmorSet" = 1)',
  VehicleAttachmentTypes: 'SELECT * FROM ONLY "VehicleAttachmentTypes"',
  Vehicles: 'SELECT "Vehicles".*, "Materials"."Name" AS "Fuel" FROM ONLY "Vehicles" LEFT JOIN ONLY "Materials" ON "Vehicles"."FuelMaterialId" = "Materials"."Id"',
  Vendors: 'SELECT "Vendors".*, "Planets"."Name" AS "Planet", "Planets"."TechnicalName" AS "PlanetTechnicalName" FROM ONLY "Vendors" LEFT JOIN ONLY "Planets" ON "Vendors"."PlanetId" = "Planets"."Id"',
  VendorOffers: 'SELECT "VendorOffers".*, "Items"."Name" AS "Item", "Items"."Value" AS "ItemValue", "Items"."Type" AS "ItemType", "Vendors"."Name" AS "Vendor", "Vendors"."PlanetId" AS "PlanetId", "Planets"."Name" AS "Planet" FROM ONLY "VendorOffers" LEFT JOIN ONLY "Items" ON "VendorOffers"."ItemId" = "Items"."Id" LEFT JOIN ONLY "Vendors" ON "VendorOffers"."VendorId" = "Vendors"."Id" LEFT JOIN ONLY "Planets" ON "Vendors"."PlanetId" = "Planets"."Id"',
  WeaponAmplifiers: 'SELECT * FROM ONLY "WeaponAmplifiers"',
  WeaponVisionAttachments: 'SELECT * FROM ONLY "WeaponVisionAttachments"',
  Weapons: 'SELECT "Weapons".*, "VehicleAttachmentTypes"."Name" AS "AttachmentType", "Materials"."Name" AS "Ammo", hit."Name" AS "ProfessionHit", dmg."Name" AS "ProfessionDmg" FROM ONLY "Weapons" LEFT JOIN ONLY "VehicleAttachmentTypes" ON "Weapons"."AttachmentTypeId" = "VehicleAttachmentTypes"."Id" LEFT JOIN ONLY "Materials" ON "Weapons"."AmmoId" = "Materials"."Id" LEFT JOIN ONLY "Professions" hit ON "Weapons"."ProfessionHitId" = hit."Id" LEFT JOIN ONLY "Professions" dmg ON "Weapons"."ProfessionDmgId" = dmg."Id"',
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

function _groupByProperty(arr, keyFunc) {
  return arr.reduce((acc, obj) => {
    let keyVal = keyFunc(obj);
    if (!acc[keyVal]) {
      acc[keyVal] = [];
    }
    acc[keyVal].push(obj);
    return acc;
  }, {});
}

async function _getTiers(ids, isArmorSet = false) {
  if (ids.length === 0) {
    return {};
  }

  let tiers;

  if (isArmorSet) {
    tiers = (await pool.query(`
    SELECT "Tiers"."Tier", "Tiers"."ItemId", "Tiers"."IsArmorSet", "ArmorSets"."Name" AS "ItemName", "TierMaterials".*, "Materials"."Name" AS "MaterialName", "Materials"."Value" AS "Value", "Materials"."Weight" AS "Weight", "Materials"."Type" AS "Type"
    FROM ONLY "Tiers"
    INNER JOIN ONLY "TierMaterials" ON "Tiers"."Id" = "TierMaterials"."TierId"
    INNER JOIN ONLY "Materials" ON "TierMaterials"."MaterialId" = "Materials"."Id"
    INNER JOIN ONLY "ArmorSets" ON "Tiers"."ItemId" = "ArmorSets"."Id"
    WHERE "Tiers"."ItemId" IN (${ids.join(',')}) AND "IsArmorSet" = 1`)).rows;
  }
  else {
    tiers = (await pool.query(`
    SELECT "Tiers"."Tier", "Tiers"."ItemId", "Tiers"."IsArmorSet", "Items"."Name" AS "ItemName", "TierMaterials".*, "Materials"."Name" AS "MaterialName", "Materials"."Value" AS "Value", "Materials"."Weight" AS "Weight", "Materials"."Type" AS "Type"
    FROM ONLY "Tiers"
    INNER JOIN ONLY "TierMaterials" ON "Tiers"."Id" = "TierMaterials"."TierId"
    INNER JOIN ONLY "Materials" ON "TierMaterials"."MaterialId" = "Materials"."Id"
    INNER JOIN ONLY "Items" ON "Tiers"."ItemId" = "Items"."Id"
    WHERE "Tiers"."ItemId" IN (${ids.join(',')}) AND "IsArmorSet" = 0`)).rows;
  }

  return tiers.reduce((acc, tier) => {
    if (!acc[tier.ItemId]) {
      acc[tier.ItemId] = {};
    }
    if (!acc[tier.ItemId][tier.Tier]) {
      acc[tier.ItemId][tier.Tier] = [];
    }
    acc[tier.ItemId][tier.Tier].push(tier);
    return acc;
  }, {})
}

async function _getEffectsOnUse(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "Effects"."Id", "Effects"."Name", "Effects"."Unit", "Effects"."Description", "EffectsOnUse"."DurationSeconds", "EffectsOnUse"."Strength", "EffectsOnUse"."ItemId" FROM ONLY "EffectsOnUse" INNER JOIN ONLY "Effects" ON "EffectsOnUse"."EffectId" = "Effects"."Id" WHERE "EffectsOnUse"."ItemId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'ItemId');
}

async function _getEffectsOnEquip(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "Effects"."Id", "Effects"."Name", "Effects"."Unit", "Effects"."Description", "EffectsOnEquip"."Strength", "EffectsOnEquip"."ItemId" FROM ONLY "EffectsOnEquip" INNER JOIN ONLY "Effects" ON "EffectsOnEquip"."EffectId" = "Effects"."Id" WHERE "EffectsOnEquip"."ItemId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'ItemId');
}

async function _getEffectsOnArmorSetEquipFromArmor(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "Effects"."Id", "Effects"."Name", "Effects"."Unit", "Effects"."Description", "EffectsOnSetEquip"."Strength", "EffectsOnSetEquip"."MinSetPieces", "Armors"."Id" AS "ItemId" FROM ONLY "EffectsOnSetEquip" INNER JOIN ONLY "Armors" ON "EffectsOnSetEquip"."SetId" = "Armors"."SetId" INNER JOIN ONLY "Effects" ON "EffectsOnSetEquip"."EffectId" = "Effects"."Id" WHERE "Armors"."Id" IN (${ids.join(',')})`);

  return _groupBy(rows, 'ItemId');
}

async function _getEffectsOnEquipSetEquipFromEquipSet(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`
    SELECT "Effects"."Id", "Effects"."Name", "Effects"."Unit", "Effects"."Description", "EffectsOnSetEquip"."Strength", "EffectsOnSetEquip"."MinSetPieces", "EquipSetItems"."ItemId", "EquipSets"."Name" AS "SetName", "EquipSets"."Id" AS "SetId"
      FROM ONLY "EffectsOnSetEquip"
    INNER JOIN ONLY "EquipSetItems" ON "EffectsOnSetEquip"."SetId" = "EquipSetItems"."EquipSetId" + ${idOffsets.equipSet}
    INNER JOIN ONLY "EquipSets" ON "EffectsOnSetEquip"."SetId" = "EquipSets"."Id" + ${idOffsets.equipSet}
    INNER JOIN ONLY "Effects" ON "EffectsOnSetEquip"."EffectId" = "Effects"."Id"
      WHERE "EquipSetItems"."ItemId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'ItemId');
}

function _formatEffectOnUse(x) {
  return {
    Name: x.Name,
    Values: {
      DurationSeconds: x.DurationSeconds !== null ? Number(x.DurationSeconds) : null,
      Strength: x.Strength !== null ? Number(x.Strength) : null,
      Unit: x.Unit,
      Description: x.Description
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
      Unit: x.Unit,
      Description: x.Description
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
      Unit: x.Unit,
      Description: x.Description
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
        FROM ONLY "Items"
        LEFT JOIN ONLY "Weapons" ON "Items"."Id" - ${idOffsets.Weapons} = "Weapons"."Id"
        WHERE "Items"."Type" != 'Armor'
        UNION ALL
        SELECT "ArmorSets"."Id" + 1000000000 AS "Id", "ArmorSets"."Name" AS "Name", 'Armor' AS "Type", NULL AS "SubType" FROM ONLY "ArmorSets"
        UNION ALL
        SELECT "Mobs"."Id" + 2000000000 AS "Id", "Mobs"."Name" AS "Name", 'Mob' AS "Type", "Planets"."Name" AS "SubType" FROM ONLY "Mobs" INNER JOIN ONLY "Planets" ON "Mobs"."PlanetId" = "Planets"."Id"
        UNION ALL
        SELECT "Skills"."Id" + 3000000000 AS "Id", "Skills"."Name" AS "Name", 'Skill' AS "Type", NULL AS "SubType" FROM ONLY "Skills"
        UNION ALL
        SELECT "Professions"."Id" + 4000000000 AS "Id", "Professions"."Name" AS "Name", 'Profession' AS "Type", NULL AS "SubType" FROM ONLY "Professions"
        UNION ALL
        SELECT "Vendors"."Id" + 5000000000 AS "Id", "Vendors"."Name" AS "Name", 'Vendor' AS "Type", NULL AS "SubType" FROM ONLY "Vendors"
      )
      WHERE "Name" ILIKE $1
    ) x
    WHERE rn <= 5
    LIMIT 20
  `;

  let { rows } = await pool.query(query, [`%${search}%`]);

  return rows.map(formatSearchResult);
}

async function searchItems(search) {
  let { rows } = await pool.query(`
    SELECT * FROM (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY "Type" ORDER BY "Id") as rn
      FROM (
        SELECT "Items"."Id" AS "Id", "Items"."Name" AS "Name", "Items"."Type" AS "Type",
          CASE
            WHEN "Items"."Type" = 'Weapon' THEN "Weapons"."Class"
            ELSE NULL
          END AS "SubType" 
        FROM ONLY "Items"
        LEFT JOIN ONLY "Weapons" ON "Items"."Id" - ${idOffsets.Weapons} = "Weapons"."Id"
        WHERE "Items"."Type" != 'Armor' AND "Items"."Name" ILIKE $1
        UNION ALL
        SELECT "ArmorSets"."Id" + 1000000000 AS "Id", "ArmorSets"."Name" AS "Name", 'Armor' AS "Type", NULL AS "SubType" FROM ONLY "ArmorSets"
        )
      WHERE "Name" ILIKE $1
    ) x
    WHERE rn <= 5
    LIMIT 20`, [`%${search}%`]);

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

  return await _getObjects(queries.Areas + whereClause, formatArea);
}

async function getArea(idOrName) {
  return await _getObject(idOrName, queries.Areas, 'Areas', formatArea);
}

function formatArea(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
      Properties: {
        TechnicalName: x.TechnicalName,
      },
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

  return await _getObjects(queries.Locations + whereClause, formatLocation);
}

async function getLocation(idOrName) {
  return await _getObject(idOrName, queries.Locations, 'Locations', formatLocation);
}

function formatLocation(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Type: x.Type,
      Coordinates: {
        Longitude: x.Longitude,
        Latitude: x.Latitude,
        Altitude: x.Altitude
      }
    },
    Planet: {
      Name: x.Planet,
      Properties: {
        TechnicalName: x.TechnicalName,
      },
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
  return await _getObjects(queries.Planets, formatPlanet);
}

async function getPlanet(idOrName) {
  return await _getObject(idOrName, queries.Planets, 'Planets', formatPlanet);
}

function formatPlanet(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  return await _getObjects(queries.Teleporters, formatTeleporter);
}

async function getTeleporter(idOrName) {
  return await _getObject(idOrName, queries.Teleporters, 'Teleporters', formatTeleporter);
}

function formatTeleporter(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Coordinates: {
        Longitude: x.Longitude,
        Latitude: x.Latitude,
        Altitude: x.Altitude
      }
    },
    Planet: {
      Name: x.Planet,
      Properties: {
        TechnicalName: x.TechnicalName,
      },
      Links: {
        "$Url": `/planets/${x.PlanetId}`
      }
    },
    Links: {
      "$Url": `/teleporters/${x.Id}`
    }
  }
}

// MobSpawns
async function getMobSpawns(mobs = null) {
  let whereClause = '';

  if (mobs != null && mobs.length > 0) {
    if (mobs.every(mob => typeof mob === 'number')) {
      whereClause = pgp.as.format(' WHERE (SELECT COUNT(*) FROM "MobSpawnMaturities" WHERE "SpawnId" = "MobSpawns"."Id" AND "MaturityId" IN (SELECT DISTINCT "MobMaturities"."Id" FROM "MobMaturities" WHERE "MobMaturities"."MobId" IN ($1:csv))) > 0', [mobs]);
    } else if (mobs.every(mob => typeof mob === 'string')) {
      whereClause = pgp.as.format(' WHERE (SELECT COUNT(*) FROM "MobSpawnMaturities" WHERE "SpawnId" = "MobSpawns"."Id" AND "MaturityId" IN (SELECT DISTINCT "MobMaturities"."Id" FROM "MobMaturities" INNER JOIN "Mobs" ON "MobMaturities"."MobId" = "Mobs"."Id" WHERE "Mobs"."Name" IN ($1:csv))) > 0', [mobs]);
    } else {
      throw new Error('Invalid mobs array: must be an array of either integers or strings');
    }
  }

  return await _getObjects(queries.MobSpawns + whereClause, formatMobSpawn, _getMobSpawnMaturities);
}

async function getMobSpawn(idOrName) {
  return await _getObject(idOrName, queries.MobSpawns, 'MobSpawns', _getMobSpawnMaturities);
}

async function _getMobSpawnMaturities(spawnIds) {
  if (spawnIds.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "MobSpawnMaturities".*, "MobMaturities".*, "Mobs"."Name" AS "Mob", "Mobs"."PlanetId", "Planets"."Name" AS "Planet", "Planets"."TechnicalName" AS "TechnicalName" FROM ONLY "MobSpawnMaturities" INNER JOIN ONLY "MobMaturities" ON "MobSpawnMaturities"."MaturityId" = "MobMaturities"."Id" INNER JOIN ONLY "Mobs" ON "MobMaturities"."MobId" = "Mobs"."Id" INNER JOIN ONLY "Planets" ON "Mobs"."PlanetId" = "Planets"."Id" WHERE "SpawnId" IN (${spawnIds.join(',')})`);

  return _groupBy(rows, 'SpawnId');
}

function formatMobSpawn(x, data) {
  let maturities = (data[x.Id] ?? (Array.isArray(data) ? data : [])).map(_formatMobSpawnMaturity);

  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Density: x.Density,
      IsShared: x.IsShared === 1,
      IsEvent: x.IsEvent === 1,
      Notes: x.Notes,
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
      Properties: {
        TechnicalName: x.TechnicalName,
      },
      Links: {
        "$Url": `/planets/${x.PlanetId}`
      }
    },
    Maturities: maturities,
    Links: {
      "$Url": `/mobspawns/${x.Id}`
    }
  }
}

function _formatMobSpawnMaturity(x) {
  return {
    IsRare: x.IsRare,
    Maturity: formatMobMaturity(x, []),
  }
}

// Items
async function getItems() {
  let { rows } = await pool.query(queries.Items);

  return rows.map(formatItem);
}

async function getItem(idOrName) {
  return await _getObject(idOrName, queries.Items, 'Items', formatItem);
}

function formatItem(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Type: x.Type,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: {
        Value: x.Value !== null ? Number(x.Value) : null,
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
  return await _getObject(idOrName, queries.Absorbers, 'Absorbers', formatAbsorber);
}

function formatAbsorber(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Absorbers,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  return await _getObjects(queries.ArmorPlatings, formatArmorPlating);
}

async function getArmorPlating(idOrName) {
  return await _getObject(idOrName, queries.ArmorPlatings, 'ArmorPlatings', formatArmorPlating);
}

function formatArmorPlating(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.ArmorPlatings,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  return await _getObjects(queries.ArmorSets, formatArmorSet, _getArmorSetPiecesAndEffects);
}

async function getArmorSet(idOrName) {
  return await _getObject(idOrName, queries.ArmorSets, 'ArmorSets', formatArmorSet, _getArmorSetPiecesAndEffects);
}
 
async function _getArmorSetPiecesAndEffects(setIds) {
  let { rows: armors } = await pool.query(`SELECT * FROM ONLY "Armors" WHERE "SetId" IN (${setIds.join(',')})`);
  let { rows: setEffects } = await pool.query(`SELECT "Effects"."Id", "Effects"."Name", "Effects"."Unit", "EffectsOnSetEquip"."Strength", "EffectsOnSetEquip"."MinSetPieces", "EffectsOnSetEquip"."SetId" FROM ONLY "EffectsOnSetEquip" INNER JOIN ONLY "Effects" ON "EffectsOnSetEquip"."EffectId" = "Effects"."Id" WHERE "EffectsOnSetEquip"."SetId" IN (${setIds.join(',')})`);

  return {
    Armors: _groupBy(armors, 'SetId'),
    Effects: await _getEffectsOnEquip(armors.map(x => x.Id + idOffsets.Armors)),
    SetEffects: _groupBy(setEffects, 'SetId'),
    Tiers: await _getTiers(setIds, true)
  }
}

async function formatArmorSet(x, data) {
  let armorPieces = (data.Armors[x.Id] ?? [])
    .map(y => {
      let armor = _formatArmor(y);
      armor.EffectsOnEquip = data.Effects[y.Id + idOffsets.Armors]?.map(_formatEffectOnEquip) ?? []
      return armor;
    });
  let maleSet = armorPieces.filter(y => y.Properties.Gender === 'Male' || y.Properties.Gender === 'Both');
  let setEffects = (data.SetEffects[x.Id] ?? []).map(_formatEffectOnSetEquip);
  let tiers = Object.values((data.Tiers[x.Id] ?? [])).map(_formatTier);

  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: Number(maleSet.map(y => y.Properties.Weight).reduce((a, b) => a + Number(b), 0).toFixed(8)) ?? null,
      Economy: {
        MaxTT: Number(maleSet.map(y => y.Properties.Economy.MaxTT).reduce((a, b) => a + Number(b), 0).toFixed(8)) ?? null,
        MinTT: Number(maleSet.map(y => y.Properties.Economy.MinTT).reduce((a, b) => a + Number(b), 0).toFixed(8)) ?? null,
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
    EffectsOnSetEquip: setEffects,
    Armors: Object.values(_groupByProperty(armorPieces, x => x.Properties.Slot)),
    Tiers: tiers,
    Links: {
      "$Url": `/armorsets/${x.Id}`
    }
  }
}

function _formatArmor(x) {
  return {
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Gender: x.Gender,
      Slot: x.Slot,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
      }
    },
    EffectsOnEquip: x.Effects,
    Links: {
      "$Url": `/armors/${x.Id}`
    }
  }
}

// Armors
async function getArmors() {
  return await _getObjects(queries.Armors, formatArmor);
}

async function getArmor(idOrName) {
  return await _getObject(idOrName, queries.Armors, 'Armors', formatArmor);
}

function formatArmor(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Armors,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  return await _getObjects(queries.BlueprintBooks, formatBlueprintBook);
}

async function getBlueprintBook(idOrName) {
  return await _getObject(idOrName, queries.BlueprintBooks, 'BlueprintBooks', formatBlueprintBook);
}

function formatBlueprintBook(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.BlueprintBooks,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
async function getBlueprints(products = null, materials = null) {
  let whereClause = '';

  if (products !== null) {
    whereClause = pgp.as.format(' WHERE "Items"."Name" IN ($1:csv)', [products.map(x => `${x}`)]);
  }
  else if (materials !== null) {
    whereClause = pgp.as.format(' WHERE "Blueprints"."Id" IN (SELECT DISTINCT "BlueprintId" FROM ONLY "BlueprintMaterials" INNER JOIN ONLY "Items" ON "Items"."Id" = "BlueprintMaterials"."ItemId" WHERE "Items"."Name" IN ($1:csv))', [materials.map(x => `${x}`)]);
  }

  return await _getObjects(queries.Blueprints + whereClause, formatBlueprint, getBlueprintIngredients);
}

async function getBlueprint(idOrName) {
  return await _getObject(idOrName, queries.Blueprints, 'Blueprints', formatBlueprint, getBlueprintIngredients);
}

async function getBlueprintIngredients(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "BlueprintId", "Name", "Amount", "ItemId", "Type", "Items"."Value" AS "Value", "Items"."Type" AS "ItemType" FROM ONLY "BlueprintMaterials" INNER JOIN ONLY "Items" ON "Items"."Id" = "BlueprintMaterials"."ItemId" WHERE "BlueprintId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'BlueprintId');
}

function formatBlueprint(x, ingredients) {
  let materials = (ingredients[x.Id] ?? []).map(_formatBlueprintMaterial);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Blueprints,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Type: x.Type,
      Level: x.Level !== null ? Number(x.Level) : null,
      IsBoosted: x.IsBoosted == 1,
      MinimumCraftAmount: x.MinimumCraftAmount !== null ? Number(x.MinimumCraftAmount) : null,
      MaximumCraftAmount: x.MaximumCraftAmount !== null ? Number(x.MaximumCraftAmount) : null,
      Skill: {
        LearningIntervalStart: x.MinLvl !== null ? Number(x.MinLvl) : null,
        LearningIntervalEnd:x.MaxLvl !== null ? Number(x.MaxLvl) : null,
        IsSiB: x.IsSib === 1,
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
    Product: x.Item != null ? {
      Name: x.Item,
      Properties: {
        Type: x.ItemType,
      },
      Links: {
        "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}`
      }
    } : null,
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
    }
  }
}

// Clothings
async function getClothings() {
  return await _getObjects(queries.Clothings, formatClothings, _getClothingData, idOffsets.Clothings);
}

async function getClothing(idOrName) {
  return await _getObject(idOrName, queries.Clothings, 'Clothes', formatClothings, _getClothingData, idOffsets.Clothings);
}

async function _getClothingData(ids) {
  const [effectsOnEquip, effectsOnSetEquip] = await Promise.all([
    _getEffectsOnEquip(ids),
    _getEffectsOnEquipSetEquipFromEquipSet(ids)
  ]);

  return { effectsOnEquip, effectsOnSetEquip };
}

function formatClothings(x, data) {
  const { effectsOnEquip, effectsOnSetEquip } = data;

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Clothings,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Gender: x.Gender,
      Type: x.Type,
      Slot: x.Slot,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null
      }
    },
    Set: effectsOnSetEquip[x.Id + idOffsets.Clothings]?.length > 0 ? {
      Name: effectsOnSetEquip[x.Id + idOffsets.Clothings][0].SetName,
      EffectsOnSetEquip: (effectsOnSetEquip[x.Id + idOffsets.Clothings] ?? []).map(_formatEffectOnSetEquip),
      Links: {
        "$Url": `/equipsets/${effectsOnSetEquip[x.Id + idOffsets.Clothings][0].SetId}`
      }
    } : null,
    EffectsOnEquip: (effectsOnEquip[x.Id + idOffsets.Clothings] ?? []).map(_formatEffectOnEquip),
    Links: {
      "$Url": `/clothings/${x.Id}`
    }
  }
}

// Consumables
async function getConsumables() {
  return await _getObjects(queries.Consumables, formatConsumable, _getConsumableEffects);
}

async function getConsumable(idOrName) {
  return await _getObject(idOrName, queries.Consumables, 'Consumables', formatConsumable, _getConsumableEffects);
}

async function _getConsumableEffects(ids) {
  let { rows } = await pool.query(`SELECT "Id", "Effects"."Name", "Effects"."Unit", "EffectsOnConsume"."DurationSeconds", "EffectsOnConsume"."Strength", "EffectsOnConsume"."ConsumableId", "Effects"."IsPositive" FROM ONLY "EffectsOnConsume" INNER JOIN ONLY "Effects" ON "EffectsOnConsume"."EffectId" = "Effects"."Id" WHERE "EffectsOnConsume"."ConsumableId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'ConsumableId');
}

async function formatConsumable(x, effects) {
  let formattedEffects = effects[x.Id].map(_formatEffectOnConsume);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Consumables,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Economy: {
        MaxTT: x.Value !== null ? Number(x.Value) : null,
      }
    },
    EffectsOnConsume: formattedEffects,
    Links: {
      "$Url": `/stimulants/${x.Id}`
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
  return await _getObjects(queries.CreatureControlCapsules, formatCreatureControlCapsule);
}

async function getCreatureControlCapsule(idOrName) {
  return await _getObject(idOrName, queries.CreatureControlCapsules, 'CreatureControlCapsules', formatCreatureControlCapsule);
}

function formatCreatureControlCapsule(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Capsules,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      MinProfessionLevel: x.ProfessionLevel !== null ? Number(x.ProfessionLevel) : null,
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
      "$Url": `/capsules/${x.Id}`,
    }
  }
}

// Decorations
async function getDecorations() {
  return await _getObjects(queries.Decorations, formatDecoration);
}

async function getDecoration(idOrName) {
  return await _getObject(idOrName, queries.Decorations, 'Decorations', formatDecoration);
}

function formatDecoration(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Decorations,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  return await _getObjects(queries.EffectChips, formatEffectChip, _getEffectsOnUse);
}

async function getEffectChip(idOrName) {
  return await _getObject(idOrName, queries.EffectChips, 'EffectChips', formatEffectChip, _getEffectsOnUse);
}

async function formatEffectChip(x, data) {
  let effects = (data[x.Id] ?? []).map(_formatEffectOnUse);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.EffectChips,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Range: x.Range !== null ? Number(x.Range) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
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
        IsSiB: x.IsSib === 1,
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
    EffectsOnUse: effects,
    Links: {
      "$Url": `/effectchips/${x.Id}`,
    }
  }
}

// Effects
async function getEffects() {
  return await _getObjects(queries.Effects, formatEffect);
}

async function getEffect(idOrName) {
  return await _getObject(idOrName, queries.Effects, 'Effects', formatEffect);
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
  return await _getObjects(queries.Enhancers, formatEnhancer);
}

async function getEnhancer(idOrName) {
  return await _getObject(idOrName, queries.Enhancers, 'Enhancers', formatEnhancer);
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

// EquipSets
async function getEquipSets() {
  return await _getObjects(queries.EquipSets, formatEquipSet, _getSetItemsAndEffects);
}

async function getEquipSet(idOrName) {
  return await _getObject(idOrName, queries.EquipSets, 'EquipSets', formatEquipSet, _getSetItemsAndEffects);
}

async function _getSetItemsAndEffects(ids) {
  const [items, effects] = await Promise.all([
    pool.query(`SELECT "EquipSets"."Id" AS "EquipSetId", "Items".* FROM ONLY "EquipSetItems" INNER JOIN ONLY "EquipSets" ON "EquipSetItems"."EquipSetId" = "EquipSets"."Id" INNER JOIN ONLY "Items" ON "EquipSetItems"."ItemId" = "Items"."Id" WHERE "EquipSetId" IN (${ids.join(',')})`).then(x => x.rows),
    pool.query(`SELECT "EffectsOnSetEquip"."SetId", "Effects"."Id", "Effects"."Name", "Effects"."Unit", "EffectsOnSetEquip"."Strength", "EffectsOnSetEquip"."MinSetPieces" FROM ONLY "EffectsOnSetEquip" INNER JOIN ONLY "Effects" ON "EffectsOnSetEquip"."EffectId" = "Effects"."Id" WHERE "SetId" IN (${ids.map(x => x + idOffsets.equipSet).join(',')})`).then(x => x.rows)
  ]);

  return {
    items: _groupBy(items, 'EquipSetId'),
    effects: _groupBy(effects, 'SetId')
  }
}

function formatEquipSet(x, data) {
  let effects = (data.effects[x.Id + idOffsets.equipSet] ?? []).map(_formatEffectOnSetEquip);
  let items = (data.items[x.Id] ?? []).map(formatItem);

  return {
    Id: x.Id,
    Name: x.Name,
    Items: items,
    EffectsOnSetEquip: effects,
    Links: {
      "$Url": `/equipsets/${x.Id}`
    }
  }
}

// Excavators
async function getExcavators() {
  return await _getObjects(queries.Excavators, formatExcavator, _getExcavatorData, idOffsets.Excavators);
}

async function getExcavator(idOrName) {
  return await _getObject(idOrName, queries.Excavators, 'Excavators', formatExcavator, _getExcavatorData, idOffsets.Excavators);
}

async function _getExcavatorData(ids) {
  const [EffectsOnEquip, Tiers] = await Promise.all([
    _getEffectsOnEquip(ids),
    _getTiers(ids)
  ]);

  return {
    EffectsOnEquip,
    Tiers
  }
}

function formatExcavator(x, data) {
  let effects = (data.EffectsOnEquip[x.Id + idOffsets.Excavators] ?? []).map(_formatEffectOnEquip);
  let tiers = Object.values((data.Tiers[x.Id + idOffsets.Excavators] ?? [])).map(_formatTier);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Excavators,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
    EffectsOnEquip: effects,
    Tiers: tiers,
    Links: {
      "$Url": `/excavators/${x.Id}`,
    }
  }
}

// FinderAmplifiers
async function getFinderAmplifiers() {
  return await _getObjects(queries.FinderAmplifiers, formatFinderAmplifier, _getEffectsOnEquip, idOffsets.FinderAmplifiers);
}

async function getFinderAmplifier(idOrName) {
  return await _getObject(idOrName, queries.FinderAmplifiers, 'FinderAmplifiers', formatFinderAmplifier, _getEffectsOnEquip, idOffsets.FinderAmplifiers);
}

function formatFinderAmplifier(x, data) {
  let effects = (data[x.Id + idOffsets.FinderAmplifiers] ?? []).map(_formatEffectOnEquip);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.FinderAmplifiers,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Efficiency: x.Efficiency !== null ? Number(x.Efficiency) : null,
      MinProfessionLevel: x.ProfessionMinimum !== null ? Number(x.ProfessionMinimum) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      }
    },
    EffectsOnEquip: effects,
    Links: {
      "$Url": `/finderamplifiers/${x.Id}`
    }
  }
}

// Finders
async function getFinders() {
  return await _getObjects(queries.Finders, formatFinder, _getFinderData, idOffsets.Finders);
}

async function getFinder(idOrName) {
  return await _getObject(idOrName, queries.Finders, 'Finders', formatFinder, _getFinderData, idOffsets.Finders);
}

async function _getFinderData(ids) {
  const [EffectsOnEquip, Tiers] = await Promise.all([
    _getEffectsOnEquip(ids),
    _getTiers(ids)
  ]);

  return {
    EffectsOnEquip,
    Tiers
  }
}

function formatFinder(x, data) {
  let effects = (data.EffectsOnEquip[x.Id + idOffsets.Finders] ?? []).map(_formatEffectOnEquip);
  let tiers = Object.values((data.Tiers[x.Id + idOffsets.Finders] ?? [])).map(_formatTier);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Finders,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
    EffectsOnEquip: effects,
    Tiers: tiers,
    Links: {
      "$Url": `/finders/${x.Id}`
    }
  }
}

// Furniture
async function getFurniture(idOrName = null) {
  if (idOrName !== null) {
    return await _getObject(idOrName, queries.Furniture, 'Furniture', formatFurniture);
  }
  else {
    return await _getObjects(queries.Furniture, formatFurniture);
  }
}

function formatFurniture(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Furniture,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  return await _getObjects(queries.Materials, formatMaterial);
}

async function getMaterial(idOrName) {
  return await _getObject(idOrName, queries.Materials, 'Materials', formatMaterial);
}

function formatMaterial(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Type: x.Type,
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
  return await _getObjects(queries.MedicalChips, formatMedicalChip, _getMedicalChipData, idOffsets.MedicalChips);
}

async function getMedicalChip(idOrName) {
  return await _getObject(idOrName, queries.MedicalChips, 'MedicalChips', formatMedicalChip, _getMedicalChipData, idOffsets.MedicalChips);
}

async function _getMedicalChipData(ids) {
  return {
    effectsOnEquip: await _getEffectsOnEquip(ids),
    effectsOnUse: await _getEffectsOnUse(ids)
  }
}
  

function formatMedicalChip(x, data) {
  let effectsOnEquip = (data.effectsOnEquip[x.Id + idOffsets.MedicalChips] ?? []).map(_formatEffectOnEquip);
  let effectsOnUse = (data.effectsOnUse[x.Id + idOffsets.MedicalChips] ?? []).map(_formatEffectOnUse);
  
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MedicalChips,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Range: x.Range !== null ? Number(x.Range) : null,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      MaxHeal: x.Heal !== null ? Number(x.Heal) : null,
      MinHeal: x.StartInterval !== null ? Number(x.StartInterval) : null,
      UsesPerMinute: x.Uses !== null ? Number(x.Uses) : null,
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
      Mindforce: {
        Level: x.Level !== null ? Number(x.Level) : null,
        Concentration: x.Concentration !== null ? Number(x.Concentration) : null,
        Cooldown: x.Cooldown !== null ? Number(x.Cooldown) : null,
        CooldownGroup: x.CooldownGroup !== null ? Number(x.CooldownGroup) : null,
      }
    },
    EffectsOnEquip: effectsOnEquip,
    EffectsOnUse: effectsOnUse,
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
  return await _getObjects(queries.MedicalTools, formatMedicalTool, _getMedicalToolData, idOffsets.MedicalTools);
}

async function getMedicalTool(idOrName) {
  return await _getObject(idOrName, queries.MedicalTools, 'MedicalTools', formatMedicalTool, _getMedicalToolData, idOffsets.MedicalTools);
}

async function _getMedicalToolData(ids) {
  const [effectsOnUse, effectsOnEquip, tiers] = await Promise.all([
    _getEffectsOnUse(ids),
    _getEffectsOnEquip(ids),
    _getTiers(ids)
  ]);

  return { 
    EffectsOnUse: effectsOnUse,
    EffectsOnEquip: effectsOnEquip,
    Tiers: tiers
  };
}

function formatMedicalTool(x, data) {
  let effectsOnUse = (data.EffectsOnUse[x.Id + idOffsets.MedicalTools] ?? []).map(_formatEffectOnUse);
  let effectsOnEquip = (data.EffectsOnEquip[x.Id + idOffsets.MedicalTools] ?? []).map(_formatEffectOnEquip);
  let tiers = Object.values(data.Tiers[x.Id + idOffsets.MedicalTools] ?? []).map(_formatTier);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MedicalTools,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
    Tiers: tiers,
    Links: {
      "$Url": `/medicaltools/${x.Id}`
    }
  }
}

// MindforceImplants
async function getMindforceImplants() {
  return await _getObjects(queries.MindforceImplants, formatMindforceImplant);
}

async function getMindforceImplant(idOrName) {
  return await _getObject(idOrName, queries.MindforceImplants, 'MindforceImplants', formatMindforceImplant);
}

function formatMindforceImplant(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MindforceImplants,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  return await _getObjects(queries.MiscTools, formatMiscTool);
}

async function getMiscTool(idOrName) {
  return await _getObject(idOrName, queries.MiscTools, 'MiscTools', formatMiscTool);
}

function formatMiscTool(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MiscTools,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Type: x.Type,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
        Decay: x.Decay !== null ? Number(x.Decay) : null,
      },
      Skill: {
        LearningIntervalStart: x.MinLevel !== null ? Number(x.MinLevel) : null,
        LearningIntervalEnd: x.MaxLevel !== null ? Number(x.MaxLevel) : null,
        IsSiB: x.IsSib === 1
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

  return await _getObjects(queries.MobLoots + whereClause, formatMobLoot);
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

  return await _getObjects(queries.MobMaturities + whereClause, formatMobMaturity, _getMobAttacks);
}

async function getMobMaturity(idOrName) {
  return await _getObject(idOrName, queries.MobMaturities, 'MobMaturities', formatMobMaturity, _getMobAttacks);
}

async function _getMobAttacks(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT * FROM ONLY "MobAttacks" WHERE "MaturityId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'MaturityId');
}

function formatMobMaturity(x, data) {
  let attacks = (data[x.Id] ?? (Array.isArray(data) ? data : [])).map(_formatMobAttack);

  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Health: x.Health !== null ? Number(x.Health) : null,
      AttacksPerMinute: x.AttackSpeed !== null ? Number(x.AttackSpeed) : null,
      Level: x.DangerLevel !== null ? Number(x.DangerLevel) : null,
      RegenerationInterval: x.RegenerationInterval !== null ? Number(x.RegenerationInterval) : null,
      RegenerationAmount: x.RegenerationAmount !== null ? Number(x.RegenerationAmount) : null,
      MissChance: x.MissChance !== null ? Number(x.MissChance) : null,
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
      Defense: {
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
    TotalDamage: x.Damage !== null ? Number(x.Damage) : null,
    IsAoE: x.IsAoE === 1,
  }
}

// MobSpecies
async function getMobSpecies(idOrName = null) {
  return idOrName !== null
    ? await _getObject(idOrName, queries.MobSpecies, 'MobSpecies', formatMobSpecies)
    : await _getObjects(queries.MobSpecies, formatMobSpecies);
}

function formatMobSpecies(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  return await _getObjects(queries.Mobs, formatMob, _getMobData);
}

async function getMob(idOrName) {
  return await _getObject(idOrName, queries.Mobs, 'Mobs', formatMob, _getMobData);
}

async function _getMobData(ids) {
  const [mobMaturities, mobLoots, mobSpawns] = await Promise.all([
    pool.query(queries.MobMaturities + ` WHERE "MobMaturities"."MobId" IN (${ids.join(',')})`)
      .then(async x => {
        let attacks = await _getMobAttacks(x.rows.map(y => (y.Id)));

        return x.rows.map(y => ({ ...y, Attacks: attacks[y.Id] ?? [] }));
      }),
    pool.query(queries.MobLoots + ` WHERE "MobLoots"."MobId" IN (${ids.join(',')})`).then(x => x.rows),
    pool.query(queries.MobSpawns + ` WHERE (SELECT COUNT(*) FROM "MobSpawnMaturities" WHERE "SpawnId" = "MobSpawns"."Id" AND "MaturityId" IN (SELECT DISTINCT "MobMaturities"."Id" FROM "MobMaturities" WHERE "MobMaturities"."MobId" IN (${ids.join(',')}))) > 0`)
      .then(async x => {

        let maturities = await _getMobSpawnMaturities(x.rows.map(y => (y.Id)));

        return x.rows.map(y => ({ ...y, Maturities: maturities[y.Id] ?? [] }));
      }),
  ]);

  return {
    Maturities: _groupBy(mobMaturities, 'MobId'),
    Loots: _groupBy(mobLoots, 'MobId'),
    MobSpawns: _groupBy(mobSpawns, 'MobId')
  }
}

function formatMob(x, data) {
  let maturities = (data.Maturities[x.Id] ?? []).map(x => formatMobMaturity(x, x.Attacks));
  let loots = (data.Loots[x.Id] ?? []).map(formatMobLoot);
  let spawns = (data.MobSpawns[x.Id] ?? []).map(x => formatMobSpawn(x, x.Maturities));

  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      AttackRange: x.AttackRange !== null ? Number(x.AttackRange) : null,
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
      Properties: {
        CodexBaseCost: x.CodexBaseCost !== null ? Number(x.CodexBaseCost) : null,
        IsCat4Codex: x.IsCat4Codex === 1,
      },
      Links: {
        "$Url": `/mobspecies/${x.SpeciesId}`
      }
    },
    Maturities: maturities,
    Spawns: spawns,
    Loots: loots,
    Links: {
      "$Url": `/mobs/${x.Id}`
    }
  }
}

// Pets
async function getPets() {
  return await _getObjects(queries.Pets, formatPet, _getPetEffects);
}

async function getPet(idOrName) {
  return await _getObject(idOrName, queries.Pets, 'Pets', formatPet, _getPetEffects);
}

async function _getPetEffects(ids) {
  let { rows } = await pool.query(`SELECT "PetEffects".*, "Effects"."Id" AS "EffectId", "Effects"."Name" AS "EffectName", "Effects"."Unit" AS "Unit", "Effects"."Description" AS "Description" FROM ONLY "PetEffects" INNER JOIN ONLY "Effects" ON "PetEffects"."EffectId" = "Effects"."Id" WHERE "PetEffects"."PetId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'PetId');
}

function formatPet(x, data) {
  let effects = (data[x.Id] ?? []).map(_formatPetEffect);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Pets,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
      Description: x.Description,
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
  return await _getObjects(queries.ProfessionCategories, formatProfessionCategory);
}

async function getProfessionCategory(idOrName) {
  return await _getObject(idOrName, queries.ProfessionCategories, 'ProfessionCategories', formatProfessionCategory);
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
  return await _getObjects(queries.Professions, formatProfession, _getProfessionSkillsAndUnlocks);
}

async function getProfession(idOrName) {
  return await _getObject(idOrName, queries.Professions, 'Professions', formatProfession, _getProfessionSkillsAndUnlocks);
}

async function _getProfessionSkillsAndUnlocks(ids) {
  let { rows: professionSkills } = await pool.query(`SELECT "ProfessionSkills"."Weight", "Skills"."Id" AS "SkillId", "Skills"."Name" AS "SkillName", "Skills"."HPIncrease" AS "HPIncrease", "Skills"."Hidden" AS "Hidden", "ProfessionId" FROM ONLY "ProfessionSkills" INNER JOIN ONLY "Skills" ON "ProfessionSkills"."SkillId" = "Skills"."Id" WHERE "ProfessionId" IN (${ids.join(',')})`);
  let { rows: skillUnlocks } = await pool.query(`SELECT "SkillUnlocks".*, "Skills"."Name" AS "Skill", "Skills"."HPIncrease" AS "HPIncrease", "Skills"."Hidden" AS "Hidden", "SkillUnlocks"."ProfessionId" FROM ONLY "SkillUnlocks" INNER JOIN ONLY "Skills" ON "SkillUnlocks"."SkillId" = "Skills"."Id" WHERE "SkillUnlocks"."ProfessionId" IN (${ids.join(',')})`);

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
    Weight: x.Weight !== null ? Number(x.Weight) : null,
    Skill: {
      Name: x.SkillName,
      Properties: {
        HpIncrease: x.HPIncrease !== null ? Number(x.HPIncrease) : null,
        IsHidden: x.Hidden === 1
      },
      Links: {
        "$Url": `/skills/${x.SkillId}`
      }
    }
  }
}

function _formatProfessionSkillUnlock(x) {
  return {
    Level: x.Level !== null ? Number(x.Level) : null,
    Skill: {
      Name: x.Skill,
      Properties: {
        HpIncrease: x.HPIncrease !== null ? Number(x.HPIncrease) : null,
        IsHidden: x.Hidden === 1
      },
      Links: {
        "$Url": `/skills/${x.SkillId}`
      }
    }
  }
}

// Refiners
async function getRefiners() {
  return await _getObjects(queries.Refiners, formatRefiner);
}

async function getRefiner(idOrName) {
  return await _getObject(idOrName, queries.Refiners, 'Refiners', formatRefiner);
}

function formatRefiner(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Refiners,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  else if (ingredients !== null) {
    whereClause = pgp.as.format(' WHERE "RefiningRecipes"."Id" IN (SELECT DISTINCT "RecipeId" FROM ONLY "RefiningIngredients" INNER JOIN ONLY "Items" ON "RefiningIngredients"."ItemId" = "Items"."Id" WHERE "Items"."Name" IN ($1:csv))', [ingredients.map(x => `${x}`)]);
  }

  return await _getObjects(queries.RefiningRecipes + whereClause, formatRefiningRecipe, _getRefiningRecipeIngredients);
}

async function getRefiningRecipe(idOrName) {
  return await _getObject(idOrName, queries.RefiningRecipes, 'RefiningRecipes', formatRefiningRecipe, _getRefiningRecipeIngredients);
}

async function _getRefiningRecipeIngredients(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "RefiningIngredients"."RecipeId", "RefiningIngredients"."Amount", "Items"."Id" AS "ItemId", "Items"."Name" AS "ItemName", "Items"."Type" AS "ItemType", "Items"."Value" AS "ItemValue" FROM ONLY "RefiningIngredients" INNER JOIN ONLY "Items" ON "RefiningIngredients"."ItemId" = "Items"."Id" WHERE "RefiningIngredients"."RecipeId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'RecipeId');
}

function formatRefiningRecipe(x, data) {
  let ingredients = (data[x.Id] ?? []).map(formatRefiningIngredient);

  return {
    Id: x.Id,
    Ingredients: ingredients,
    Amount: x.Amount !== null ? Number(x.Amount) : null,
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
  return await _getObjects(queries.Scanners, formatScanner);
}

async function getScanner(idOrName) {
  return await _getObject(idOrName, queries.Scanners, 'Scanners', formatScanner);
}

function formatScanner(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Scanners,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  return await _getObjects(queries.Signs, formatSign);
}

async function getSign(idOrName) {
  return await _getObject(idOrName, queries.Signs, 'Signs', formatSign);
}

function formatSign(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Signs,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  return await _getObjects(queries.SkillCategories, formatSkillCategory);
}

async function getSkillCategory(idOrName) {
  return await _getObject(idOrName, queries.SkillCategories, 'SkillCategories', formatSkillCategory);
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
  return await _getObjects(queries.Skills, formatSkill, _getSkillUnlocks);
}

async function getSkill(idOrName) {
  return await _getObject(idOrName, queries.Skills, 'Skills', formatSkill, _getSkillUnlocks);
}

async function _getSkillUnlocks(ids) {
  let { rows: skillProfessions } = await pool.query(`
    SELECT "ProfessionSkills".*, "Professions"."Name" AS "ProfessionName", "ProfessionCategories"."Name" AS "Category"
    FROM ONLY "ProfessionSkills"
    INNER JOIN ONLY "Professions" ON "ProfessionSkills"."ProfessionId" = "Professions"."Id"
    INNER JOIN ONLY "ProfessionCategories" ON "Professions"."CategoryId" = "ProfessionCategories"."Id"
    WHERE "ProfessionSkills"."SkillId" IN (${ids.join(',')})`);

  let { rows: skillUnlocks } = await pool.query(`
    SELECT "SkillUnlocks".*, "Professions"."Name" AS "ProfessionName", "ProfessionCategories"."Name" AS "Category"
    FROM ONLY "SkillUnlocks"
    INNER JOIN ONLY "Professions" ON "SkillUnlocks"."ProfessionId" = "Professions"."Id"
    INNER JOIN ONLY "ProfessionCategories" ON "Professions"."CategoryId" = "ProfessionCategories"."Id"
    WHERE "SkillUnlocks"."SkillId" IN (${ids.join(',')})`);

  return {
    SkillProfessions: _groupBy(skillProfessions, 'SkillId'), 
    SkillUnlocks: _groupBy(skillUnlocks, 'SkillId'),
  };
}

function formatSkill(x, data) {
  let professionSkills = (data.SkillProfessions[x.Id] ?? []).map(_formatSkillProfession);
  let unlocks = (data.SkillUnlocks[x.Id] ?? []).map(_formatSkillUnlock);

  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      HpIncrease: x.HPIncrease !== null ? Number(x.HPIncrease) : null,
      IsHidden: unlocks !== null && unlocks.length > 0,
    },
    Professions: professionSkills,
    Unlocks: unlocks.length > 0 ? unlocks : null,
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

function _formatSkillProfession(x) {
  return {
    Weight: x.Weight !== null ? Number(x.Weight) : null,
    Profession: {
      Name: x.ProfessionName,
      Properties: {
        Category: x.Category
      },
      Links: {
        "$Url": `/professions/${x.ProfessionId}`
      }
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

// Strongboxes
async function getStrongboxes() {
  return await _getObjects(queries.Strongboxes, formatStrongbox, _getLoots);
}

async function getStrongbox(idOrName) {
  return await _getObject(idOrName, queries.Strongboxes, 'Strongboxes', formatStrongbox, _getLoots);
}

async function _getLoots(ids) {
  let { rows: loots } = await pool.query(`
    SELECT "StrongboxLoots".*, "Items"."Name" AS "Name", "Items"."Type" AS "Type", "Items"."Value" AS "Value"`);

  return {
    Loots: _groupBy(loots, 'StrongboxId'),
  };
}

function formatStrongbox(x, data) {
  let loots = (data.Loots[x.Id] ?? []).map(_formatLoot);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Strongboxes,
    Name: x.Name,
    Properties: {
      Description: x.Description,
    },
    Loots: loots,
  }
}

function _formatLoot(x) {
  return {
    Rarity: x.Rarity,
    AvailableFrom: x.AvailableFrom,
    AvailableUntil: x.AvailableUntil,
    Item: {
      Name: x.Name,
      Properties: {
        Type: x.Type,
        Economy: {
          MaxTT: x.Value !== null ? Number(x.Value) : null,
        }
      },
      Links: {
        "$Url": `/${x.Type.toLowerCase()}s/${x.ItemId % 100000}`
      }
    }
  }
}

// StorageContainers
async function getStorageContainers() {
  return await _getObjects(queries.StorageContainers, formatStorageContainer);
}

async function getStorageContainer(idOrName) {
  return await _getObject(idOrName, queries.StorageContainers, 'StorageContainers', formatStorageContainer);
}

function formatStorageContainer(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.StorageContainers,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
  return await _getObjects(queries.TeleportationChips, formatTeleportationChip);
}

async function getTeleportationChip(idOrName) {
  return await _getObject(idOrName, queries.TeleportationChips, 'TeleportationChips', formatTeleportationChip);
}

function formatTeleportationChip(x) {
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.TeleportationChips,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
async function getTiers(itemId = null, isArmorSet = null, tier = null) {
  let whereClause = '';

  if (itemId != null) {
    whereClause = pgp.as.format(`WHERE "ItemId" = $1`, itemId);
  }

  if (isArmorSet != null) {
    whereClause = pgp.as.format(whereClause.length > 0 ? `${whereClause} AND "IsArmorSet" = $1` : `WHERE "IsArmorSet" = $1`, isArmorSet);
  }

  if (tier != null) {
    whereClause = pgp.as.format(whereClause.length > 0 ? `${whereClause} AND "Tier" = $1` : `WHERE "Tier" = $1`, tier);
  }

  return await _getObjects(`${queries.Tiers} ${whereClause}`, formatTier, _getTierMaterials);
}

async function getTier(idOrName) {
  return await _getObject(idOrName, queries.Tiers, null, formatTier, _getTierMaterials);
}

async function _getTierMaterials(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "TierMaterials".*, "Materials"."Name" AS "MaterialName", "Materials"."Value" AS "Value", "Materials"."Weight" AS "Weight", "Materials"."Type" AS "Type" FROM ONLY "TierMaterials" INNER JOIN ONLY "Materials" ON "TierMaterials"."MaterialId" = "Materials"."Id" WHERE "TierMaterials"."TierId" IN (${ids.join(',')})`);

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
  return await _getObjects(queries.VehicleAttachmentTypes, formatVehicleAttachmentType);
}

async function getVehicleAttachmentType(idOrName) {
  return await _getObject(idOrName, queries.VehicleAttachmentTypes, 'VehicleAttachmentTypes', formatVehicleAttachmentType);
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
  return await _getObjects(queries.Vehicles, formatVehicle, _getAttachmentSlots);
}

async function getVehicle(idOrName) {
  return await _getObject(idOrName, queries.Vehicles, 'Vehicles', formatVehicle, _getAttachmentSlots);
}

async function _getAttachmentSlots(ids) {
  let { rows } = await pool.query(`SELECT "VehicleAttachmentSlots".*, "VehicleAttachmentTypes"."Name" AS "Type" FROM ONLY "VehicleAttachmentSlots" INNER JOIN ONLY "VehicleAttachmentTypes" ON "VehicleAttachmentTypes"."Id" = "VehicleAttachmentSlots"."AttachmentId" WHERE "VehicleId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'VehicleId');
}

function formatVehicle(x, data) {
  let slots = (data[x.Id] ?? []).map(_formatAttachmentSlot);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Vehicles,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      SpawnedWeight: x.SpawnedWeight !== null ? Number(x.SpawnedWeight) : null,
      PassengerCount: x.Passengers !== null ? Number(x.Passengers) : null,
      ItemCapacity: x.StorageCapacity !== null ? Number(x.StorageCapacity) : null,
      WeightCapacity: x.WeightCapacity !== null ? Number(x.WeightCapacity) : null,
      WheelGrip: x.WheelGrip !== null ? Number(x.WheelGrip) : null,
      EnginePower: x.EnginePower !== null ? Number(x.EnginePower) : null,
      MaxSpeed: x.MaxSpeed !== null ? Number(x.MaxSpeed) : null,
      MaxStructuralIntegrity: x.MaxSI !== null ? Number(x.MaxSI) : null,
      Economy: {
        MaxTT: x.MaxTT !== null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT !== null ? Number(x.MinTT) : null,
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
async function getVendors(offerItems = null) {
  let whereClause = '';

  if (offerItems !== null) {
    whereClause = pgp.as.format(' WHERE "Vendors"."Id" IN (SELECT DISTINCT "VendorId" FROM ONLY "VendorOffers" INNER JOIN ONLY "Items" ON "VendorOffers"."ItemId" = "Items"."Id" WHERE "Items"."Name" IN ($1:csv))', [offerItems.map(x => `${x}`)]);
  }

  return await _getObjects(queries.Vendors + whereClause, formatVendor, _getVendorOffers);
}

async function getVendor(idOrName) {
  return await _getObject(idOrName, queries.Vendors, 'Vendors', formatVendor, _getVendorOffers);
}

async function _getVendorOffers(ids) {
  if (ids.length === 0) {
    return {
      Offers: {},
      Prices: {}
    };
  }

  let { rows: offers } = await pool.query(`SELECT "VendorOffers".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" AS "Value" FROM ONLY "VendorOffers" INNER JOIN ONLY "Items" ON "VendorOffers"."ItemId" = "Items"."Id" WHERE "VendorId" IN (${ids.join(',')})`);

  let offerIds = offers.map(x => x.Id);

  if (offerIds.length === 0) {
    return {
      Offers: {},
      Prices: {}
    };
  }

  let { rows: prices } = await pool.query(`SELECT "VendorOfferPrices".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" AS "Value" FROM ONLY "VendorOfferPrices" INNER JOIN ONLY "Items" ON "VendorOfferPrices"."ItemId" = "Items"."Id" WHERE "OfferId" IN (${offerIds.join(',')})`);

  return {
    Offers: _groupBy(offers, 'VendorId'),
    Prices: _groupBy(prices, 'OfferId'),
  }
}

function formatVendor(x, data) {
  let offers = data.Offers[x.Id] ?? [];
  offers.forEach(offer => offer.Prices = (data.Prices[offer.Id] ?? []).map(_formatVendorOfferPrice));
  offers = offers.map(_formatVendorOffer);

  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Coordinates: {
        Longitude: x.Longitude !== null ? Number(x.Longitude) : null,
        Latitude: x.Latitude !== null ? Number(x.Latitude) : null,
        Altitude: x.Altitude !== null ? Number(x.Altitude) : null,
      }
    },
    Planet: {
      Name: x.Planet,
      Properties: {
        TechnicalName: x.PlanetTechnicalName
      },
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
    IsLimited: x.IsLimited,
    Item: {
      Name: x.Item,
      Properties: {
        Type: x.ItemType,
        Economy: {
          Value: x.Value !== null ? Number(x.Value) : null,
        },
      },
      Links: {
        "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}`
      }
    },
    Prices: x.Prices ?? []
  }
}

function _formatVendorOfferPrice(x) {
  return {
    Amount: x.Amount !== null ? Number(x.Amount) : null,
    Item: {
      Name: x.Item,
      Properties: {
        Type: x.ItemType,
        Economy: {
          Value: x.Value !== null ? Number(x.Value) : null,
        },
      }, 
      Links: {
        "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}`
      }
    }
  }
}

// VendorOffers
async function getVendorOffers(items, prices = null) {
  let whereClause = '';

  if (items !== null) {
    whereClause += pgp.as.format(' WHERE "Items"."Name" IN ($1:csv)', [items.map(x => `${x}`)]);
  }

  let objects = await _getObjects(queries.VendorOffers + whereClause, formatVendorOffer, _getVendorOfferPrices);

  if (prices !== null) {
    objects = objects.filter(x => (x.Prices ?? []).some(y => prices.includes(y.Item.Name)));
  }

  return objects;
}

async function getVendorOffer(idOrName) {
  return await _getObject(idOrName, queries.VendorOffers, 'VendorOffers', formatVendorOffer, _getVendorOfferPrices);
}

async function _getVendorOfferPrices(ids) {
  if (ids.length === 0) {
    return {};
  }

  let { rows } = await pool.query(`SELECT "VendorOfferPrices".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" FROM ONLY "VendorOfferPrices" INNER JOIN ONLY "Items" ON "VendorOfferPrices"."ItemId" = "Items"."Id" WHERE "OfferId" IN (${ids.join(',')})`);

  return _groupBy(rows, 'OfferId');
}

function formatVendorOffer(x, data) {
  let prices = (data[x.Id] ?? []).map(_formatVendorOfferPrice);

  return {
    Id: x.Id,
    IsLimited: x.IsLimited,
    Item: {
      Name: x.Item,
      Properties: {
        Type: x.ItemType,
        Economy: {
          Value: x.Value !== null ? Number(x.ItemValue) : null,
        }
      },
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
  return await _getObjects(queries.WeaponAmplifiers, formatWeaponAmplifier, _getEffectsOnEquip, idOffsets.WeaponAmplifiers);
}

async function getWeaponAmplifier(idOrName) {
  return await _getObject(idOrName, queries.WeaponAmplifiers, 'WeaponAmplifiers', formatWeaponAmplifier, _getEffectsOnEquip, idOffsets.WeaponAmplifiers);
}

function formatWeaponAmplifier(x, data) {
  let effects = (data[x.Id + idOffsets.WeaponAmplifiers] ?? []).map(_formatEffectOnEquip);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.WeaponAmplifiers,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
    EffectsOnEquip: effects,
    Links: {
      "$Url": `/weaponamplifiers/${x.Id}`
    }
  }
}

// WeaponVisionAttachments
async function getWeaponVisionAttachments() {
  return await _getObjects(queries.WeaponVisionAttachments, formatWeaponVisionAttachment, _getEffectsOnEquip, idOffsets.WeaponVisionAttachments);
}

async function getWeaponVisionAttachment(idOrName) {
  return await _getObject(idOrName, queries.WeaponVisionAttachments, 'WeaponVisionAttachments', formatWeaponVisionAttachment, _getEffectsOnEquip, idOffsets.WeaponVisionAttachments);
}

function formatWeaponVisionAttachment(x, data) {
  let effects = (data[x.Id + idOffsets.WeaponVisionAttachments] ?? []).map(_formatEffectOnEquip);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.WeaponVisionAttachments,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
    EffectsOnEquip: effects,
    Links: {
      "$Url": `/weaponvisionattachments/${x.Id}`
    }
  }
}

// Weapons
async function getWeapons() {
  return await _getObjects(queries.Weapons, formatWeapon, _getWeaponData, idOffsets.Weapons);
}

async function getWeapon(idOrName) {
  return await _getObject(idOrName, queries.Weapons, 'Weapons', formatWeapon, _getWeaponData, idOffsets.Weapons);
}

async function _getWeaponData(ids) {
  if (ids.length === 0) {
    return {};
  }

  return {
    EffectsOnEquip: await _getEffectsOnEquip(ids),
    EffectsOnUse: await _getEffectsOnUse(ids),
    Tiers: await _getTiers(ids),
  };
}

function formatWeapon(x, data) {
  let effectsOnEquip = (data.EffectsOnEquip[x.Id + idOffsets.Weapons] ?? []).map(_formatEffectOnEquip);
  let effectsOnUse = (data.EffectsOnUse[x.Id + idOffsets.Weapons] ?? []).map(_formatEffectOnUse);
  let tiers = Object.values((data.Tiers[x.Id + idOffsets.Weapons] ?? [])).map(_formatTier);

  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.Weapons,
    Name: x.Name,
    Properties: {
      Description: x.Description,
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
    EffectsOnEquip: effectsOnEquip,
    EffectsOnUse: effectsOnUse,
    Tiers: tiers,
    Links: {
      "$Url": `/weapons/${x.Id}`
    }
  }
}

function _formatTier(x) {
  let tier = x[0];

  return {
    Name: `${tier.ItemName} Tier ${tier.Tier}`,
    Properties: {
      Tier: tier.Tier,
      IsArmorSet: tier.IsArmorSet === 1,
    },
    Materials: x.map(_formatTierMaterial),
    Links: {
      "$Url": `/tiers?ItemId=${tier.ItemId}&IsArmorSet=${tier.IsArmorSet}&Tier=${tier.Tier}`
    }
  }
}


module.exports = { pool,
  search,
  searchItems,

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
  getClothing, getClothings,
  getConsumable, getConsumables,
  getCreatureControlCapsule, getCreatureControlCapsules,
  getDecoration, getDecorations,
  getEffectChip, getEffectChips,
  getEffect, getEffects,
  getEnhancer, getEnhancers,
  getEquipSet, getEquipSets,
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
  getMobSpawn, getMobSpawns,
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
  getStrongbox, getStrongboxes,
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
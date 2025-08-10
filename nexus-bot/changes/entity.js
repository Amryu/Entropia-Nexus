export const UpsertConfigs = {
  Shop: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Description },
      { name: "MaxGuests", value: x => x.MaxGuests ?? null },
      { name: "Longitude", value: x => x.Coordinates?.Longitude ?? null },
      { name: "Latitude", value: x => x.Coordinates?.Latitude ?? null },
      { name: "Altitude", value: x => x.Coordinates?.Altitude ?? null },
      { name: "PlanetId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [x.Planet?.Name]).then(res => res.rows[0]?.Id ?? null) },
      // Type is an enum EstateType in DB; use text value 'Shop'
      { name: "Type", value: _ => 'Shop' },
      { name: "ItemTradeAvailable", value: _ => true }
    ],
    table: "Estates",
    relationChangeFunc: async (client, id, x) => await applyEstateSectionsChanges(client, id, x.Sections ?? [])
  },
  Weapon: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Class", value: x => x.Properties.Class },
      { name: "Type", value: x => x.Properties.Type },
      { name: "Category", value: x => x.Properties.Category },
      { name: "Range", value: x => x.Properties.Range },
      { name: "Attacks", value: x => x.Properties.UsesPerMinute },
      { name: "ImpactRadius", value: x => x.Properties.ImpactRadius },
      { name: "MFLevel", value: x => x.Properties.Mindforce?.Level },
      { name: "Concentration", value: x => x.Properties.Mindforce?.Concentration },
      { name: "Cooldown", value: x => x.Properties.Mindforce?.Cooldown },
      { name: "CooldownGroup", value: x => x.Properties.Mindforce?.CooldownGroup },
      { name: "Efficiency", value: x => x.Properties.Economy.Efficiency },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
      { name: "AmmoBurn", value: x => x.Properties.Economy.AmmoBurn },
      { name: "SIB", value: x => x.Properties.Skill.IsSiB ? 1 : 0 },
      { name: "MinHit", value: x => x.Properties.Skill.Hit.LearningIntervalStart },
      { name: "MaxHit", value: x => x.Properties.Skill.Hit.LearningIntervalEnd },
      { name: "MinDmg", value: x => x.Properties.Skill.Dmg.LearningIntervalStart },
      { name: "MaxDmg", value: x => x.Properties.Skill.Dmg.LearningIntervalEnd },
      { name: "Stab", value: x => x.Properties.Damage.Stab },
      { name: "Cut", value: x => x.Properties.Damage.Cut },
      { name: "Impact", value: x => x.Properties.Damage.Impact },
      { name: "Penetration", value: x => x.Properties.Damage.Penetration },
      { name: "Shrapnel", value: x => x.Properties.Damage.Shrapnel },
      { name: "Burn", value: x => x.Properties.Damage.Burn },
      { name: "Cold", value: x => x.Properties.Damage.Cold },
      { name: "Acid", value: x => x.Properties.Damage.Acid },
      { name: "Electric", value: x => x.Properties.Damage.Electric },
      { name: "AmmoId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Materials" WHERE "Name" = $1`, [x.Ammo.Name]).then(res => res.rows[0]?.Id) },
      { name: "AttachmentTypeId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "VehicleAttachmentTypes" WHERE "Name" = $1`, [x.AttachmentType.Name]).then(res => res.rows[0]?.Id) },
      { name: "ProfessionHitId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.ProfessionHit.Name]).then(res => res.rows[0]?.Id) },
      { name: "ProfessionDmgId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.ProfessionDmg.Name]).then(res => res.rows[0]?.Id) }
    ],
    offset: 2000000,
    table: "Weapons",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip),
      applyEffectsOnUseChanges(client, id, x.EffectsOnUse),
      applyTierChanges(client, id, x.Tiers)
    ])
  },
  ArmorSet: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Durability", value: x => x.Properties.Economy.Durability },
      { name: "Stab", value: x => x.Properties.Defense.Stab },
      { name: "Cut", value: x => x.Properties.Defense.Cut },
      { name: "Impact", value: x => x.Properties.Defense.Impact },
      { name: "Penetration", value: x => x.Properties.Defense.Penetration },
      { name: "Shrapnel", value: x => x.Properties.Defense.Shrapnel },
      { name: "Burn", value: x => x.Properties.Defense.Burn },
      { name: "Cold", value: x => x.Properties.Defense.Cold },
      { name: "Acid", value: x => x.Properties.Defense.Acid },
      { name: "Electric", value: x => x.Properties.Defense.Electric }
    ],
    table: "ArmorSets",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnSetEquipChanges(client, id, x.EffectsOnSetEquip),
      applyArmorChanges(client, id, x.Armors.flat()),
      applyTierChanges(client, id, x.Tiers, true)
    ])
  },
  MedicalTool: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Heal", value: x => x.Properties.MaxHeal },
      { name: "StartInterval", value: x => x.Properties.MinHeal },
      { name: "Uses", value: x => x.Properties.UsesPerMinute },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
      { name: "MinLvl", value: x => x.Properties.Skill.LearningIntervalStart },
      { name: "MaxLvl", value: x => x.Properties.Skill.LearningIntervalEnd },
      { name: "SIB", value: x => x.Properties.Skill.IsSiB ? 1 : 0 }
    ],
    offset: 4100000,
    table: "MedicalTools",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip),
      applyEffectsOnUseChanges(client, id, x.EffectsOnUse),
      applyTierChanges(client, id, x.Tiers)
    ])
  },
  MedicalChip: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Level", value: x => x.Properties.Mindforce.Level },
      { name: "Range", value: x => x.Properties.Range },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Heal", value: x => x.Properties.MaxHeal },
      { name: "StartInterval", value: x => x.Properties.MinHeal },
      { name: "Uses", value: x => x.Properties.UsesPerMinute },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
      { name: "AmmoBurn", value: x => x.Properties.Economy.AmmoBurn },
      { name: "Concentration", value: x => x.Properties.Mindforce.Concentration },
      { name: "Cooldown", value: x => x.Properties.Mindforce.Cooldown },
      { name: "CooldownGroup", value: x => x.Properties.Mindforce.CooldownGroup },
      { name: "AmmoId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Materials" WHERE "Name" = $1`, [x.Ammo.Name]).then(res => res.rows[0]?.Id) },
      { name: "MinLvl", value: x => x.Properties.Skill.LearningIntervalStart },
      { name: "MaxLvl", value: x => x.Properties.Skill.LearningIntervalEnd },
      { name: "SIB", value: x => x.Properties.Skill.IsSiB ? 1 : 0 }
    ],
    offset: 4800000,
    table: "MedicalChips",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip),
      applyEffectsOnUseChanges(client, id, x.EffectsOnUse)
    ])
  },
  Refiner: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Uses", value: x => x.Properties.UsesPerMinute },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
    ],
    table: "Refiners"
  },
  Scanner: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Range", value: x => x.Properties.Range },
      { name: "Uses", value: x => x.Properties.UsesPerMinute },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay }
    ],
    table: "Scanners"
  },
  Finder: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Range", value: x => x.Properties.Range },
      { name: "Depth", value: x => x.Properties.Depth },
      { name: "Uses", value: x => x.Properties.UsesPerMinute },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
      { name: "IntervalStart", value: x => x.Properties.Skill.LearningIntervalStart },
      { name: "IntervalEnd", value: x => x.Properties.Skill.LearningIntervalEnd },
      { name: "Probes", value: x => x.Properties.Economy.AmmoBurn }
    ],
    offset: 4500000,
    table: "Finders",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip),
      applyTierChanges(client, id, x.Tiers)
    ])
  },
  Excavator: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Efficiency", value: x => x.Properties.Efficiency },
      { name: "Uses", value: x => x.Properties.UsesPerMinute },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
      { name: "IntervalStart", value: x => x.Properties.Skill.LearningIntervalStart },
      { name: "IntervalEnd", value: x => x.Properties.Skill.LearningIntervalEnd },
    ],
    offset: 4600000,
    table: "Excavators",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip),
      applyTierChanges(client, id, x.Tiers)
    ])
  },
  TeleportationChip: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Level", value: x => x.Properties.Mindforce.Level },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Range", value: x => x.Properties.Range },
      { name: "UsesPerMinute", value: x => x.Properties.UsesPerMinute },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
      { name: "AmmoBurn", value: x => x.Properties.Economy.AmmoBurn },
      { name: "Concentration", value: x => x.Properties.Mindforce.Concentration },
      { name: "Cooldown", value: x => x.Properties.Mindforce.Cooldown },
      { name: "CooldownGroup", value: x => x.Properties.Mindforce.CooldownGroup },
      { name: "MinLevel", value: x => x.Properties.Skill.LearningIntervalStart },
      { name: "MaxLevel", value: x => x.Properties.Skill.LearningIntervalEnd },
      { name: "AmmoId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Materials" WHERE "Name" = $1`, [x.Ammo.Name]).then(res => res.rows[0]?.Id) },
    ],
    offset: 4810000,
    table: "TeleportationChips"
  },
  EffectChip: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Level", value: x => x.Properties.Mindforce.Level },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Range", value: x => x.Properties.Range },
      { name: "Uses", value: x => x.Properties.UsesPerMinute },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
      { name: "AmmoBurn", value: x => x.Properties.Economy.AmmoBurn },
      { name: "Concentration", value: x => x.Properties.Mindforce.Concentration },
      { name: "Cooldown", value: x => x.Properties.Mindforce.Cooldown },
      { name: "CooldownGroup", value: x => x.Properties.Mindforce.CooldownGroup },
      { name: "MinLevel", value: x => x.Properties.Skill.LearningIntervalStart },
      { name: "MaxLevel", value: x => x.Properties.Skill.LearningIntervalEnd },
      { name: "IsSib", value: x => x.Properties.Skill.IsSiB ? 1 : 0 },
      { name: "ProfessionId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.Profession.Name]).then(res => res.rows[0]?.Id) },
      { name: "AmmoId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Materials" WHERE "Name" = $1`, [x.Ammo.Name]).then(res => res.rows[0]?.Id) },
    ],
    offset: 4820000,
    table: "EffectChips",
    relationChangeFunc: async (client, id, x) => await applyEffectsOnUseChanges(client, id, x.EffectsOnUse)
  },
  MiscTool: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
      { name: "ProfessionId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.Profession.Name]).then(res => res.rows[0]?.Id) },
      { name: "IsSib", value: x => x.Properties.Skill.IsSiB ? 1 : 0 },
      { name: "MinLevel", value: x => x.Properties.Skill.LearningIntervalStart },
      { name: "MaxLevel", value: x => x.Properties.Skill.LearningIntervalEnd }
    ],
    offset: 4200000,
    table: "MiscTools"
  },
  WeaponAmplifier: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Type", value: x => x.Properties.Type},
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
      { name: "Ammo", value: x => x.Properties.Economy.AmmoBurn },
      { name: "Efficiency", value: x => x.Properties.Economy.Efficiency },
      { name: "Stab", value: x => x.Properties.Damage.Stab },
      { name: "Cut", value: x => x.Properties.Damage.Cut },
      { name: "Impact", value: x => x.Properties.Damage.Impact },
      { name: "Penetration", value: x => x.Properties.Damage.Penetration },
      { name: "Shrapnel", value: x => x.Properties.Damage.Shrapnel },
      { name: "Burn", value: x => x.Properties.Damage.Burn },
      { name: "Cold", value: x => x.Properties.Damage.Cold },
      { name: "Acid", value: x => x.Properties.Damage.Acid },
      { name: "Electric", value: x => x.Properties.Damage.Electric },
    ],
    offset: 5100000,
    table: "WeaponAmplifiers",
    relationChangeFunc: async (client, id, x) => await applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip)
  },
  WeaponVisionAttachment: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Type", value: x => x.Properties.Type},
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Zoom", value: x => x.Properties.Zoom },
      { name: "SkillMod", value: x => x.Properties.SkillModification },
      { name: "SkillBonus", value: x => x.Properties.SkillBonus },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
      { name: "Efficiency", value: x => x.Properties.Economy.Efficiency },
    ],
    offset: 5200000,
    table: "WeaponVisionAttachments",
    relationChangeFunc: async (client, id, x) => await applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip)
  },
  Absorber: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Efficiency", value: x => x.Properties.Economy.Efficiency },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Absorption", value: x => x.Properties.Economy.Absorption },
    ],
    offset: 5300000,
    table: "Absorbers"
  },
  FinderAmplifier: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Efficiency", value: x => x.Properties.Efficiency },
      { name: "ProfessionMinimum", value: x => x.Properties.MinProfessionLevel },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
    ],
    offset: 5400000,
    table: "FinderAmplifiers",
    relationChangeFunc: async (client, id, x) => await applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip)
  },
  ArmorPlating: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Durability", value: x => x.Properties.Economy.Durability },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Block", value: x => x.Properties.Economy.Block },
      { name: "Stab", value: x => x.Properties.Defense.Stab },
      { name: "Cut", value: x => x.Properties.Defense.Cut },
      { name: "Impact", value: x => x.Properties.Defense.Impact },
      { name: "Penetration", value: x => x.Properties.Defense.Penetration },
      { name: "Shrapnel", value: x => x.Properties.Defense.Shrapnel },
      { name: "Burn", value: x => x.Properties.Defense.Burn },
      { name: "Cold", value: x => x.Properties.Defense.Cold },
      { name: "Acid", value: x => x.Properties.Defense.Acid },
      { name: "Electric", value: x => x.Properties.Defense.Electric },
    ],
    offset: 5500000,
    table: "ArmorPlatings"
  },
  MindforceImplant: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "MaxLvl", value: x => x.Properties.MaxProfessionLevel },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Absorption", value: x => x.Properties.Economy.Absorption },
    ],
    offset: 5700000,
    table: "MindforceImplants"
  },
  Blueprint: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Type", value: x => x.Properties.Type },
      { name: "Level", value: x => x.Properties.Level },
      { name: "ItemId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Items" WHERE "Name" = $1`, [x.Product.Name]).then(res => res.rows[0]?.Id) },
      { name: "ProfessionId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.Profession.Name]).then(res => res.rows[0]?.Id) },
      { name: "BookId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "BlueprintBooks" WHERE "Name" = $1`, [x.Book.Name]).then(res => res.rows[0]?.Id) },
      { name: "MinLvl", value: x => x.Properties.Skill.LearningIntervalStart },
      { name: "MaxLvl", value: x => x.Properties.Skill.LearningIntervalEnd },
      { name: "IsSib", value: x => x.Properties.Skill.IsSiB ? 1 : 0 },
      { name: "IsBoosted", value: x => x.Properties.Skill.IsBoosted ? 1 : 0 },
      { name: "MinimumCraftAmount", value: x => x.Properties.MinimumCraftAmount },
      { name: "MaximumCraftAmount", value: x => x.Properties.MaximumCraftAmount },
    ],
    offset: 6000000,
    table: "Blueprints",
    relationChangeFunc: async (client, id, x) => await applyBlueprintMaterialsChanges(client, id - 6000000, x.Materials)
  },
  Material: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Value", value: x => x.Properties.Economy.MaxTT }
    ],
    offset: 1000000,
    table: "Materials",
    relationChangeFunc: async (client, id, x) => {
      if (x.RefiningRecipes) {
        await applyRefiningRecipesChanges(client, id - 1000000, x.RefiningRecipes);
      }
    }
  },
  Pet: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Rarity", value: x => x.Properties.Rarity },
      { name: "Training", value: x => x.Properties.TrainingDifficulty },
      { name: "NutrioCapacity", value: x => x.Properties.NutrioCapacity },
      { name: "NutrioConsumption", value: x => x.Properties.NutrioConsumptionPerHour },
      { name: "Exportable", value: x => x.Properties.ExportableLevel },
      { name: "TamingLevel", value: x => x.Properties.TamingLevel },
      { name: "PlanetId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [x.Planet.Name]).then(res => res.rows[0]?.Id) },
    ],
    offset: 11000000,
    table: "Pets",
    relationChangeFunc: async (client, id, x) => await applyPetEffectChanges(client, id - 11000000, x.Effects)
  },
  Consumable: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Type", value: x => x.Properties.Type },
      { name: "Value", value: x => x.Properties.Economy.MaxTT }
    ],
    offset: 10000000,
    table: "Consumables",
    relationChangeFunc: async (client, id, x) => await applyEffectsOnConsumeChanges(client, id - 10000000, x.EffectsOnConsume)
  },
  Capsule: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "ProfessionLevel", value: x => x.Properties.MinProfessionLevel },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MobId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Mobs" WHERE "Name" = $1`, [x.Mob.Name]).then(res => res.rows[0]?.Id) },
      { name: "ScanningProfessionId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.Profession.Name]).then(res => res.rows[0]?.Id) },
    ],
    offset: 10100000,
    table: "CreatureControlCapsules"
  },
  Vehicle: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Passengers", value: x => x.Properties.PassengerCount },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "SpawnedWeight", value: x => x.Properties.SpawnedWeight },
      { name: "StorageCount", value: x => x.Properties.ItemCapacity },
      { name: "StorageWeight", value: x => x.Properties.WeightCapacity },
      { name: "FuelMaterialId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Materials" WHERE "Name" = $1`, [x.Fuel.Name]).then(res => res.rows[0]?.Id) },
      { name: "FuelActive", value: x => x.Properties.Economy.FuelConsumptionActive },
      { name: "FuelPassive", value: x => x.Properties.Economy.FuelConsumptionPassive },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "WheelGrip", value: x => x.Properties.WheelGrip },
      { name: "EnginePower", value: x => x.Properties.EnginePower },
      { name: "MaxSpeed", value: x => x.Properties.MaxSpeed },
      { name: "MaxSI", value: x => x.Properties.MaxStructuralIntegrity },
      { name: "Stab", value: x => x.Properties.Defense.Stab },
      { name: "Cut", value: x => x.Properties.Defense.Cut },
      { name: "Impact", value: x => x.Properties.Defense.Impact },
      { name: "Penetration", value: x => x.Properties.Defense.Penetration },
      { name: "Shrapnel", value: x => x.Properties.Defense.Shrapnel },
      { name: "Burn", value: x => x.Properties.Defense.Burn },
      { name: "Cold", value: x => x.Properties.Defense.Cold },
      { name: "Acid", value: x => x.Properties.Defense.Acid },
      { name: "Electric", value: x => x.Properties.Defense.Electric },
      { name: "Durability", value: x => x.Properties.Economy.Durability },
    ],
    offset: 7000000,
    table: "Vehicles",
    relationChangeFunc: async (client, id, x) => await applyAttachmentSlotChanges(client, id - 7000000, x.AttachmentSlots)
  },
  Furniture: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Type", value: x => x.Properties.Type },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
    ],
    offset: 9100000,
    table: "Furniture"
  },
  Decoration: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
    ],
    offset: 9200000,
    table: "Decorations"
  },
  StorageContainer: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Capacity", value: x => x.Properties.ItemCapacity },
      { name: "MaxWeight", value: x => x.Properties.WeightCapacity },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
    ],
    offset: 9300000,
    table: "StorageContainers"
  },
  Strongbox: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
    ],
    offset: 12000000,
    table: "Strongboxes",
    relationChangeFunc: async (client, id, x) => await applyStrongboxLootsChanges(client, id - 12000000, x.Loots)
  },
  Sign: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "ItemPoints", value: x => x.Properties.ItemPoints },
      { name: "AspectRatio", value: x => x.Properties.Display.AspectRatio },
      { name: "LocalContentScreen", value: x => x.Properties.Display.CanShowLocalContentScreen ? 1 : 0 },
      { name: "ImagesAndText", value: x => x.Properties.Display.CanShowImagesAndText ? 1 : 0 },
      { name: "Effects", value: x => x.Properties.Display.CanShowEffects ? 1 : 0 },
      { name: "Multimedia", value: x => x.Properties.Display.CanShowMultimedia ? 1 : 0 },
      { name: "ParticipantContent", value: x => x.Properties.Display.CanShowParticipantContent ? 1 : 0 },
      { name: "Cost", value: x => x.Properties.Economy.Cost },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
    ],
    offset: 9400000,
    table: "Signs"
  },
  Clothing: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Type", value: x => x.Properties.Type },
      { name: "Gender", value: x => x.Properties.Gender },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT }
    ],
    offset: 8000000,
    table: "Clothes",
    relationChangeFunc: async (client, id, x) => {
      const clothingIdOffset = 8000000;
      const equipSetOffset = 100000;

      let [oldSetId, oldSetName] = await client.query(`SELECT "Id", "Name" FROM ONLY "EquipSets" INNER JOIN ONLY "EquipSetItems" ON "EquipSets"."Id" = "EquipSetItems"."EquipSetId" WHERE "EquipSetItems"."ItemId" = $1`, [id]).then(res => [res.rows[0]?.Id, res.rows[0]?.Name]);

      let newSetId, newSetName;

      if (x.Set && x.Set.Name && x.Set.Name === oldSetName) {
        newSetId = oldSetId;
        newSetName = oldSetName;
      }
      else if (x.Set && x.Set.Name) {
        [newSetId, newSetName] = await client.query(`SELECT "Id", "Name" FROM ONLY "EquipSets" WHERE "Name" = $1`, [x.Set.Name]).then(res => [res.rows[0]?.Id, res.rows[0]?.Name]);
        
        if (!newSetId) {
          newSetId = await client.query(`INSERT INTO "EquipSets" ("Name") VALUES ($1) RETURNING "Id"`, [x.Set.Name]).then(res => res.rows[0].Id);
          newSetName = x.Set.Name;
        }
      }

      let oldSetPieces = oldSetId
        ? await client.query(`SELECT "ItemId" FROM ONLY "EquipSetItems" WHERE "EquipSetId" = $1`, [oldSetId]).then(res => res.rows.map(x => x.ItemId - clothingIdOffset))
        : [];

      if (oldSetId && newSetName !== oldSetName) {
        // Delete this item from the old set if they are different
        await client.query(`DELETE FROM ONLY "EquipSetItems" WHERE "EquipSetId" = $1 AND "ItemId" = $2`, [oldSetId, id]);

        oldSetPieces = oldSetPieces.filter(x => x !== id);
      }
      
      if (newSetId) {
        // Add/Update this item to the new set
        await client.query(`INSERT INTO "EquipSetItems" ("EquipSetId", "ItemId") VALUES ($1, $2) ON CONFLICT ("EquipSetId", "ItemId") DO NOTHING`, [newSetId, id]);
      }

      if (oldSetId && oldSetPieces.length === 0) {
        // Remove all set effects if the old set has no more pieces
        await applyEffectsOnSetEquipChanges(client, oldSetId + equipSetOffset, []);

        // Delete the old set if it has no more pieces
        await client.query(`DELETE FROM ONLY "EquipSets" WHERE "Id" = $1`, [oldSetId]);
      }

      await Promise.all([
        applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip),
        newSetId ? await applyEffectsOnSetEquipChanges(client, newSetId + equipSetOffset, x.Set.EffectsOnSetEquip) : Promise.resolve(null)
      ])
    }
  },
  Vendor: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "PlanetId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [x.Planet.Name]).then(res => res.rows[0]?.Id) },
      { name: "Longitude", value: x => x.Properties.Coordinates.Longitude },
      { name: "Latitude", value: x => x.Properties.Coordinates.Latitude },
      { name: "Altitude", value: x => x.Properties.Coordinates.Altitude }
    ],
    table: "Vendors",
    relationChangeFunc: async (client, id, x) => await applyVendorOfferChanges(client, id, x.Offers)
  },
  Mob: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "SpeciesId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "MobSpecies" WHERE "Name" = $1`, [x.Species.Name]).then(res => res.rows[0]?.Id) },
      { name: "PlanetId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [x.Planet.Name]).then(res => res.rows[0]?.Id) },
      { name: "AttackRange", value: x => x.Properties.AttackRange },
      { name: "AggressionRange", value: x => x.Properties.Aggression },
      { name: "Sweatable", value: x => x.Properties.IsSweatable ? 1 : 0 },
      { name: "DefensiveProfessionId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.DefensiveProfession.Name]).then(res => res.rows[0]?.Id) },
      { name: "ScanningProfessionId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.ScanningProfession.Name]).then(res => res.rows[0]?.Id) },
    ],
    table: "Mobs",
    relationChangeFunc: async (client, id, x) => {
      await applyMobMaturityChanges(client, id, x.Maturities);
      await applyMobLootChanges(client, id, x.Loots);
      if (x.Spawns) {
        await applyMobSpawnChanges(client, id, x.Spawns);
      }
    }
  }
}

async function applyEstateSectionsChanges(client, estateId, sections) {
  // Map section names and max points
  const newSectionNames = sections.map(s => s.Name);

  // Remove sections not present anymore
  await client.query(`DELETE FROM ONLY "EstateSections" WHERE "EstateId" = $1 AND "Name" NOT IN (SELECT * FROM unnest($2::text[]))`, [estateId, newSectionNames.length ? newSectionNames : ['']]);

  // Upsert sections with ItemPoints using a single statement
  await Promise.all(sections.map(s => client.query(`
    INSERT INTO "EstateSections" ("EstateId", "Name", "Description", "ItemPoints")
    VALUES ($1, $2, $3, $4)
    ON CONFLICT ("EstateId", "Name") DO UPDATE SET
      "Description" = EXCLUDED."Description",
      "ItemPoints" = EXCLUDED."ItemPoints"
  `, [estateId, s.Name, null, s.MaxItemPoints ?? null])));
}

async function applyMobMaturityChanges(client, mobId, maturities) {
  maturities = await Promise.all([
    client.query(`DELETE FROM ONLY "MobMaturities" WHERE "MobId" = $1 AND "Name" NOT IN (SELECT * FROM unnest($2::text[]))`, [mobId, maturities.map(x => x.Name)]),
    ...maturities.map(maturity => client.query(`
      INSERT INTO "MobMaturities"
      ("MobId", "Name", "Health", "RegenerationInterval", "RegenerationAmount", "AttackSpeed", "DangerLevel", "TamingLevel", "Strength", "Agility", "Intelligence", "Psyche", "Stamina", "MissChance", "ResistanceStab", "ResistanceCut", "ResistanceImpact", "ResistancePenetration", "ResistanceShrapnel", "ResistanceBurn", "ResistanceCold", "ResistanceAcid", "ResistanceElectric")
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23)
      ON CONFLICT ("MobId", "Name") DO UPDATE SET
      "Health" = $3, "RegenerationInterval" = $4, "RegenerationAmount" = $5, "AttackSpeed" = $6, "DangerLevel" = $7, "TamingLevel" = $8, "Strength" = $9, "Agility" = $10, "Intelligence" = $11, "Psyche" = $12, "Stamina" = $13, "MissChance" = $14, "ResistanceStab" = $15, "ResistanceCut" = $16, "ResistanceImpact" = $17, "ResistancePenetration" = $18, "ResistanceShrapnel" = $19, "ResistanceBurn" = $20, "ResistanceCold" = $21, "ResistanceAcid" = $22, "ResistanceElectric" = $23
      RETURNING "Id"`,
      [
        mobId,
        maturity.Name,
        maturity.Properties.Health,
        maturity.Properties.RegenerationInterval,
        maturity.Properties.RegenerationAmount,
        maturity.Properties.AttacksPerMinute,
        maturity.Properties.Level,
        maturity.Properties.Taming.TamingLevel,
        maturity.Properties.Attributes.Strength,
        maturity.Properties.Attributes.Agility,
        maturity.Properties.Attributes.Intelligence,
        maturity.Properties.Attributes.Psyche,
        maturity.Properties.Attributes.Stamina,
        maturity.Properties.MissChance,
        maturity.Properties.Defense.Stab,
        maturity.Properties.Defense.Cut,
        maturity.Properties.Defense.Impact,
        maturity.Properties.Defense.Penetration,
        maturity.Properties.Defense.Shrapnel,
        maturity.Properties.Defense.Burn,
        maturity.Properties.Defense.Cold,
        maturity.Properties.Defense.Acid,
        maturity.Properties.Defense.Electric]).then(res => ({ ...maturity, Id: res.rows[0].Id })))
  ]).then(res => res.slice(1));

  await Promise.all(maturities.map(maturity => applyMobAttackChanges(client, maturity.Id, maturity.Attacks)));
}

async function applyMobAttackChanges(client, maturityId, attacks) {
  await Promise.all([
    client.query(`DELETE FROM ONLY "MobAttacks" WHERE "MaturityId" = $1 AND "Name" NOT IN (SELECT * FROM unnest($2::text[]))`, [maturityId, attacks.map(x => x.Name)]),
    ...attacks.map(attack => client.query(`
      INSERT INTO "MobAttacks"
      ("MaturityId", "Name", "Stab", "Cut", "Impact", "Penetration", "Shrapnel", "Burn", "Cold", "Acid", "Electric", "IsAoE", "Damage")
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
      ON CONFLICT ("MaturityId", "Name") DO UPDATE SET
      "Stab" = $3, "Cut" = $4, "Impact" = $5, "Penetration" = $6, "Shrapnel" = $7, "Burn" = $8, "Cold" = $9, "Acid" = $10, "Electric" = $11, "IsAoE" = $12, "Damage" = $13`,
      [maturityId, attack.Name, attack.Damage.Stab, attack.Damage.Cut, attack.Damage.Impact, attack.Damage.Penetration, attack.Damage.Shrapnel, attack.Damage.Burn, attack.Damage.Cold, attack.Damage.Acid, attack.Damage.Electric, attack.IsAoE ? 1 : 0, attack.TotalDamage])
    )
  ]);
}

async function applyMobLootChanges(client, mobId, loots) {
  await Promise.all(loots.map(loot => client.query(`SELECT "Id" FROM ONLY "Items" WHERE "Name" = $1`, [loot.Item.Name]).then(res => loot.Item.Id = res.rows[0]?.Id)));
  await Promise.all(loots.map(loot => client.query(`SELECT "Id" FROM ONLY "MobMaturities" WHERE "Name" = $1`, [loot.Maturity.Name]).then(res => loot.Maturity.Id = res.rows[0]?.Id)));

  await Promise.all([
    client.query(`DELETE FROM ONLY "MobLoots" WHERE "MobId" = $1 AND "ItemId" NOT IN (SELECT * FROM unnest($2::int[]))`, [mobId, loots.map(x => x.ItemId)]),
    ...loots.map(loot => client.query(`
      INSERT INTO "MobLoots" ("MobId", "ItemId", "MaturityId", "Frequency", "IsEvent")
      VALUES ($1, $2, $3, $4, $5)
      ON CONFLICT ("MobId", "ItemId") DO UPDATE SET
      "MaturityId" = $3, "Frequency" = $4, "IsEvent" = $5`,
      [mobId, loot.Item.Id, loot.Maturity.Id ?? null, loot.Frequency, loot.IsEvent ? 1 : 0])
    )
  ]);
}

async function applyVendorOfferChanges(client, vendorId, offers) {
  let newItems = await Promise.all(offers.map(offer => client.query(`SELECT "Id" FROM ONLY "Items" WHERE "Name" = $1`, [offer.Item.Name]).then(res => ({ id: res.rows[0]?.Id, name: offer.Item.Name, limited: offer.IsLimited, prices: offer.Prices }))));

  let newOffers = (await Promise.all([
    // Since the primary key is a composite of VendorId and ItemId, we need to delete all rows that don't match the new items
    client.query(`DELETE FROM ONLY "VendorOffers" WHERE "VendorId" = $1 AND "ItemId" NOT IN (SELECT * FROM unnest($2::int[]))`, [vendorId, newItems.map(x => x.id)]),
    ...newItems.map(item => client.query(`INSERT INTO "VendorOffers" ("VendorId", "ItemId", "IsLimited") VALUES ($1, $2, $3) ON CONFLICT ("VendorId", "ItemId") DO UPDATE SET "IsLimited" = $3 RETURNING "Id"`, [vendorId, item.id, item.limited]).then(res => ({ id: res.rows[0].Id, prices: item.prices })))
  ])).slice(1);

  await Promise.all(newOffers.map(offer => applyVendorOfferPriceChanges(client, offer.id, offer.prices)));
}

async function applyVendorOfferPriceChanges(client, offerId, prices) {
  let newPrices = await Promise.all(prices.map(price => client.query(`SELECT "Id" FROM ONLY "Items" WHERE "Name" = $1`, [price.Item.Name]).then(res => ({ id: res.rows[0]?.Id, name: price.Item.Name, amount: price.Amount }))));

  let newPricesArrayId = newPrices.map(price => price.id);

  await Promise.all([
    // Since the primary key is a composite of OfferId and ItemId, we need to delete all rows that don't match the new prices
    client.query(`DELETE FROM ONLY "VendorOfferPrices" WHERE "OfferId" = $1 AND "ItemId" NOT IN (SELECT * FROM unnest($2::int[]))`, [offerId, newPricesArrayId]),
    ...newPrices.map(price => client.query(`INSERT INTO "VendorOfferPrices" ("OfferId", "ItemId", "Amount") VALUES ($1, $2, $3) ON CONFLICT ("OfferId", "ItemId") DO UPDATE SET "Amount" = $3`, [offerId, price.id, price.amount]))
  ]);
}

async function applyArmorChanges(client, setId, armors) {
  let newArmorNames = armors.map(armor => armor.Name);
  let newArmors = await Promise.all(newArmorNames.map(armorName => client.query(`SELECT "Id" FROM ONLY "Armors" WHERE "Name" = $1`, [armorName]).then(res => ({ id: res.rows.length === 1 ? res.rows[0].Id : null, name: armorName }))));
  let oldArmors = await client.query(`SELECT "Armors"."Id", "Armors"."Name" FROM ONLY "Armors" WHERE "SetId" = $1`, [setId]).then(res => res.rows.map(x => ({ id: x.Id, name: x.Name })));

  let armorsToRemove = oldArmors.filter(armor => !newArmors.some(x => x.name === armor.name));
  let armorsToAdd = newArmors.filter(armor => !oldArmors.some(x => x.name === armor.name));
  let armorsToUpdate = newArmors.filter(armor => oldArmors.some(x => x.name === armor.name));

  let modifiedArmors = await Promise.all([
    ...armorsToRemove.map(armor => client.query(`DELETE FROM ONLY "Armors" WHERE "Id" = $1 AND "SetId" = $2 RETURNING "Id"`, [armor.id, setId]).then(res => ({ id: res.rows[0].Id, name: armor.name, action: 'delete' }))),
    ...armorsToAdd.map(armor => client.query(`
      INSERT INTO "Armors" ("Name", "SetId", "Weight", "MaxTT", "MinTT", "Gender", "Slot") VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING "Id"`,
      [
        armor.name,
        setId,
        ...[armors.find(x => x.Name === armor.name)].flatMap(x => [x.Properties.Weight, x.Properties.Economy.MaxTT, x.Properties.Economy.MinTT, x.Properties.Gender, x.Properties.Slot]),
      ]).then(res => ({ id: res.rows[0].Id, name: armor.name, action: 'insert' }))),
    ...armorsToUpdate.map(armor => client.query(`
      UPDATE ONLY "Armors" SET "Name" = $1, "Weight" = $2, "MaxTT" = $3, "MinTT" = $4, "Gender" = $5, "Slot" = $6 WHERE "Id" = $7 AND "SetId" = $8 RETURNING "Id"`,
      [
        armor.name,
        ...[armors.find(x => x.Name === armor.name)].flatMap(x => [x.Properties.Weight, x.Properties.Economy.MaxTT, x.Properties.Economy.MinTT, x.Properties.Gender, x.Properties.Slot]),
        armor.id,
        setId
      ]).then(res => ({ id: res.rows[0].Id, name: armor.name, action: 'update' })))
  ]);

  if (armorsToRemove.length + armorsToAdd.length + armorsToUpdate.length !== modifiedArmors.length) {
    throw new Error('Failed to update armors.');
  }

  const armorIdOffset = 3000000;

  // Delete effects on equip for removed armors
  if (modifiedArmors.some(x => x.action === 'delete')) {
    await client.query(`DELETE FROM ONLY "EffectsOnEquip" WHERE "ItemId" = ANY($1)`, [modifiedArmors.filter(x => x.action === 'delete').map(x => x.id + armorIdOffset)]);
  }
  
  await Promise.all(armors.map(x => applyEffectsOnEquipChanges(client, modifiedArmors.filter(x => x.action !== 'delete').find(y => x.Name === y.name).id + armorIdOffset, x.EffectsOnEquip)));
}

async function applyBlueprintMaterialsChanges(client, blueprintId, materialEntries) {
  let newMaterials = await Promise.all(materialEntries.map(materialEntry => client.query(`SELECT "Id" FROM ONLY "Materials" WHERE "Name" = $1`, [materialEntry.Item.Name]).then(res => ({ id: res.rows[0].Id, name: materialEntry.Item.Name, amount: materialEntry.Amount }))));

  const materialIdOffset = 1000000;

  let newMaterialArrayId = newMaterials.map(material => material.id + materialIdOffset);

  await Promise.all([
    // Since the primary key is a composite of BlueprintId and MaterialId, we need to delete all rows that don't match the new materials
    client.query(`DELETE FROM ONLY "BlueprintMaterials" WHERE "BlueprintId" = $1 AND "ItemId" NOT IN (SELECT * FROM unnest($2::int[]))`, [blueprintId, newMaterialArrayId]),
    ...newMaterials.map(material => client.query(`INSERT INTO "BlueprintMaterials" ("BlueprintId", "ItemId", "Amount") VALUES ($1, $2, $3) ON CONFLICT ("BlueprintId", "ItemId") DO UPDATE SET "Amount" = $3`, [blueprintId, material.id + materialIdOffset, material.amount]))
  ]);
}

async function applyEffectsOnUseChanges(client, id, effects) {
  let newEffects = await Promise.all(effects.map(effect => client.query(`SELECT "Id" FROM ONLY "Effects" WHERE "Name" = $1`, [effect.Name]).then(res => ({ Id: res.rows[0].Id, ...effect }))));

  let newEffectsArrayId = newEffects.map(effect => effect.Id);

  await Promise.all([
    client.query(`DELETE FROM ONLY "EffectsOnUse" WHERE "ItemId" = $1 AND "EffectId" NOT IN (SELECT * FROM unnest($2::int[]))`, [id, newEffectsArrayId]),
    ...newEffects.map(effect => client.query(`INSERT INTO "EffectsOnUse" ("ItemId", "EffectId", "Strength", "DurationSeconds") VALUES ($1, $2, $3, $4) ON CONFLICT ("ItemId", "EffectId") DO UPDATE SET "Strength" = $3, "DurationSeconds" = $4`, [id, effect.Id, effect.Values.Strength, effect.Values.DurationSeconds]))
  ]);
}

async function applyEffectsOnConsumeChanges(client, id, effects) {
  let newEffects = await Promise.all(effects.map(effect => client.query(`SELECT "Id" FROM ONLY "Effects" WHERE "Name" = $1`, [effect.Name]).then(res => ({ Id: res.rows[0].Id, ...effect }))));

  let newEffectsArrayId = newEffects.map(effect => effect.Id);

  await Promise.all([
    client.query(`DELETE FROM ONLY "EffectsOnConsume" WHERE "ConsumableId" = $1 AND "EffectId" NOT IN (SELECT * FROM unnest($2::int[]))`, [id, newEffectsArrayId]),
    ...newEffects.map(effect => client.query(`INSERT INTO "EffectsOnConsume" ("ConsumableId", "EffectId", "Strength", "DurationSeconds") VALUES ($1, $2, $3, $4) ON CONFLICT ("ConsumableId", "EffectId") DO UPDATE SET "Strength" = $3, "DurationSeconds" = $4`, [id, effect.Id, effect.Values.Strength, effect.Values.DurationSeconds]))
  ]);
}

async function applyEffectsOnEquipChanges(client, id, effects) {
  let newEffects = await Promise.all(effects.map(effect => client.query(`SELECT "Id" FROM ONLY "Effects" WHERE "Name" = $1`, [effect.Name]).then(res => ({ Id: res.rows[0].Id, ...effect }))));

  let newEffectsArrayId = newEffects.map(effect => effect.Id);

  await Promise.all([
    client.query(`DELETE FROM ONLY "EffectsOnEquip" WHERE "ItemId" = $1 AND "EffectId" NOT IN (SELECT * FROM unnest($2::int[]))`, [id, newEffectsArrayId]),
    ...newEffects.map(effect => client.query(`INSERT INTO "EffectsOnEquip" ("ItemId", "EffectId", "Strength") VALUES ($1, $2, $3) ON CONFLICT ("ItemId", "EffectId") DO UPDATE SET "Strength" = $3`, [id, effect.Id, effect.Values.Strength]))
  ]);
}

async function applyEffectsOnSetEquipChanges(client, setId, effects) {
  let newEffects = await Promise.all(effects.map(effect => client.query(`SELECT "Id" FROM ONLY "Effects" WHERE "Name" = $1`, [effect.Name]).then(res => ({ Id: res.rows[0].Id, ...effect }))));

  let newEffectsArrayId = newEffects.map(effect => effect.Id);
  let newEffectsArrayMinSetPieces = newEffects.map(effect => effect.Values.MinSetPieces);

  await Promise.all([
    // Since the primary key is a composite of EffectId and MinSetPieces, we need to delete all rows that don't match the new effects
    client.query(`DELETE FROM ONLY "EffectsOnSetEquip" WHERE "SetId" = $1 AND ("EffectId", "MinSetPieces") NOT IN (SELECT * FROM unnest($2::int[], $3::int[]))`, [setId, newEffectsArrayId, newEffectsArrayMinSetPieces]),
    ...newEffects.map(effect => client.query(`INSERT INTO "EffectsOnSetEquip" ("SetId", "EffectId", "Strength", "MinSetPieces") VALUES ($1, $2, $3, $4) ON CONFLICT ("SetId", "EffectId", "MinSetPieces") DO UPDATE SET "Strength" = $3`, [setId, effect.Id, effect.Values.Strength, effect.Values.MinSetPieces]))
  ]);
}

async function applyPetEffectChanges(client, petId, effects) {
  let newEffects = await Promise.all(effects.map(effect => client.query(`SELECT "Id" FROM ONLY "Effects" WHERE "Name" = $1`, [effect.Name]).then(res => ({ Id: res.rows[0].Id, ...effect }))));

  let newEffectsArrayId = newEffects.map(effect => effect.Id);
  let newEffectsArrayStrength = newEffects.map(effect => effect.Properties.Strength);

  await Promise.all([
    client.query(`DELETE FROM ONLY "PetEffects" WHERE "PetId" = $1 AND ("EffectId", "Strength") NOT IN (SELECT * FROM unnest($2::int[], $3::numeric[]))`, [petId, newEffectsArrayId, newEffectsArrayStrength]),
    ...newEffects.map(effect => client.query(`INSERT INTO "PetEffects"
        ("PetId", "EffectId", "Strength", "Consumption", "UnlockLevel", "UnlockPED", "UnlockEssence", "UnlockRareEssence", "UnlockCriteria", "UnlockCriteriaValue")
        VALUES
        ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
      ON CONFLICT ("PetId", "EffectId", "Strength") DO UPDATE SET
        "Strength" = $3, "Consumption" = $4, "UnlockLevel" = $5, "UnlockPED" = $6, "UnlockEssence" = $7, "UnlockRareEssence" = $8, "UnlockCriteria" = $9, "UnlockCriteriaValue" = $10`,
        [
          petId,
          effect.Id,
          effect.Properties.Strength,
          effect.Properties.NutrioConsumptionPerHour,
          effect.Properties.Unlock.Level,
          effect.Properties.Unlock.CostPED,
          effect.Properties.Unlock.CostEssence,
          effect.Properties.Unlock.CostRareEssence,
          effect.Properties.Unlock.Criteria,
          effect.Properties.Unlock.CriteriaValue
        ]))
  ]);
}

async function applyTierChanges(client, id, tiers, armorSet = false) {
  let newTiers = tiers.map(tier => tier.Properties.Tier);
  let oldTiers = await client.query(`SELECT "Tier" FROM ONLY "Tiers" WHERE "ItemId" = $1`, [id]).then(res => res.rows.map(x => x.Tier));

  let tiersToRemove = oldTiers.filter(tier => !newTiers.includes(tier));

  // TierMaterials are cascaded on delete
  await Promise.all(tiersToRemove.map(tier => client.query(`DELETE FROM ONLY "Tiers" WHERE "ItemId" = $1 AND "Tier" = $2`, [id, tier])));

  let upsertedTiers = await Promise.all(newTiers.map(tier => client.query(`INSERT INTO "Tiers" ("ItemId", "Tier", "IsArmorSet") VALUES ($1, $2, $3) ON CONFLICT ("ItemId", "Tier") DO UPDATE SET "IsArmorSet" = $3 RETURNING "Id"`, [id, tier, armorSet ? 1 : 0])
    .then(res => ({ tier, id: res.rows[0].Id }))));

  await Promise.all(upsertedTiers.flatMap(tier => {
    let materialEntries = tiers.find(x => x.Properties.Tier === tier.tier).Materials;

    return materialEntries.map(materialEntry => client.query(`SELECT "Id" FROM ONLY "Materials" WHERE "Name" = $1`, [materialEntry.Material.Name])
      .then(async (res) => client.query(`INSERT INTO "TierMaterials" ("TierId", "MaterialId", "Amount") VALUES ($1, $2, $3) ON CONFLICT ("TierId", "MaterialId") DO UPDATE SET "Amount" = $3`, [tier.id, res.rows[0].Id, materialEntry.Amount])));
  }));
}

async function applyAttachmentSlotChanges(client, vehicleId, attachmentSlots) {
  let newAttachmentSlots = attachmentSlots.map(slot => slot.Name);
  let oldAttachmentSlots = await client.query(`SELECT "Name" FROM ONLY "VehicleAttachmentSlots" INNER JOIN ONLY "VehicleAttachmentTypes" ON "AttachmentId" = "Id" WHERE "VehicleId" = $1`, [vehicleId]).then(res => res.rows.map(x => x.Name));

  let allAttachmentSlots = Array.from(new Set([...newAttachmentSlots, ...oldAttachmentSlots]));

  let attachmentSlotIds = await Promise.all(allAttachmentSlots.map(slot => client.query(`SELECT "Id" FROM ONLY "VehicleAttachmentTypes" WHERE "Name" = $1`, [slot]).then(res => ({ name: slot, id: res.rows[0]?.Id }))));

  let attachmentSlotsToRemove = oldAttachmentSlots.filter(slot => !newAttachmentSlots.includes(slot));
  let attachmentSlotsToAdd = newAttachmentSlots.filter(slot => !oldAttachmentSlots.includes(slot));

  await Promise.all([
    // Since the primary key is a composite of VehicleId and SlotName, we need to delete all rows that don't match the new attachment slots
    ...attachmentSlotsToAdd.map(slot => client.query(`INSERT INTO "VehicleAttachmentSlots" ("VehicleId", "AttachmentId") VALUES ($1, $2)`, [vehicleId, attachmentSlotIds.find(x => x.name === slot).id])),
    ...attachmentSlotsToRemove.map(slot => client.query(`DELETE FROM ONLY "VehicleAttachmentSlots" WHERE "VehicleId" = $1 AND "AttachmentId" = $2`, [vehicleId, attachmentSlotIds.find(x => x.name === slot).id]))
  ]);
}

async function applyStrongboxLootsChanges(client, strongboxId, loots) {
  let newLoots = await Promise.all(loots.map(loot => client.query(`SELECT "Id" FROM ONLY "Items" WHERE "Name" = $1`, [loot.Item.Name]).then(res => ({ id: res.rows[0].Id, ...loot }))));

  let newLootArrayId = newLoots.map(loot => loot.id);

  await Promise.all([
    // Since the primary key is a composite of StrongboxId and ItemId, we need to delete all rows that don't match the new loots
    client.query(`DELETE FROM ONLY "StrongboxLoots" WHERE "StrongboxId" = $1 AND "ItemId" NOT IN (SELECT * FROM unnest($2::int[]))`, [strongboxId, newLootArrayId]),
    ...newLoots.map(loot => client.query(`INSERT INTO "StrongboxLoots" ("StrongboxId", "ItemId", "Rarity", "AvailableFrom", "AvailableUntil") VALUES ($1, $2, $3, $4, $5) ON CONFLICT ("StrongboxId", "ItemId") DO UPDATE SET "Rarity" = $3, "AvailableFrom" = $4, "AvailableUntil" = $5`, [strongboxId, loot.id, loot.Rarity, loot.AvailableFrom, loot.AvailableUntil]))
  ]);
}

async function applyMobSpawnChanges(client, mobId, spawns) {
  // Get planet ID for this mob
  const planetResult = await client.query(`SELECT "PlanetId" FROM "Mobs" WHERE "Id" = $1`, [mobId]);
  const planetId = planetResult.rows[0]?.PlanetId;

  // Get existing spawns and areas for this mob
  const existingSpawns = await client.query(`
    SELECT DISTINCT "MobSpawns"."Id" AS "SpawnId", "MobSpawns"."AreaId", "Areas"."Shape", "Areas"."Data", "Areas"."Altitude"
    FROM "MobSpawns" 
    INNER JOIN "Areas" ON "MobSpawns"."AreaId" = "Areas"."Id"
    INNER JOIN "MobSpawnMaturities" ON "MobSpawns"."Id" = "MobSpawnMaturities"."SpawnId"
    INNER JOIN "MobMaturities" ON "MobSpawnMaturities"."MaturityId" = "MobMaturities"."Id"
    WHERE "MobMaturities"."MobId" = $1
  `, [mobId]);

  // Process spawns and match with existing areas
  const processedSpawns = await Promise.all(spawns.map(async (spawn, index) => {
    try {
      if (!spawn.Properties.Shape || !spawn.Properties.Data) {
        console.warn(`Skipping spawn ${index}: missing Shape or Data`, spawn.Properties);
        return null;
      }

      const shape = spawn.Properties.Shape == 'Point' ? 'Circle' : spawn.Properties.Shape;
      const data = typeof spawn.Properties.Data === 'string' ? spawn.Properties.Data : JSON.stringify(spawn.Properties.Data);
      const altitude = spawn.Properties.Coordinates?.Altitude || 0;

      // Check if there's an existing area with matching Shape, Data, and Altitude
      const matchingArea = existingSpawns.rows.find(existing => 
        existing.Shape === shape && 
        existing.Data === data && 
        Number(existing.Altitude) === altitude
      );

      let areaId, spawnId;

      if (matchingArea) {
        // Use existing area and spawn
        areaId = matchingArea.AreaId;
        spawnId = matchingArea.SpawnId;
        
        // Update the spawn properties that might have changed
        await client.query(`
          UPDATE "MobSpawns" 
          SET "Density" = $1, "IsShared" = $2, "IsEvent" = $3, "Name" = $4, "Description" = $5 
          WHERE "Id" = $6
        `, [
          spawn.Properties.Density || 2,
          spawn.Properties.IsShared ? 1 : 0,
          spawn.Properties.IsEvent ? 1 : 0,
          spawn.Properties.Name || null,
          spawn.Properties.Description || null,
          spawnId
        ]);
      } else {
        // Generate area name based on mobs and maturities
        let areaName = spawn.Properties.Name;
        if (!areaName && spawn.Maturities && spawn.Maturities.length > 0) {
          // Group maturities by mob
          const mobGroups = {};
          spawn.Maturities.forEach(maturity => {
            const mobName = maturity.Maturity?.Mob?.Name;
            if (mobName) {
              if (!mobGroups[mobName]) {
                mobGroups[mobName] = [];
              }
              if (maturity.Maturity?.Name) {
                mobGroups[mobName].push(maturity.Maturity.Name);
              }
            }
          });

          // Create name: "Mob1 - Maturity1/Maturity2, Mob2 - Maturity3"
          const mobParts = Object.entries(mobGroups).map(([mobName, maturities]) => {
            if (maturities.length > 0) {
              return `${mobName} - ${maturities.join('/')}`;
            }
            return mobName;
          });
          
          areaName = mobParts.join(', ') || `Spawn Area ${index + 1}`;
        }
        
        if (!areaName) {
          areaName = `Spawn Area ${index + 1}`;
        }

        // Create new Area
        const areaResult = await client.query(`
          INSERT INTO "Areas" ("Name", "Type", "Shape", "Data", "Altitude", "PlanetId") 
          VALUES ($1, $2, $3, $4, $5, $6)
          RETURNING "Id"
        `, [
          areaName,
          'MobArea',
          shape,
          data,
          altitude,
          planetId
        ]);

        areaId = areaResult.rows[0].Id;

        // Create new MobSpawn
        const spawnResult = await client.query(`
          INSERT INTO "MobSpawns" ("AreaId", "Density", "IsShared", "IsEvent", "Name", "Description") 
          VALUES ($1, $2, $3, $4, $5, $6)
          RETURNING "Id"
        `, [
          areaId,
          spawn.Properties.Density || 2,
          spawn.Properties.IsShared ? 1 : 0,
          spawn.Properties.IsEvent ? 1 : 0,
          spawn.Properties.Name || null,
          spawn.Properties.Description || null
        ]);

        spawnId = spawnResult.rows[0].Id;
      }

      return { ...spawn, Id: spawnId, AreaId: areaId };
    } catch (error) {
      console.error(`Error processing spawn ${index}:`, error, spawn);
      return null;
    }
  }));

  const validSpawns = processedSpawns.filter(s => s !== null);

  // Delete spawns and areas that are no longer in the new data
  const usedAreaIds = validSpawns.map(s => s.AreaId);
  const areasToDelete = existingSpawns.rows.filter(existing => 
    !usedAreaIds.includes(existing.AreaId)
  );

  for (const areaToDelete of areasToDelete) {
    // Only delete areas - cascading will handle MobSpawns and MobSpawnMaturities
    await client.query(`DELETE FROM "Areas" WHERE "Id" = $1`, [areaToDelete.AreaId]);
  }

  // Handle spawn maturities for each spawn
  await Promise.all(validSpawns.map(async (spawn) => {
    if (!spawn.Maturities || spawn.Maturities.length === 0) return;

    // Get maturity IDs
    const maturitiesWithIds = await Promise.all(spawn.Maturities.map(async (maturity) => {
      if (!maturity.Maturity?.Mob?.Name || !maturity.Maturity?.Name) {
        console.warn('Skipping maturity with missing data:', maturity);
        return null;
      }
      
      const result = await client.query(`
        SELECT "MobMaturities"."Id" 
        FROM "MobMaturities" 
        INNER JOIN "Mobs" ON "MobMaturities"."MobId" = "Mobs"."Id"
        WHERE "Mobs"."Name" = $1 AND "MobMaturities"."Name" = $2
      `, [maturity.Maturity.Mob.Name, maturity.Maturity.Name]);

      return result.rows[0] ? { ...maturity, MaturityId: result.rows[0].Id } : null;
    }));

    const validMaturities = maturitiesWithIds.filter(m => m !== null);

    // Delete old maturities and insert new ones
    await Promise.all([
      client.query(`DELETE FROM "MobSpawnMaturities" WHERE "SpawnId" = $1 AND "MaturityId" NOT IN (SELECT * FROM unnest($2::int[]))`, 
        [spawn.Id, validMaturities.map(m => m.MaturityId)]),
      ...validMaturities.map(maturity => 
        client.query(`
          INSERT INTO "MobSpawnMaturities" ("SpawnId", "MaturityId", "IsRare")
          VALUES ($1, $2, $3)
          ON CONFLICT ("SpawnId", "MaturityId") DO UPDATE SET "IsRare" = $3
        `, [spawn.Id, maturity.MaturityId, maturity.IsRare ? 1 : 0])
      )
    ]);
  }));
}

// OLD VERSION OF applyMobSpawnChanges (kept as backup in case of issues):
// async function applyMobSpawnChanges(client, mobId, spawns) {
//   // Get planet ID for this mob
//   const planetResult = await client.query(`SELECT "PlanetId" FROM "Mobs" WHERE "Id" = $1`, [mobId]);
//   const planetId = planetResult.rows[0]?.PlanetId;
// 
//   // First, clean up ALL existing spawns and areas for this mob
//   const existingSpawns = await client.query(`
//     SELECT DISTINCT "MobSpawns"."Id", "AreaId"
//     FROM "MobSpawns" 
//     INNER JOIN "MobSpawnMaturities" ON "MobSpawns"."Id" = "MobSpawnMaturities"."SpawnId"
//     INNER JOIN "MobMaturities" ON "MobSpawnMaturities"."MaturityId" = "MobMaturities"."Id"
//     WHERE "MobMaturities"."MobId" = $1
//   `, [mobId]);
// 
//   for (const spawn of existingSpawns.rows) {
//     await client.query(`DELETE FROM "MobSpawnMaturities" WHERE "SpawnId" = $1`, [spawn.Id]);
//     await client.query(`DELETE FROM "MobSpawns" WHERE "Id" = $1`, [spawn.Id]);
//     await client.query(`DELETE FROM "Areas" WHERE "Id" = $1`, [spawn.AreaId]);
//   }
// 
//   // Process spawns with area creation and get spawn IDs
//   const processedSpawns = await Promise.all(spawns.map(async (spawn, index) => {
//     try {
//       if (!spawn.Properties.Shape || !spawn.Properties.Data) {
//         console.warn(`Skipping spawn ${index}: missing Shape or Data`, spawn.Properties);
//         return null;
//       }
// 
//       // Generate area name based on mobs and maturities
//     let areaName = spawn.Properties.Name;
//     if (!areaName && spawn.Maturities && spawn.Maturities.length > 0) {
//       // Group maturities by mob
//       const mobGroups = {};
//       spawn.Maturities.forEach(maturity => {
//         const mobName = maturity.Maturity?.Mob?.Name;
//         if (mobName) {
//           if (!mobGroups[mobName]) {
//             mobGroups[mobName] = [];
//           }
//           if (maturity.Maturity?.Name) {
//             mobGroups[mobName].push(maturity.Maturity.Name);
//           }
//         }
//       });
// 
//       // Create name: "Mob1 - Maturity1/Maturity2, Mob2 - Maturity3"
//       const mobParts = Object.entries(mobGroups).map(([mobName, maturities]) => {
//         if (maturities.length > 0) {
//           return `${mobName} - ${maturities.join('/')}`;
//         }
//         return mobName;
//       });
//       
//       areaName = mobParts.join(', ') || `Spawn Area ${index + 1}`;
//     }
//     
//     if (!areaName) {
//       areaName = `Spawn Area ${index + 1}`;
//     }
// 
//     // Create Area
//     const areaResult = await client.query(`
//       INSERT INTO "Areas" ("Name", "Type", "Shape", "Data", "Altitude", "PlanetId") 
//       VALUES ($1, $2, $3, $4, $5, $6)
//       RETURNING "Id"
//     `, [
//       areaName,
//       'MobArea',
//       spawn.Properties.Shape == 'Point' ? 'Circle' : spawn.Properties.Shape,
//       typeof spawn.Properties.Data === 'string' ? spawn.Properties.Data : JSON.stringify(spawn.Properties.Data),
//       spawn.Properties.Coordinates?.Altitude || 0,
//       planetId
//     ]);
// 
//     // Create MobSpawn
//     const spawnResult = await client.query(`
//       INSERT INTO "MobSpawns" ("AreaId", "Density", "IsShared", "IsEvent", "Name", "Description") 
//       VALUES ($1, $2, $3, $4, $5, $6)
//       RETURNING "Id"
//     `, [
//       areaResult.rows[0].Id,
//       spawn.Properties.Density || 2,
//       spawn.Properties.IsShared ? 1 : 0,
//       spawn.Properties.IsEvent ? 1 : 0,
//       spawn.Properties.Name || null,
//       spawn.Properties.Description || null
//     ]);
// 
//     return { ...spawn, Id: spawnResult.rows[0].Id };
//     } catch (error) {
//       console.error(`Error processing spawn ${index}:`, error, spawn);
//       return null;
//     }
//   }));
// 
//   const validSpawns = processedSpawns.filter(s => s !== null);
// 
//   // Handle spawn maturities for each spawn
//   await Promise.all(validSpawns.map(async (spawn) => {
//     if (!spawn.Maturities || spawn.Maturities.length === 0) return;
// 
//     // Get maturity IDs
//     const maturitiesWithIds = await Promise.all(spawn.Maturities.map(async (maturity) => {
//       if (!maturity.Maturity?.Mob?.Name || !maturity.Maturity?.Name) {
//         console.warn('Skipping maturity with missing data:', maturity);
//         return null;
//       }
//       
//       const result = await client.query(`
//         SELECT "MobMaturities"."Id" 
//         FROM "MobMaturities" 
//         INNER JOIN "Mobs" ON "MobMaturities"."MobId" = "Mobs"."Id"
//         WHERE "Mobs"."Name" = $1 AND "MobMaturities"."Name" = $2
//       `, [maturity.Maturity.Mob.Name, maturity.Maturity.Name]);
// 
//       return result.rows[0] ? { ...maturity, MaturityId: result.rows[0].Id } : null;
//     }));
// 
//     const validMaturities = maturitiesWithIds.filter(m => m !== null);
// 
//     // Delete old maturities and insert new ones
//     await Promise.all([
//       client.query(`DELETE FROM "MobSpawnMaturities" WHERE "SpawnId" = $1 AND "MaturityId" NOT IN (SELECT * FROM unnest($2::int[]))`, 
//         [spawn.Id, validMaturities.map(m => m.MaturityId)]),
//       ...validMaturities.map(maturity => 
//         client.query(`
//           INSERT INTO "MobSpawnMaturities" ("SpawnId", "MaturityId", "IsRare")
//           VALUES ($1, $2, $3)
//           ON CONFLICT ("SpawnId", "MaturityId") DO UPDATE SET "IsRare" = $3
//         `, [spawn.Id, maturity.MaturityId, maturity.IsRare ? 1 : 0])
//       )
//     ]);
//   }));
// }

async function applyRefiningRecipesChanges(client, materialId, recipes) {
  // Get recipe IDs with amounts for this material
  const newRecipes = recipes.map((recipe, index) => ({
    id: null, // Will be set after insert/update
    amount: recipe.Amount,
    ingredients: recipe.Ingredients,
    index: index
  }));

  // Delete all existing recipes for this material (by ProductId)
  await client.query(`DELETE FROM "RefiningRecipes" WHERE "ProductId" = $1`, [materialId + 1000000]);

  // Insert new recipes and get their IDs
  const insertedRecipes = await Promise.all(newRecipes.map(async (recipe) => {
    const result = await client.query(`
      INSERT INTO "RefiningRecipes" ("ProductId", "Amount") 
      VALUES ($1, $2) 
      RETURNING "Id"
    `, [materialId + 1000000, recipe.amount]);
    
    return {
      ...recipe,
      id: result.rows[0].Id
    };
  }));

  // Insert ingredients for each recipe
  await Promise.all(insertedRecipes.map(async (recipe) => {
    await Promise.all(recipe.ingredients.map(async (ingredient) => {
      // Resolve item name to ID
      const itemResult = await client.query(`
        SELECT "Id" FROM "Items" WHERE "Name" = $1
      `, [ingredient.Item.Name]);
      
      if (itemResult.rows.length === 0) {
        throw new Error(`Item not found: ${ingredient.Item.Name}`);
      }
      
      const itemId = itemResult.rows[0].Id;
      
      await client.query(`
        INSERT INTO "RefiningIngredients" ("RecipeId", "ItemId", "Amount") 
        VALUES ($1, $2, $3)
      `, [recipe.id, itemId, ingredient.Amount]);
    }));
  }));
}
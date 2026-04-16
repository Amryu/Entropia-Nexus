import { poolUsers } from '../db.js';

export const UpsertConfigs = {
  Shop: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Description },
      { name: "Type", value: _ => 'Estate' },
      { name: "Longitude", value: x => x.Coordinates?.Longitude ?? null },
      { name: "Latitude", value: x => x.Coordinates?.Latitude ?? null },
      { name: "Altitude", value: x => x.Coordinates?.Altitude ?? null },
      { name: "PlanetId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [x.Planet?.Name]).then(res => res.rows[0]?.Id ?? null) }
    ],
    table: "Locations",
    relationChangeFunc: async (client, locationId, x) => {
      await applyLocationExtensionChanges(client, locationId, {
        Properties: { Type: 'Estate', EstateType: 'Shop', OwnerId: x.OwnerId, ItemTradeAvailable: true, MaxGuests: x.MaxGuests },
        Owner: x.Owner,
        Sections: x.Sections ?? []
      });
    }
  },
  Apartment: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties?.Description ?? x.Description ?? null },
      { name: "Type", value: _ => 'Estate' },
      { name: "Longitude", value: x => x.Properties?.Coordinates?.Longitude ?? x.Coordinates?.Longitude ?? null },
      { name: "Latitude", value: x => x.Properties?.Coordinates?.Latitude ?? x.Coordinates?.Latitude ?? null },
      { name: "Altitude", value: x => x.Properties?.Coordinates?.Altitude ?? x.Coordinates?.Altitude ?? null },
      { name: "PlanetId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [x.Planet?.Name]).then(res => res.rows[0]?.Id ?? null) }
    ],
    table: "Locations",
    relationChangeFunc: async (client, locationId, x) => {
      await applyLocationExtensionChanges(client, locationId, {
        Properties: { Type: 'Estate', EstateType: 'Apartment', MaxGuests: x.MaxGuests },
        Sections: x.Sections ?? []
      });
    }
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
      applyTierChanges(client, id, x.Tiers),
      applyItemProperties(client, id, x)
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
    relationChangeFunc: async (client, id, x) => {
      await Promise.all([
        applyEffectsOnSetEquipChanges(client, id, x.EffectsOnSetEquip),
        applyArmorChanges(client, id, x.Armors.flat()),
        applyTierChanges(client, id, x.Tiers, true),
        applyItemProperties(client, id + 13000000, x)
      ]);
      // Propagate IsUntradeable/IsRare to each armor piece in the set
      const armorOffset = 3000000;
      const pieces = await client.query(
        `SELECT "Id", "Name" FROM ONLY "Armors" WHERE "SetId" = $1`, [id]
      );
      const flatArmors = x.Armors.flat();
      await Promise.all(pieces.rows.map(r => {
        const pieceData = flatArmors.find(a => a.Name === r.Name);
        return applyItemProperties(client, r.Id + armorOffset, pieceData || x);
      }));
    }
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
      applyTierChanges(client, id, x.Tiers),
      applyItemProperties(client, id, x)
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
      applyEffectsOnUseChanges(client, id, x.EffectsOnUse),
      applyItemProperties(client, id, x)
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
    offset: 4300000,
    table: "Refiners",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
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
    offset: 4400000,
    table: "Scanners",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
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
      applyTierChanges(client, id, x.Tiers),
      applyItemProperties(client, id, x)
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
      applyTierChanges(client, id, x.Tiers),
      applyItemProperties(client, id, x)
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
    table: "TeleportationChips",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
  },
  get TeleportChip() { return this.TeleportationChip; },
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
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnUseChanges(client, id, x.EffectsOnUse),
      applyItemProperties(client, id, x)
    ])
  },
  MiscTool: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Type", value: x => x.Properties.Type },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
      { name: "MinTT", value: x => x.Properties.Economy.MinTT },
      { name: "Decay", value: x => x.Properties.Economy.Decay },
      { name: "ProfessionId", value: async (x, c) => {
        if (!x.Profession?.Name) return null;
        return c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.Profession.Name]).then(res => res.rows[0]?.Id);
      }},
      { name: "IsSib", value: x => x.Properties.Skill?.IsSiB ? 1 : 0 },
      { name: "MinLevel", value: x => x.Properties.Skill?.LearningIntervalStart ?? null },
      { name: "MaxLevel", value: x => x.Properties.Skill?.LearningIntervalEnd ?? null }
    ],
    offset: 4200000,
    table: "MiscTools",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
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
      { name: "Absorption", value: x => x.Properties.Economy.Absorption },
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
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip),
      applyItemProperties(client, id, x)
    ])
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
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip),
      applyItemProperties(client, id, x)
    ])
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
      { name: "Decay", value: x => x.Properties.Economy.Decay },
    ],
    offset: 5300000,
    table: "Absorbers",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
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
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip),
      applyItemProperties(client, id, x)
    ])
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
    table: "ArmorPlatings",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip),
      applyItemProperties(client, id, x)
    ])
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
    table: "MindforceImplants",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnEquipChanges(client, id, x.EffectsOnEquip),
      applyItemProperties(client, id, x)
    ])
  },
  FishingRod: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "RodType", value: x => x.Properties.RodType },
      { name: "Strength", value: x => x.Properties.Strength ?? null },
      { name: "Flexibility", value: x => x.Properties.Flexibility ?? null },
      { name: "MaxTT", value: x => x.Properties.Economy?.MaxTT ?? null },
      { name: "MinTT", value: x => x.Properties.Economy?.MinTT ?? null },
      { name: "Decay", value: x => x.Properties.Economy?.Decay ?? null },
      { name: "ProfessionId", value: async (x, c) => {
        if (!x.Profession?.Name) return null;
        return c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.Profession.Name]).then(res => res.rows[0]?.Id ?? null);
      }},
      { name: "IsSib", value: x => x.Properties.Skill?.IsSiB ? 1 : 0 },
      { name: "MinLevel", value: x => x.Properties.Skill?.LearningIntervalStart ?? null },
      { name: "MaxLevel", value: x => x.Properties.Skill?.LearningIntervalEnd ?? null }
    ],
    offset: 4900000,
    table: "FishingRods",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
  },
  FishingReel: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Strength", value: x => x.Properties.Strength ?? null },
      { name: "Speed", value: x => x.Properties.Speed ?? null },
      { name: "MaxTT", value: x => x.Properties.Economy?.MaxTT ?? null },
      { name: "MinTT", value: x => x.Properties.Economy?.MinTT ?? null },
      { name: "Decay", value: x => x.Properties.Economy?.Decay ?? null }
    ],
    offset: 5800000,
    table: "FishingReels",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
  },
  FishingBlank: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Strength", value: x => x.Properties.Strength ?? null },
      { name: "Flexibility", value: x => x.Properties.Flexibility ?? null },
      { name: "MaxTT", value: x => x.Properties.Economy?.MaxTT ?? null },
      { name: "MinTT", value: x => x.Properties.Economy?.MinTT ?? null },
      { name: "Decay", value: x => x.Properties.Economy?.Decay ?? null }
    ],
    offset: 5810000,
    table: "FishingBlanks",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
  },
  FishingLine: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Flexibility", value: x => x.Properties.Flexibility ?? null },
      { name: "Strength", value: x => x.Properties.Strength ?? null },
      { name: "Length", value: x => x.Properties.Length ?? null },
      { name: "MaxTT", value: x => x.Properties.Economy?.MaxTT ?? null },
      { name: "MinTT", value: x => x.Properties.Economy?.MinTT ?? null },
      { name: "Decay", value: x => x.Properties.Economy?.Decay ?? null }
    ],
    offset: 5820000,
    table: "FishingLines",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
  },
  FishingLure: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Depth", value: x => x.Properties.Depth ?? null },
      { name: "Quality", value: x => x.Properties.Quality ?? null },
      { name: "MaxTT", value: x => x.Properties.Economy?.MaxTT ?? null },
      { name: "MinTT", value: x => x.Properties.Economy?.MinTT ?? null },
      { name: "Decay", value: x => x.Properties.Economy?.Decay ?? null }
    ],
    offset: 5830000,
    table: "FishingLures",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
  },
  Blueprint: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Type", value: x => x.Properties.Type },
      { name: "Level", value: x => x.Properties.Level },
      { name: "ItemId", value: async (x, c) => {
        const res = await c.query(`SELECT "Id" FROM ONLY "Items" WHERE "Name" = $1`, [x.Product.Name]);
        if (!res.rows[0]) throw new Error(`Blueprint product not found: "${x.Product.Name}"`);
        return res.rows[0].Id;
      } },
      { name: "ProfessionId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.Profession.Name]).then(res => res.rows[0]?.Id) },
      { name: "BookId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "BlueprintBooks" WHERE "Name" = $1`, [x.Book.Name]).then(res => res.rows[0]?.Id) },
      { name: "MinLvl", value: x => x.Properties.Skill.LearningIntervalStart },
      { name: "MaxLvl", value: x => x.Properties.Skill.LearningIntervalEnd },
      { name: "IsSib", value: x => x.Properties.Skill.IsSiB ? 1 : 0 },
      { name: "IsBoosted", value: x => x.Properties.Skill.IsBoosted ? 1 : 0 },
      { name: "MinimumCraftAmount", value: x => x.Properties.MinimumCraftAmount },
      { name: "MaximumCraftAmount", value: x => x.Properties.MaximumCraftAmount },
      { name: "IsDroppable", value: x => x.Properties.IsDroppable ? true : false },
      { name: "DropRarity", value: x => x.Properties.DropRarity || null },
    ],
    offset: 6000000,
    table: "Blueprints",
    relationChangeFunc: async (client, id, x) => {
      const bpId = id - 6000000;
      await Promise.all([
        applyBlueprintMaterialsChanges(client, bpId, x.Materials),
        applyItemProperties(client, id, x)
      ]);
    }
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
      await Promise.all([
        x.RefiningRecipes ? applyRefiningRecipesChanges(client, id - 1000000, x.RefiningRecipes) : null,
        applyItemProperties(client, id, x)
      ]);
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
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyPetEffectChanges(client, id - 11000000, x.Effects),
      applyItemProperties(client, id, x)
    ])
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
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyEffectsOnConsumeChanges(client, id - 10000000, x.EffectsOnConsume),
      applyItemProperties(client, id, x)
    ])
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
    table: "CreatureControlCapsules",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
  },
  get CreatureControlCapsule() { return this.Capsule; },
  Vehicle: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
  { name: "Type", value: x => x.Properties.Type },
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
      { name: "Decay", value: x => x.Properties.Economy.Decay },
    ],
    offset: 7000000,
    table: "Vehicles",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyAttachmentSlotChanges(client, id - 7000000, x.AttachmentSlots),
      applyItemProperties(client, id, x)
    ])
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
    table: "Furniture",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
  },
  Decoration: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "MaxTT", value: x => x.Properties.Economy.MaxTT },
    ],
    offset: 9200000,
    table: "Decorations",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
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
    table: "StorageContainers",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
  },
  Strongbox: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
    ],
    offset: 12000000,
    table: "Strongboxes",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyStrongboxLootsChanges(client, id - 12000000, x.Loots),
      applyItemProperties(client, id, x)
    ])
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
    table: "Signs",
    relationChangeFunc: async (client, id, x) => await applyItemProperties(client, id, x)
  },
  Clothing: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "Weight", value: x => x.Properties.Weight },
      { name: "Type", value: x => x.Properties.Type },
      { name: "Slot", value: x => x.Properties.Slot },
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
        newSetId ? await applyEffectsOnSetEquipChanges(client, newSetId + equipSetOffset, x.Set.EffectsOnSetEquip) : Promise.resolve(null),
        applyItemProperties(client, id, x)
      ])
    }
  },
  Vendor: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Type", value: () => 'Vendor' },
      { name: "Description", value: x => x.Properties?.Description ?? null },
      { name: "PlanetId", value: async (x, c) => x.Planet?.Name ? await c.query(`SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [x.Planet.Name]).then(res => res.rows[0]?.Id ?? null) : null },
      { name: "Longitude", value: x => x.Properties?.Coordinates?.Longitude ?? null },
      { name: "Latitude", value: x => x.Properties?.Coordinates?.Latitude ?? null },
      { name: "Altitude", value: x => x.Properties?.Coordinates?.Altitude ?? null }
    ],
    table: "Locations",
    relationChangeFunc: async (client, id, x) => {
      await applyLocationExtensionChanges(client, id, {
        Properties: { Type: 'Vendor' },
        Offers: x.Offers ?? []
      });
    }
  },
  Profession: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Description },
      { name: "CategoryId", value: async (x, c) => x.Category?.Name
        ? await c.query(`SELECT "Id" FROM ONLY "ProfessionCategories" WHERE "Name" = $1`, [x.Category.Name]).then(res => res.rows[0]?.Id ?? null)
        : null }
    ],
    table: "Professions",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applyProfessionSkillsChanges(client, id, x.Skills || []),
      applyProfessionUnlocksChanges(client, id, x.Unlocks || [])
    ])
  },
  Skill: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties?.Description ?? null },
      { name: "HPIncrease", value: x => x.Properties?.HpIncrease ?? null },
      { name: "Hidden", value: x => (x.Properties?.IsHidden == null ? null : (x.Properties.IsHidden ? 1 : 0)) },
      { name: "IsExtractable", value: x => x.Properties?.IsExtractable ?? null },
      { name: "CategoryId", value: async (x, c) => x.Category?.Name
        ? await c.query(`SELECT "Id" FROM ONLY "SkillCategories" WHERE "Name" = $1`, [x.Category.Name]).then(res => res.rows[0]?.Id ?? null)
        : null }
    ],
    table: "Skills",
    relationChangeFunc: async (client, id, x) => await Promise.all([
      applySkillProfessionsChanges(client, id, x.Professions || []),
      applySkillUnlocksChanges(client, id, x.Unlocks || [])
    ])
  },
  Mob: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties.Description },
      { name: "SpeciesId", value: async (x, c) => {
        if (x.Species?._newSpecies && x.Species?.Name) {
          const ns = x.Species._newSpecies;
          await c.query(
            `INSERT INTO "MobSpecies" ("Name", "CodexBaseCost", "CodexType")
             VALUES ($1, $2, $3)
             ON CONFLICT ("Name") DO UPDATE SET
               "CodexBaseCost" = COALESCE(EXCLUDED."CodexBaseCost", "MobSpecies"."CodexBaseCost"),
               "CodexType" = COALESCE(EXCLUDED."CodexType", "MobSpecies"."CodexType")`,
            [x.Species.Name, ns.CodexBaseCost ?? null, ns.CodexType ?? null]
          );
        }
        return await c.query(`SELECT "Id" FROM ONLY "MobSpecies" WHERE "Name" = $1`, [x.Species.Name]).then(res => res.rows[0]?.Id);
      }},
      { name: "PlanetId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [x.Planet.Name]).then(res => res.rows[0]?.Id) },
      { name: "AttackRange", value: x => x.Properties.AttackRange },
      { name: "AggressionRange", value: x => x.Properties.AggressionRange },
      { name: "AggressionTimer", value: x => x.Properties.AggressionTimer },
      { name: "AttacksPerMinute", value: x => x.Properties.AttacksPerMinute },
      { name: "Sweatable", value: x => x.Properties.IsSweatable ? 1 : 0 },
      { name: "DefensiveProfessionId", value: async (x, c) => await c.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [x.DefensiveProfession.Name]).then(res => res.rows[0]?.Id) },
      { name: "Type", value: x => {
        const t = (x.Type || '').toLowerCase();
        if (t === 'animal' || t === 'mutant' || t === 'robot' || t === 'asteroid') return x.Type;
        // Back-compat: infer from ScanningProfession if provided by old clients
        const sp = x.ScanningProfession?.Name;
        if (sp === 'Animal Investigator') return 'Animal';
        if (sp === 'Mutant Investigator') return 'Mutant';
        if (sp === 'Robot Investigator') return 'Robot';
        return null;
      } },
    ],
    table: "Mobs",
    relationChangeFunc: async (client, id, x) => {
      // Update MobSpecies.CodexType and CodexBaseCost based on selection and Mob Type
      // _newSpecies comes from the inline species dialog; Properties from normal mob edits
      try {
        if (x.Species?.Name) {
          const speciesProps = x.Species?._newSpecies || x.Species?.Properties;
          const desiredType = x.Type === 'Asteroid'
            ? 'Asteroid'
            : ((speciesProps?.CodexType === 'MobLooter') ? 'MobLooter' : 'Mob');
          await client.query(`UPDATE ONLY "MobSpecies" SET "CodexType" = $2 WHERE "Name" = $1`, [x.Species.Name, desiredType]);

          const baseCost = speciesProps?.CodexBaseCost;
          if (baseCost != null && !Number.isNaN(Number(baseCost))) {
            await client.query(`UPDATE ONLY "MobSpecies" SET "CodexBaseCost" = $2 WHERE "Name" = $1`, [x.Species.Name, Number(baseCost)]);
          }
        }
      } catch (err) {
        console.warn('Failed to set MobSpecies codex fields during Mob upsert', err);
      }

      // If Asteroid, ensure attack/aggression cleared and maturities trimmed
      if (x.Type === 'Asteroid') {
        await client.query(`UPDATE ONLY "Mobs" SET "AttackRange" = NULL, "AggressionRange" = NULL WHERE "Id" = $1`, [id]);
        x.Maturities = (x.Maturities || []).map(m => ({
          ...m,
          Properties: {
            Description: m?.Properties?.Description ?? null,
            Level: m?.Properties?.Level ?? null,
            Health: m?.Properties?.Health ?? null,
            AttacksPerMinute: null,
            RegenerationInterval: null,
            RegenerationAmount: null,
            MissChance: null,
            Taming: { IsTameable: null, TamingLevel: null },
            Attributes: { Strength: null, Agility: null, Intelligence: null, Psyche: null, Stamina: null },
            Defense: { Stab: null, Cut: null, Impact: null, Penetration: null, Shrapnel: null, Burn: null, Cold: null, Acid: null, Electric: null }
          },
          Attacks: []
        }));
      }

      await applyMobMaturityChanges(client, id, x.Maturities);
      await applyMobLootChanges(client, id, x.Loots);
      if (x.Spawns) {
        await applyMobSpawnChanges(client, id, x.Spawns);
      }
    }
  },
  Fish: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Description", value: x => x.Properties?.Description ?? null },
      { name: "ItemId", value: async (x, c) => {
        // Fish IS the material - not a foreign reference to one. The upsert
        // owns the Materials row that backs this fish:
        //
        //   * Update path (x.Id set): resolve the existing Fish row's
        //     ItemId, locate the Materials row, and write Name/Weight/Value
        //     back to it so the material stays in sync with the fish edit.
        //   * Create path: find-or-create a Materials row by Name (so a
        //     Fish can attach to a pre-existing generic material without
        //     duplicating it), then write Weight/Value either way.
        //
        // ItemId is Materials.Id + 1000000 (Items view offset for Materials).
        const weight = x.Properties?.Weight ?? null;
        const ttValue = x.Properties?.Economy?.MaxTT ?? null;

        if (x.Id) {
          const existing = await c.query(
            `SELECT "ItemId" FROM ONLY "Fish" WHERE "Id" = $1`,
            [x.Id]
          );
          const existingItemId = existing.rows[0]?.ItemId;
          if (existingItemId) {
            const matId = existingItemId - 1000000;
            await c.query(
              `UPDATE ONLY "Materials" SET "Name" = $1, "Weight" = $2, "Value" = $3 WHERE "Id" = $4`,
              [x.Name, weight, ttValue, matId]
            );
            return existingItemId;
          }
        }

        // Find-or-create Materials row by name
        const found = await c.query(
          `SELECT "Id" FROM ONLY "Materials" WHERE "Name" = $1 ORDER BY "Id" LIMIT 1`,
          [x.Name]
        );
        let matId = found.rows[0]?.Id;
        if (matId) {
          await c.query(
            `UPDATE ONLY "Materials" SET "Weight" = $1, "Value" = $2 WHERE "Id" = $3`,
            [weight, ttValue, matId]
          );
        } else {
          const inserted = await c.query(
            `INSERT INTO "Materials" ("Name", "Weight", "Value") VALUES ($1, $2, $3) RETURNING "Id"`,
            [x.Name, weight, ttValue]
          );
          matId = inserted.rows[0].Id;
        }
        return matId + 1000000;
      }},
      { name: "SpeciesId", value: async (x, c) => {
        // Fish ↔ MobSpecies is 1:1. Always upsert the species row by the
        // name provided in the form (defaults to the fish's own Name when
        // not set) and force CodexType='Fish'.
        const speciesName = x.Species?.Name || x.Name;
        if (!speciesName) return null;
        const baseCost = x.Species?.CodexBaseCost ?? null;
        await c.query(
          `INSERT INTO "MobSpecies" ("Name", "CodexBaseCost", "CodexType")
           VALUES ($1, $2, 'Fish'::"CodexType")
           ON CONFLICT ("Name") DO UPDATE SET
             "CodexBaseCost" = COALESCE(EXCLUDED."CodexBaseCost", "MobSpecies"."CodexBaseCost"),
             "CodexType" = 'Fish'::"CodexType"`,
          [speciesName, baseCost]
        );
        return await c.query(`SELECT "Id" FROM ONLY "MobSpecies" WHERE "Name" = $1`, [speciesName]).then(res => res.rows[0]?.Id ?? null);
      }},
      { name: "Biome", value: x => x.Properties?.Biome ?? null },
      { name: "Size", value: x => x.Properties?.Size ?? null },
      { name: "Strength", value: x => x.Properties?.Strength ?? null },
      { name: "Difficulty", value: x => x.Properties?.Difficulty ?? null },
      { name: "MinDepth", value: x => x.Properties?.MinDepth ?? null },
      { name: "PreferredLureId", value: async (x, c) => {
        if (!x.PreferredLure?.Name) return null;
        // Only FishingLure items are valid preferred lures.
        return await c.query(
          `SELECT "Id" FROM "Items" WHERE "Name" = $1 AND "Type" = 'FishingLure'`,
          [x.PreferredLure.Name]
        ).then(res => res.rows[0]?.Id ?? null);
      }},
      { name: "TimeOfDay", value: x => x.Properties?.TimeOfDay ?? null }
    ],
    table: "Fish",
    relationChangeFunc: async (client, id, x) => {
      await applyFishPlanetsChanges(client, id, x.Planets || []);
      await applyFishRodTypesChanges(client, id, x.Properties?.RodTypes || []);
    }
  },
  Mission: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "PlanetId", value: async (x, c) => x.Planet?.Name ? await c.query(`SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [x.Planet.Name]).then(res => res.rows[0]?.Id ?? null) : null },
      { name: "MissionChainId", value: async (x, c) => x.MissionChain?.Name ? await upsertMissionChain(c, x.MissionChain) : null },
      { name: "EventId", value: x => x.Event?.Id ?? null },
      { name: "Type", value: x => x.Properties?.Type ?? null },
      { name: "Description", value: x => x.Properties?.Description ?? null },
      { name: "CooldownDuration", value: x => x.Properties?.CooldownDuration ?? null },
      { name: "CooldownStartsOn", value: x => x.Properties?.CooldownStartsOn ?? null },
      { name: "StartLocationId", value: x => x.StartLocationId != null ? Number(x.StartLocationId) : null }
    ],
    table: "Missions",
    relationChangeFunc: async (client, id, x) => {
      await applyMissionStepsChanges(client, id, x.Steps || []);
      await applyMissionRewardsChanges(client, id, x.Rewards || null);
      if (x.Dependencies) {
        await applyMissionDependenciesChanges(client, id, x.Dependencies);
      }
    }
  },
  Location: {
    columns: [
      { name: "Name", value: x => x.Name },
      { name: "Type", value: x => x.Properties?.Type ?? null },
      { name: "Description", value: x => x.Properties?.Description ?? null },
      { name: "Longitude", value: x => x.Properties?.Coordinates?.Longitude ?? null },
      { name: "Latitude", value: x => x.Properties?.Coordinates?.Latitude ?? null },
      { name: "Altitude", value: x => x.Properties?.Coordinates?.Altitude ?? null },
      { name: "TechnicalId", value: x => x.Properties?.TechnicalId ?? null },
      { name: "PlanetId", value: async (x, c) => x.Planet?.Name ? await c.query(`SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [x.Planet.Name]).then(res => res.rows[0]?.Id ?? null) : null },
      { name: "ParentLocationId", value: async (x, c) => x.ParentLocation?.Name ? await c.query(`SELECT "Id" FROM ONLY "Locations" WHERE "Name" = $1`, [x.ParentLocation.Name]).then(res => res.rows[0]?.Id ?? null) : null }
    ],
    table: "Locations",
    relationChangeFunc: async (client, id, x) => {
      await applyLocationFacilitiesChanges(client, id, x.Facilities || []);
      await applyLocationExtensionChanges(client, id, x);
    }
  },
  // Backwards compatibility: existing pending changes may use entity='Area'
  get Area() { return this.Location; }
}

/**
 * Upsert or delete an ItemProperties row for the given global ItemId.
 * Deletes the row when both flags are falsy (only rows with at least one TRUE flag are kept).
 */
async function applyItemProperties(client, itemId, x) {
  const isUntradeable = x.Properties?.IsUntradeable || false;
  const isRare = x.Properties?.IsRare || false;
  if (isUntradeable || isRare) {
    await client.query(
      `INSERT INTO "ItemProperties" ("ItemId", "IsUntradeable", "IsRare")
       VALUES ($1, $2, $3)
       ON CONFLICT ("ItemId") DO UPDATE SET "IsUntradeable" = $2, "IsRare" = $3`,
      [itemId, isUntradeable, isRare]
    );
  } else {
    await client.query(`DELETE FROM "ItemProperties" WHERE "ItemId" = $1`, [itemId]);
  }
}

async function applyMissionStepsChanges(client, missionId, steps) {
  const normalized = (steps || []).map((step, index) => ({
    Id: Number.isInteger(step?.Id) ? step.Id : null,
    Index: Number.isFinite(Number(step?.Index)) ? Number(step.Index) : index + 1,
    Title: step?.Title ?? null,
    Description: step?.Description ?? null,
    Objectives: Array.isArray(step?.Objectives) ? step.Objectives : []
  }));

  const existing = await client.query(`SELECT "Id" FROM ONLY "MissionSteps" WHERE "MissionId" = $1`, [missionId]);
  const existingIds = existing.rows.map(r => r.Id);
  const incomingIds = normalized.map(step => step.Id).filter(id => Number.isInteger(id));

  if (incomingIds.length > 0) {
    await client.query(
      `DELETE FROM ONLY "MissionSteps" WHERE "MissionId" = $1 AND "Id" NOT IN (SELECT * FROM unnest($2::int[]))`,
      [missionId, incomingIds]
    );
  } else {
    await client.query(`DELETE FROM ONLY "MissionSteps" WHERE "MissionId" = $1`, [missionId]);
  }

  for (const step of normalized) {
    let stepId = step.Id;
    if (stepId && existingIds.includes(stepId)) {
      await client.query(
        `UPDATE ONLY "MissionSteps"
         SET "Index" = $2, "Title" = $3, "Description" = $4
         WHERE "Id" = $1`,
        [stepId, step.Index, step.Title, step.Description]
      );
    } else {
      const result = await client.query(
        `INSERT INTO "MissionSteps" ("MissionId", "Index", "Title", "Description")
         VALUES ($1, $2, $3, $4)
         RETURNING "Id"`,
        [missionId, step.Index, step.Title, step.Description]
      );
      stepId = result.rows[0]?.Id;
    }

    if (stepId) {
      await applyMissionObjectivesChanges(client, stepId, step.Objectives || []);
    }
  }
}

async function applyMissionObjectivesChanges(client, stepId, objectives) {
  const normalized = (objectives || []).map(obj => ({
    Id: Number.isInteger(obj?.Id) ? obj.Id : null,
    Type: obj?.Type ?? 'Dialog',
    Payload: obj?.Payload ?? {}
  }));

  const existing = await client.query(`SELECT "Id" FROM ONLY "MissionObjectives" WHERE "StepId" = $1`, [stepId]);
  const existingIds = existing.rows.map(r => r.Id);
  const incomingIds = normalized.map(obj => obj.Id).filter(id => Number.isInteger(id));

  if (incomingIds.length > 0) {
    await client.query(
      `DELETE FROM ONLY "MissionObjectives" WHERE "StepId" = $1 AND "Id" NOT IN (SELECT * FROM unnest($2::int[]))`,
      [stepId, incomingIds]
    );
  } else {
    await client.query(`DELETE FROM ONLY "MissionObjectives" WHERE "StepId" = $1`, [stepId]);
  }

  for (const objective of normalized) {
    const payloadJson = JSON.stringify(objective.Payload ?? {});
    if (objective.Id && existingIds.includes(objective.Id)) {
      await client.query(
        `UPDATE ONLY "MissionObjectives"
         SET "Type" = $2, "Payload" = $3::jsonb
         WHERE "Id" = $1`,
        [objective.Id, objective.Type, payloadJson]
      );
    } else {
      await client.query(
        `INSERT INTO "MissionObjectives" ("StepId", "Type", "Payload")
         VALUES ($1, $2, $3::jsonb)
         ON CONFLICT ("Id") DO UPDATE SET "Type" = EXCLUDED."Type", "Payload" = EXCLUDED."Payload"`,
        [stepId, objective.Type, payloadJson]
      );
    }
  }
}

async function applyMissionRewardsChanges(client, missionId, rewards) {
  // Choices format: rewards is an array of {Items, Skills, Unlocks} packages
  if (Array.isArray(rewards)) {
    await client.query(
      `INSERT INTO "MissionRewards" ("MissionId", "Items", "Skills", "Unlocks")
       VALUES ($1, $2::jsonb, NULL, NULL)
       ON CONFLICT ("MissionId") DO UPDATE SET
         "Items" = EXCLUDED."Items",
         "Skills" = NULL,
         "Unlocks" = NULL`,
      [missionId, JSON.stringify(rewards)]
    );
    return;
  }

  // Flat format: rewards is {Items, Skills, Unlocks}
  const items = Array.isArray(rewards?.Items) ? rewards.Items : [];
  const skills = Array.isArray(rewards?.Skills) ? rewards.Skills : [];
  const unlocks = Array.isArray(rewards?.Unlocks) ? rewards.Unlocks : [];

  await client.query(
    `INSERT INTO "MissionRewards" ("MissionId", "Items", "Skills", "Unlocks")
     VALUES ($1, $2::jsonb, $3::jsonb, $4)
     ON CONFLICT ("MissionId") DO UPDATE SET
       "Items" = EXCLUDED."Items",
       "Skills" = EXCLUDED."Skills",
       "Unlocks" = EXCLUDED."Unlocks"`,
    [missionId, JSON.stringify(items), JSON.stringify(skills), unlocks]
  );
}

async function applyMissionDependenciesChanges(client, missionId, dependencies) {
  if (!dependencies) return;

  // Handle Prerequisites (missions that must be completed before this one)
  const prereqs = Array.isArray(dependencies.Prerequisites) ? dependencies.Prerequisites : [];
  const prereqIds = [];

  for (const entry of prereqs) {
    if (Number.isInteger(entry?.Id)) {
      prereqIds.push(entry.Id);
      continue;
    }
    if (entry?.Name) {
      const result = await client.query(`SELECT "Id" FROM ONLY "Missions" WHERE "Name" = $1`, [entry.Name]);
      const found = result.rows[0]?.Id;
      if (Number.isInteger(found)) prereqIds.push(found);
    }
  }

  const uniquePrereqIds = Array.from(new Set(prereqIds));

  if (uniquePrereqIds.length > 0) {
    await client.query(
      `DELETE FROM ONLY "MissionDependencies"
       WHERE "MissionId" = $1 AND "PrerequisiteMissionId" NOT IN (SELECT * FROM unnest($2::int[]))`,
      [missionId, uniquePrereqIds]
    );
  } else {
    await client.query(`DELETE FROM ONLY "MissionDependencies" WHERE "MissionId" = $1`, [missionId]);
  }

  await Promise.all(uniquePrereqIds.map(id => client.query(
    `INSERT INTO "MissionDependencies" ("MissionId", "PrerequisiteMissionId")
     VALUES ($1, $2)
     ON CONFLICT ("MissionId", "PrerequisiteMissionId") DO NOTHING`,
    [missionId, id]
  )));

  // Handle Dependents (missions that this one unlocks)
  // These are stored as entries where current mission is the PrerequisiteMissionId
  const dependents = Array.isArray(dependencies.Dependents) ? dependencies.Dependents : [];
  const dependentIds = [];

  for (const entry of dependents) {
    if (Number.isInteger(entry?.Id)) {
      dependentIds.push(entry.Id);
      continue;
    }
    if (entry?.Name) {
      const result = await client.query(`SELECT "Id" FROM ONLY "Missions" WHERE "Name" = $1`, [entry.Name]);
      const found = result.rows[0]?.Id;
      if (Number.isInteger(found)) dependentIds.push(found);
    }
  }

  const uniqueDependentIds = Array.from(new Set(dependentIds));

  // Update dependent relationships (where this mission is the prerequisite)
  if (uniqueDependentIds.length > 0) {
    await client.query(
      `DELETE FROM ONLY "MissionDependencies"
       WHERE "PrerequisiteMissionId" = $1 AND "MissionId" NOT IN (SELECT * FROM unnest($2::int[]))`,
      [missionId, uniqueDependentIds]
    );
  } else {
    await client.query(`DELETE FROM ONLY "MissionDependencies" WHERE "PrerequisiteMissionId" = $1`, [missionId]);
  }

  await Promise.all(uniqueDependentIds.map(id => client.query(
    `INSERT INTO "MissionDependencies" ("MissionId", "PrerequisiteMissionId")
     VALUES ($1, $2)
     ON CONFLICT ("MissionId", "PrerequisiteMissionId") DO NOTHING`,
    [id, missionId]
  )));
}

/**
 * Upsert a MissionChain - insert if not exists, update if exists.
 * Returns the chain ID.
 * @param {Object} client - Database client
 * @param {Object} chainData - Chain data with Name, Planet, Properties
 *   Supports two formats:
 *   - Schema format: { Name, Planet: { Name }, Properties: { Type, Description } }
 *   - API format: { Name, Planet: "string", Description: "string" }
 */
async function upsertMissionChain(client, chainData) {
  if (!chainData?.Name) return null;

  // Normalize planet name - support both { Name: "..." } and "..." formats
  const planetName = typeof chainData.Planet === 'string'
    ? chainData.Planet
    : chainData.Planet?.Name;

  // Normalize description - support both Properties.Description and Description
  const description = chainData.Properties?.Description ?? chainData.Description ?? null;
  const type = chainData.Properties?.Type ?? chainData.Type ?? null;

  // Check if chain exists
  const existing = await client.query(
    `SELECT "Id" FROM ONLY "MissionChains" WHERE "Name" = $1`,
    [chainData.Name]
  );

  // Get planet ID if provided
  let planetId = null;
  if (planetName) {
    const planetResult = await client.query(
      `SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`,
      [planetName]
    );
    planetId = planetResult.rows[0]?.Id ?? null;
  }

  if (existing.rows.length > 0) {
    // Chain exists - update it if we have any additional data
    const chainId = existing.rows[0].Id;

    // Update if any data is provided (not just Properties)
    if (chainData.Properties || chainData.Description !== undefined || chainData.Planet !== undefined) {
      await client.query(
        `UPDATE ONLY "MissionChains"
         SET "Type" = COALESCE($2, "Type"),
             "Description" = COALESCE($3, "Description"),
             "PlanetId" = COALESCE($4, "PlanetId")
         WHERE "Id" = $1`,
        [chainId, type, description, planetId]
      );
    }

    return chainId;
  }

  // Chain doesn't exist - create it
  const result = await client.query(
    `INSERT INTO "MissionChains" ("Name", "PlanetId", "Type", "Description")
     VALUES ($1, $2, $3, $4)
     RETURNING "Id"`,
    [
      chainData.Name,
      planetId,
      type,
      description
    ]
  );

  return result.rows[0]?.Id ?? null;
}

/**
 * Validate that all missions in a chain are connected.
 * Returns { isConnected: boolean, disconnectedMissions: string[] }
 * @param {Object} client - Database client
 * @param {number} chainId - The mission chain ID to validate
 */
export async function validateChainConnectivity(client, chainId) {
  if (!chainId) return { isConnected: true, disconnectedMissions: [] };

  // Get all missions in the chain
  const missionsResult = await client.query(
    `SELECT "Id", "Name" FROM ONLY "Missions" WHERE "MissionChainId" = $1`,
    [chainId]
  );
  const missions = missionsResult.rows;

  if (missions.length <= 1) {
    return { isConnected: true, disconnectedMissions: [] };
  }

  const missionIds = new Set(missions.map(m => m.Id));

  // Get all dependencies within this chain
  const depsResult = await client.query(
    `SELECT "MissionId", "PrerequisiteMissionId"
     FROM ONLY "MissionDependencies"
     WHERE "MissionId" = ANY($1) AND "PrerequisiteMissionId" = ANY($1)`,
    [[...missionIds]]
  );

  // Build adjacency lists
  const adjacencyNext = new Map(); // prerequisite -> missions it unlocks
  const adjacencyPrev = new Map(); // mission -> its prerequisites

  for (const dep of depsResult.rows) {
    const fromId = dep.PrerequisiteMissionId;
    const toId = dep.MissionId;

    if (!adjacencyNext.has(fromId)) adjacencyNext.set(fromId, []);
    adjacencyNext.get(fromId).push(toId);

    if (!adjacencyPrev.has(toId)) adjacencyPrev.set(toId, []);
    adjacencyPrev.get(toId).push(fromId);
  }

  // Find root missions (no prerequisites within the chain)
  const roots = missions.filter(m => {
    const prereqs = adjacencyPrev.get(m.Id) || [];
    return prereqs.length === 0;
  });

  if (roots.length === 0) {
    // All missions have prerequisites - there's a cycle or all are disconnected
    return {
      isConnected: false,
      disconnectedMissions: missions.map(m => m.Name)
    };
  }

  // BFS from all roots to find all reachable missions
  const visited = new Set();
  const queue = roots.map(r => r.Id);
  queue.forEach(id => visited.add(id));

  while (queue.length > 0) {
    const current = queue.shift();
    const unlocks = adjacencyNext.get(current) || [];
    for (const unlockId of unlocks) {
      if (!visited.has(unlockId)) {
        visited.add(unlockId);
        queue.push(unlockId);
      }
    }
  }

  // Find disconnected missions
  const disconnected = missions.filter(m => !visited.has(m.Id));

  return {
    isConnected: disconnected.length === 0,
    disconnectedMissions: disconnected.map(m => m.Name)
  };
}

async function applyEstateSectionsChanges(client, locationId, sections) {
  const normalized = (sections || []).map(s => ({
    Name: s.Name,
    Description: s.Description ?? null,
    ItemPoints: s.ItemPoints ?? s.MaxItemPoints ?? null
  }));
  const newSectionNames = normalized.map(s => s.Name);

  // Remove sections not present anymore
  await client.query(
    `DELETE FROM ONLY "EstateSections" WHERE "LocationId" = $1 AND "Name" NOT IN (SELECT * FROM unnest($2::text[]))`,
    [locationId, newSectionNames.length ? newSectionNames : ['']]
  );

  // Upsert sections with ItemPoints using a single statement
  await Promise.all(normalized.map(s => client.query(`
    INSERT INTO "EstateSections" ("LocationId", "Name", "Description", "ItemPoints")
    VALUES ($1, $2, $3, $4)
    ON CONFLICT ("LocationId", "Name") DO UPDATE SET
      "Description" = EXCLUDED."Description",
      "ItemPoints" = EXCLUDED."ItemPoints"
  `, [locationId, s.Name, s.Description, s.ItemPoints])));
}

// Location helper functions
async function applyLocationFacilitiesChanges(client, locationId, facilities) {
  const facilityNames = (facilities || [])
    .map(f => typeof f === 'string' ? f : f?.Name)
    .filter(Boolean);

  if (facilityNames.length === 0) {
    await client.query(`DELETE FROM ONLY "LocationFacilities" WHERE "LocationId" = $1`, [locationId]);
    return;
  }

  // Get facility IDs by name
  const { rows: facilityRows } = await client.query(
    `SELECT "Id", "Name" FROM ONLY "Facilities" WHERE "Name" = ANY($1)`,
    [facilityNames]
  );
  const facilityIds = facilityRows.map(r => r.Id);

  // Delete facilities not in the new list
  if (facilityIds.length > 0) {
    await client.query(
      `DELETE FROM ONLY "LocationFacilities" WHERE "LocationId" = $1 AND "FacilityId" NOT IN (SELECT * FROM unnest($2::int[]))`,
      [locationId, facilityIds]
    );
  } else {
    await client.query(`DELETE FROM ONLY "LocationFacilities" WHERE "LocationId" = $1`, [locationId]);
  }

  // Insert new facilities
  for (const facilityId of facilityIds) {
    await client.query(
      `INSERT INTO "LocationFacilities" ("LocationId", "FacilityId") VALUES ($1, $2) ON CONFLICT DO NOTHING`,
      [locationId, facilityId]
    );
  }
}

const AREA_TYPES = ['PvpArea', 'PvpLootArea', 'MobArea', 'LandArea', 'ZoneArea', 'CityArea', 'EstateArea', 'EventArea', 'WaveEventArea'];

async function applyLocationExtensionChanges(client, locationId, x) {
  const locationType = x.Properties?.Type;
  // Derive AreaType: explicit AreaType field, or backward-compat where Type holds the AreaType value
  const areaType = x.Properties?.AreaType ||
    (AREA_TYPES.includes(locationType) ? locationType : null);

  // Handle Areas extension for Area type
  if ((locationType === 'Area' || areaType) && areaType) {
    const sanitized = sanitizeShapeAndData(x.Properties || {});
    const shape = sanitized.shape ?? x.Properties?.Shape ?? 'Point';
    const data = sanitized.data ?? JSON.stringify(x.Properties?.Data ?? {});
    await client.query(
      `INSERT INTO "Areas" ("LocationId", "Type", "Shape", "Data")
       VALUES ($1, $2::"AreaType", $3::"Shape", $4::jsonb)
       ON CONFLICT ("LocationId") DO UPDATE SET "Type" = $2::"AreaType", "Shape" = $3::"Shape", "Data" = $4::jsonb`,
      [locationId, areaType, shape, data]
    );

    // Handle LandAreas extension for LandArea AreaType
    if (areaType === 'LandArea') {
      const taxHunting = x.Properties?.TaxRateHunting ?? null;
      const taxMining = x.Properties?.TaxRateMining ?? null;
      const taxShops = x.Properties?.TaxRateShops ?? null;

      // Changes carry owner as top-level NamedEntity; fall back to legacy Properties field
      const ownerName = x.Owner?.Name || x.Properties?.LandAreaOwnerName || null;
      let ownerId = null;
      let ownerNameToStore = ownerName;
      if (ownerName) {
        try {
          const { rows } = await poolUsers.query(
            'SELECT id FROM users WHERE eu_name = $1 AND verified = true LIMIT 1',
            [ownerName]
          );
          if (rows.length > 0) {
            ownerId = rows[0].id;
            ownerNameToStore = null; // Resolved — don't store the name
          }
        } catch (e) {
          console.error(`Failed to resolve LandArea owner "${ownerName}": ${e.message}`);
          // Fall through: store name without ID
        }
      }

      await client.query(
        `INSERT INTO "LandAreas" ("LocationId", "TaxRateHunting", "TaxRateMining", "TaxRateShops", "OwnerId", "OwnerName")
         VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT ("LocationId") DO UPDATE SET "TaxRateHunting" = $2, "TaxRateMining" = $3, "TaxRateShops" = $4, "OwnerId" = $5, "OwnerName" = $6`,
        [locationId, taxHunting, taxMining, taxShops, ownerId, ownerNameToStore]
      );
    }
  }

  // Handle Estates extension for Estate type
  if (locationType === 'Estate' && x.Properties?.EstateType) {
    const estateType = x.Properties.EstateType;
    const itemTradeAvailable = x.Properties?.ItemTradeAvailable ?? false;
    const maxGuests = x.Properties?.MaxGuests ?? null;

    // Resolve owner: top-level NamedEntity, fall back to legacy Properties.OwnerId
    const estateOwnerName = x.Owner?.Name || null;
    let estateOwnerId = x.Properties?.OwnerId ?? null;
    let estateOwnerNameToStore = null;
    if (estateOwnerName) {
      estateOwnerId = null; // NamedEntity takes precedence over legacy ID
      try {
        const { rows } = await poolUsers.query(
          'SELECT id FROM users WHERE eu_name = $1 AND verified = true LIMIT 1',
          [estateOwnerName]
        );
        if (rows.length > 0) {
          estateOwnerId = rows[0].id;
        } else {
          estateOwnerNameToStore = estateOwnerName;
        }
      } catch (e) {
        console.error(`Failed to resolve Estate owner "${estateOwnerName}": ${e.message}`);
        estateOwnerNameToStore = estateOwnerName;
      }
    }

    await client.query(
      `INSERT INTO "Estates" ("LocationId", "Type", "OwnerId", "OwnerName", "ItemTradeAvailable", "MaxGuests")
       VALUES ($1, $2::"EstateType", $3, $4, $5, $6)
       ON CONFLICT ("LocationId") DO UPDATE SET "Type" = $2::"EstateType", "OwnerId" = $3, "OwnerName" = $4, "ItemTradeAvailable" = $5, "MaxGuests" = $6`,
      [locationId, estateType, estateOwnerId, estateOwnerNameToStore, itemTradeAvailable, maxGuests]
    );

    // Handle EstateSections for estates
    if (Array.isArray(x.Sections)) {
      await applyEstateSectionsChanges(client, locationId, x.Sections);
    }
  }

  // Handle MobSpawns extension for MobArea type
  if (areaType === 'MobArea') {
    const density = x.Properties?.Density ?? null;
    const isShared = x.Properties?.IsShared ? 1 : 0;
    const isEvent = x.Properties?.IsEvent ? 1 : 0;
    const recurringEventId = x.Properties?.RecurringEventId ?? null;
    await client.query(
      `INSERT INTO "MobSpawns" ("LocationId", "Density", "IsShared", "IsEvent", "RecurringEventId")
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT ("LocationId") DO UPDATE SET
         "Density" = COALESCE($2, "MobSpawns"."Density"),
         "IsShared" = $3,
         "IsEvent" = $4,
         "RecurringEventId" = $5`,
      [locationId, density, isShared, isEvent, recurringEventId]
    );

    const mobData = x.Maturities;
    if (Array.isArray(mobData)) {
      if (mobData.length === 0) {
        await client.query(`DELETE FROM "MobSpawnMaturities" WHERE "LocationId" = $1`, [locationId]);
      } else {
        const valid = mobData.filter(m => m.Maturity?.Id != null);
        await client.query(
          `DELETE FROM "MobSpawnMaturities" WHERE "LocationId" = $1 AND "MaturityId" NOT IN (SELECT * FROM unnest($2::int[]))`,
          [locationId, valid.map(m => m.Maturity.Id)]
        );
        await Promise.all(valid.map(m =>
          client.query(
            `INSERT INTO "MobSpawnMaturities" ("LocationId", "MaturityId", "IsRare")
             VALUES ($1, $2, $3)
             ON CONFLICT ("LocationId", "MaturityId") DO UPDATE SET "IsRare" = $3`,
            [locationId, m.Maturity.Id, m.IsRare ? 1 : 0]
          )
        ));
      }
    }
  }

  // Handle VendorOffers for Vendor type
  if (locationType === 'Vendor' && Array.isArray(x.Offers)) {
    await applyVendorOfferChanges(client, locationId, x.Offers);
  }

  // Handle WaveEventWaves for WaveEventArea area type
  if (areaType === 'WaveEventArea' && Array.isArray(x.Waves)) {
    await applyWaveEventWavesChanges(client, locationId, x.Waves);
  }
}

async function applyWaveEventWavesChanges(client, locationId, waves) {
  const normalized = (waves || []).map((wave, index) => ({
    Id: Number.isInteger(wave?.Id) ? wave.Id : null,
    WaveIndex: Number.isFinite(Number(wave?.WaveIndex)) ? Number(wave.WaveIndex) : index,
    TimeToComplete: wave?.TimeToComplete ?? null,
    MobMaturities: Array.isArray(wave?.MobMaturities) ? wave.MobMaturities : []
  }));

  const existing = await client.query(`SELECT "Id" FROM ONLY "WaveEventWaves" WHERE "LocationId" = $1`, [locationId]);
  const existingIds = existing.rows.map(r => r.Id);
  const incomingIds = normalized.map(w => w.Id).filter(id => Number.isInteger(id));

  // Delete waves not in the new list
  if (incomingIds.length > 0) {
    await client.query(
      `DELETE FROM ONLY "WaveEventWaves" WHERE "LocationId" = $1 AND "Id" NOT IN (SELECT * FROM unnest($2::int[]))`,
      [locationId, incomingIds]
    );
  } else {
    await client.query(`DELETE FROM ONLY "WaveEventWaves" WHERE "LocationId" = $1`, [locationId]);
  }

  // Upsert waves
  for (const wave of normalized) {
    const mobMaturitiesJson = JSON.stringify(wave.MobMaturities);
    if (wave.Id && existingIds.includes(wave.Id)) {
      await client.query(
        `UPDATE ONLY "WaveEventWaves"
         SET "WaveIndex" = $2, "TimeToComplete" = $3, "MobMaturities" = $4::jsonb
         WHERE "Id" = $1`,
        [wave.Id, wave.WaveIndex, wave.TimeToComplete, mobMaturitiesJson]
      );
    } else {
      await client.query(
        `INSERT INTO "WaveEventWaves" ("LocationId", "WaveIndex", "TimeToComplete", "MobMaturities")
         VALUES ($1, $2, $3, $4::jsonb)`,
        [locationId, wave.WaveIndex, wave.TimeToComplete, mobMaturitiesJson]
      );
    }
  }
}

// Classify a maturity into a Damage Potential bucket using max attack damage.
// Falls back to the client-supplied value only when no attack has TotalDamage.
// Bucket ranges mirror sql/nexus/migrations/026_seed_enumerations.sql.
function classifyDamagePotential(maturity) {
  const attacks = Array.isArray(maturity?.Attacks) ? maturity.Attacks : [];
  let max = 0;
  for (const a of attacks) {
    const v = a?.TotalDamage;
    if (v != null && v > max) max = v;
  }
  if (max <= 0) return maturity.Properties?.DamagePotential ?? null;
  if (max >= 500) return 'Colossal';
  if (max >= 356) return 'Gigantic';
  if (max >= 271) return 'Immense';
  if (max >= 161) return 'Huge';
  if (max >= 101) return 'Great';
  if (max >= 60)  return 'Large';
  if (max >= 40)  return 'Medium';
  if (max >= 30)  return 'Limited';
  if (max >= 20)  return 'Small';
  return 'Minimal';
}

async function applyMobMaturityChanges(client, mobId, maturities) {
  // Rename detection: UPDATE the (Name, DangerLevel) identity in-place so the Id
  // (and all FK references in MobSpawnMaturities, MobLoots, etc.) is preserved
  // instead of being cascade-deleted / set-null.
  //
  // Phase 1: Explicit renames - frontend sets _oldName + _oldLevel on the maturity
  // object when the user changes a maturity's name or level.
  for (const maturity of maturities) {
    if (maturity._oldName === undefined) continue;
    const oldLevel = maturity._oldLevel ?? -1;
    const newLevel = maturity.Properties.Level ?? -1;
    if (maturity._oldName !== maturity.Name || oldLevel !== newLevel) {
      await client.query(
        `UPDATE ONLY "MobMaturities" SET "Name" = $1, "DangerLevel" = NULLIF($2, -1)
         WHERE "MobId" = $3 AND "Name" = $4 AND COALESCE("DangerLevel", -1) = $5`,
        [maturity.Name, newLevel, mobId, maturity._oldName, oldLevel]
      );
    }
  }

  // Phase 2: Heuristic fallback for changes without explicit metadata (e.g. bot).
  // Match disappearing→appearing by (Level, Health), then Level alone.
  // Only match when exactly 1 candidate exists at that key to avoid wrong pairings.
  const existing = await client.query(
    `SELECT "Id", "Name", "Health", COALESCE("DangerLevel", -1) AS "Level" FROM ONLY "MobMaturities" WHERE "MobId" = $1`,
    [mobId]
  );
  const newPairs = new Set(maturities.map(m => `${m.Name}\0${m.Properties.Level ?? -1}`));
  const existingPairs = new Set(existing.rows.map(e => `${e.Name}\0${e.Level}`));
  const disappearing = existing.rows.filter(e => !newPairs.has(`${e.Name}\0${e.Level}`));
  const appearing = maturities.filter(m =>
    m._oldName === undefined && !existingPairs.has(`${m.Name}\0${m.Properties.Level ?? -1}`)
  );

  if (disappearing.length > 0 && appearing.length > 0) {
    const matched = new Set();
    for (const pass of ['levelHealth', 'level']) {
      const keyFnOld = pass === 'levelHealth' ? e => `${e.Level}\0${e.Health}` : e => `${e.Level}`;
      const keyFnNew = pass === 'levelHealth' ? m => `${m.Properties.Level ?? -1}\0${m.Properties.Health}` : m => `${m.Properties.Level ?? -1}`;

      const oldByKey = new Map();
      for (const d of disappearing) {
        if (matched.has(d.Id)) continue;
        const k = keyFnOld(d);
        if (!oldByKey.has(k)) oldByKey.set(k, []);
        oldByKey.get(k).push(d);
      }
      const newByKey = new Map();
      for (const a of appearing) {
        if (matched.has(a.Name)) continue;
        const k = keyFnNew(a);
        if (!newByKey.has(k)) newByKey.set(k, []);
        newByKey.get(k).push(a);
      }

      for (const [key, oldGroup] of oldByKey) {
        const newGroup = newByKey.get(key);
        if (oldGroup.length === 1 && newGroup?.length === 1) {
          await client.query(
            `UPDATE ONLY "MobMaturities" SET "Name" = $1 WHERE "Id" = $2`,
            [newGroup[0].Name, oldGroup[0].Id]
          );
          matched.add(oldGroup[0].Id);
          matched.add(newGroup[0].Name);
        }
      }
    }
  }

  maturities = await Promise.all([
    client.query(
      `DELETE FROM ONLY "MobMaturities"
       WHERE "MobId" = $1
         AND ("Name", COALESCE("DangerLevel", -1)) NOT IN (
           SELECT * FROM unnest($2::text[], $3::int[])
         )`,
      [mobId, maturities.map(x => x.Name), maturities.map(x => x.Properties.Level ?? -1)]
    ),
    ...maturities.map(maturity => client.query(`
      INSERT INTO "MobMaturities"
      ("MobId", "Name", "NameMode", "Health", "RegenerationInterval", "RegenerationAmount", "AttackSpeed", "DangerLevel", "TamingLevel", "Strength", "Agility", "Intelligence", "Psyche", "Stamina", "MissChance", "ResistanceStab", "ResistanceCut", "ResistanceImpact", "ResistancePenetration", "ResistanceShrapnel", "ResistanceBurn", "ResistanceCold", "ResistanceAcid", "ResistanceElectric", "Boss", "Description", "DamagePotential")
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27)
      ON CONFLICT ("MobId", "Name", (COALESCE("DangerLevel", -1))) DO UPDATE SET
      "NameMode" = $3, "Health" = $4, "RegenerationInterval" = $5, "RegenerationAmount" = $6, "AttackSpeed" = $7, "DangerLevel" = $8, "TamingLevel" = $9, "Strength" = $10, "Agility" = $11, "Intelligence" = $12, "Psyche" = $13, "Stamina" = $14, "MissChance" = $15, "ResistanceStab" = $16, "ResistanceCut" = $17, "ResistanceImpact" = $18, "ResistancePenetration" = $19, "ResistanceShrapnel" = $20, "ResistanceBurn" = $21, "ResistanceCold" = $22, "ResistanceAcid" = $23, "ResistanceElectric" = $24, "Boss" = $25, "Description" = $26, "DamagePotential" = $27
      RETURNING "Id"`,
      [
        mobId,
        maturity.Name,
        maturity.NameMode || null,
        maturity.Properties.Health,
        maturity.Properties.RegenerationInterval,
        maturity.Properties.RegenerationAmount,
        maturity.Properties.AttacksPerMinute,
        maturity.Properties.Level,
        maturity.Properties.Taming?.TamingLevel ?? null,
        maturity.Properties.Attributes?.Strength ?? null,
        maturity.Properties.Attributes?.Agility ?? null,
        maturity.Properties.Attributes?.Intelligence ?? null,
        maturity.Properties.Attributes?.Psyche ?? null,
        maturity.Properties.Attributes?.Stamina ?? null,
        maturity.Properties.MissChance,
        maturity.Properties.Defense?.Stab ?? null,
        maturity.Properties.Defense?.Cut ?? null,
        maturity.Properties.Defense?.Impact ?? null,
        maturity.Properties.Defense?.Penetration ?? null,
        maturity.Properties.Defense?.Shrapnel ?? null,
        maturity.Properties.Defense?.Burn ?? null,
        maturity.Properties.Defense?.Cold ?? null,
        maturity.Properties.Defense?.Acid ?? null,
        maturity.Properties.Defense?.Electric ?? null,
        maturity.Properties.Boss || false,
        maturity.Properties.Description ?? null,
        classifyDamagePotential(maturity)]).then(res => ({ ...maturity, Id: res.rows[0].Id })))
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

async function applyFishPlanetsChanges(client, fishId, planets) {
  planets = Array.isArray(planets) ? planets : [];

  const resolved = await Promise.all(planets.map(async p => {
    if (!p?.Name) return null;
    const r = await client.query(`SELECT "Id" FROM ONLY "Planets" WHERE "Name" = $1`, [p.Name]);
    return r.rows[0]?.Id ?? null;
  }));
  const newIds = resolved.filter(id => Number.isInteger(id));

  await client.query(
    `DELETE FROM "FishPlanets" WHERE "FishId" = $1 AND "PlanetId" NOT IN (SELECT * FROM unnest($2::int[]))`,
    [fishId, newIds]
  );
  await Promise.all(newIds.map(pid => client.query(
    `INSERT INTO "FishPlanets" ("FishId", "PlanetId") VALUES ($1, $2) ON CONFLICT DO NOTHING`,
    [fishId, pid]
  )));
}

async function applyFishRodTypesChanges(client, fishId, rodTypes) {
  rodTypes = Array.isArray(rodTypes) ? rodTypes.filter(Boolean) : [];

  await client.query(
    `DELETE FROM "FishRodTypes" WHERE "FishId" = $1 AND "RodType" NOT IN (SELECT * FROM unnest($2::"FishingRodType"[]))`,
    [fishId, rodTypes]
  );
  await Promise.all(rodTypes.map(rt => client.query(
    `INSERT INTO "FishRodTypes" ("FishId", "RodType") VALUES ($1, $2::"FishingRodType") ON CONFLICT DO NOTHING`,
    [fishId, rt]
  )));
}

async function applyMobLootChanges(client, mobId, loots) {
  // Normalize input
  loots = Array.isArray(loots) ? loots : [];

  // Resolve Item and Maturity IDs
  await Promise.all(loots.map(loot => client.query(`SELECT "Id" FROM ONLY "Items" WHERE "Name" = $1`, [loot.Item.Name]).then(res => loot.Item.Id = res.rows[0]?.Id)));
  await Promise.all(loots.map(loot => client.query(`SELECT "Id" FROM ONLY "MobMaturities" WHERE "MobId" = $1 AND "Name" = $2`, [mobId, loot.Maturity.Name]).then(res => loot.Maturity.Id = res.rows[0]?.Id)));

  const newItemIds = loots
    .map(loot => loot?.Item?.Id)
    .filter(id => Number.isInteger(id));

  await Promise.all([
    client.query(`DELETE FROM ONLY "MobLoots" WHERE "MobId" = $1 AND "ItemId" NOT IN (SELECT * FROM unnest($2::int[]))`, [mobId, newItemIds]),
    ...loots.map(loot => client.query(`
      INSERT INTO "MobLoots" ("MobId", "ItemId", "MaturityId", "Frequency", "IsEvent")
      VALUES ($1, $2, $3, $4, $5)
      ON CONFLICT ("MobId", "ItemId") DO UPDATE SET
      "MaturityId" = $3, "Frequency" = $4, "IsEvent" = $5`,
      [mobId, loot.Item.Id, loot.Maturity.Id ?? null, loot.Frequency, loot.IsEvent ? 1 : 0])
    )
  ]);
}

async function applyVendorOfferChanges(client, locationId, offers) {
  let newItems = await Promise.all(offers.map(offer => client.query(`SELECT "Id" FROM ONLY "Items" WHERE "Name" = $1`, [offer.Item.Name]).then(res => ({ id: res.rows[0]?.Id, name: offer.Item.Name, limited: offer.IsLimited, prices: offer.Prices, value: offer.Value }))));

  let newOffers = (await Promise.all([
    // Delete offers that aren't in the new set
    client.query(`DELETE FROM ONLY "VendorOffers" WHERE "LocationId" = $1 AND "ItemId" NOT IN (SELECT * FROM unnest($2::int[]))`, [locationId, newItems.map(x => x.id)]),
    ...newItems.map(item => client.query(`INSERT INTO "VendorOffers" ("LocationId", "ItemId", "IsLimited", "Value") VALUES ($1, $2, $3, $4) ON CONFLICT ("LocationId", "ItemId") DO UPDATE SET "IsLimited" = $3, "Value" = $4 RETURNING "Id"`, [locationId, item.id, item.limited, item.value]).then(res => ({ id: res.rows[0].Id, prices: item.prices })))
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

async function upsertNewEffects(client, effects) {
  for (const effect of effects) {
    if (!effect._newEffect || !effect.Name) continue;
    const { CanonicalName, Unit, IsPositive, Description } = effect._newEffect;
    await client.query(
      `INSERT INTO "Effects" ("Name", "CanonicalName", "Unit", "IsPositive", "Description")
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT ("Name") DO UPDATE SET
         "CanonicalName" = COALESCE(EXCLUDED."CanonicalName", "Effects"."CanonicalName"),
         "Unit" = COALESCE(EXCLUDED."Unit", "Effects"."Unit"),
         "IsPositive" = COALESCE(EXCLUDED."IsPositive", "Effects"."IsPositive"),
         "Description" = COALESCE(EXCLUDED."Description", "Effects"."Description")`,
      [effect.Name, CanonicalName || null, Unit || null, IsPositive != null ? (IsPositive ? 1 : 0) : null, Description || null]
    );
  }
}

async function resolveEffectIds(client, effects) {
  await upsertNewEffects(client, effects);
  const validEffects = effects.filter(e => e.Name);
  return Promise.all(validEffects.map(effect =>
    client.query(`SELECT "Id" FROM ONLY "Effects" WHERE "Name" = $1`, [effect.Name]).then(res => {
      if (!res.rows[0]) throw new Error(`Effect "${effect.Name}" not found in Effects table`);
      return { Id: res.rows[0].Id, ...effect };
    })
  ));
}

async function applyEffectsOnUseChanges(client, id, effects) {
  let newEffects = await resolveEffectIds(client, effects);

  let newEffectsArrayId = newEffects.map(effect => effect.Id);

  await Promise.all([
    client.query(`DELETE FROM ONLY "EffectsOnUse" WHERE "ItemId" = $1 AND "EffectId" NOT IN (SELECT * FROM unnest($2::int[]))`, [id, newEffectsArrayId]),
    ...newEffects.map(effect => client.query(`INSERT INTO "EffectsOnUse" ("ItemId", "EffectId", "Strength", "DurationSeconds") VALUES ($1, $2, $3, $4) ON CONFLICT ("ItemId", "EffectId") DO UPDATE SET "Strength" = $3, "DurationSeconds" = $4`, [id, effect.Id, effect.Values.Strength, effect.Values.DurationSeconds]))
  ]);
}

async function applyEffectsOnConsumeChanges(client, id, effects) {
  let newEffects = await resolveEffectIds(client, effects);

  let newEffectsArrayId = newEffects.map(effect => effect.Id);

  await Promise.all([
    client.query(`DELETE FROM ONLY "EffectsOnConsume" WHERE "ConsumableId" = $1 AND "EffectId" NOT IN (SELECT * FROM unnest($2::int[]))`, [id, newEffectsArrayId]),
    ...newEffects.map(effect => client.query(`INSERT INTO "EffectsOnConsume" ("ConsumableId", "EffectId", "Strength", "DurationSeconds") VALUES ($1, $2, $3, $4) ON CONFLICT ("ConsumableId", "EffectId") DO UPDATE SET "Strength" = $3, "DurationSeconds" = $4`, [id, effect.Id, effect.Values.Strength, effect.Values.DurationSeconds]))
  ]);
}

async function applyEffectsOnEquipChanges(client, id, effects) {
  let newEffects = await resolveEffectIds(client, effects);

  let newEffectsArrayId = newEffects.map(effect => effect.Id);

  await Promise.all([
    client.query(`DELETE FROM ONLY "EffectsOnEquip" WHERE "ItemId" = $1 AND "EffectId" NOT IN (SELECT * FROM unnest($2::int[]))`, [id, newEffectsArrayId]),
    ...newEffects.map(effect => client.query(`INSERT INTO "EffectsOnEquip" ("ItemId", "EffectId", "Strength") VALUES ($1, $2, $3) ON CONFLICT ("ItemId", "EffectId") DO UPDATE SET "Strength" = $3`, [id, effect.Id, effect.Values.Strength]))
  ]);
}

async function applyEffectsOnSetEquipChanges(client, setId, effects) {
  let newEffects = await resolveEffectIds(client, effects);

  let newEffectsArrayId = newEffects.map(effect => effect.Id);
  let newEffectsArrayMinSetPieces = newEffects.map(effect => effect.Values.MinSetPieces);

  await Promise.all([
    // Since the primary key is a composite of EffectId and MinSetPieces, we need to delete all rows that don't match the new effects
    client.query(`DELETE FROM ONLY "EffectsOnSetEquip" WHERE "SetId" = $1 AND ("EffectId", "MinSetPieces") NOT IN (SELECT * FROM unnest($2::int[], $3::int[]))`, [setId, newEffectsArrayId, newEffectsArrayMinSetPieces]),
    ...newEffects.map(effect => client.query(`INSERT INTO "EffectsOnSetEquip" ("SetId", "EffectId", "Strength", "MinSetPieces") VALUES ($1, $2, $3, $4) ON CONFLICT ("SetId", "EffectId", "MinSetPieces") DO UPDATE SET "Strength" = $3`, [setId, effect.Id, effect.Values.Strength, effect.Values.MinSetPieces]))
  ]);
}

async function applyPetEffectChanges(client, petId, effects) {
  let newEffects = await resolveEffectIds(client, effects);

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

async function resolveProfessionId(client, profession) {
  if (profession?.Id) return profession.Id;
  if (!profession?.Name) return null;
  const res = await client.query(`SELECT "Id" FROM ONLY "Professions" WHERE "Name" = $1`, [profession.Name]);
  return res.rows[0]?.Id ?? null;
}

async function resolveSkillId(client, skill) {
  if (skill?.Id) return skill.Id;
  if (!skill?.Name) return null;
  const res = await client.query(`SELECT "Id" FROM ONLY "Skills" WHERE "Name" = $1`, [skill.Name]);
  return res.rows[0]?.Id ?? null;
}

async function applyProfessionSkillsChanges(client, professionId, skills) {
  const entries = await Promise.all((skills || []).map(async (entry) => {
    const skillId = await resolveSkillId(client, entry?.Skill);
    if (!skillId) return null;
    return { skillId, weight: entry?.Weight ?? null };
  }));
  const valid = entries.filter(Boolean);
  if (valid.length === 0) {
    await client.query(`DELETE FROM ONLY "ProfessionSkills" WHERE "ProfessionId" = $1`, [professionId]);
    return;
  }
  const skillIds = valid.map(entry => entry.skillId);
  await client.query(
    `DELETE FROM ONLY "ProfessionSkills" WHERE "ProfessionId" = $1 AND "SkillId" NOT IN (SELECT * FROM unnest($2::int[]))`,
    [professionId, skillIds]
  );
  await Promise.all(valid.map(entry => client.query(
    `INSERT INTO "ProfessionSkills" ("ProfessionId", "SkillId", "Weight")
     VALUES ($1, $2, $3)
     ON CONFLICT ("ProfessionId", "SkillId") DO UPDATE SET "Weight" = $3`,
    [professionId, entry.skillId, entry.weight]
  )));
}

async function applySkillProfessionsChanges(client, skillId, professions) {
  const entries = await Promise.all((professions || []).map(async (entry) => {
    const professionId = await resolveProfessionId(client, entry?.Profession);
    if (!professionId) return null;
    return { professionId, weight: entry?.Weight ?? null };
  }));
  const valid = entries.filter(Boolean);
  if (valid.length === 0) {
    await client.query(`DELETE FROM ONLY "ProfessionSkills" WHERE "SkillId" = $1`, [skillId]);
    return;
  }
  const professionIds = valid.map(entry => entry.professionId);
  await client.query(
    `DELETE FROM ONLY "ProfessionSkills" WHERE "SkillId" = $1 AND "ProfessionId" NOT IN (SELECT * FROM unnest($2::int[]))`,
    [skillId, professionIds]
  );
  await Promise.all(valid.map(entry => client.query(
    `INSERT INTO "ProfessionSkills" ("ProfessionId", "SkillId", "Weight")
     VALUES ($1, $2, $3)
     ON CONFLICT ("ProfessionId", "SkillId") DO UPDATE SET "Weight" = $3`,
    [entry.professionId, skillId, entry.weight]
  )));
}

async function applyProfessionUnlocksChanges(client, professionId, unlocks) {
  const entries = await Promise.all((unlocks || []).map(async (entry) => {
    const skillId = await resolveSkillId(client, entry?.Skill);
    if (!skillId) return null;
    return { skillId, level: entry?.Level ?? null };
  }));
  const valid = entries.filter(Boolean);
  if (valid.length === 0) {
    await client.query(`DELETE FROM ONLY "SkillUnlocks" WHERE "ProfessionId" = $1`, [professionId]);
    return;
  }
  const skillIds = valid.map(entry => entry.skillId);
  await client.query(
    `DELETE FROM ONLY "SkillUnlocks" WHERE "ProfessionId" = $1 AND "SkillId" NOT IN (SELECT * FROM unnest($2::int[]))`,
    [professionId, skillIds]
  );
  await Promise.all(valid.map(entry => client.query(
    `INSERT INTO "SkillUnlocks" ("SkillId", "ProfessionId", "Level")
     VALUES ($1, $2, $3)
     ON CONFLICT ("SkillId", "ProfessionId") DO UPDATE SET "Level" = $3`,
    [entry.skillId, professionId, entry.level]
  )));
}

async function applySkillUnlocksChanges(client, skillId, unlocks) {
  const entries = await Promise.all((unlocks || []).map(async (entry) => {
    const professionId = await resolveProfessionId(client, entry?.Profession);
    if (!professionId) return null;
    return { professionId, level: entry?.Level ?? null };
  }));
  const valid = entries.filter(Boolean);
  if (valid.length === 0) {
    await client.query(`DELETE FROM ONLY "SkillUnlocks" WHERE "SkillId" = $1`, [skillId]);
    return;
  }
  const professionIds = valid.map(entry => entry.professionId);
  await client.query(
    `DELETE FROM ONLY "SkillUnlocks" WHERE "SkillId" = $1 AND "ProfessionId" NOT IN (SELECT * FROM unnest($2::int[]))`,
    [skillId, professionIds]
  );
  await Promise.all(valid.map(entry => client.query(
    `INSERT INTO "SkillUnlocks" ("SkillId", "ProfessionId", "Level")
     VALUES ($1, $2, $3)
     ON CONFLICT ("SkillId", "ProfessionId") DO UPDATE SET "Level" = $3`,
    [skillId, entry.professionId, entry.level]
  )));
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

// Sanitize and normalize Area shape/data before DB comparison/insertion
function sanitizeShapeAndData(props) {
  const shapeIn = props?.Shape;
  let dataRaw = props?.Data;
  if (!shapeIn || dataRaw == null) return { shape: null, data: null };

  // Parse data into an object if needed
  let parsed = null;
  if (typeof dataRaw === 'string') {
    try { parsed = JSON.parse(dataRaw); } catch { parsed = null; }
  } else if (typeof dataRaw === 'object') {
    parsed = dataRaw;
  }
  if (parsed == null) return { shape: null, data: null };

  // Normalize shape naming
  let shape = shapeIn === 'Point' ? 'Circle' : shapeIn;
  if (/^polygon?$/i.test(String(shape))) shape = 'Polygon';

  // Keep only required fields and validate
  if (shape === 'Circle') {
    const x = Number(parsed.x);
    const y = Number(parsed.y);
    const radius = Number(parsed.radius);
    if (![x, y, radius].every(Number.isFinite)) return { shape: null, data: null };
    return { shape, data: JSON.stringify({ x, y, radius }) };
  }
  if (shape === 'Rectangle') {
    const x = Number(parsed.x);
    const y = Number(parsed.y);
    const width = Number(parsed.width);
    const height = Number(parsed.height);
    if (![x, y, width, height].every(Number.isFinite)) return { shape: null, data: null };
    return { shape, data: JSON.stringify({ x, y, width, height }) };
  }
  if (shape === 'Polygon') {
    let vertices = Array.isArray(parsed.vertices) ? parsed.vertices.map(Number) : null;
    if (!vertices || vertices.some(v => !Number.isFinite(v))) return { shape: null, data: null };
    // Ensure even length
    if (vertices.length % 2 !== 0) vertices = vertices.slice(0, vertices.length - 1);
    const pointCount = Math.floor(vertices.length / 2);
    if (pointCount < 3) return { shape: null, data: null };
    // Ensure closing point present (tolerance for rounding errors)
    const x1 = vertices[0], y1 = vertices[1];
    const lastX = vertices[vertices.length - 2], lastY = vertices[vertices.length - 1];
    if (Math.abs(x1 - lastX) < 0.01 && Math.abs(y1 - lastY) < 0.01) {
      // Already closed — snap last to exactly match first
      vertices[vertices.length - 2] = x1;
      vertices[vertices.length - 1] = y1;
    } else {
      vertices = [...vertices, x1, y1];
    }
    if (vertices.length < 8) return { shape: null, data: null }; // 3 points + closing
    return { shape: 'Polygon', data: JSON.stringify({ vertices }) };
  }

  // Unknown shape -> invalid
  return { shape: null, data: null };
}

async function applyMobSpawnChanges(client, mobId, spawns) {
  // Get planet ID for this mob
  const planetResult = await client.query(`SELECT "PlanetId" FROM "Mobs" WHERE "Id" = $1`, [mobId]);
  const planetId = planetResult.rows[0]?.PlanetId;

  // Get existing spawns and areas for this mob
  const existingSpawns = await client.query(`
  SELECT DISTINCT "MobSpawns"."LocationId", "Areas"."Shape", "Areas"."Data", "Locations"."Altitude"
  FROM "MobSpawns"
  INNER JOIN "Locations" ON "MobSpawns"."LocationId" = "Locations"."Id"
  INNER JOIN "Areas" ON "MobSpawns"."LocationId" = "Areas"."LocationId"
  INNER JOIN "MobSpawnMaturities" ON "MobSpawns"."LocationId" = "MobSpawnMaturities"."LocationId"
  INNER JOIN "MobMaturities" ON "MobSpawnMaturities"."MaturityId" = "MobMaturities"."Id"
    WHERE "MobMaturities"."MobId" = $1
  `, [mobId]);

  // Process spawns and match with existing areas
  const processedSpawns = await Promise.all(spawns.map(async (spawn, index) => {
    try {
      if (!spawn.Properties.Shape || !spawn.Properties.Data) {
        console.warn(`Skipping spawn ${index}: missing Shape or Data`, spawn.Properties);
        throw new Error(`Spawn ${index} is missing Shape or Data`);
      }

      const { shape, data } = sanitizeShapeAndData(spawn.Properties);
      if (!shape || !data) {
        console.warn(`Skipping spawn ${index}: invalid Shape/Data`, spawn.Properties);
        throw new Error(`Spawn ${index} is invalid Shape/Data`);
      }
      const altitude = spawn.Properties.Coordinates?.Altitude || 0;

      // Derive a human-friendly name used for Areas and MobSpawns when none is provided
      let derivedName = spawn.Properties.Name;
      if (!derivedName && spawn.Maturities && spawn.Maturities.length > 0) {
        const mobGroups = {};
        spawn.Maturities.forEach(maturity => {
          const mobName = maturity?.Maturity?.Mob?.Name;
          const maturityName = maturity?.Maturity?.Name;
          if (mobName) {
            if (!mobGroups[mobName]) mobGroups[mobName] = [];
            if (maturityName) mobGroups[mobName].push(maturityName);
          }
        });
        const mobParts = Object.entries(mobGroups).map(([mobName, maturities]) =>
          maturities.length > 0 ? `${mobName} - ${maturities.join('/')}` : mobName
        );
        derivedName = mobParts.join(', ');
      }
      if (!derivedName) derivedName = `Spawn Area ${index + 1}`;

      // Check if there's an existing area with matching Shape, Data, and Altitude
      const matchingArea = existingSpawns.rows.find(existing => 
        existing.Shape === shape && 
        existing.Data === data && 
        Number(existing.Altitude) === altitude
      );

      let areaId;

      if (matchingArea) {
        // Use existing location
        areaId = matchingArea.LocationId;

        // Update the spawn properties that might have changed
        await client.query(`
          UPDATE "MobSpawns"
          SET "Density" = $1, "IsShared" = $2, "IsEvent" = $3, "Name" = $4, "Description" = $5, "RecurringEventId" = $6
          WHERE "LocationId" = $7
        `, [
          spawn.Properties.Density || 3,
          spawn.Properties.IsShared ? 1 : 0,
          spawn.Properties.IsEvent ? 1 : 0,
          derivedName || null,
          spawn.Properties.Description || null,
          spawn.Properties.RecurringEventId ?? null,
          areaId
        ]);
      } else {
        // Use derivedName for Location name when creating a new Location
        const areaName = derivedName;

        // Create new Location first
        const longitude = spawn.Properties.Coordinates?.Longitude || null;
        const latitude = spawn.Properties.Coordinates?.Latitude || null;
        const locationResult = await client.query(`
          INSERT INTO "Locations" ("Name", "Type", "Longitude", "Latitude", "Altitude", "PlanetId")
          VALUES ($1, $2, $3, $4, $5, $6)
          RETURNING "Id"
        `, [
          areaName,
          'Area',
          longitude,
          latitude,
          altitude,
          planetId
        ]);

        areaId = locationResult.rows[0].Id;

        // Create Area extension record
        await client.query(`
          INSERT INTO "Areas" ("LocationId", "Type", "Shape", "Data")
          VALUES ($1, $2, $3, $4)
          ON CONFLICT ("LocationId") DO UPDATE SET
            "Type" = EXCLUDED."Type",
            "Shape" = EXCLUDED."Shape",
            "Data" = EXCLUDED."Data"
        `, [
          areaId,
          'MobArea',
          shape,
          data
        ]);

        // Create new MobSpawn (LocationId is the PK and FK to Locations)
        await client.query(`
          INSERT INTO "MobSpawns" ("LocationId", "Density", "IsShared", "IsEvent", "RecurringEventId")
          VALUES ($1, $2, $3, $4, $5)
          ON CONFLICT ("LocationId") DO UPDATE SET
            "Density" = EXCLUDED."Density",
            "IsShared" = EXCLUDED."IsShared",
            "IsEvent" = EXCLUDED."IsEvent",
            "RecurringEventId" = EXCLUDED."RecurringEventId"
        `, [
          areaId,
          spawn.Properties.Density || 3,
          spawn.Properties.IsShared ? 1 : 0,
          spawn.Properties.IsEvent ? 1 : 0,
          spawn.Properties.RecurringEventId ?? null
        ]);
      }

      return { ...spawn, LocationId: areaId };
    } catch (error) {
      console.error(`Error processing spawn ${index}:`, error, spawn);
      return null;
    }
  }));

  const validSpawns = processedSpawns.filter(s => s !== null);

  // Delete spawns and locations that are no longer in the new data
  const usedLocationIds = validSpawns.map(s => s.LocationId);
  const locationsToDelete = existingSpawns.rows.filter(existing =>
    !usedLocationIds.includes(existing.LocationId)
  );

  for (const locationToDelete of locationsToDelete) {
    // Delete in order: MobSpawnMaturities, MobSpawns, then Locations (which cascades to Areas)
    await client.query(`DELETE FROM "MobSpawnMaturities" WHERE "LocationId" = $1`, [locationToDelete.LocationId]);
    await client.query(`DELETE FROM "MobSpawns" WHERE "LocationId" = $1`, [locationToDelete.LocationId]);
    await client.query(`DELETE FROM "Locations" WHERE "Id" = $1`, [locationToDelete.LocationId]);
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

      // Always resolve by name - direct Ids from change data can be stale after renames
      const result = await client.query(`
        SELECT "MobMaturities"."Id"
        FROM ONLY "MobMaturities"
        INNER JOIN "Mobs" ON "MobMaturities"."MobId" = "Mobs"."Id"
        WHERE "Mobs"."Name" = $1 AND "MobMaturities"."Name" = $2
      `, [maturity.Maturity.Mob.Name, maturity.Maturity.Name]);

      return result.rows[0] ? { ...maturity, MaturityId: result.rows[0].Id } : null;
    }));

    const validMaturities = maturitiesWithIds.filter(m => m !== null);

    // Delete old maturities and insert new ones
    if (validMaturities.length === 0) {
      // Explicitly clear all maturities if none are valid/mapped
      await client.query(`DELETE FROM "MobSpawnMaturities" WHERE "LocationId" = $1`, [spawn.LocationId]);
      return;
    }
    await Promise.all([
      client.query(`DELETE FROM "MobSpawnMaturities" WHERE "LocationId" = $1 AND "MaturityId" NOT IN (SELECT * FROM unnest($2::int[]))`,
        [spawn.LocationId, validMaturities.map(m => m.MaturityId)]),
      ...validMaturities.map(maturity =>
        client.query(`
          INSERT INTO "MobSpawnMaturities" ("LocationId", "MaturityId", "IsRare")
          VALUES ($1, $2, $3)
          ON CONFLICT ("LocationId", "MaturityId") DO UPDATE SET "IsRare" = $3
        `, [spawn.LocationId, maturity.MaturityId, maturity.IsRare ? 1 : 0])
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


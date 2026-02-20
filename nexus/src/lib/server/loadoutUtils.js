// @ts-nocheck
const MAX_LOADOUT_BYTES = 50000;
const MAX_SETS_PER_SECTION = 10;
const MAX_IMPORT_BYTES = 1024 * 1024; // 1MB per import request payload

function clampNumber(value, fallback = 0, min = null, max = null) {
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (!Number.isFinite(num)) return fallback;
  if (min != null && num < min) return min;
  if (max != null && num > max) return max;
  return num;
}

function sanitizeString(value, fallback = null, maxLen = 200) {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  if (!trimmed) return fallback;
  return trimmed.slice(0, maxLen);
}

function sanitizeNameObject(value) {
  const name = sanitizeString(value?.Name ?? value, null, 200);
  return name ? { Name: name } : null;
}

export function createEmptyLoadout() {
  const newArmorObject = () => ({
    Name: null,
    Plate: null
  });

  return {
    Id: null,
    Name: 'New Loadout',
    Properties: {
      BonusDamage: 0,
      BonusCritChance: 0,
      BonusCritDamage: 0,
      BonusReload: 0
    },
    Gear: {
      Weapon: {
        Name: null,
        Amplifier: null,
        Scope: null,
        Sight: null,
        Absorber: null,
        Implant: null,
        Matrix: null,
        Enhancers: {
          Damage: 0,
          Accuracy: 0,
          Range: 0,
          Economy: 0,
          SkillMod: 0
        }
      },
      Armor: {
        SetName: null,
        PlateName: null,
        Head: newArmorObject(),
        Torso: newArmorObject(),
        Arms: newArmorObject(),
        Hands: newArmorObject(),
        Legs: newArmorObject(),
        Shins: newArmorObject(),
        Feet: newArmorObject(),
        Enhancers: {
          Defense: 0,
          Durability: 0
        },
        ManageIndividual: false
      },
      Healing: {
        Name: null,
        Enhancers: {
          Heal: 0,
          Economy: 0,
          SkillMod: 0
        }
      },
      Clothing: [],
      Consumables: [],
      Pet: {
        Name: null,
        Effect: null
      }
    },
    Sets: null,
    Skill: {
      Hit: 200,
      Dmg: 200,
      Heal: 200
    },
    Markup: {
      Weapon: 100,
      Ammo: 100,
      Amplifier: 100,
      Absorber: 100,
      Scope: 100,
      Sight: 100,
      ScopeSight: 100,
      Matrix: 100,
      Implant: 100,
      ArmorSet: 100,
      PlateSet: 100,
      Armors: {
        Head: 100,
        Torso: 100,
        Arms: 100,
        Hands: 100,
        Legs: 100,
        Shins: 100,
        Feet: 100
      },
      Plates: {
        Head: 100,
        Torso: 100,
        Arms: 100,
        Hands: 100,
        Legs: 100,
        Shins: 100,
        Feet: 100
      },
      HealingTool: 100
    }
  };
}

export function sanitizeLoadoutData(input) {
  const base = createEmptyLoadout();
  const sanitized = JSON.parse(JSON.stringify(base));

  if (!input || typeof input !== 'object') {
    return sanitized;
  }

  sanitized.Id = sanitizeString(input.Id, sanitized.Id, 64);
  sanitized.Name = sanitizeString(input.Name, sanitized.Name, 120) || sanitized.Name;

  sanitized.Properties.BonusDamage = clampNumber(input?.Properties?.BonusDamage, 0, -1000, 1000);
  sanitized.Properties.BonusCritChance = clampNumber(input?.Properties?.BonusCritChance, 0, -1000, 1000);
  sanitized.Properties.BonusCritDamage = clampNumber(input?.Properties?.BonusCritDamage, 0, -1000, 1000);
  sanitized.Properties.BonusReload = clampNumber(input?.Properties?.BonusReload, 0, -1000, 1000);

  sanitized.Skill.Hit = clampNumber(input?.Skill?.Hit, 200, 0, 10000);
  sanitized.Skill.Dmg = clampNumber(input?.Skill?.Dmg, 200, 0, 10000);
  sanitized.Skill.Heal = clampNumber(input?.Skill?.Heal, 200, 0, 10000);

  sanitized.Gear.Weapon.Name = sanitizeString(input?.Gear?.Weapon?.Name, null, 200);
  sanitized.Gear.Weapon.Amplifier = sanitizeNameObject(input?.Gear?.Weapon?.Amplifier);
  sanitized.Gear.Weapon.Scope = sanitizeNameObject(input?.Gear?.Weapon?.Scope);
  sanitized.Gear.Weapon.Sight = sanitizeNameObject(input?.Gear?.Weapon?.Sight);
  sanitized.Gear.Weapon.Absorber = sanitizeNameObject(input?.Gear?.Weapon?.Absorber);
  sanitized.Gear.Weapon.Implant = sanitizeNameObject(input?.Gear?.Weapon?.Implant);
  sanitized.Gear.Weapon.Matrix = sanitizeNameObject(input?.Gear?.Weapon?.Matrix);
  sanitized.Gear.Weapon.Enhancers.Damage = clampNumber(input?.Gear?.Weapon?.Enhancers?.Damage, 0, 0, 10);
  sanitized.Gear.Weapon.Enhancers.Accuracy = clampNumber(input?.Gear?.Weapon?.Enhancers?.Accuracy, 0, 0, 10);
  sanitized.Gear.Weapon.Enhancers.Range = clampNumber(input?.Gear?.Weapon?.Enhancers?.Range, 0, 0, 10);
  sanitized.Gear.Weapon.Enhancers.Economy = clampNumber(input?.Gear?.Weapon?.Enhancers?.Economy, 0, 0, 10);
  sanitized.Gear.Weapon.Enhancers.SkillMod = clampNumber(input?.Gear?.Weapon?.Enhancers?.SkillMod, 0, 0, 10);

  sanitized.Gear.Armor.ManageIndividual = !!input?.Gear?.Armor?.ManageIndividual;
  sanitized.Gear.Armor.SetName = sanitizeString(input?.Gear?.Armor?.SetName, null, 200);
  sanitized.Gear.Armor.PlateName = sanitizeString(input?.Gear?.Armor?.PlateName, null, 200);
  sanitized.Gear.Armor.Enhancers.Defense = clampNumber(input?.Gear?.Armor?.Enhancers?.Defense, 0, 0, 10);
  sanitized.Gear.Armor.Enhancers.Durability = clampNumber(input?.Gear?.Armor?.Enhancers?.Durability, 0, 0, 10);

  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];
  armorSlots.forEach(slot => {
    sanitized.Gear.Armor[slot].Name = sanitizeString(input?.Gear?.Armor?.[slot]?.Name, null, 200);
    sanitized.Gear.Armor[slot].Plate = sanitizeNameObject(input?.Gear?.Armor?.[slot]?.Plate);
  });

  sanitized.Gear.Clothing = Array.isArray(input?.Gear?.Clothing)
    ? input.Gear.Clothing
      .map(item => ({
        Slot: sanitizeString(item?.Slot, null, 60),
        Side: sanitizeString(item?.Side, null, 20),
        Name: sanitizeString(item?.Name ?? item, null, 200)
      }))
      .filter(item => item.Name && item.Slot)
    : [];

  sanitized.Gear.Consumables = Array.isArray(input?.Gear?.Consumables)
    ? input.Gear.Consumables.map(sanitizeNameObject).filter(Boolean)
    : [];

  sanitized.Gear.Healing = {
    Name: sanitizeString(input?.Gear?.Healing?.Name, null, 200),
    Enhancers: {
      Heal: clampNumber(input?.Gear?.Healing?.Enhancers?.Heal, 0, 0, 10),
      Economy: clampNumber(input?.Gear?.Healing?.Enhancers?.Economy, 0, 0, 10),
      SkillMod: clampNumber(input?.Gear?.Healing?.Enhancers?.SkillMod, 0, 0, 10)
    }
  };

  sanitized.Gear.Pet = {
    Name: sanitizeString(input?.Gear?.Pet?.Name, null, 200),
    Effect: sanitizeString(input?.Gear?.Pet?.Effect, null, 200)
  };

  sanitized.Markup.Weapon = clampNumber(input?.Markup?.Weapon, 100, 0, 100000);
  sanitized.Markup.Ammo = clampNumber(input?.Markup?.Ammo, 100, 0, 100000);
  sanitized.Markup.Amplifier = clampNumber(input?.Markup?.Amplifier, 100, 0, 100000);
  sanitized.Markup.Absorber = clampNumber(input?.Markup?.Absorber, 100, 0, 100000);
  sanitized.Markup.Scope = clampNumber(input?.Markup?.Scope, 100, 0, 100000);
  sanitized.Markup.Sight = clampNumber(input?.Markup?.Sight, 100, 0, 100000);
  sanitized.Markup.ScopeSight = clampNumber(input?.Markup?.ScopeSight, 100, 0, 100000);
  sanitized.Markup.Matrix = clampNumber(input?.Markup?.Matrix, 100, 0, 100000);
  sanitized.Markup.Implant = clampNumber(input?.Markup?.Implant, 100, 0, 100000);
  sanitized.Markup.ArmorSet = clampNumber(input?.Markup?.ArmorSet, 100, 0, 100000);
  sanitized.Markup.PlateSet = clampNumber(input?.Markup?.PlateSet, 100, 0, 100000);

  armorSlots.forEach(slot => {
    sanitized.Markup.Armors[slot] = clampNumber(input?.Markup?.Armors?.[slot], 100, 0, 100000);
    sanitized.Markup.Plates[slot] = clampNumber(input?.Markup?.Plates?.[slot], 100, 0, 100000);
  });

  sanitized.Markup.HealingTool = clampNumber(input?.Markup?.HealingTool, 100, 0, 100000);

  // Sanitize Sets (multi-set support)
  sanitized.Sets = sanitizeSets(input?.Sets);

  return sanitized;
}

function sanitizeWeaponGear(weapon) {
  return {
    Name: sanitizeString(weapon?.Name, null, 200),
    Amplifier: sanitizeNameObject(weapon?.Amplifier),
    Scope: sanitizeNameObject(weapon?.Scope),
    Sight: sanitizeNameObject(weapon?.Sight),
    Absorber: sanitizeNameObject(weapon?.Absorber),
    Implant: sanitizeNameObject(weapon?.Implant),
    Matrix: sanitizeNameObject(weapon?.Matrix),
    Enhancers: {
      Damage: clampNumber(weapon?.Enhancers?.Damage, 0, 0, 10),
      Accuracy: clampNumber(weapon?.Enhancers?.Accuracy, 0, 0, 10),
      Range: clampNumber(weapon?.Enhancers?.Range, 0, 0, 10),
      Economy: clampNumber(weapon?.Enhancers?.Economy, 0, 0, 10),
      SkillMod: clampNumber(weapon?.Enhancers?.SkillMod, 0, 0, 10)
    }
  };
}

function sanitizeWeaponMarkup(markup) {
  return {
    Weapon: clampNumber(markup?.Weapon, 100, 0, 100000),
    Ammo: clampNumber(markup?.Ammo, 100, 0, 100000),
    Amplifier: clampNumber(markup?.Amplifier, 100, 0, 100000),
    Absorber: clampNumber(markup?.Absorber, 100, 0, 100000),
    Scope: clampNumber(markup?.Scope, 100, 0, 100000),
    Sight: clampNumber(markup?.Sight, 100, 0, 100000),
    ScopeSight: clampNumber(markup?.ScopeSight, 100, 0, 100000),
    Matrix: clampNumber(markup?.Matrix, 100, 0, 100000),
    Implant: clampNumber(markup?.Implant, 100, 0, 100000)
  };
}

function sanitizeArmorGear(armor) {
  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];
  const result = {
    SetName: sanitizeString(armor?.SetName, null, 200),
    PlateName: sanitizeString(armor?.PlateName, null, 200),
    Enhancers: {
      Defense: clampNumber(armor?.Enhancers?.Defense, 0, 0, 10),
      Durability: clampNumber(armor?.Enhancers?.Durability, 0, 0, 10)
    },
    ManageIndividual: !!armor?.ManageIndividual
  };
  armorSlots.forEach(slot => {
    result[slot] = {
      Name: sanitizeString(armor?.[slot]?.Name, null, 200),
      Plate: sanitizeNameObject(armor?.[slot]?.Plate)
    };
  });
  return result;
}

function sanitizeArmorMarkup(markup) {
  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];
  const result = {
    ArmorSet: clampNumber(markup?.ArmorSet, 100, 0, 100000),
    PlateSet: clampNumber(markup?.PlateSet, 100, 0, 100000),
    Armors: {},
    Plates: {}
  };
  armorSlots.forEach(slot => {
    result.Armors[slot] = clampNumber(markup?.Armors?.[slot], 100, 0, 100000);
    result.Plates[slot] = clampNumber(markup?.Plates?.[slot], 100, 0, 100000);
  });
  return result;
}

function sanitizeHealingGear(healing) {
  return {
    Name: sanitizeString(healing?.Name, null, 200),
    Enhancers: {
      Heal: clampNumber(healing?.Enhancers?.Heal, 0, 0, 10),
      Economy: clampNumber(healing?.Enhancers?.Economy, 0, 0, 10),
      SkillMod: clampNumber(healing?.Enhancers?.SkillMod, 0, 0, 10)
    }
  };
}

function sanitizeHealingMarkup(markup) {
  return {
    HealingTool: clampNumber(markup?.HealingTool, 100, 0, 100000)
  };
}

function sanitizeAccessoriesGear(gear) {
  const clothing = Array.isArray(gear?.Clothing)
    ? gear.Clothing
      .map(item => ({
        Slot: sanitizeString(item?.Slot, null, 60),
        Side: sanitizeString(item?.Side, null, 20),
        Name: sanitizeString(item?.Name ?? item, null, 200)
      }))
      .filter(item => item.Name && item.Slot)
    : [];

  const consumables = Array.isArray(gear?.Consumables)
    ? gear.Consumables.map(sanitizeNameObject).filter(Boolean)
    : [];

  const pet = {
    Name: sanitizeString(gear?.Pet?.Name, null, 200),
    Effect: sanitizeString(gear?.Pet?.Effect, null, 200)
  };

  return { Clothing: clothing, Consumables: consumables, Pet: pet };
}

function sanitizeSetEntry(entry, sanitizeGearFn, sanitizeMarkupFn) {
  if (!entry || typeof entry !== 'object') return null;
  const result = {
    id: sanitizeString(entry.id, null, 64),
    name: sanitizeString(entry.name, 'Unnamed Set', 120),
    isDefault: !!entry.isDefault,
    gear: sanitizeGearFn(entry.gear)
  };
  if (sanitizeMarkupFn) {
    result.markup = sanitizeMarkupFn(entry.markup);
  }
  return result;
}

function sanitizeSectionSets(arr, sanitizeGearFn, sanitizeMarkupFn) {
  if (!Array.isArray(arr) || arr.length === 0) return null;
  const sets = arr
    .slice(0, MAX_SETS_PER_SECTION)
    .map(entry => sanitizeSetEntry(entry, sanitizeGearFn, sanitizeMarkupFn))
    .filter(Boolean);
  if (sets.length === 0) return null;
  // Ensure exactly one default
  const hasDefault = sets.some(s => s.isDefault);
  if (!hasDefault) sets[0].isDefault = true;
  return sets;
}

function sanitizeSets(sets) {
  if (!sets || typeof sets !== 'object') return null;

  const weapon = sanitizeSectionSets(sets.Weapon, sanitizeWeaponGear, sanitizeWeaponMarkup);
  const armor = sanitizeSectionSets(sets.Armor, sanitizeArmorGear, sanitizeArmorMarkup);
  const healing = sanitizeSectionSets(sets.Healing, sanitizeHealingGear, sanitizeHealingMarkup);
  const accessories = sanitizeSectionSets(sets.Accessories, sanitizeAccessoriesGear, null);

  if (!weapon && !armor && !healing && !accessories) return null;

  return {
    Weapon: weapon,
    Armor: armor,
    Healing: healing,
    Accessories: accessories
  };
}

export function getPayloadSizeBytes(payload) {
  try {
    return new TextEncoder().encode(JSON.stringify(payload)).length;
  } catch (err) {
    return Number.MAX_SAFE_INTEGER;
  }
}

export { MAX_LOADOUT_BYTES };
export { MAX_IMPORT_BYTES };

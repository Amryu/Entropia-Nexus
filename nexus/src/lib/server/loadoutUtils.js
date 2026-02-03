// @ts-nocheck
const MAX_LOADOUT_BYTES = 20000;
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
      Clothing: [],
      Consumables: [],
      Pet: {
        Name: null,
        Effect: null
      }
    },
    Skill: {
      Hit: 200,
      Dmg: 200
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
      }
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

  return sanitized;
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

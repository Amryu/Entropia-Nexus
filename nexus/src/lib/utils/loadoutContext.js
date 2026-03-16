// @ts-nocheck
/**
 * Shared utility for building the evaluation context from raw entity data.
 * Used by both the loadout page and mob page (cost-to-kill columns).
 */

const ARMOR_SLOTS = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];

function alphabeticalSort(a, b) {
  if (a?.Name === null) return 1;
  if (b?.Name === null) return -1;
  return a.Name.localeCompare(b.Name, undefined, { numeric: true });
}

/**
 * Get a display name for a loadout, using weapon/armor names when the
 * loadout still has the default "New Loadout" name.
 *
 * @param {object} loadout - Loadout data object
 * @returns {string}
 */
export function getLoadoutDisplayName(loadout) {
  if (!loadout) return 'Untitled';
  const name = loadout.Name || loadout.name;
  if (name && name !== 'New Loadout') return name;
  const weaponName = loadout.Gear?.Weapon?.Name;
  const armorName = loadout.Gear?.Armor?.SetName;
  if (weaponName && armorName) return `${weaponName} (${armorName})`;
  if (weaponName) return weaponName;
  return name || 'New Loadout';
}

/**
 * Process raw entity data (from loadLoadoutEntities) into the context shape
 * required by evaluateLoadout().
 *
 * @param {object} entities - Raw entities from loadLoadoutEntities()
 * @returns {object} Context object for evaluateLoadout()
 */
export function buildEvalContext(entities) {
  const rawWeapons = entities.weapons || [];
  const rawAmplifiers = entities.weaponAmplifiers || [];
  const rawVisionAttachments = entities.weaponVisionAttachments || [];

  return {
    armorSlots: ARMOR_SLOTS,
    weapons: rawWeapons.filter(x => x.Properties?.Class !== 'Attached' && x.Properties?.Class !== 'Stationary').sort(alphabeticalSort),
    amplifiers: rawAmplifiers.filter(x => x.Properties?.Type !== 'Matrix').sort(alphabeticalSort),
    scopes: rawVisionAttachments.filter(x => x.Properties?.Type === 'Scope').sort(alphabeticalSort),
    sights: rawVisionAttachments.filter(x => x.Properties?.Type === 'Sight').sort(alphabeticalSort),
    absorbers: (entities.absorbers || []).sort(alphabeticalSort),
    matrices: rawAmplifiers.filter(x => x.Properties?.Type === 'Matrix').sort(alphabeticalSort),
    implants: (entities.mindforceImplants || []).sort(alphabeticalSort),
    armorSets: (entities.armorSets || []).sort(alphabeticalSort),
    armors: (entities.armors || []).sort(alphabeticalSort),
    armorPlatings: (entities.armorPlatings || []).sort(alphabeticalSort),
    clothing: (entities.clothings || []).sort(alphabeticalSort),
    pets: (entities.pets || []).sort(alphabeticalSort),
    stimulants: (entities.consumables || []).sort(alphabeticalSort),
    medicalTools: (entities.medicalTools || []).sort(alphabeticalSort),
    medicalChips: (entities.medicalChips || []).sort(alphabeticalSort),
  };
}

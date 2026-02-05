// Utility to decide which items are non-stackable for MU formatting
// Extend this list/rules as needed based on item details
/**
 * @param {any} item
 */
export function isNonStackable(item) {
  // Items with condition/TT that can be damaged
  const t = item?.Properties?.Type || item?.type || '';
  return [
    'Weapon', 'Armor', 'Vehicle',
    'WeaponAmplifier', 'WeaponVisionAttachment',
    'Finder', 'FinderAmplifier', 'Excavator', 'Refiner', 'Scanner',
    'TeleportationChip', 'EffectChip', 'MedicalChip',
    'MiscTool', 'MedicalTool', 'MindforceImplant', 'Pet'
  ].includes(t);
}

// New alias for future condition-based logic. Keep current behavior identical.
/**
 * @param {any} item
 */
export function hasCondition(item) {
  return isNonStackable(item);
}

// Build display text for stacks and markup
/**
 * @param {any} entry
 * @param {any} item
 */
export function buildStackMuDisplay(entry, item) {
  const stack = Number(entry.StackSize ?? entry.stack_size ?? 0);
  const mu = Number(entry.Markup ?? entry.markup ?? 0);
  const stackText = stack > 0 ? `stacks: ${stack}` : '';
  let muText = '';
  if (!Number.isNaN(mu) && mu > 0) {
    muText = isNonStackable(item) ? `+${mu}` : `${mu.toFixed(0)}%`;
  }
  return { stackText, muText };
}

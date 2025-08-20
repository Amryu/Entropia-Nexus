// Utility functions for order dialog logic
import { hasItemTag } from '$lib/util.js';
import { hasCondition } from '$lib/shopUtils';

const tierableTypes = new Set([
  'Weapon',
  'Armor',
  'Finder',
  'Excavator',
  'MedicalTool',
]);

export function isBlueprint(item: any): boolean {
  return (
    item?.Properties?.Type === 'Blueprint' ||
    item?.t === 'Blueprint'
  );
}

export function isItemTierable(item: any): boolean {
  const type = item?.Properties?.Type || item?.t || null;
  return tierableTypes.has(type);
}

export function isLimited(item: any): boolean {
  const name = item?.n || item?.Name || '';
  return hasItemTag(name, 'L');
}

export function itemHasCondition(item: any): boolean {
  if (isBlueprint(item) && isLimited(item)) return false;
  if (isBlueprint(item)) return true;
  return hasCondition(item);
}

export function getMaxTT(item: any): number | null {
  return item?.Properties?.Economy?.MaxTT ?? null;
}

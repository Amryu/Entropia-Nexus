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
  const type = item?.Properties?.Type ?? item?.Type ?? item?.t;
  return type === 'Blueprint';
}

export function isItemTierable(item: any): boolean {
  const type = item?.Properties?.Type ?? item?.Type ?? item?.t;
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
  return item?.Properties?.Economy?.MaxTT ?? item?.MaxTT ?? item?.Value ?? null;
}

export function isItemStackable(item: any): boolean {
  const type = item?.Properties?.Type ?? item?.Type ?? item?.t;
  return type === 'Material'
    || type === 'Consumable'
    || type === 'Capsule'
    || type === 'Enhancer'
    || (type === 'Blueprint' && isLimited(item));
}

export function isPercentMarkup(item: any): boolean {
  return isItemStackable(item) || (itemHasCondition(item) && isLimited(item));
}

export function isAbsoluteMarkup(item: any): boolean {
  return !isPercentMarkup(item);
}

/**
 * Format a markup value for display.
 * - Percentage: thousands separators, 4 decimals if < 105%, scientific notation if >= 100,000%
 * - Absolute: thousands separators, 4 decimals if < +5
 */
export function formatMarkupValue(value: any, absolute: boolean): string {
  if (value == null || !isFinite(value)) return 'N/A';
  const v = Number(value);
  const MIN_DECIMALS = 2;
  const MAX_DECIMALS = 4;
  // Use up to 4 decimals in the precision range, but only if the extra digits are non-zero
  function smartDecimals(val: number, usePrecision: boolean): number {
    if (!usePrecision) return MIN_DECIMALS;
    const rounded2 = Math.round(val * 100) / 100;
    if (Math.abs(val - rounded2) < 1e-9) return MIN_DECIMALS;
    const rounded3 = Math.round(val * 1000) / 1000;
    if (Math.abs(val - rounded3) < 1e-9) return 3;
    return MAX_DECIMALS;
  }
  if (absolute) {
    const d = smartDecimals(v, v < 5);
    return `+${v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}`;
  }
  if (v >= 100000) return `${v.toExponential(2)}%`;
  const d = smartDecimals(v, v < 105);
  return `${v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}%`;
}

/**
 * Format a markup value based on item type detection.
 */
export function formatMarkupForItem(value: any, item: any): string {
  return formatMarkupValue(value, isAbsoluteMarkup(item));
}

/**
 * Format a PED value for display.
 * - Thousands separators, smart decimals (2-4), scientific notation >= 1,000,000
 */
export function formatPedValue(value: any): string {
  if (value == null || !isFinite(value)) return 'N/A';
  const v = Number(value);
  const MIN_DECIMALS = 2;
  const MAX_DECIMALS = 4;
  function smartDecimals(val: number, usePrecision: boolean): number {
    if (!usePrecision) return MIN_DECIMALS;
    const rounded2 = Math.round(val * 100) / 100;
    if (Math.abs(val - rounded2) < 1e-9) return MIN_DECIMALS;
    const rounded3 = Math.round(val * 1000) / 1000;
    if (Math.abs(val - rounded3) < 1e-9) return 3;
    return MAX_DECIMALS;
  }
  if (Math.abs(v) >= 1000000) return `${v.toExponential(2)} PED`;
  const d = smartDecimals(v, Math.abs(v) < 5);
  return `${v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })} PED`;
}

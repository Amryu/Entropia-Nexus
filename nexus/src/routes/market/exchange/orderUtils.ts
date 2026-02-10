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
  return item?.Properties?.Economy?.MaxTT ?? item?.MaxTT ?? item?.Value ?? item?.v ?? null;
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

const MIN_DECIMALS = 2;
const MAX_DECIMALS = 4;

/**
 * Determine how many decimal places to show.
 * For very small values (0 < |val| < 0.01), extends up to 4 decimals.
 * Returns -1 if scientific notation should be used (value needs 5+ decimals).
 */
function smartDecimals(val: number, usePrecision: boolean): number {
  const absVal = Math.abs(val);
  // For very small values, extend decimals to show the first significant digit
  if (absVal > 0 && absVal < 0.01) {
    let d = MIN_DECIMALS;
    while (d < MAX_DECIMALS && absVal * Math.pow(10, d) < 1) d++;
    // If 4 decimals still can't show a significant digit, signal scientific notation
    if (d >= MAX_DECIMALS && absVal * Math.pow(10, MAX_DECIMALS) < 1) return -1;
    return d;
  }
  if (!usePrecision) return MIN_DECIMALS;
  const rounded2 = Math.round(val * 100) / 100;
  if (Math.abs(val - rounded2) < 1e-9) return MIN_DECIMALS;
  const rounded3 = Math.round(val * 1000) / 1000;
  if (Math.abs(val - rounded3) < 1e-9) return 3;
  return MAX_DECIMALS;
}

function formatLocale(v: number, decimals: number): string {
  return v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatNum(v: number, usePrecision: boolean): string {
  const d = smartDecimals(v, usePrecision);
  if (d === -1) return v.toExponential(2);
  return formatLocale(v, d);
}

/**
 * Format a markup value for display.
 * - Percentage: thousands separators, up to 4 decimals if < 105%, scientific notation if >= 100,000%
 * - Absolute: thousands separators, up to 4 decimals, scientific notation for very small values
 */
export function formatMarkupValue(value: any, absolute: boolean): string {
  if (value == null || !isFinite(value)) return 'N/A';
  const v = Number(value);
  if (absolute) {
    return `+${formatNum(v, v < 5)}`;
  }
  if (v >= 100000) return `${v.toExponential(2)}%`;
  return `${formatNum(v, v < 105)}%`;
}

/**
 * Format a markup value based on item type detection.
 */
export function formatMarkupForItem(value: any, item: any): string {
  return formatMarkupValue(value, isAbsoluteMarkup(item));
}

/**
 * Format a PED value for display (with " PED" suffix).
 * Up to 4 decimals for small values, scientific notation beyond that.
 */
export function formatPedValue(value: any): string {
  if (value == null || !isFinite(value)) return 'N/A';
  const v = Number(value);
  return `${formatNum(v, Math.abs(v) < 5)} PED`;
}

/**
 * Format a PED value without suffix (for use in templates that add " PED" separately).
 */
export function formatPedRaw(value: any): string {
  if (value == null || !isFinite(value)) return 'N/A';
  return formatNum(Number(value), Math.abs(Number(value)) < 5);
}

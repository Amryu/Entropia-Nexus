// Utility functions for order dialog logic
import { hasItemTag } from '$lib/util.js';
import { hasCondition } from '$lib/shopUtils';
import { STACKABLE_TYPES, TIERABLE_TYPES, ABSOLUTE_MARKUP_MATERIAL_TYPES } from '$lib/common/itemTypes.js';

export function isBlueprint(item: any): boolean {
  const type = item?.Properties?.Type ?? item?.Type ?? item?.t;
  return type === 'Blueprint';
}

export function isItemTierable(item: any): boolean {
  const type = item?.Properties?.Type ?? item?.Type ?? item?.t;
  return TIERABLE_TYPES.has(type);
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

/** Default MaxTT for pets when nutrio capacity is unknown (PED) */
export const PET_DEFAULT_MAX_TT = 100;

export function getMaxTT(item: any): number | null {
  const tt = item?.Properties?.Economy?.MaxTT ?? item?.MaxTT ?? item?.Value ?? item?.v ?? null;
  if (tt != null) return tt;
  // Pets: MaxTT = nutrio capacity (stored in cents, convert to PED)
  if (isPet(item)) {
    const nutrio = item?.Properties?.NutrioCapacity;
    return nutrio != null ? nutrio / 100 : PET_DEFAULT_MAX_TT;
  }
  return null;
}

export function isItemStackable(item: any): boolean {
  const type = item?.Properties?.Type ?? item?.Type ?? item?.t;
  if (STACKABLE_TYPES.has(type)) return true;
  if (type === 'Blueprint' && isLimited(item)) return true;
  return false;
}

export function isPercentMarkup(item: any): boolean {
  if (isItemStackable(item)) {
    // Deed/Token materials use absolute markup despite being stackable
    const subType = item?.Properties?.Type ?? item?.st;
    if (ABSOLUTE_MARKUP_MATERIAL_TYPES.has(subType)) return false;
    return true;
  }
  return itemHasCondition(item) && isLimited(item);
}

export function isAbsoluteMarkup(item: any): boolean {
  return !isPercentMarkup(item);
}

export function isPet(item: any): boolean {
  const type = item?.Properties?.Type ?? item?.Type ?? item?.t;
  return type === 'Pet';
}

/** Non-limited blueprint (instance item with QR, absolute markup) */
export function isBlueprintNonL(item: any): boolean {
  return isBlueprint(item) && !isLimited(item);
}

/** Get the TT value for a single unit, accounting for non-L BPs using QR/100 */
export function getUnitTT(item: any, order?: any): number | null {
  if (isBlueprintNonL(item)) {
    const qr = Number(order?.details?.QualityRating ?? order?.Metadata?.QualityRating) || 0;
    return qr > 0 ? qr / 100 : null;
  }
  return getMaxTT(item);
}

/** Get the display value for an order: CurrentTT from details if available, otherwise getUnitTT */
export function getOrderValue(item: any, order?: any): number | null {
  const ct = Number(order?.details?.CurrentTT ?? order?.Metadata?.CurrentTT);
  if (ct > 0) return ct;
  return getUnitTT(item, order);
}

/** Compute the unit price for an order given item + markup */
export function computeUnitPrice(item: any, markup: number | null, order?: any): number | null {
  if (markup == null) return null;
  const mu = Number(markup);
  if (isBlueprintNonL(item)) {
    const tt = getUnitTT(item, order);
    return tt != null ? tt + mu : mu;
  }
  const maxTT = getMaxTT(item);
  if (maxTT == null) return null;
  if (isAbsoluteMarkup(item)) {
    // Use CurrentTT if available (e.g. sell orders with specific condition), otherwise MaxTT
    const ct = Number(order?.details?.CurrentTT ?? order?.Metadata?.CurrentTT);
    const tt = ct > 0 ? ct : maxTT;
    return tt + mu;
  }
  return maxTT * (mu / 100);
}

/** Get pet level from order details */
export function getPetLevel(order: any): number | null {
  const lvl = order?.details?.Pet?.Level ?? order?.Metadata?.Pet?.Level ?? null;
  return lvl != null ? Number(lvl) : null;
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

/** Returns an inline HTML badge for special item types (e.g. ArmorSet → "Set"). */
export function itemTypeBadge(type: string | null | undefined): string {
  if (type === 'ArmorSet') return ' <span class="badge badge-subtle badge-accent" style="margin-left:6px">Set</span>';
  return '';
}

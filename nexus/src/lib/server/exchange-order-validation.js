//@ts-nocheck
/**
 * Shared validation functions for exchange order creation.
 * Used by both the single-order and batch-order endpoints.
 */
import { getResponse } from '$lib/util.js';
import { GENDERED_TYPES } from '$lib/common/itemTypes.js';
import { getPercentUndercutAmount, getAbsoluteUndercutAmount } from '../../routes/market/exchange/exchangeConstants.js';

/**
 * Validate and sanitize order details JSONB.
 * Only allows known metadata keys with correct types.
 */
export function validateOrderDetails(details) {
  if (details === null || details === undefined) return null;
  if (typeof details !== 'object' || Array.isArray(details)) return null;

  const clean = {};

  if (typeof details.item_name === 'string') {
    clean.item_name = details.item_name.slice(0, 200);
  }
  if (details.Tier != null) {
    const tier = Math.round(Number(details.Tier));
    if (Number.isFinite(tier) && tier >= 0 && tier <= 10) clean.Tier = tier;
  }
  if (details.TierIncreaseRate != null) {
    const tir = Math.round(Number(details.TierIncreaseRate));
    // (L) items allow TiR up to 4000, non-(L) up to 200
    const itemName = details.item_name || '';
    const isL = /\(.*L.*\)/.test(itemName);
    const maxTir = isL ? 4000 : 200;
    if (Number.isFinite(tir) && tir >= 0 && tir <= maxTir) clean.TierIncreaseRate = tir;
  }
  if (details.QualityRating != null) {
    const qr = Math.round(Number(details.QualityRating));
    if (Number.isFinite(qr) && qr >= 1 && qr <= 100) clean.QualityRating = qr;
  }
  if (details.CurrentTT != null) {
    const ct = parseFloat(details.CurrentTT);
    if (Number.isFinite(ct) && ct >= 0) clean.CurrentTT = ct;
  }
  if (details.Pet != null && typeof details.Pet === 'object' && !Array.isArray(details.Pet)) {
    const pet = {};
    if (details.Pet.Level != null) {
      const lvl = parseInt(details.Pet.Level, 10);
      if (Number.isFinite(lvl) && lvl >= 0) pet.Level = lvl;
    }
    if (Object.keys(pet).length > 0) clean.Pet = pet;
  }
  if (details.is_set === true) {
    clean.is_set = true;
  }
  if (details.Gender != null && typeof details.Gender === 'string') {
    if (details.Gender === 'Male' || details.Gender === 'Female') {
      clean.Gender = details.Gender;
    }
  }

  return Object.keys(clean).length > 0 ? clean : null;
}

/**
 * Strip is_set from details if the item type doesn't support it.
 */
export function enforceSetConstraint(details, itemType) {
  if (!details?.is_set) return details;
  if (itemType !== 'ArmorPlating') {
    const { is_set, ...rest } = details;
    return Object.keys(rest).length > 0 ? rest : null;
  }
  return details;
}

/**
 * Validate and enforce gender constraints based on item type.
 * Gender is available on itemInfo.gender (fetched from API).
 * Returns { details } on success, { error } on failure.
 */
export function enforceGenderConstraint(details, itemInfo) {
  if (!GENDERED_TYPES.has(itemInfo?.type)) {
    // Strip Gender from non-gendered types
    if (details?.Gender) {
      const { Gender, ...rest } = details;
      return { details: Object.keys(rest).length > 0 ? rest : null };
    }
    return { details };
  }

  const itemGender = itemInfo.gender;

  // Clothing with null gender → not tradeable
  if (itemInfo.type === 'Clothing' && itemGender === null) {
    return { error: 'This clothing item cannot be traded (no gender classification).' };
  }

  // Neutral clothing → no gender required, strip if provided
  if (itemGender === 'Neutral') {
    if (details?.Gender) {
      const { Gender, ...rest } = details;
      return { details: Object.keys(rest).length > 0 ? rest : null };
    }
    return { details };
  }

  // Gender required (Both, Male, or Female)
  if (!details?.Gender || !['Male', 'Female'].includes(details.Gender)) {
    return { error: 'Gender (Male or Female) is required for this item type.' };
  }

  // Set-gender items: must match
  if (itemGender !== 'Both' && details.Gender !== itemGender) {
    return { error: `This item is ${itemGender}-only. Gender must be "${itemGender}".` };
  }

  return { details };
}

/**
 * Check if a markup value violates undercut enforcement.
 * Returns an error message string if rejected, or null if allowed.
 *
 * Rules:
 * - SELL: markup in (bestSell - undercut, bestSell] is forbidden (too close without undercutting)
 * - BUY: markup in [bestBuy, bestBuy + outbid) is forbidden (too close without outbidding)
 * - Markups worse than best (higher sell / lower buy) are allowed freely
 * - Markups better by at least the undercut amount are allowed
 *
 * @param {number} markup - Submitted markup value
 * @param {'BUY'|'SELL'} type - Order side
 * @param {number|null} bestMarkup - Best existing markup from other users (null = no orders)
 * @param {boolean} isPercentMu - Whether this item uses percent markup
 * @returns {string|null} Error message or null
 */
export function checkUndercutEnforcement(markup, type, bestMarkup, isPercentMu) {
  if (bestMarkup == null) return null; // No competing orders

  const undercutAmt = isPercentMu
    ? getPercentUndercutAmount(bestMarkup)
    : getAbsoluteUndercutAmount(bestMarkup);

  if (type === 'SELL') {
    const threshold = Math.round((bestMarkup - undercutAmt) * 100) / 100;
    if (markup > threshold && markup <= bestMarkup) {
      const unit = isPercentMu ? '%' : ' PED';
      return `Sell markup must undercut the best offer (${bestMarkup}${unit}) by at least ${undercutAmt}${unit}, or be higher. Suggested: ${threshold}${unit}.`;
    }
  } else {
    const threshold = Math.round((bestMarkup + undercutAmt) * 100) / 100;
    if (markup >= bestMarkup && markup < threshold) {
      const unit = isPercentMu ? '%' : ' PED';
      return `Buy markup must outbid the best offer (${bestMarkup}${unit}) by at least ${undercutAmt}${unit}, or be lower. Suggested: ${threshold}${unit}.`;
    }
  }
  return null;
}

/**
 * Extract and verify authenticated user from request locals.
 * Returns { user } on success, { error: Response } on failure.
 */
export function getVerifiedUser(locals) {
  const user = locals.session?.user;
  if (!user) return { error: getResponse({ error: 'Authentication required' }, 401) };
  if (!user.verified) return { error: getResponse({ error: 'Verified account required' }, 403) };
  return { user };
}

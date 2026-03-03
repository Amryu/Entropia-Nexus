/**
 * Shared rental pricing utilities.
 * Used by both client (pricing preview) and server (snapshot on request creation).
 */

/**
 * Round to 2 decimal places (PED precision).
 * @param {number} value
 * @returns {number}
 */
function round2(value) {
  if (!Number.isFinite(value)) return 0;
  return Math.round(value * 100) / 100;
}

/**
 * Count the number of inclusive days between two date strings.
 * @param {string} startDate - ISO date string (YYYY-MM-DD)
 * @param {string} endDate - ISO date string (YYYY-MM-DD)
 * @returns {number} Number of days (inclusive)
 */
export function countDays(startDate, endDate) {
  const start = new Date(startDate + 'T00:00:00Z');
  const end = new Date(endDate + 'T00:00:00Z');
  const diffMs = end.getTime() - start.getTime();
  if (!Number.isFinite(diffMs)) return 1;
  return Math.max(1, Math.floor(diffMs / (24 * 60 * 60 * 1000)) + 1);
}

/**
 * Find the best applicable discount for a given number of days.
 * @param {Array<{minDays: number, percent: number}>} discounts - Sorted by minDays ascending
 * @param {number} totalDays - Number of rental days
 * @returns {{ percent: number, minDays: number } | null}
 */
export function findApplicableDiscount(discounts, totalDays) {
  if (!Array.isArray(discounts) || discounts.length === 0) return null;

  let best = null;
  for (const d of discounts) {
    if (d.minDays > 0 && d.percent > 0 && totalDays >= d.minDays) {
      if (!best || d.minDays > best.minDays) {
        best = d;
      }
    }
  }
  return best;
}

/**
 * Calculate rental price for a given duration.
 * @param {number} pricePerDay - Base price per day in PED
 * @param {Array<{minDays: number, percent: number}>} discounts - Discount thresholds
 * @param {number} totalDays - Number of rental days
 * @returns {{ totalDays: number, pricePerDay: number, discountPct: number, totalPrice: number }}
 */
export function calculateRentalPrice(pricePerDay, discounts, totalDays) {
  if (!Number.isFinite(totalDays) || totalDays <= 0 || !Number.isFinite(pricePerDay) || pricePerDay <= 0) {
    return { totalDays: 0, pricePerDay: 0, discountPct: 0, totalPrice: 0 };
  }

  const discount = findApplicableDiscount(discounts, totalDays);
  const discountPct = discount ? discount.percent : 0;
  const effectiveRate = round2(pricePerDay * (1 - discountPct / 100));
  const totalPrice = round2(effectiveRate * totalDays);

  return {
    totalDays,
    pricePerDay: effectiveRate,
    discountPct,
    totalPrice
  };
}

/**
 * Calculate extension price.
 * @param {number} basePricePerDay - Offer's base price per day
 * @param {Array<{minDays: number, percent: number}>} discounts - Offer's discount thresholds
 * @param {number} originalTotalPrice - Price already charged for the original rental
 * @param {number} originalDays - Original rental duration
 * @param {number} extraDays - Extension days
 * @param {boolean} retroactive - Whether to recalculate discount for total duration
 * @param {number|null} customPricePerDay - Owner-set custom rate (overrides base for non-retroactive)
 * @returns {{ extraDays: number, pricePerDay: number, discountPct: number, extraPrice: number, newTotalPrice: number }}
 */
export function calculateExtensionPrice(basePricePerDay, discounts, originalTotalPrice, originalDays, extraDays, retroactive, customPricePerDay = null) {
  if (!Number.isFinite(extraDays) || extraDays <= 0) {
    return { extraDays: 0, pricePerDay: 0, discountPct: 0, extraPrice: 0, newTotalPrice: originalTotalPrice || 0 };
  }

  const newTotalDays = originalDays + extraDays;

  if (retroactive) {
    // Recalculate for the full duration as one block
    const fullCalc = calculateRentalPrice(basePricePerDay, discounts, newTotalDays);
    const extraPrice = round2(fullCalc.totalPrice - originalTotalPrice);

    return {
      extraDays,
      pricePerDay: fullCalc.pricePerDay,
      discountPct: fullCalc.discountPct,
      extraPrice: Math.max(0, extraPrice),
      newTotalPrice: fullCalc.totalPrice
    };
  }

  // Non-retroactive: charge extension at base rate (or custom rate)
  const rate = customPricePerDay != null && customPricePerDay > 0 ? customPricePerDay : basePricePerDay;
  const discount = findApplicableDiscount(discounts, extraDays);
  const discountPct = discount ? discount.percent : 0;
  const effectiveRate = round2(rate * (1 - discountPct / 100));
  const extraPrice = round2(effectiveRate * extraDays);

  return {
    extraDays,
    pricePerDay: effectiveRate,
    discountPct,
    extraPrice,
    newTotalPrice: round2(originalTotalPrice + extraPrice)
  };
}

/**
 * Format a price for display (e.g. "12.50 PED").
 * @param {number} price
 * @returns {string}
 */
export function formatPrice(price) {
  if (price == null || isNaN(price)) return '0.00 PED';
  return `${Number(price).toFixed(2)} PED`;
}

/**
 * Format a date string or ISO timestamp for display (e.g. "Feb 27, 2026").
 * Handles both bare date strings "YYYY-MM-DD" and ISO timestamps "YYYY-MM-DDTHH:mm:ss.sssZ".
 * @param {string|null|undefined} dateStr
 * @returns {string}
 */
export function formatDateDisplay(dateStr) {
  if (!dateStr) return '\u2014';
  const dateOnly = String(dateStr).split('T')[0];
  const d = new Date(dateOnly + 'T00:00:00');
  if (isNaN(d.getTime())) return '\u2014';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/**
 * Generate a pricing preview table for different durations.
 * @param {number} pricePerDay
 * @param {Array} discounts
 * @returns {Array<{days: number, pricePerDay: number, discountPct: number, totalPrice: number}>}
 */
export function generatePricingPreview(pricePerDay, discounts) {
  const durations = [1, 3, 7, 14, 30, 90, 180, 365];
  return durations.map(days => calculateRentalPrice(pricePerDay, discounts, days));
}

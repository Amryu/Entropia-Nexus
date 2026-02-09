//@ts-nocheck
import { writable } from 'svelte/store';

/** User's own active offers */
export const myOffers = writable([]);

/** User's server-stored inventory */
export const inventory = writable([]);

/** Trade list items (offers the user wants to act on) */
export const tradeList = writable([]);

/** Whether the my-offers view is open */
export const showMyOffers = writable(false);

/** Whether the inventory panel is open */
export const showInventory = writable(false);

/** Whether the trade list panel is open */
export const showTradeList = writable(false);

/** Whether the trades panel is open */
export const showTrades = writable(false);

/** User's trade requests */
export const tradeRequests = writable([]);

/**
 * Add an item to the trade list.
 * @param {object} offer - The offer to add (must include offerId and side)
 */
export function addToTradeList(offer) {
  tradeList.update(items => {
    // Don't add duplicates
    if (items.some(i => i.offerId === offer.offerId)) return items;
    return [...items, offer];
  });
}

/**
 * Remove an item from the trade list.
 * @param {number} offerId
 */
export function removeFromTradeList(offerId) {
  tradeList.update(items => items.filter(i => i.offerId !== offerId));
}

/**
 * Clear the entire trade list.
 */
export function clearTradeList() {
  tradeList.set([]);
}

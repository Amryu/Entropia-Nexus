//@ts-nocheck
import { writable } from 'svelte/store';
import { computeState } from './exchangeConstants.js';

/** User's own active orders */
export const myOrders = writable([]);

/**
 * Enrich raw order data with display fields (item_name, state_display).
 * @param {Array} orders - Raw orders from the API
 * @returns {Array} Enriched orders
 */
export function enrichOrders(orders) {
  return (orders || []).map(o => ({
    ...o,
    state_display: o.computed_state || computeState(o.bumped_at),
    item_name: o.item_name || o.details?.item_name || `Item #${o.item_id}`,
  }));
}

/** User's server-stored inventory */
export const inventory = writable([]);

/** Trade list items (orders the user wants to act on) */
export const tradeList = writable([]);

/** Whether the my-orders view is open */
export const showMyOrders = writable(false);

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
 * @param {object} order - The order to add (must include orderId and side)
 */
export function addToTradeList(order) {
  tradeList.update(items => {
    // Don't add duplicates
    if (items.some(i => i.orderId === order.orderId)) return items;
    return [...items, order];
  });
}

/**
 * Remove an item from the trade list.
 * @param {number} orderId
 */
export function removeFromTradeList(orderId) {
  tradeList.update(items => items.filter(i => i.orderId !== orderId));
}

/**
 * Clear the entire trade list.
 */
export function clearTradeList() {
  tradeList.set([]);
}

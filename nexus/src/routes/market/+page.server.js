// @ts-nocheck
import { apiCall } from '$lib/util';
import { getExchangeCategorizationSummary } from '$lib/market/cache.js';

/** Display names for top-level exchange categories */
const CATEGORY_NAMES = {
  weapons: 'Weapons',
  armor: 'Armor',
  tools: 'Tools',
  materials: 'Materials',
  blueprints: 'Blueprints',
  vehicles: 'Vehicles',
  enhancers: 'Enhancers',
  clothes: 'Clothes',
  consumables: 'Consumables',
  pets: 'Pets',
  skill_implants: 'Skill Implants',
  furnishings: 'Furnishings',
  strongboxes: 'Strongboxes',
  financial: 'Financial'
};

/** Recursively count items with active orders in a category subtree */
function countActiveItems(node) {
  if (Array.isArray(node)) {
    return node.filter(item => (item.b > 0 || item.s > 0)).length;
  }
  if (node && typeof node === 'object') {
    let count = 0;
    for (const child of Object.values(node)) {
      count += countActiveItems(child);
    }
    return count;
  }
  return 0;
}

export async function load({ fetch }) {
  const [exchangeSummary, services, auctionResult, rentals, shops] = await Promise.all([
    getExchangeCategorizationSummary(fetch),
    apiCall(fetch, '/api/services'),
    apiCall(fetch, '/api/auction?status=active&limit=1&offset=0'),
    apiCall(fetch, '/api/rental?limit=100'),
    apiCall(fetch, '/shops')
  ]);

  // Build exchange category counts (items with active orders)
  const exchangeCategories = [];
  if (exchangeSummary && typeof exchangeSummary === 'object') {
    for (const [key, name] of Object.entries(CATEGORY_NAMES)) {
      if (exchangeSummary[key]) {
        exchangeCategories.push({
          key,
          name,
          activeCount: countActiveItems(exchangeSummary[key])
        });
      }
    }
  }

  // Total exchange items with active orders (sum across all categories)
  const totalExchangeActive = exchangeCategories.reduce((sum, c) => sum + c.activeCount, 0);

  // Count services by type
  const serviceCounts = { healing: 0, dps: 0, transportation: 0, custom: 0 };
  if (services) {
    for (const s of services) {
      if (s.type && serviceCounts[s.type] !== undefined) {
        serviceCounts[s.type]++;
      }
    }
  }
  const totalServices = services?.length || 0;

  return {
    exchangeCategories,
    totalExchangeActive,
    serviceCounts,
    totalServices,
    activeAuctions: auctionResult?.total || 0,
    availableRentals: Array.isArray(rentals) ? rentals.length : 0,
    totalShops: Array.isArray(shops) ? shops.length : 0
  };
}

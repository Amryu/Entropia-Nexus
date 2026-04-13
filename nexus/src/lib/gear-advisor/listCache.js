// @ts-nocheck
import { apiCall } from '$lib/util';

let armorSetsPromise = null;
let armorPlatingsPromise = null;
let mobsPromise = null;

export function getArmorSets(fetchFn = fetch) {
  if (!armorSetsPromise) {
    armorSetsPromise = apiCall(fetchFn, '/armorsets')
      .then(v => Array.isArray(v) ? v : [])
      .catch(() => []);
  }
  return armorSetsPromise;
}

export function getArmorPlatings(fetchFn = fetch) {
  if (!armorPlatingsPromise) {
    armorPlatingsPromise = apiCall(fetchFn, '/armorplatings')
      .then(v => Array.isArray(v) ? v : [])
      .catch(() => []);
  }
  return armorPlatingsPromise;
}

export function getMobs(fetchFn = fetch) {
  if (!mobsPromise) {
    mobsPromise = apiCall(fetchFn, '/mobs')
      .then(v => Array.isArray(v) ? v : [])
      .catch(() => []);
  }
  return mobsPromise;
}

export function clearGearAdvisorListCache() {
  armorSetsPromise = null;
  armorPlatingsPromise = null;
  mobsPromise = null;
}

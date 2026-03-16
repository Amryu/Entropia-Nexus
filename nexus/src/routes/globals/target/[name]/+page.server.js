// @ts-nocheck
import { decodeURIComponentSafe } from '$lib/util.js';

export function load({ params, fetch }) {
  const targetName = decodeURIComponentSafe(params.name);

  // Return promise without awaiting — SvelteKit streams it so the
  // page shell (header, search, skeleton) renders immediately.
  const targetData = fetch(`/api/globals/target/${encodeURIComponent(targetName)}`)
    .then(r => r.ok ? r.json() : null)
    .catch(() => null);

  return { targetData, targetName };
}

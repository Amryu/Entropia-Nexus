// @ts-nocheck
import { decodeURIComponentSafe } from '$lib/util.js';

export function load({ params, fetch }) {
  const playerName = decodeURIComponentSafe(params.name);

  // Return promise without awaiting — SvelteKit streams it so the
  // page shell (header, search, skeleton) renders immediately.
  const playerData = fetch(`/api/globals/player/${encodeURIComponent(playerName)}`)
    .then(r => r.ok ? r.json() : null)
    .catch(() => null);

  return { playerData, playerName };
}

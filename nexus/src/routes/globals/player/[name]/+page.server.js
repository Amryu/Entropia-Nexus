// @ts-nocheck
import { decodeURIComponentSafe } from '$lib/util.js';

export function load({ params, fetch }) {
  const playerName = decodeURIComponentSafe(params.name);

  // Return the promise nested so SvelteKit streams it instead of
  // blocking SSR. The page shell renders immediately with a skeleton,
  // and data streams in when the API responds.
  return {
    playerName,
    streamed: {
      playerData: fetch(`/api/globals/player/${encodeURIComponent(playerName)}?period=90d`)
        .then(r => r.ok ? r.json() : null)
        .catch(() => null)
    }
  };
}

// @ts-nocheck
import { decodeURIComponentSafe } from '$lib/util.js';

export function load({ params, fetch }) {
  const targetName = decodeURIComponentSafe(params.name);

  // Return the promise nested so SvelteKit streams it instead of
  // blocking SSR. The page shell renders immediately with a skeleton,
  // and data streams in when the API responds.
  return {
    targetName,
    streamed: {
      targetData: fetch(`/api/globals/target/${encodeURIComponent(targetName)}`)
        .then(r => r.ok ? r.json() : null)
        .catch(() => null)
    }
  };
}

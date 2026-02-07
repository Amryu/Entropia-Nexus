// @ts-nocheck
import { pageResponse } from '$lib/util';

// UUID v4 pattern: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function load({ fetch, params }) {
  const slug = params.slug || null;

  // No slug - normal loadout manager mode
  if (!slug) {
    return pageResponse(null, null, { loadoutId: null, sharedLoadout: null, shareCode: null, shareError: null });
  }

  // Check if slug is a UUID (user's own loadout ID)
  if (UUID_PATTERN.test(slug)) {
    return pageResponse(null, null, { loadoutId: slug, sharedLoadout: null, shareCode: null, shareError: null });
  }

  // Otherwise, treat as share code and fetch the shared loadout
  let sharedLoadout = null;
  let shareError = null;

  try {
    const response = await fetch(`/api/tools/loadout/share/${slug}`);
    if (response.ok) {
      sharedLoadout = await response.json();
    } else {
      const payload = await response.json().catch(() => null);
      shareError = payload?.error || 'Loadout not found.';
    }
  } catch (err) {
    shareError = 'Failed to load shared loadout.';
  }

  return pageResponse(null, sharedLoadout, { loadoutId: null, sharedLoadout, shareCode: slug, shareError });
}

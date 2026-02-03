// @ts-nocheck
import { pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  let sharedLoadout = null;
  let error = null;

  try {
    const response = await fetch(`/api/tools/loadout/share/${params.share_code}`);
    if (response.ok) {
      sharedLoadout = await response.json();
    } else {
      const payload = await response.json().catch(() => null);
      error = payload?.error || 'Loadout not found.';
    }
  } catch (err) {
    error = 'Failed to load shared loadout.';
  }

  return pageResponse(null, sharedLoadout, { error, shareCode: params.share_code });
}

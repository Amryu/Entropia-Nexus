// @ts-nocheck
import { requireVerified } from '$lib/server/auth';
import { getUserLoadouts } from '$lib/server/db.js';
import { apiCall } from '$lib/util';
import { env } from '$env/dynamic/public';

export async function load({ fetch, locals, url }) {
  const user = requireVerified(locals, url.pathname);

  const loadoutsRaw = await getUserLoadouts(user.id).catch(() => []);

  // Check disclaimer status
  const disclaimerStatus = await apiCall(fetch, '/api/auction/disclaimer');

  const loadouts = (loadoutsRaw || []).map(l => ({
    id: l.id,
    name: l.name,
    linked_item_set: l.linked_item_set
  }));

  return {
    loadouts,
    disclaimerStatus: disclaimerStatus || { bidder: false, seller: false },
    turnstileSiteKey: env.PUBLIC_TURNSTILE_SITE_KEY || ''
  };
}

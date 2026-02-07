// @ts-nocheck
import { pageResponse } from '$lib/util';

export async function load({ params }) {
  // Blueprint data will be lazy loaded on client for faster initial page load
  // Pass the planId from the route params
  return pageResponse(null, null, { planId: params.planId || null });
}

// @ts-nocheck
import { apiCall } from '$lib/util';
import { requireLogin } from '$lib/server/auth';

export async function load({ fetch, locals, url }) {
  requireLogin(locals, url.pathname);

  const [offers, requests] = await Promise.all([
    apiCall(fetch, '/api/rental/my?type=offers'),
    apiCall(fetch, '/api/rental/my?type=requests')
  ]);

  return {
    offers: offers || [],
    requests: requests || []
  };
}

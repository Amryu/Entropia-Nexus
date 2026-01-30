// @ts-nocheck
import { apiCall } from '$lib/util';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, locals, url }) {
  // Require verified user to sync availability
  requireVerified(locals, url.pathname);

  // Fetch user's services
  const services = await apiCall(fetch, '/api/services/my');

  return {
    services: (services || []).filter(s => s.is_active)
  };
}

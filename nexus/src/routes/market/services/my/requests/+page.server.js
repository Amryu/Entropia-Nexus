// @ts-nocheck
import { apiCall } from '$lib/util';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, locals, url }) {
  // Require verified user to access outgoing requests
  requireVerified(locals, url.pathname);

  const statusFilter = url.searchParams.get('status') || null;

  // Fetch user's outgoing requests
  const requests = await apiCall(fetch, `/api/services/requests/outgoing${statusFilter ? `?status=${statusFilter}` : ''}`);

  return {
    requests: requests || [],
    statusFilter
  };
}

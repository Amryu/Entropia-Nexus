// @ts-nocheck
import { apiCall } from '$lib/util';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, locals, url }) {
  // Require verified user to access incoming offers
  requireVerified(locals, url.pathname);

  const statusFilter = url.searchParams.get('status') || null;

  // Fetch user's services and all incoming requests
  const [services, incomingRequests] = await Promise.all([
    apiCall(fetch, '/api/services/my'),
    apiCall(fetch, `/api/services/my/requests${statusFilter ? `?status=${statusFilter}` : ''}`)
  ]);

  return {
    services: services || [],
    incomingRequests: incomingRequests || [],
    statusFilter
  };
}

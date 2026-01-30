// @ts-nocheck
import { apiCall } from '$lib/util';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, locals, url }) {
  // Require verified user to access My Services
  requireVerified(locals, url.pathname);

  // Fetch user's services and requests in parallel
  const [services, incomingRequests, outgoingRequests] = await Promise.all([
    apiCall(fetch, '/api/services/my'),
    apiCall(fetch, '/api/services/my/requests'),
    apiCall(fetch, '/api/services/requests/outgoing')
  ]);

  return {
    services: services || [],
    incomingRequests: incomingRequests || [],
    outgoingRequests: outgoingRequests || []
  };
}

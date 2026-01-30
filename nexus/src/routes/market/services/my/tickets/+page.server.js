// @ts-nocheck
import { apiCall } from '$lib/util';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, locals, url }) {
  // Require verified user to access tickets
  requireVerified(locals, url.pathname);

  // Check if user has any transportation services (to show "Issued Tickets" tab)
  const services = await apiCall(fetch, '/api/services/my');
  const hasTransportServices = (services || []).some(s => s.type === 'transportation');

  // Fetch owned tickets and issued tickets (if provider)
  const [ownedTickets, issuedTickets, expiredTickets, expiredIssuedTickets] = await Promise.all([
    apiCall(fetch, '/api/services/tickets/owned'),
    hasTransportServices ? apiCall(fetch, '/api/services/tickets/issued') : Promise.resolve([]),
    apiCall(fetch, '/api/services/tickets/owned?expired=recent'),
    hasTransportServices ? apiCall(fetch, '/api/services/tickets/issued?expired=recent') : Promise.resolve([])
  ]);

  return {
    ownedTickets: ownedTickets || [],
    issuedTickets: issuedTickets || [],
    expiredTickets: expiredTickets || [],
    expiredIssuedTickets: expiredIssuedTickets || [],
    hasTransportServices
  };
}

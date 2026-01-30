// @ts-nocheck
import { getResponse } from '$lib/util';
import { getProviderIssuedTickets, getProviderExpiredIssuedTickets } from '$lib/server/db';

export async function GET({ locals, url }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to view issued tickets.' }, 401);
  }

  try {
    const expired = url.searchParams.get('expired');

    if (expired === 'recent') {
      // Get recently expired issued tickets (most recent per service)
      const tickets = await getProviderExpiredIssuedTickets(user.id);
      return getResponse(tickets, 200);
    }

    const includeExpired = url.searchParams.get('includeExpired') !== 'false';
    const tickets = await getProviderIssuedTickets(user.id, includeExpired);
    return getResponse(tickets, 200);
  } catch (error) {
    console.error('Error fetching issued tickets:', error);
    return getResponse({ error: 'Failed to fetch tickets.' }, 500);
  }
}

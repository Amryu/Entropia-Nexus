// @ts-nocheck
import { getResponse } from '$lib/util';
import { getUserOwnedTickets } from '$lib/server/db';

export async function GET({ locals, url }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to view your tickets.' }, 401);
  }

  try {
    const expired = url.searchParams.get('expired');
    const includeExpired = expired === 'true';
    const recentExpiredOnly = expired === 'recent';

    const tickets = await getUserOwnedTickets(user.id, includeExpired, recentExpiredOnly);
    return getResponse(tickets, 200);
  } catch (error) {
    console.error('Error fetching owned tickets:', error);
    return getResponse({ error: 'Failed to fetch tickets.' }, 500);
  }
}

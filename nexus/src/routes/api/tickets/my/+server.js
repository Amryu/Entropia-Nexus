//@ts-nocheck
import { getUserTickets } from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// GET user's tickets
export async function GET({ url, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to view your tickets.' }, 401);
  }

  try {
    const includeExpired = url.searchParams.get('include_expired') === 'true';
    const tickets = await getUserTickets(user.id, includeExpired);
    return getResponse(tickets, 200);
  } catch (error) {
    console.error('Error fetching user tickets:', error);
    return getResponse({ error: 'Failed to fetch tickets.' }, 500);
  }
}

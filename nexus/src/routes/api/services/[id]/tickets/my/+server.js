// @ts-nocheck
import { getUserTicketsForService } from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

export async function GET({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  try {
    const tickets = await getUserTicketsForService(user.id, serviceId);
    // Return the first active/pending ticket if any
    const activeTicket = tickets.find(t => t.status === 'active' || t.status === 'pending');

    return getResponse({ ticket: activeTicket || null }, 200);
  } catch (error) {
    console.error('Error fetching user ticket:', error);
    return getResponse({ error: 'Failed to fetch ticket.' }, 500);
  }
}

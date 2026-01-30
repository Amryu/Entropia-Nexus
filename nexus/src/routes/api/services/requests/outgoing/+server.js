// @ts-nocheck
import { getResponse } from '$lib/util';
import { getUserOutgoingRequests } from '$lib/server/db';

export async function GET({ locals, url }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to view your requests.' }, 401);
  }

  try {
    const status = url.searchParams.get('status') || null;

    const filters = {};
    if (status) filters.status = status;

    const requests = await getUserOutgoingRequests(user.id, filters);
    return getResponse(requests, 200);
  } catch (error) {
    console.error('Error fetching user requests:', error);
    return getResponse({ error: 'Failed to fetch requests.' }, 500);
  }
}

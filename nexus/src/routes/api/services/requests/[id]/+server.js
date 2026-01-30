// @ts-nocheck
import { getResponse } from '$lib/util';
import { getRequestWithContext } from '$lib/server/db';

export async function GET({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to view request details.' }, 401);
  }

  const requestId = parseInt(params.id);
  if (isNaN(requestId)) {
    return getResponse({ error: 'Invalid request ID.' }, 400);
  }

  try {
    const request = await getRequestWithContext(requestId);

    if (!request) {
      return getResponse({ error: 'Request not found.' }, 404);
    }

    // Verify the user is either the requester or the provider
    if (request.requester_id !== user.id && request.provider_id !== user.id && !user.administrator) {
      return getResponse({ error: 'You can only view your own requests.' }, 403);
    }

    return getResponse(request, 200);
  } catch (error) {
    console.error('Error fetching request:', error);
    return getResponse({ error: 'Failed to fetch request.' }, 500);
  }
}

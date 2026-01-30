//@ts-nocheck
import { getResponse } from '$lib/util';
import { getUserActiveRequestsForService } from '$lib/server/db';

// GET user's active request for a specific service
export async function GET({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse(null, 200); // Not logged in, no request
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  try {
    const activeRequests = await getUserActiveRequestsForService(user.id, serviceId);

    if (activeRequests && activeRequests.length > 0) {
      return getResponse(activeRequests[0], 200);
    }

    return getResponse(null, 200);
  } catch (error) {
    console.error('Error fetching user active request:', error);
    return getResponse({ error: 'Failed to fetch request.' }, 500);
  }
}

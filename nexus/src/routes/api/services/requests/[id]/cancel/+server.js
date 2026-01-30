// @ts-nocheck
import { getResponse } from '$lib/util';
import { getRequestWithContext, updateRequestStatus } from '$lib/server/db';

export async function PUT({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to cancel a request.' }, 401);
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

    // Verify the user is the requester
    if (request.requester_id !== user.id && !user.administrator) {
      return getResponse({ error: 'You can only cancel your own requests.' }, 403);
    }

    // Check if cancellation is allowed
    const cancellableStatuses = ['pending', 'negotiating', 'accepted'];
    if (!cancellableStatuses.includes(request.status)) {
      return getResponse({
        error: `Cannot cancel a request with status '${request.status}'.`
      }, 400);
    }

    const updatedRequest = await updateRequestStatus(requestId, 'cancelled');
    return getResponse(updatedRequest, 200);
  } catch (error) {
    console.error('Error cancelling request:', error);
    return getResponse({ error: 'Failed to cancel request.' }, 500);
  }
}

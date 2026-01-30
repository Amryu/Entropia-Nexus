// @ts-nocheck
import { getResponse } from '$lib/util';
import {
  getRequestWithContext,
  updateRequestStatus
} from '$lib/server/db';

// Valid status transitions for questions (simplified from old request system)
// Questions only need: pending -> completed or cancelled
const validTransitions = {
  pending: ['completed', 'cancelled'],
  completed: [], // Terminal
  cancelled: [] // Terminal
};

// This endpoint is now simplified for questions only (service_notes starting with [QUESTION])
// The old request workflow for HPS/DPS/Custom has been removed
// Transportation now uses the flight/check-in system instead
export async function PUT({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to update request status.' }, 401);
  }

  const requestId = parseInt(params.requestId);
  if (isNaN(requestId)) {
    return getResponse({ error: 'Invalid request ID.' }, 400);
  }

  try {
    const body = await request.json();
    const { status: newStatus, service_notes } = body;

    if (!newStatus) {
      return getResponse({ error: 'Status is required.' }, 400);
    }

    // Get the request with context
    const serviceRequest = await getRequestWithContext(requestId);
    if (!serviceRequest) {
      return getResponse({ error: 'Request not found.' }, 404);
    }

    // Verify the user is the provider of this service
    if (serviceRequest.provider_id !== user.id && !user.administrator) {
      return getResponse({ error: 'You can only update requests for your own services.' }, 403);
    }

    // Validate the status transition
    const allowedTransitions = validTransitions[serviceRequest.status] || [];
    if (!allowedTransitions.includes(newStatus)) {
      return getResponse({
        error: `Cannot transition from '${serviceRequest.status}' to '${newStatus}'.`
      }, 400);
    }

    // Update the request (only service_notes is allowed to be updated)
    const updateData = {};
    if (service_notes !== undefined) {
      updateData.service_notes = service_notes;
    }

    const updatedRequest = await updateRequestStatus(requestId, newStatus, updateData);

    return getResponse(updatedRequest, 200);
  } catch (error) {
    console.error('Error updating request status:', error);
    return getResponse({ error: 'Failed to update request status.' }, 500);
  }
}

// @ts-nocheck
import { getResponse } from '$lib/util';
import { getRequestWithContext, updateServiceRequest } from '$lib/server/db';

export async function PUT({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to complete a request.' }, 401);
  }

  const requestId = parseInt(params.id);
  if (isNaN(requestId)) {
    return getResponse({ error: 'Invalid request ID.' }, 400);
  }

  try {
    const body = await request.json();
    const { review_score, review_comment } = body;

    const serviceRequest = await getRequestWithContext(requestId);

    if (!serviceRequest) {
      return getResponse({ error: 'Request not found.' }, 404);
    }

    // Verify the user is the requester (customer marks as complete)
    if (serviceRequest.requester_id !== user.id && !user?.grants?.includes('admin.panel')) {
      return getResponse({ error: 'Only the requester can mark a request as complete.' }, 403);
    }

    // Check if the request is in a state that allows completion review
    if (serviceRequest.status !== 'completed') {
      return getResponse({
        error: `Cannot add review to a request with status '${serviceRequest.status}'. Request must be completed by the provider first.`
      }, 400);
    }

    // Validate review score if provided
    if (review_score !== undefined && review_score !== null) {
      if (review_score < 1 || review_score > 10) {
        return getResponse({ error: 'Review score must be between 1 and 10.' }, 400);
      }
    }

    const updateData = {};
    if (review_score) {
      updateData.review_score = review_score;
      updateData.reviewed_at = new Date().toISOString();
    }
    if (review_comment) {
      updateData.review_comment = review_comment;
    }

    const updatedRequest = await updateServiceRequest(requestId, updateData);
    return getResponse(updatedRequest, 200);
  } catch (error) {
    console.error('Error completing request:', error);
    return getResponse({ error: 'Failed to complete request.' }, 500);
  }
}

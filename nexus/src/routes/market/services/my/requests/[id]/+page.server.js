// @ts-nocheck
import { apiCall } from '$lib/util';
import { error } from '@sveltejs/kit';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, locals, params, url }) {
  // Require verified user to view request details
  const user = requireVerified(locals, url.pathname);

  const requestId = parseInt(params.id);
  if (isNaN(requestId)) {
    throw error(400, 'Invalid request ID');
  }

  // Fetch request details
  const request = await apiCall(fetch, `/api/services/requests/${requestId}`);

  if (!request) {
    throw error(404, 'Request not found');
  }

  // Verify the user is the requester
  if (request.requester_id !== user.id && !user.administrator) {
    throw error(403, 'You can only view your own requests');
  }

  return {
    request
  };
}

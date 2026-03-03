// @ts-nocheck
import { apiCall } from '$lib/util';
import { error } from '@sveltejs/kit';
import { requireLogin } from '$lib/server/auth';

export async function load({ fetch, locals, params, url }) {
  requireLogin(locals, url.pathname);

  const requestId = parseInt(params.requestId);
  if (isNaN(requestId)) {
    throw error(400, 'Invalid request ID');
  }

  const request = await apiCall(fetch, `/api/rental/requests/${requestId}`);

  if (!request) {
    throw error(404, 'Rental request not found');
  }

  return {
    request
  };
}

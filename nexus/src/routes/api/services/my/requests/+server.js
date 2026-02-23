// @ts-nocheck
import { getResponse } from '$lib/util';
import { getProviderIncomingRequests } from '$lib/server/db';
import { requireGrantAPI } from '$lib/server/auth.js';

export async function GET({ locals, url }) {
  const user = requireGrantAPI(locals, 'services.manage');

  try {
    const status = url.searchParams.get('status') || null;
    const serviceId = url.searchParams.get('serviceId') ? parseInt(url.searchParams.get('serviceId')) : null;

    const filters = {};
    if (status) filters.status = status;
    if (serviceId && !isNaN(serviceId)) filters.serviceId = serviceId;

    const requests = await getProviderIncomingRequests(user.id, filters);
    return getResponse(requests, 200);
  } catch (error) {
    console.error('Error fetching provider requests:', error);
    return getResponse({ error: 'Failed to fetch requests.' }, 500);
  }
}

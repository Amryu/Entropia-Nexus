// @ts-nocheck
import { apiCall } from '$lib/util';
import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/public';

export async function load({ fetch, params, locals }) {
  const auction = await apiCall(fetch, `/api/auction/${params.id}`);

  if (!auction || auction.error) {
    throw error(404, 'Auction not found');
  }

  const user = locals.session?.user;
  let disclaimerStatus = null;
  let auditLog = null;

  // Fetch disclaimer status if logged in
  if (user?.verified) {
    disclaimerStatus = await apiCall(fetch, '/api/auction/disclaimer');
  }

  // Fetch audit log if admin
  const isAdmin = user?.grants?.includes('admin.panel') || user?.administrator;
  if (isAdmin) {
    auditLog = await apiCall(fetch, `/api/auction/${params.id}/admin/audit`);
  }

  return {
    auction,
    disclaimerStatus,
    auditLog,
    turnstileSiteKey: env.PUBLIC_TURNSTILE_SITE_KEY || ''
  };
}

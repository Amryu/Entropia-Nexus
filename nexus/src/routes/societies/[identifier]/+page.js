// @ts-nocheck
import { redirect, error } from '@sveltejs/kit';
import { apiCall, decodeURIComponentSafe, encodeURIComponentSafe } from '$lib/util';

export async function load({ fetch, params, parent }) {
  const parentData = await parent();
  const rawIdentifier = params.identifier;
  const identifier = decodeURIComponentSafe(rawIdentifier);
  const encoded = encodeURIComponentSafe(identifier);

  const societyData = await apiCall(fetch, `/api/societies/${encoded}`);
  if (!societyData) {
    throw error(404, 'Society not found');
  }

  const isNumeric = /^\d+$/.test(rawIdentifier);
  const name = societyData?.society?.name;
  if (isNumeric && name) {
    throw redirect(302, `/societies/${encodeURIComponentSafe(name)}`);
  }

  return {
    session: parentData.session,
    societyData
  };
}

// @ts-nocheck
import { redirect, error } from '@sveltejs/kit';
import { apiCall, decodeURIComponentSafe, encodeURIComponentSafe } from '$lib/util';

export async function load({ fetch, params, parent }) {
  const parentData = await parent();
  const rawIdentifier = params.identifier;
  const identifier = decodeURIComponentSafe(rawIdentifier);
  const encoded = encodeURIComponentSafe(identifier);

  const profileData = await apiCall(fetch, `/api/users/profiles/${encoded}`);
  if (!profileData) {
    throw error(404, 'User not found');
  }

  const euName = profileData?.profile?.euName;
  const isNumeric = /^\d+$/.test(rawIdentifier);
  if (isNumeric && euName) {
    throw redirect(302, `/user/${encodeURIComponentSafe(euName)}`);
  }

  return {
    session: parentData.session,
    profileData
  };
}

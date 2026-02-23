// @ts-nocheck
import { requireVerified } from '$lib/server/auth.js';
import { getUserAuthorizations } from '$lib/server/oauth.js';

export async function load({ locals }) {
  const user = requireVerified(locals);

  const authorizations = await getUserAuthorizations(BigInt(user.id));

  return { authorizations };
}

// @ts-nocheck
import { requireVerified } from '$lib/server/auth.js';
import { getClientsByUser, MAX_CLIENTS_PER_USER } from '$lib/server/oauth.js';

export async function load({ locals }) {
  const user = requireVerified(locals);

  const clients = await getClientsByUser(BigInt(user.id));

  return {
    clients,
    maxClients: MAX_CLIENTS_PER_USER
  };
}

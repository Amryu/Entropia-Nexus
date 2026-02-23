// @ts-nocheck
import { requireVerified } from '$lib/server/auth.js';
import { getClientsByUser, getScopeDefinitions, MAX_CLIENTS_PER_USER } from '$lib/server/oauth.js';

export async function load({ locals }) {
  const user = requireVerified(locals);

  const [clients, scopeMap] = await Promise.all([
    getClientsByUser(BigInt(user.id)),
    getScopeDefinitions()
  ]);

  // Convert scope Map to serializable array grouped by category
  const scopes = [];
  for (const [key, def] of scopeMap) {
    scopes.push({ key, description: def.description });
  }

  return {
    clients,
    maxClients: MAX_CLIENTS_PER_USER,
    scopes
  };
}

// @ts-nocheck
/**
 * GET /api/oauth/clients — List current user's OAuth clients
 * POST /api/oauth/clients — Register a new OAuth client
 */
import { getResponse } from '$lib/util.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';
import { getClientsByUser, createClient, MAX_CLIENTS_PER_USER } from '$lib/server/oauth.js';

export async function GET({ locals }) {
  const user = requireVerifiedAPI(locals);

  const clients = await getClientsByUser(BigInt(user.id));
  return getResponse(clients, 200);
}

export async function POST({ request, locals }) {
  const user = requireVerifiedAPI(locals);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  const { name, description, website_url, redirect_uris, is_confidential } = body;

  if (!name || typeof name !== 'string' || name.trim().length === 0) {
    return getResponse({ error: 'name is required' }, 400);
  }
  if (name.length > 100) {
    return getResponse({ error: 'name must be 100 characters or fewer' }, 400);
  }
  if (description && description.length > 500) {
    return getResponse({ error: 'description must be 500 characters or fewer' }, 400);
  }
  if (website_url && website_url.length > 500) {
    return getResponse({ error: 'website_url must be 500 characters or fewer' }, 400);
  }
  if (website_url) {
    try {
      new URL(website_url);
    } catch {
      return getResponse({ error: 'website_url must be a valid URL' }, 400);
    }
  }

  if (!Array.isArray(redirect_uris) || redirect_uris.length === 0) {
    return getResponse({ error: 'At least one redirect_uri is required' }, 400);
  }
  if (redirect_uris.length > 10) {
    return getResponse({ error: 'Maximum 10 redirect URIs' }, 400);
  }
  for (const uri of redirect_uris) {
    if (typeof uri !== 'string' || uri.length > 500) {
      return getResponse({ error: 'Each redirect_uri must be a string of 500 characters or fewer' }, 400);
    }
    try {
      new URL(uri);
    } catch {
      return getResponse({ error: `Invalid redirect_uri: ${uri}` }, 400);
    }
  }

  try {
    const result = await createClient(
      BigInt(user.id),
      name.trim(),
      description?.trim() || null,
      website_url?.trim() || null,
      redirect_uris,
      is_confidential !== false
    );
    return getResponse(result, 201);
  } catch (err) {
    if (err.message?.includes('Maximum')) {
      return getResponse({ error: err.message }, 409);
    }
    console.error('Error creating OAuth client:', err);
    return getResponse({ error: 'Failed to create client' }, 500);
  }
}

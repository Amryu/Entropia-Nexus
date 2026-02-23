// @ts-nocheck
/**
 * GET /api/oauth/clients/[id] — Get a specific client
 * PUT /api/oauth/clients/[id] — Update a client
 * DELETE /api/oauth/clients/[id] — Delete a client
 */
import { getResponse } from '$lib/util.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';
import { getClient, updateClient, deleteClient } from '$lib/server/oauth.js';

export async function GET({ params, locals }) {
  const user = requireVerifiedAPI(locals);

  const client = await getClient(params.id);
  if (!client || String(client.user_id) !== String(user.id)) {
    return getResponse({ error: 'Client not found' }, 404);
  }

  return getResponse(client, 200);
}

export async function PUT({ params, request, locals }) {
  const user = requireVerifiedAPI(locals);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  const updates = {};
  if (body.name !== undefined) {
    if (typeof body.name !== 'string' || body.name.trim().length === 0) {
      return getResponse({ error: 'name must be a non-empty string' }, 400);
    }
    if (body.name.length > 100) {
      return getResponse({ error: 'name must be 100 characters or fewer' }, 400);
    }
    updates.name = body.name.trim();
  }
  if (body.description !== undefined) {
    if (body.description && body.description.length > 500) {
      return getResponse({ error: 'description must be 500 characters or fewer' }, 400);
    }
    updates.description = body.description?.trim() || null;
  }
  if (body.website_url !== undefined) {
    if (body.website_url) {
      try { new URL(body.website_url); } catch {
        return getResponse({ error: 'website_url must be a valid URL' }, 400);
      }
    }
    updates.websiteUrl = body.website_url?.trim() || null;
  }
  if (body.redirect_uris !== undefined) {
    if (!Array.isArray(body.redirect_uris) || body.redirect_uris.length === 0) {
      return getResponse({ error: 'At least one redirect_uri is required' }, 400);
    }
    for (const uri of body.redirect_uris) {
      try { new URL(uri); } catch {
        return getResponse({ error: `Invalid redirect_uri: ${uri}` }, 400);
      }
    }
    updates.redirectUris = body.redirect_uris;
  }

  const updated = await updateClient(params.id, BigInt(user.id), updates);
  if (!updated) {
    return getResponse({ error: 'Client not found or no changes made' }, 404);
  }

  const client = await getClient(params.id);
  return getResponse(client, 200);
}

export async function DELETE({ params, locals }) {
  const user = requireVerifiedAPI(locals);

  const deleted = await deleteClient(params.id, BigInt(user.id));
  if (!deleted) {
    return getResponse({ error: 'Client not found' }, 404);
  }

  return getResponse({ deleted: true }, 200);
}

//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getUserBlueprintOwnership, updateUserBlueprintOwnership } from '$lib/server/db.js';

const MAX_OWNERSHIP_BYTES = 100000; // 100KB for ownership map

function sanitizeOwnershipData(data) {
  if (!data || typeof data !== 'object') {
    return {};
  }

  const sanitized = {};
  for (const [key, value] of Object.entries(data)) {
    // Only store blueprints that are NOT owned (value === false)
    // Owned blueprints are assumed by default, so we don't need to store them
    if (value === false) {
      const blueprintId = parseInt(key, 10);
      if (!isNaN(blueprintId) && blueprintId > 0) {
        sanitized[blueprintId] = false;
      }
    }
  }

  return sanitized;
}

function getPayloadSizeBytes(obj) {
  return new TextEncoder().encode(JSON.stringify(obj)).length;
}

export async function GET({ locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  try {
    const ownership = await getUserBlueprintOwnership(user.id);
    return getResponse(ownership, 200);
  } catch (error) {
    console.error('Error fetching blueprint ownership:', error);
    return getResponse({ error: 'Failed to fetch blueprint ownership.' }, 500);
  }
}

export async function PUT({ request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  if (getPayloadSizeBytes(body) > MAX_OWNERSHIP_BYTES) {
    return getResponse({ error: 'Payload exceeds 100KB limit.' }, 413);
  }

  try {
    // Client sends the full ownership state, so replace rather than merge
    const sanitized = sanitizeOwnershipData(body);

    if (getPayloadSizeBytes(sanitized) > MAX_OWNERSHIP_BYTES) {
      return getResponse({ error: 'Ownership data exceeds 100KB limit.' }, 413);
    }

    const record = await updateUserBlueprintOwnership(user.id, sanitized);
    return getResponse(record.data, 200);
  } catch (error) {
    console.error('Error updating blueprint ownership:', error);
    return getResponse({ error: 'Failed to update blueprint ownership.' }, 500);
  }
}

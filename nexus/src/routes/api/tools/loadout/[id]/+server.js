//@ts-nocheck
import crypto from 'crypto';
import { getResponse } from '$lib/util.js';
import { getUserLoadoutById, updateUserLoadout, deleteUserLoadout } from '$lib/server/db.js';
import { sanitizeLoadoutData, getPayloadSizeBytes, MAX_LOADOUT_BYTES } from '$lib/server/loadoutUtils.js';

const SHARE_CODE_LENGTH = 10;
const SHARE_CODE_ATTEMPTS = 5;
const BASE62 = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';

function sanitizeName(value, fallback = 'New Loadout') {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, 120) : fallback;
}

function generateShareCode(length = SHARE_CODE_LENGTH) {
  const bytes = crypto.randomBytes(length);
  let code = '';
  for (let i = 0; i < length; i += 1) {
    code += BASE62[bytes[i] % BASE62.length];
  }
  return code;
}

async function updateWithShareCode(userId, id, name, data, isPublic, existingCode) {
  let shareCode = existingCode;
  if (isPublic && !shareCode) {
    shareCode = generateShareCode();
  }

  for (let attempt = 0; attempt < SHARE_CODE_ATTEMPTS; attempt += 1) {
    try {
      return await updateUserLoadout(userId, id, name, data, isPublic, shareCode);
    } catch (err) {
      if (err?.code === '23505' && shareCode) {
        shareCode = generateShareCode();
        continue;
      }
      throw err;
    }
  }
  throw new Error('Failed to generate a unique share code.');
}

export async function GET({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  try {
    const record = await getUserLoadoutById(user.id, params.id);
    if (!record) {
      return getResponse({ error: 'Loadout not found.' }, 404);
    }
    return getResponse(record, 200);
  } catch (error) {
    console.error('Error fetching loadout:', error);
    return getResponse({ error: 'Failed to fetch loadout.' }, 500);
  }
}

export async function PUT({ params, request, locals }) {
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

  if (getPayloadSizeBytes(body) > MAX_LOADOUT_BYTES) {
    return getResponse({ error: 'Payload exceeds 20KB limit.' }, 413);
  }

  try {
    const existing = await getUserLoadoutById(user.id, params.id);
    if (!existing) {
      return getResponse({ error: 'Loadout not found.' }, 404);
    }

    const incomingData = body?.data ?? existing.data;
    const sanitizedData = sanitizeLoadoutData(incomingData);
    const name = sanitizeName(body?.name ?? sanitizedData?.Name ?? existing.name ?? 'New Loadout');
    sanitizedData.Name = name;

    if (getPayloadSizeBytes(sanitizedData) > MAX_LOADOUT_BYTES) {
      return getResponse({ error: 'Loadout data exceeds 20KB limit.' }, 413);
    }

    const isPublic = body?.public != null ? !!body.public : !!existing.public;
    const record = await updateWithShareCode(user.id, params.id, name, sanitizedData, isPublic, existing.share_code);
    return getResponse(record, 200);
  } catch (error) {
    console.error('Error updating loadout:', error);
    return getResponse({ error: 'Failed to update loadout.' }, 500);
  }
}

// POST handler for sendBeacon save-on-close (sendBeacon only supports POST)
export async function POST({ params, request, locals }) {
  return PUT({ params, request, locals });
}

export async function DELETE({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  try {
    const record = await getUserLoadoutById(user.id, params.id);
    if (!record) {
      return getResponse({ error: 'Loadout not found.' }, 404);
    }

    await deleteUserLoadout(user.id, params.id);
    return getResponse({ success: true }, 200);
  } catch (error) {
    console.error('Error deleting loadout:', error);
    return getResponse({ error: 'Failed to delete loadout.' }, 500);
  }
}

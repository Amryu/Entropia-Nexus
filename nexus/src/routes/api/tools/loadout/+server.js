//@ts-nocheck
import crypto from 'crypto';
import { getResponse } from '$lib/util.js';
import { requireGrantAPI } from '$lib/server/auth.js';
import { countUserLoadouts, createUserLoadout, getUserLoadouts } from '$lib/server/db.js';
import { sanitizeLoadoutData, getPayloadSizeBytes, MAX_LOADOUT_BYTES } from '$lib/server/loadoutUtils.js';

const MAX_LOADOUTS = 500;
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

async function createWithShareCode(userId, name, data, isPublic) {
  let shareCode = isPublic ? generateShareCode() : null;
  for (let attempt = 0; attempt < SHARE_CODE_ATTEMPTS; attempt += 1) {
    try {
      return await createUserLoadout(userId, name, data, isPublic, shareCode);
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

export async function GET({ locals }) {
  const user = requireGrantAPI(locals, 'loadouts.read');

  try {
    const loadouts = await getUserLoadouts(user.id);
    return getResponse(loadouts, 200);
  } catch (error) {
    console.error('Error fetching loadouts:', error);
    return getResponse({ error: 'Failed to fetch loadouts.' }, 500);
  }
}

export async function POST({ request, locals }) {
  const user = requireGrantAPI(locals, 'loadouts.manage');

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
    const loadoutCount = await countUserLoadouts(user.id);
    if (loadoutCount >= MAX_LOADOUTS) {
      return getResponse({ error: 'Loadout limit reached.' }, 403);
    }

    const sanitizedData = sanitizeLoadoutData(body?.data);
    const name = sanitizeName(body?.name ?? sanitizedData?.Name ?? 'New Loadout');
    sanitizedData.Name = name;

    if (getPayloadSizeBytes(sanitizedData) > MAX_LOADOUT_BYTES) {
      return getResponse({ error: 'Loadout data exceeds 20KB limit.' }, 413);
    }

    const isPublic = !!body?.public;
    const record = await createWithShareCode(user.id, name, sanitizedData, isPublic);
    return getResponse(record, 201);
  } catch (error) {
    console.error('Error creating loadout:', error);
    return getResponse({ error: 'Failed to create loadout.' }, 500);
  }
}

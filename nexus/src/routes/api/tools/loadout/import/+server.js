//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { countUserLoadouts, createUserLoadout } from '$lib/server/db.js';
import { sanitizeLoadoutData, getPayloadSizeBytes, MAX_LOADOUT_BYTES, MAX_IMPORT_BYTES } from '$lib/server/loadoutUtils.js';

const MAX_LOADOUTS = 500;

function sanitizeName(value, fallback = 'New Loadout') {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, 120) : fallback;
}

export async function POST({ request, locals }) {
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

  if (getPayloadSizeBytes(body) > MAX_IMPORT_BYTES) {
    return getResponse({ error: 'Payload exceeds 1MB limit.' }, 413);
  }

  const loadouts = Array.isArray(body?.loadouts) ? body.loadouts : [];
  if (!loadouts.length) {
    return getResponse({ error: 'No loadouts provided.' }, 400);
  }

  try {
    const existingCount = await countUserLoadouts(user.id);
    const remaining = MAX_LOADOUTS - existingCount;
    if (remaining <= 0) {
      return getResponse({ error: 'Loadout limit reached.' }, 403);
    }

    let imported = 0;
    let skipped = 0;

    for (const item of loadouts) {
      if (imported >= remaining) {
        skipped += 1;
        continue;
      }

      const sanitizedData = sanitizeLoadoutData(item);
      const name = sanitizeName(item?.Name ?? sanitizedData?.Name ?? 'New Loadout');
      sanitizedData.Name = name;

      if (getPayloadSizeBytes(sanitizedData) > MAX_LOADOUT_BYTES) {
        skipped += 1;
        continue;
      }

      try {
        await createUserLoadout(user.id, name, sanitizedData, false, null);
        imported += 1;
      } catch (error) {
        console.error('Failed to import loadout:', error);
        skipped += 1;
      }
    }

    return getResponse({ imported, skipped }, 200);
  } catch (error) {
    console.error('Error importing loadouts:', error);
    return getResponse({ error: 'Failed to import loadouts.' }, 500);
  }
}

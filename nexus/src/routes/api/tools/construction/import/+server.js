//@ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  getUserCraftingPlans,
  createUserCraftingPlan,
  getUserBlueprintOwnership,
  updateUserBlueprintOwnership
} from '$lib/server/db.js';

const MAX_PLANS = 100;
const MAX_IMPORT_BYTES = 1024 * 1024; // 1MB limit for import
const MAX_PLAN_BYTES = 50000; // 50KB per plan

function sanitizeName(value, fallback = 'New Plan') {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, 120) : fallback;
}

function sanitizePlanData(data) {
  if (!data || typeof data !== 'object') {
    return { targets: [] };
  }

  const targets = [];
  if (Array.isArray(data.targets)) {
    for (const target of data.targets) {
      if (typeof target?.blueprintId === 'number' && typeof target?.quantity === 'number') {
        targets.push({
          blueprintId: Math.floor(target.blueprintId),
          quantity: Math.max(1, Math.floor(target.quantity))
        });
      }
    }
  }

  return { targets };
}

function sanitizeOwnershipData(data) {
  if (!data || typeof data !== 'object') {
    return {};
  }

  const sanitized = {};
  for (const [key, value] of Object.entries(data)) {
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

  const plans = Array.isArray(body?.plans) ? body.plans : [];
  const ownership = body?.ownership || {};

  try {
    // Import ownership (merge with existing)
    let ownershipImported = 0;
    if (Object.keys(ownership).length > 0) {
      const existingOwnership = await getUserBlueprintOwnership(user.id);
      const sanitizedOwnership = sanitizeOwnershipData(ownership);

      // Merge: imported values override existing for conflicts
      const merged = { ...existingOwnership, ...sanitizedOwnership };
      await updateUserBlueprintOwnership(user.id, merged);
      ownershipImported = Object.keys(sanitizedOwnership).length;
    }

    // Import plans
    const existingPlans = await getUserCraftingPlans(user.id);
    const existingNames = new Set(existingPlans.map(p => p.name.toLowerCase()));
    const remaining = MAX_PLANS - existingPlans.length;

    let plansImported = 0;
    let plansSkipped = 0;

    for (const plan of plans) {
      if (plansImported >= remaining) {
        plansSkipped += 1;
        continue;
      }

      const sanitizedData = sanitizePlanData(plan?.data);
      let name = sanitizeName(plan?.name ?? 'New Plan');

      // Check for duplicate names and add suffix if needed
      if (existingNames.has(name.toLowerCase())) {
        name = `${name} (imported)`;
        // If still duplicate, add number
        let counter = 2;
        while (existingNames.has(name.toLowerCase())) {
          name = `${sanitizeName(plan?.name ?? 'New Plan')} (imported ${counter})`;
          counter += 1;
        }
      }

      if (getPayloadSizeBytes(sanitizedData) > MAX_PLAN_BYTES) {
        plansSkipped += 1;
        continue;
      }

      if (sanitizedData.targets.length === 0) {
        // Skip empty plans
        plansSkipped += 1;
        continue;
      }

      try {
        await createUserCraftingPlan(user.id, name, sanitizedData);
        existingNames.add(name.toLowerCase());
        plansImported += 1;
      } catch (error) {
        console.error('Failed to import plan:', error);
        plansSkipped += 1;
      }
    }

    return getResponse({
      plansImported,
      plansSkipped,
      ownershipImported
    }, 200);
  } catch (error) {
    console.error('Error importing construction data:', error);
    return getResponse({ error: 'Failed to import data.' }, 500);
  }
}

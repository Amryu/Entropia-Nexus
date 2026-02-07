//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getUserCraftingPlanById, updateUserCraftingPlan, deleteUserCraftingPlan } from '$lib/server/db.js';

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

function getPayloadSizeBytes(obj) {
  return new TextEncoder().encode(JSON.stringify(obj)).length;
}

export async function GET({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  try {
    const record = await getUserCraftingPlanById(user.id, params.id);
    if (!record) {
      return getResponse({ error: 'Plan not found.' }, 404);
    }
    return getResponse(record, 200);
  } catch (error) {
    console.error('Error fetching crafting plan:', error);
    return getResponse({ error: 'Failed to fetch crafting plan.' }, 500);
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

  if (getPayloadSizeBytes(body) > MAX_PLAN_BYTES) {
    return getResponse({ error: 'Payload exceeds 50KB limit.' }, 413);
  }

  try {
    const existing = await getUserCraftingPlanById(user.id, params.id);
    if (!existing) {
      return getResponse({ error: 'Plan not found.' }, 404);
    }

    const incomingData = body?.data ?? existing.data;
    const sanitizedData = sanitizePlanData(incomingData);
    const name = sanitizeName(body?.name ?? existing.name ?? 'New Plan');

    if (getPayloadSizeBytes(sanitizedData) > MAX_PLAN_BYTES) {
      return getResponse({ error: 'Plan data exceeds 50KB limit.' }, 413);
    }

    const record = await updateUserCraftingPlan(user.id, params.id, name, sanitizedData);
    return getResponse(record, 200);
  } catch (error) {
    console.error('Error updating crafting plan:', error);
    return getResponse({ error: 'Failed to update crafting plan.' }, 500);
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
    const record = await getUserCraftingPlanById(user.id, params.id);
    if (!record) {
      return getResponse({ error: 'Plan not found.' }, 404);
    }

    await deleteUserCraftingPlan(user.id, params.id);
    return getResponse({ success: true }, 200);
  } catch (error) {
    console.error('Error deleting crafting plan:', error);
    return getResponse({ error: 'Failed to delete crafting plan.' }, 500);
  }
}

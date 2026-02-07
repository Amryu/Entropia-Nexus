//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getUserCraftingPlans, createUserCraftingPlan } from '$lib/server/db.js';

const MAX_PLANS = 100;
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

export async function GET({ locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  try {
    const plans = await getUserCraftingPlans(user.id);
    return getResponse(plans, 200);
  } catch (error) {
    console.error('Error fetching crafting plans:', error);
    return getResponse({ error: 'Failed to fetch crafting plans.' }, 500);
  }
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

  if (getPayloadSizeBytes(body) > MAX_PLAN_BYTES) {
    return getResponse({ error: 'Payload exceeds 50KB limit.' }, 413);
  }

  try {
    const existingPlans = await getUserCraftingPlans(user.id);
    if (existingPlans.length >= MAX_PLANS) {
      return getResponse({ error: 'Plan limit reached.' }, 403);
    }

    const sanitizedData = sanitizePlanData(body?.data);
    const name = sanitizeName(body?.name ?? 'New Plan');

    if (getPayloadSizeBytes(sanitizedData) > MAX_PLAN_BYTES) {
      return getResponse({ error: 'Plan data exceeds 50KB limit.' }, 413);
    }

    const record = await createUserCraftingPlan(user.id, name, sanitizedData);
    return getResponse(record, 201);
  } catch (error) {
    console.error('Error creating crafting plan:', error);
    return getResponse({ error: 'Failed to create crafting plan.' }, 500);
  }
}

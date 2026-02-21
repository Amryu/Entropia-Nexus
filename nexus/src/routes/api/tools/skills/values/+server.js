// @ts-nocheck
/**
 * POST /api/tools/skills/values — Batch skill↔PED conversions.
 * Public endpoint (no auth required). Rate limited by IP.
 */
import { getResponse } from '$lib/util.js';
import { checkRateLimit, getRateLimitHeaders } from '$lib/server/rateLimiter.js';
import { batchSkillPointsToPED, batchPedToSkillPoints } from '$lib/server/skillFormula.js';

const MAX_BATCH_SIZE = 200;
const RATE_LIMIT = 60;
const RATE_WINDOW_MS = 60_000;

export async function POST({ request, locals }) {
  const ip = locals.ip || request.headers.get('x-forwarded-for') || request.headers.get('cf-connecting-ip') || 'unknown';
  const rateCheck = checkRateLimit(`skill-values:${ip}`, RATE_LIMIT, RATE_WINDOW_MS);

  if (!rateCheck.allowed) {
    return new Response(JSON.stringify({
      error: 'Rate limit exceeded. Please try again later.',
      retryAfter: Math.ceil(rateCheck.resetIn / 1000)
    }), {
      status: 429,
      headers: { 'Content-Type': 'application/json', ...getRateLimitHeaders(RATE_LIMIT, 0, rateCheck.resetIn) }
    });
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON.' }, 400);
  }

  if (typeof body !== 'object' || body === null) {
    return getResponse({ error: 'Request body must be an object.' }, 400);
  }

  const { skillPointsToPED: spToPed, pedToSkillPoints: pedToSp } = body;

  if (!Array.isArray(spToPed) && !Array.isArray(pedToSp)) {
    return getResponse({ error: 'Provide at least one of: skillPointsToPED, pedToSkillPoints (arrays of numbers).' }, 400);
  }

  const totalItems = (spToPed?.length || 0) + (pedToSp?.length || 0);
  if (totalItems > MAX_BATCH_SIZE) {
    return getResponse({ error: `Batch too large. Maximum ${MAX_BATCH_SIZE} total conversions per request.` }, 400);
  }

  const err = validateArray(spToPed, 'skillPointsToPED') || validateArray(pedToSp, 'pedToSkillPoints');
  if (err) return getResponse({ error: err }, 400);

  const result = {};
  if (spToPed) result.skillPointsToPED = batchSkillPointsToPED(spToPed);
  if (pedToSp) result.pedToSkillPoints = batchPedToSkillPoints(pedToSp);

  return new Response(JSON.stringify(result), {
    status: 200,
    headers: { 'Content-Type': 'application/json', ...getRateLimitHeaders(RATE_LIMIT, rateCheck.remaining, rateCheck.resetIn) }
  });
}

function validateArray(arr, name) {
  if (!arr) return null;
  if (!Array.isArray(arr)) return `${name} must be an array.`;
  for (let i = 0; i < arr.length; i++) {
    if (typeof arr[i] !== 'number' || !Number.isFinite(arr[i]) || arr[i] < 0) {
      return `${name}[${i}] must be a non-negative finite number.`;
    }
  }
  return null;
}

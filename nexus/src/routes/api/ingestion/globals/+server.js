//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';
import { checkRateLimit, getRateLimitHeaders, checkConcurrentUploads, startUpload, endUpload } from '$lib/server/rateLimiter.js';
import {
  isIngestionAllowed,
  isIngestionBanned,
  validateGlobalEvent,
  ingestGlobals,
  getGlobalsSince,
  parseRequestBody,
  maybeRunFraudDetection,
} from '$lib/server/ingestion.js';

const MAX_BATCH_SIZE = 500;
const GET_RATE_LIMIT_MAX = 30;
const GET_RATE_LIMIT_WINDOW = 60_000; // 30 requests per 60 seconds
const RATE_LIMIT_MAX = 20;
const RATE_LIMIT_WINDOW = 60_000; // 20 requests per 60 seconds

/**
 * POST /api/ingestion/globals — Submit a batch of global events.
 * OAuth required, no specific scopes needed. Must be verified and not ingestion-banned.
 */
export async function POST({ request, locals }) {
  const user = requireVerifiedAPI(locals);

  // Rate limit (admins bypass)
  const isAdmin = user.grants?.includes('admin.panel');
  if (!isAdmin) {
    const rl = checkRateLimit(`ingest-globals:${user.id}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW);
    if (!rl.allowed) {
      return getResponse(
        { error: 'Rate limited', retryAfter: Math.ceil(rl.resetIn / 1000) },
        429
      );
    }
  }

  // Concurrent upload guard (1 per user per endpoint)
  const uploadKey = `ingest-globals:${user.id}`;
  if (!checkConcurrentUploads(uploadKey, 1)) {
    return getResponse({ error: 'Concurrent ingestion in progress' }, 409);
  }
  startUpload(uploadKey);

  try {
    // Allowlist check (OAuth client application must be approved)
    if (!(await isIngestionAllowed(locals.oauthClientId || null))) {
      return getResponse({ error: 'This application is not authorized for ingestion' }, 403);
    }
    if (await isIngestionBanned(user.id)) {
      return getResponse({ error: 'Ingestion access revoked' }, 403);
    }

    // Parse body (supports gzip)
    let body;
    try {
      body = await parseRequestBody(request);
    } catch (e) {
      return getResponse({ error: 'Invalid request body' }, 400);
    }

    const events = body?.globals;
    if (!Array.isArray(events) || events.length === 0) {
      return getResponse({ error: 'Missing or empty globals array' }, 400);
    }
    if (events.length > MAX_BATCH_SIZE) {
      return getResponse({ error: `Batch too large (max ${MAX_BATCH_SIZE})` }, 400);
    }

    // Validate each event
    const validEvents = [];
    const errors = [];
    for (let i = 0; i < events.length; i++) {
      const err = validateGlobalEvent(events[i]);
      if (err) {
        errors.push({ index: i, error: err });
      } else {
        validEvents.push(events[i]);
      }
    }

    if (validEvents.length === 0) {
      return getResponse({ error: 'No valid events in batch', details: errors }, 400);
    }

    // Process
    const result = await ingestGlobals(user.id, validEvents);
    if (result.rejected) {
      return getResponse({ error: result.reason }, 400);
    }
    maybeRunFraudDetection();
    const response = {
      ...result,
      total: events.length,
      invalid: errors.length,
    };
    if (errors.length > 0) response.errors = errors;
    return getResponse(response, 200);
  } catch (e) {
    console.error('[ingestion] Failed to ingest globals:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  } finally {
    endUpload(uploadKey);
  }
}

/**
 * GET /api/ingestion/globals — Distribution endpoint.
 * Returns all global events newer than `since`, each with a `confirmed` flag.
 */
export async function GET({ url, locals, request }) {
  const ip = locals.ip || request.headers.get('x-forwarded-for') || request.headers.get('cf-connecting-ip') || 'unknown';

  const rl = checkRateLimit(`ingest-get-globals:${ip}`, GET_RATE_LIMIT_MAX, GET_RATE_LIMIT_WINDOW);
  if (!rl.allowed) {
    return getResponse(
      { error: 'Rate limited', retryAfter: Math.ceil(rl.resetIn / 1000) },
      429
    );
  }

  const since = url.searchParams.get('since');
  if (!since) {
    return getResponse({ error: 'Missing required parameter: since' }, 400);
  }

  const sinceDate = new Date(since);
  if (isNaN(sinceDate.getTime())) {
    return getResponse({ error: 'Invalid since timestamp' }, 400);
  }

  const limit = Math.min(parseInt(url.searchParams.get('limit') || '200') || 200, 1000);

  try {
    const rows = await getGlobalsSince(sinceDate.toISOString(), limit);

    const globals = rows.map(r => ({
      id: r.id,
      type: r.global_type,
      player: r.player_name,
      target: r.target_name,
      value: r.value != null ? parseFloat(r.value) : null,
      unit: r.value_unit,
      location: r.location,
      hof: r.is_hof,
      ath: r.is_ath,
      timestamp: r.event_timestamp,
      confirmations: r.confirmation_count,
      confirmed: r.confirmed,
      occurrence: r.occurrence,
    }));

    const cursor = rows.length > 0
      ? rows[rows.length - 1].first_seen_at
      : since;

    return getResponse({ globals, cursor }, 200);
  } catch (e) {
    console.error('[ingestion] Failed to fetch globals:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}

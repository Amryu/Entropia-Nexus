//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';
import { checkRateLimit, checkConcurrentUploads, startUpload, endUpload } from '$lib/server/rateLimiter.js';
import {
  isIngestionAllowed,
  isIngestionBanned,
  validateTradeMessage,
  ingestTrades,
  getTradesSince,
  parseRequestBody,
  maybeRunFraudDetection,
} from '$lib/server/ingestion.js';

const MAX_BATCH_SIZE = 500;
const GET_RATE_LIMIT_MAX = 30;
const GET_RATE_LIMIT_WINDOW = 60_000; // 30 requests per 60 seconds
const RATE_LIMIT_MAX = 20;
const RATE_LIMIT_WINDOW = 60_000; // 20 requests per 60 seconds

/**
 * POST /api/ingestion/trade — Submit a batch of trade messages.
 * OAuth required, no specific scopes needed.
 */
export async function POST({ request, locals }) {
  const user = requireVerifiedAPI(locals);

  // Rate limit (admins bypass)
  const isAdmin = user.grants?.includes('admin.panel');
  if (!isAdmin) {
    const rl = checkRateLimit(`ingest-trade:${user.id}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW);
    if (!rl.allowed) {
      return getResponse(
        { error: 'Rate limited', retryAfter: Math.ceil(rl.resetIn / 1000) },
        429
      );
    }
  }

  // Concurrent upload guard (1 per user per endpoint)
  const uploadKey = `ingest-trade:${user.id}`;
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

    let body;
    try {
      body = await parseRequestBody(request);
    } catch (e) {
      return getResponse({ error: 'Invalid request body' }, 400);
    }

    const messages = body?.trades;
    if (!Array.isArray(messages) || messages.length === 0) {
      return getResponse({ error: 'Missing or empty trades array' }, 400);
    }
    if (messages.length > MAX_BATCH_SIZE) {
      return getResponse({ error: `Batch too large (max ${MAX_BATCH_SIZE})` }, 400);
    }

    const validMessages = [];
    const errors = [];
    for (let i = 0; i < messages.length; i++) {
      const err = await validateTradeMessage(messages[i]);
      if (err) {
        errors.push({ index: i, error: err });
      } else {
        validMessages.push(messages[i]);
      }
    }

    if (validMessages.length === 0) {
      return getResponse({ error: 'No valid messages in batch', details: errors }, 400);
    }

    const result = await ingestTrades(user.id, validMessages);
    if (result.rejected) {
      return getResponse({ error: result.reason }, 400);
    }
    maybeRunFraudDetection();
    const response = {
      ...result,
      total: messages.length,
      invalid: errors.length,
    };
    if (errors.length > 0) response.errors = errors;
    return getResponse(response, 200);
  } catch (e) {
    console.error('[ingestion] Failed to ingest trades:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  } finally {
    endUpload(uploadKey);
  }
}

/**
 * GET /api/ingestion/trade — Distribution endpoint.
 * Returns all trade messages newer than `since` with confirmation_count.
 */
export async function GET({ url, locals }) {
  const user = requireVerifiedAPI(locals);

  const rl = checkRateLimit(`ingest-get-trade:${user.id}`, GET_RATE_LIMIT_MAX, GET_RATE_LIMIT_WINDOW);
  if (!rl.allowed) {
    return getResponse(
      { error: 'Rate limited', retryAfter: Math.ceil(rl.resetIn / 1000) },
      429
    );
  }

  if (await isIngestionBanned(user.id)) {
    return getResponse({ error: 'Ingestion access revoked' }, 403);
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
    const rows = await getTradesSince(sinceDate.toISOString(), limit);

    const trades = rows.map(r => ({
      id: r.id,
      channel: r.channel,
      username: r.username,
      message: r.message,
      timestamp: r.event_timestamp,
      confirmations: r.confirmation_count,
    }));

    const cursor = rows.length > 0
      ? rows[rows.length - 1].first_seen_at
      : since;

    return getResponse({ trades, cursor }, 200);
  } catch (e) {
    console.error('[ingestion] Failed to fetch trades:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}

//@ts-nocheck
import { getPromoById, updatePromo, deletePromo, hasActivePromoBookings, getPromoImages } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';
import { sanitizeRichText } from '$lib/server/sanitizeRichText.js';

const MAX_NAME_LENGTH = 100;
const MAX_SUMMARY_LENGTH = 500;
const MAX_LINK_LENGTH = 500;
const MAX_CONTENT_HTML_LENGTH = 50_000;

function containsHtmlTags(str) {
  return /<[^>]*>/g.test(str);
}

// GET promo by ID (owner check)
export async function GET({ params, locals }) {
  const user = requireVerifiedAPI(locals);

  const promoId = parseInt(params.id);
  if (isNaN(promoId)) {
    return getResponse({ error: 'Invalid promo ID.' }, 400);
  }

  try {
    const promo = await getPromoById(promoId);
    if (!promo) {
      return getResponse({ error: 'Promo not found.' }, 404);
    }

    if (String(promo.owner_id) !== String(user.id) && !user.grants?.includes('admin.panel')) {
      return getResponse({ error: 'You do not have permission to view this promo.' }, 403);
    }

    promo.images = await getPromoImages(promoId);
    return getResponse(promo, 200);
  } catch (err) {
    console.error('Error fetching promo:', err);
    return getResponse({ error: 'Failed to fetch promo.' }, 500);
  }
}

// PUT update promo (owner check)
export async function PUT({ params, request, locals }) {
  const user = requireVerifiedAPI(locals);

  const rateCheck = checkRateLimit(`promos:update:${user.id}`, 20, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const promoId = parseInt(params.id);
  if (isNaN(promoId)) {
    return getResponse({ error: 'Invalid promo ID.' }, 400);
  }

  const promo = await getPromoById(promoId);
  if (!promo) {
    return getResponse({ error: 'Promo not found.' }, 404);
  }

  if (String(promo.owner_id) !== String(user.id) && !user.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only edit your own promos.' }, 403);
  }

  const hasActive = await hasActivePromoBookings(promoId);
  if (hasActive) {
    return getResponse({ error: 'Cannot modify a promo with active bookings.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  // Build update fields (only allowed pending fields)
  const fields = {};

  if (body.name !== undefined) {
    const name = body.name?.trim();
    if (!name) {
      return getResponse({ error: 'Promo name cannot be empty.' }, 400);
    }
    if (name.length > MAX_NAME_LENGTH) {
      return getResponse({ error: `Promo name cannot exceed ${MAX_NAME_LENGTH} characters.` }, 400);
    }
    if (containsHtmlTags(name)) {
      return getResponse({ error: 'Name cannot contain HTML tags.' }, 400);
    }
    fields.name = name;
  }

  if (body.title !== undefined) {
    const title = body.title?.trim() || null;
    if (title && containsHtmlTags(title)) {
      return getResponse({ error: 'Title cannot contain HTML tags.' }, 400);
    }
    fields.title = title;
  }

  if (body.summary !== undefined) {
    const summary = body.summary?.trim() || null;
    if (summary && containsHtmlTags(summary)) {
      return getResponse({ error: 'Summary cannot contain HTML tags.' }, 400);
    }
    if (summary && summary.length > MAX_SUMMARY_LENGTH) {
      return getResponse({ error: `Summary cannot exceed ${MAX_SUMMARY_LENGTH} characters.` }, 400);
    }
    fields.summary = summary;
  }

  if (body.link !== undefined) {
    const link = body.link?.trim() || null;
    if (link && link.length > MAX_LINK_LENGTH) {
      return getResponse({ error: `Link cannot exceed ${MAX_LINK_LENGTH} characters.` }, 400);
    }
    if (link) {
      try {
        const parsedLink = new URL(link);
        if (parsedLink.protocol !== 'http:' && parsedLink.protocol !== 'https:') {
          return getResponse({ error: 'Link must use http or https protocol.' }, 400);
        }
      } catch {
        return getResponse({ error: 'Link must be a valid URL.' }, 400);
      }
    }
    fields.link = link;
  }

  if (body.content_html !== undefined) {
    if (body.content_html && body.content_html.length > MAX_CONTENT_HTML_LENGTH) {
      return getResponse({ error: `Content HTML cannot exceed ${MAX_CONTENT_HTML_LENGTH} characters.` }, 400);
    }
    fields.content_html = body.content_html ? (sanitizeRichText(body.content_html) || null) : null;
  }

  if (Object.keys(fields).length === 0) {
    return getResponse({ error: 'No valid fields to update.' }, 400);
  }

  try {
    const updated = await updatePromo(promoId, fields);
    return getResponse(updated, 200);
  } catch (err) {
    console.error('Error updating promo:', err);
    return getResponse({ error: 'Failed to update promo.' }, 500);
  }
}

// DELETE promo (owner check, no active bookings)
export async function DELETE({ params, locals }) {
  const user = requireVerifiedAPI(locals);

  const rateCheck = checkRateLimit(`promos:delete:${user.id}`, 5, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const promoId = parseInt(params.id);
  if (isNaN(promoId)) {
    return getResponse({ error: 'Invalid promo ID.' }, 400);
  }

  const promo = await getPromoById(promoId);
  if (!promo) {
    return getResponse({ error: 'Promo not found.' }, 404);
  }

  if (String(promo.owner_id) !== String(user.id) && !user.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only delete your own promos.' }, 403);
  }

  const hasActive = await hasActivePromoBookings(promoId);
  if (hasActive) {
    return getResponse({ error: 'Cannot delete promo with active bookings. Cancel or wait for bookings to expire first.' }, 400);
  }

  try {
    await deletePromo(promoId);
    return getResponse({ success: true, message: 'Promo deleted successfully.' }, 200);
  } catch (err) {
    console.error('Error deleting promo:', err);
    return getResponse({ error: 'Failed to delete promo.' }, 500);
  }
}

//@ts-nocheck
import { getPromosByOwner, createPromo } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';
import { sanitizeRichText } from '$lib/server/sanitizeRichText.js';

const VALID_PROMO_TYPES = ['placement', 'featured_post'];
const MAX_NAME_LENGTH = 100;
const MAX_SUMMARY_LENGTH = 500;
const MAX_LINK_LENGTH = 500;
const MAX_CONTENT_HTML_LENGTH = 50_000;

function containsHtmlTags(str) {
  return /<[^>]*>/g.test(str);
}

// GET list current user's promos
export async function GET({ locals }) {
  const user = requireVerifiedAPI(locals);

  try {
    const promos = await getPromosByOwner(user.id);
    return getResponse(promos, 200);
  } catch (err) {
    console.error('Error fetching promos:', err);
    return getResponse({ error: 'Failed to fetch promos.' }, 500);
  }
}

// POST create new promo
export async function POST({ request, locals }) {
  const user = requireVerifiedAPI(locals);

  const rateCheck = checkRateLimit(`promos:create:${user.id}`, 10, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  // Validate promo_type
  if (!body.promo_type || !VALID_PROMO_TYPES.includes(body.promo_type)) {
    return getResponse({ error: `Invalid promo type. Must be one of: ${VALID_PROMO_TYPES.join(', ')}.` }, 400);
  }

  // Validate name (required)
  const name = body.name?.trim();
  if (!name) {
    return getResponse({ error: 'Promo name is required.' }, 400);
  }
  if (name.length > MAX_NAME_LENGTH) {
    return getResponse({ error: `Promo name cannot exceed ${MAX_NAME_LENGTH} characters.` }, 400);
  }

  // Validate optional fields
  const title = body.title?.trim() || null;
  const summary = body.summary?.trim() || null;
  if (title && containsHtmlTags(title)) {
    return getResponse({ error: 'Title cannot contain HTML tags.' }, 400);
  }
  if (summary && containsHtmlTags(summary)) {
    return getResponse({ error: 'Summary cannot contain HTML tags.' }, 400);
  }
  if (name && containsHtmlTags(name)) {
    return getResponse({ error: 'Name cannot contain HTML tags.' }, 400);
  }
  const link = body.link?.trim() || null;
  if (body.content_html && body.content_html.length > MAX_CONTENT_HTML_LENGTH) {
    return getResponse({ error: `Content HTML cannot exceed ${MAX_CONTENT_HTML_LENGTH} characters.` }, 400);
  }
  const contentHtml = body.content_html ? (sanitizeRichText(body.content_html) || null) : null;

  if (summary && summary.length > MAX_SUMMARY_LENGTH) {
    return getResponse({ error: `Summary cannot exceed ${MAX_SUMMARY_LENGTH} characters.` }, 400);
  }
  // Placement promos require a link (click-through destination)
  if (body.promo_type === 'placement' && !link) {
    return getResponse({ error: 'Placement promos require a link URL.' }, 400);
  }
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

  try {
    const promo = await createPromo({
      ownerId: user.id,
      promoType: body.promo_type,
      name,
      title,
      summary,
      link,
      contentHtml
    });
    return getResponse(promo, 201);
  } catch (err) {
    console.error('Error creating promo:', err);
    return getResponse({ error: 'Failed to create promo.' }, 500);
  }
}

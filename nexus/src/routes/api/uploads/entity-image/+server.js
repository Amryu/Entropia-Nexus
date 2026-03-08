/**
 * API endpoint for entity image uploads.
 * Handles multipart form data with image file.
 *
 * Security measures:
 * - Authentication required
 * - Rate limiting per user (10 uploads per 5 minutes)
 * - Concurrent upload limiting (max 3 simultaneous)
 * - Request size limit (3MB max)
 * - File type validation (MIME type check)
 * - Magic byte verification in processor
 * - Path traversal prevention
 */
// @ts-nocheck
import { error } from '@sveltejs/kit';
import { processAndSaveImage, approveImage, isAutoApproveType, computeImageHash, getApprovedImagePath } from '$lib/server/imageProcessor.js';
import {
  checkRateLimit,
  getRateLimitHeaders,
  checkConcurrentUploads,
  startUpload,
  endUpload
} from '$lib/server/rateLimiter.js';
import { getUserItemSetById, notifyAdmins } from '$lib/server/db.js';

// Rate limit configuration
const RATE_LIMIT_MAX = 50; // Max uploads
const RATE_LIMIT_WINDOW = 5 * 60 * 1000; // 5 minutes

// Max request body size (slightly larger than max file to account for form data)
const MAX_REQUEST_SIZE = 3 * 1024 * 1024; // 3MB

// Max concurrent uploads per user
const MAX_CONCURRENT = 3;

// Allowed MIME types (additional check before processing)
const ALLOWED_MIME_TYPES = [
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/gif'
];

/** @type {import('./$types').RequestHandler} */
export async function POST({ request, locals }) {
  // 1. Check authentication
  const user = locals.session?.user;
  if (!user) {
    throw error(401, 'Authentication required');
  }

  // 2. Check verified status
  if (!user.verified) {
    throw error(403, 'Account verification required to upload images');
  }

  const userId = String(user.Id || user.id);
  const rateLimitKey = `upload:${userId}`;

  // 3. Check rate limit
  const rateCheck = checkRateLimit(rateLimitKey, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW);
  const rateLimitHeaders = getRateLimitHeaders(RATE_LIMIT_MAX, rateCheck.remaining, rateCheck.resetIn);

  if (!rateCheck.allowed) {
    return new Response(JSON.stringify({
      error: 'Too many upload requests. Please try again later.',
      retryAfter: Math.ceil(rateCheck.resetIn / 1000)
    }), {
      status: 429,
      headers: {
        'Content-Type': 'application/json',
        'Retry-After': String(Math.ceil(rateCheck.resetIn / 1000)),
        ...rateLimitHeaders
      }
    });
  }

  // 4. Check concurrent uploads
  if (!checkConcurrentUploads(userId, MAX_CONCURRENT)) {
    return new Response(JSON.stringify({
      error: 'Too many concurrent uploads. Please wait for current uploads to complete.'
    }), {
      status: 429,
      headers: {
        'Content-Type': 'application/json',
        ...rateLimitHeaders
      }
    });
  }

  // 5. Check content-length header before reading body
  const contentLength = request.headers.get('content-length');
  if (contentLength && parseInt(contentLength) > MAX_REQUEST_SIZE) {
    throw error(413, `Request too large. Maximum size is ${MAX_REQUEST_SIZE / 1024 / 1024}MB`);
  }

  // Track this upload
  startUpload(userId);

  try {
    // 6. Parse form data with size check
    let formData;
    try {
      formData = await request.formData();
    } catch (parseError) {
      // Handle oversized or malformed requests
      if (parseError.message?.includes('size') || parseError.message?.includes('limit')) {
        throw error(413, 'Request body too large');
      }
      throw error(400, 'Invalid form data');
    }

    const imageFile = formData.get('image');
    const entityType = formData.get('entityType');
    let entityId = formData.get('entityId');
    const entityName = formData.get('entityName') || null;
    const autoApprove = formData.get('autoApprove') === 'true';

    // 7. Validate required fields
    if (!imageFile || !(imageFile instanceof File)) {
      throw error(400, 'Image file is required');
    }

    if (!entityType || typeof entityType !== 'string') {
      throw error(400, 'Entity type is required');
    }

    if (!entityId) {
      throw error(400, 'Entity ID is required');
    }

    // 8. Validate entity type format (alphanumeric and hyphens)
    if (!/^[a-zA-Z][a-zA-Z\-]*$/.test(entityType)) {
      throw error(400, 'Invalid entity type format');
    }

    // 8a. Block user type — profile images use /api/image/user/{userId} with ownership checks
    if (entityType === 'user') {
      throw error(400, 'Use /api/image/user/{userId} for profile images');
    }

    // 8b. Permission checks for auto-approved types (these bypass admin review)
    if (entityType === 'announcement') {
      if (!user.grants?.includes('admin.panel')) {
        throw error(403, 'Only administrators can upload announcement images');
      }
    }

    if (entityType === 'guide-category') {
      if (!user.grants?.includes('guide.edit') && !user.grants?.includes('admin.panel')) {
        throw error(403, 'Guide editing permission required to upload guide images');
      }
    }

    // 8b. For item-set images, verify ownership and that set contains (C) items
    if (entityType === 'item-set') {
      const itemSet = await getUserItemSetById(userId, entityId);
      if (!itemSet) {
        throw error(404, 'Item set not found');
      }
      const items = itemSet.data?.items || [];
      const hasCTag = items.some(item =>
        item.setName
          ? item.pieces?.some(p => /\(([^)]*,)?C(,[^)]*)?\)$/.test(p.name))
          : /\(([^)]*,)?C(,[^)]*)?\)$/.test(item.name)
      );
      if (!hasCTag) {
        throw error(400, 'Custom image upload requires at least one item with a (C) tag');
      }
    }

    // 9. Validate file size
    if (imageFile.size > MAX_REQUEST_SIZE) {
      throw error(413, 'Image file too large');
    }

    // 10. Validate MIME type
    if (!ALLOWED_MIME_TYPES.includes(imageFile.type)) {
      throw error(400, `Invalid file type. Allowed: ${ALLOWED_MIME_TYPES.join(', ')}`);
    }

    // 11. Get image buffer
    let buffer;
    try {
      const arrayBuffer = await imageFile.arrayBuffer();
      buffer = Buffer.from(arrayBuffer);
    } catch (bufferError) {
      throw error(400, 'Failed to read image file');
    }

    // 12. Double-check buffer size
    if (buffer.length > MAX_REQUEST_SIZE) {
      throw error(413, 'Image file too large');
    }

    // 12a. For richtext images, use content hash as entity ID for deduplication
    let imageHash = null;
    if (entityType === 'richtext') {
      imageHash = computeImageHash(buffer);
      entityId = imageHash;

      // Check if an approved image with this hash already exists
      const existingPath = getApprovedImagePath('richtext', imageHash);
      if (existingPath) {
        return new Response(JSON.stringify({
          success: true,
          approved: true,
          hash: imageHash,
          imageUrl: `/api/img/richtext/${imageHash}`
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json', ...rateLimitHeaders }
        });
      }
    }

    // 13. Process and save the image (additional validations happen here)
    const result = await processAndSaveImage(buffer, entityType, entityId, userId, entityName);

    // 14. Auto-approve: type-based (guide-category) or grant-based (richtext with user grant)
    let approved = false;
    if (isAutoApproveType(entityType)) {
      await approveImage(entityType, entityId);
      approved = true;
    } else if (autoApprove && entityType === 'richtext') {
      const hasApproveGrant = user.grants?.includes('wiki.approve') || user.grants?.includes('guide.edit');
      if (hasApproveGrant) {
        await approveImage(entityType, entityId);
        approved = true;
      }
    } else if (user.grants?.includes('admin.panel')) {
      // Admins skip the approval queue
      await approveImage(entityType, entityId);
      approved = true;
    }

    if (!approved) {
      const displayName = user.eu_name || user.global_name || user.username;
      const label = entityName || entityId;
      notifyAdmins(`${displayName} uploaded an image for review: ${entityType} "${label}"`).catch(() => {});
    }

    return new Response(JSON.stringify({
      success: true,
      approved,
      tempPath: result.tempPath,
      previewUrl: result.previewUrl,
      ...(imageHash ? { hash: imageHash, imageUrl: `/api/img/richtext/${imageHash}` } : {})
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        ...rateLimitHeaders
      }
    });
  } catch (err) {
    console.error('Image upload error:', err);

    // Return structured error response
    if (err.status) {
      throw err;
    }

    // Map common errors to appropriate status codes
    const message = err.message || 'Failed to process image';

    if (message.includes('Invalid') || message.includes('must be')) {
      throw error(400, message);
    }

    if (message.includes('limit') || message.includes('too large')) {
      throw error(413, message);
    }

    console.error('Unhandled upload error:', message);
    throw error(500, 'Failed to process image');
  } finally {
    // Always decrement concurrent upload counter
    endUpload(userId);
  }
}

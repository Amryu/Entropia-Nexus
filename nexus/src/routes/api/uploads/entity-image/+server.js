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
import { processAndSaveImage, approveImage, isAutoApproveType } from '$lib/server/imageProcessor.js';
import {
  checkRateLimit,
  getRateLimitHeaders,
  checkConcurrentUploads,
  startUpload,
  endUpload
} from '$lib/server/rateLimiter.js';

// Rate limit configuration
const RATE_LIMIT_MAX = 10; // Max uploads
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
    const entityId = formData.get('entityId');

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

    // 13. Process and save the image (additional validations happen here)
    const result = await processAndSaveImage(buffer, entityType, entityId, userId);

    // 14. Auto-approve guide images (skip approval workflow)
    if (isAutoApproveType(entityType)) {
      await approveImage(entityType, entityId);
    }

    return new Response(JSON.stringify({
      success: true,
      tempPath: result.tempPath,
      previewUrl: result.previewUrl
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

    throw error(500, message);
  } finally {
    // Always decrement concurrent upload counter
    endUpload(userId);
  }
}

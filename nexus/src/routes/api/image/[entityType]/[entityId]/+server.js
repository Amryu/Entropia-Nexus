// @ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  processAndSaveImage,
  approveImage,
  deleteApprovedImage,
  getApprovedImagePath
} from '$lib/server/imageProcessor.js';
import {
  checkRateLimit,
  checkConcurrentUploads,
  startUpload,
  endUpload
} from '$lib/server/rateLimiter.js';
import { r2Enabled, getFromR2 } from '$lib/server/r2Storage.js';
import { existsSync, statSync } from 'fs';
import { readFile } from 'fs/promises';

const CACHE_MAX_AGE = 86400;

// Profile image upload limits
const RATE_LIMIT_MAX = 10;
const RATE_LIMIT_WINDOW = 5 * 60 * 1000; // 5 minutes
const MAX_REQUEST_SIZE = 3 * 1024 * 1024; // 3MB
const MAX_CONCURRENT = 2;

/** @type {import('./$types').RequestHandler} */
export async function GET({ params }) {
  const { entityType, entityId } = params;
  if (!entityType || !entityId) {
    return getResponse({ error: 'Invalid image request.' }, 400);
  }

  const type = entityType.toLowerCase();

  // Try R2 first
  if (r2Enabled) {
    const r2Buffer = await getFromR2(`${type}/${entityId}/icon.webp`);
    if (r2Buffer) {
      return new Response(r2Buffer, {
        status: 200,
        headers: {
          'Content-Type': 'image/webp',
          'Content-Length': String(r2Buffer.length),
          'Cache-Control': `public, max-age=${CACHE_MAX_AGE}`,
          'ETag': `"r2-${r2Buffer.length}"`
        }
      });
    }
  }

  // Fall back to local disk
  const imagePath = getApprovedImagePath(type, entityId, 'icon');
  if (!imagePath || !existsSync(imagePath)) {
    return new Response(null, { status: 204 });
  }

  try {
    const stats = statSync(imagePath);
    const imageBuffer = await readFile(imagePath);
    const etag = `"${stats.size}-${stats.mtimeMs}"`;
    return new Response(imageBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'image/webp',
        'Content-Length': String(imageBuffer.length),
        'Cache-Control': `public, max-age=${CACHE_MAX_AGE}`,
        'ETag': etag,
        'Last-Modified': stats.mtime.toUTCString()
      }
    });
  } catch (error) {
    console.error('Error serving image:', error);
    return new Response('Error serving image', { status: 500 });
  }
}

/** @type {import('./$types').RequestHandler} */
export async function POST({ params, request, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const { entityType, entityId } = params;
  if (!entityType || !entityId) {
    return getResponse({ error: 'Invalid image request.' }, 400);
  }

  const type = entityType.toLowerCase();
  if (type !== 'user' && type !== 'user-banner' && type !== 'user-background') {
    return getResponse({ error: 'Only user images are supported.' }, 400);
  }

  const userId = String(user.Id || user.id);
  if (String(entityId) !== userId && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only update your own profile image.' }, 403);
  }

  // Rate limiting
  const rateCheck = checkRateLimit(`profile-upload:${userId}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many upload requests. Please try again later.' }, 429);
  }

  // Concurrent upload limit
  if (!checkConcurrentUploads(userId, MAX_CONCURRENT)) {
    return getResponse({ error: 'Too many concurrent uploads.' }, 429);
  }

  // Content-Length pre-check
  const contentLength = request.headers.get('content-length');
  if (contentLength && parseInt(contentLength) > MAX_REQUEST_SIZE) {
    return getResponse({ error: 'Request too large.' }, 413);
  }

  startUpload(userId);
  try {
    let formData;
    try {
      formData = await request.formData();
    } catch {
      return getResponse({ error: 'Invalid form data.' }, 400);
    }

    const imageFile = formData.get('image');
    if (!imageFile || !(imageFile instanceof File)) {
      return getResponse({ error: 'Image file is required.' }, 400);
    }

    const arrayBuffer = await imageFile.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    await processAndSaveImage(buffer, type, entityId, userId);
    await approveImage(type, entityId);
    return getResponse({ success: true }, 200);
  } catch (err) {
    console.error('Profile image upload error:', err);
    return getResponse({ error: 'Failed to upload image.' }, 500);
  } finally {
    endUpload(userId);
  }
}

/** @type {import('./$types').RequestHandler} */
export async function DELETE({ params, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const { entityType, entityId } = params;
  if (!entityType || !entityId) {
    return getResponse({ error: 'Invalid image request.' }, 400);
  }

  const type = entityType.toLowerCase();
  if (type !== 'user' && type !== 'user-banner' && type !== 'user-background') {
    return getResponse({ error: 'Only user images are supported.' }, 400);
  }

  const userId = String(user.Id || user.id);
  if (String(entityId) !== userId && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only delete your own profile image.' }, 403);
  }

  try {
    await deleteApprovedImage(type, entityId);
  } catch (err) {
    if (err?.message?.includes('Approved image not found')) {
      return getResponse({ success: true }, 200);
    }
    console.error('Profile image delete error:', err);
    return getResponse({ error: 'Failed to delete image.' }, 500);
  }

  return getResponse({ success: true }, 200);
}

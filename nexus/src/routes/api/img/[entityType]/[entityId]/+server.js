/**
 * API endpoint for serving entity images.
 * Reads from Cloudflare R2 first, falls back to local filesystem.
 *
 * GET /api/img/:entityType/:entityId - Serves the icon image
 * GET /api/img/:entityType/:entityId?type=thumb - Serves the thumbnail
 * GET /api/img/:entityType/:entityId?size=32|48|64|128|320 - Resized thumbnail (cached to disk)
 * GET /api/img/:entityType/:entityId?mode=dark|light - Enhanced icon with trim/scale/backdrop
 */
import { getApprovedImagePath, buildApprovedImagePath, isValidEntityType } from '$lib/server/imageProcessor.js';
import { enhanceEntityImage } from '$lib/server/imageEnhancer.js';
import { r2Enabled, getFromR2 } from '$lib/server/r2Storage.js';
import { existsSync, statSync } from 'fs';
import { readFile, writeFile, mkdir } from 'fs/promises';
import { dirname } from 'path';

// Cache duration: 1 day for approved images (they rarely change)
const CACHE_MAX_AGE = 86400;

const VALID_MODES = ['dark', 'light'];
const VALID_SIZES = new Set([32, 48, 64, 128, 320]);

export async function GET({ params, url }) {
  const { entityType, entityId } = params;
  const type = url.searchParams.get('type') || 'icon';
  const mode = url.searchParams.get('mode');
  const sizeParam = url.searchParams.get('size');

  // Validate entity type
  if (!isValidEntityType(entityType)) {
    return new Response('Invalid entity type', { status: 400 });
  }

  // Validate type parameter
  if (type !== 'icon' && type !== 'thumb') {
    return new Response('Invalid type. Must be "icon" or "thumb"', { status: 400 });
  }

  // Validate size parameter (optional, mutually exclusive with mode)
  const size = sizeParam ? parseInt(sizeParam, 10) : null;
  if (size !== null && !VALID_SIZES.has(size)) {
    return new Response('Invalid size. Must be 32, 48, 64, 128, or 320', { status: 400 });
  }

  // Validate mode parameter (optional)
  if (mode !== null && !VALID_MODES.includes(mode)) {
    return new Response('Invalid mode. Must be "dark" or "light"', { status: 400 });
  }

  // Validate entity ID (prevent path traversal)
  if (!entityId || !/^[\w\s\-]+$/.test(entityId) || entityId.length > 200) {
    return new Response('Invalid entity ID', { status: 400 });
  }

  const lowerType = entityType.toLowerCase();
  const r2Prefix = `${lowerType}/${entityId}`;

  // --- Size variant request ---
  if (size) {
    // Try R2 first for pre-generated variant
    if (r2Enabled) {
      const r2Buffer = await getFromR2(`${r2Prefix}/s${size}.webp`);
      if (r2Buffer) {
        return serveBuffer(r2Buffer, `"r2-s${size}-${r2Buffer.length}"`);
      }
    }

    // Try local disk cache
    const cachedPath = buildApprovedImagePath(lowerType, entityId, `s${size}`);
    if (existsSync(cachedPath)) {
      return serveFile(cachedPath, size);
    }

    // Generate on-demand from local source
    const sourceType = 'thumb';
    const thumbPath = getApprovedImagePath(lowerType, entityId, sourceType);
    if (thumbPath && existsSync(thumbPath)) {
      return resizeAndServe(thumbPath, lowerType, entityId, size);
    }
    const iconPath = getApprovedImagePath(lowerType, entityId, 'icon');
    if (iconPath && existsSync(iconPath)) {
      return resizeAndServe(iconPath, lowerType, entityId, size);
    }

    return new Response(null, { status: 204 });
  }

  // --- Icon/thumb request (possibly with mode enhancement) ---

  // Try R2 first for the base image
  let imageBuffer = null;
  let etag = null;

  if (r2Enabled) {
    imageBuffer = await getFromR2(`${r2Prefix}/${type}.webp`);
    if (imageBuffer) {
      etag = `"r2-${type}-${imageBuffer.length}"`;
    }
  }

  // Fall back to local disk
  if (!imageBuffer) {
    const imagePath = getApprovedImagePath(lowerType, entityId, type);
    if (!imagePath || !existsSync(imagePath)) {
      return new Response(null, { status: 204 });
    }

    try {
      const stats = statSync(imagePath);
      imageBuffer = await readFile(imagePath);
      etag = `"${stats.size}-${stats.mtimeMs}"`;
    } catch (error) {
      console.error('Error reading image:', error);
      return new Response('Error serving image', { status: 500 });
    }
  }

  // Apply enhancement pipeline for icons when mode is specified
  let outputBuffer = imageBuffer;
  if (mode && type === 'icon') {
    try {
      outputBuffer = await enhanceEntityImage(imageBuffer, mode);
    } catch {
      // Enhancement failed — serve original image
      outputBuffer = imageBuffer;
    }
    // Include mode in ETag so CDN caches dark/light variants separately
    etag = mode ? `${etag.slice(0, -1)}-${mode}"` : etag;
  }

  return new Response(outputBuffer, {
    status: 200,
    headers: {
      'Content-Type': 'image/webp',
      'Content-Length': String(outputBuffer.length),
      'Cache-Control': `public, max-age=${CACHE_MAX_AGE}`,
      'ETag': etag
    }
  });
}

/**
 * Serve a Buffer directly with cache headers.
 */
function serveBuffer(buffer, etag) {
  return new Response(buffer, {
    status: 200,
    headers: {
      'Content-Type': 'image/webp',
      'Content-Length': String(buffer.length),
      'Cache-Control': `public, max-age=${CACHE_MAX_AGE}`,
      'ETag': etag
    }
  });
}

/**
 * Resize source image to requested size, cache to disk, and serve.
 */
async function resizeAndServe(sourcePath, entityType, entityId, size) {
  try {
    const sharp = (await import('sharp')).default;
    const sourceBuffer = await readFile(sourcePath);
    const resizedBuffer = await sharp(sourceBuffer)
      .resize(size, size, { fit: 'cover', position: 'center' })
      .webp({ quality: size <= 48 ? 80 : 85 })
      .toBuffer();

    // Cache resized image to disk (non-blocking, best-effort)
    const cachePath = buildApprovedImagePath(entityType, entityId, `s${size}`);
    mkdir(dirname(cachePath), { recursive: true })
      .then(() => writeFile(cachePath, resizedBuffer))
      .catch(() => {});

    return serveBuffer(resizedBuffer, `"gen-s${size}-${resizedBuffer.length}"`);
  } catch (error) {
    console.error('Error resizing image:', error);
    return new Response('Error resizing image', { status: 500 });
  }
}

/**
 * Serve a cached resized file from disk.
 */
async function serveFile(filePath, size) {
  try {
    const stats = statSync(filePath);
    const buffer = await readFile(filePath);
    return new Response(buffer, {
      status: 200,
      headers: {
        'Content-Type': 'image/webp',
        'Content-Length': String(buffer.length),
        'Cache-Control': `public, max-age=${CACHE_MAX_AGE}`,
        'ETag': `"${stats.size}-${stats.mtimeMs}-s${size}"`,
        'Last-Modified': stats.mtime.toUTCString()
      }
    });
  } catch (error) {
    console.error('Error serving cached image:', error);
    return new Response('Error serving image', { status: 500 });
  }
}

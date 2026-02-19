/**
 * API endpoint for serving entity images.
 * Serves approved images with proper caching headers.
 *
 * GET /api/img/:entityType/:entityId - Serves the icon image
 * GET /api/img/:entityType/:entityId?type=thumb - Serves the thumbnail
 * GET /api/img/:entityType/:entityId?size=32|48|64|128|320 - Resized thumbnail (cached to disk)
 * GET /api/img/:entityType/:entityId?mode=dark|light - Enhanced icon with trim/scale/backdrop
 */
import { getApprovedImagePath, buildApprovedImagePath, isValidEntityType } from '$lib/server/imageProcessor.js';
import { enhanceEntityImage } from '$lib/server/imageEnhancer.js';
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

  // If size is requested, try to serve a cached resized version first
  if (size) {
    const cachedPath = buildApprovedImagePath(lowerType, entityId, `s${size}`);
    if (existsSync(cachedPath)) {
      return serveFile(cachedPath, size);
    }
  }

  // Get the source image path (use thumb as source for resizing — smaller file)
  const sourceType = size ? 'thumb' : type;
  const imagePath = getApprovedImagePath(lowerType, entityId, sourceType);

  if (!imagePath || !existsSync(imagePath)) {
    // If requesting a size and thumb doesn't exist, try icon as fallback
    if (size) {
      const iconPath = getApprovedImagePath(lowerType, entityId, 'icon');
      if (iconPath && existsSync(iconPath)) {
        return resizeAndServe(iconPath, lowerType, entityId, size);
      }
    }
    return new Response(null, { status: 204 });
  }

  // If a specific size is requested, resize from source
  if (size) {
    return resizeAndServe(imagePath, lowerType, entityId, size);
  }

  try {
    const stats = statSync(imagePath);
    const imageBuffer = await readFile(imagePath);

    // Apply enhancement pipeline for icons when mode is specified
    let outputBuffer = imageBuffer;
    if (mode && type === 'icon') {
      try {
        outputBuffer = await enhanceEntityImage(imageBuffer, mode);
      } catch {
        // Enhancement failed — serve original image
        outputBuffer = imageBuffer;
      }
    }

    // Include mode in ETag so CDN caches dark/light variants separately
    const etagBase = `${stats.size}-${stats.mtimeMs}`;
    const etag = mode ? `"${etagBase}-${mode}"` : `"${etagBase}"`;

    return new Response(outputBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'image/webp',
        'Content-Length': String(outputBuffer.length),
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

    return new Response(resizedBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'image/webp',
        'Content-Length': String(resizedBuffer.length),
        'Cache-Control': `public, max-age=${CACHE_MAX_AGE}`,
      }
    });
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

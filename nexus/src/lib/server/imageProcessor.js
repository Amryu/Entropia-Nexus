/**
 * Server-side image processing for entity icons.
 * Uses sharp library for image manipulation.
 */
import sharp from 'sharp';
import { existsSync, mkdirSync, unlinkSync, readdirSync, statSync } from 'fs';
import { join, dirname } from 'path';
import { randomUUID } from 'crypto';

// Image size configurations
const ICON_SIZE = 320;
const THUMB_SIZE = 128;

// Base upload directories (configured via environment)
const UPLOAD_BASE = process.env.UPLOAD_DIR || './uploads';
const PENDING_DIR = join(UPLOAD_BASE, 'pending');
const APPROVED_DIR = join(UPLOAD_BASE, 'approved');
const TEMP_DIR = join(UPLOAD_BASE, 'temp');

// Security limits
const MAX_FILE_SIZE = 2 * 1024 * 1024; // 2MB
const MAX_IMAGE_DIMENSION = 8192; // Max width/height in pixels
const MIN_IMAGE_DIMENSION = 32; // Min width/height in pixels

// Allowed image formats (verified via magic bytes, not just extension)
const ALLOWED_FORMATS = ['jpeg', 'png', 'webp', 'gif'];

// Valid entity types to prevent path traversal
const VALID_ENTITY_TYPES = [
  'weapon', 'armorset', 'material', 'blueprint', 'clothing',
  'consumable', 'tool', 'attachment', 'medicaltool', 'vehicle',
  'pet', 'furnishing', 'strongbox', 'mob', 'skill', 'profession', 'vendor',
  'location', 'area', 'user'
];

/**
 * Ensure directory exists, creating it if necessary
 * @param {string} dir
 */
function ensureDir(dir) {
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
}

/**
 * Get the path for an entity's images
 * @param {string} baseDir - Base directory (pending/approved)
 * @param {string} entityType
 * @param {string|number} entityId
 * @returns {string}
 */
function getEntityPath(baseDir, entityType, entityId) {
  return join(baseDir, entityType, String(entityId));
}

/**
 * Validate entity type to prevent path traversal attacks
 * @param {string} entityType
 * @returns {boolean}
 */
function isValidEntityType(entityType) {
  if (!entityType || typeof entityType !== 'string') return false;
  // Normalize and check against whitelist
  const normalized = entityType.toLowerCase().trim();
  return VALID_ENTITY_TYPES.includes(normalized) && !/[\/\\\.\.]/g.test(entityType);
}

/**
 * Validate entity ID to prevent path traversal
 * @param {string|number} entityId
 * @returns {boolean}
 */
function isValidEntityId(entityId) {
  if (entityId === null || entityId === undefined) return false;
  const idStr = String(entityId);
  // Only allow alphanumeric, hyphens, underscores, and spaces
  // Max length 200 characters
  return /^[\w\s\-]+$/.test(idStr) && idStr.length > 0 && idStr.length <= 200;
}

/**
 * Count total files in temp directory for global limit
 * @returns {number}
 */
function countTempFiles() {
  if (!existsSync(TEMP_DIR)) return 0;
  try {
    return readdirSync(TEMP_DIR).length;
  } catch {
    return 0;
  }
}

/**
 * Delete any pending image from a user for a specific entity
 * This ensures only one pending image per user per entity exists
 * @param {string} uploaderId - ID of the uploader
 * @param {string} entityType - Entity type
 * @param {string|number} entityId - Entity ID
 * @returns {Promise<void>}
 */
async function deleteUserPendingImage(uploaderId, entityType, entityId) {
  if (!existsSync(TEMP_DIR)) return;

  const fs = await import('fs/promises');
  const tempDirs = readdirSync(TEMP_DIR);

  for (const tempId of tempDirs) {
    const metadataPath = join(TEMP_DIR, tempId, 'metadata.json');
    if (!existsSync(metadataPath)) continue;

    try {
      const metadata = JSON.parse(await fs.readFile(metadataPath, 'utf-8'));
      // Delete if same uploader and same entity
      if (metadata.uploaderId === uploaderId &&
          metadata.entityType === entityType &&
          metadata.entityId === String(entityId)) {
        await fs.rm(join(TEMP_DIR, tempId), { recursive: true, force: true });
      }
    } catch {
      // Ignore errors reading individual metadata files
    }
  }
}

/**
 * Get pending image for a specific entity uploaded by a specific user
 * @param {string} uploaderId - ID of the uploader
 * @param {string} entityType - Entity type
 * @param {string|number} entityId - Entity ID
 * @returns {Promise<{tempId: string, previewUrl: string, uploadedAt: string}|null>}
 */
export async function getUserPendingImage(uploaderId, entityType, entityId) {
  if (!existsSync(TEMP_DIR)) {
    return null;
  }

  const fs = await import('fs/promises');
  const tempDirs = readdirSync(TEMP_DIR);

  for (const tempId of tempDirs) {
    const metadataPath = join(TEMP_DIR, tempId, 'metadata.json');
    if (!existsSync(metadataPath)) continue;

    try {
      const metadata = JSON.parse(await fs.readFile(metadataPath, 'utf-8'));

      // Check if entity type and ID match
      const typeMatches = metadata.entityType === entityType;
      const idMatches = metadata.entityId === String(entityId);

      if (typeMatches && idMatches) {
        // Uploader matches, OR this is a legacy image without uploaderId tracking
        // (backward compatibility for images uploaded before uploaderId was added)
        const uploaderMatches = metadata.uploaderId === uploaderId || metadata.uploaderId === undefined;

        if (uploaderMatches) {
          return {
            tempId,
            previewUrl: `/api/uploads/preview/${tempId}`,
            uploadedAt: metadata.uploadedAt
          };
        }
      }
    } catch {
      // Ignore errors reading individual metadata files
    }
  }

  return null;
}

/**
 * Process and save an uploaded image
 * @param {Buffer} imageBuffer - The raw image buffer
 * @param {string} entityType - Entity type (e.g., 'weapon', 'mob')
 * @param {string|number} entityId - Entity ID
 * @param {string} uploaderId - ID of the user uploading the image
 * @returns {Promise<{tempPath: string, previewUrl: string}>}
 */
export async function processAndSaveImage(imageBuffer, entityType, entityId, uploaderId) {
  // ===== SECURITY VALIDATIONS =====

  // 1. Validate entity type (prevent path traversal)
  if (!isValidEntityType(entityType)) {
    throw new Error('Invalid entity type');
  }

  // 2. Validate entity ID (prevent path traversal)
  if (!isValidEntityId(entityId)) {
    throw new Error('Invalid entity ID');
  }

  // 3. Validate uploader ID
  if (!uploaderId || typeof uploaderId !== 'string') {
    throw new Error('Invalid uploader ID');
  }

  // 4. Validate file size (early check before processing)
  if (!imageBuffer || imageBuffer.length === 0) {
    throw new Error('Empty image file');
  }

  if (imageBuffer.length > MAX_FILE_SIZE) {
    throw new Error(`Image must be smaller than ${MAX_FILE_SIZE / 1024 / 1024}MB`);
  }

  // 5. Global temp file limit (prevent disk flooding)
  const tempCount = countTempFiles();
  if (tempCount >= 1000) {
    throw new Error('Server storage limit reached. Please try again later.');
  }

  // 6. Delete any existing pending image from this user for this entity
  await deleteUserPendingImage(uploaderId, entityType, entityId);

  // Generate unique temp ID for this upload
  const tempId = randomUUID();
  const tempEntityPath = join(TEMP_DIR, tempId);
  ensureDir(tempEntityPath);

  try {
    // 7. Validate actual image content using sharp (magic bytes verification)
    // Sharp will throw if the buffer isn't a valid image
    const image = sharp(imageBuffer, {
      // Limit memory usage during processing
      limitInputPixels: MAX_IMAGE_DIMENSION * MAX_IMAGE_DIMENSION,
      // Fail on invalid/corrupt images
      failOn: 'error'
    });

    const metadata = await image.metadata();

    // 8. Validate image format (verified by sharp, not just MIME type)
    if (!metadata.format || !ALLOWED_FORMATS.includes(metadata.format)) {
      throw new Error('Invalid image format. Supported: JPEG, PNG, WebP, GIF');
    }

    // 9. Validate image dimensions
    if (!metadata.width || !metadata.height) {
      throw new Error('Cannot determine image dimensions');
    }

    if (metadata.width > MAX_IMAGE_DIMENSION || metadata.height > MAX_IMAGE_DIMENSION) {
      throw new Error(`Image dimensions must not exceed ${MAX_IMAGE_DIMENSION}x${MAX_IMAGE_DIMENSION} pixels`);
    }

    if (metadata.width < MIN_IMAGE_DIMENSION || metadata.height < MIN_IMAGE_DIMENSION) {
      throw new Error(`Image dimensions must be at least ${MIN_IMAGE_DIMENSION}x${MIN_IMAGE_DIMENSION} pixels`);
    }

    // 10. Check for decompression bombs (images that expand massively)
    const pixelCount = metadata.width * metadata.height;
    const expectedMinBytes = pixelCount / 1000; // Very generous ratio
    if (imageBuffer.length < expectedMinBytes && pixelCount > 1000000) {
      throw new Error('Suspicious image compression ratio detected');
    }

    // Process icon (512x512)
    const iconPath = join(tempEntityPath, 'icon.webp');
    await image
      .resize(ICON_SIZE, ICON_SIZE, {
        fit: 'cover',
        position: 'center'
      })
      .webp({ quality: 90 })
      .toFile(iconPath);

    // Process thumbnail (128x128)
    const thumbPath = join(tempEntityPath, 'thumb.webp');
    await sharp(imageBuffer)
      .resize(THUMB_SIZE, THUMB_SIZE, {
        fit: 'cover',
        position: 'center'
      })
      .webp({ quality: 85 })
      .toFile(thumbPath);

    // Store metadata for later approval
    const metadataPath = join(tempEntityPath, 'metadata.json');
    const fs = await import('fs/promises');
    await fs.writeFile(metadataPath, JSON.stringify({
      entityType,
      entityId: String(entityId),
      uploaderId,
      uploadedAt: new Date().toISOString(),
      tempId
    }));

    return {
      tempPath: tempId,
      previewUrl: `/api/uploads/preview/${tempId}`
    };
  } catch (error) {
    // Clean up on error
    try {
      const fs = await import('fs/promises');
      await fs.rm(tempEntityPath, { recursive: true, force: true });
    } catch {}
    throw error;
  }
}

/**
 * Get a preview image from temp storage
 * @param {string} tempId - Temp upload ID
 * @param {string} type - 'icon' or 'thumb'
 * @returns {Promise<Buffer|null>}
 */
export async function getPreviewImage(tempId, type = 'icon') {
  const imagePath = join(TEMP_DIR, tempId, `${type}.webp`);

  if (!existsSync(imagePath)) {
    return null;
  }

  const fs = await import('fs/promises');
  return fs.readFile(imagePath);
}

/**
 * Get list of pending image uploads for admin review
 * @returns {Promise<Array>}
 */
export async function getPendingImages() {
  ensureDir(PENDING_DIR);
  const pending = [];
  const fs = await import('fs/promises');

  // Also check temp directory for unsubmitted uploads
  if (existsSync(TEMP_DIR)) {
    const tempDirs = readdirSync(TEMP_DIR);
    for (const tempId of tempDirs) {
      const metadataPath = join(TEMP_DIR, tempId, 'metadata.json');
      if (existsSync(metadataPath)) {
        try {
          const metadata = JSON.parse(await fs.readFile(metadataPath, 'utf-8'));
          pending.push({
            ...metadata,
            status: 'pending',
            previewUrl: `/api/uploads/preview/${tempId}`
          });
        } catch {}
      }
    }
  }

  return pending;
}

/**
 * Move an image from temp to pending status (when entity change is submitted)
 * @param {string} tempId - Temp upload ID
 * @returns {Promise<string>} - Pending ID
 */
export async function submitImageForApproval(tempId) {
  const tempPath = join(TEMP_DIR, tempId);

  if (!existsSync(tempPath)) {
    throw new Error('Temp image not found');
  }

  const fs = await import('fs/promises');
  const metadata = JSON.parse(await fs.readFile(join(tempPath, 'metadata.json'), 'utf-8'));

  // Move to pending directory
  const pendingPath = getEntityPath(PENDING_DIR, metadata.entityType, metadata.entityId);
  ensureDir(dirname(pendingPath));

  // Remove existing pending if any
  if (existsSync(pendingPath)) {
    await fs.rm(pendingPath, { recursive: true, force: true });
  }

  await fs.rename(tempPath, pendingPath);

  // Update metadata with pending ID
  const pendingId = `${metadata.entityType}/${metadata.entityId}`;
  await fs.writeFile(
    join(pendingPath, 'metadata.json'),
    JSON.stringify({
      ...metadata,
      pendingId,
      submittedAt: new Date().toISOString()
    })
  );

  return pendingId;
}

/**
 * Approve a pending image
 * Searches both TEMP_DIR (uploaded but not yet submitted) and PENDING_DIR (submitted for approval)
 * @param {string} entityType
 * @param {string|number} entityId
 * @returns {Promise<void>}
 */
export async function approveImage(entityType, entityId) {
  const fs = await import('fs/promises');
  let sourcePath = null;

  // First, check PENDING_DIR (submitted images)
  const pendingPath = getEntityPath(PENDING_DIR, entityType, entityId);
  if (existsSync(pendingPath)) {
    sourcePath = pendingPath;
  } else if (existsSync(TEMP_DIR)) {
    // Search TEMP_DIR for matching images
    const tempDirs = readdirSync(TEMP_DIR);
    for (const tempId of tempDirs) {
      const metadataPath = join(TEMP_DIR, tempId, 'metadata.json');
      if (!existsSync(metadataPath)) continue;

      try {
        const metadata = JSON.parse(await fs.readFile(metadataPath, 'utf-8'));
        if (metadata.entityType === entityType && metadata.entityId === String(entityId)) {
          sourcePath = join(TEMP_DIR, tempId);
          break;
        }
      } catch {
        // Ignore errors reading individual metadata files
      }
    }
  }

  if (!sourcePath) {
    throw new Error('Pending image not found');
  }

  const approvedPath = getEntityPath(APPROVED_DIR, entityType, entityId);
  ensureDir(dirname(approvedPath));

  // Remove existing approved if any
  if (existsSync(approvedPath)) {
    await fs.rm(approvedPath, { recursive: true, force: true });
  }

  // Move source to approved
  await fs.rename(sourcePath, approvedPath);

  // Update metadata
  const metadataPath = join(approvedPath, 'metadata.json');
  if (existsSync(metadataPath)) {
    const metadata = JSON.parse(await fs.readFile(metadataPath, 'utf-8'));
    await fs.writeFile(metadataPath, JSON.stringify({
      ...metadata,
      approvedAt: new Date().toISOString()
    }));
  }
}

/**
 * Deny/delete a pending image
 * Searches both TEMP_DIR (uploaded but not yet submitted) and PENDING_DIR (submitted for approval)
 * @param {string} entityType
 * @param {string|number} entityId
 * @returns {Promise<void>}
 */
export async function denyImage(entityType, entityId) {
  const fs = await import('fs/promises');

  // First, check PENDING_DIR (submitted images)
  const pendingPath = getEntityPath(PENDING_DIR, entityType, entityId);
  if (existsSync(pendingPath)) {
    await fs.rm(pendingPath, { recursive: true, force: true });
    return;
  }

  // Otherwise, search TEMP_DIR for matching images
  if (existsSync(TEMP_DIR)) {
    const tempDirs = readdirSync(TEMP_DIR);
    for (const tempId of tempDirs) {
      const metadataPath = join(TEMP_DIR, tempId, 'metadata.json');
      if (!existsSync(metadataPath)) continue;

      try {
        const metadata = JSON.parse(await fs.readFile(metadataPath, 'utf-8'));
        if (metadata.entityType === entityType && metadata.entityId === String(entityId)) {
          await fs.rm(join(TEMP_DIR, tempId), { recursive: true, force: true });
          return;
        }
      } catch {
        // Ignore errors reading individual metadata files
      }
    }
  }

  throw new Error('Pending image not found');
}

/**
 * Get approved image path for an entity
 * @param {string} entityType
 * @param {string|number} entityId
 * @param {string} type - 'icon' or 'thumb'
 * @returns {string|null}
 */
export function getApprovedImagePath(entityType, entityId, type = 'icon') {
  const imagePath = join(getEntityPath(APPROVED_DIR, entityType, entityId), `${type}.webp`);
  return existsSync(imagePath) ? imagePath : null;
}

/**
 * Get list of all approved images
 * @returns {Promise<Array>}
 */
export async function getApprovedImages() {
  ensureDir(APPROVED_DIR);
  const approved = [];
  const fs = await import('fs/promises');

  if (!existsSync(APPROVED_DIR)) {
    return approved;
  }

  // Iterate through entity type directories
  const typeDirs = readdirSync(APPROVED_DIR);
  for (const entityType of typeDirs) {
    const typePath = join(APPROVED_DIR, entityType);
    if (!statSync(typePath).isDirectory()) continue;

    // Iterate through entity ID directories
    const entityDirs = readdirSync(typePath);
    for (const entityId of entityDirs) {
      const entityPath = join(typePath, entityId);
      if (!statSync(entityPath).isDirectory()) continue;

      const metadataPath = join(entityPath, 'metadata.json');
      let metadata = { entityType, entityId };

      if (existsSync(metadataPath)) {
        try {
          metadata = JSON.parse(await fs.readFile(metadataPath, 'utf-8'));
        } catch {}
      }

      approved.push({
        ...metadata,
        entityType,
        entityId,
        status: 'approved',
        imageUrl: `/api/uploads/approved/${entityType}/${entityId}`
      });
    }
  }

  return approved;
}

/**
 * Delete an approved image
 * @param {string} entityType
 * @param {string|number} entityId
 * @returns {Promise<void>}
 */
export async function deleteApprovedImage(entityType, entityId) {
  const approvedPath = getEntityPath(APPROVED_DIR, entityType, entityId);

  if (!existsSync(approvedPath)) {
    throw new Error('Approved image not found');
  }

  const fs = await import('fs/promises');
  await fs.rm(approvedPath, { recursive: true, force: true });
}

/**
 * Clean up old temp uploads (older than 24 hours)
 * @returns {Promise<number>} - Number of cleaned up directories
 */
export async function cleanupTempUploads() {
  if (!existsSync(TEMP_DIR)) {
    return 0;
  }

  const fs = await import('fs/promises');
  const now = Date.now();
  const maxAge = 24 * 60 * 60 * 1000; // 24 hours
  let cleaned = 0;

  const dirs = readdirSync(TEMP_DIR);
  for (const dir of dirs) {
    const dirPath = join(TEMP_DIR, dir);
    const stats = statSync(dirPath);

    if (now - stats.mtimeMs > maxAge) {
      await fs.rm(dirPath, { recursive: true, force: true });
      cleaned++;
    }
  }

  return cleaned;
}

export default {
  processAndSaveImage,
  getPreviewImage,
  getPendingImages,
  getApprovedImages,
  getUserPendingImage,
  submitImageForApproval,
  approveImage,
  denyImage,
  deleteApprovedImage,
  getApprovedImagePath,
  cleanupTempUploads
};

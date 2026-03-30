/**
 * Cloudflare R2 storage module (S3-compatible API).
 *
 * All functions gracefully return null/false when R2 is not configured,
 * allowing the system to operate in local-only mode without code changes.
 *
 * Environment variables:
 *   R2_ACCOUNT_ID        - Cloudflare account ID
 *   R2_ACCESS_KEY_ID     - R2 API token access key
 *   R2_SECRET_ACCESS_KEY - R2 API token secret key
 *   R2_BUCKET_NAME       - R2 bucket name (e.g. "entropia-nexus-images")
 */
import {
  S3Client,
  PutObjectCommand,
  GetObjectCommand,
  DeleteObjectCommand,
  CopyObjectCommand,
  ListObjectsV2Command
} from '@aws-sdk/client-s3';

const ACCOUNT_ID = process.env.R2_ACCOUNT_ID;
const ACCESS_KEY_ID = process.env.R2_ACCESS_KEY_ID;
const SECRET_ACCESS_KEY = process.env.R2_SECRET_ACCESS_KEY;
const BUCKET = process.env.R2_BUCKET_NAME;

/** Whether R2 is configured and available */
export const r2Enabled = !!(ACCOUNT_ID && ACCESS_KEY_ID && SECRET_ACCESS_KEY && BUCKET);

/** @type {S3Client | null} */
let client = null;

function getClient() {
  if (!r2Enabled) return null;
  if (!client) {
    client = new S3Client({
      region: 'auto',
      endpoint: `https://${ACCOUNT_ID}.r2.cloudflarestorage.com`,
      credentials: {
        accessKeyId: ACCESS_KEY_ID || '',
        secretAccessKey: SECRET_ACCESS_KEY || ''
      }
    });
  }
  return client;
}

/**
 * Upload a file to R2.
 * @param {string} key - Object key (e.g. "weapon/123/icon.webp")
 * @param {Buffer} buffer - File contents
 * @param {string} [contentType='image/webp'] - MIME type
 * @returns {Promise<boolean>} true on success, false if R2 is unavailable or fails
 */
async function uploadToR2(key, buffer, contentType = 'image/webp') {
  const s3 = getClient();
  if (!s3) return false;

  try {
    await s3.send(new PutObjectCommand({
      Bucket: BUCKET,
      Key: key,
      Body: buffer,
      ContentType: contentType
    }));
    return true;
  } catch (/** @type {any} */ err) {
    console.error(`[R2] Upload failed for ${key}:`, err?.message);
    return false;
  }
}

/**
 * Download a file from R2.
 * @param {string} key - Object key
 * @returns {Promise<Buffer|null>} File contents or null
 */
export async function getFromR2(key) {
  const s3 = getClient();
  if (!s3) return null;

  try {
    const response = await s3.send(new GetObjectCommand({
      Bucket: BUCKET,
      Key: key
    }));
    // Convert readable stream to Buffer
    if (!response.Body) return null;
    const chunks = [];
    for await (const chunk of /** @type {AsyncIterable<Uint8Array>} */ (response.Body)) {
      chunks.push(chunk);
    }
    return Buffer.concat(chunks);
  } catch (/** @type {any} */ err) {
    if (err?.name === 'NoSuchKey') return null;
    console.error(`[R2] Get failed for ${key}:`, err?.message);
    return null;
  }
}

/**
 * Delete all objects under a key prefix (e.g. "weapon/123/").
 * @param {string} prefix - Key prefix ending with "/"
 * @returns {Promise<number>} Number of objects deleted
 */
export async function deleteR2Prefix(prefix) {
  const s3 = getClient();
  if (!s3) return 0;

  try {
    const listed = await s3.send(new ListObjectsV2Command({
      Bucket: BUCKET,
      Prefix: prefix
    }));

    const objects = listed.Contents || [];
    let deleted = 0;

    for (const obj of objects) {
      try {
        await s3.send(new DeleteObjectCommand({
          Bucket: BUCKET,
          Key: obj.Key
        }));
        deleted++;
      } catch {
        // Continue deleting remaining objects
      }
    }

    return deleted;
  } catch (/** @type {any} */ err) {
    console.error(`[R2] Prefix delete failed for ${prefix}:`, err?.message);
    return 0;
  }
}

/**
 * Copy an object within R2 (server-side, no download needed).
 * @param {string} sourceKey - Source object key
 * @param {string} destKey - Destination object key
 * @returns {Promise<boolean>}
 */
export async function copyInR2(sourceKey, destKey) {
  const s3 = getClient();
  if (!s3) return false;

  try {
    await s3.send(new CopyObjectCommand({
      Bucket: BUCKET,
      CopySource: `${BUCKET}/${sourceKey}`,
      Key: destKey
    }));
    return true;
  } catch (/** @type {any} */ err) {
    console.error(`[R2] Copy failed ${sourceKey} → ${destKey}:`, err?.message);
    return false;
  }
}

/**
 * Upload multiple files to R2 in parallel.
 * @param {Array<{key: string, buffer: Buffer, contentType?: string}>} files
 * @returns {Promise<{succeeded: number, failed: number}>}
 */
export async function uploadBatchToR2(files) {
  if (!r2Enabled) return { succeeded: 0, failed: 0 };

  const results = await Promise.allSettled(
    files.map(f => uploadToR2(f.key, f.buffer, f.contentType || 'image/webp'))
  );

  let succeeded = 0;
  let failed = 0;
  for (const r of results) {
    if (r.status === 'fulfilled' && r.value) succeeded++;
    else failed++;
  }
  return { succeeded, failed };
}

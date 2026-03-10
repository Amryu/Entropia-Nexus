#!/usr/bin/env node
/**
 * Migration script: Upload all existing approved images to Cloudflare R2.
 *
 * Usage:
 *   node migrate-images-to-r2.mjs [--env <path>] [--dry-run] [--force]
 *
 * Options:
 *   --env <path>  Load environment variables from a .env file (default: ./.env)
 *   --dry-run     Show what would be uploaded without actually uploading
 *   --force       Re-upload even if the object already exists in R2
 *
 * Environment variables (required):
 *   R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
 *   UPLOAD_DIR (optional, defaults to ./uploads)
 *
 * Can safely be run while the site is live — reads are local-only.
 */
import { existsSync, readdirSync, statSync, readFileSync } from 'fs';
import { readFile } from 'fs/promises';
import { join, resolve } from 'path';

// --- Load .env file ---
const args = process.argv.slice(2);
const envIdx = args.indexOf('--env');
const envPath = resolve(envIdx !== -1 && args[envIdx + 1] ? args[envIdx + 1] : '.env');
if (existsSync(envPath)) {
  for (const line of readFileSync(envPath, 'utf-8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim();
    if (!process.env[key]) process.env[key] = val;
  }
  console.log(`Loaded env from ${envPath}`);
} else if (envIdx !== -1) {
  console.error(`Env file not found: ${envPath}`);
  process.exit(1);
}
import sharp from 'sharp';
import {
  S3Client,
  PutObjectCommand,
  HeadObjectCommand
} from '@aws-sdk/client-s3';

// --- Configuration ---

const ACCOUNT_ID = process.env.R2_ACCOUNT_ID;
const ACCESS_KEY_ID = process.env.R2_ACCESS_KEY_ID;
const SECRET_ACCESS_KEY = process.env.R2_SECRET_ACCESS_KEY;
const BUCKET = process.env.R2_BUCKET_NAME;
const UPLOAD_DIR = process.env.UPLOAD_DIR || './uploads';
const APPROVED_DIR = join(UPLOAD_DIR, 'approved');

const VARIANT_SIZES = [32, 48, 64, 128];

const DRY_RUN = args.includes('--dry-run');
const FORCE = args.includes('--force');

// --- Validate ---

if (!ACCOUNT_ID || !ACCESS_KEY_ID || !SECRET_ACCESS_KEY || !BUCKET) {
  console.error('Missing R2 environment variables. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME.');
  process.exit(1);
}

if (!existsSync(APPROVED_DIR)) {
  console.error(`Approved directory not found: ${APPROVED_DIR}`);
  process.exit(1);
}

// --- R2 Client ---

const s3 = new S3Client({
  region: 'auto',
  endpoint: `https://${ACCOUNT_ID}.r2.cloudflarestorage.com`,
  credentials: { accessKeyId: ACCESS_KEY_ID, secretAccessKey: SECRET_ACCESS_KEY }
});

async function existsInR2(key) {
  try {
    await s3.send(new HeadObjectCommand({ Bucket: BUCKET, Key: key }));
    return true;
  } catch {
    return false;
  }
}

async function upload(key, buffer, contentType = 'image/webp') {
  await s3.send(new PutObjectCommand({
    Bucket: BUCKET,
    Key: key,
    Body: buffer,
    ContentType: contentType
  }));
}

// --- Size variant generation ---

async function generateVariants(iconBuffer, thumbBuffer) {
  const source = thumbBuffer || iconBuffer;
  const variants = {};
  for (const size of VARIANT_SIZES) {
    const quality = size <= 48 ? 80 : 85;
    variants[`s${size}`] = await sharp(source)
      .resize(size, size, { fit: 'cover', position: 'center' })
      .webp({ quality })
      .toBuffer();
  }
  return variants;
}

// --- Main ---

async function migrate() {
  console.log(`Migrating approved images from ${APPROVED_DIR} to R2 bucket "${BUCKET}"`);
  if (DRY_RUN) console.log('  (DRY RUN — no uploads will be made)');
  if (FORCE) console.log('  (FORCE — re-uploading all objects)');
  console.log();

  const stats = { entities: 0, uploaded: 0, skipped: 0, failed: 0 };

  const typeDirs = readdirSync(APPROVED_DIR).filter(d =>
    statSync(join(APPROVED_DIR, d)).isDirectory()
  );

  for (const entityType of typeDirs) {
    const typePath = join(APPROVED_DIR, entityType);
    const entityDirs = readdirSync(typePath).filter(d =>
      statSync(join(typePath, d)).isDirectory()
    );

    for (const entityId of entityDirs) {
      stats.entities++;
      const entityPath = join(typePath, entityId);
      const prefix = `${entityType}/${entityId}`;

      try {
        // Check if already migrated (skip if icon exists in R2 and not forced)
        if (!FORCE && await existsInR2(`${prefix}/icon.webp`)) {
          stats.skipped++;
          continue;
        }

        // Read source files
        const iconPath = join(entityPath, 'icon.webp');
        const thumbPath = join(entityPath, 'thumb.webp');
        const metadataPath = join(entityPath, 'metadata.json');

        const iconBuffer = existsSync(iconPath) ? await readFile(iconPath) : null;
        const thumbBuffer = existsSync(thumbPath) ? await readFile(thumbPath) : null;

        if (!iconBuffer) {
          console.warn(`  SKIP ${prefix} — no icon.webp`);
          stats.skipped++;
          continue;
        }

        // Generate size variants
        const variants = await generateVariants(iconBuffer, thumbBuffer);

        if (DRY_RUN) {
          const files = ['icon.webp'];
          if (thumbBuffer) files.push('thumb.webp');
          files.push(...Object.keys(variants).map(k => `${k}.webp`));
          if (existsSync(metadataPath)) files.push('metadata.json');
          console.log(`  ${prefix}: would upload ${files.length} files`);
          stats.uploaded++;
          continue;
        }

        // Upload all files
        await upload(`${prefix}/icon.webp`, iconBuffer);
        if (thumbBuffer) await upload(`${prefix}/thumb.webp`, thumbBuffer);
        for (const [name, buffer] of Object.entries(variants)) {
          await upload(`${prefix}/${name}.webp`, buffer);
        }
        if (existsSync(metadataPath)) {
          const metadata = await readFile(metadataPath);
          await upload(`${prefix}/metadata.json`, metadata, 'application/json');
        }

        stats.uploaded++;
        if (stats.uploaded % 50 === 0) {
          console.log(`  Progress: ${stats.uploaded} entities uploaded...`);
        }
      } catch (err) {
        console.error(`  FAIL ${prefix}: ${err?.message}`);
        stats.failed++;
      }
    }
  }

  console.log();
  console.log('Migration complete:');
  console.log(`  Total entities: ${stats.entities}`);
  console.log(`  Uploaded:       ${stats.uploaded}`);
  console.log(`  Skipped:        ${stats.skipped}`);
  console.log(`  Failed:         ${stats.failed}`);
}

migrate().catch(err => {
  console.error('Migration failed:', err);
  process.exit(1);
});

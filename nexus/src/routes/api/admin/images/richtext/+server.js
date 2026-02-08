// @ts-nocheck
import { json } from '@sveltejs/kit';
import { scanRichtextImageUsage, deleteApprovedImage } from '$lib/server/imageProcessor.js';
import { pool, nexusPool } from '$lib/server/db.js';

/**
 * GET /api/admin/images/richtext
 * Scan all rich text fields in both databases and return image usage report.
 */
export async function GET({ locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser?.grants?.includes('admin.panel')) {
    return json({ error: 'Only administrators can access this endpoint' }, { status: 403 });
  }

  try {
    const result = await scanRichtextImageUsage(pool, nexusPool);
    return json(result);
  } catch (err) {
    console.error('Richtext image scan failed:', err);
    return json({ error: 'Failed to scan richtext images' }, { status: 500 });
  }
}

/**
 * DELETE /api/admin/images/richtext
 * Delete unused richtext images. Expects { hashes: string[] } in body.
 */
export async function DELETE({ request, locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser?.grants?.includes('admin.panel')) {
    return json({ error: 'Only administrators can access this endpoint' }, { status: 403 });
  }

  const body = await request.json();
  const hashes = body?.hashes;

  if (!Array.isArray(hashes) || hashes.length === 0) {
    return json({ error: 'hashes must be a non-empty array of image hashes' }, { status: 400 });
  }

  // Validate all hashes are proper SHA-256 hex strings
  const hashRegex = /^[a-f0-9]{64}$/;
  const invalidHashes = hashes.filter(h => !hashRegex.test(h));
  if (invalidHashes.length > 0) {
    return json({ error: `Invalid hash format: ${invalidHashes[0]}` }, { status: 400 });
  }

  const deleted = [];
  const errors = [];

  for (const hash of hashes) {
    try {
      await deleteApprovedImage('richtext', hash);
      deleted.push(hash);
    } catch (err) {
      errors.push({ hash, error: err?.message || 'Unknown error' });
    }
  }

  return json({ deleted, errors });
}

// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';
import { reloadBotIpRanges } from '$lib/server/route-analytics.js';

/**
 * GET /api/admin/analytics/bots/ip-ranges
 */
export async function GET({ locals }) {
  requireAdminAPI(locals);
  try {
    const { rows } = await pool.query(
      `SELECT id, cidr::text, description, enabled, created_at FROM bot_ip_ranges ORDER BY id`
    );
    return json({ ranges: rows });
  } catch (e) {
    console.error('[analytics] IP ranges error:', e);
    return json({ error: 'Failed to fetch IP ranges' }, { status: 500 });
  }
}

/**
 * POST /api/admin/analytics/bots/ip-ranges
 */
export async function POST({ locals, request }) {
  requireAdminAPI(locals);
  const body = await request.json();
  const { cidr, description } = body;

  if (!cidr || typeof cidr !== 'string' || !cidr.includes('/')) {
    return json({ error: 'Valid CIDR notation required (e.g. 43.128.0.0/10)' }, { status: 400 });
  }

  try {
    const { rows } = await pool.query(
      `INSERT INTO bot_ip_ranges (cidr, description) VALUES ($1::cidr, $2)
       RETURNING id, cidr::text, description, enabled, created_at`,
      [cidr.trim(), description?.trim() || null]
    );
    await reloadBotIpRanges();
    return json({ range: rows[0] }, { status: 201 });
  } catch (e) {
    if (e.code === '23505') return json({ error: 'CIDR range already exists' }, { status: 409 });
    if (e.message?.includes('invalid input syntax for type cidr')) {
      return json({ error: 'Invalid CIDR notation' }, { status: 400 });
    }
    console.error('[analytics] Add IP range error:', e);
    return json({ error: 'Failed to add IP range' }, { status: 500 });
  }
}

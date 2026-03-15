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
 *
 * Smart merge logic:
 *   1. If new range is already contained within an existing range → skip
 *   2. If existing ranges are contained within the new range → delete them, insert new
 *   3. If new range is a sibling of an existing range (same parent /N-1) → merge into parent
 *   4. Otherwise → insert as-is
 */
export async function POST({ locals, request }) {
  requireAdminAPI(locals);
  const body = await request.json();
  const { cidr, description } = body;

  if (!cidr || typeof cidr !== 'string' || !cidr.includes('/')) {
    return json({ error: 'Valid CIDR notation required (e.g. 43.128.0.0/10)' }, { status: 400 });
  }

  const trimmed = cidr.trim();

  try {
    // 1. Already covered by an existing wider range?
    const { rows: covering } = await pool.query(
      `SELECT id, cidr::text FROM bot_ip_ranges
       WHERE enabled = true AND $1::cidr <<= cidr`,
      [trimmed]
    );
    if (covering.length > 0) {
      return json({
        range: covering[0],
        merged: true,
        message: `Already covered by ${covering[0].cidr}`
      });
    }

    // 2. Does the new range cover existing narrower ranges? Remove them.
    const { rows: absorbed } = await pool.query(
      `DELETE FROM bot_ip_ranges WHERE cidr <<= $1::cidr RETURNING id, cidr::text`,
      [trimmed]
    );

    // 3. Check for sibling merge: if there's an existing range that shares
    // the same parent (one bit wider) as the new range, merge into the parent.
    // e.g. existing 10.0.0.0/24 + new 10.0.1.0/24 → merge into 10.0.0.0/23
    let finalCidr = trimmed;
    let siblingMerged = false;
    const bits = parseInt(trimmed.split('/')[1], 10);

    if (bits > 8) { // don't merge wider than /8
      const { rows: siblings } = await pool.query(
        `SELECT id, cidr::text FROM bot_ip_ranges
         WHERE masklen(cidr) = $1
           AND network(set_masklen(cidr, $1 - 1)) = network(set_masklen($2::cidr, $1 - 1))
           AND enabled = true`,
        [bits, trimmed]
      );

      if (siblings.length > 0) {
        // Merge: delete the sibling, use the parent CIDR
        const parentBits = bits - 1;
        const { rows: parentRows } = await pool.query(
          `SELECT network(set_masklen($1::cidr, $2))::text AS parent_cidr`,
          [trimmed, parentBits]
        );
        finalCidr = parentRows[0].parent_cidr;
        await pool.query(`DELETE FROM bot_ip_ranges WHERE id = $1`, [siblings[0].id]);
        siblingMerged = true;
      }
    }

    // 4. Insert the final range
    const desc = siblingMerged
      ? `${description || 'Merged'} (merged from /${bits} siblings)`
      : (description?.trim() || null);

    const { rows } = await pool.query(
      `INSERT INTO bot_ip_ranges (cidr, description) VALUES ($1::cidr, $2)
       RETURNING id, cidr::text, description, enabled, created_at`,
      [finalCidr, desc]
    );

    await reloadBotIpRanges();

    return json({
      range: rows[0],
      merged: siblingMerged || absorbed.length > 0,
      absorbed: absorbed.map(a => a.cidr),
      message: siblingMerged
        ? `Merged with sibling into ${finalCidr}`
        : absorbed.length > 0
          ? `Absorbed ${absorbed.length} narrower range(s)`
          : null
    }, { status: 201 });
  } catch (e) {
    if (e.code === '23505') return json({ error: 'CIDR range already exists' }, { status: 409 });
    if (e.message?.includes('invalid input syntax for type cidr')) {
      return json({ error: 'Invalid CIDR notation' }, { status: 400 });
    }
    console.error('[analytics] Add IP range error:', e);
    return json({ error: 'Failed to add IP range' }, { status: 500 });
  }
}

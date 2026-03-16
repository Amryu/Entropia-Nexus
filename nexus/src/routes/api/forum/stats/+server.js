// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getForumStats } from '$lib/server/db.js';

export async function GET() {
  try {
    const stats = await getForumStats();
    return json(stats);
  } catch (err) {
    console.error('[api/forum/stats] Error:', err.message);
    return json({ error: 'Internal server error' }, { status: 500 });
  }
}

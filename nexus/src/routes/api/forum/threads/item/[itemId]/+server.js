// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getForumThreadsByItem } from '$lib/server/db.js';

export async function GET({ params, url }) {
  const itemId = parseInt(params.itemId, 10);
  if (!itemId || isNaN(itemId)) return json({ error: 'Invalid item ID' }, { status: 400 });

  const limit = Math.max(1, Math.min(parseInt(url.searchParams.get('limit') || '20', 10), 50));

  try {
    const threads = await getForumThreadsByItem(itemId, limit);
    return json({ threads });
  } catch (err) {
    console.error('[api/forum/threads/item] Error:', err.message);
    return json({ error: 'Internal server error' }, { status: 500 });
  }
}

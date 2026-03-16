// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getForumThreads } from '$lib/server/db.js';

const VALID_TYPES = new Set(['selling', 'buying', 'all']);
const VALID_SORTS = new Set(['activity', 'created', 'comments']);
const MAX_LIMIT = 200;

export async function GET({ url }) {
  const type = url.searchParams.get('type') || 'all';
  const sort = url.searchParams.get('sort') || 'activity';
  const query = (url.searchParams.get('q') || '').trim();
  const excludeClosed = url.searchParams.get('excludeClosed') !== 'false';
  let limit = parseInt(url.searchParams.get('limit') || '50', 10);
  let offset = parseInt(url.searchParams.get('offset') || '0', 10);

  if (!VALID_TYPES.has(type)) return json({ error: 'Invalid type' }, { status: 400 });
  if (!VALID_SORTS.has(sort)) return json({ error: 'Invalid sort' }, { status: 400 });
  if (query.length > 200) return json({ error: 'Query too long' }, { status: 400 });

  limit = Math.max(1, Math.min(limit, MAX_LIMIT));
  offset = Math.max(0, offset);

  try {
    const result = await getForumThreads({ type, sort, limit, offset, excludeClosed, query });
    return json(result);
  } catch (err) {
    console.error('[api/forum/threads] Error:', err.message);
    return json({ error: 'Internal server error' }, { status: 500 });
  }
}

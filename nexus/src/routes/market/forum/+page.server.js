// @ts-nocheck
import { getForumThreads, getForumStats } from '$lib/server/db.js';

export async function load() {
  const [result, stats] = await Promise.all([
    getForumThreads({ type: 'all', sort: 'activity', limit: 200, offset: 0, excludeClosed: true }),
    getForumStats(),
  ]);

  return {
    threads: result.threads,
    stats,
  };
}

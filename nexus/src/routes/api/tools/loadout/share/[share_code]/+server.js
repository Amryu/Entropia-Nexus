//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getLoadoutByShareCode } from '$lib/server/db.js';

export async function GET({ params }) {
  const shareCode = params.share_code;
  if (!shareCode) {
    return getResponse({ error: 'Share code is required.' }, 400);
  }

  try {
    const record = await getLoadoutByShareCode(shareCode);
    if (!record) {
      return getResponse({ error: 'Loadout not found.' }, 404);
    }

    return getResponse({
      id: record.id,
      name: record.name,
      data: record.data,
      share_code: record.share_code,
      public: record.public,
      created_at: record.created_at,
      last_update: record.last_update
    }, 200);
  } catch (error) {
    console.error('Error fetching shared loadout:', error);
    return getResponse({ error: 'Failed to fetch shared loadout.' }, 500);
  }
}

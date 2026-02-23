//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireGrantAPI } from '$lib/server/auth.js';
import { getSkillImportDeltas } from '$lib/server/skillsDb.js';

export async function GET({ params, locals }) {
  const user = requireGrantAPI(locals, 'skills.read');

  const importId = parseInt(params.id, 10);
  if (!Number.isFinite(importId) || importId <= 0) {
    return getResponse({ error: 'Invalid import ID.' }, 400);
  }

  try {
    const deltas = await getSkillImportDeltas(importId, user.id);
    return getResponse(deltas, 200);
  } catch (error) {
    console.error('Error fetching skill import deltas:', error);
    return getResponse({ error: 'Failed to fetch import deltas.' }, 500);
  }
}

// @ts-nocheck
import { countOpenChangesForEntity, getChangeEntities } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

// Returns the count of open (Draft/Pending/DirectApply/ApplyFailed) changes for
// each requested entity type. Used to block cross-entity edits on Skill and
// Profession wiki pages (their relation arrays share junction tables, so
// concurrent approvals would race on the bot side).
//
// GET /api/changes/any-open?entity=Skill,Profession
export async function GET({ url }) {
  const param = url.searchParams.get('entity');
  if (!param) {
    return getResponse({ error: 'Missing required query parameter: entity' }, 400);
  }

  const validEntities = await getChangeEntities();
  const requested = param.split(',').map(s => s.trim()).filter(Boolean);
  const invalid = requested.filter(e => !validEntities.includes(e));
  if (invalid.length > 0) {
    return getResponse({ error: `Invalid entity. Must be one of: ${validEntities.join(', ')}` }, 400);
  }

  const counts = {};
  await Promise.all(requested.map(async e => {
    counts[e] = await countOpenChangesForEntity(e);
  }));

  return getResponse({ counts }, 200);
}

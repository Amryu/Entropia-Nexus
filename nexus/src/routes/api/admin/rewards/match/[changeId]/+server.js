// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth';
import { getMatchingRules } from '$lib/server/db';
import { pool } from '$lib/server/db';
import { compareJson } from '$lib/utils/compareJson';

export async function GET({ params, locals }) {
  requireAdminAPI(locals);

  const changeResult = await pool.query(
    'SELECT entity, type, data FROM changes WHERE id = $1',
    [parseInt(params.changeId)]
  );

  const change = changeResult.rows[0];
  if (!change) {
    return json({ error: 'Change not found' }, { status: 404 });
  }

  const dataKeys = await getChangedDataKeys(change);
  const subType = change.entity === 'Location' ? change.data?.Properties?.Type : null;
  const rules = await getMatchingRules(change.entity, change.type, dataKeys, subType);

  return json({ rules, changed_keys: dataKeys });
}

async function getChangedDataKeys(change) {
  if (!change?.data) return [];
  if (change.type === 'Create') return Object.keys(change.data);
  if (change.type !== 'Update') return [];

  const rawChangeId = change.data.Id;
  if (!Number.isFinite(Number(rawChangeId))) return [];

  const apartmentId = change.entity === 'Apartment'
    ? (Number(rawChangeId) > 300000 ? Number(rawChangeId) - 300000 : Number(rawChangeId))
    : Number(rawChangeId);
  const fetchId = change.entity === 'Apartment' ? apartmentId : rawChangeId;
  const fetchUrl = `${process.env.API_URL}/${getEntityApiCollection(change.entity)}/${fetchId}`;

  const entity = await fetch(fetchUrl)
    .then(res => res.status === 404 ? Promise.resolve({}) : res.json())
    .catch(_ => null);
  if (!entity) return [];

  const diff = compareJson(entity, change.data);
  if (!diff || Array.isArray(diff)) return [];

  return extractChangedTopLevelKeys(diff);
}

function getEntityApiCollection(entityType) {
  switch (entityType) {
    case 'TeleportChip':
    case 'TeleportationChip':
      return 'teleportationchips';
    case 'CreatureControlCapsule':
    case 'Capsule':
      return 'capsules';
    default:
      return `${entityType.toLowerCase()}s`;
  }
}

function extractChangedTopLevelKeys(diffObject) {
  return Object.entries(diffObject)
    .filter(([key, value]) => key !== '_status' && isDiffNodeChanged(value))
    .map(([key]) => key);
}

function isDiffNodeChanged(node) {
  if (Array.isArray(node)) return node.length > 0;
  if (!node || typeof node !== 'object') return false;
  if (node._changed === true || node._status) return true;
  return Object.entries(node)
    .some(([key, value]) => !key.startsWith('_') && isDiffNodeChanged(value));
}

// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getRoleGrants, setRoleGrants } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

export async function GET({ params, locals }) {
  requireGrant(locals, 'admin.users');
  const grants = await getRoleGrants(params.id);
  return json(grants);
}

export async function PUT({ params, request, locals }) {
  requireGrant(locals, 'admin.users');
  const body = await request.json();

  if (!Array.isArray(body.grants)) {
    return json({ error: 'grants must be an array of { key, granted } objects' }, { status: 400 });
  }

  await setRoleGrants(params.id, body.grants);
  const updated = await getRoleGrants(params.id);
  return json(updated);
}

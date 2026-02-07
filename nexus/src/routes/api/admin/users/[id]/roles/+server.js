// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getUserRoles, setUserRoles } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

export async function GET({ params, locals }) {
  requireGrant(locals, 'admin.users');
  const roles = await getUserRoles(BigInt(params.id));
  return json(roles);
}

export async function PUT({ params, request, locals }) {
  const user = requireGrant(locals, 'admin.users');
  const body = await request.json();

  if (!Array.isArray(body.roleIds)) {
    return json({ error: 'roleIds must be an array of role IDs' }, { status: 400 });
  }

  const realUser = locals.session?.realUser || locals.session?.user;
  await setUserRoles(BigInt(params.id), body.roleIds, realUser.id);
  const updated = await getUserRoles(BigInt(params.id));
  return json(updated);
}

// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getUserGrantOverrides, setUserGrantOverrides } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

export async function GET({ params, locals }) {
  requireGrant(locals, 'admin.users');
  const grants = await getUserGrantOverrides(BigInt(params.id));
  return json(grants);
}

export async function PUT({ params, request, locals }) {
  requireGrant(locals, 'admin.users');
  const body = await request.json();

  if (!Array.isArray(body.grants)) {
    return json({ error: 'grants must be an array of { key, granted } objects' }, { status: 400 });
  }

  const realUser = locals.session?.realUser || locals.session?.user;
  await setUserGrantOverrides(BigInt(params.id), body.grants, realUser.id);
  const updated = await getUserGrantOverrides(BigInt(params.id));
  return json(updated);
}

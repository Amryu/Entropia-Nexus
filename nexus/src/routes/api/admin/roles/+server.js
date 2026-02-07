// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getAllRoles, createRole } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

export async function GET({ locals }) {
  requireGrant(locals, 'admin.users');
  const roles = await getAllRoles();
  return json(roles);
}

export async function POST({ request, locals }) {
  requireGrant(locals, 'admin.users');
  const body = await request.json();

  if (!body.name?.trim()) {
    return json({ error: 'Role name is required' }, { status: 400 });
  }

  try {
    const role = await createRole({
      name: body.name.trim(),
      description: body.description?.trim() || null,
      parent_id: body.parent_id || null
    });
    return json(role, { status: 201 });
  } catch (e) {
    if (e.code === '23505') {
      return json({ error: 'A role with that name already exists' }, { status: 409 });
    }
    throw e;
  }
}

// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getRoleById, updateRole, deleteRole } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

export async function GET({ params, locals }) {
  requireGrant(locals, 'admin.users');
  const role = await getRoleById(params.id);
  if (!role) return json({ error: 'Role not found' }, { status: 404 });
  return json(role);
}

export async function PUT({ params, request, locals }) {
  requireGrant(locals, 'admin.users');
  const body = await request.json();

  if (!body.name?.trim()) {
    return json({ error: 'Role name is required' }, { status: 400 });
  }

  try {
    const role = await updateRole(params.id, {
      name: body.name.trim(),
      description: body.description?.trim() || null,
      parent_id: body.parent_id || null
    });
    if (!role) return json({ error: 'Role not found' }, { status: 404 });
    return json(role);
  } catch (e) {
    if (e.code === '23505') {
      return json({ error: 'A role with that name already exists' }, { status: 409 });
    }
    throw e;
  }
}

export async function DELETE({ params, locals }) {
  requireGrant(locals, 'admin.users');

  const role = await getRoleById(params.id);
  if (!role) return json({ error: 'Role not found' }, { status: 404 });

  // Prevent deletion of the built-in admin role
  if (role.name === 'admin') {
    return json({ error: 'Cannot delete the built-in admin role' }, { status: 400 });
  }

  await deleteRole(params.id);
  return json({ success: true });
}

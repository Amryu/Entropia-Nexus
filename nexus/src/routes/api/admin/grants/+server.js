// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getAllGrants } from '$lib/server/db.js';
import { requireGrant } from '$lib/server/auth.js';

export async function GET({ locals }) {
  requireGrant(locals, 'admin.users');
  const grants = await getAllGrants();
  return json(grants);
}

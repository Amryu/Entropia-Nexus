// @ts-nocheck
import { requireAdmin } from '$lib/server/auth.js';

export async function load({ locals }) {
  requireAdmin(locals);
  return {};
}

// @ts-nocheck
import { requireVerified } from '$lib/server/auth.js';

export async function load({ locals, url }) {
  requireVerified(locals, url.pathname);
  return {};
}

// @ts-nocheck
import { requireVerified } from '$lib/server/auth';

export async function load({ locals, url }) {
  requireVerified(locals, url.pathname);
}

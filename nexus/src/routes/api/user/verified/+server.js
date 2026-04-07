// @ts-nocheck
import { json } from '@sveltejs/kit';

/** Lightweight endpoint for polling verification status */
export function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) return json({ verified: false }, { status: 401 });
  return json({ verified: !!user.verified });
}

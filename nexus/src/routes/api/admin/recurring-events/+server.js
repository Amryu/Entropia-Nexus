// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdmin } from '$lib/server/auth.js';
import { apiCall } from '$lib/util.js';

export async function GET({ locals, fetch }) {
  requireAdmin(locals);
  const data = await apiCall(fetch, '/recurringevents');
  return json(data || []);
}

export async function POST({ request, locals, fetch }) {
  requireAdmin(locals);
  const body = await request.json();

  const apiBase = process.env.INTERNAL_API_URL || 'http://api:3000';
  const res = await fetch(`${apiBase}/recurringevents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await res.json();
  return json(data, { status: res.status });
}

// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdmin } from '$lib/server/auth.js';

export async function PUT({ params, request, locals, fetch }) {
  requireAdmin(locals);
  const body = await request.json();

  const apiBase = process.env.INTERNAL_API_URL || 'http://api:3000';
  const res = await fetch(`${apiBase}/recurringevents/${params.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await res.json();
  return json(data, { status: res.status });
}

export async function DELETE({ params, locals, fetch }) {
  requireAdmin(locals);

  const apiBase = process.env.INTERNAL_API_URL || 'http://api:3000';
  const res = await fetch(`${apiBase}/recurringevents/${params.id}`, {
    method: 'DELETE'
  });
  const data = await res.json();
  return json(data, { status: res.status });
}

// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getActiveRecurringEventNames } from '$lib/server/db.js';

export async function GET() {
  try {
    const active = await getActiveRecurringEventNames();
    return json({ active });
  } catch (err) {
    console.error('Error fetching active recurring events:', err);
    return json({ active: [] });
  }
}

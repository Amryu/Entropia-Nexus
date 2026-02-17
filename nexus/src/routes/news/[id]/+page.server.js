// @ts-nocheck
import { error } from '@sveltejs/kit';
import { getPublishedAnnouncementById } from '$lib/server/db.js';

export async function load({ params }) {
  const id = parseInt(params.id, 10);
  if (isNaN(id)) throw error(404, 'Not found');

  const announcement = await getPublishedAnnouncementById(id);
  if (!announcement) throw error(404, 'Not found');

  return { announcement };
}

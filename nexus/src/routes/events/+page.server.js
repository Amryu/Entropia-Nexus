// @ts-nocheck
import { getUpcomingEvents, getPastEvents } from '$lib/server/db.js';

export async function load() {
  const [upcoming, past] = await Promise.all([
    getUpcomingEvents(50),
    getPastEvents(100)
  ]);

  return { upcoming, past };
}

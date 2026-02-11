// @ts-nocheck
import { apiCall } from '$lib/util';

export async function load({ fetch, params }) {
  const [offer, availability, planets] = await Promise.all([
    apiCall(fetch, `/api/rental/${params.id}`),
    apiCall(fetch, `/api/rental/${params.id}/availability?months=3`),
    apiCall(fetch, '/planets')
  ]);

  // Attach planet name from the separate entity database
  if (offer && offer.planet_id && Array.isArray(planets)) {
    const planet = planets.find(p => p.Id === offer.planet_id);
    if (planet) offer.planet_name = planet.Name;
  }

  return {
    offer,
    availability: availability || { blockedDates: [], bookedDates: [] }
  };
}

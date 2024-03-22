// @ts-nocheck
import { apiCall, pageResponse } from '$lib/util.js';

let items;

export async function load({ fetch, params }) {
  if (!items) {
    items = await apiCall(fetch, '/planets');
  }
  
  if (!params.planet) {
    return pageResponse(items);
  }

  let planet = items.find((planet) => planet.Name.replace(/[^a-zA-Z0-9]/g, '').toLowerCase() === params.planet);

  if (planet == null) {
    return pageResponse(items, null, null, 404);
  }

  let locations = await apiCall(fetch, '/locations?Planet=' + planet.Name);
  let areas = await apiCall(fetch, '/areas?Planet=' + planet.Name);

  locations = locations.map(location => {
    const matchingArea = areas.find(area => 
      area.Name === location.Name && 
      area.Properties.Type === location.Properties.Type && 
      area.Properties.Type.endsWith("Area")
    );
    
    return matchingArea || location;
  });

  if (!params.planet && !params.slug) {
    return pageResponse(
      items,
      null,
      {
        locations,
        areas,
        planet,
      }
    );
  }

  let location = areas.find((area) => area.Name === params.slug)
    ?? locations.find((location) => location.Name === params.slug);

  if (location === null) {
    return pageResponse(
      items,
      null,
      {
        locations,
        areas,
        planet
      },
      404);
  }

  return pageResponse(
    items,
    location,
    {
      locations,
      areas,
      planet
    }
  );
}
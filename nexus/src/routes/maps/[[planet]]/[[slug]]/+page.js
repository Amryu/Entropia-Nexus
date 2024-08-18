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

  let [locations, areas, mobSpawns] = await Promise.all([
    apiCall(fetch, '/locations?Planet=' + planet.Name),
    apiCall(fetch, '/areas?Planet=' + planet.Name),
    apiCall(fetch, '/mobspawns?Planet=' + planet.Name)
  ]);

  areas = areas.map(area => {
    const matchingMobSpawn = mobSpawns.find(mobSpawn => mobSpawn.Id === area.Id);

    return matchingMobSpawn || area;
  });

  locations = locations.map(location => {
    const matchingArea = areas.find(area => 
      area.Name === location.Name && 
      area.Properties.Type.endsWith("Area") &&
      area.Properties.Coordinates.Longitude === location.Properties.Coordinates.Longitude &&
      area.Properties.Coordinates.Latitude === location.Properties.Coordinates.Latitude &&
      area.Properties.Coordinates.Altitude === location.Properties.Coordinates.Altitude &&
      area.Properties.Type === location.Properties.Type
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

  let location = areas.find((area) => area.Id == params.slug)
    ?? locations.find((location) => location.Id == params.slug);

  if (location === null) {
    return pageResponse(
      items,
      null,
      {
        locations,
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
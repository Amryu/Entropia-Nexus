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

  // Build a map of Id to object, preferring MobSpawn > Area > Location
  const byId = {};

  // 1. Add all locations (least specific)
  for (const loc of locations) {
    byId[loc.Id] = loc;
  }

  // 2. Add all areas (replace location if same Id or if area.Id + 200000 === location.Id)
  for (const area of areas) {
    byId[area.Id] = area;
    // Remove any location with area.Id + 200000 === location.Id
    const offsetId = area.Id + 200000;
    if (byId[offsetId] && byId[offsetId].Properties && !byId[offsetId].Properties.Shape) {
      delete byId[offsetId];
    }
  }

  // 3. Add all mobspawns (replace area if same Id)
  for (const mobSpawn of mobSpawns) {
    byId[mobSpawn.Id] = mobSpawn;
  }

  locations = Object.values(byId);

  // Check for duplicate IDs in the final combined dataset
  const idCounts = {};
  const duplicateIds = [];
  
  locations.forEach(location => {
    const id = location.Id;
    idCounts[id] = (idCounts[id] || 0) + 1;
    if (idCounts[id] === 2) {
      duplicateIds.push(id);
    }
  });

  if (duplicateIds.length > 0) {
    console.warn('Duplicate IDs found in locations:', duplicateIds);
    duplicateIds.forEach(duplicateId => {
      const duplicateItems = locations.filter(loc => loc.Id === duplicateId);
      console.warn(`ID ${duplicateId} appears ${duplicateItems.length} times:`, duplicateItems.map(item => ({
        Id: item.Id,
        Name: item.Name,
        Type: item.Properties.Type,
        HasShape: !!item.Properties.Shape,
        HasData: !!item.Properties.Data,
        Source: item.Properties.Shape ? 'area' : 'location'
      })));
    });
  }

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
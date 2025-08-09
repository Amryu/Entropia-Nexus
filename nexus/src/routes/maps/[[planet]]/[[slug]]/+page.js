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

  // Create a combined dataset: start with all areas (which have Shape/Data), then add locations that don't have corresponding areas
  let combinedLocations = [...areas];
  
  locations.forEach(location => {
    // Check if this location already exists as an area (using ID offset)
    const hasMatchingArea = areas.some(area => area.Id + 200000 === location.Id);
    if (!hasMatchingArea) {
      combinedLocations.push(location);
    }
  });

  locations = combinedLocations;

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

  console.log(`Final dataset: ${areas.length} areas, ${locations.length - areas.length} locations, ${locations.length} total`);
  console.log(`Areas with Shape: ${areas.filter(a => a.Properties.Shape).length}, MobAreas: ${areas.filter(a => a.Properties.Type === 'MobArea').length}`);

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
// @ts-nocheck
import { apiCall, pageResponse, loadPendingChangesData } from '$lib/util.js';
import { MAX_PENDING_CREATES } from '$lib/constants';

let items;

export async function load({ fetch, params, url, parent }) {
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

  const parentData = await parent();
  const session = parentData.session;

  const mode = url.searchParams.get('mode') || 'view';
  const isCreateMode = mode === 'create' && !!(session?.user?.verified || session?.user?.isAdmin || session?.user?.administrator);
  const changeId = url.searchParams.get('changeId');

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

  const response = pageResponse(
    items,
    location,
    {
      locations,
      areas,
      planet
    }
  );

  response.session = session;
  response.isCreateMode = isCreateMode;

  // If a changeId is provided (editing an existing pending create), fetch that change
  if (changeId && isCreateMode) {
    try {
      const changeRes = await fetch(`/api/changes/${changeId}`);
      if (changeRes.ok) {
        const change = await changeRes.json();
        response.existingChange = change;
        response.pendingChange = change;
      }
    } catch (e) {
      console.warn('Failed to fetch existing change:', e);
    }
  }

  const getEntityType = (loc) => {
    if (!loc) return null;
    if (loc?.Properties?.Type === 'MobArea') return null;
    if (loc?.Properties?.Type === 'Shop') return null;
    if (loc?.Properties?.Type === 'Apartment') return 'Apartment';
    if (loc?.Properties?.Shape || loc?.Properties?.Type?.endsWith('Area')) return 'Area';
    return 'Location';
  };

  const entityType = getEntityType(location);
  const rawEntityId = location?.Id ?? null;
  const numericEntityId = rawEntityId != null ? Number(rawEntityId) : null;
  const entityId = entityType === 'Apartment' && Number.isFinite(numericEntityId)
    ? numericEntityId - 300000
    : rawEntityId;
  const pendingData = entityType
    ? await loadPendingChangesData(fetch, session?.user, {
      entity: entityType,
      entityId,
      changeId,
      isAdmin: session?.user?.isAdmin || false
    })
    : null;

  const [locationPending, areaPending, apartmentPending] = session?.user
    ? await Promise.all([
      loadPendingChangesData(fetch, session.user, {
        entity: 'Location',
        entityId: null,
        changeId: null,
        isAdmin: session.user?.isAdmin || false
      }),
      loadPendingChangesData(fetch, session.user, {
        entity: 'Area',
        entityId: null,
        changeId: null,
        isAdmin: session.user?.isAdmin || false
      }),
      loadPendingChangesData(fetch, session.user, {
        entity: 'Apartment',
        entityId: null,
        changeId: null,
        isAdmin: session.user?.isAdmin || false
      })
    ])
    : [{}, {}, {}];

  const combinedCreates = [
    ...(locationPending?.userPendingCreates || []),
    ...(areaPending?.userPendingCreates || []),
    ...(apartmentPending?.userPendingCreates || [])
  ];
  const combinedUpdates = [
    ...(locationPending?.userPendingUpdates || []),
    ...(areaPending?.userPendingUpdates || []),
    ...(apartmentPending?.userPendingUpdates || [])
  ];

  response.pendingChange = pendingData?.pendingChange || response.pendingChange || null;
  response.userPendingCreates = combinedCreates;
  response.userPendingUpdates = combinedUpdates;

  const totalPendingCreates =
    (locationPending?.pendingCreatesCount || 0) +
    (areaPending?.pendingCreatesCount || 0) +
    (apartmentPending?.pendingCreatesCount || 0);
  response.pendingCreatesCount = totalPendingCreates;
  response.canCreateNew = session?.user?.isAdmin ? true : totalPendingCreates < MAX_PENDING_CREATES;

  return response;
}

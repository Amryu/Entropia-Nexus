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
  const changeId = url.searchParams.get('changeId');

  let locations = await apiCall(fetch, '/locations?Planet=' + planet.Name) || [];

  if (!params.planet && !params.slug) {
    return pageResponse(
      items,
      null,
      {
        locations,
        planet,
      }
    );
  }

  let location = locations.find((loc) => loc.Id == params.slug);

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
      planet
    }
  );

  response.session = session;

  const getEntityType = (loc) => {
    if (!loc) return null;
    if (loc?.Properties?.AreaType === 'MobArea') return null;
    if (loc?.Properties?.Type === 'Shop') return null;
    if (loc?.Properties?.Type === 'Apartment') return 'Apartment';
    if (loc?.Properties?.Type === 'Area' || loc?.Properties?.Shape) return 'Area';
    return 'Location';
  };

  const entityType = getEntityType(location);
  const rawEntityId = location?.Id ?? null;
  const numericEntityId = rawEntityId != null ? Number(rawEntityId) : null;
  const entityId = entityType === 'Apartment' && Number.isFinite(numericEntityId)
    ? numericEntityId - 300000
    : rawEntityId;
  const userGrants = session?.user?.grants || [];
  const hasEditGrant = userGrants.some(g => g.startsWith('wiki.'));
  const isAdmin = userGrants.includes('wiki.approve');

  const pendingData = entityType
    ? await loadPendingChangesData(fetch, session?.user, {
      entity: entityType,
      entityId,
      changeId,
      isAdmin,
      hasEditGrant
    })
    : null;

  const [locationPending, areaPending, apartmentPending] = session?.user
    ? await Promise.all([
      loadPendingChangesData(fetch, session.user, {
        entity: 'Location',
        entityId: null,
        changeId: null,
        isAdmin,
        hasEditGrant
      }),
      loadPendingChangesData(fetch, session.user, {
        entity: 'Area',
        entityId: null,
        changeId: null,
        isAdmin,
        hasEditGrant
      }),
      loadPendingChangesData(fetch, session.user, {
        entity: 'Apartment',
        entityId: null,
        changeId: null,
        isAdmin,
        hasEditGrant
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
  response.canCreateNew = isAdmin ? true : totalPendingCreates < MAX_PENDING_CREATES;

  // Load ALL pending changes for this planet (any author) — for map editor overlay
  if (session?.user) {
    try {
      const allPendingRes = await fetch(
        `/api/changes?entity=Location,Area&state=Pending,Draft&planet=${encodeURIComponent(planet.Name)}&limit=100`
      );
      response.planetPendingChanges = allPendingRes.ok ? await allPendingRes.json() : [];
    } catch {
      response.planetPendingChanges = [];
    }
  } else {
    response.planetPendingChanges = [];
  }

  return response;
}

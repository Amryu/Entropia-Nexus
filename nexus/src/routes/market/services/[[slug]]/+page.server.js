// @ts-nocheck
import { apiCall } from '$lib/util';

export async function load({ fetch, params, url }) {
  const slug = params.slug;
  const mode = url.searchParams.get('mode') || 'view';

  // Only fetch essential service data - entity data will be lazy loaded on client
  const [services, allPlanets] = await Promise.all([
    apiCall(fetch, '/api/services?include_details=true'),
    apiCall(fetch, '/planets')
  ]);

  // Filter to main planets only
  const mainPlanets = (allPlanets || []).filter(planet => {
    const subPlanets = [
      'Asteroid F.O.M.A.',
      'Crystal Palace',
      'Space',
      'Setesh',
      'ARIS',
      'Arkadia Moon',
      'Arkadia Underground',
      'HELL',
      'Secret Island',
      'Hunt The THING',
      'Ancient Greece',
      'DSEC9'
    ];
    return planet.Id > 0 && !subPlanets.includes(planet.Name);
  });

  // Group services by type for filtering
  const servicesByType = {
    healing: [],
    dps: [],
    transportation: [],
    custom: []
  };

  if (services) {
    for (const service of services) {
      if (service.type && servicesByType[service.type]) {
        servicesByType[service.type].push(service);
      }
    }
  }

  // If slug provided, fetch specific service and its availability
  let service = null;
  let availability = [];
  let pilots = [];
  let activeRequest = null;
  if (slug) {
    const serviceId = parseInt(slug);
    if (!isNaN(serviceId)) {
      // Fetch service, availability, and user's active request in parallel
      const [serviceData, availabilityData, activeRequestData] = await Promise.all([
        apiCall(fetch, `/api/services/${serviceId}`),
        apiCall(fetch, `/api/services/${serviceId}/availability`),
        apiCall(fetch, `/api/services/${serviceId}/my-request`)
      ]);
      service = serviceData;
      availability = availabilityData || [];
      activeRequest = activeRequestData || null;

      // Fetch pilots for transportation services (only for warp_privateer, but fetch for all to simplify)
      if (service?.type === 'transportation') {
        pilots = await apiCall(fetch, `/api/services/${serviceId}/pilots`) || [];
      }
    }
  }

  return {
    services,
    servicesByType,
    planets: mainPlanets,
    service,
    availability,
    pilots,
    activeRequest,
    mode
  };
}

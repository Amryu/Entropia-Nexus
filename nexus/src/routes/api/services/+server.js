//@ts-nocheck
import { getServices, createService, upsertServiceHealingDetails, upsertServiceDpsDetails, upsertServiceTransportationDetails, addServiceEquipment, getServiceHealingDetails, getServiceDpsDetails, getServiceTransportationDetails } from "$lib/server/db.js";
import { getResponse, apiCall } from "$lib/util.js";
import { checkRateLimit } from '$lib/server/rateLimiter.js';

// GET all services (with optional filters)
export async function GET({ url, locals, fetch }) {
  const filters = {};

  const type = url.searchParams.get('type');
  if (type) filters.type = type;

  const planetId = url.searchParams.get('planet_id');
  if (planetId) filters.planet_id = parseInt(planetId);

  const includeDetails = url.searchParams.get('include_details') === 'true';

  try {
    const services = await getServices(filters);
    
    // Fetch planets to map planet_id to planet_name
    const planets = await apiCall(fetch, '/planets');
    const planetMap = {};
    if (planets && Array.isArray(planets)) {
      planets.forEach(planet => {
        planetMap[planet.Id] = planet.Name;
      });
    }
    
    // Add planet_name to each service
    if (services && Array.isArray(services)) {
      services.forEach(service => {
        service.planet_name = service.planet_id ? planetMap[service.planet_id] : null;
      });
    }
    
    // If include_details is true, fetch type-specific details for each service
    if (includeDetails && services) {
      await Promise.all(services.map(async (service) => {
        if (service.type === 'healing') {
          service.healing_details = await getServiceHealingDetails(service.id);
        } else if (service.type === 'dps') {
          service.dps_details = await getServiceDpsDetails(service.id);
        } else if (service.type === 'transportation') {
          service.transportation_details = await getServiceTransportationDetails(service.id);
        }
      }));
    }
    
    return getResponse(services, 200);
  } catch (error) {
    console.error('Error fetching services:', error);
    return getResponse({ error: 'Failed to fetch services' }, 500);
  }
}

// POST create new service
export async function POST({ request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to create a service.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before creating services.' }, 403);
  }

  const rateCheck = checkRateLimit(`services:create:${user.id}`, 5, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }
  const rateCheckH = checkRateLimit(`services:create-h:${user.id}`, 15, 3_600_000);
  if (!rateCheckH.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  // Validate required fields
  if (!body.title || !body.title.trim()) {
    return getResponse({ error: 'Service title is required.' }, 400);
  }
  if (!body.type) {
    return getResponse({ error: 'Service type is required.' }, 400);
  }

  const validTypes = ['healing', 'dps', 'transportation', 'crafting', 'hunting', 'mining', 'custom'];
  if (!validTypes.includes(body.type)) {
    return getResponse({ error: 'Invalid service type.' }, 400);
  }

  // Validate equipment count
  if (body.equipment && Array.isArray(body.equipment) && body.equipment.length > 50) {
    return getResponse({ error: 'Equipment list cannot exceed 50 items.' }, 400);
  }

  try {
    // Create the service
    const serviceData = {
      user_id: user.id,
      type: body.type,
      custom_type_name: body.type === 'custom' ? body.custom_type_name : null,
      title: body.title.trim(),
      description: body.description?.trim() || null,
      planet_id: body.planet_id || null,
      willing_to_travel: body.willing_to_travel || false,
      travel_fee: body.travel_fee ? parseFloat(parseFloat(body.travel_fee).toFixed(2)) : null
    };

    const service = await createService(serviceData);

    // Create type-specific details if provided
    if (body.type === 'healing' && body.healing_details) {
      const healingDetails = {
        ...body.healing_details,
        rate_per_hour: body.healing_details.rate_per_hour ? parseFloat(parseFloat(body.healing_details.rate_per_hour).toFixed(2)) : null
      };
      await upsertServiceHealingDetails(service.id, healingDetails);
    } else if (body.type === 'dps' && body.dps_details) {
      const dpsDetails = {
        ...body.dps_details,
        rate_per_hour: body.dps_details.rate_per_hour ? parseFloat(parseFloat(body.dps_details.rate_per_hour).toFixed(2)) : null
      };
      await upsertServiceDpsDetails(service.id, dpsDetails);
    } else if (body.type === 'transportation' && body.transportation_details) {
      await upsertServiceTransportationDetails(service.id, body.transportation_details);
    }

    // Save equipment if provided
    if (body.equipment && Array.isArray(body.equipment)) {
      for (const equip of body.equipment) {
        if (equip.item_id && equip.item_type) {
          await addServiceEquipment(service.id, {
            ...equip,
            extra_price: equip.extra_price ? parseFloat(parseFloat(equip.extra_price).toFixed(2)) : null
          });
        }
      }
    }

    return getResponse(service, 201);
  } catch (error) {
    console.error('Error creating service:', error);
    return getResponse({ error: 'Failed to create service.' }, 500);
  }
}

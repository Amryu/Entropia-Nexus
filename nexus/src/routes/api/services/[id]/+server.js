//@ts-nocheck
import {
  getServiceById,
  updateService,
  deleteService,
  getServiceHealingDetails,
  getServiceDpsDetails,
  getServiceTransportationDetails,
  getServiceEquipment,
  getServiceArmorSets,
  getServiceAvailability,
  upsertServiceHealingDetails,
  upsertServiceDpsDetails,
  upsertServiceTransportationDetails,
  addServiceEquipment,
  deleteServiceEquipment,
  getServiceRequests,
  updateRequestStatus
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";
import { checkRateLimit } from '$lib/server/rateLimiter.js';

// GET single service with all details
export async function GET({ params, locals }) {
  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  try {
    const service = await getServiceById(serviceId);
    if (!service) {
      return getResponse({ error: 'Service not found.' }, 404);
    }

    // Fetch type-specific details
    if (service.type === 'healing') {
      service.healing_details = await getServiceHealingDetails(serviceId);
    } else if (service.type === 'dps') {
      service.dps_details = await getServiceDpsDetails(serviceId);
    } else if (service.type === 'transportation') {
      service.transportation_details = await getServiceTransportationDetails(serviceId);
    }

    // Fetch equipment and armor sets
    service.equipment = await getServiceEquipment(serviceId);
    service.armor_sets = await getServiceArmorSets(serviceId);

    // Fetch availability
    service.availability = await getServiceAvailability(serviceId);

    // Note: review_stats removed - review_score column dropped in migration 010

    return getResponse(service, 200);
  } catch (error) {
    console.error('Error fetching service:', error);
    return getResponse({ error: 'Failed to fetch service.' }, 500);
  }
}

// PUT update service
export async function PUT({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to update a service.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before making changes.' }, 403);
  }

  const rateCheck = checkRateLimit(`services:update:${user.id}`, 20, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  // Check ownership
  const existingService = await getServiceById(serviceId);
  if (!existingService) {
    return getResponse({ error: 'Service not found.' }, 404);
  }

  if (existingService.user_id !== user.id && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only edit your own services.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  // Validate equipment count
  if (body.equipment !== undefined && Array.isArray(body.equipment) && body.equipment.length > 50) {
    return getResponse({ error: 'Equipment list cannot exceed 50 items.' }, 400);
  }

  // Check for active requests before deactivating
  if (body.is_active === false && existingService.is_active === true) {
    const allRequests = await getServiceRequests(serviceId);
    const activeRequests = allRequests.filter(r => ['accepted', 'in_progress'].includes(r.status));
    const pendingRequests = allRequests.filter(r => r.status === 'pending');

    // Block deactivation if there are accepted or in-progress requests
    if (activeRequests.length > 0) {
      return getResponse({
        error: `Cannot deactivate service with ${activeRequests.length} active request(s). Please complete or abort them first.`,
        activeRequests: activeRequests.length
      }, 400);
    }

    // Decline all pending requests when deactivating
    if (pendingRequests.length > 0 && body.declinePending !== false) {
      for (const request of pendingRequests) {
        await updateRequestStatus(request.id, 'declined');
      }
    }
  }

  try {
    // Update main service fields
    const serviceData = {
      type: body.type || existingService.type,
      custom_type_name: body.type === 'custom' ? body.custom_type_name : null,
      title: body.title?.trim() || existingService.title,
      description: body.description?.trim() || existingService.description,
      planet_id: body.planet_id !== undefined ? body.planet_id : existingService.planet_id,
      willing_to_travel: body.willing_to_travel !== undefined ? body.willing_to_travel : existingService.willing_to_travel,
      travel_fee: body.travel_fee !== undefined ? (body.travel_fee ? parseFloat(parseFloat(body.travel_fee).toFixed(2)) : null) : existingService.travel_fee,
      is_active: body.is_active !== undefined ? body.is_active : existingService.is_active
    };

    const service = await updateService(serviceId, serviceData);

    // Update type-specific details if provided
    if (body.healing_details) {
      const healingDetails = {
        ...body.healing_details,
        rate_per_hour: body.healing_details.rate_per_hour ? parseFloat(parseFloat(body.healing_details.rate_per_hour).toFixed(2)) : null
      };
      await upsertServiceHealingDetails(serviceId, healingDetails);
    }
    if (body.dps_details) {
      const dpsDetails = {
        ...body.dps_details,
        rate_per_hour: body.dps_details.rate_per_hour ? parseFloat(parseFloat(body.dps_details.rate_per_hour).toFixed(2)) : null
      };
      await upsertServiceDpsDetails(serviceId, dpsDetails);
    }
    if (body.transportation_details) {
      await upsertServiceTransportationDetails(serviceId, body.transportation_details);
    }

    // Handle equipment updates if provided
    if (body.equipment !== undefined && Array.isArray(body.equipment)) {
      // Delete existing equipment
      const existingEquipment = await getServiceEquipment(serviceId);
      for (const equip of existingEquipment) {
        await deleteServiceEquipment(equip.id);
      }
      
      // Add new equipment
      for (const equip of body.equipment) {
        if (equip.item_id && equip.item_type) {
          await addServiceEquipment(serviceId, {
            ...equip,
            extra_price: equip.extra_price ? parseFloat(parseFloat(equip.extra_price).toFixed(2)) : null
          });
        }
      }
    }

    return getResponse(service, 200);
  } catch (error) {
    console.error('Error updating service:', error);
    return getResponse({ error: 'Failed to update service.' }, 500);
  }
}

// DELETE service (soft delete)
export async function DELETE({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to delete a service.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before making changes.' }, 403);
  }

  const rateCheck = checkRateLimit(`services:delete:${user.id}`, 5, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  // Check ownership
  const existingService = await getServiceById(serviceId);
  if (!existingService) {
    return getResponse({ error: 'Service not found.' }, 404);
  }

  if (existingService.user_id !== user.id && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only delete your own services.' }, 403);
  }

  try {
    await deleteService(serviceId);
    return getResponse({ success: true, message: 'Service deleted successfully.' }, 200);
  } catch (error) {
    console.error('Error deleting service:', error);
    return getResponse({ error: 'Failed to delete service.' }, 500);
  }
}

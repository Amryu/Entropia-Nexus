//@ts-nocheck
import {
  getServiceById,
  getServiceEquipment,
  addServiceEquipment,
  updateServiceEquipment,
  deleteServiceEquipment
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// GET service equipment
export async function GET({ params, locals }) {
  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  try {
    const equipment = await getServiceEquipment(serviceId);
    return getResponse(equipment, 200);
  } catch (error) {
    console.error('Error fetching equipment:', error);
    return getResponse({ error: 'Failed to fetch equipment.' }, 500);
  }
}

// POST add equipment
export async function POST({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account.' }, 403);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  // Check ownership
  const service = await getServiceById(serviceId);
  if (!service) {
    return getResponse({ error: 'Service not found.' }, 404);
  }
  if (service.user_id !== user.id && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only edit your own services.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON.' }, 400);
  }

  if (!body.item_id || !body.item_type) {
    return getResponse({ error: 'item_id and item_type are required.' }, 400);
  }

  try {
    const equipment = await addServiceEquipment(serviceId, body);
    return getResponse(equipment, 201);
  } catch (error) {
    console.error('Error adding equipment:', error);
    return getResponse({ error: 'Failed to add equipment.' }, 500);
  }
}

// PUT update all equipment (replace)
export async function PUT({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account.' }, 403);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  // Check ownership
  const service = await getServiceById(serviceId);
  if (!service) {
    return getResponse({ error: 'Service not found.' }, 404);
  }
  if (service.user_id !== user.id && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only edit your own services.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON.' }, 400);
  }

  if (!Array.isArray(body.equipment)) {
    return getResponse({ error: 'equipment must be an array.' }, 400);
  }

  try {
    // Get existing equipment
    const existing = await getServiceEquipment(serviceId);
    const existingIds = new Set(existing.map(e => e.id));
    const newIds = new Set();

    // Update or add equipment
    for (const item of body.equipment) {
      if (item.id && existingIds.has(item.id)) {
        await updateServiceEquipment(item.id, item);
        newIds.add(item.id);
      } else {
        const added = await addServiceEquipment(serviceId, item);
        newIds.add(added.id);
      }
    }

    // Delete removed equipment
    for (const item of existing) {
      if (!newIds.has(item.id)) {
        await deleteServiceEquipment(item.id);
      }
    }

    const updated = await getServiceEquipment(serviceId);
    return getResponse(updated, 200);
  } catch (error) {
    console.error('Error updating equipment:', error);
    return getResponse({ error: 'Failed to update equipment.' }, 500);
  }
}

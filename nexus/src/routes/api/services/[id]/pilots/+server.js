// @ts-nocheck
import {
  getServiceById,
  getServicePilots,
  addServicePilot,
  removeServicePilot
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { getUserByUsernameOrDiscordTag } from "$lib/server/db.js";

// GET - List all pilots for a service
export async function GET({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
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
    return getResponse({ error: 'You can only manage pilots for your own services.' }, 403);
  }

  if (service.type !== 'transportation') {
    return getResponse({ error: 'Pilots can only be added to transportation services.' }, 400);
  }

  try {
    const pilots = await getServicePilots(serviceId);
    return getResponse(pilots, 200);
  } catch (error) {
    console.error('Error fetching pilots:', error);
    return getResponse({ error: 'Failed to fetch pilots.' }, 500);
  }
}

// POST - Add a pilot to a service
export async function POST({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const rateCheck = checkRateLimit(`services:pilots:${user.id}`, 15, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
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
    return getResponse({ error: 'You can only manage pilots for your own services.' }, 403);
  }

  if (service.type !== 'transportation') {
    return getResponse({ error: 'Pilots can only be added to transportation services.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const { identifier } = body; // username or discord tag

  if (!identifier || typeof identifier !== 'string') {
    return getResponse({ error: 'Pilot username or Discord tag is required.' }, 400);
  }

  try {
    // Find user by username or discord tag
    const pilotUser = await getUserByUsernameOrDiscordTag(identifier.trim());

    if (!pilotUser) {
      return getResponse({ error: `User not found: ${identifier}` }, 404);
    }

    // Check if user is verified
    if (!pilotUser.verified) {
      return getResponse({ error: 'User must be verified to be added as a pilot.' }, 400);
    }

    // Check if user is already the owner
    if (pilotUser.id === service.user_id) {
      return getResponse({ error: 'Service owner cannot be added as a pilot.' }, 400);
    }

    // Check if already a pilot
    const existingPilots = await getServicePilots(serviceId);
    if (existingPilots.some(p => p.user_id === pilotUser.id)) {
      return getResponse({ error: 'User is already a pilot for this service.' }, 400);
    }

    // Add pilot
    const pilot = await addServicePilot(serviceId, pilotUser.id, user.id);

    return getResponse({
      ...pilot,
      username: pilotUser.username,
      eu_name: pilotUser.eu_name,
      message: `${pilotUser.username} added as pilot.`
    }, 201);
  } catch (error) {
    console.error('Error adding pilot:', error);
    return getResponse({ error: 'Failed to add pilot.' }, 500);
  }
}

// DELETE - Remove a pilot from a service
export async function DELETE({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const rateCheck = checkRateLimit(`services:pilots:${user.id}`, 15, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
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
    return getResponse({ error: 'You can only manage pilots for your own services.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const { userId } = body;

  if (!userId) {
    return getResponse({ error: 'Pilot user ID is required.' }, 400);
  }

  const pilotUserId = typeof userId === 'string' ? parseInt(userId) : userId;

  if (isNaN(pilotUserId)) {
    return getResponse({ error: 'Invalid pilot user ID.' }, 400);
  }

  try {
    const removed = await removeServicePilot(serviceId, pilotUserId);

    if (!removed) {
      return getResponse({ error: 'Pilot not found for this service.' }, 404);
    }

    return getResponse({ message: 'Pilot removed successfully.' }, 200);
  } catch (error) {
    console.error('Error removing pilot:', error);
    return getResponse({ error: 'Failed to remove pilot.' }, 500);
  }
}

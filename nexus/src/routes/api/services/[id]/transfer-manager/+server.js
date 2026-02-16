// @ts-nocheck
import { getServiceById, getUserById, isServicePilot, transferManager } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

export async function POST({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before making changes.' }, 403);
  }

  const rateCheck = checkRateLimit(`services:transfer:${user.id}`, 5, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  const service = await getServiceById(serviceId);
  if (!service) {
    return getResponse({ error: 'Service not found.' }, 404);
  }

  // Only manager, owner, or admin can transfer
  const isManager = service.user_id === user.id;
  const isOwner = service.owner_user_id && service.owner_user_id === user.id;
  const isAdmin = user?.grants?.includes('admin.panel');

  if (!isManager && !isOwner && !isAdmin) {
    return getResponse({ error: 'Only the manager or owner can transfer the manager role.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const newManagerUserId = typeof body.newManagerUserId === 'string'
    ? parseInt(body.newManagerUserId)
    : body.newManagerUserId;

  if (!newManagerUserId || isNaN(newManagerUserId)) {
    return getResponse({ error: 'New manager user ID is required.' }, 400);
  }

  // Verify the new manager exists and is verified
  const newManager = await getUserById(newManagerUserId);
  if (!newManager) {
    return getResponse({ error: 'User not found.' }, 400);
  }
  if (!newManager.verified) {
    return getResponse({ error: 'The new manager must have a verified account.' }, 400);
  }

  // New manager must be a current pilot or the owner
  const isPilot = await isServicePilot(serviceId, newManagerUserId);
  const isNewManagerOwner = service.owner_user_id === newManagerUserId;

  if (!isPilot && !isNewManagerOwner) {
    return getResponse({ error: 'New manager must be a current pilot or the owner.' }, 400);
  }

  // Cannot transfer to the current manager
  if (newManagerUserId === service.user_id) {
    return getResponse({ error: 'This user is already the manager.' }, 400);
  }

  try {
    await transferManager(serviceId, newManagerUserId, service.user_id);
    const updatedService = await getServiceById(serviceId);
    return getResponse({ success: true, service: updatedService }, 200);
  } catch (err) {
    console.error('Error transferring manager:', err);
    return getResponse({ error: 'Failed to transfer manager role.' }, 500);
  }
}

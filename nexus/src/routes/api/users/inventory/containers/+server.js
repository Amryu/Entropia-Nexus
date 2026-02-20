//@ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  getUserContainerNames,
  upsertContainerName,
  deleteContainerName,
  remapContainerNames
} from '$lib/server/inventory.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

const MAX_PATH_LENGTH = 500;
const MAX_NAME_LENGTH = 100;
const MAX_ITEM_NAME_LENGTH = 255;
const MAX_REMAPS = 500;

/**
 * GET /api/users/inventory/containers — Get custom container names
 */
export async function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  try {
    const names = await getUserContainerNames(user.id);
    return getResponse(names, 200);
  } catch (err) {
    console.error('Error fetching container names:', err);
    return getResponse({ error: 'Failed to fetch container names' }, 500);
  }
}

/**
 * PUT /api/users/inventory/containers — Upsert a container name
 * Body: { container_path, custom_name, container_ref?, item_name }
 */
export async function PUT({ request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  const rateCheck = checkRateLimit(`inv:container-name:${user.id}`, 30, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many updates. Please slow down.' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  const containerPath = typeof body.container_path === 'string' ? body.container_path.trim() : '';
  if (!containerPath) {
    return getResponse({ error: 'container_path is required' }, 400);
  }
  if (containerPath.length > MAX_PATH_LENGTH) {
    return getResponse({ error: `container_path exceeds maximum length of ${MAX_PATH_LENGTH}` }, 400);
  }
  if (!containerPath.includes(' > ')) {
    return getResponse({ error: 'Cannot rename base storages' }, 400);
  }

  const customName = typeof body.custom_name === 'string' ? body.custom_name.trim() : '';
  if (!customName) {
    return getResponse({ error: 'custom_name is required' }, 400);
  }
  if (customName.length > MAX_NAME_LENGTH) {
    return getResponse({ error: `custom_name exceeds maximum length of ${MAX_NAME_LENGTH}` }, 400);
  }

  const itemName = typeof body.item_name === 'string' ? body.item_name.trim() : '';
  if (itemName.length > MAX_ITEM_NAME_LENGTH) {
    return getResponse({ error: `item_name exceeds maximum length of ${MAX_ITEM_NAME_LENGTH}` }, 400);
  }

  const containerRef = body.container_ref != null ? parseInt(body.container_ref, 10) : null;

  try {
    const result = await upsertContainerName(user.id, containerPath, customName, containerRef, itemName);
    return getResponse(result, 200);
  } catch (err) {
    console.error('Error upserting container name:', err);
    return getResponse({ error: 'Failed to save container name' }, 500);
  }
}

/**
 * DELETE /api/users/inventory/containers — Remove a container name
 * Body: { container_path }
 */
export async function DELETE({ request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  const containerPath = typeof body.container_path === 'string' ? body.container_path.trim() : '';
  if (!containerPath) {
    return getResponse({ error: 'container_path is required' }, 400);
  }

  try {
    const deleted = await deleteContainerName(user.id, containerPath);
    return getResponse({ deleted }, deleted ? 200 : 404);
  } catch (err) {
    console.error('Error deleting container name:', err);
    return getResponse({ error: 'Failed to delete container name' }, 500);
  }
}

/**
 * PATCH /api/users/inventory/containers — Batch remap paths after import
 * Body: { remaps: [{ old_path, new_path, container_ref? }], remove_paths?: string[] }
 */
export async function PATCH({ request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  const remaps = Array.isArray(body.remaps) ? body.remaps : [];
  const removePaths = Array.isArray(body.remove_paths) ? body.remove_paths : [];

  if (remaps.length > MAX_REMAPS) {
    return getResponse({ error: `Maximum ${MAX_REMAPS} remaps per request` }, 400);
  }

  // Validate remaps
  const validated = [];
  for (let i = 0; i < remaps.length; i++) {
    const r = remaps[i];
    const oldPath = typeof r.old_path === 'string' ? r.old_path.trim() : '';
    const newPath = typeof r.new_path === 'string' ? r.new_path.trim() : '';
    if (!oldPath || !newPath) {
      return getResponse({ error: `remaps[${i}] requires old_path and new_path` }, 400);
    }
    if (oldPath.length > MAX_PATH_LENGTH || newPath.length > MAX_PATH_LENGTH) {
      return getResponse({ error: `remaps[${i}] path exceeds maximum length` }, 400);
    }
    const containerRef = r.container_ref != null ? parseInt(r.container_ref, 10) : null;
    validated.push({ oldPath, newPath, containerRef });
  }

  // Validate remove paths
  const validatedRemove = removePaths
    .map(p => typeof p === 'string' ? p.trim() : '')
    .filter(p => p.length > 0 && p.length <= MAX_PATH_LENGTH);

  try {
    await remapContainerNames(user.id, validated, validatedRemove);
    return getResponse({ remapped: validated.length, removed: validatedRemove.length }, 200);
  } catch (err) {
    console.error('Error remapping container names:', err);
    return getResponse({ error: 'Failed to remap container names' }, 500);
  }
}

//@ts-nocheck
import { updateShopManagers, getUserByEntropiaName, getShopManagers } from "$lib/server/db.js";
import { getResponse, apiCall } from "$lib/util.js";

// GET shop managers
export async function GET({ params, locals, fetch }) {
  let user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to view shop managers.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account.' }, 403);
  }

  if (!params.shop) {
    return getResponse({ error: 'Please provide the shop identifier.' }, 400);
  }

  // Get the current shop from dedicated API to check ownership
  const currentShop = await apiCall(fetch, `/shops/${encodeURIComponent(params.shop)}`);
  if (!currentShop) {
    return getResponse({ error: 'Shop not found.' }, 404);
  }

  // Check if user is owner
  const isOwner = currentShop.OwnerId != null && String(currentShop.OwnerId) === String(user.id);
  
  if (!isOwner && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only view managers for shops you own.' }, 403);
  }

  // Fetch managers and return only Name
  const dbManagers = await getShopManagers(currentShop.Id);
  const Managers = (dbManagers || []).map(m => ({ Name: m.user_name }));
  return getResponse({ Managers });
}

// UPDATE shop managers (PUT)
export async function PUT({ params, request, locals, fetch }) {
  let user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to update shop managers.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before making changes.' }, 403);
  }

  if (!params.shop) {
    return getResponse({ error: 'Please provide the shop identifier.' }, 400);
  }

  // Get the current shop from dedicated API to check ownership
  const currentShop = await apiCall(fetch, `/shops/${encodeURIComponent(params.shop)}`);
  if (!currentShop) {
    return getResponse({ error: 'Shop not found.' }, 404);
  }

  // Check if user is owner
  const isOwner = currentShop.OwnerId != null && String(currentShop.OwnerId) === String(user.id);
  
  if (!isOwner && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only manage managers for shops you own.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const { Managers } = body;

  // Validate managers data
  if (!Array.isArray(Managers)) {
    return getResponse({ error: 'Managers must be an array.' }, 400);
  }

  // Validate and convert to user IDs (DB expects snake_case)
  const validatedManagers = [];
  const invalidNames = [];
  const seenUserIds = new Set();

  for (const manager of Managers) {
    const name = manager?.Name ?? '';
    if (!name || typeof name !== 'string') {
      continue;
    }

    const entropiaName = name.trim();
    if (!entropiaName) {
      continue;
    }

    const dbUser = await getUserByEntropiaName(entropiaName);
    if (!dbUser) {
      invalidNames.push(entropiaName);
      continue;
    }

    if (!dbUser.verified) {
      invalidNames.push(`${entropiaName} (not verified)`);
      continue;
    }

    // Skip duplicates (case-insensitive by user ID)
    if (seenUserIds.has(dbUser.id)) {
      continue;
    }
    seenUserIds.add(dbUser.id);

    validatedManagers.push({ user_id: dbUser.id, eu_name: dbUser.eu_name });
  }

  if (invalidNames.length > 0) {
    return getResponse({ 
      error: `The following Entropia names could not be found or are not verified: ${invalidNames.join(', ')}` 
    }, 400);
  }

  const success = await updateShopManagers(currentShop.Id, validatedManagers);
  
  if (success) {
    return getResponse({ success: true, message: 'Managers updated successfully' });
  } else {
    return getResponse({ error: 'Failed to update managers' }, 500);
  }
}

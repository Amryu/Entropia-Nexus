//@ts-nocheck
import { updateShopOwner, getUserByEntropiaName } from "$lib/server/db.js";
import { getResponse, apiCall } from "$lib/util.js";

// UPDATE shop owner (PUT) - Admin only
export async function PUT({ params, request, locals, fetch }) {
  let user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to change shop owner.' }, 401);
  }

  // Only admins can change shop owners
  if (!user.administrator) {
    return getResponse({ error: 'Only administrators can change shop owners.' }, 403);
  }

  if (!params.shop) {
    return getResponse({ error: 'Please provide the shop identifier.' }, 400);
  }

  // Get the current shop from dedicated API
  const currentShop = await apiCall(fetch, `/shops/${encodeURIComponent(params.shop)}`);
  if (!currentShop) {
    return getResponse({ error: 'Shop not found.' }, 404);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const { OwnerName } = body;

  if (!OwnerName || typeof OwnerName !== 'string') {
    return getResponse({ error: 'Owner name is required.' }, 400);
  }

  const ownerName = OwnerName.trim();
  if (!ownerName) {
    return getResponse({ error: 'Owner name cannot be empty.' }, 400);
  }

  // Look up the user by Entropia name
  const newOwner = await getUserByEntropiaName(ownerName);
  if (!newOwner) {
    return getResponse({ error: `User "${ownerName}" not found.` }, 400);
  }

  if (!newOwner.verified) {
    return getResponse({ error: `User "${ownerName}" is not verified.` }, 400);
  }

  // Update shop owner (this also clears managers)
  const success = await updateShopOwner(currentShop.Id, newOwner.id);

  if (success) {
    return getResponse({
      success: true,
      message: 'Owner updated successfully. All managers have been cleared.',
      ownerId: newOwner.id,
      ownerName: newOwner.eu_name
    });
  } else {
    return getResponse({ error: 'Failed to update owner' }, 500);
  }
}

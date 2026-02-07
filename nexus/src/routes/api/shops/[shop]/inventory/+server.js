//@ts-nocheck
import { updateShopInventory, getShopInventory, getShopManagers } from "$lib/server/db.js";
import { getResponse, apiCall } from "$lib/util.js";

// GET shop inventory
export async function GET({ params, locals, fetch }) {
  let user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to view shop inventory.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account.' }, 403);
  }

  if (!params.shop) {
    return getResponse({ error: 'Please provide the shop identifier.' }, 400);
  }

  // Get the current shop from dedicated API to check permissions
  const currentShop = await apiCall(fetch, `/shops/${encodeURIComponent(params.shop)}`);
  if (!currentShop) {
    return getResponse({ error: 'Shop not found.' }, 404);
  }

  // Check if user is owner or manager
  const isOwner = currentShop.OwnerId === user.id;
  let isManager = false;
  
  if (!isOwner) {
    const managers = await getShopManagers(currentShop.Id);
    isManager = managers.some(manager => manager.user_id === user.id);
  }
  
  if (!isOwner && !isManager && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only view inventory for shops you own or manage.' }, 403);
  }

  // Fetch inventory (snake_case from DB) and convert to PascalCase
  const inventoryGroups = await getShopInventory(currentShop.Id);
  const InventoryGroups = (inventoryGroups || []).map(group => ({
    Name: group.name,
    Items: (group.Items || []).map(item => ({
      ItemId: item.item_id,
      StackSize: item.stack_size,
      Markup: item.markup,
      SortOrder: item.sort_order
    }))
  }));
  
  return getResponse({ InventoryGroups });
}

// UPDATE shop inventory (PUT)
export async function PUT({ params, request, locals, fetch }) {
  let user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to update shop inventory.' }, 401);
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

  // Check if user is owner or manager
  const isOwner = currentShop.OwnerId === user.id;
  let isManager = false;
  
  if (!isOwner) {
    const managers = await getShopManagers(currentShop.Id);
    isManager = managers.some(manager => manager.user_id === user.id);
  }
  
  if (!isOwner && !isManager && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only edit inventory for shops you own or manage.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const { InventoryGroups } = body;

  // Validate inventory groups data
  if (!Array.isArray(InventoryGroups)) {
    return getResponse({ error: 'InventoryGroups must be an array.' }, 400);
  }

  // Sanitize and convert PascalCase to snake_case for DB
  const sanitizedInventoryGroups = InventoryGroups.map(group => ({
    name: String(group.Name || '').trim().substring(0, 255),
    Items: Array.isArray(group.Items) ? group.Items.map(item => ({
      item_id: item.ItemId ? parseInt(item.ItemId) : null,
      stack_size: Math.max(1, parseInt(item.StackSize) || 1),
      markup: Math.max(0, parseFloat(item.Markup) || 100),
      sort_order: parseInt(item.SortOrder) || 0
    })).filter(item => item.item_id) : []
  })).filter(group => group.name);

  // Update the shop inventory
  const success = await updateShopInventory(currentShop.Id, sanitizedInventoryGroups);
  
  if (success) {
    return getResponse({ success: true, message: 'Inventory updated successfully' });
  } else {
    return getResponse({ error: 'Failed to update inventory' }, 500);
  }
}

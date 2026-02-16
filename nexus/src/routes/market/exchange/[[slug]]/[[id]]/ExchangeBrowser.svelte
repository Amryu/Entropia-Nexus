<script lang="ts">
  // @ts-nocheck
  import { onMount, onDestroy } from "svelte";

  import CategoryTree from "./CategoryTree.svelte";
  import FancyTable from "$lib/components/FancyTable.svelte";
  import OrderDialog from './OrderDialog.svelte';
  import MyOrdersView from './MyOrdersView.svelte';
  import OrderBookTable from './OrderBookTable.svelte';
  import InventoryImportDialog from './InventoryImportDialog.svelte';
  import OrderAdjustDialog from './OrderAdjustDialog.svelte';
  import InventoryPanel from './InventoryPanel.svelte';
  import CartSummary from './CartSummary.svelte';
  import FavouritesTree from './FavouritesTree.svelte';
  import QuickTradeDialog from './QuickTradeDialog.svelte';
  import { scoreSearchResult } from '$lib/search.js';
  import UserOrdersPanel from './UserOrdersPanel.svelte';
  import BulkTradeDialog from './BulkTradeDialog.svelte';
  import TradeRequestsPanel from './TradeRequestsPanel.svelte';
  import MassSellDialog from './MassSellDialog.svelte';
  import PriceHistoryChart from './PriceHistoryChart.svelte';
  import RangeSlider from '$lib/components/RangeSlider.svelte';

  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { apiCall, getItemLink, hasItemTag, encodeURIComponentSafe, decodeURIComponentSafe } from "$lib/util.js";
  import { isBlueprint, isItemTierable, isItemStackable, isLimited, itemHasCondition, isAbsoluteMarkup, getMaxTT, formatMarkupValue, formatMarkupForItem, formatPedValue, isPet, isBlueprintNonL, getUnitTT, computeUnitPrice, getPetLevel, itemTypeBadge } from '../../orderUtils';
  import { PET_ID_OFFSET, ARMOR_SET_OFFSET, GENDERED_TYPES } from '$lib/common/itemTypes.js';
  import { PLANETS } from '../../exchangeConstants.js';
  import { showMyOrders, showInventory, showTradeList, showTrades, tradeList, addToTradeList, clearTradeList, myOrders, inventory, upsertOrder } from '../../exchangeStore.js';
  import { favourites, isFavourite, toggleFavourite, createFolder } from '../../favouritesStore.js';
  import { hasCondition } from '$lib/shopUtils';
  import { addToast } from '$lib/stores/toasts.js';
  import { env } from '$env/dynamic/public';
  import TurnstileWidget from '$lib/components/TurnstileWidget.svelte';

  const VIEW_SLUGS = new Set(['listings', 'orders', 'inventory', 'trades']);

  let searchTerm = "";
  let selectedCategory = "All";
  let selectedCategoryRawPath = null; // raw key path array for URL construction
  let selectedPlanet = "All Planets";
  let selectedLimited = "all";
  let selectedSex = "both";
  let selectedOrderSide = "all"; // 'all' | 'buy' | 'sell'
  let filteredItems = [];
  let selectedItems = [];
  let savedOverviewFilters = null; // snapshot of filters before entering detail view
  let loading = false;
  let showOrderDialog = false;
  let showBulkTradeDialog = false;
  let orderDialogType = null; // 'buy' | 'sell'
  let orderDialogRef;
  let orderDialogExistingCount = 0; // existing orders for the current item+side
  // Title bar filters for tierable items
  let mobileSidebarOpen = false;
  let sidebarTab = 'categories'; // 'categories' | 'favourites'
  let selectedFavFolderId = null; // folder id, 'all', 'root', or null
  let favouriteFolderFilter = null; // Set<number> | null — when set, filters main listing
  // Range slider filter state
  let tierMin = 0;
  let tierMax = 10;
  let tirMin = 0;
  let tirMax = 200;
  let qrMin = 0;
  let qrMax = 100;
  let minConditionPct = 0;
  let showFilterDialog = false;
  let smallViewport = typeof window !== 'undefined' && window.innerWidth <= 600;

  function handleViewportResize() {
    smallViewport = typeof window !== 'undefined' && window.innerWidth <= 600;
  }

  // Tierable types list (used by detail view tables)
  const tierableTypes = new Set([
    "Weapon",
    "Armor",
    "ArmorSet",
    "Finder",
    "Excavator",
    "MedicalTool",
  ]);

  // Pending edit order (set when user clicks Edit in MyOrdersView)
  let pendingEditOrder = null;

  // Inline edit: item details loaded separately from detail view
  let inlineEditItem = null;

  // Quick trade dialog state
  let showQuickTrade = false;
  let quickTradeOrder = null;
  let quickTradeSide = 'buy'; // 'buy' | 'sell'
  let quickTradeItem = null; // Override item context for type detection
  let quickTradeRef;

  // User orders panel state
  let showUserOrders = false;
  let userOrdersTarget = null; // { id, name }
  let userOrdersReturnUrl = null; // URL to return to when closing the panel

  // Side filter for floating panel (All/Buy/Sell)
  let panelSideFilter = 'all'; // 'all' | 'BUY' | 'SELL'

  // Inventory & Orders panel
  let showImportDialog = false;
  let showAdjustDialog = false;
  let showMassSellDialog = false;
  let massSellItems = [];
  let massSellMode = false;
  let inventoryPanelRef;
  let myOrdersRef;
  let tradesPanelRef;
  let bumpingAll = false;
  let bumpCooldownEnd = 0;
  let bumpCooldownRemaining = 0;
  let bumpCooldownTimer = null;

  function startBumpCooldown(seconds) {
    bumpCooldownEnd = Date.now() + seconds * 1000;
    tickBumpCooldown();
  }

  function tickBumpCooldown() {
    clearInterval(bumpCooldownTimer);
    const remaining = Math.max(0, Math.ceil((bumpCooldownEnd - Date.now()) / 1000));
    bumpCooldownRemaining = remaining;
    if (remaining > 0) {
      bumpCooldownTimer = setInterval(() => {
        const r = Math.max(0, Math.ceil((bumpCooldownEnd - Date.now()) / 1000));
        bumpCooldownRemaining = r;
        if (r <= 0) clearInterval(bumpCooldownTimer);
      }, 1000);
    }
  }

  function formatCooldown(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  }

  onDestroy(() => {
    clearInterval(bumpCooldownTimer);
    if (typeof window !== 'undefined') window.removeEventListener('resize', handleViewportResize);
  });

  // Turnstile confirmation modal (for actions outside OrderDialog: bump-all, close)
  let pendingTurnstileAction = null; // { type: 'bump'|'close', order?, callback }
  let turnstileModalToken = null;
  let resetTurnstileModal = false;

  function requestTurnstile(type, callback, order = null) {
    turnstileModalToken = null;
    resetTurnstileModal = true;
    pendingTurnstileAction = { type, callback, order };
  }

  function cancelTurnstileModal() {
    pendingTurnstileAction = null;
    turnstileModalToken = null;
  }

  async function executeTurnstileAction() {
    if (!pendingTurnstileAction || !turnstileModalToken) return;
    const { callback } = pendingTurnstileAction;
    const token = turnstileModalToken;
    pendingTurnstileAction = null;
    turnstileModalToken = null;
    await callback(token);
  }

  // Reactive discrepancy count: compare sell orders against inventory
  $: discrepancyCount = computeDiscrepancyCount($myOrders, $inventory);
  // Current active sell order count for MassSellDialog pre-flight display
  $: currentSellCount = ($myOrders || []).filter(o => o.type === 'SELL' && o.state !== 'closed').length;

  function computeDiscrepancyCount(orders, inv) {
    const sellOrders = (orders || []).filter(o => o.type === 'SELL' && o.state_display !== 'closed' && o.state_display !== 'terminated');
    if (sellOrders.length === 0 || !inv || inv.length === 0) return 0;
    const invQtyMap = new Map();
    for (const item of inv) {
      if (item.item_id > 0) {
        invQtyMap.set(item.item_id, (invQtyMap.get(item.item_id) || 0) + item.quantity);
      }
    }
    let count = 0;
    for (const order of sellOrders) {
      const invQty = invQtyMap.get(order.item_id) || 0;
      if (order.quantity > invQty) count++;
    }
    return count;
  }

  /** Fetch full item details, using type-specific endpoints for Pet/ArmorSet items */
  async function fetchItemDetails(itemId, itemType) {
    if (itemType === 'Pet') {
      const pet = await apiCall(window.fetch, `/pets/${itemId - PET_ID_OFFSET}`);
      if (pet) {
        pet.Id = pet.ItemId ?? itemId;
        pet.Properties = pet.Properties || {};
        pet.Properties.Type = 'Pet';
      }
      return pet;
    }
    if (itemType === 'ArmorSet') {
      const set = await apiCall(window.fetch, `/armorsets/${itemId - ARMOR_SET_OFFSET}`);
      if (set) {
        set.Id = set.ItemId ?? itemId;
        set.Properties = set.Properties || {};
        set.Properties.Type = 'ArmorSet';
      }
      return set;
    }
    return apiCall(window.fetch, `/items/${itemId}`);
  }

  function closeFloatingPanel() {
    showMyOrders.set(false);
    showInventory.set(false);
    showTrades.set(false);
    if (showUserOrders) clearTradeList();
    showUserOrders = false;
    goto('/market/exchange/listings');
  }

  /** Navigate from detail view back to overview, explicitly resetting detail state */
  function handleBackToOverview() {
    // Abort any in-flight detail requests
    if (detailsAbort?.abort) detailsAbort.abort();
    detailsAbort = null;
    lastDetailsItemId = null;
    // Clear detail-specific data
    selectedItemDetails = null;
    buyOrders = [];
    sellOrders = [];
    ordersLoadedKey = '';
    showPriceHistory = false;
    showFilterDialog = false;
    // Navigate — this triggers the route-sync reactive block
    // which will restore savedOverviewFilters
    goto('/market/exchange/listings');
  }

  /** Close floating panel tabs without navigating — used by sidebar handlers */
  function closeFloatingPanelIfOpen() {
    if (!floatingPanelOpen) return;
    showMyOrders.set(false);
    showInventory.set(false);
    showTrades.set(false);
    showTradeList.set(false);
    if (showUserOrders) { clearTradeList(); showUserOrders = false; }
  }

  async function editOrderInline(order) {
    if (!order?.item_id) return;
    try {
      const slimItem = (allItems || []).find(si => si?.i === order.item_id);
      const itemType = slimItem?.t || null;
      const item = await fetchItemDetails(order.item_id, itemType);
      if (!item) return;

      inlineEditItem = item;
      const type = order.type === 'BUY' ? 'buy' : 'sell';
      orderDialogType = type;

      const editOrder = {
        Type: order.type === 'BUY' ? 'Buy' : 'Sell',
        Item: {
          Name: item?.Name || order.details?.item_name || '',
          Type: item?.Properties?.Type || item?.Type || null,
          MaxTT: getMaxTT(item),
          st: slimItem?.st ?? null,
        },
        Planet: order.planet || 'Calypso',
        Quantity: order.quantity || 1,
        MinQuantity: order.min_quantity ?? null,
        CurrentTT: order.details?.CurrentTT ?? null,
        Markup: Number(order.markup) || 0,
        Metadata: { ...(order.details || {}) },
        _orderId: order.id,
        _inlineEdit: true,
      };
      delete editOrder.Metadata.item_name;
      delete editOrder.Metadata.CurrentTT;

      setTimeout(() => {
        orderDialogRef?.initOrder(editOrder, type, 'edit');
        showOrderDialog = true;
      }, 0);
    } catch (e) {
      console.error('Failed to load item for inline edit:', e);
    }
  }

  async function openUserOrdersByName(name) {
    // Skip if already showing this user's orders
    if (showUserOrders && userOrdersTarget?.name === name) return;
    try {
      const res = await fetch(`/api/users/profiles/${encodeURIComponentSafe(name)}`);
      if (res.ok) {
        const data = await res.json();
        const userId = data?.profile?.id;
        if (userId) {
          openUserOrdersPanel(userId, name);
          return;
        }
      }
    } catch {}
    // Fallback: just open My Orders if lookup fails
    switchFloatingTab('orders');
  }

  function openUserOrdersPanel(userId, name) {
    const currentPath = $page.url.pathname;
    const currentSearch = $page.url.search || '';
    const currentUrl = `${currentPath}${currentSearch}`;
    const isCurrentExchange = currentPath.startsWith('/market/exchange');
    const isCurrentOrdersRoute = currentPath.startsWith('/market/exchange/orders/');
    let fallbackReturnUrl = '/market/exchange';

    // When arriving directly on /orders/<name>, use exchange referrer if present;
    // otherwise fall back to base exchange to avoid login/callback history loops.
    if (!isCurrentOrdersRoute && isCurrentExchange) {
      fallbackReturnUrl = currentUrl;
    } else if (typeof document !== 'undefined' && document.referrer) {
      try {
        const ref = new URL(document.referrer);
        if (ref.origin === window.location.origin && ref.pathname.startsWith('/market/exchange')) {
          fallbackReturnUrl = `${ref.pathname}${ref.search || ''}`;
        }
      } catch {
        fallbackReturnUrl = '/market/exchange';
      }
    }

    userOrdersTarget = { id: userId, name };
    userOrdersReturnUrl = fallbackReturnUrl;
    showUserOrders = true;
    showMyOrders.set(false);
    showInventory.set(false);
    showTrades.set(false);
    showTradeList.set(false);
    clearTradeList();
    panelSideFilter = 'all';
    // Update URL to reflect the user's orders page
    const ordersUrl = `/market/exchange/orders/${encodeURIComponentSafe(name)}`;
    if ($page.url.pathname !== ordersUrl) {
      goto(ordersUrl, { replaceState: false });
    }
  }

  function closeUserOrdersPanel() {
    showUserOrders = false;
    clearTradeList();
    const currentUrl = `${$page.url.pathname}${$page.url.search || ''}`;
    if (userOrdersReturnUrl && userOrdersReturnUrl !== currentUrl) goto(userOrdersReturnUrl);
    else goto('/market/exchange');
  }

  function handleOrderAction(e) {
    if (!canPostOrders) {
      openAuthDialog();
      return;
    }
    const item = e.detail;
    // Resolve the slim item for the order's item_id so type detection works
    const rawOrder = item.order || item;
    const slimItem = (allItems || []).find(si => si?.i === (rawOrder.item_id ?? item.itemId));
    if ($tradeList.length === 0) {
      // No trade list started — open QuickTradeDialog for a single trade request
      const side = item.side === 'SELL' ? 'buy' : 'sell';
      openQuickTrade(rawOrder, side, slimItem || null);
    } else {
      // Trade list already started — add to it
      addToTradeList(item);
    }
  }

  function handleAddToListFromDialog(e) {
    const { order, quantity, side } = e.detail;
    if (!order) return;
    addToTradeList({
      orderId: order.id,
      itemId: order.item_id,
      itemName: order.details?.item_name || 'Unknown',
      sellerId: userOrdersTarget?.id || order.user_id,
      sellerName: order.seller_name || userOrdersTarget?.name || 'Unknown',
      planet: order.planet || '',
      quantity: quantity || order.quantity || 1,
      unitPrice: Number(order.markup) || 0,
      markup: Number(order.markup) || 0,
      side: order.type || 'SELL',
    });
    closeQuickTrade();
  }

  function switchFloatingTab(tab) {
    if (showUserOrders) clearTradeList();
    showMyOrders.set(tab === 'orders');
    showInventory.set(tab === 'inventory');
    showTrades.set(tab === 'trades');
    showTradeList.set(false);
    showUserOrders = false;
    panelSideFilter = 'all';
  }

  function refreshFloatingPanel() {
    if ($showMyOrders && myOrdersRef) myOrdersRef.refresh();
    else if ($showInventory && inventoryPanelRef) inventoryPanelRef.refresh();
    else if ($showTrades && tradesPanelRef) tradesPanelRef.refresh();
  }

  async function handleInventorySell(e) {
    const { invItem, existingOrder } = e.detail;
    if (!invItem?.item_id) return;

    try {
      // Fetch full item details for the OrderDialog (pet-aware)
      const slimItem = (allItems || []).find(si => si?.i === invItem.item_id);
      const itemType = slimItem?.t || null;

      // Block untradeable clothing (null gender)
      if (itemType === 'Clothing' && slimItem?.g === null) {
        addToast('This item cannot be traded (no gender classification).', { type: 'warning' });
        return;
      }
      const item = await fetchItemDetails(invItem.item_id, itemType);
      if (!item) return;

      // Get MaxTT from fetched details (pet endpoint includes NutrioCapacity)
      const maxTT = getMaxTT(item) ?? (slimItem?.v != null ? Number(slimItem.v) : null);

      // Current TT from inventory value field
      const invCurrentTT = invItem.value != null ? Number(invItem.value) : null;

      inlineEditItem = item;
      orderDialogType = 'sell';

      // Count existing sell orders for this item
      orderDialogExistingCount = ($myOrders || []).filter(
        o => o.item_id === invItem.item_id && o.type === 'SELL' && o.state !== 'closed'
      ).length;

      if (existingOrder) {
        // Edit existing order
        const editOrder = {
          Type: 'Sell',
          Item: {
            Name: item?.Name || existingOrder.details?.item_name || '',
            Type: itemType,
            MaxTT: maxTT,
            st: slimItem?.st ?? null,
          },
          Planet: existingOrder.planet || invItem.container || 'Calypso',
          Quantity: existingOrder.quantity || 1,
          MinQuantity: existingOrder.min_quantity ?? null,
          CurrentTT: existingOrder.details?.CurrentTT ?? invCurrentTT,
          Markup: existingOrder.markup || 0,
          Metadata: { ...(existingOrder.details || {}) },
          _orderId: existingOrder.id,
          _inlineEdit: true,
          _inventoryWarning: `You already have a sell order for this item. Editing it now.`,
        };
        delete editOrder.Metadata.item_name;
        delete editOrder.Metadata.CurrentTT;

        setTimeout(() => {
          orderDialogRef?.initOrder(editOrder, 'sell', 'edit');
          showOrderDialog = true;
        }, 0);
      } else {
        // Create new sell order pre-filled from inventory
        const details = typeof invItem.details === 'string' ? JSON.parse(invItem.details) : (invItem.details || {});
        const newOrder = {
          Type: 'Sell',
          Item: {
            Name: item?.Name || invItem.item_name || '',
            Type: itemType,
            MaxTT: maxTT,
            Id: invItem.item_id,
            st: slimItem?.st ?? null,
          },
          Planet: invItem.container || 'Calypso',
          Quantity: invItem.quantity || 1,
          CurrentTT: invCurrentTT,
          Markup: 0,
          Metadata: {},
          _inventoryQty: invItem.quantity || 0,
        };

        // Pre-fill metadata from inventory details
        if (details.Tier != null) newOrder.Metadata.Tier = details.Tier;
        if (details.TierIncreaseRate != null) newOrder.Metadata.TierIncreaseRate = details.TierIncreaseRate;
        if (details.QualityRating != null) newOrder.Metadata.QualityRating = details.QualityRating;

        setTimeout(() => {
          orderDialogRef?.initOrder(newOrder, 'sell', 'create');
          showOrderDialog = true;
        }, 0);
      }
    } catch (e) {
      console.error('Failed to open sell dialog from inventory:', e);
    }
  }

  function toggleMassSellMode() {
    massSellMode = !massSellMode;
    if (inventoryPanelRef) {
      if (massSellMode) {
        inventoryPanelRef.setMassSellMode(true);
      } else {
        inventoryPanelRef.clearMassSell();
      }
    }
  }

  function handleMassSell(e) {
    massSellItems = e.detail.items;
    showMassSellDialog = true;
  }

  async function handleMassSellComplete() {
    showMassSellDialog = false;
    massSellMode = false;
    // Clear mass sell list in inventory panel
    if (inventoryPanelRef) inventoryPanelRef.clearMassSell();
    await refreshAfterOrderChange();
    // Also refresh inventory panel
    if (inventoryPanelRef) inventoryPanelRef.refresh();
  }

  // Exchange price data for detail view
  let exchangePrices = null;

  // Price history state
  const PRICE_PERIODS = [
    { value: '24h', label: '24h' },
    { value: '7d', label: '7d' },
    { value: '30d', label: '30d' },
    { value: '3m', label: '3m' },
    { value: '6m', label: '6m' },
    { value: '1y', label: '1y' },
    { value: '5y', label: '5y' },
    { value: 'all', label: 'All' },
  ];
  let selectedPeriod = '7d';
  let showPriceHistory = false;
  let priceHistoryData = [];
  let priceHistoryLoading = false;
  let periodStats = null;

  // Detail view state
  let tableMode = "both"; // 'both' | 'buy' | 'sell'
  let lastUpdateFilter = "all"; // 'fresh' | 'recent' | 'all'
  let buyOrders = [];
  let sellOrders = [];
  let selectedItemDetails = null;

  // Persisted filter settings
  const LS_KEY = "exchangeFilters.v1";
  const LS_ORDER_KEY = "exchangeOrderPrefs.v1";
  async function ensureCategorizedLoaded() {
    try {
      initialLoading = true;
      // If already loaded, skip
      if (categorizedItems && Object.keys(categorizedItems).length > 0) return;
      const res = await fetch("/api/market/exchange", {
        headers: { "cache-control": "max-age=60" },
      });
      if (res.ok) {
        const json = await res.json();
        categorizedItems = json || {};
      }
    } finally {
      initialLoading = false;
    }
  }
  // State for category tree and route-driven selection
  let categorizedItems = {};
  let initialLoading = false;

  // Format a raw category key to display name (same logic as CategoryTree)
  function formatCategoryName(key) {
    if (key === 'all') return 'All';
    return key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ');
  }


  // Recursively find a category by display name in the raw categorization object
  function findCategoryByName(obj, targetName, path = []) {
    for (const [key, value] of Object.entries(obj)) {
      const displayName = formatCategoryName(key);
      const currentPath = [...path, key];
      if (displayName === targetName) {
        return { path: currentPath, value };
      }
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        const found = findCategoryByName(value, targetName, currentPath);
        if (found) return found;
      }
    }
    return null;
  }

  // Gather items at a raw key path in the categorization object
  function gatherItemsAtPath(obj, rawKeys) {
    if (!obj || !rawKeys || rawKeys.length === 0) return [];
    let node = obj;
    for (const key of rawKeys) {
      if (!node) return [];
      if (Array.isArray(node)) return node;
      if (!(key in node)) return [];
      node = node[key];
    }
    if (Array.isArray(node)) return node;
    return flattenItems(node);
  }

  // Current route params — [[slug]] is view type, [[id]] is content
  $: viewSlug = VIEW_SLUGS.has($page?.params?.slug) ? $page.params.slug : 'listings';
  $: routeId = $page?.params?.id ?? ($page?.params?.slug && !VIEW_SLUGS.has($page.params.slug) ? $page.params.slug : '');

  // Build a root "All" node with every item flattened
  $: allItems = flattenItems(categorizedItems);
  $: categoriesWithAll = { all: allItems, ...categorizedItems };

  // For listings: resolve routeId as category (dot-separated raw key path or legacy leaf name)
  $: resolvedCategory = (() => {
    if (viewSlug !== 'listings' || !routeId) return null;
    try {
      const decoded = decodeURIComponentSafe(routeId);
      if (decoded === 'All' || decoded === 'all') return null;

      // Dot-separated path: walk the tree by raw keys (e.g. "enhancers.armor")
      if (decoded.includes('.')) {
        const keys = decoded.split('.');
        let node = categorizedItems;
        for (const key of keys) {
          if (!node || typeof node !== 'object' || Array.isArray(node)) return null;
          if (!(key in node)) return null;
          node = node[key];
        }
        return { path: keys, value: node };
      }

      // Legacy: single name lookup (leaf name)
      return findCategoryByName(categorizedItems, decoded);
    } catch { return null; }
  })();

  // Detail view = listings + routeId present + NOT a category match
  $: isDetailView = viewSlug === 'listings' && !!routeId && !resolvedCategory;

  // Save overview filters when entering detail view
  let wasDetailView = false;
  $: {
    if (isDetailView && !wasDetailView) {
      savedOverviewFilters = {
        category: selectedCategory,
        categoryRawPath: selectedCategoryRawPath,
        items: selectedItems,
        searchTerm,
        planet: selectedPlanet,
        limited: selectedLimited,
        sex: selectedSex,
        sidebarTab,
        favFolderId: selectedFavFolderId,
        favFolderFilter: favouriteFolderFilter,
        tierMin, tierMax,
        tirMin, tirMax,
        qrMin, qrMax,
      };
    }
    wasDetailView = isDetailView;
  }

  // Resolve the selected item for detail view
  $: selectedItem = (() => {
    if (!isDetailView) return null;
    const key = routeId;
    const all = allItems || [];
    if (!Array.isArray(all) || all.length === 0) return null;
    if (/^\d+$/.test(String(key))) {
      const idNum = Number(key);
      return all.find((it) => it?.i === idNum) || null;
    }
    try {
      const name = decodeURIComponentSafe(key);
      const found = all.find((it) => it?.n === name) || null;
      if (found) return found;
      const name2 = decodeURIComponent(key);
      return all.find((it) => it?.n === name2) || null;
    } catch {
      return all.find((it) => it?.n === key) || null;
    }
  })();

  // Gender from slim cache: undefined = non-gendered, null = untradeable clothing, 'Both'/'Male'/'Female'/'Neutral'
  $: selectedItemGender = selectedItem?.g;
  $: isGenderedDetail = GENDERED_TYPES.has(selectedItem?.t) && selectedItemGender !== 'Neutral' && selectedItemGender !== null;

  // Gender filter for price history (gendered items only)
  let priceGender = 'Both';

  // Sync category selection from route
  $: {
    if (viewSlug === 'listings') {
      if (!routeId || !resolvedCategory) {
        if (!routeId) {
          if (savedOverviewFilters) {
            // Restore saved filters from before detail view
            selectedCategory = savedOverviewFilters.category;
            selectedCategoryRawPath = savedOverviewFilters.categoryRawPath;
            selectedItems = savedOverviewFilters.items;
            searchTerm = savedOverviewFilters.searchTerm;
            selectedPlanet = savedOverviewFilters.planet;
            selectedLimited = savedOverviewFilters.limited;
            selectedSex = savedOverviewFilters.sex;
            sidebarTab = savedOverviewFilters.sidebarTab;
            selectedFavFolderId = savedOverviewFilters.favFolderId;
            favouriteFolderFilter = savedOverviewFilters.favFolderFilter;
            tierMin = savedOverviewFilters.tierMin;
            tierMax = savedOverviewFilters.tierMax;
            tirMin = savedOverviewFilters.tirMin;
            tirMax = savedOverviewFilters.tirMax;
            qrMin = savedOverviewFilters.qrMin;
            qrMax = savedOverviewFilters.qrMax;
            savedOverviewFilters = null;
          } else {
            selectedCategory = 'All';
            selectedCategoryRawPath = null;
            selectedItems = allItems;
          }
        }
      } else {
        // Matched a category by path (legacy URL)
        const displayPath = resolvedCategory.path.map(formatCategoryName).join(' > ');
        selectedCategory = displayPath;
        selectedCategoryRawPath = resolvedCategory.path;
        selectedItems = gatherItemsAtPath(categorizedItems, resolvedCategory.path);
      }
    }
  }

  // View change handling — open/close panels based on slug
  let currentViewSlug = null;
  $: if (viewSlug !== currentViewSlug) {
    currentViewSlug = viewSlug;
    if (viewSlug === 'listings') {
      showMyOrders.set(false);
      showInventory.set(false);
      showTrades.set(false);
      if (showUserOrders) clearTradeList();
      showUserOrders = false;
    } else if (viewSlug === 'orders') {
      const id = routeId;
      const decodedName = id ? decodeURIComponentSafe(id) : null;
      const currentUserName = $page?.data?.session?.user?.eu_name;
      if (decodedName && decodedName !== currentUserName) {
        openUserOrdersByName(decodedName);
      } else {
        switchFloatingTab('orders');
      }
    } else if (viewSlug === 'inventory') {
      switchFloatingTab('inventory');
    } else if (viewSlug === 'trades') {
      switchFloatingTab('trades');
    }
  }

  // Prefetch full item details for link building and MU rules (only when ID changes)
  let lastDetailsItemId = null;
  let detailsAbort = null;
  $: {
    const id = selectedItem?.i ?? null;
    if (!id) {
      // Clear when no item is selected
      if (detailsAbort?.abort) detailsAbort.abort();
      detailsAbort = null;
      lastDetailsItemId = null;
      if (selectedItemDetails !== null) {
        selectedItemDetails = null;
        console.log('[ExchangeBrowser] selectedItemDetails cleared (no selected item)');
      }
    } else if (id !== lastDetailsItemId) {
      try {
        // Cancel any in-flight request
        if (detailsAbort?.abort) detailsAbort.abort();
      } catch {}
      // Fire new request for this ID only
      lastDetailsItemId = id; // optimistic set to avoid duplicate dispatches
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
      detailsAbort = controller;
      (async () => {
        try {
          const it = await fetchItemDetails(id, selectedItem?.t);
          // Ignore if another fetch superseded this
          if (controller && controller.signal.aborted) return;
          selectedItemDetails = it || null;
          console.log('[ExchangeBrowser] selectedItemDetails loaded:', selectedItemDetails);
        } catch (e) {
          if (controller && controller.signal?.aborted) return;
          selectedItemDetails = null;
          console.log('[ExchangeBrowser] selectedItemDetails error:', e);
        } finally {
          if (detailsAbort === controller) detailsAbort = null;
        }
      })();
    }
  }

  // If a pending edit order exists and item details have loaded, open the edit dialog
  $: if (pendingEditOrder && selectedItemDetails) {
    const order = pendingEditOrder;
    pendingEditOrder = null;
    const type = order.type === 'BUY' ? 'buy' : 'sell';
    orderDialogType = type;
    setTimeout(() => {
      // Build an order object for editing
      const editOrder = {
        Type: order.type === 'BUY' ? 'Buy' : 'Sell',
        Item: {
          Name: selectedItemDetails?.Name || order.details?.item_name || '',
          Type: selectedItemDetails?.Properties?.Type || selectedItemDetails?.Type || null,
          MaxTT: getMaxTT(selectedItemDetails) ?? selectedItem?.v ?? null,
        },
        Planet: order.planet || 'Calypso',
        Quantity: order.quantity || 1,
        MinQuantity: order.min_quantity ?? null,
        CurrentTT: order.details?.CurrentTT ?? null,
        Markup: Number(order.markup) || 0,
        Metadata: { ...(order.details || {}) },
        _orderId: order.id,  // track original order ID for PUT
      };
      // Clean up non-metadata fields from Metadata
      delete editOrder.Metadata.item_name;
      delete editOrder.Metadata.CurrentTT;
      orderDialogRef?.initOrder(editOrder, type, 'edit');
      showOrderDialog = true;
    }, 0);
  }

  // Filter items based on search, L/UL, and Sex
  $: {
    const needle = searchTerm.toLowerCase();
    const base = Array.isArray(selectedItems) ? selectedItems : allItems;

    const appliesLUL = new Set([
      "Weapon",
      "Armor",
      "WeaponAmplifier",
      "WeaponVisionAttachment",
      "Absorber",
      "ArmorPlating",
      "FinderAmplifier",
      "MedicalTool",
      "Scanner",
      "Finder",
      "Excavator",
      "Refiner",
      "TeleportationChip",
      "MiscTool",
      "Clothing",
      "Blueprint",
      "Vehicle",
    ]);

    filteredItems = base.filter((item) => {
      const name = item?.n ?? "";

      // Favourites folder filter
      if (favouriteFolderFilter && !favouriteFolderFilter.has(item?.i)) return false;

      // Search filter with scoring
      if (needle) {
        const score = scoreSearchResult(name, searchTerm);
        if (score <= 0) return false;
        item._searchScore = score;
      } else {
        item._searchScore = 0;
      }

      if (selectedLimited !== "all") {
        const isL = hasItemTag(name, "L");
        if (selectedLimited === "L" && !isL) return false;
        if (selectedLimited === "UL" && isL) return false;
      }

      // Gender filter: only applies to Armor/Clothing
      const genderRelevant = item.t === 'Armor' || item.t === 'Clothing';
      if (genderRelevant && selectedSex === "male" && hasItemTag(name, "F")) return false;
      if (genderRelevant && selectedSex === "female" && hasItemTag(name, "M")) return false;

      // Planet filter: only show items with orders on the selected planet
      if (selectedPlanet !== "All Planets") {
        if (!item.pl || !item.pl.includes(selectedPlanet)) return false;
      }

      // Order side filter: only show items with orders of the selected type
      if (selectedOrderSide === 'buy' && (!item.b || item.b === 0)) return false;
      if (selectedOrderSide === 'sell' && (!item.s || item.s === 0)) return false;

      return true;
    });
  }

  // Map filtered items to FancyTable data
  $: listTableData = (() => {
    const rows = (filteredItems || []).map((item) => ({
      _item: item,
      name: item.n,
      median: item.m ?? null,
      percentile10: item.p ?? null,
      wap: item.w ?? null,
      orders: (item.s || 0) + (item.b || 0),
      volume: (item.sv || 0) + (item.bv || 0),
      lastUpdate: item.u ?? null,
      _orderPriority: (item.b > 0 || item.s > 0) ? 1 : 0,
    }));
    // When searching, sort by match score first; otherwise by order priority + recency
    const isSearching = !!searchTerm;
    rows.sort((a, b) => {
      if (isSearching) {
        const sa = a._item._searchScore || 0;
        const sb = b._item._searchScore || 0;
        if (sa !== sb) return sb - sa;
      }
      if (a._orderPriority !== b._orderPriority) return b._orderPriority - a._orderPriority;
      if (a._orderPriority > 0 && a.lastUpdate && b.lastUpdate) {
        return new Date(b.lastUpdate).getTime() - new Date(a.lastUpdate).getTime();
      }
      return 0;
    });
    return rows;
  })();

  $: listDefaultSort = { column: smallViewport ? 'orders' : 'lastUpdate', order: 'DESC' };

  // Columns for the main list view FancyTable
  const listColumns = [
    { key: 'name', header: 'Item', main: true, mobileWidth: '1fr', sortable: true, searchable: true, formatter: (val, row) => val + itemTypeBadge(row._item?.t) },
    { key: 'median', header: 'Median', width: '100px', mobileWidth: '60px', sortable: true, searchable: false, formatter: (v, row) => v != null ? formatMarkupForItem(v, row?._item) : '<span style="opacity:0.35">N/A</span>' },
    { key: 'percentile10', header: '10%', width: '100px', sortable: true, searchable: false, hideOnMobile: true, formatter: (v, row) => v != null ? formatMarkupForItem(v, row?._item) : '<span style="opacity:0.35">N/A</span>' },
    { key: 'wap', header: 'Weight. Avg', width: '100px', sortable: true, searchable: false, hideOnMobile: true, formatter: (v, row) => v != null ? formatMarkupForItem(v, row?._item) : '<span style="opacity:0.35">N/A</span>' },
    { key: 'orders', header: 'Orders', width: '90px', mobileWidth: '50px', sortable: true, searchable: false,
      cellClass: () => 'cell-center',
      sortPhases: [
        { sortValue: (row) => row._item?.s || 0, order: 'DESC', color: 'var(--error-color)' },
        { sortValue: (row) => row._item?.s || 0, order: 'ASC', color: 'var(--error-color)' },
        { sortValue: (row) => row._item?.b || 0, order: 'DESC', color: 'var(--success-color)' },
        { sortValue: (row) => row._item?.b || 0, order: 'ASC', color: 'var(--success-color)' },
      ],
      formatter: (v, row) => {
        const s = row._item?.s || 0;
        const b = row._item?.b || 0;
        return `<span class="split-cell"><span class="split-l" style="color:var(--error-color)${s === 0 ? ';opacity:0.3' : ''}">${s}</span><span class="split-sep">/</span><span class="split-r" style="color:var(--success-color)${b === 0 ? ';opacity:0.3' : ''}">${b}</span></span>`;
      }
    },
    { key: 'volume', header: 'Volume', width: '120px', sortable: true, searchable: false, hideOnMobile: true,
      cellClass: () => 'cell-center',
      sortPhases: [
        { sortValue: (row) => row._item?.sv || 0, order: 'DESC', color: 'var(--error-color)' },
        { sortValue: (row) => row._item?.sv || 0, order: 'ASC', color: 'var(--error-color)' },
        { sortValue: (row) => row._item?.bv || 0, order: 'DESC', color: 'var(--success-color)' },
        { sortValue: (row) => row._item?.bv || 0, order: 'ASC', color: 'var(--success-color)' },
      ],
      formatter: (v, row) => {
        const sv = row._item?.sv || 0;
        const bv = row._item?.bv || 0;
        return `<span class="split-cell"><span class="split-l" style="color:var(--error-color)${sv === 0 ? ';opacity:0.3' : ''}">${sv}</span><span class="split-sep">/</span><span class="split-r" style="color:var(--success-color)${bv === 0 ? ';opacity:0.3' : ''}">${bv}</span></span>`;
      }
    },
    { key: 'lastUpdate', header: 'Updated', width: '100px', sortable: true, searchable: false, hideOnMobile: true,
      sortValue: (row) => row.lastUpdate ? new Date(row.lastUpdate).getTime() : 0,
      formatter: (v) => {
        if (!v) return '<span style="opacity:0.35">-</span>';
        const diff = Date.now() - new Date(v).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 2) return 'Just now';
        if (mins < 60) return `${mins}m ago`;
        const hours = Math.floor(mins / 60);
        if (hours < 24) return `${hours}h ago`;
        const days = Math.floor(hours / 24);
        if (days < 30) return `${days}d ago`;
        return new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      }
    },
  ];

  function flattenItems(obj) {
    const items = [];

    function traverse(current) {
      if (Array.isArray(current)) {
        items.push(...current);
      } else if (typeof current === "object" && current !== null) {
        Object.values(current).forEach(traverse);
      }
    }

    traverse(obj);
    return items;
  }

  function handleCategorySelect(categoryPath, items, rawPath) {
    const wasFloatingPanelOpen = floatingPanelOpen;
    closeFloatingPanelIfOpen();
    favouriteFolderFilter = null;
    selectedFavFolderId = null;
    selectedCategory = categoryPath;
    selectedCategoryRawPath = rawPath || null;
    selectedItems = Array.isArray(items) ? items : [];
    if (isDetailView || wasFloatingPanelOpen) {
      // Save the selected category so the route-sync reactive block restores it
      // instead of resetting to "All" when the URL changes
      savedOverviewFilters = {
        category: categoryPath,
        categoryRawPath: rawPath || null,
        items: Array.isArray(items) ? items : [],
        searchTerm: '',
        planet: selectedPlanet,
        limited: selectedLimited,
        sex: selectedSex,
        sidebarTab,
        favFolderId: null,
        favFolderFilter: null,
        tierMin, tierMax,
        tirMin, tirMax,
        qrMin, qrMax,
      };
      goto('/market/exchange/listings');
    } else {
      savedOverviewFilters = null;
    }
  }

  function handleFavouriteFolderSelect(folderId, itemIds) {
    const wasFloatingPanelOpen = floatingPanelOpen;
    closeFloatingPanelIfOpen();
    selectedFavFolderId = folderId;
    favouriteFolderFilter = new Set(itemIds);
    if (viewSlug !== 'listings' || isDetailView || wasFloatingPanelOpen) {
      // Save state so route-sync restores it instead of resetting to "All"
      savedOverviewFilters = {
        category: selectedCategory,
        categoryRawPath: selectedCategoryRawPath,
        items: selectedItems,
        searchTerm: '',
        planet: selectedPlanet,
        limited: selectedLimited,
        sex: selectedSex,
        sidebarTab: 'favourites',
        favFolderId: folderId,
        favFolderFilter: new Set(itemIds),
        tierMin, tierMax,
        tirMin, tirMax,
        qrMin, qrMax,
      };
      goto('/market/exchange/listings');
    } else {
      savedOverviewFilters = null;
    }
    mobileSidebarOpen = false;
  }

  function formatPrice(value) {
    return formatPedValue(value);
  }

  let detailMarkupItem = null;
  let detailIsAbsoluteMarkup = true;
  $: detailMarkupItem = selectedItemDetails || selectedItem;
  $: detailIsAbsoluteMarkup = isAbsoluteMarkup(detailMarkupItem);

  function formatMarkupDisplay(value, absoluteMarkup) {
    return formatMarkupValue(value, absoluteMarkup);
  }

  // Only apply L/UL filter for specific category paths
  function pathAppliesLUL(pathStr) {
    if (!pathStr || typeof pathStr !== "string") return false;
    const head = pathStr.split(" > ")[0]?.toLowerCase?.() || "";
    if (head === "weapons" || head === "armor") return true;
    if (
      head === "tools" ||
      head === "clothes" ||
      head === "blueprints" ||
      head === "vehicles"
    )
      return true;
    return false;
  }

  $: appliesLULForCurrent =
    selectedCategory &&
    selectedCategory !== "All" &&
    pathAppliesLUL(selectedCategory);

  let orderPlanet = "Calypso"; // persisted planet pref for order dialog

  // Derive available planets from items that have orders
  $: availablePlanets = (() => {
    const planets = new Set();
    for (const item of allItems || []) {
      if (item.pl) for (const p of item.pl) planets.add(p);
    }
    return PLANETS.filter(p => planets.has(p));
  })();

  // Helpers
  function classifyFreshness(date) {
    if (!date) return "stale";
    const ts =
      typeof date === "string" || typeof date === "number"
        ? new Date(date)
        : date;
    const diffMs = Date.now() - ts.getTime();
    const dayMs = 24 * 60 * 60 * 1000;
    if (diffMs < dayMs) return "fresh";
    if (diffMs < 7 * dayMs) return "recent";
    return "stale";
  }

  function timeSince(date) {
    if (!date) return "N/A";
    const ts =
      typeof date === "string" || typeof date === "number"
        ? new Date(date)
        : date;
    const diff = Math.max(0, Date.now() - ts.getTime());
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m (${classifyFreshness(ts)})`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h (${classifyFreshness(ts)})`;
    const days = Math.floor(hrs / 24);
    return `${days}d (${classifyFreshness(ts)})`;
  }

  function formatLastUpdateDHm(date) {
    if (!date) return "N/A";
    const ts =
      typeof date === "string" || typeof date === "number"
        ? new Date(date)
        : date;
    const diffMs = Math.max(0, Date.now() - ts.getTime());
    const totalM = Math.floor(diffMs / 60000);
    const d = Math.floor(totalM / (60 * 24));
    const h = Math.floor((totalM - d * 60 * 24) / 60);
    const m = totalM - d * 60 * 24 - h * 60;
    const parts = [];
    if (d > 0) parts.push(`${d}d`);
    if (h > 0 || d > 0) parts.push(`${h}h`);
    parts.push(`${m}min`);
    return parts.join(" ");
  }

  function getUpdatedAt(o) {
    return o?.UpdatedAt || o?.updated_at || o?.Updated || o?.updated || null;
  }

  function getPrice(o) {
    return o?.Price ?? o?.price ?? null;
  }

  function getSellerId(o) {
    return o?.SellerId ?? o?.UserId ?? o?.user_id ?? o?.OwnerId ?? null;
  }

  // Persist and restore basic filters
  onMount(() => {
    try {
      handleViewportResize();
      window.addEventListener('resize', handleViewportResize);
      // Ensure categories are loaded
      ensureCategorizedLoaded();
      if (typeof window !== "undefined") {
        const stored = localStorage.getItem(LS_KEY);
        if (stored) {
          const obj = JSON.parse(stored);
          if (obj?.planet) selectedPlanet = obj.planet;
          if (obj?.tableMode) tableMode = obj.tableMode;
          if (obj?.lastUpdateFilter) lastUpdateFilter = obj.lastUpdateFilter;
        }
        const orderStored = localStorage.getItem(LS_ORDER_KEY);
        if (orderStored) {
          const o = JSON.parse(orderStored);
          if (o?.planet) orderPlanet = o.planet;
        } else {
          orderPlanet = "Calypso";
        }
      }
      // Load favourites (from localStorage immediately, then DB if logged in)
      const userId = $page?.data?.session?.user?.id ?? null;
      favourites.load(userId);
    } catch {}
  });
  $: if (typeof window !== "undefined") {
    try {
      localStorage.setItem(
        LS_KEY,
        JSON.stringify({ planet: selectedPlanet, tableMode, lastUpdateFilter })
      );
      localStorage.setItem(
        LS_ORDER_KEY,
        JSON.stringify({ planet: orderPlanet })
      );
    } catch {}
  }

  // Load orders for detail view — only when we have a numeric item ID
  $: if (isDetailView && selectedItem?.i) {
    loadOrders(selectedItem.i, selectedPlanet);
  }

  // Reload price data when gender filter changes for gendered items
  $: if (isDetailView && selectedItem?.i && isGenderedDetail) {
    if (priceGender === 'Both') {
      exchangePrices = null;
      periodStats = null;
      priceHistoryData = [];
      lastGenderPriceKey = '';
    } else {
      reloadPricesForGender(selectedItem.i, priceGender);
    }
  }

  let ordersLoading = false;
  let ordersLoadedKey = "";
  async function loadOrders(numericId, planet) {
    if (!numericId || typeof numericId !== 'number') return;
    const key = `${numericId}::${planet}`;
    if (ordersLoadedKey === key) return;
    ordersLoadedKey = key;
    ordersLoading = true;
    buyOrders = [];
    sellOrders = [];
    exchangePrices = null;
    showPriceHistory = false;
    priceHistoryData = [];
    periodStats = null;
    // Reset price gender to 'Both' when switching items (no prices loaded until M/F selected)
    priceGender = 'Both';
    const skipPrices = isGenderedDetail; // gendered items on 'Both' don't need prices
    try {
      const [ordersRes, pricesRes] = await Promise.all([
        fetch(`/api/market/exchange/orders/item/${encodeURIComponent(numericId)}`),
        skipPrices ? null : fetch(`/api/market/prices/exchange/${encodeURIComponent(numericId)}?period=${selectedPeriod}`).catch(() => null),
      ]);
      if (ordersRes.ok) {
        const data = await ordersRes.json();
        buyOrders = data.buy || [];
        sellOrders = data.sell || [];
      } else {
        buyOrders = [];
        sellOrders = [];
      }
      if (pricesRes?.ok) {
        const priceData = await pricesRes.json();
        exchangePrices = { buy: priceData.buy, sell: priceData.sell };
        periodStats = priceData.period || null;
      } else {
        exchangePrices = null;
        periodStats = null;
      }
    } catch (e) {
      console.error('Error loading orders:', e);
      buyOrders = [];
      sellOrders = [];
    } finally {
      ordersLoading = false;
    }
  }

  // Reload period stats when period changes (without reloading orders)
  let lastPeriodStatsKey = '';
  async function loadPeriodStats(itemId, period) {
    if (isGenderedDetail && priceGender === 'Both') return;
    const genderParam = isGenderedDetail ? `&gender=${priceGender}` : '';
    const key = `${itemId}::${period}::${genderParam}`;
    if (key === lastPeriodStatsKey) return;
    lastPeriodStatsKey = key;
    try {
      const includeHistory = showPriceHistory ? '&history=1' : '';
      const res = await fetch(`/api/market/prices/exchange/${encodeURIComponent(itemId)}?period=${period}${includeHistory}${genderParam}`);
      if (res.ok) {
        const data = await res.json();
        periodStats = data.period || null;
        if (data.history) priceHistoryData = data.history;
      }
    } catch { /* non-fatal */ }
  }

  $: if (isDetailView && selectedItem?.i && selectedPeriod) {
    loadPeriodStats(selectedItem.i, selectedPeriod);
  }

  // Load/reload price history when toggled on or period changes
  async function loadPriceHistory() {
    if (!selectedItem?.i) return;
    if (isGenderedDetail && priceGender === 'Both') return;
    priceHistoryLoading = true;
    const genderParam = isGenderedDetail ? `&gender=${priceGender}` : '';
    try {
      const res = await fetch(`/api/market/prices/exchange/${encodeURIComponent(selectedItem.i)}?period=${selectedPeriod}&history=1${genderParam}`);
      if (res.ok) {
        const data = await res.json();
        priceHistoryData = data.history || [];
        periodStats = data.period || null;
        lastPeriodStatsKey = `${selectedItem.i}::${selectedPeriod}`;
      }
    } catch {
      priceHistoryData = [];
    } finally {
      priceHistoryLoading = false;
    }
  }

  let lastGenderPriceKey = '';
  async function reloadPricesForGender(itemId, gender) {
    const key = `${itemId}::${gender}`;
    if (key === lastGenderPriceKey) return;
    lastGenderPriceKey = key;
    const genderParam = `&gender=${gender}`;
    try {
      const includeHistory = showPriceHistory ? '&history=1' : '';
      const res = await fetch(`/api/market/prices/exchange/${encodeURIComponent(itemId)}?period=${selectedPeriod}${genderParam}${includeHistory}`);
      if (res.ok) {
        const data = await res.json();
        exchangePrices = { buy: data.buy, sell: data.sell };
        periodStats = data.period || null;
        if (data.history) priceHistoryData = data.history;
        lastPeriodStatsKey = `${itemId}::${selectedPeriod}::${genderParam}`;
      }
    } catch { /* non-fatal */ }
  }

  function togglePriceHistory() {
    showPriceHistory = !showPriceHistory;
    if (showPriceHistory && priceHistoryData.length === 0) {
      loadPriceHistory();
    }
  }

  // Reload chart data when period changes while chart is visible
  $: if (showPriceHistory && selectedItem?.i && selectedPeriod) {
    loadPriceHistory();
  }

  $: currentUser = $page?.data?.session?.user ?? null;
  $: needsAuth = !currentUser;
  $: needsVerification = !!(currentUser && !currentUser.verified);
  $: canPostOrders = !!(currentUser && currentUser.verified);
  $: floatingPanelOpen = showUserOrders || (canPostOrders && ($showMyOrders || $showInventory || $showTrades));
  $: if (!canPostOrders && $showTradeList) showTradeList.set(false);

  // Auth dialog state
  let showAuthDialog = false;
  function openAuthDialog() { showAuthDialog = true; }
  function closeAuthDialog() { showAuthDialog = false; }
  $: loginUrl = `/discord/login?redirect=${encodeURIComponent($page.url.pathname + $page.url.search)}`;

  function mapOrderRow(o, addCartCol = false) {
    const mine = currentUser && getSellerId(o) === currentUser.id;
    const cellStyle = mine
      ? "background-color: var(--hover-color); border-left: 2px solid #4caf50; border-right: 2px solid #4caf50;"
      : "";
    const qty = o?.Quantity ?? o?.quantity ?? 0;
    const unit = getPrice(o) ?? o?.UnitPrice ?? o?.unit_price ?? null;
    const ttUnit = o?.TTValue ?? o?.Value ?? o?.tt_value ?? o?.details?.CurrentTT ?? null;
    const total =
      o?.TotalPrice ??
      o?.total ??
      (unit != null && qty != null ? unit * qty : null);
    const ttTotal =
      o?.TTTotal ??
      o?.tt_total ??
      (ttUnit != null && qty != null ? ttUnit * qty : null);
    const muPct =
      o?.MarkupPct ??
      o?.markup_pct ??
      (ttTotal && total ? (total / ttTotal) * 100 : null);
    const absMu =
      unit != null && ttUnit != null
        ? unit - ttUnit
        : (o?.Markup ?? o?.markup ?? null);
    const isAbsMu = detailIsAbsoluteMarkup;
    const muText = isAbsMu
      ? formatMarkupValue(absMu, true)
      : formatMarkupValue(muPct, false);

    const type =
      selectedItemDetails?.Properties?.Type || selectedItem?.t || null;
    const isTierable = tierableTypes.has(type);
    const tier = o?.Tier ?? o?.tier ?? o?.details?.Tier ?? null;
    const tir = o?.TiR ?? o?.tir ?? o?.TIR ?? o?.details?.TierIncreaseRate ?? null;

    const baseValues = [
      qty,
      formatPedValue(ttUnit),
      muText,
      formatPedValue(total),
      o?.Planet || o?.planet || selectedPlanet || "N/A",
      o?.SellerName || o?.seller || "Unknown",
      formatLastUpdateDHm(getUpdatedAt(o)),
    ];
    const baseStyles = [
      cellStyle,
      cellStyle,
      cellStyle,
      cellStyle,
      cellStyle,
      cellStyle,
      cellStyle,
    ];

    const values = isTierable
      ? [tier ?? "N/A", tir ?? "N/A", ...baseValues]
      : baseValues;
    const tdStyles = isTierable
      ? [cellStyle, cellStyle, ...baseStyles]
      : baseStyles;

    if (addCartCol) {
      const orderId = o?.id ?? o?.Id ?? 0;
      const cartBtn = `<button class="cell-button cart-add-btn" data-cart-add="${orderId}">+Cart</button>`;
      values.push(cartBtn);
      tdStyles.push(cellStyle);
    }

    return { values, tdStyles, detail: o };
  }

  function applyOrderFilters(orders) {
    const maxTT = getMaxTT(selectedItemDetails);
    const isAbsMu = detailIsAbsoluteMarkup;
    const bpNonL = isBlueprintNonL(selectedItemDetails);

    return (orders || [])
      .filter((o) =>
        selectedPlanet === "All Planets" ||
        (o?.Planet || o?.planet) === selectedPlanet
      )
      .filter((o) => {
        // Tier filter (UL tierable items only)
        if (!isTierableDetail || isLimitedDetail) return true;
        if (tierMin <= 0 && tierMax >= 10) return true;
        const t = Number(o?.Tier ?? o?.tier ?? o?.details?.Tier);
        return isFinite(t) ? Math.floor(t) >= tierMin && Math.floor(t) <= tierMax : true;
      })
      .filter((o) => {
        // TiR filter (all tierable items)
        if (!isTierableDetail) return true;
        if (tirMin <= 0 && tirMax >= tirRangeMax) return true;
        const tir = Number(o?.TiR ?? o?.tir ?? o?.TIR ?? o?.details?.TierIncreaseRate);
        return isFinite(tir) ? tir >= tirMin && tir <= tirMax : true;
      })
      .filter((o) =>
        lastUpdateFilter === "all"
          ? true
          : classifyFreshness(getUpdatedAt(o)) === lastUpdateFilter
      )
      .filter((o) => {
        // Min TT filter (stackable items only)
        if (!minTTFilter || !detailItemStackable) return true;
        const qty = o?.Quantity ?? o?.quantity ?? 0;
        const ttTotal = maxTT != null ? maxTT * qty : null;
        return ttTotal == null || ttTotal >= minTTFilter;
      })
      .filter((o) => {
        // Condition % filter (condition items only)
        if (!detailHasCondition || minConditionPct <= 0) return true;
        const currentTT = o?.details?.CurrentTT ?? o?.Value ?? o?.tt_value ?? null;
        if (currentTT == null || maxTT == null || maxTT <= 0) return true;
        const pct = (currentTT / maxTT) * 100;
        return pct >= minConditionPct;
      })
      .filter((o) => {
        // QR filter (non-L blueprints only)
        if (!isBlueprintDetail || isLimitedDetail) return true;
        if (qrMin <= 0 && qrMax >= 100) return true;
        const qr = Number(o?.details?.QualityRating) || 0;
        return qr >= qrMin && qr <= qrMax;
      })
      .filter((o) => {
        // Gender filter (gendered items only)
        if (!isGenderedDetail || priceGender === 'Both') return true;
        return o?.details?.Gender === priceGender;
      })
      .map(o => {
        const qty = o?.Quantity ?? o?.quantity ?? 0;
        const mu = o?.Markup ?? o?.markup ?? null;
        const muNum = mu != null ? Number(mu) : null;
        // Compute TT value and unit price from item's MaxTT and order markup
        let ttValue = o?.TTValue ?? o?.Value ?? o?.tt_value ?? o?.details?.CurrentTT ?? null;
        let unitPrice = o?.Price ?? o?.price ?? o?.UnitPrice ?? o?.unit_price ?? null;
        if (ttValue == null) {
          if (bpNonL) {
            const qr = Number(o?.details?.QualityRating) || 0;
            if (qr > 0) ttValue = qr / 100;
          } else if (maxTT != null) {
            ttValue = maxTT;
          }
        }
        if (unitPrice == null && muNum != null) {
          if (bpNonL) {
            unitPrice = (ttValue || 0) + muNum;
          } else if (ttValue != null) {
            unitPrice = isAbsMu ? ttValue + muNum : ttValue * (muNum / 100);
          }
        }
        return {
          ...o,
          quantity: qty,
          tier: o?.Tier ?? o?.tier ?? o?.details?.Tier ?? null,
          tir: o?.TiR ?? o?.tir ?? o?.TIR ?? o?.details?.TierIncreaseRate ?? null,
          planet: o?.Planet ?? o?.planet ?? selectedPlanet ?? 'N/A',
          seller_name: o?.SellerName ?? o?.seller ?? o?.seller_name ?? 'Unknown',
          markup: mu,
          TTValue: ttValue,
          Price: unitPrice,
        };
      });
  }

  let minTTFilter = 0;

  // Explicit dependency list so Svelte re-runs when any filter variable changes
  $: orderFilterDeps = [selectedPlanet, tierMin, tierMax, tirMin, tirMax, tirRangeMax,
    lastUpdateFilter, minTTFilter, minConditionPct, qrMin, qrMax,
    detailItemStackable, detailHasCondition, isTierableDetail, isLimitedDetail, isBlueprintDetail,
    isGenderedDetail, priceGender];

  $: filteredSellOrders = (orderFilterDeps, applyOrderFilters(sellOrders))
    .sort((a, b) => (a.Price ?? Infinity) - (b.Price ?? Infinity));

  $: filteredBuyOrders = (orderFilterDeps, applyOrderFilters(buyOrders))
    .sort((a, b) => (b.Price ?? -Infinity) - (a.Price ?? -Infinity));

  $: myBuyOrder = currentUser && (buyOrders || []).find(o => getSellerId(o) === currentUser.id) || null;
  $: mySellOrder = currentUser && (sellOrders || []).find(o => getSellerId(o) === currentUser.id) || null;
  // Only show "Edit" for fungible/stackable items (single order per side)
  $: detailItemStackable = selectedItemDetails ? isItemStackable(selectedItemDetails) : false;
  $: hasMyBuyOrder = detailItemStackable && !!myBuyOrder;
  $: hasMySellOrder = detailItemStackable && !!mySellOrder;

  function openOrderDialog(type) {
    const item = selectedItemDetails;
    if (!item) return;

    // Block untradeable clothing (null gender classification)
    if (selectedItem?.t === 'Clothing' && selectedItemGender === null) {
      addToast('This item cannot be traded (no gender classification).', { type: 'warning' });
      return;
    }

    orderDialogType = type;
    const itemId = item?.ItemId ?? item?.Id ?? item?.i;
    const side = type === 'buy' ? 'BUY' : 'SELL';
    // Count existing orders for this item+side
    orderDialogExistingCount = ($myOrders || []).filter(
      o => o.item_id === itemId && o.type === side && o.state !== 'closed'
    ).length;

    // For fungible/stackable items, edit the existing order if one exists
    const existingOrder = detailItemStackable
      ? (type === 'buy' ? myBuyOrder : mySellOrder)
      : null;
    if (existingOrder) {
      editOrderInline(existingOrder);
      return;
    }

    // Ensure MaxTT is available — fall back to slim item value if full details lack it
    if (getMaxTT(item) == null && selectedItem?.v != null) {
      item.MaxTT = selectedItem.v;
    }
    // Carry material sub-type (Deed/Token/Share) from slim item for markup detection
    if (selectedItem?.st) item.st = selectedItem.st;

    setTimeout(() => {
      orderDialogRef?.initOrder(item, type, 'create');
      showOrderDialog = true;
    }, 0);
  }
  // Compute whether the current dialog item is non-fungible (allows multiple orders)
  $: orderDialogItemType = (() => {
    const item = inlineEditItem || selectedItemDetails || selectedItem;
    return item?.Properties?.Type ?? item?.Type ?? item?.t ?? null;
  })();
  $: orderDialogIsNonFungible = orderDialogItemType ? !isItemStackable({ Type: orderDialogItemType, Name: (inlineEditItem || selectedItemDetails || selectedItem)?.Name || (inlineEditItem || selectedItemDetails || selectedItem)?.n || '' }) : false;

  // Resolve gender for OrderDialog: use slim cache for inline edits, selectedItemGender for detail view
  $: orderDialogGender = (() => {
    if (inlineEditItem) {
      // Inline edit: look up gender from slim cache
      const itemId = inlineEditItem?.ItemId ?? inlineEditItem?.Id ?? inlineEditItem?.i;
      const slimItem = itemId ? (allItems || []).find(si => si?.i === itemId) : null;
      return slimItem?.g;
    }
    return selectedItemGender;
  })();

  function closeOrderDialog() {
    showOrderDialog = false;
    orderDialogType = null;
    inlineEditItem = null;
    orderDialogExistingCount = 0;
  }

  let submittingOrder = false; // Prevent double-click

  async function submitOrderPayload(order, closeAfter = true, turnstileToken = null) {
    if (submittingOrder) return false;
    submittingOrder = true;

    const item = inlineEditItem || selectedItemDetails || selectedItem;
    const itemId = item?.ItemId ?? item?.Id ?? item?.i;
    if (!itemId) { if (closeAfter) closeOrderDialog(); submittingOrder = false; return false; }

    const isEdit = !!order._orderId;
    const payload = {
      type: order.Type === 'Buy' ? 'BUY' : 'SELL',
      item_id: itemId,
      quantity: order.Quantity || 1,
      markup: order.Markup || 0,
      planet: order.Planet || selectedPlanet || 'Calypso',
      min_quantity: order.MinQuantity || null,
      details: {
        item_name: order.Item?.Name || item?.Name || item?.n || '',
        ...(order.Metadata || {}),
      }
    };
    if (turnstileToken) payload.turnstile_token = turnstileToken;
    if (order.CurrentTT != null) {
      payload.details.CurrentTT = order.CurrentTT;
    }
    delete payload.details._orderId;
    delete payload.details._inlineEdit;
    delete payload.details._inventoryWarning;
    delete payload.details._inventoryQty;

    try {
      let res;
      if (isEdit) {
        res = await fetch(`/api/market/exchange/orders/${order._orderId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        res = await fetch('/api/market/exchange/orders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }
      const data = await res.json();
      if (!res.ok) {
        addToast(data.error || `Order ${isEdit ? 'update' : 'creation'} failed`);
        submittingOrder = false;
        return false;
      }
      upsertOrder(data);
      await refreshAfterOrderChange();
      if (closeAfter) closeOrderDialog();
      return true;
    } catch (e) {
      console.error('Error submitting order:', e);
      if (closeAfter) closeOrderDialog();
      return false;
    } finally {
      submittingOrder = false;
    }
  }

  async function refreshAfterOrderChange() {
    if (!inlineEditItem) {
      // New order created — full reload including prices
      ordersLoadedKey = '';
      if (selectedItem?.i) await loadOrders(selectedItem.i, selectedPlanet);
    } else if (isDetailView && selectedItem?.i) {
      // Edited/deleted from detail view — refresh orders only (preserve price/gender state)
      try {
        const res = await fetch(`/api/market/exchange/orders/item/${encodeURIComponent(selectedItem.i)}`);
        if (res.ok) {
          const data = await res.json();
          buyOrders = data.buy || [];
          sellOrders = data.sell || [];
        }
      } catch (e) {
        console.error('Error refreshing orders:', e);
      }
    }
  }

  async function onSubmitOrder(e) {
    const order = e?.detail?.order;
    const turnstileToken = e?.detail?.turnstileToken;
    if (!order) { closeOrderDialog(); return; }
    await submitOrderPayload(order, true, turnstileToken);
  }

  async function onNextOrder(e) {
    const order = e?.detail?.order;
    const turnstileToken = e?.detail?.turnstileToken;
    if (!order) return;
    const success = await submitOrderPayload(order, false, turnstileToken);
    if (success) {
      orderDialogExistingCount++;
      // Re-init dialog for the next order (keep same item, reset form)
      const item = inlineEditItem || selectedItemDetails || selectedItem;
      if (item) {
        orderDialogRef?.initOrder(item, orderDialogType || 'sell', 'create');
      }
    }
  }

  async function handleDeleteOrder(e) {
    const order = e?.detail?.order;
    const turnstileToken = e?.detail?.turnstileToken;
    const orderId = order?._orderId;
    if (!orderId) { closeOrderDialog(); return; }

    if (!confirm('Are you sure you want to delete this order?')) return;

    try {
      const res = await fetch(`/api/market/exchange/orders/${orderId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ turnstile_token: turnstileToken })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        addToast(data.error || 'Failed to delete order');
        return;
      }
      upsertOrder(data);
      await refreshAfterOrderChange();
      closeOrderDialog();
    } catch (err) {
      addToast('Failed to delete order');
    }
  }

  // FancyTable columns for detail view buy/sell tables
  $: detailColumns = (() => {
    const type = selectedItemDetails?.Properties?.Type || selectedItem?.t || null;
    const showTier = tierableTypes.has(type);
    const isAbsMu = detailIsAbsoluteMarkup;
    const isBpNonL = isBlueprintNonL(selectedItemDetails);
    const isPetItem = isPet(selectedItemDetails) || selectedItem?.t === 'Pet';
    const cols = [];

    // Mobile: combined "Details" column with tags (like UserOrdersPanel)
    const hasDetailTags = showTier || isPetItem || type === 'ArmorPlating' || isGenderedDetail || isBpNonL;
    if (hasDetailTags) {
      cols.push({ key: '_detailTags', header: 'Details', width: '120px', mobileWidth: '95px', sortable: false, searchable: false,
        hideOnDesktop: true,
        formatter: (v, row) => {
          const d = row?.details;
          if (!d) return '';
          const tags = [];
          if (showTier && d.Tier != null) tags.push(`<span class="detail-tag">T${d.Tier}</span>`);
          if (showTier && d.TierIncreaseRate != null) tags.push(`<span class="detail-tag">TiR ${d.TierIncreaseRate}</span>`);
          if (isPetItem && d.Pet?.Level != null) tags.push(`<span class="detail-tag">Lv ${d.Pet.Level}</span>`);
          if (isBpNonL && d.QualityRating != null) tags.push(`<span class="detail-tag">QR ${d.QualityRating}</span>`);
          if (type === 'ArmorPlating' && d.is_set) tags.push(`<span class="detail-tag">Set</span>`);
          if (isGenderedDetail && d.Gender) tags.push(`<span class="detail-tag">${d.Gender}</span>`);
          return tags.length ? `<span class="detail-tags">${tags.join('')}</span>` : '';
        }
      });
    }

    if (showTier) {
      cols.push({ key: 'tier', header: 'Tier', width: '60px', sortable: true, searchable: false, hideOnMobile: true,
        formatter: (v) => v ?? 'N/A' });
      cols.push({ key: 'tir', header: 'TiR', width: '80px', sortable: true, searchable: false, hideOnMobile: true,
        formatter: (v) => v ?? 'N/A' });
    }
    if (isPetItem) {
      cols.push({ key: '_petLevel', header: 'Level', width: '70px', sortable: true, searchable: false, hideOnMobile: true,
        sortValue: (row) => getPetLevel(row) ?? -1,
        formatter: (v, row) => {
          const lvl = getPetLevel(row);
          return lvl != null ? String(lvl) : 'N/A';
        }});
    }
    const itemMaxTT = getMaxTT(selectedItemDetails) ?? selectedItem?.v ?? null;
    const stackable = isItemStackable(selectedItemDetails || selectedItem);
    if (stackable) {
      cols.push({ key: 'quantity', header: 'Qty', width: '80px', mobileWidth: '55px', sortable: true, searchable: false,
        formatter: (v) => v ?? 0 });
    }

    // ArmorPlating: show Set column
    if (type === 'ArmorPlating') {
      cols.push({ key: '_is_set', header: 'Set', width: '55px', sortable: true, searchable: false, hideOnMobile: true,
        sortValue: (row) => row?.details?.is_set ? 1 : 0,
        formatter: (v, row) => row?.details?.is_set
          ? '<span class="badge badge-subtle badge-set-yes">Yes</span>'
          : '<span class="badge badge-subtle">No</span>'
      });
    }

    // Gendered items: show Gender column
    if (isGenderedDetail) {
      cols.push({ key: '_gender', header: 'Gender', width: '70px', sortable: true, searchable: false, hideOnMobile: true,
        sortValue: (row) => row?.details?.Gender === 'Male' ? 0 : row?.details?.Gender === 'Female' ? 1 : 2,
        formatter: (v, row) => {
          const g = row?.details?.Gender;
          return g === 'Male' ? 'M' : g === 'Female' ? 'F' : '-';
        }
      });
    }

    // Helper: get TT value for a row, accounting for non-L BPs using QR/100
    function getRowTT(row) {
      if (isBpNonL) {
        const qr = Number(row?.details?.QualityRating) || 0;
        return qr > 0 ? qr / 100 : null;
      }
      const qty = row?.quantity ?? 1;
      // Stackable items have fixed TT per unit — always use maxTT * qty
      if (stackable && itemMaxTT != null) return itemMaxTT * qty;
      return row?.details?.CurrentTT ?? itemMaxTT;
    }

    cols.push({ key: '_value', header: 'Value', width: '130px', mobileWidth: '85px', sortable: true, searchable: false,
      sortValue: (row) => getRowTT(row) ?? -1,
      formatter: (v, row) => {
        if (isBpNonL) {
          const qr = Number(row?.details?.QualityRating) || 0;
          if (qr <= 0) return 'Any QR';
          return `${formatPedValue(qr / 100)} <span class="tt-pct">(QR ${qr})</span>`;
        }
        const tt = getRowTT(row);
        if (tt == null) return 'N/A';
        const ttStr = formatPedValue(tt);
        if (!stackable && row?.details?.CurrentTT != null && itemMaxTT != null && itemMaxTT > 0) {
          const pct = Math.round((Number(row.details.CurrentTT) / itemMaxTT) * 100);
          return `${ttStr} <span class="tt-pct">(${pct}%)</span>`;
        }
        return ttStr;
      }});
    cols.push({ key: 'markup', header: isAbsMu ? 'MU (+PED)' : 'MU (%)', width: '100px', mobileWidth: '80px', sortable: true, searchable: false,
      formatter: (v) => formatMarkupValue(v, isAbsMu)});
    cols.push({ key: '_total', header: 'Total', width: '120px', sortable: true, searchable: false, hideOnMobile: true,
      sortValue: (row) => {
        const mu = row?.markup != null ? Number(row.markup) : null;
        if (mu == null) return -1;
        if (isBpNonL) {
          const tt = getRowTT(row);
          return tt != null ? tt + mu : mu;
        }
        const qty = row?.quantity ?? 1;
        const tt = getRowTT(row);
        if (tt == null) return -1;
        return isAbsMu ? tt + mu * qty : tt * (mu / 100);
      },
      formatter: (v, row) => {
        const mu = row?.markup != null ? Number(row.markup) : null;
        if (mu == null) return 'N/A';
        if (isBpNonL) {
          const tt = getRowTT(row);
          return formatPedValue(tt != null ? tt + mu : mu);
        }
        const qty = row?.quantity ?? 1;
        const tt = getRowTT(row);
        if (tt == null) return 'N/A';
        const total = isAbsMu ? tt + mu * qty : tt * (mu / 100);
        return formatPedValue(total);
      }});
    cols.push({ key: 'planet', header: 'Planet', width: '120px', sortable: true, searchable: false, hideOnMobile: true,
      formatter: (v) => v || selectedPlanet || 'N/A' });
    cols.push({ key: 'bumped_at', header: 'Updated', width: '100px', sortable: true, searchable: false, hideOnMobile: true,
      formatter: (v, row) => formatLastUpdateDHm(getUpdatedAt(row) || v) });

    return cols;
  })();

  function makeUserColumn(header) {
    return { key: 'seller_name', header, main: true, mobileWidth: '1fr', sortable: true, searchable: false,
      formatter: (v, row) => {
        const name = row?.SellerName ?? row?.seller ?? v ?? 'Unknown';
        const userId = row?.user_id ?? '';
        const safeName = name.replace(/"/g, '&quot;');
        const href = `/market/exchange/orders/${encodeURIComponent(name)}`;
        return `<a class="seller-link" href="${href}" data-seller-id="${userId}" data-seller-name="${safeName}">${name}</a>`;
      }};
  }

  // Sell orders: user column = "Seller", action = "Buy" (or "Edit" for own orders)
  $: sellDetailColumns = (() => {
    const cols = detailColumns.map(c => ({...c}));
    // For stackable items, add Min Qty column after Qty
    const stackable = isItemStackable(selectedItemDetails || selectedItem);
    if (stackable) {
      const qtyIdx = cols.findIndex(c => c.key === 'quantity');
      if (qtyIdx >= 0) {
        cols.splice(qtyIdx + 1, 0, {
          key: 'min_quantity', header: 'Min Qty', width: '70px', sortable: true, searchable: false, hideOnMobile: true,
          formatter: (v) => v != null && v > 0 ? v : '\u2014'
        });
      }
    }
    const updatedIdx = cols.findIndex(c => c.key === 'bumped_at');
    cols.splice(updatedIdx >= 0 ? updatedIdx : cols.length, 0, makeUserColumn('Seller'));
    cols.push({
      key: '_action', header: '', width: '70px', mobileWidth: '40px', sortable: false, searchable: false,
      cellClass: () => 'cell-center',
      formatter: canPostOrders ? (v, row) => {
        const orderId = row?.id ?? row?.Id ?? 0;
        const isOwn = currentUser && String(getSellerId(row)) === String(currentUser.id);
        if (isOwn) return `<button class="cell-button trade-btn edit-trade-btn" data-trade-buy="${orderId}">Edit</button>`;
        return `<button class="cell-button trade-btn buy-trade-btn" data-trade-buy="${orderId}">Buy</button>`;
      } : () => ''
    });
    return cols;
  })();

  // Buy orders: user column = "Buyer", action = "Sell" (or "Edit" for own orders)
  $: buyDetailColumns = (() => {
    const cols = detailColumns.map(c => ({...c}));
    // Buy orders specify minimum requirements for properties
    for (const col of cols) {
      if (col.key === 'tier') col.header = 'Min. Tier';
      else if (col.key === 'tir') col.header = 'Min. TiR';
      else if (col.key === '_petLevel') col.header = 'Min. Level';
      else if (col.key === '_value' && isBlueprintNonL(selectedItemDetails)) col.header = 'Min. QR';
    }
    const stackable = isItemStackable(selectedItemDetails || selectedItem);
    if (stackable) {
      const qtyIdx = cols.findIndex(c => c.key === 'quantity');
      if (qtyIdx >= 0) {
        cols.splice(qtyIdx + 1, 0, {
          key: 'min_quantity', header: 'Min Qty', width: '70px', sortable: true, searchable: false, hideOnMobile: true,
          formatter: (v) => v != null && v > 0 ? v : '\u2014'
        });
      }
    }
    const updatedIdx = cols.findIndex(c => c.key === 'bumped_at');
    cols.splice(updatedIdx >= 0 ? updatedIdx : cols.length, 0, makeUserColumn('Buyer'));
    cols.push({
      key: '_action', header: '', width: '70px', mobileWidth: '40px', sortable: false, searchable: false,
      cellClass: () => 'cell-center',
      formatter: canPostOrders ? (v, row) => {
        const orderId = row?.id ?? row?.Id ?? 0;
        const isOwn = currentUser && String(getSellerId(row)) === String(currentUser.id);
        if (isOwn) return `<button class="cell-button trade-btn edit-trade-btn" data-trade-sell="${orderId}">Edit</button>`;
        return `<button class="cell-button trade-btn sell-trade-btn" data-trade-sell="${orderId}">Sell</button>`;
      } : () => ''
    });
    return cols;
  })();

  /** Handle clicks on Buy/Sell trade buttons and seller links in detail view */
  function handleDetailClick(e) {
    // Seller name click → open user orders panel
    const sellerEl = e.target.closest('[data-seller-id]');
    if (sellerEl) {
      e.stopPropagation();
      e.preventDefault();
      const userId = sellerEl.dataset.sellerId;
      const name = sellerEl.dataset.sellerName || 'Unknown';
      if (userId) openUserOrdersPanel(userId, name);
      return;
    }

    const buyBtn = e.target.closest('[data-trade-buy]');
    const sellBtn = e.target.closest('[data-trade-sell]');
    if (!buyBtn && !sellBtn) return;
    e.stopPropagation();
    e.preventDefault();

    if (buyBtn) {
      const orderId = parseInt(buyBtn.dataset.tradeBuy, 10);
      const order = (sellOrders || []).find(o => (o?.id ?? o?.Id) === orderId);
      if (order) {
        if (currentUser && String(getSellerId(order)) === String(currentUser.id)) {
          editOrderInline(order);
        } else {
          openQuickTrade(order, 'buy');
        }
      }
    } else if (sellBtn) {
      const orderId = parseInt(sellBtn.dataset.tradeSell, 10);
      const order = (buyOrders || []).find(o => (o?.id ?? o?.Id) === orderId);
      if (order) {
        if (currentUser && String(getSellerId(order)) === String(currentUser.id)) {
          editOrderInline(order);
        } else {
          openQuickTrade(order, 'sell');
        }
      }
    }
  }

  function openQuickTrade(order, side, itemOverride = null) {
    quickTradeOrder = order;
    quickTradeSide = side;
    quickTradeItem = itemOverride;
    showQuickTrade = true;
  }

  function closeQuickTrade() {
    showQuickTrade = false;
    quickTradeOrder = null;
    quickTradeItem = null;
  }

  async function handleQuickTradeConfirm(e) {
    const { order, quantity, side } = e.detail;
    const item = selectedItemDetails || selectedItem;
    const itemName = order.details?.item_name || item?.Name || item?.n || 'Unknown';

    try {
      const res = await fetch('/api/market/trade-requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_id: order.user_id,
          planet: order.planet || null,
          items: [{
            offer_id: order.id,
            item_id: order.item_id ?? item?.i ?? item?.Id,
            item_name: itemName,
            quantity: quantity || order.quantity || 1,
            markup: order.markup || 0,
            side: order.type || (side === 'buy' ? 'SELL' : 'BUY')
          }]
        })
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || 'Failed to create trade request');
      }
      closeQuickTrade();
      // Open trades tab so user can see the new request
      goto('/market/exchange/trades');
    } catch (err) {
      console.error('Trade request error:', err);
      quickTradeRef?.setError(err.message || 'Failed to create trade request');
    }
  }

  async function handleBulkSubmit(e) {
    const { matches, planet } = e.detail;
    const item = selectedItemDetails || selectedItem;
    const itemName = item?.Name || item?.n || 'Unknown';
    const itemId = item?.ItemId ?? item?.Id ?? item?.i;

    let created = 0;
    for (const match of matches) {
      try {
        const res = await fetch('/api/market/trade-requests', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_id: match.user_id,
            planet: planet || match.planet || null,
            items: [{
              offer_id: match.id,
              item_id: match.item_id ?? itemId,
              item_name: match.details?.item_name || itemName,
              quantity: match.fillQuantity || match.quantity || 1,
              markup: match.markup || 0,
              side: match.type || 'SELL'
            }]
          })
        });
        if (res.ok) created++;
      } catch (err) {
        console.error('Bulk trade request error:', err);
      }
    }
    if (created > 0) {
      showBulkTradeDialog = false;
      goto('/market/exchange/trades');
    }
  }

  $: isBlueprintDetail = selectedItemDetails && isBlueprint(selectedItemDetails);
  $: isTierableDetail = selectedItemDetails && isItemTierable(selectedItemDetails);
  $: isLimitedDetail = selectedItemDetails && isLimited(selectedItemDetails);
  $: detailHasCondition = selectedItemDetails && itemHasCondition(selectedItemDetails) && !detailItemStackable && isLimitedDetail;
  $: tirRangeMax = isLimitedDetail ? 4000 : 200;
  $: hasDetailFilters = isTierableDetail || (isBlueprintDetail && !isLimitedDetail) || detailItemStackable || detailHasCondition;
  $: hasActiveDetailFilters = (isTierableDetail && !isLimitedDetail && (tierMin > 0 || tierMax < 10))
    || (isTierableDetail && (tirMin > 0 || tirMax < tirRangeMax))
    || (isBlueprintDetail && !isLimitedDetail && (qrMin > 0 || qrMax < 100))
    || (detailItemStackable && minTTFilter > 0)
    || (detailHasCondition && minConditionPct > 0);

  // Reset detail filters when item changes
  let lastFilterItemId = null;
  $: if (selectedItem?.i !== lastFilterItemId) {
    lastFilterItemId = selectedItem?.i ?? null;
    tierMin = 0; tierMax = 10;
    tirMin = 0; tirMax = tirRangeMax;
    qrMin = 0; qrMax = 100;
    minConditionPct = 0;
    minTTFilter = 0;
    showFilterDialog = false;
  }
  // Sync tirMax when tirRangeMax changes (e.g. item details load and L/UL is determined)
  let lastTirRangeMax = 200;
  $: if (tirRangeMax !== lastTirRangeMax) {
    if (tirMax === lastTirRangeMax) tirMax = tirRangeMax;
    lastTirRangeMax = tirRangeMax;
  }

  // Favourites
  $: currentItemId = selectedItem?.i ?? null;
  $: isCurrentFavourited = currentItemId != null && $favourites && isFavourite(currentItemId);

  function handleToggleFavourite() {
    if (currentItemId != null) toggleFavourite(currentItemId);
  }

  function handleFavouriteItemSelect(itemId) {
    closeFloatingPanelIfOpen();
    if (itemId != null) {
      goto(`/market/exchange/listings/${itemId}`);
    }
  }
</script>

<svelte:head>
  <title>{isDetailView && selectedItem?.n ? `${selectedItem.n} - ` : viewSlug !== 'listings' ? `${viewSlug.charAt(0).toUpperCase() + viewSlug.slice(1)} - ` : ''}Exchange - Market - Entropia Nexus</title>
</svelte:head>

<div class="exchange-browser">
  <div class="content">
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="sidebar-overlay" class:visible={mobileSidebarOpen} on:click={() => mobileSidebarOpen = false}></div>
    <div class="sidebar" class:mobile-open={mobileSidebarOpen}>
      <h1 class="sidebar-title">Exchange <span class="beta-badge">BETA</span></h1>
      <div class="sidebar-tabs">
        <button class="sidebar-tab" class:active={sidebarTab === 'categories'} on:click={() => { sidebarTab = 'categories'; favouriteFolderFilter = null; selectedFavFolderId = null; }}>Categories</button>
        <button class="sidebar-tab" class:active={sidebarTab === 'favourites'} on:click={() => sidebarTab = 'favourites'}>Favourites</button>
      </div>
      {#if sidebarTab === 'categories'}
        <div class="category-scroll">
          <CategoryTree
            categories={categoriesWithAll}
            onSelectCategory={(path, items) => { handleCategorySelect(path, items); mobileSidebarOpen = false; }}
            selectedPath={selectedCategory}
          />
        </div>
      {:else}
        <div class="favourites-header">
          <h3>Favourites</h3>
          <button class="new-folder-header-btn" on:click={() => createFolder('New Folder')}>+ Folder</button>
        </div>
        <div class="category-scroll">
          <FavouritesTree
            favouritesData={$favourites}
            {allItems}
            showNewFolderButton={false}
            selectedFolderId={selectedFavFolderId}
            selectedItemId={currentItemId}
            onSelectItem={(itemId) => { handleFavouriteItemSelect(itemId); mobileSidebarOpen = false; }}
            onSelectFolder={handleFavouriteFolderSelect}
          />
        </div>
      {/if}
    </div>

    <div class="main-content">
      {#if floatingPanelOpen}
        <!-- Content hidden when floating panel is open -->
      {:else if !isDetailView}
        <div class="filters">
          <div class="filter-search-row">
            <button class="mobile-category-toggle" on:click={() => mobileSidebarOpen = !mobileSidebarOpen}>
              Categories
            </button>
            <input
              type="text"
              placeholder="Search items..."
              bind:value={searchTerm}
              class="search-input"
            />
          </div>
          <div class="filter-dropdowns">
            <select
              class="filter-select"
              bind:value={selectedPlanet}
            >
              <option>All Planets</option>
              {#each availablePlanets as p}
                <option>{p}</option>
              {/each}
            </select>
            <select class="filter-select" bind:value={selectedLimited}>
              <option value="all">{smallViewport ? 'L & UL' : 'Limited & Unlimited'}</option>
              <option value="L">{smallViewport ? 'L' : 'Limited'}</option>
              <option value="UL">{smallViewport ? 'UL' : 'Unlimited'}</option>
            </select>
            <select class="filter-select" bind:value={selectedSex}>
              <option value="both">{smallViewport ? 'M & F' : 'Male & Female'}</option>
              <option value="male">{smallViewport ? 'M' : 'Male'}</option>
              <option value="female">{smallViewport ? 'F' : 'Female'}</option>
            </select>
          </div>
          <div class="filter-actions">
            <div class="order-side-toggle">
              <button class="order-side-btn" class:active={selectedOrderSide === 'all'} on:click={() => selectedOrderSide = 'all'}>All</button>
              <button class="order-side-btn" class:active={selectedOrderSide === 'sell'} on:click={() => selectedOrderSide = 'sell'}>Sell</button>
              <button class="order-side-btn" class:active={selectedOrderSide === 'buy'} on:click={() => selectedOrderSide = 'buy'}>Buy</button>
            </div>
            <div class="actions-right">
            {#if canPostOrders}
              <button class="action-btn accent-btn" title="My Orders" on:click={() => {
                const userName = currentUser?.eu_name;
                goto(userName ? `/market/exchange/orders/${encodeURIComponentSafe(userName)}` : '/market/exchange/orders');
              }}>My Orders</button>
              <button class="action-btn accent-btn" title="Inventory" on:click={() => goto('/market/exchange/inventory')}>Inventory</button>
              {#if $tradeList.length > 0}
                <button class="action-btn trade-list-btn" title="Trade List" on:click={() => { closeFloatingPanel(); showTradeList.set(true); }}>
                  Trade List ({$tradeList.length})
                </button>
              {/if}
            {:else}
              <button class="auth-hint-btn" on:click={openAuthDialog}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <span>{needsAuth ? 'Log in to post Orders' : 'Verify to post Orders'}</span>
              </button>
            {/if}
            </div>
          </div>
        </div>

        {#if $showTradeList}
          <CartSummary {allItems} on:close={() => showTradeList.set(false)} />
        {:else if listTableData.length > 0}
          <div class="table-wrapper">
            <FancyTable
              columns={listColumns}
              data={listTableData}
              rowHeight={32}
              compact={true}
              sortable={true}
              searchable={false}
              defaultSort={listDefaultSort}
              emptyMessage="No items found"
              on:rowClick={(evt) => {
                const item = evt?.detail?.row?._item;
                if (item?.i != null) goto(`/market/exchange/listings/${item.i}`);
              }}
            />
            {#if loading}
              <div class="overlay"><div class="spinner"></div></div>
            {/if}
          </div>
        {:else if selectedCategory}
          <div class="empty-state">
            <p>
              No items found in this category{searchTerm
                ? ` matching \"${searchTerm}\"`
                : ""}.
            </p>
          </div>
        {:else if searchTerm}
          <div class="empty-state">
            <p>No items found matching "{searchTerm}".</p>
          </div>
        {:else}
          <div class="welcome-state">
            <h3>Welcome to the Entropia Exchange</h3>
            <p>
              Select a category from the sidebar or use the search bar to find
              items.
            </p>
          </div>
        {/if}
        {#if initialLoading}
          <div class="overlay"><div class="loader">Loading exchange…</div></div>
        {/if}
      {:else}
        <div class="filters filters-detail">
          <button class="mobile-category-toggle" on:click={() => mobileSidebarOpen = !mobileSidebarOpen}>
            Categories
          </button>
          <select
            class="filter-select"
            bind:value={selectedPlanet}
            on:change={() => { ordersLoadedKey = ''; if (selectedItem?.i) loadOrders(selectedItem.i, selectedPlanet); }}
          >
            <option>All Planets</option>
            {#each PLANETS as p}
              <option>{p}</option>
            {/each}
          </select>
          <select class="filter-select" bind:value={tableMode}>
            <option value="both">Buy & Sell</option>
            <option value="buy">Buy Only</option>
            <option value="sell">Sell Only</option>
          </select>
          <select class="filter-select" bind:value={lastUpdateFilter}>
            <option value="fresh">Fresh only (24h)</option>
            <option value="recent">Recent only (7d)</option>
            <option value="all">All</option>
          </select>
          <div class="actions-right">
            {#if selectedItem?.t === 'Clothing' && selectedItemGender === null}
              <span class="untradeable-notice">This item cannot be traded (no gender classification)</span>
            {:else if canPostOrders}
              <button
                class="action-btn buy-btn"
                on:click={() => openOrderDialog("buy")}
                disabled={!selectedItemDetails}
                title={hasMyBuyOrder
                  ? "Edit your existing buy order"
                  : "Create Buy Order"}>{hasMyBuyOrder ? 'Edit Buy' : 'Buy'}</button
              >
              <button
                class="action-btn sell-btn"
                on:click={() => openOrderDialog("sell")}
                disabled={!selectedItemDetails}
                title={hasMySellOrder
                  ? "Edit your existing sell order"
                  : "Create Sell Order"}>{hasMySellOrder ? 'Edit Sell' : 'Sell'}</button
              >
              {#if currentUser?.grants?.includes('market.bulk') && selectedItemDetails}
                <button
                  class="action-btn bulk-trade-btn"
                  on:click={() => showBulkTradeDialog = true}
                  title="Open bulk trade matching"
                >Bulk Trade</button>
              {/if}
              {#if $tradeList.length > 0}
                <span class="actions-divider"></span>
                <button class="action-btn trade-list-btn" title="Trade List" on:click={() => { showMyOrders.set(false); showInventory.set(false); showTradeList.set(true); }}>
                  Trade List ({$tradeList.length})
                </button>
              {/if}
            {:else}
              <button class="auth-hint-btn" on:click={openAuthDialog}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <span>{needsAuth ? 'Log in to post Orders' : 'Verify to post Orders'}</span>
              </button>
            {/if}
          </div>
        </div>
        <div class="detail-title">
          <button
            class="action-btn back-btn"
            on:click={handleBackToOverview}
            title="Back to list"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            <span class="back-text">Back</span>
          </button>
          <button
            class="favourite-star"
            class:active={isCurrentFavourited}
            on:click={handleToggleFavourite}
            title={isCurrentFavourited ? 'Remove from favourites' : 'Add to favourites'}
          >{isCurrentFavourited ? '\u2605' : '\u2606'}</button>
          <!-- svelte-ignore a11y-missing-content -->
          <a
            class="detail-title-name"
            href={getItemLink(selectedItemDetails || selectedItem)}
            target="_blank"
            rel="noopener"
            title={selectedItem?.n || ""}
          >{selectedItem?.n || ""}{@html itemTypeBadge(selectedItem?.t)}</a>
          {#if selectedItemDetails && !hasCondition(selectedItemDetails) && getMaxTT(selectedItemDetails) != null}
            <span class="detail-tt-badge">{formatPedValue(getMaxTT(selectedItemDetails))}</span>
          {/if}
          <!-- Title-row controls: filter btn + history controls (mobile: same row as title) -->
          <div class="detail-title-controls">
            {#if hasDetailFilters || isGenderedDetail}
              <button
                class="detail-filter-btn"
                class:has-active={hasActiveDetailFilters}
                on:click={() => showFilterDialog = !showFilterDialog}
                title="Filters"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
                </svg>
              </button>
            {/if}
            <div class="history-controls">
              <select
                class="filter-select period-select"
                bind:value={selectedPeriod}
                title="Price history period"
              >
                {#each PRICE_PERIODS as p}
                  <option value={p.value}>{p.label}</option>
                {/each}
              </select>
              <button
                class="action-btn chart-toggle-btn"
                class:active={showPriceHistory}
                on:click={togglePriceHistory}
                title={showPriceHistory ? "Show order book" : "Show price history"}
              >{showPriceHistory ? "Orders" : "Chart"}</button>
            </div>
          </div>
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div class="detail-filters" class:open={showFilterDialog} on:click|self={() => showFilterDialog = false}>
            <div class="detail-filters-content">
              <div class="detail-filters-header">
                <span>Filters</span>
                <button class="detail-filters-close" on:click={() => showFilterDialog = false}>&times;</button>
              </div>
              {#if isGenderedDetail}
                <div class="dialog-gender-toggle">
                  <span class="dialog-filter-label">Gender</span>
                  <div class="gender-toggle">
                    <button class="gender-btn" class:active={priceGender === 'Male'} on:click={() => priceGender = 'Male'}>M</button>
                    <button class="gender-btn" class:active={priceGender === 'Both'} on:click={() => priceGender = 'Both'}>M+F</button>
                    <button class="gender-btn" class:active={priceGender === 'Female'} on:click={() => priceGender = 'Female'}>F</button>
                  </div>
                </div>
              {/if}
              {#if isTierableDetail && !isLimitedDetail}
                <RangeSlider min={0} max={10} bind:valueMin={tierMin} bind:valueMax={tierMax} label="Tier" compact />
              {/if}
              {#if isTierableDetail}
                <RangeSlider min={0} max={tirRangeMax} step={10} bind:valueMin={tirMin} bind:valueMax={tirMax} label="TiR" compact />
              {/if}
              {#if isBlueprintDetail && !isLimitedDetail}
                <RangeSlider min={0} max={100} bind:valueMin={qrMin} bind:valueMax={qrMax} label="QR" compact />
              {/if}
              {#if detailItemStackable}
                <div class="min-tt-group">
                  <span class="filter-hint">Min TT</span>
                  <input
                    type="number"
                    class="filter-input-small"
                    placeholder="Min TT"
                    min="0"
                    step="0.01"
                    bind:value={minTTFilter}
                    title="Minimum total TT value to show"
                  />
                </div>
              {/if}
              {#if detailHasCondition}
                <div class="condition-filter">
                  <label class="condition-label">Cond: <strong style="display:inline-block;min-width:4ch;text-align:right">{minConditionPct}%</strong></label>
                  <input
                    type="range"
                    class="condition-slider"
                    min="0"
                    max="100"
                    step="1"
                    bind:value={minConditionPct}
                    title="Minimum condition %"
                  />
                </div>
              {/if}
            </div>
          </div>
          <div class="detail-title-right">
            {#if isGenderedDetail}
              <div class="gender-toggle desktop-only-gender">
                <button class="gender-btn" class:active={priceGender === 'Male'} on:click={() => priceGender = 'Male'}>M</button>
                <button class="gender-btn" class:active={priceGender === 'Both'} on:click={() => priceGender = 'Both'}>M+F</button>
                <button class="gender-btn" class:active={priceGender === 'Female'} on:click={() => priceGender = 'Female'}>F</button>
              </div>
            {/if}
            <div class="metric">
              Median:<br /><span class="metric-value"
                >{periodStats?.median != null
                  ? formatMarkupDisplay(periodStats.median, detailIsAbsoluteMarkup)
                  : (typeof selectedItem?.m === "number" && !(isGenderedDetail && priceGender === 'Both') ? formatMarkupDisplay(selectedItem.m, detailIsAbsoluteMarkup) : "\u2014")}</span
              >
            </div>
            <div class="metric">
              10%:<br /><span class="metric-value"
                >{periodStats?.p10 != null
                  ? formatMarkupDisplay(periodStats.p10, detailIsAbsoluteMarkup)
                  : (typeof selectedItem?.p === "number" && !(isGenderedDetail && priceGender === 'Both') ? formatMarkupDisplay(selectedItem.p, detailIsAbsoluteMarkup) : "\u2014")}</span
              >
            </div>
            <div class="metric">
              Weighted Avg:<br /><span class="metric-value"
                >{periodStats?.wap != null
                  ? formatMarkupDisplay(periodStats.wap, detailIsAbsoluteMarkup)
                  : (typeof selectedItem?.w === "number" && !(isGenderedDetail && priceGender === 'Both') ? formatMarkupDisplay(selectedItem.w, detailIsAbsoluteMarkup) : "\u2014")}</span
              >
            </div>
            {#if exchangePrices?.buy}
              <div class="metric exchange-metric">
                Best Buy:<br /><span class="metric-value buy-value">{formatMarkupDisplay(exchangePrices.buy.best_markup, detailIsAbsoluteMarkup)}</span>
              </div>
            {/if}
            {#if exchangePrices?.sell}
              <div class="metric exchange-metric">
                Best Sell:<br /><span class="metric-value sell-value">{formatMarkupDisplay(exchangePrices.sell.best_markup, detailIsAbsoluteMarkup)}</span>
              </div>
            {/if}
            <div class="history-controls desktop-only-history">
              <select
                class="filter-select period-select"
                bind:value={selectedPeriod}
                title="Price history period"
              >
                {#each PRICE_PERIODS as p}
                  <option value={p.value}>{p.label}</option>
                {/each}
              </select>
              <button
                class="action-btn chart-toggle-btn"
                class:active={showPriceHistory}
                on:click={togglePriceHistory}
                title={showPriceHistory ? "Show order book" : "Show price history"}
              >{showPriceHistory ? "Orders" : "Chart"}</button>
            </div>
          </div>
        </div>

        {#if showPriceHistory}
          <div class="detail-wrapper chart-view">
            <PriceHistoryChart
              itemId={selectedItem?.i}
              period={selectedPeriod}
              isAbsoluteMarkup={detailIsAbsoluteMarkup}
              data={priceHistoryData}
              loading={priceHistoryLoading}
            />
          </div>
        {:else}
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div class="detail-wrapper" class:single-table={tableMode !== 'both'} on:click|capture={handleDetailClick}>
            {#if tableMode !== "buy"}
              <div class="detail-table sell">
                <span class="table-label sell">Sell{ordersLoading ? "..." : ""}</span>
                <FancyTable
                  columns={sellDetailColumns}
                  data={filteredSellOrders}
                  rowHeight={30}
                  compact={true}
                  sortable={true}
                  searchable={false}
                  emptyMessage="No sell orders"
                  rowClass={(row) => currentUser && String(getSellerId(row)) === String(currentUser.id) ? 'my-order' : null}
                />
              </div>
            {/if}
            {#if tableMode !== "sell"}
              <div class="detail-table buy">
                <span class="table-label buy">Buy{ordersLoading ? "..." : ""}</span>
                <FancyTable
                  columns={buyDetailColumns}
                  data={filteredBuyOrders}
                  rowHeight={30}
                  compact={true}
                  sortable={true}
                  searchable={false}
                  emptyMessage="No buy orders"
                  rowClass={(row) => currentUser && String(getSellerId(row)) === String(currentUser.id) ? 'my-order' : null}
                />
              </div>
            {/if}
            {#if initialLoading}
              <div class="overlay">
                <div class="loader">Loading exchange…</div>
              </div>
            {/if}
          </div>
        {/if}

      {/if}

      <QuickTradeDialog
        bind:this={quickTradeRef}
        show={showQuickTrade}
        order={quickTradeOrder}
        side={quickTradeSide}
        item={quickTradeItem || selectedItemDetails || selectedItem}
        showAddToList={showUserOrders}
        on:close={closeQuickTrade}
        on:confirm={handleQuickTradeConfirm}
        on:addToList={handleAddToListFromDialog}
        on:editOwn={(e) => { closeQuickTrade(); editOrderInline(e.detail.order); }}
      />

      <OrderDialog
        bind:this={orderDialogRef}
        show={showOrderDialog}
        existingOrderCount={orderDialogExistingCount}
        isNonFungible={orderDialogIsNonFungible}
        submitting={submittingOrder}
        itemGender={orderDialogGender}
        on:close={closeOrderDialog}
        on:submit={onSubmitOrder}
        on:next={onNextOrder}
        on:delete={handleDeleteOrder}
      />

      <BulkTradeDialog
        show={showBulkTradeDialog}
        itemName={selectedItemDetails?.Name || selectedItem?.n || ''}
        item={selectedItemDetails || selectedItem}
        orderBookOrders={[...(buyOrders || []), ...(sellOrders || [])]}
        on:close={() => showBulkTradeDialog = false}
        on:bulkSubmit={handleBulkSubmit}
      />
    </div>

    {#if showUserOrders || (canPostOrders && ($showMyOrders || $showInventory || $showTrades))}
      <div class="floating-panel">
        {#if showUserOrders}
          <div class="panel-title-bar">
            <button class="back-btn" on:click={closeUserOrdersPanel}>Back</button>
            <span class="panel-title-text">{userOrdersTarget?.name || 'User'}</span>
            <div class="panel-header-actions">
              <div class="order-side-toggle">
                <button class="order-side-btn" class:active={panelSideFilter === 'all'} on:click={() => panelSideFilter = 'all'}>All</button>
                <button class="order-side-btn" class:active={panelSideFilter === 'SELL'} on:click={() => panelSideFilter = 'SELL'}>Sell</button>
                <button class="order-side-btn" class:active={panelSideFilter === 'BUY'} on:click={() => panelSideFilter = 'BUY'}>Buy</button>
              </div>
              {#if canPostOrders}
                <button
                  class="panel-action-btn"
                  class:accent={$tradeList.length > 0}
                  on:click={() => {
                    if ($tradeList.length > 0) {
                      showTradeList.set(!$showTradeList);
                    } else {
                      showTradeList.set(!$showTradeList);
                    }
                  }}
                >
                  Trade List{$tradeList.length > 0 ? ` (${$tradeList.length})` : ''}
                </button>
              {/if}
            </div>
          </div>
          {#if $showTradeList}
            {#if $tradeList.length > 0}
              <CartSummary {allItems} on:close={() => showTradeList.set(false)} />
            {:else}
              <div class="trade-list-empty-state">
                <p>Your trade list is empty.</p>
                <p class="trade-list-hint">Click <strong>Buy</strong> or <strong>Sell</strong> on any order to add items. This lets you buy multiple items from this user in a single trade request.</p>
                <button class="trade-list-back-btn" on:click={() => showTradeList.set(false)}>Back to Orders</button>
              </div>
            {/if}
          {:else}
            <div class="detail-wrapper" class:single-table={panelSideFilter !== 'all'}>
              {#if panelSideFilter !== 'BUY'}
                <div class="detail-table sell">
                  <span class="table-label sell">Sell</span>
                  <UserOrdersPanel user={userOrdersTarget} sideFilter="SELL" canTrade={canPostOrders} {allItems} on:orderAction={handleOrderAction} />
                </div>
              {/if}
              {#if panelSideFilter !== 'SELL'}
                <div class="detail-table buy">
                  <span class="table-label buy">Buy</span>
                  <UserOrdersPanel user={userOrdersTarget} sideFilter="BUY" canTrade={canPostOrders} {allItems} on:orderAction={handleOrderAction} />
                </div>
              {/if}
            </div>
          {/if}
        {:else}
          <div class="panel-title-bar">
            <button class="back-btn" on:click={closeFloatingPanel}>Back</button>
            <div class="panel-tabs">
              <button class="panel-tab" class:active={$showMyOrders} on:click={() => {
                const userName = currentUser?.eu_name;
                goto(userName ? `/market/exchange/orders/${encodeURIComponentSafe(userName)}` : '/market/exchange/orders');
              }}>My Orders</button>
              <button class="panel-tab" class:active={$showInventory} on:click={() => goto('/market/exchange/inventory')}>Inventory</button>
              <button class="panel-tab" class:active={$showTrades} on:click={() => goto('/market/exchange/trades')}>Trades</button>
            </div>
            <div class="panel-header-actions">
              {#if $showMyOrders}
                <div class="order-side-toggle">
                  <button class="order-side-btn" class:active={panelSideFilter === 'all'} on:click={() => panelSideFilter = 'all'}>All</button>
                  <button class="order-side-btn" class:active={panelSideFilter === 'SELL'} on:click={() => panelSideFilter = 'SELL'}>Sell</button>
                  <button class="order-side-btn" class:active={panelSideFilter === 'BUY'} on:click={() => panelSideFilter = 'BUY'}>Buy</button>
                </div>
                <button class="panel-action-btn accent" disabled={bumpingAll || bumpCooldownRemaining > 0} on:click={() => {
                  async function doBump(token) {
                    bumpingAll = true;
                    const cooldown = await myOrdersRef?.bumpAll(token);
                    bumpingAll = false;
                    if (cooldown != null) startBumpCooldown(cooldown);
                  }
                  if (env.PUBLIC_TURNSTILE_SITE_KEY) {
                    requestTurnstile('bump', doBump);
                  } else {
                    doBump();
                  }
                }}>{bumpingAll ? 'Bumping...' : bumpCooldownRemaining > 0 ? `Bump All (${formatCooldown(bumpCooldownRemaining)})` : 'Bump All'}</button>
              {/if}
              {#if $showInventory}
                <button class="panel-action-btn" class:mass-sell={!massSellMode} class:mass-sell-cancel={massSellMode} on:click={toggleMassSellMode}>{massSellMode ? 'Cancel' : 'Mass Sell'}</button>
                <button class="panel-action-btn accent" on:click={() => { showImportDialog = true; }}>Import</button>
                {#if discrepancyCount > 0}
                  <button class="panel-action-btn warn" on:click={() => { showAdjustDialog = true; }}>Adjust ({discrepancyCount})</button>
                {/if}
              {/if}
              <button class="panel-action-btn" on:click={refreshFloatingPanel}>Refresh</button>
            </div>
          </div>

          {#if $showMyOrders}
            <MyOrdersView
              bind:this={myOrdersRef}
              user={currentUser}
              sideFilter={panelSideFilter}
              {allItems}
              on:edit={(e) => {
                const order = e.detail;
                if (order?.item_id) {
                  editOrderInline(order);
                }
              }}
              on:close={(e) => {
                const order = e.detail;
                if (!order?.id) return;
                if (env.PUBLIC_TURNSTILE_SITE_KEY) {
                  requestTurnstile('close', async (token) => {
                    try {
                      const res = await fetch(`/api/market/exchange/orders/${order.id}`, {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ turnstile_token: token })
                      });
                      const data = await res.json();
                      if (!res.ok) throw new Error(data.error || 'Close failed');
                      upsertOrder(data);
                    } catch (err) {
                      addToast(err.message);
                    }
                  }, order);
                } else {
                  (async () => {
                    try {
                      const res = await fetch(`/api/market/exchange/orders/${order.id}`, { method: 'DELETE' });
                      const data = await res.json();
                      if (!res.ok) throw new Error(data.error || 'Close failed');
                      upsertOrder(data);
                    } catch (err) {
                      addToast(err.message);
                    }
                  })();
                }
              }}
            />
          {:else if $showInventory}
            <InventoryPanel
              bind:this={inventoryPanelRef}
              user={currentUser}
              {allItems}
              on:sell={handleInventorySell}
              on:massSell={handleMassSell}
            />
          {:else if $showTrades}
            <TradeRequestsPanel
              bind:this={tradesPanelRef}
              user={currentUser}
            />
          {/if}
        {/if}
      </div>
    {/if}
  </div>
</div>

<InventoryImportDialog
  show={showImportDialog}
  {allItems}
  on:close={() => { showImportDialog = false; }}
  on:imported={() => {
    // Refresh inventory panel — dialog stays open to show results
    if ($showInventory && inventoryPanelRef) {
      inventoryPanelRef.refresh();
    }
  }}
/>

<OrderAdjustDialog
  show={showAdjustDialog}
  on:close={() => { showAdjustDialog = false; }}
/>

<MassSellDialog
  show={showMassSellDialog}
  items={massSellItems}
  {allItems}
  sellOrderCount={currentSellCount}
  on:close={() => { showMassSellDialog = false; }}
  on:complete={handleMassSellComplete}
/>

{#if pendingTurnstileAction}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="turnstile-modal-overlay" on:click={cancelTurnstileModal}>
    <div class="turnstile-modal" on:click|stopPropagation>
      <h3 class="turnstile-modal-title">
        {pendingTurnstileAction.type === 'bump' ? 'Bump All Orders' : 'Close Order'}
      </h3>
      <p class="turnstile-modal-desc">Please complete the verification to continue.</p>
      <TurnstileWidget
        siteKey={env.PUBLIC_TURNSTILE_SITE_KEY}
        bind:token={turnstileModalToken}
        bind:reset={resetTurnstileModal}
      />
      <div class="turnstile-modal-actions">
        <button class="btn-cancel" on:click={cancelTurnstileModal}>Cancel</button>
        <button class="btn-confirm" disabled={!turnstileModalToken} on:click={executeTurnstileAction}>
          {pendingTurnstileAction.type === 'bump' ? 'Bump All' : 'Close Order'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if showAuthDialog}
  <div class="auth-dialog-overlay" on:click={closeAuthDialog} on:keydown={(e) => e.key === 'Escape' && closeAuthDialog()}>
    <div class="auth-dialog-content" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="auth-dialog-title">
      <button class="auth-dialog-close" on:click={closeAuthDialog} aria-label="Close">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>

      <h2 id="auth-dialog-title" class="auth-dialog-title">
        {needsAuth ? 'Login Required' : 'Verification Required'}
      </h2>

      {#if needsAuth}
        <div class="auth-dialog-body">
          <p>To post buy and sell orders on the exchange, you need to log in and verify your account.</p>

          <div class="auth-steps">
            <div class="auth-step">
              <span class="step-number">1</span>
              <div class="step-content">
                <strong>Login with Discord</strong>
                <p>Click the button below to log in using your Discord account.</p>
              </div>
            </div>

            <div class="auth-step">
              <span class="step-number">2</span>
              <div class="step-content">
                <strong>Join our Discord Server</strong>
                <p>After logging in, join the Entropia Nexus Discord server if you haven't already.</p>
              </div>
            </div>

            <div class="auth-step">
              <span class="step-number">3</span>
              <div class="step-content">
                <strong>Complete Verification</strong>
                <p>A verification thread will automatically open (may take up to 5 minutes). Follow the instructions to verify your Entropia Universe character.</p>
              </div>
            </div>
          </div>

          <div class="auth-dialog-actions">
            <a href={loginUrl} class="auth-dialog-btn primary">Login with Discord</a>
            <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener" class="auth-dialog-btn secondary">Join Discord Server</a>
          </div>
        </div>
      {:else}
        <div class="auth-dialog-body">
          <p>Your account needs to be verified before you can post orders on the exchange.</p>

          <div class="auth-steps">
            <div class="auth-step">
              <span class="step-number">1</span>
              <div class="step-content">
                <strong>Join our Discord Server</strong>
                <p>Make sure you've joined the Entropia Nexus Discord server.</p>
              </div>
            </div>

            <div class="auth-step">
              <span class="step-number">2</span>
              <div class="step-content">
                <strong>Wait for Verification Thread</strong>
                <p>A verification thread will automatically open in your Discord DMs or in a private channel. This may take up to 5 minutes after joining.</p>
              </div>
            </div>

            <div class="auth-step">
              <span class="step-number">3</span>
              <div class="step-content">
                <strong>Follow Verification Instructions</strong>
                <p>Respond to the verification thread with the requested information about your Entropia Universe character.</p>
              </div>
            </div>
          </div>

          <div class="auth-dialog-actions">
            <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener" class="auth-dialog-btn primary">Join Discord Server</a>
            <button class="auth-dialog-btn secondary" on:click={closeAuthDialog}>Close</button>
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .exchange-browser {
    padding: 12px;
    width: 100%;
    box-sizing: border-box;
    height: 100%;
  }

  .search-input {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 13px;
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    flex: 1 1 auto;
    min-width: 160px;
    transition: border-color 0.2s ease;
  }
  .search-input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .content {
    display: flex;
    gap: 0;
    width: 100%;
    height: 100%;
    box-sizing: border-box;
    min-height: 0;
    position: relative;
  }

  .floating-panel {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: calc(100% - 308px); /* account for sidebar */
    z-index: 15;
    display: flex;
    flex-direction: column;
  }

  .panel-title-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 8px 16px;
    flex-shrink: 0;
  }
  .panel-title-bar .back-btn {
    display: inline-flex;
    align-items: center;
    padding: 6px 14px;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    cursor: pointer;
    border-radius: 6px;
    font-size: 13px;
    transition: all 0.2s ease;
  }
  .panel-title-bar .back-btn:hover { background: var(--hover-color); border-color: var(--border-hover); }
  .panel-title-text {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
    flex: 1;
  }

  .trade-list-empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 2rem;
    text-align: center;
    color: var(--text-muted);
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 13px;
    margin-top: 8px;
  }
  .trade-list-empty-state p { margin: 0; }
  .trade-list-hint {
    font-size: 12px;
    max-width: 300px;
    line-height: 1.5;
  }
  .trade-list-back-btn {
    padding: 6px 14px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-color);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s ease;
    margin-top: 4px;
  }
  .trade-list-back-btn:hover {
    background: var(--hover-color);
    border-color: var(--border-hover);
  }
  .panel-tabs {
    display: flex;
    gap: 2px;
    background: var(--bg-color, rgba(0,0,0,0.05));
    border-radius: 6px;
    padding: 2px;
  }
  .panel-tab {
    padding: 5px 14px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.15s ease;
  }
  .panel-tab:hover {
    color: var(--text-color);
    background: var(--hover-color);
  }
  .panel-tab.active {
    color: var(--text-color);
    background: var(--secondary-color);
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }

  .panel-header-actions {
    display: flex;
    gap: 6px;
    margin-left: auto;
  }
  .panel-action-btn {
    padding: 6px 14px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-color);
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s ease;
  }
  .panel-action-btn:hover { background: var(--hover-color); border-color: var(--border-hover); }
  .panel-action-btn.accent {
    color: var(--accent-color);
    border-color: var(--accent-color);
  }
  .panel-action-btn.accent:hover {
    background: rgba(59, 130, 246, 0.1);
  }
  .panel-action-btn.warn {
    color: var(--warning-color, #f59e0b);
    border-color: var(--warning-color, #f59e0b);
  }
  .panel-action-btn.warn:hover {
    background: rgba(245, 158, 11, 0.1);
  }
  .panel-action-btn.mass-sell {
    color: var(--success-color);
    border-color: var(--success-color);
  }
  .panel-action-btn.mass-sell:hover {
    background: rgba(52, 199, 89, 0.1);
  }
  .panel-action-btn.mass-sell-cancel {
    color: var(--error-color);
    border-color: var(--error-color);
  }
  .panel-action-btn.mass-sell-cancel:hover {
    background: rgba(239, 68, 68, 0.1);
  }

  .sidebar {
    flex: 0 0 300px;
    display: flex;
    flex-direction: column;
    background: var(--secondary-color);
    padding: 16px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    height: 100%;
    margin: 0 8px 0 0;
    box-sizing: border-box;
    min-height: 0;
  }

  .sidebar-title {
    color: var(--text-color);
    text-align: center;
    margin: 0 0 12px 0;
    font-size: 22px;
    font-weight: 700;
    line-height: 1.3;
    padding-bottom: 12px;
    border-bottom: 2px solid var(--accent-color);
  }
  .beta-badge {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 2px 8px;
    border-radius: 4px;
    background: var(--accent-color);
    color: #fff;
    vertical-align: middle;
    position: relative;
    top: -2px;
  }

  .sidebar h3 {
    margin: 0;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  .sidebar-tabs {
    display: flex;
    gap: 0;
    margin-bottom: 10px;
    border-bottom: 1px solid var(--border-color);
  }

  .sidebar-tab {
    flex: 1;
    padding: 6px 0;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .sidebar-tab:hover {
    color: var(--text-color);
  }
  .sidebar-tab.active {
    color: var(--accent-color);
    border-bottom-color: var(--accent-color);
  }

  .favourites-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .new-folder-header-btn {
    padding: 2px 8px;
    font-size: 11px;
    border: 1px dashed var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .new-folder-header-btn:hover {
    border-color: var(--accent-color);
    color: var(--accent-color);
    background: rgba(59, 130, 246, 0.05);
  }

  .category-scroll {
    flex: 1 1 auto;
    overflow: auto;
    min-height: 0;
  }

  .main-content {
    flex: 1;
    min-width: 0;
    min-height: 0;
    position: relative;
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .filters {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    flex-wrap: wrap;
  }

  .filter-search-row {
    display: contents;
  }
  .filter-dropdowns {
    display: contents;
  }
  .filter-actions {
    display: contents;
  }
  .actions-right {
    margin-left: auto;
    display: flex;
    gap: 6px;
    flex: 1 0 auto;
    justify-content: flex-end;
  }

  .filter-select {
    padding: 7px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    font-size: 13px;
    transition: border-color 0.2s ease;
  }
  .filter-select:focus {
    border-color: var(--accent-color);
    outline: none;
  }
  .filter-input-small {
    padding: 7px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    font-size: 13px;
    width: 80px;
    flex-shrink: 0;
    transition: border-color 0.2s ease;
  }
  .filter-input-small:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .min-tt-group {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }
  .filter-hint {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .action-btn {
    padding: 7px 14px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: transparent;
    color: var(--text-color);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s ease;
  }
  .action-btn:hover:not(:disabled) {
    background-color: var(--hover-color);
    border-color: var(--border-hover);
  }
  .action-btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  /* Colored Buy/Sell action buttons in detail view */
  .action-btn.buy-btn {
    color: var(--success-color, #16a34a);
    border-color: var(--success-color, #16a34a);
  }
  .action-btn.buy-btn:hover:not(:disabled) {
    background: rgba(22, 163, 106, 0.1);
  }
  .action-btn.sell-btn {
    color: var(--error-color, #ef4444);
    border-color: var(--error-color, #ef4444);
  }
  .action-btn.sell-btn:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.1);
  }

  /* Accent-outlined user action buttons */
  .action-btn.accent-btn {
    color: var(--accent-color);
    border-color: var(--accent-color);
  }
  .action-btn.accent-btn:hover:not(:disabled) {
    background: rgba(59, 130, 246, 0.1);
  }

  .action-btn.bulk-trade-btn {
    color: var(--accent-color);
    border-color: var(--accent-color);
  }
  .action-btn.bulk-trade-btn:hover:not(:disabled) {
    background: rgba(59, 130, 246, 0.1);
  }
  .trade-list-btn {
    color: var(--accent-color) !important;
    border-color: var(--accent-color) !important;
  }
  .actions-divider {
    width: 1px;
    height: 20px;
    background: var(--border-color);
    flex-shrink: 0;
  }

  .table-wrapper {
    display: flex;
    overflow: hidden;
    width: 100%;
    margin: 8px 0 0 0;
    box-sizing: border-box;
    position: relative;
    flex: 1 1 0;
    min-height: 0;
    flex-direction: column;
  }
  .table-wrapper :global(.table-body) {
    overflow-y: scroll;
  }


  /* Center content in action columns */
  :global(.cell-center) {
    justify-content: center;
  }

  /* Split cell: left value / right value with fixed separator */
  :global(.split-cell) {
    display: inline-flex;
    width: 100%;
  }
  :global(.split-l) {
    flex: 1;
    text-align: right;
  }
  :global(.split-sep) {
    width: 14px;
    text-align: center;
    opacity: 0.4;
    flex-shrink: 0;
  }
  :global(.split-r) {
    flex: 1;
    text-align: left;
  }

  /* Action buttons inside last two columns */
  :global(.table-wrapper a) {
    text-decoration: none;
    display: block;
    width: 100%;
    height: 100%;
  }
  :global(.cell-button) {
    padding: 2px 6px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-color);
    font-size: 11px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s ease;
  }
  :global(.trade-btn) {
    font-weight: 500;
  }
  :global(.buy-trade-btn) {
    color: var(--success-color, #16a34a);
    border-color: var(--success-color, #16a34a);
  }
  :global(.buy-trade-btn:hover) {
    background: rgba(22, 163, 74, 0.15);
  }
  :global(.sell-trade-btn) {
    color: var(--error-color, #ef4444);
    border-color: var(--error-color, #ef4444);
  }
  :global(.sell-trade-btn:hover) {
    background: rgba(239, 68, 68, 0.15);
  }
  :global(.edit-trade-btn) {
    color: var(--accent-color);
    border-color: var(--accent-color);
  }
  :global(.edit-trade-btn:hover) {
    background: rgba(59, 130, 246, 0.15);
  }
  :global(.seller-link) {
    cursor: pointer;
    color: var(--accent-color);
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: block;
  }
  :global(.seller-link:hover) {
    text-decoration: underline;
  }
  :global(.tt-pct) {
    color: var(--text-muted);
    font-size: 0.9em;
  }
  :global(.badge-set-yes) {
    background: var(--accent-color);
    color: #fff;
    font-weight: 600;
  }
  :global(.detail-tags) {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    align-items: center;
  }
  :global(.detail-tag) {
    font-size: 11px;
    padding: 2px 5px;
    border-radius: 3px;
    background: var(--accent-color-bg);
    color: var(--accent-color);
    white-space: nowrap;
  }

  .empty-state,
  .welcome-state {
    text-align: center;
    padding: 3rem 2rem;
    color: var(--text-muted);
  }

  .welcome-state {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin: 8px 0 0 0;
    padding: 3rem 2rem;
  }

  .welcome-state h3 {
    color: var(--text-color);
    margin: 0 0 8px 0;
    font-size: 18px;
    font-weight: 600;
  }

  .welcome-state p {
    margin: 0;
    font-size: 14px;
    line-height: 1.5;
  }

  .overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.15);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 2;
    border-radius: 8px;
  }

  .loader {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 18px;
    border: 1px solid var(--border-color);
    background-color: var(--secondary-color);
    color: var(--text-color);
    border-radius: 8px;
    font-size: 13px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }
  .loader::before {
    content: '';
    width: 16px;
    height: 16px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .detail-wrapper {
    display: grid;
    grid-template-rows: 1fr 1fr;
    gap: 8px;
    overflow: hidden;
    width: 100%;
    margin: 8px 0 0 0;
    box-sizing: border-box;
    flex: 1 1 0;
    min-height: 0;
  }
  .detail-wrapper.single-table {
    grid-template-rows: 1fr;
  }
  .detail-wrapper.chart-view {
    display: flex;
    flex-direction: column;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 12px;
  }

  .detail-table {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    position: relative;
  }
  .detail-table.sell {
    border-top: 2px solid var(--error-color, #ef4444);
  }
  .detail-table.buy {
    border-top: 2px solid var(--success-color, #16a34a);
  }

  .table-label {
    position: absolute;
    top: 0;
    right: 12px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 2px 8px;
    border-radius: 0 0 4px 4px;
    z-index: 11;
    pointer-events: none;
  }
  .table-label.sell {
    background: var(--error-color, #ef4444);
    color: white;
  }
  .table-label.buy {
    background: var(--success-color, #16a34a);
    color: white;
  }

  .detail-table :global(.my-order) {
    background-color: var(--hover-color) !important;
    box-shadow: inset 2px 0 0 var(--accent-color);
  }

  .detail-table :global(table) {
    height: 100%;
  }

  .detail-title {
    display: flex;
    align-items: stretch;
    gap: 12px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 10px 16px;
    margin: 8px 0 0 0;
    min-width: 0;
    flex-wrap: wrap;
  }

  .favourite-star {
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
    color: var(--text-muted);
    padding: 2px 4px;
    line-height: 1;
    flex-shrink: 0;
    transition: color 0.15s ease;
    display: flex;
    align-items: center;
  }
  .favourite-star:hover {
    color: var(--warning-color, #f59e0b);
  }
  .favourite-star.active {
    color: var(--warning-color, #f59e0b);
  }

  .detail-title-name {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-weight: 700;
    padding: 0 4px;
    font-size: 18px;
    line-height: 1.3;
    color: var(--text-color);
    text-decoration: none;
    display: flex;
    align-items: center;
  }
  a.detail-title-name:hover {
    color: var(--accent-color);
    text-decoration: underline;
  }

  .detail-tt-badge {
    flex-shrink: 0;
    background: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    white-space: nowrap;
    display: flex;
    align-items: center;
  }

  .detail-title-right {
    margin-left: auto;
    display: flex;
    align-items: stretch;
    gap: 8px;
    flex-wrap: wrap;
    flex: 0 0 auto;
    max-width: 100%;
  }

  /* Title controls: hidden on desktop (duplicate controls live in .detail-title-right) */
  .detail-title-controls {
    display: none;
  }
  .desktop-only-gender,
  .desktop-only-history {
    display: flex;
  }
  .dialog-gender-toggle {
    display: none;
  }
  .dialog-filter-label {
    font-size: 13px;
    color: var(--text-muted);
    font-weight: 500;
  }

  .condition-filter {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 0 0 auto;
  }
  .condition-label {
    font-size: 0.8rem;
    color: var(--text-muted);
    white-space: nowrap;
  }
  .condition-label strong {
    color: var(--text-color);
  }
  .condition-slider {
    width: 100px;
    accent-color: var(--accent-color);
    cursor: pointer;
  }

  /* Back button with icon */
  .back-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding-left: 8px;
  }
  .back-btn svg {
    flex-shrink: 0;
  }

  /* Filter button: hidden on desktop, shown on mobile */
  .detail-filter-btn {
    display: none;
  }

  /* Filter container: inline on desktop */
  .detail-filters {
    display: contents;
  }
  .detail-filters-content {
    display: contents;
  }
  .detail-filters-header {
    display: none;
  }

  /* Metric mini-cards — inline by default for compact title bar */
  .detail-title-right .metric {
    flex: 0 1 auto;
    min-width: 0;
    background: var(--hover-color);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.4;
    text-align: left;
    display: flex;
    flex-direction: row;
    gap: 3px;
    align-items: center;
    white-space: nowrap;
  }
  .detail-title-right .metric br {
    display: none;
  }

  .detail-title-right .action-btn {
    flex: 0 0 auto;
    white-space: nowrap;
  }

  .metric .metric-value {
    font-weight: 700;
    color: var(--text-color);
    font-size: 12px;
    display: inline;
  }
  
  .exchange-metric .buy-value {
    color: var(--success-color, #16a34a);
  }
  .exchange-metric .sell-value {
    color: var(--error-color, #ef4444);
  }

  .history-controls {
    display: flex;
    flex-direction: row;
    gap: 4px;
    flex-shrink: 0;
    align-items: stretch;
  }

  .period-select {
    width: auto;
    min-width: 55px;
    padding: 3px 6px;
    font-size: 12px;
  }

  .chart-toggle-btn {
    min-width: 56px;
    padding: 3px 8px;
    font-size: 12px;
  }
  .chart-toggle-btn.active {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .untradeable-notice {
    font-size: 12px;
    color: var(--warning-color, #f59e0b);
    font-style: italic;
  }

  .gender-toggle {
    display: flex;
    gap: 0;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
    align-self: stretch;
  }
  .gender-btn {
    padding: 4px 0;
    width: 36px;
    text-align: center;
    font-size: 12px;
    font-weight: 600;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .gender-btn:not(:last-child) {
    border-right: 1px solid var(--border-color);
  }
  .gender-btn.active {
    background: var(--accent-color);
    color: white;
  }
  .gender-btn:hover:not(.active) {
    background: var(--hover-color);
  }

  .order-side-toggle {
    display: flex;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
    align-self: stretch;
  }
  .order-side-btn {
    padding: 6px 0;
    width: 36px;
    text-align: center;
    font-size: 12px;
    font-weight: 600;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .order-side-btn:not(:last-child) {
    border-right: 1px solid var(--border-color);
  }
  .order-side-btn.active {
    background: var(--accent-color);
    color: white;
  }
  .order-side-btn:hover:not(.active) {
    background: var(--hover-color);
  }

  /* Mobile sidebar toggle */
  .mobile-category-toggle {
    display: none;
    padding: 7px 14px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-color);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .mobile-category-toggle:hover {
    background: var(--hover-color);
  }

  /* Mobile overlay for sidebar */
  .sidebar-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 99;
  }

  @media (max-width: 900px) {
    .exchange-browser {
      padding: 8px;
    }
    .sidebar {
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      bottom: 0;
      z-index: 100;
      width: 280px;
      max-width: 85vw;
      margin: 0;
      border-radius: 0 8px 8px 0;
      height: 100%;
      box-shadow: 4px 0 20px rgba(0, 0, 0, 0.3);
    }
    .sidebar.mobile-open {
      display: flex;
    }
    .sidebar-overlay.visible {
      display: block;
    }
    .mobile-category-toggle {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }
    .filter-search-row {
      display: flex;
      flex: 1 1 100%;
      gap: 8px;
      align-items: center;
    }
    .filter-search-row .search-input {
      flex: 1 1 auto;
      min-width: 0;
    }
    .filter-dropdowns {
      display: flex;
      flex: 1 1 100%;
      gap: 8px;
    }
    .filter-dropdowns .filter-select {
      flex: 1 1 0;
      min-width: 0;
    }
    .filter-actions {
      display: flex;
      flex: 1 1 100%;
      align-items: center;
      gap: 8px;
    }
    .filter-actions .actions-right {
      flex: 1 0 auto;
      margin-left: auto;
    }
    .floating-panel {
      width: 100%;
    }
    .panel-title-bar {
      flex-wrap: wrap;
      gap: 8px;
      padding: 8px 12px;
    }
  }

  @media (max-width: 600px) {
    :global(.tt-pct) {
      display: none;
    }
    .filters {
      gap: 4px;
      padding: 6px 8px;
    }
    .filter-select {
      padding: 5px 6px;
      font-size: 12px;
    }
    .search-input {
      padding: 5px 8px;
      font-size: 12px;
      min-width: 100px;
    }
    .mobile-category-toggle {
      padding: 5px 10px;
      font-size: 12px;
    }
    .action-btn {
      padding: 5px 10px;
      font-size: 12px;
    }
    .auth-hint-btn {
      padding: 5px 10px;
      font-size: 12px;
      max-height: none;
      gap: 4px;
    }
    .auth-hint-btn svg {
      width: 12px;
      height: 12px;
    }
    /* Detail view: 12-col grid — Row 1: 4 equal buttons (3 cols each), Row 2: 3 equal dropdowns (4 cols each) */
    .filters-detail {
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      column-gap: 4px;
      row-gap: 4px;
    }
    .filters-detail {
      padding: 8px;
    }
    .filters-detail > .mobile-category-toggle {
      grid-row: 1;
      grid-column: span 3;
      text-align: center;
      font-size: 13px;
      padding: 8px;
    }
    /* Flatten actions-right so its children become direct grid items */
    .filters-detail > .actions-right {
      display: contents;
    }
    .filters-detail > .actions-right > .action-btn,
    .filters-detail > .actions-right > .auth-hint-btn {
      grid-row: 1;
      grid-column: span 3;
      min-width: 0;
      justify-content: center;
      text-align: center;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      font-size: 13px;
      padding: 8px;
    }
    /* Auth button (when not logged in) spans remaining cols */
    .filters-detail > .actions-right > .auth-hint-btn {
      grid-column: span 9;
    }
    .filters-detail > .actions-right > .actions-divider,
    .filters-detail > .actions-right > .trade-list-btn {
      display: none;
    }
    .filters-detail > .filter-select {
      grid-row: 2;
      grid-column: span 4;
      min-width: 0;
      overflow: hidden;
      padding: 8px;
      font-size: 13px;
    }
    .filter-search-row {
      gap: 4px;
    }
    .filter-dropdowns {
      gap: 4px;
    }
    .filter-actions {
      gap: 4px;
    }
    .detail-title {
      gap: 4px 8px;
      padding: 8px 10px;
      flex-wrap: wrap;
      align-items: center;
    }
    /* Mobile: square back button with icon only */
    .back-btn {
      padding: 6px;
    }
    .back-text {
      display: none;
    }
    .detail-title-name {
      font-size: 15px;
      flex: 1 1 0;
      min-width: 60px;
    }
    .detail-tt-badge {
      font-size: 13px;
      padding: 1px 6px;
    }
    /* Mobile: controls row with filter btn + period + chart — same height as back btn */
    .detail-title-controls {
      display: flex;
      align-items: stretch;
      gap: 4px;
      margin-left: auto;
    }
    .desktop-only-gender,
    .desktop-only-history {
      display: none !important;
    }
    .dialog-gender-toggle {
      display: contents;
    }
    .dialog-gender-toggle :global(.gender-toggle) {
      justify-self: start;
    }
    .dialog-gender-toggle :global(.gender-btn) {
      padding: 6px 12px;
    }
    .detail-title-right {
      width: 100%;
      justify-content: flex-start;
      gap: 4px;
      flex-wrap: wrap;
    }
    .detail-title-right .metric {
      padding: 2px 6px;
      font-size: 10px;
    }
    .metric .metric-value {
      font-size: 13px;
    }
    .detail-title-controls .period-select {
      min-width: 45px;
      padding: 5px 4px;
      font-size: 13px;
    }
    .detail-title-controls .chart-toggle-btn {
      min-width: 44px;
      padding: 5px 6px;
      font-size: 13px;
    }
    /* Mobile filter dialog */
    .detail-filter-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 4px 8px;
      border: 1px solid var(--border-color);
      border-radius: 6px;
      background: transparent;
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .detail-filter-btn.has-active {
      color: var(--accent-color);
      border-color: var(--accent-color);
      background: var(--accent-color-bg);
    }
    .detail-filters {
      display: none;
    }
    .detail-filters.open {
      display: flex;
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 1000;
      background: rgba(0, 0, 0, 0.5);
      align-items: flex-end;
      justify-content: center;
    }
    .detail-filters-content {
      display: grid;
      grid-template-columns: auto 1fr;
      column-gap: 8px;
      row-gap: 16px;
      align-items: center;
      width: 100%;
      max-height: 80vh;
      overflow-y: auto;
      background: var(--bg-color);
      border-radius: 12px 12px 0 0;
      padding: 16px 20px 24px;
      box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.2);
    }
    .detail-filters-header {
      grid-column: 1 / -1;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 15px;
      font-weight: 600;
      color: var(--text-color);
    }
    .detail-filters-close {
      background: none;
      border: none;
      font-size: 22px;
      color: var(--text-muted);
      cursor: pointer;
      padding: 0 4px;
      line-height: 1;
    }
    .detail-filters-close:hover {
      color: var(--text-color);
    }
    /* Min-tt group: display:contents to align label + input in grid */
    .detail-filters .min-tt-group {
      display: contents;
    }
    .detail-filters .filter-input-small {
      width: 100%;
    }
    /* RangeSliders: display:contents to expose label + track to parent grid */
    .detail-filters-content :global(.range-slider.compact) {
      display: contents;
    }
    .detail-filters-content :global(.range-slider.compact .track) {
      width: 100%;
      margin: 0;
    }
    .detail-filters-content :global(.range-slider.compact .range-label) {
      white-space: nowrap;
    }
    /* Condition filter: also use display:contents for label + slider alignment */
    .detail-filters .condition-filter {
      display: contents;
    }
    .detail-filters .condition-slider {
      width: 100%;
    }
  }

  /* Auth hint button */
  .auth-hint-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 6px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 13px;
    transition: all 0.15s;
    max-height: 32px;
    box-sizing: border-box;
    white-space: nowrap;
  }

  .auth-hint-btn:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color);
  }

  /* Auth dialog */
  .auth-dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
    box-sizing: border-box;
  }

  .auth-dialog-content {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 12px;
    max-width: 500px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    position: relative;
    padding: 24px;
    box-sizing: border-box;
  }

  .auth-dialog-close {
    position: absolute;
    top: 12px;
    right: 12px;
    background: transparent;
    border: none;
    color: var(--text-muted, #999);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: all 0.15s;
  }

  .auth-dialog-close:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .auth-dialog-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-color);
    margin: 0 0 16px 0;
    padding-right: 32px;
  }

  .auth-dialog-body {
    color: var(--text-color);
  }

  .auth-dialog-body > p {
    margin: 0 0 20px 0;
    color: var(--text-muted, #999);
    line-height: 1.5;
  }

  .auth-steps {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 24px;
  }

  .auth-step {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }

  .step-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 50%;
    font-size: 14px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .step-content {
    flex: 1;
  }

  .step-content strong {
    display: block;
    margin-bottom: 4px;
    color: var(--text-color);
  }

  .step-content p {
    margin: 0;
    font-size: 13px;
    color: var(--text-muted, #999);
    line-height: 1.4;
  }

  .auth-dialog-actions {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }

  .auth-dialog-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.15s;
    border: none;
  }

  .auth-dialog-btn.primary {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .auth-dialog-btn.primary:hover {
    filter: brightness(1.1);
  }

  .auth-dialog-btn.secondary {
    background-color: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color, #555);
  }

  .auth-dialog-btn.secondary:hover {
    border-color: var(--accent-color, #4a9eff);
  }

  /* Turnstile confirmation modal */
  .turnstile-modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
    box-sizing: border-box;
  }
  .turnstile-modal {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 24px;
    max-width: 400px;
    width: 100%;
    box-sizing: border-box;
  }
  .turnstile-modal-title {
    margin: 0 0 8px 0;
    font-size: 16px;
    color: var(--text-color);
  }
  .turnstile-modal-desc {
    margin: 0 0 16px 0;
    font-size: 13px;
    color: var(--text-muted);
  }
  .turnstile-modal-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 16px;
  }
  .turnstile-modal-actions .btn-cancel {
    padding: 8px 16px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-color);
    cursor: pointer;
    font-size: 13px;
  }
  .turnstile-modal-actions .btn-cancel:hover {
    background: var(--hover-color);
  }
  .turnstile-modal-actions .btn-confirm {
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    background: var(--accent-color);
    color: #fff;
    cursor: pointer;
    font-size: 13px;
  }
  .turnstile-modal-actions .btn-confirm:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .turnstile-modal-actions .btn-confirm:hover:not(:disabled) {
    filter: brightness(1.1);
  }

</style>

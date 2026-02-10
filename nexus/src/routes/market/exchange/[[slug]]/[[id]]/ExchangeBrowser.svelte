<script lang="ts">
  // @ts-nocheck
  import { onMount } from "svelte";

  import CategoryTree from "./CategoryTree.svelte";
  import FancyTable from "$lib/components/FancyTable.svelte";
  import OrderDialog from './OrderDialog.svelte';
  import MyOffersView from './MyOffersView.svelte';
  import OrderBookTable from './OrderBookTable.svelte';
  import InventoryImportDialog from './InventoryImportDialog.svelte';
  import OfferAdjustDialog from './OfferAdjustDialog.svelte';
  import InventoryPanel from './InventoryPanel.svelte';
  import CartSummary from './CartSummary.svelte';
  import FavouritesTree from './FavouritesTree.svelte';
  import QuickTradeDialog from './QuickTradeDialog.svelte';
  import UserOffersPanel from './UserOffersPanel.svelte';
  import TradeRequestsPanel from './TradeRequestsPanel.svelte';
  import PriceHistoryChart from './PriceHistoryChart.svelte';

  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { apiCall, getItemLink, hasItemTag, encodeURIComponentSafe, decodeURIComponentSafe } from "$lib/util.js";
  import { isBlueprint, isItemTierable, isLimited, itemHasCondition, isAbsoluteMarkup, getMaxTT } from '../../orderUtils';
  import { PLANETS } from '../../exchangeConstants.js';
  import { showMyOffers, showInventory, showTradeList, showTrades, tradeList, addToTradeList, clearTradeList, myOffers, inventory } from '../../exchangeStore.js';
  import { favourites, isFavourite, toggleFavourite, createFolder } from '../../favouritesStore.js';
  import { hasCondition } from '$lib/shopUtils';

  const VIEW_SLUGS = new Set(['listings', 'offers', 'inventory', 'trades']);

  let searchTerm = "";
  let selectedCategory = "All";
  let selectedCategoryRawPath = null; // raw key path array for URL construction
  let selectedPlanet = "All Planets";
  let selectedLimited = "all";
  let selectedSex = "both";
  let filteredItems = [];
  let selectedItems = [];
  let loading = false;
  let showOrderDialog = false;
  let orderDialogType = null; // 'buy' | 'sell'
  let orderDialogRef;
  // Title bar filters for tierable items
  let mobileSidebarOpen = false;
  let sidebarTab = 'categories'; // 'categories' | 'favourites'
  let selectedFavFolderId = null; // folder id, 'all', 'root', or null
  let favouriteFolderFilter = null; // Set<number> | null — when set, filters main listing
  let selectedTierFilter = "All"; // UL default
  let selectedTiRRange = "All"; // L default
  // QR filter dropdown options
  const qrRangeOptions = [
    { label: "All", value: "all" },
    ...Array.from({ length: 10 }, (_, i) => ({
      label: `${i * 10 + 1}-${i * 10 + 9}`,
      value: `${i * 10}`
    })),
    { label: "100", value: "100" }
  ];
  let selectedQRRange = "all";
  const tierOptionLabels = [
    "All",
    ...Array.from({ length: 11 }, (_, i) => String(i)),
  ];
  const tirRangeOptions = (() => {
    const arr = [{ label: "All" }, { label: "0-500", min: 0, max: 500 }];
    for (let start = 501; start <= 3501; start += 500) {
      const end = start + 499;
      arr.push({ label: `${start}-${end}`, min: start, max: end });
    }
    return arr;
  })();

  // Tierable types list (used by detail view tables)
  const tierableTypes = new Set([
    "Weapon",
    "Armor",
    "Finder",
    "Excavator",
    "MedicalTool",
  ]);

  // Pending edit offer (set when user clicks Edit in MyOffersView)
  let pendingEditOffer = null;

  // Inline edit: item details loaded separately from detail view
  let inlineEditItem = null;

  // Quick trade dialog state
  let showQuickTrade = false;
  let quickTradeOffer = null;
  let quickTradeSide = 'buy'; // 'buy' | 'sell'
  let quickTradeRef;

  // User offers panel state
  let showUserOffers = false;
  let userOffersTarget = null; // { id, name }
  let userOffersReturnUrl = null; // URL to return to when closing the panel

  // Side filter for floating panel (All/Buy/Sell)
  let panelSideFilter = 'all'; // 'all' | 'BUY' | 'SELL'

  // Inventory & Offers panel
  let showImportDialog = false;
  let showAdjustDialog = false;
  let inventoryPanelRef;
  let myOffersRef;
  let tradesPanelRef;
  let bumpingAll = false;

  // Reactive discrepancy count: compare sell offers against inventory
  $: discrepancyCount = computeDiscrepancyCount($myOffers, $inventory);

  function computeDiscrepancyCount(offers, inv) {
    const sellOffers = (offers || []).filter(o => o.type === 'SELL');
    if (sellOffers.length === 0 || !inv || inv.length === 0) return 0;
    const invQtyMap = new Map();
    for (const item of inv) {
      if (item.item_id > 0) {
        invQtyMap.set(item.item_id, (invQtyMap.get(item.item_id) || 0) + item.quantity);
      }
    }
    let count = 0;
    for (const offer of sellOffers) {
      const invQty = invQtyMap.get(offer.item_id) || 0;
      if (offer.quantity > invQty) count++;
    }
    return count;
  }

  function closeFloatingPanel() {
    showMyOffers.set(false);
    showInventory.set(false);
    showTrades.set(false);
    if (showUserOffers) clearTradeList();
    showUserOffers = false;
    goto('/market/exchange/listings' + getCategoryUrlSegment());
  }

  async function editOfferInline(offer) {
    if (!offer?.item_id) return;
    try {
      const item = await apiCall(window.fetch, `/items/${offer.item_id}`);
      if (!item) return;

      inlineEditItem = item;
      const type = offer.type === 'BUY' ? 'buy' : 'sell';
      orderDialogType = type;

      const editOrder = {
        Type: offer.type === 'BUY' ? 'Buy' : 'Sell',
        Item: {
          Name: item?.Name || offer.details?.item_name || '',
          Type: item?.Properties?.Type || item?.Type || null,
          MaxTT: getMaxTT(item),
        },
        Planet: offer.planet || 'Calypso',
        Quantity: offer.quantity || 1,
        CurrentTT: offer.details?.CurrentTT ?? null,
        Markup: offer.markup || 0,
        Metadata: { ...(offer.details || {}) },
        _offerId: offer.id,
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

  async function openUserOffersByName(name) {
    // Skip if already showing this user's offers
    if (showUserOffers && userOffersTarget?.name === name) return;
    try {
      const res = await fetch(`/api/users/profiles/${encodeURIComponentSafe(name)}`);
      if (res.ok) {
        const data = await res.json();
        const userId = data?.profile?.id;
        if (userId) {
          openUserOffersPanel(userId, name);
          return;
        }
      }
    } catch {}
    // Fallback: just open My Offers if lookup fails
    switchFloatingTab('offers');
  }

  function openUserOffersPanel(userId, name) {
    userOffersTarget = { id: userId, name };
    userOffersReturnUrl = $page.url.pathname;
    showUserOffers = true;
    showMyOffers.set(false);
    showInventory.set(false);
    showTrades.set(false);
    showTradeList.set(false);
    clearTradeList();
    panelSideFilter = 'all';
    // Update URL to reflect the user's offers page
    const offersUrl = `/market/exchange/offers/${encodeURIComponentSafe(name)}`;
    if ($page.url.pathname !== offersUrl) {
      goto(offersUrl, { replaceState: false });
    }
  }

  function closeUserOffersPanel() {
    showUserOffers = false;
    clearTradeList();
    goto(userOffersReturnUrl || '/market/exchange/listings' + getCategoryUrlSegment());
  }

  function handleOfferAction(e) {
    const item = e.detail;
    if ($tradeList.length === 0) {
      // No trade list started — open QuickTradeDialog for a single trade request
      const rawOffer = item.offer || item;
      const side = item.side === 'SELL' ? 'buy' : 'sell';
      openQuickTrade(rawOffer, side);
    } else {
      // Trade list already started — add to it
      addToTradeList(item);
    }
  }

  function handleAddToListFromDialog(e) {
    const { offer, quantity, side } = e.detail;
    if (!offer) return;
    addToTradeList({
      offerId: offer.id,
      itemId: offer.item_id,
      itemName: offer.details?.item_name || 'Unknown',
      sellerId: userOffersTarget?.id || offer.user_id,
      sellerName: offer.seller_name || userOffersTarget?.name || 'Unknown',
      planet: offer.planet || '',
      quantity: quantity || offer.quantity || 1,
      unitPrice: Number(offer.markup) || 0,
      markup: Number(offer.markup) || 0,
      side: offer.type || 'SELL',
    });
    closeQuickTrade();
  }

  function switchFloatingTab(tab) {
    if (showUserOffers) clearTradeList();
    showMyOffers.set(tab === 'offers');
    showInventory.set(tab === 'inventory');
    showTrades.set(tab === 'trades');
    showTradeList.set(false);
    showUserOffers = false;
    panelSideFilter = 'all';
  }

  function refreshFloatingPanel() {
    if ($showMyOffers && myOffersRef) myOffersRef.refresh();
    else if ($showInventory && inventoryPanelRef) inventoryPanelRef.refresh();
    else if ($showTrades && tradesPanelRef) tradesPanelRef.refresh();
  }

  async function handleInventorySell(e) {
    const { invItem, existingOffer } = e.detail;
    if (!invItem?.item_id) return;

    try {
      // Fetch full item details for the OrderDialog
      const item = await apiCall(window.fetch, `/items/${invItem.item_id}`);
      if (!item) return;

      inlineEditItem = item;
      orderDialogType = 'sell';

      if (existingOffer) {
        // Edit existing offer
        const editOrder = {
          Type: 'Sell',
          Item: {
            Name: item?.Name || existingOffer.details?.item_name || '',
            Type: item?.Properties?.Type || item?.Type || null,
            MaxTT: getMaxTT(item),
          },
          Planet: existingOffer.planet || invItem.container || 'Calypso',
          Quantity: existingOffer.quantity || 1,
          CurrentTT: existingOffer.details?.CurrentTT ?? null,
          Markup: existingOffer.markup || 0,
          Metadata: { ...(existingOffer.details || {}) },
          _offerId: existingOffer.id,
          _inlineEdit: true,
          _inventoryWarning: `You already have a sell offer for this item. Editing it now.`,
        };
        delete editOrder.Metadata.item_name;
        delete editOrder.Metadata.CurrentTT;

        setTimeout(() => {
          orderDialogRef?.initOrder(editOrder, 'sell', 'edit');
          showOrderDialog = true;
        }, 0);
      } else {
        // Create new sell offer pre-filled from inventory
        const details = typeof invItem.details === 'string' ? JSON.parse(invItem.details) : (invItem.details || {});
        const newOrder = {
          Type: 'Sell',
          Item: {
            Name: item?.Name || invItem.item_name || '',
            Type: item?.Properties?.Type || item?.Type || null,
            MaxTT: getMaxTT(item),
            Id: invItem.item_id,
          },
          Planet: invItem.container || 'Calypso',
          Quantity: invItem.quantity || 1,
          CurrentTT: null,
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

  // Get URL segment for current category (empty string for All)
  function getCategoryUrlSegment() {
    if (!selectedCategory || selectedCategory === 'All') return '';
    if (selectedCategoryRawPath) return '/' + selectedCategoryRawPath.join('.');
    return '';
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

  // Find which category contains a specific item by ID
  function findItemCategory(obj, itemId, path = []) {
    for (const [key, value] of Object.entries(obj)) {
      const currentPath = [...path, key];
      if (Array.isArray(value)) {
        if (value.some(item => item.i === itemId)) return currentPath;
      } else if (typeof value === 'object' && value !== null) {
        const found = findItemCategory(value, itemId, currentPath);
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

  // Sync category selection from route
  $: {
    if (viewSlug === 'listings') {
      if (!routeId || !resolvedCategory) {
        // No routeId or it's an item (not category) — default to All unless item resolves below
        if (!routeId) {
          selectedCategory = 'All';
          selectedCategoryRawPath = null;
          selectedItems = allItems;
        }
      } else {
        // Matched a category by path
        const displayPath = resolvedCategory.path.map(formatCategoryName).join(' > ');
        selectedCategory = displayPath;
        selectedCategoryRawPath = resolvedCategory.path;
        selectedItems = gatherItemsAtPath(categorizedItems, resolvedCategory.path);
      }
    }
  }

  // When an item is resolved, auto-select its parent category
  $: if (selectedItem && isDetailView) {
    const catPath = findItemCategory(categorizedItems, selectedItem.i);
    if (catPath) {
      selectedCategory = catPath.map(formatCategoryName).join(' > ');
      selectedCategoryRawPath = catPath;
      selectedItems = gatherItemsAtPath(categorizedItems, catPath);
    }
  }

  // View change handling — open/close panels based on slug
  let currentViewSlug = null;
  $: if (viewSlug !== currentViewSlug) {
    currentViewSlug = viewSlug;
    if (viewSlug === 'listings') {
      showMyOffers.set(false);
      showInventory.set(false);
      showTrades.set(false);
      if (showUserOffers) clearTradeList();
      showUserOffers = false;
    } else if (viewSlug === 'offers') {
      const id = routeId;
      const decodedName = id ? decodeURIComponentSafe(id) : null;
      const currentUserName = $page?.data?.session?.user?.eu_name;
      if (decodedName && decodedName !== currentUserName) {
        openUserOffersByName(decodedName);
      } else {
        switchFloatingTab('offers');
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
          const it = await apiCall(window.fetch, `/items/${id}`);
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

  // If a pending edit offer exists and item details have loaded, open the edit dialog
  $: if (pendingEditOffer && selectedItemDetails) {
    const offer = pendingEditOffer;
    pendingEditOffer = null;
    const type = offer.type === 'BUY' ? 'buy' : 'sell';
    orderDialogType = type;
    setTimeout(() => {
      // Build an order object from the offer for editing
      const editOrder = {
        Type: offer.type === 'BUY' ? 'Buy' : 'Sell',
        Item: {
          Name: selectedItemDetails?.Name || offer.details?.item_name || '',
          Type: selectedItemDetails?.Properties?.Type || selectedItemDetails?.Type || null,
          MaxTT: getMaxTT(selectedItemDetails),
        },
        Planet: offer.planet || 'Calypso',
        Quantity: offer.quantity || 1,
        CurrentTT: offer.details?.CurrentTT ?? null,
        Markup: offer.markup || 0,
        Metadata: { ...(offer.details || {}) },
        _offerId: offer.id,  // track original offer ID for PUT
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

      if (needle && !name.toLowerCase().includes(needle)) return false;

      if (selectedLimited !== "all") {
        const isL = hasItemTag(name, "L");
        if (selectedLimited === "L" && !isL) return false;
        if (selectedLimited === "UL" && isL) return false;
      }

      if (selectedSex === "male" && hasItemTag(name, "F")) return false;
      if (selectedSex === "female" && hasItemTag(name, "M")) return false;

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
      buys: item.b || null,
      sells: item.s || null,
      lastUpdate: null,
      _hasBoth: (item.b > 0 && item.s > 0) ? 1 : 0,
    }));
    // Default: items with both buy + sell orders float to top
    rows.sort((a, b) => b._hasBoth - a._hasBoth);
    return rows;
  })();

  // Columns for the main list view FancyTable
  const listColumns = [
    { key: 'name', header: 'Item', main: true, sortable: true, searchable: true },
    { key: 'median', header: 'Median', width: '100px', sortable: true, searchable: false, formatter: (v) => v != null ? Number(v).toFixed(2) : '<span style="opacity:0.35">N/A</span>' },
    { key: 'percentile10', header: '10%', width: '80px', sortable: true, searchable: false, hideOnMobile: true, formatter: (v) => v != null ? Number(v).toFixed(2) : '<span style="opacity:0.35">N/A</span>' },
    { key: 'wap', header: 'WAP', width: '80px', sortable: true, searchable: false, hideOnMobile: true, formatter: (v) => v != null ? Number(v).toFixed(2) : '<span style="opacity:0.35">N/A</span>' },
    { key: 'buys', header: 'Buys', width: '70px', sortable: true, searchable: false, hideOnMobile: true, formatter: (v) => v != null ? v : '<span style="opacity:0.35">-</span>' },
    { key: 'sells', header: 'Sells', width: '70px', sortable: true, searchable: false, hideOnMobile: true, formatter: (v) => v != null ? v : '<span style="opacity:0.35">-</span>' },
    { key: 'lastUpdate', header: 'Updated', width: '100px', sortable: true, searchable: false, hideOnMobile: true, formatter: (v) => v || '<span style="opacity:0.35">-</span>' },
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
    favouriteFolderFilter = null;
    selectedFavFolderId = null;
    selectedCategory = categoryPath;
    selectedCategoryRawPath = rawPath || null;
    selectedItems = Array.isArray(items) ? items : [];
    // Use dot-separated raw key path for unambiguous URL routing
    const urlSegment = rawPath ? rawPath.join('.') : '';
    goto('/market/exchange/listings' + (urlSegment ? '/' + urlSegment : ''));
  }

  function handleFavouriteFolderSelect(folderId, itemIds) {
    selectedFavFolderId = folderId;
    favouriteFolderFilter = new Set(itemIds);
    if (viewSlug !== 'listings' || isDetailView || selectedCategory !== 'All') {
      goto('/market/exchange/listings');
    }
    mobileSidebarOpen = false;
  }

  function formatPrice(value) {
    return value ? `${value.toFixed(2)} PED` : "N/A";
  }

  function formatMarkupDisplay(value) {
    if (value == null || !isFinite(value)) return 'N/A';
    if (isAbsoluteMarkup(selectedItemDetails)) {
      return `+${value.toFixed(2)}`;
    }
    return `${value.toFixed(1)}%`;
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
  let lastPlanet = selectedPlanet;
  async function handlePlanetChange() {
    if (selectedPlanet === lastPlanet) return;
    lastPlanet = selectedPlanet;
    loading = true;
    try {
      // TODO: call backend to fetch planet-specific market data once available
      // const res = await fetch(`/api/market/exchange?planet=${encodeURIComponent(selectedPlanet)}`);
      // const json = await res.json();
      if (selectedLimited !== "all" && appliesLULForCurrent) {
        await new Promise((r) => setTimeout(r, 400));
      }
    } finally {
      loading = false;
    }
  }

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

  let ordersLoading = false;
  let ordersLoadedKey = "";
  async function loadOrders(numericId, planet) {
    if (!numericId || typeof numericId !== 'number') return;
    const key = `${numericId}::${planet}`;
    if (ordersLoadedKey === key) return;
    ordersLoadedKey = key;
    ordersLoading = true;
    showPriceHistory = false;
    priceHistoryData = [];
    periodStats = null;
    try {
      const [ordersRes, pricesRes] = await Promise.all([
        fetch(`/api/market/exchange/offers/item/${encodeURIComponent(numericId)}`),
        fetch(`/api/market/prices/exchange/${encodeURIComponent(numericId)}?period=${selectedPeriod}`).catch(() => null),
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
    const key = `${itemId}::${period}`;
    if (key === lastPeriodStatsKey) return;
    lastPeriodStatsKey = key;
    try {
      const includeHistory = showPriceHistory ? '&history=1' : '';
      const res = await fetch(`/api/market/prices/exchange/${encodeURIComponent(itemId)}?period=${period}${includeHistory}`);
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
    priceHistoryLoading = true;
    try {
      const res = await fetch(`/api/market/prices/exchange/${encodeURIComponent(selectedItem.i)}?period=${selectedPeriod}&history=1`);
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
    const isAbsMu = isAbsoluteMarkup(selectedItemDetails);
    const fmt = (x, digits = 2) =>
      typeof x === "number" && isFinite(x) ? x.toFixed(digits) : "N/A";
    const muText = isAbsMu
      ? absMu != null
        ? `+${fmt(absMu)}`
        : "N/A"
      : muPct != null
        ? `${fmt(muPct, 1)}%`
        : "N/A";

    const type =
      selectedItemDetails?.Properties?.Type || selectedItem?.t || null;
    const isTierable = tierableTypes.has(type);
    const tier = o?.Tier ?? o?.tier ?? o?.details?.Tier ?? null;
    const tir = o?.TiR ?? o?.tir ?? o?.TIR ?? o?.details?.TierIncreaseRate ?? null;

    const baseValues = [
      qty,
      ttUnit != null ? `${fmt(ttUnit)} PED` : "N/A",
      muText,
      total != null ? `${fmt(total)} PED` : "N/A",
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
      const offerId = o?.id ?? o?.Id ?? 0;
      const cartBtn = `<button class="cell-button cart-add-btn" data-cart-add="${offerId}">+Cart</button>`;
      values.push(cartBtn);
      tdStyles.push(cellStyle);
    }

    return { values, tdStyles, detail: o };
  }

  function applyOrderFilters(orders) {
    const maxTT = getMaxTT(selectedItemDetails);
    const isAbsMu = isAbsoluteMarkup(selectedItemDetails);

    return (orders || [])
      .filter((o) =>
        selectedPlanet === "All Planets" ||
        (o?.Planet || o?.planet) === selectedPlanet
      )
      .filter((o) => {
        if (!isTierableDetail) return true;
        if (!isLimitedDetail) {
          if (selectedTierFilter === "All") return true;
          const t = Number(o?.Tier ?? o?.tier ?? o?.details?.Tier);
          return isFinite(t) ? Math.floor(t) === Number(selectedTierFilter) : true;
        } else {
          if (selectedTiRRange === "All") return true;
          const tir = Number(o?.TiR ?? o?.tir ?? o?.TIR ?? o?.details?.TierIncreaseRate);
          const [min, max] = (selectedTiRRange || "0-500").split("-").map(Number);
          return isFinite(tir) ? tir >= min && tir <= max : true;
        }
      })
      .filter((o) =>
        lastUpdateFilter === "all"
          ? true
          : classifyFreshness(getUpdatedAt(o)) === lastUpdateFilter
      )
      .filter((o) => {
        if (!minTTFilter) return true;
        const qty = o?.Quantity ?? o?.quantity ?? 0;
        const ttTotal = maxTT != null ? maxTT * qty : null;
        return ttTotal == null || ttTotal >= minTTFilter;
      })
      .map(o => {
        const qty = o?.Quantity ?? o?.quantity ?? 0;
        const mu = o?.Markup ?? o?.markup ?? null;
        // Compute TT value and unit price from item's MaxTT and order markup
        let ttValue = o?.TTValue ?? o?.Value ?? o?.tt_value ?? o?.details?.CurrentTT ?? null;
        let unitPrice = o?.Price ?? o?.price ?? o?.UnitPrice ?? o?.unit_price ?? null;
        if (ttValue == null && maxTT != null) ttValue = maxTT;
        if (unitPrice == null && ttValue != null && mu != null) {
          unitPrice = isAbsMu ? ttValue + mu : ttValue * (mu / 100);
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

  $: filteredSellOrders = applyOrderFilters(sellOrders)
    .sort((a, b) => (a.Price ?? Infinity) - (b.Price ?? Infinity));

  $: filteredBuyOrders = applyOrderFilters(buyOrders)
    .sort((a, b) => (b.Price ?? -Infinity) - (a.Price ?? -Infinity));

  $: myBuyOrder = currentUser && (buyOrders || []).find(o => getSellerId(o) === currentUser.id) || null;
  $: mySellOrder = currentUser && (sellOrders || []).find(o => getSellerId(o) === currentUser.id) || null;
  $: hasMyBuyOrder = !!myBuyOrder;
  $: hasMySellOrder = !!mySellOrder;

  function openOrderDialog(type) {
    const item = selectedItemDetails;
    if (!item) return;
    orderDialogType = type;
    const existingOrder = type === 'buy' ? myBuyOrder : mySellOrder;
    setTimeout(() => {
      if (existingOrder) {
        // Open existing order for editing
        const editOrder = {
          Type: existingOrder.type === 'BUY' ? 'Buy' : 'Sell',
          Item: {
            Name: item?.Name || existingOrder.details?.item_name || '',
            Type: item?.Properties?.Type || item?.Type || null,
            MaxTT: getMaxTT(item),
          },
          Planet: existingOrder.planet || 'Calypso',
          Quantity: existingOrder.quantity || 1,
          CurrentTT: existingOrder.details?.CurrentTT ?? null,
          Markup: existingOrder.markup || 0,
          MinQuantity: existingOrder.min_quantity || null,
          Metadata: { ...(existingOrder.details || {}) },
          _offerId: existingOrder.id,
        };
        delete editOrder.Metadata.item_name;
        delete editOrder.Metadata.CurrentTT;
        orderDialogRef?.initOrder(editOrder, type, 'edit');
      } else {
        orderDialogRef?.initOrder(item, type, 'create');
      }
      showOrderDialog = true;
    }, 0);
  }
  function closeOrderDialog() {
    showOrderDialog = false;
    orderDialogType = null;
    inlineEditItem = null;
  }

  async function onSubmitOrder(e) {
    const order = e?.detail?.order;
    if (!order) { closeOrderDialog(); return; }

    const item = inlineEditItem || selectedItemDetails || selectedItem;
    const itemId = item?.ItemId ?? item?.Id ?? item?.i;
    if (!itemId) { closeOrderDialog(); return; }

    const isEdit = !!order._offerId;
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
    // Include CurrentTT if set (condition items)
    if (order.CurrentTT != null) {
      payload.details.CurrentTT = order.CurrentTT;
    }
    // Clean internal tracking fields from details
    delete payload.details._offerId;
    delete payload.details._inlineEdit;
    delete payload.details._inventoryWarning;
    delete payload.details._inventoryQty;

    try {
      let res;
      if (isEdit) {
        res = await fetch(`/api/market/exchange/offers/${order._offerId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        res = await fetch('/api/market/exchange/offers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }
      const data = await res.json();
      if (!res.ok) {
        console.error(`Order ${isEdit ? 'update' : 'creation'} failed:`, data.error);
        return;
      }
      // Reload orders for this item (detail view) or refresh My Offers (inline edit)
      if (inlineEditItem) {
        if (myOffersRef) myOffersRef.refresh();
        // Also refresh myOffers store directly for discrepancy count
        try {
          const offersRes = await fetch('/api/market/exchange/offers');
          if (offersRes.ok) myOffers.set(await offersRes.json());
        } catch {}
      } else {
        ordersLoadedKey = '';
        if (selectedItem?.i) await loadOrders(selectedItem.i, selectedPlanet);
      }
    } catch (e) {
      console.error('Error submitting order:', e);
    } finally {
      closeOrderDialog();
    }
  }

  async function handleDeleteOffer(e) {
    const order = e?.detail?.order;
    const offerId = order?._offerId;
    if (!offerId) { closeOrderDialog(); return; }

    if (!confirm('Are you sure you want to delete this offer?')) return;

    try {
      const res = await fetch(`/api/market/exchange/offers/${offerId}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        console.error('Delete failed:', data.error);
        return;
      }
      // Refresh orders
      if (inlineEditItem) {
        if (myOffersRef) myOffersRef.refresh();
        try {
          const offersRes = await fetch('/api/market/exchange/offers');
          if (offersRes.ok) myOffers.set(await offersRes.json());
        } catch {}
      } else {
        ordersLoadedKey = '';
        if (selectedItem?.i) await loadOrders(selectedItem.i, selectedPlanet);
      }
    } catch (err) {
      console.error('Error deleting offer:', err);
    } finally {
      closeOrderDialog();
    }
  }

  // FancyTable columns for detail view buy/sell tables
  $: detailColumns = (() => {
    const type = selectedItemDetails?.Properties?.Type || selectedItem?.t || null;
    const showTier = tierableTypes.has(type);
    const isAbsMu = isAbsoluteMarkup(selectedItemDetails);
    const cols = [];

    if (showTier) {
      cols.push({ key: 'tier', header: 'Tier', width: '60px', sortable: true, searchable: false,
        formatter: (v) => v ?? 'N/A' });
      cols.push({ key: 'tir', header: 'TiR', width: '80px', sortable: true, searchable: false,
        formatter: (v) => v ?? 'N/A' });
    }
    cols.push({ key: 'quantity', header: 'Qty', width: '80px', sortable: true, searchable: false,
      formatter: (v) => v ?? 0 });
    cols.push({ key: '_value', header: 'Value', width: '100px', sortable: true, searchable: false,
      formatter: (v, row) => {
        const tt = row?.TTValue ?? row?.Value ?? row?.tt_value ?? null;
        return tt != null ? `${Number(tt).toFixed(2)} PED` : 'N/A';
      }});
    cols.push({ key: 'markup', header: isAbsMu ? 'MU (+PED)' : 'MU (%)', width: '90px', sortable: true, searchable: false,
      formatter: (v) => {
        const mu = v != null ? Number(v) : null;
        if (mu == null || !isFinite(mu)) return 'N/A';
        return isAbsMu ? `+${mu.toFixed(2)}` : `${mu.toFixed(1)}%`;
      }});
    cols.push({ key: '_total', header: 'Total', width: '100px', sortable: true, searchable: false,
      formatter: (v, row) => {
        const qty = row?.Quantity ?? row?.quantity ?? 0;
        const price = row?.Price ?? row?.price ?? row?.UnitPrice ?? row?.unit_price ?? null;
        const total = row?.TotalPrice ?? row?.total ?? (price != null ? price * qty : null);
        return total != null ? `${Number(total).toFixed(2)} PED` : 'N/A';
      }});
    cols.push({ key: 'planet', header: 'Planet', width: '120px', sortable: true, searchable: false,
      formatter: (v) => v || selectedPlanet || 'N/A' });
    cols.push({ key: 'bumped_at', header: 'Updated', width: '100px', sortable: true, searchable: false,
      formatter: (v, row) => formatLastUpdateDHm(getUpdatedAt(row) || v) });

    return cols;
  })();

  function makeUserColumn(header) {
    return { key: 'seller_name', header, main: true, sortable: true, searchable: false,
      formatter: (v, row) => {
        const name = row?.SellerName ?? row?.seller ?? v ?? 'Unknown';
        const userId = row?.user_id ?? '';
        return `<span class="seller-link" data-seller-id="${userId}" data-seller-name="${name.replace(/"/g, '&amp;quot;')}">${name}</span>`;
      }};
  }

  // Sell orders: user column = "Seller", action = "Buy" (or "Edit" for own orders)
  $: sellDetailColumns = (() => {
    const cols = [...detailColumns];
    const updatedIdx = cols.findIndex(c => c.key === 'bumped_at');
    cols.splice(updatedIdx >= 0 ? updatedIdx : cols.length, 0, makeUserColumn('Seller'));
    cols.push({
      key: '_action', header: '', width: '70px', sortable: false, searchable: false,
      formatter: (v, row) => {
        const offerId = row?.id ?? row?.Id ?? 0;
        const isOwn = currentUser && String(getSellerId(row)) === String(currentUser.id);
        if (isOwn) return `<button class="cell-button trade-btn edit-trade-btn" data-trade-buy="${offerId}">Edit</button>`;
        return `<button class="cell-button trade-btn buy-trade-btn" data-trade-buy="${offerId}">Buy</button>`;
      }
    });
    return cols;
  })();

  // Buy orders: user column = "Buyer", action = "Sell" (or "Edit" for own orders)
  $: buyDetailColumns = (() => {
    const cols = [...detailColumns];
    const updatedIdx = cols.findIndex(c => c.key === 'bumped_at');
    cols.splice(updatedIdx >= 0 ? updatedIdx : cols.length, 0, makeUserColumn('Buyer'));
    cols.push({
      key: '_action', header: '', width: '70px', sortable: false, searchable: false,
      formatter: (v, row) => {
        const offerId = row?.id ?? row?.Id ?? 0;
        const isOwn = currentUser && String(getSellerId(row)) === String(currentUser.id);
        if (isOwn) return `<button class="cell-button trade-btn edit-trade-btn" data-trade-sell="${offerId}">Edit</button>`;
        return `<button class="cell-button trade-btn sell-trade-btn" data-trade-sell="${offerId}">Sell</button>`;
      }
    });
    return cols;
  })();

  /** Handle clicks on Buy/Sell trade buttons and seller links in detail view */
  function handleDetailClick(e) {
    // Seller name click → open user offers panel
    const sellerEl = e.target.closest('[data-seller-id]');
    if (sellerEl) {
      e.stopPropagation();
      e.preventDefault();
      const userId = sellerEl.dataset.sellerId;
      const name = sellerEl.dataset.sellerName || 'Unknown';
      if (userId) openUserOffersPanel(userId, name);
      return;
    }

    const buyBtn = e.target.closest('[data-trade-buy]');
    const sellBtn = e.target.closest('[data-trade-sell]');
    if (!buyBtn && !sellBtn) return;
    e.stopPropagation();
    e.preventDefault();

    if (buyBtn) {
      const offerId = parseInt(buyBtn.dataset.tradeBuy, 10);
      const order = (sellOrders || []).find(o => (o?.id ?? o?.Id) === offerId);
      if (order) {
        if (currentUser && String(getSellerId(order)) === String(currentUser.id)) {
          editOfferInline(order);
        } else {
          openQuickTrade(order, 'buy');
        }
      }
    } else if (sellBtn) {
      const offerId = parseInt(sellBtn.dataset.tradeSell, 10);
      const order = (buyOrders || []).find(o => (o?.id ?? o?.Id) === offerId);
      if (order) {
        if (currentUser && String(getSellerId(order)) === String(currentUser.id)) {
          editOfferInline(order);
        } else {
          openQuickTrade(order, 'sell');
        }
      }
    }
  }

  function openQuickTrade(offer, side) {
    quickTradeOffer = offer;
    quickTradeSide = side;
    showQuickTrade = true;
  }

  function closeQuickTrade() {
    showQuickTrade = false;
    quickTradeOffer = null;
  }

  async function handleQuickTradeConfirm(e) {
    const { offer, quantity, side } = e.detail;
    const item = selectedItemDetails || selectedItem;
    const itemName = offer.details?.item_name || item?.Name || item?.n || 'Unknown';

    try {
      const res = await fetch('/api/market/trade-requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_id: offer.user_id,
          planet: offer.planet || null,
          items: [{
            offer_id: offer.id,
            item_id: offer.item_id ?? item?.i ?? item?.Id,
            item_name: itemName,
            quantity: quantity || offer.quantity || 1,
            markup: offer.markup || 0,
            side: offer.type || (side === 'buy' ? 'SELL' : 'BUY')
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
    const { order: bulkOrder, matches, planet } = e.detail;
    const item = selectedItemDetails || selectedItem;
    const itemName = bulkOrder?.Item?.Name || item?.Name || item?.n || 'Unknown';
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
      closeOrderDialog();
      goto('/market/exchange/trades');
    }
  }

  $: isBlueprintDetail = selectedItemDetails && isBlueprint(selectedItemDetails);
  $: isTierableDetail = selectedItemDetails && isItemTierable(selectedItemDetails);
  $: isLimitedDetail = selectedItemDetails && isLimited(selectedItemDetails);

  // Favourites
  $: currentItemId = selectedItem?.i ?? null;
  $: isCurrentFavourited = currentItemId != null && $favourites && isFavourite(currentItemId);

  function handleToggleFavourite() {
    if (currentItemId != null) toggleFavourite(currentItemId);
  }

  function handleFavouriteItemSelect(itemId) {
    const item = (allItems || []).find(it => it?.i === itemId);
    if (item?.n) {
      goto(`/market/exchange/listings/${encodeURIComponentSafe(item.n)}`);
    } else if (itemId != null) {
      goto(`/market/exchange/listings/${itemId}`);
    }
  }
</script>

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
            onSelectItem={(itemId) => { handleFavouriteItemSelect(itemId); mobileSidebarOpen = false; }}
            onSelectFolder={handleFavouriteFolderSelect}
          />
        </div>
      {/if}
    </div>

    <div class="main-content">
      {#if !isDetailView}
        <div class="filters">
          <button class="mobile-category-toggle" on:click={() => mobileSidebarOpen = !mobileSidebarOpen}>
            Categories
          </button>
          <input
            type="text"
            placeholder="Search items..."
            bind:value={searchTerm}
            class="search-input"
          />
          <select
            class="filter-select"
            bind:value={selectedPlanet}
            on:change={handlePlanetChange}
          >
            <option>All Planets</option>
            {#each PLANETS as p}
              <option>{p}</option>
            {/each}
          </select>
          <select class="filter-select" bind:value={selectedLimited}>
            <option value="all">Limited & Unlimited</option>
            <option value="L">Limited</option>
            <option value="UL">Unlimited</option>
          </select>
          <select class="filter-select" bind:value={selectedSex}>
            <option value="both">Male & Female</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
          <div class="actions-right">
            <button class="action-btn accent-btn" title="My Offers" on:click={() => {
              const userName = currentUser?.eu_name;
              goto(userName ? `/market/exchange/offers/${encodeURIComponentSafe(userName)}` : '/market/exchange/offers');
            }}>My Offers</button>
            <button class="action-btn accent-btn" title="Inventory" on:click={() => goto('/market/exchange/inventory')}>Inventory</button>
            {#if $tradeList.length > 0}
              <button class="action-btn trade-list-btn" title="Trade List" on:click={() => { closeFloatingPanel(); showTradeList.set(true); }}>
                Trade List ({$tradeList.length})
              </button>
            {/if}
          </div>
        </div>

        {#if $showTradeList}
          <CartSummary on:close={() => showTradeList.set(false)} />
        {:else if listTableData.length > 0}
          <div class="table-wrapper">
            <FancyTable
              columns={listColumns}
              data={listTableData}
              rowHeight={32}
              compact={true}
              sortable={true}
              searchable={false}
              emptyMessage="No items found"
              on:rowClick={(evt) => {
                const item = evt?.detail?.row?._item;
                if (item?.n) {
                  goto(`/market/exchange/listings/${encodeURIComponentSafe(item.n)}`);
                } else if (item?.i != null) {
                  goto(`/market/exchange/listings/${item.i}`);
                }
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
        <div class="filters">
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
          <div class="min-tt-group">
            <input
              type="number"
              class="filter-input-small"
              placeholder="Min TT"
              min="0"
              step="0.01"
              bind:value={minTTFilter}
              title="Minimum total TT value to show"
            />
            <span class="filter-hint">Min total TT</span>
          </div>
          <div class="actions-right">
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
            {#if $tradeList.length > 0}
              <span class="actions-divider"></span>
              <button class="action-btn trade-list-btn" title="Trade List" on:click={() => { showMyOffers.set(false); showInventory.set(false); showTradeList.set(true); }}>
                Trade List ({$tradeList.length})
              </button>
            {/if}
          </div>
        </div>
        <div class="detail-title">
          <button
            class="action-btn"
            on:click={() =>
              goto('/market/exchange/listings' + getCategoryUrlSegment())}
            title="Back to list">Back</button
          >
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
          >{selectedItem?.n || ""}</a>
          {#if selectedItemDetails && !hasCondition(selectedItemDetails) && getMaxTT(selectedItemDetails) != null}
            <span class="detail-tt-badge">{getMaxTT(selectedItemDetails).toFixed(2)} PED</span>
          {/if}
          {#if isTierableDetail}
            {#if !isLimitedDetail}
              <div class="tier-filter" title="Filter by Tier (UL)">
                <label for="tierFilterSelect">Tier</label>
                <select
                  id="tierFilterSelect"
                  bind:value={selectedTierFilter}
                  class="filter-select tier-select"
                >
                  {#each tierOptionLabels as t}
                    <option value={t}>{t}</option>
                  {/each}
                </select>
              </div>
            {:else}
              <div class="tier-filter" title="Filter by TiR range (L)">
                <label for="tirRangeSelect">TiR</label>
                <select
                  id="tirRangeSelect"
                  bind:value={selectedTiRRange}
                  class="filter-select tier-select"
                >
                  {#each tirRangeOptions as opt}
                    <option value={opt.label}>{opt.label}</option>
                  {/each}
                </select>
              </div>
            {/if}
          {/if}
          {#if isBlueprintDetail && !isLimitedDetail}
            <div class="tier-filter" title="Filter by QR range (Blueprints)">
              <label for="qrRangeSelect">QR</label>
              <select
                id="qrRangeSelect"
                bind:value={selectedQRRange}
                class="filter-select tier-select"
              >
                {#each qrRangeOptions as opt}
                  <option value={opt.value}>{opt.label}</option>
                {/each}
              </select>
            </div>
          {/if}
          <div class="detail-title-right">
            <div class="metric">
              Median:<br /><span class="metric-value"
                >{periodStats?.median != null
                  ? formatMarkupDisplay(periodStats.median)
                  : (typeof selectedItem?.m === "number" ? formatMarkupDisplay(selectedItem.m) : "N/A")}</span
              >
            </div>
            <div class="metric">
              10%:<br /><span class="metric-value"
                >{periodStats?.p10 != null
                  ? formatMarkupDisplay(periodStats.p10)
                  : (typeof selectedItem?.p === "number" ? formatMarkupDisplay(selectedItem.p) : "N/A")}</span
              >
            </div>
            <div class="metric">
              WAP:<br /><span class="metric-value"
                >{periodStats?.wap != null
                  ? formatMarkupDisplay(periodStats.wap)
                  : (typeof selectedItem?.w === "number" ? formatMarkupDisplay(selectedItem.w) : "N/A")}</span
              >
            </div>
            {#if exchangePrices?.buy}
              <div class="metric exchange-metric">
                Best Buy:<br /><span class="metric-value buy-value">{formatMarkupDisplay(exchangePrices.buy.best_markup)}</span>
              </div>
            {/if}
            {#if exchangePrices?.sell}
              <div class="metric exchange-metric">
                Best Sell:<br /><span class="metric-value sell-value">{formatMarkupDisplay(exchangePrices.sell.best_markup)}</span>
              </div>
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
        </div>

        {#if showPriceHistory}
          <div class="detail-wrapper chart-view">
            <PriceHistoryChart
              itemId={selectedItem?.i}
              period={selectedPeriod}
              isAbsoluteMarkup={isAbsoluteMarkup(selectedItemDetails)}
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
        offer={quickTradeOffer}
        side={quickTradeSide}
        item={selectedItemDetails || selectedItem}
        showAddToList={showUserOffers}
        on:close={closeQuickTrade}
        on:confirm={handleQuickTradeConfirm}
        on:addToList={handleAddToListFromDialog}
        on:editOwn={(e) => { closeQuickTrade(); editOfferInline(e.detail.offer); }}
      />

      <OrderDialog
        bind:this={orderDialogRef}
        show={showOrderDialog}
        hideBulkTab={!!inlineEditItem || !currentUser?.grants?.includes('market.bulk')}
        orderBookOffers={[...(buyOrders || []), ...(sellOrders || [])]}
        on:close={closeOrderDialog}
        on:submit={onSubmitOrder}
        on:bulkSubmit={handleBulkSubmit}
        on:delete={handleDeleteOffer}
      />
    </div>

    {#if $showMyOffers || $showInventory || $showTrades || showUserOffers}
      <div class="floating-panel">
        {#if showUserOffers}
          <div class="panel-title-bar">
            <button class="back-btn" on:click={closeUserOffersPanel}>Back</button>
            <span class="panel-title-text">{userOffersTarget?.name || 'User'}'s Offers</span>
            <div class="panel-header-actions">
              <div class="panel-side-filter">
                <button class="panel-filter-btn" class:active={panelSideFilter === 'all'} on:click={() => panelSideFilter = 'all'}>All</button>
                <button class="panel-filter-btn" class:active={panelSideFilter === 'BUY'} on:click={() => panelSideFilter = 'BUY'}>Buy</button>
                <button class="panel-filter-btn" class:active={panelSideFilter === 'SELL'} on:click={() => panelSideFilter = 'SELL'}>Sell</button>
              </div>
              {#if $tradeList.length > 0}
                <button class="panel-action-btn accent" on:click={() => showTradeList.set(true)}>
                  Trade List ({$tradeList.length})
                </button>
              {/if}
            </div>
          </div>
          {#if $showTradeList}
            <CartSummary on:close={() => showTradeList.set(false)} />
          {:else}
            <UserOffersPanel user={userOffersTarget} sideFilter={panelSideFilter} on:offerAction={handleOfferAction} />
          {/if}
        {:else}
          <div class="panel-title-bar">
            <button class="back-btn" on:click={closeFloatingPanel}>Back</button>
            <div class="panel-tabs">
              <button class="panel-tab" class:active={$showMyOffers} on:click={() => {
                const userName = currentUser?.eu_name;
                goto(userName ? `/market/exchange/offers/${encodeURIComponentSafe(userName)}` : '/market/exchange/offers');
              }}>My Offers</button>
              <button class="panel-tab" class:active={$showInventory} on:click={() => goto('/market/exchange/inventory')}>Inventory</button>
              <button class="panel-tab" class:active={$showTrades} on:click={() => goto('/market/exchange/trades')}>Trades</button>
            </div>
            <div class="panel-header-actions">
              {#if $showMyOffers}
                <div class="panel-side-filter">
                  <button class="panel-filter-btn" class:active={panelSideFilter === 'all'} on:click={() => panelSideFilter = 'all'}>All</button>
                  <button class="panel-filter-btn" class:active={panelSideFilter === 'BUY'} on:click={() => panelSideFilter = 'BUY'}>Buy</button>
                  <button class="panel-filter-btn" class:active={panelSideFilter === 'SELL'} on:click={() => panelSideFilter = 'SELL'}>Sell</button>
                </div>
                <button class="panel-action-btn accent" disabled={bumpingAll} on:click={async () => { bumpingAll = true; await myOffersRef?.bumpAll(); bumpingAll = false; }}>{bumpingAll ? 'Bumping...' : 'Bump All'}</button>
              {/if}
              {#if $showInventory}
                <button class="panel-action-btn accent" on:click={() => { showImportDialog = true; }}>Import</button>
                {#if discrepancyCount > 0}
                  <button class="panel-action-btn warn" on:click={() => { showAdjustDialog = true; }}>Adjust ({discrepancyCount})</button>
                {/if}
              {/if}
              <button class="panel-action-btn" on:click={refreshFloatingPanel}>Refresh</button>
            </div>
          </div>

          {#if $showMyOffers}
            <MyOffersView
              bind:this={myOffersRef}
              user={currentUser}
              sideFilter={panelSideFilter}
              on:edit={(e) => {
                const offer = e.detail;
                if (offer?.item_id) {
                  editOfferInline(offer);
                }
              }}
            />
          {:else if $showInventory}
            <InventoryPanel
              bind:this={inventoryPanelRef}
              user={currentUser}
              {allItems}
              on:sell={handleInventorySell}
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
    showImportDialog = false;
    // Refresh inventory panel if open
    if ($showInventory && inventoryPanelRef) {
      inventoryPanelRef.refresh();
    }
  }}
/>

<OfferAdjustDialog
  show={showAdjustDialog}
  on:close={() => { showAdjustDialog = false; }}
/>


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
    gap: 8px;
    background: var(--bg-color);
    box-shadow: -4px 0 20px rgba(0, 0, 0, 0.15);
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

  .panel-side-filter {
    display: flex;
    gap: 2px;
    background: var(--bg-color, rgba(0,0,0,0.05));
    border-radius: 6px;
    padding: 2px;
  }
  .panel-filter-btn {
    padding: 4px 12px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
    transition: all 0.15s ease;
  }
  .panel-filter-btn:hover {
    color: var(--text-color);
    background: var(--secondary-color);
  }
  .panel-filter-btn.active {
    color: var(--text-color);
    background: var(--secondary-color);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
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


  /* Action buttons inside last two columns */
  :global(.table-wrapper a) {
    text-decoration: none;
    display: block;
    width: 100%;
    height: 100%;
  }
  :global(.cell-button) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 2px 8px;
    text-align: center;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    line-height: 17px;
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  :global(.trade-btn) {
    font-size: 11px;
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
  }
  :global(.seller-link:hover) {
    text-decoration: underline;
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
    align-items: center;
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
  }

  .detail-title-right {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    flex: 0 0 auto;
    max-width: 100%;
  }

  .tier-filter {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex: 0 0 auto;
  }
  .tier-filter label {
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  .tier-select {
    flex: 0 0 auto;
    width: 100px;
    padding: 5px 8px;
    height: 30px;
    font-size: 12px;
  }

  /* Metric mini-cards */
  .detail-title-right .metric {
    flex: 0 1 auto;
    min-width: 70px;
    background: var(--hover-color);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.4;
    text-align: center;
  }

  .detail-title-right .action-btn {
    flex: 0 0 auto;
    white-space: nowrap;
  }

  .metric .metric-value {
    font-weight: 700;
    color: var(--text-color);
    font-size: 13px;
    display: block;
  }
  
  .exchange-metric .buy-value {
    color: var(--success-color, #16a34a);
  }
  .exchange-metric .sell-value {
    color: var(--error-color, #ef4444);
  }

  .history-controls {
    display: flex;
    flex-direction: column;
    gap: 3px;
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
    font-size: 11px;
  }
  .chart-toggle-btn.active {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
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
      gap: 6px;
    }
    .filter-select {
      flex: 1 1 auto;
      min-width: 120px;
    }
    .actions-right {
      flex: 1 0 100%;
      justify-content: flex-start;
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
    .filters {
      gap: 6px;
      padding: 6px 8px;
    }
    .filter-select {
      flex: 1 1 100%;
    }
    .detail-title {
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
      padding: 10px 12px;
    }
    .detail-title-name {
      font-size: 16px;
    }
    .detail-title-right {
      width: 100%;
      justify-content: flex-start;
      gap: 6px;
    }
  }

</style>

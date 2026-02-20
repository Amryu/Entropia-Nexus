<script>
  //@ts-nocheck
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { addToast } from '$lib/stores/toasts.js';
  import { apiCall } from '$lib/util.js';
  import {
    isBlueprint, isItemStackable, isLimited, isAbsoluteMarkup, isPercentMarkup,
    getMaxTT, getUnitTT, computeUnitPrice, formatPedRaw, formatMarkupValue,
    formatMarkupForItem, getTopCategory, itemTypeBadge
  } from '../../market/exchange/orderUtils';
  import { PLANETS } from '../../market/exchange/exchangeConstants.js';
  import InventoryImportDialog from '../../market/exchange/[[slug]]/[[id]]/InventoryImportDialog.svelte';
  import InventoryItemDialog from '../../market/exchange/[[slug]]/[[id]]/InventoryItemDialog.svelte';
  import ItemDetailDialog from './ItemDetailDialog.svelte';
  import ImportHistory from './ImportHistory.svelte';
  import VirtualGrid from './VirtualGrid.svelte';
  import ContainerTreeView from './ContainerTreeView.svelte';

  export let user = null;

  // --- Data state ---
  let inventoryItems = [];
  let allSlimItems = [];       // Flat array of all exchange slim items
  let itemLookup = new Map();  // item_id → slim item
  let userMarkups = new Map(); // item_id → markup value
  let importHistory = [];
  let userSellOrders = new Map(); // item_id → [{ id, planet, computed_state }]
  let containerNames = new Map(); // container_path → custom_name
  let loading = true;
  let error = null;

  // --- View state ---
  let viewMode = 'list';         // 'list' | 'grid' | 'tree'
  let selectedPlanet = 'all';
  let selectedCategory = 'all';
  let searchTerm = '';
  let markupFilter = 'all';     // 'all' | 'has-markup' | 'no-markup'
  let mobileSidebarOpen = false;

  // --- Dialogs ---
  let showImportDialog = false;
  let showItemDialog = false;
  let editingItem = null;
  let showDetailDialog = false;
  let detailItem = null;
  let showHistoryPanel = false;

  // --- Bulk selection ---
  let selectedItems = new Set();
  let showBulkMarkupDialog = false;
  let bulkMarkupValue = '';

  // --- Delta state ---
  let showDeltaPanel = false;
  let latestImport = null;
  let latestDeltas = [];
  let loadingDeltas = false;

  // --- Constants ---
  const ALL_CATEGORIES = [
    'Weapons', 'Armor', 'Tools', 'Enhancers', 'Clothes',
    'Blueprints', 'Materials', 'Consumables', 'Vehicles', 'Pets',
    'Skill Implants', 'Furnishings', 'Strongboxes', 'Other'
  ];

  // --- Init ---
  onMount(async () => {
    // Read view prefs from localStorage
    const VALID_VIEWS = ['list', 'grid', 'tree'];
    const stored = localStorage.getItem('nexus.inventory.viewMode');
    viewMode = VALID_VIEWS.includes(stored) ? stored : 'list';

    // Read filters from URL
    const params = $page.url.searchParams;
    if (params.get('planet')) selectedPlanet = params.get('planet');
    if (params.get('category')) selectedCategory = params.get('category');
    if (params.get('search')) searchTerm = params.get('search');
    const urlView = params.get('view');
    if (urlView && VALID_VIEWS.includes(urlView)) viewMode = urlView;
    if (params.get('markup')) markupFilter = params.get('markup');

    await loadData();
  });

  async function loadData() {
    loading = true;
    error = null;
    try {
      const [invRes, exchangeRes, markupRes, histRes, ordersRes, containerNamesRes] = await Promise.all([
        fetch('/api/users/inventory'),
        fetch('/api/market/exchange'),
        user?.verified ? fetch('/api/users/inventory/markups') : Promise.resolve(null),
        user?.verified ? fetch('/api/users/inventory/imports?limit=5') : Promise.resolve(null),
        user?.verified ? fetch('/api/market/exchange/orders') : Promise.resolve(null),
        user?.verified ? fetch('/api/users/inventory/containers') : Promise.resolve(null),
      ]);

      if (invRes.ok) {
        inventoryItems = await invRes.json();
      } else if (invRes.status === 401 || invRes.status === 403) {
        error = 'Please log in with a verified account to view your inventory.';
        loading = false;
        return;
      }

      if (exchangeRes.ok) {
        const categorized = await exchangeRes.json();
        // Flatten categorized items into a single array
        allSlimItems = flattenCategorized(categorized);
        itemLookup = new Map();
        for (const item of allSlimItems) {
          if (item?.i != null) itemLookup.set(item.i, item);
        }
      }

      if (markupRes?.ok) {
        const markups = await markupRes.json();
        userMarkups = new Map();
        for (const m of markups) {
          userMarkups.set(m.item_id, m.markup);
        }
      }

      if (histRes?.ok) {
        importHistory = await histRes.json();
        if (importHistory.length > 0) {
          latestImport = importHistory[0];
        }
      }

      if (ordersRes?.ok) {
        const orders = await ordersRes.json();
        userSellOrders = new Map();
        for (const o of orders) {
          if (o.type !== 'SELL' || o.state === 'closed' || o.computed_state === 'terminated') continue;
          const list = userSellOrders.get(o.item_id) || [];
          list.push(o);
          userSellOrders.set(o.item_id, list);
        }
      }

      if (containerNamesRes?.ok) {
        const names = await containerNamesRes.json();
        containerNames = new Map();
        for (const entry of names) {
          containerNames.set(entry.container_path, entry.custom_name);
        }
      }
    } catch (err) {
      console.error('Error loading inventory data:', err);
      error = 'Failed to load inventory data.';
    } finally {
      loading = false;
    }
  }

  function flattenCategorized(categorized) {
    const items = [];
    function walk(obj) {
      if (Array.isArray(obj)) {
        for (const item of obj) {
          if (item && typeof item === 'object' && item.i != null) items.push(item);
        }
      } else if (obj && typeof obj === 'object') {
        for (const val of Object.values(obj)) walk(val);
      }
    }
    walk(categorized);
    return items;
  }

  // --- URL sync ---
  function updateUrl() {
    const params = new URLSearchParams();
    if (selectedPlanet !== 'all') params.set('planet', selectedPlanet);
    if (selectedCategory !== 'all') params.set('category', selectedCategory);
    if (searchTerm) params.set('search', searchTerm);
    if (viewMode !== 'list') params.set('view', viewMode);
    if (markupFilter !== 'all') params.set('markup', markupFilter);
    const qs = params.toString();
    goto(`/account/inventory${qs ? '?' + qs : ''}`, { replaceState: true, keepFocus: true });
  }

  // --- Enriched items ---
  $: enrichedItems = inventoryItems.map(item => {
    const slim = itemLookup.get(item.item_id);
    const type = slim?.t || null;
    const category = getTopCategory(type);
    const maxTT = slim ? getMaxTT(slim) : null;
    const markup = userMarkups.get(item.item_id) ?? null;
    const marketPrice = slim?.w ?? slim?.m ?? null;

    // Compute TT value for this inventory item
    let ttValue = null;
    if (item.value != null) {
      ttValue = Number(item.value);
    } else if (maxTT != null) {
      ttValue = isItemStackable(slim) ? maxTT * item.quantity : maxTT;
    }

    // Compute total value: custom markup > market price > TT
    // For non-stackable condition items, use CurrentTT from inventory instead of MaxTT
    const orderLike = !isItemStackable(slim) && item.value != null
      ? { details: { CurrentTT: Number(item.value) } }
      : undefined;
    let totalValue = null;
    let valueSource = 'default'; // 'custom' | 'market' | 'default'
    if (markup != null && slim) {
      const unitPrice = computeUnitPrice(slim, markup, orderLike);
      if (unitPrice != null) {
        totalValue = isItemStackable(slim) ? unitPrice * item.quantity : unitPrice;
        valueSource = 'custom';
      }
    }
    if (valueSource === 'default' && marketPrice != null && slim) {
      const unitPrice = computeUnitPrice(slim, Number(marketPrice), orderLike);
      if (unitPrice != null && unitPrice > 0) {
        totalValue = isItemStackable(slim) ? unitPrice * item.quantity : unitPrice;
        valueSource = 'market';
      }
    }
    if (valueSource === 'default' && ttValue != null) {
      totalValue = ttValue;
    }

    // Sell order matching: check if item has active orders for matching planet
    const sellOrders = userSellOrders.get(item.item_id) || [];
    const matchingOrders = sellOrders.filter(o =>
      !o.planet || (item.container && item.container.includes(o.planet))
    );

    return {
      ...item,
      container: item.container || 'Carried',
      _slim: slim,
      _type: type,
      _category: category,
      _maxTT: maxTT,
      _markup: markup,
      _marketPrice: marketPrice,
      _ttValue: ttValue,
      _totalValue: totalValue,
      _valueSource: valueSource,
      _isAbsolute: slim ? isAbsoluteMarkup(slim) : true,
      _sellOrders: matchingOrders,
    };
  });

  // --- Filtering ---
  $: filteredItems = enrichedItems.filter(item => {
    // Planet filter
    if (selectedPlanet !== 'all' && item.container !== selectedPlanet) return false;

    // Category filter
    if (selectedCategory !== 'all' && item._category !== selectedCategory) return false;

    // Search
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      if (!item.item_name.toLowerCase().includes(term)) return false;
    }

    // Markup filter
    if (markupFilter === 'has-markup' && item._markup == null) return false;
    if (markupFilter === 'no-markup' && item._markup != null) return false;

    return true;
  });

  // --- Planet counts ---
  $: planetCounts = (() => {
    const counts = new Map();
    counts.set('all', enrichedItems.length);
    for (const item of enrichedItems) {
      counts.set(item.container, (counts.get(item.container) || 0) + 1);
    }
    return counts;
  })();

  // --- Available planets from inventory ---
  $: availablePlanets = (() => {
    const planets = new Set();
    for (const item of enrichedItems) {
      planets.add(item.container);
    }
    // Sort alphabetically but keep 'Carried' last
    return [...planets].sort((a, b) => {
      if (a === 'Carried') return 1;
      if (b === 'Carried') return -1;
      return a.localeCompare(b);
    });
  })();

  // --- Category counts (from filtered by planet) ---
  $: categoryCounts = (() => {
    const planetFiltered = selectedPlanet === 'all'
      ? enrichedItems
      : enrichedItems.filter(i => i.container === selectedPlanet);
    const counts = new Map();
    counts.set('all', planetFiltered.length);
    for (const item of planetFiltered) {
      const cat = item._category;
      counts.set(cat, (counts.get(cat) || 0) + 1);
    }
    return counts;
  })();

  // --- Summary values ---
  $: summaryTT = filteredItems.reduce((sum, item) => sum + (item._ttValue || 0), 0);
  $: summaryTotal = filteredItems.reduce((sum, item) => sum + (item._totalValue || 0), 0);
  $: summaryUnknown = filteredItems.filter(item => !item._slim).reduce((sum, item) => sum + (item._ttValue || 0), 0);
  $: summaryCount = filteredItems.length;
  $: summaryLabel = (() => {
    const parts = [];
    if (selectedPlanet !== 'all') parts.push(selectedPlanet);
    if (selectedCategory !== 'all') parts.push(selectedCategory);
    if (searchTerm) parts.push(`"${searchTerm}"`);
    return parts.length > 0 ? parts.join(' / ') : 'All Items';
  })();

  // --- View mode handlers ---
  function setViewMode(mode) {
    viewMode = mode;
    localStorage.setItem('nexus.inventory.viewMode', mode);
    updateUrl();
  }

  function selectPlanet(planet) {
    selectedPlanet = planet;
    updateUrl();
  }

  function selectCategory(cat) {
    selectedCategory = cat;
    updateUrl();
  }

  function handleSearch() {
    updateUrl();
  }

  // --- Image error tracking ---
  let failedImages = new Set();

  // --- Markup editing ---
  let editingMarkupId = null;
  let editingMarkupValue = '';
  let markupSaveTimer = null;

  function startMarkupEdit(item) {
    editingMarkupId = item.item_id;
    editingMarkupValue = item._markup != null ? String(item._markup) : '';
  }

  function handleMarkupInput() {
    clearTimeout(markupSaveTimer);
    markupSaveTimer = setTimeout(() => saveMarkup(), 400);
  }

  function isDefaultMarkup(val, itemId) {
    if (!Number.isFinite(val)) return true;
    const item = enrichedItems.find(i => i.item_id === itemId);
    if (!item) return false;
    return item._isAbsolute ? val === 0 : val === 100;
  }

  async function deleteMarkup(id) {
    try {
      const res = await fetch(`/api/users/inventory/markups/${id}`, { method: 'DELETE' });
      if (res.status === 429) {
        addToast('Too many markup updates. Please slow down.', 'warning');
        return;
      }
      if (!res.ok && res.status !== 404) {
        addToast('Failed to delete markup', 'error');
        return;
      }
      userMarkups.delete(id);
      userMarkups = userMarkups;
    } catch (err) {
      addToast('Failed to delete markup', 'error');
    }
  }

  async function saveMarkup() {
    const id = editingMarkupId;
    const val = parseFloat(editingMarkupValue);
    if (!id) return;

    if (isDefaultMarkup(val, id)) {
      if (userMarkups.has(id)) await deleteMarkup(id);
      return;
    }

    try {
      const res = await fetch('/api/users/inventory/markups', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: [{ item_id: id, markup: val }] }),
      });
      if (res.status === 429) {
        addToast('Too many markup updates. Please slow down.', 'warning');
        return;
      }
      if (!res.ok) {
        addToast('Failed to save markup', 'error');
        return;
      }
      userMarkups.set(id, val);
      userMarkups = userMarkups;
    } catch (err) {
      addToast('Failed to save markup', 'error');
    }
  }

  function finishMarkupEdit() {
    clearTimeout(markupSaveTimer);
    saveMarkup();
    editingMarkupId = null;
  }

  // --- Bulk markup ---
  function toggleSelectItem(id) {
    if (selectedItems.has(id)) {
      selectedItems.delete(id);
    } else {
      selectedItems.add(id);
    }
    selectedItems = selectedItems; // trigger reactivity
  }

  function selectAllVisible() {
    for (const item of filteredItems) {
      if (item.item_id > 0) selectedItems.add(item.item_id);
    }
    selectedItems = selectedItems;
  }

  function clearSelection() {
    selectedItems = new Set();
  }

  async function applyBulkMarkup() {
    const val = parseFloat(bulkMarkupValue);
    if (!Number.isFinite(val)) {
      addToast('Please enter a valid markup value', 'error');
      return;
    }

    const items = [...selectedItems].map(item_id => ({ item_id, markup: val }));
    try {
      const res = await fetch('/api/users/inventory/markups', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items }),
      });
      if (res.status === 429) {
        addToast('Too many markup updates. Please slow down.', 'warning');
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        addToast(data.error || 'Failed to save markups', 'error');
        return;
      }
      for (const { item_id, markup } of items) {
        userMarkups.set(item_id, markup);
      }
      userMarkups = userMarkups;
      showBulkMarkupDialog = false;
      selectedItems = new Set();
      addToast(`Markup set for ${items.length} items`, 'success');
    } catch (err) {
      addToast('Failed to save markups', 'error');
    }
  }

  // --- Import ---
  function handleImported() {
    showImportDialog = false;
    loadData();
    addToast('Inventory imported successfully', 'success');
  }

  // --- Container renaming ---
  async function handleSaveContainerName(e) {
    const { path, name, itemName } = e.detail;
    try {
      const res = await fetch('/api/users/inventory/containers', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ container_path: path, custom_name: name, item_name: itemName }),
      });
      if (res.status === 429) {
        addToast('Too many updates. Please slow down.', 'warning');
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        addToast(data.error || 'Failed to rename container', 'error');
        return;
      }
      containerNames.set(path, name);
      containerNames = containerNames;
    } catch {
      addToast('Failed to rename container', 'error');
    }
  }

  async function handleDeleteContainerName(e) {
    const { path } = e.detail;
    try {
      await fetch('/api/users/inventory/containers', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ container_path: path }),
      });
      containerNames.delete(path);
      containerNames = containerNames;
    } catch {
      // Non-critical — silently handle
    }
  }

  // --- Item dialog ---
  function openItemDialog(item) {
    detailItem = item;
    showDetailDialog = true;
  }

  function handleEditFromDetail() {
    showDetailDialog = false;
    editingItem = detailItem;
    showItemDialog = true;
  }

  // --- Delta loading ---
  async function loadLatestDeltas() {
    if (!latestImport) return;
    loadingDeltas = true;
    try {
      const res = await fetch(`/api/users/inventory/imports/${latestImport.id}/deltas`);
      if (res.ok) {
        latestDeltas = await res.json();
      }
    } catch (err) {
      console.error('Error loading deltas:', err);
    } finally {
      loadingDeltas = false;
    }
  }

  function toggleDeltaPanel() {
    showDeltaPanel = !showDeltaPanel;
    if (showDeltaPanel && latestDeltas.length === 0 && latestImport) {
      loadLatestDeltas();
    }
  }

  // --- Thumbnail helpers ---
  function getItemImageUrl(item, size) {
    if (!item._type || item.item_id <= 0) return null;
    return `/api/img/${item._type.toLowerCase()}/${item.item_id}?size=${size}`;
  }

  function sellBadge(row) {
    if (!row._sellOrders?.length) return '';
    return ' <span class="badge badge-subtle badge-success" title="Active sell order" style="font-size:0.6rem;padding:1px 4px;">SALE</span>';
  }

  // --- FancyTable columns ---
  const listColumns = [
    {
      key: 'item_name', header: 'Item', main: true, sortable: true, searchable: true, slotted: true,
      formatter: (v, row) => `${v}${row._slim ? itemTypeBadge(row._type) : ''}${sellBadge(row)}`,
    },
    {
      key: 'quantity', header: 'Qty', sortable: true, width: '60px',
      formatter: (v) => v?.toLocaleString() ?? '-',
    },
    {
      key: '_ttValue', header: 'TT Value', sortable: true, width: '90px', hideOnMobile: true,
      formatter: (v) => v != null ? formatPedRaw(v) : '-',
    },
    {
      key: '_markup', header: 'Markup', sortable: true, width: '90px', hideOnMobile: true, slotted: true,
      sortValue: (row) => row._markup ?? (row._isAbsolute ? 0 : 100),
    },
    {
      key: '_marketPrice', header: 'Market', sortable: true, width: '90px', hideOnMobile: true,
      cellClass: () => 'text-center',
      sortPhases: [
        { sortValue: (row) => row._slim?.b || 0, order: 'DESC', color: 'var(--success-color)' },
        { sortValue: (row) => row._slim?.b || 0, order: 'ASC', color: 'var(--success-color)' },
        { sortValue: (row) => row._slim?.s || 0, order: 'DESC', color: 'var(--error-color)' },
        { sortValue: (row) => row._slim?.s || 0, order: 'ASC', color: 'var(--error-color)' },
      ],
      formatter: (v, row) => {
        const s = row._slim?.s || 0;
        const b = row._slim?.b || 0;
        if (s === 0 && b === 0) return '<span class="text-muted">-</span>';
        const sv = row._slim?.sv ? formatPedRaw(row._slim.sv) + ' PED' : '0 PED';
        const bv = row._slim?.bv ? formatPedRaw(row._slim.bv) + ' PED' : '0 PED';
        const tooltip = `${s} Sell Order${s !== 1 ? 's' : ''} (${sv}) / ${b} Buy Order${b !== 1 ? 's' : ''} (${bv})`;
        const cell = `<span class="split-cell"><span class="split-l" style="color:var(--error-color)${s === 0 ? ';opacity:0.3' : ''}">${s}</span><span class="split-sep">/</span><span class="split-r" style="color:var(--success-color)${b === 0 ? ';opacity:0.3' : ''}">${b}</span></span>`;
        if (row.item_id > 0) return `<a href="/market/exchange/listings/${row.item_id}" class="market-link" title="${tooltip}">${cell}</a>`;
        return `<span title="${tooltip}">${cell}</span>`;
      },
    },
    {
      key: '_totalValue', header: 'Total', sortable: true, width: '90px',
      formatter: (v, row) => {
        if (v == null) return '<span class="text-muted">-</span>';
        const src = row._valueSource;
        if (src === 'custom') return `<span style="color:var(--accent-color)">${formatPedRaw(v)}</span>`;
        if (src === 'market') return `<span style="color:var(--text-color)">${formatPedRaw(v)}</span>`;
        if (src === 'default') return `<span class="text-muted">${formatPedRaw(v)}</span>`;
        return formatPedRaw(v);
      },
    },
    {
      key: 'container', header: 'Storage', sortable: true, width: '90px', hideOnMobile: true,
      formatter: (v) => v || '-',
    },
  ];

  const deltaColumns = [
    {
      key: 'delta_type', header: 'Change', sortable: true, width: '80px',
      formatter: (v) => `<span class="badge badge-subtle badge-${v === 'added' ? 'success' : v === 'removed' ? 'error' : 'warning'}">${v}</span>`,
    },
    { key: 'item_name', header: 'Item', main: true, sortable: true, searchable: true },
    {
      key: 'old_quantity', header: 'Old Qty', sortable: true, width: '70px',
      formatter: (v) => v != null ? v.toLocaleString() : '-',
    },
    {
      key: 'new_quantity', header: 'New Qty', sortable: true, width: '70px',
      formatter: (v) => v != null ? v.toLocaleString() : '-',
    },
    {
      key: 'container', header: 'Storage', sortable: true, width: '90px', hideOnMobile: true,
      formatter: (v) => v || '-',
    },
  ];

</script>

<div class="scroll-container">
  <div class="page-container">
    {#if error}
      <div class="inventory-error">
        <p>{error}</p>
        {#if !user}
          <a href="/login" class="btn btn-primary">Log in</a>
        {/if}
      </div>
    {:else}
      <div class="inventory-header">
        <h1>Inventory</h1>
        <div class="header-actions">
          <button class="btn btn-ghost btn-sm" on:click={toggleDeltaPanel}
            title={latestImport ? 'Show changes from last import' : 'Import your inventory first to see changes'}
            disabled={!latestImport}>
            Changes
            {#if latestImport?.summary}
              <span class="badge badge-subtle badge-info">
                {(latestImport.summary.added || 0) + (latestImport.summary.updated || 0) + (latestImport.summary.removed || 0)}
              </span>
            {/if}
          </button>
          <button class="btn btn-ghost btn-sm" on:click={() => showHistoryPanel = true}
            title={latestImport ? 'View import history and value chart' : 'Import your inventory first to see history'}
            disabled={!latestImport}>
            History
          </button>
          <button class="btn btn-primary btn-sm" on:click={() => showImportDialog = true}>
            Import
          </button>
        </div>
      </div>

      <!-- Summary bar -->
      <div class="summary-bar">
        <div class="summary-item">
          <span class="summary-label">Scope</span>
          <span class="summary-value">{summaryLabel}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Items</span>
          <span class="summary-value">{summaryCount.toLocaleString()}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">TT Value</span>
          <span class="summary-value">{formatPedRaw(summaryTT)} PED</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Est. Value</span>
          <span class="summary-value">{formatPedRaw(summaryTotal)} PED</span>
        </div>
        {#if summaryUnknown > 0}
          <div class="summary-item">
            <span class="summary-label">Unknown</span>
            <span class="summary-value">{formatPedRaw(summaryUnknown)} PED</span>
          </div>
        {/if}
      </div>

      <!-- Delta panel -->
      {#if showDeltaPanel && latestImport}
        <div class="delta-panel">
          <div class="delta-header">
            <span>Last import: {new Date(latestImport.imported_at).toLocaleString()} &mdash;
              <span class="badge badge-subtle badge-success">{latestImport.summary?.added || 0} added</span>
              <span class="badge badge-subtle badge-error">{latestImport.summary?.removed || 0} removed</span>
              <span class="badge badge-subtle badge-warning">{latestImport.summary?.updated || 0} changed</span>
            </span>
            <button class="btn btn-ghost btn-xs" on:click={() => showDeltaPanel = false}>Close</button>
          </div>
          {#if loadingDeltas}
            <p class="text-muted">Loading changes...</p>
          {:else if latestDeltas.length > 0}
            <div class="delta-table">
              <FancyTable
                columns={deltaColumns}
                data={latestDeltas}
                rowHeight={36}
                compact={true}
                emptyMessage="No changes in this import"
              />
            </div>
          {:else}
            <p class="text-muted">No changes in this import.</p>
          {/if}
        </div>
      {/if}

      <!-- Main layout -->
      <div class="inventory-layout">
        <!-- Sidebar -->
        <div class="inventory-sidebar" class:mobile-open={mobileSidebarOpen}>
          <!-- Planet selector -->
          <div class="sidebar-section">
            <h3 class="sidebar-heading">Storage</h3>
            <div class="planet-pills">
              <button
                class="planet-pill"
                class:active={selectedPlanet === 'all'}
                on:click={() => selectPlanet('all')}
              >All <span class="pill-count">{planetCounts.get('all') || 0}</span></button>
              {#each availablePlanets as planet}
                <button
                  class="planet-pill"
                  class:active={selectedPlanet === planet}
                  on:click={() => selectPlanet(planet)}
                >{planet} <span class="pill-count">{planetCounts.get(planet) || 0}</span></button>
              {/each}
            </div>
          </div>

          <!-- Category filter -->
          <div class="sidebar-section">
            <h3 class="sidebar-heading">Categories</h3>
            <div class="category-list">
              <button
                class="category-item"
                class:active={selectedCategory === 'all'}
                on:click={() => selectCategory('all')}
              >All <span class="cat-count">{categoryCounts.get('all') || 0}</span></button>
              {#each ALL_CATEGORIES.filter(c => categoryCounts.get(c) > 0) as cat}
                <button
                  class="category-item"
                  class:active={selectedCategory === cat}
                  on:click={() => selectCategory(cat)}
                >{cat} <span class="cat-count">{categoryCounts.get(cat) || 0}</span></button>
              {/each}
            </div>
          </div>
        </div>

        <!-- Mobile sidebar toggle -->
        <button class="sidebar-toggle" on:click={() => mobileSidebarOpen = !mobileSidebarOpen}>
          {mobileSidebarOpen ? '✕' : '☰'} Filters
        </button>

        <!-- Mobile sidebar overlay -->
        {#if mobileSidebarOpen}
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <div class="sidebar-overlay" on:click={() => mobileSidebarOpen = false}></div>
        {/if}

        <!-- Main content -->
        <div class="inventory-main">
          <!-- Toolbar -->
          <div class="inventory-toolbar">
            <div class="toolbar-left">
              <input
                type="text"
                class="search-input"
                placeholder="Search items..."
                bind:value={searchTerm}
                on:input={handleSearch}
              />
              <select class="markup-filter" bind:value={markupFilter} on:change={updateUrl}>
                <option value="all">All items</option>
                <option value="has-markup">Has markup</option>
                <option value="no-markup">No markup</option>
              </select>
            </div>
            <div class="toolbar-right">
              <!-- View toggle -->
              <div class="toggle-group">
                <button class="toggle-btn" class:active={viewMode === 'list'}
                  on:click={() => setViewMode('list')} title="List view">List</button>
                <button class="toggle-btn" class:active={viewMode === 'grid'}
                  on:click={() => setViewMode('grid')} title="Grid view">Grid</button>
                <button class="toggle-btn" class:active={viewMode === 'tree'}
                  on:click={() => setViewMode('tree')} title="Tree view">Tree</button>
              </div>
              <!-- Bulk actions -->
              {#if selectedItems.size > 0}
                <button class="btn btn-sm btn-accent" on:click={() => showBulkMarkupDialog = true}>
                  Set Markup ({selectedItems.size})
                </button>
                <button class="btn btn-sm btn-ghost" on:click={clearSelection}>Clear</button>
              {/if}
            </div>
          </div>

          <!-- Content area -->
          <div class="inventory-content" class:inventory-content-scroll={viewMode === 'grid' || viewMode === 'tree'}>
          {#if loading}
            <div class="loading-state">
              <div class="skeleton-rows">
                {#each Array(8) as _}
                  <div class="skeleton-row"></div>
                {/each}
              </div>
            </div>
          {:else if inventoryItems.length === 0}
            <div class="empty-state">
              <h2>No items in your inventory</h2>
              <p>Import your inventory from Entropia Universe to get started.</p>
              <button class="btn btn-primary" on:click={() => showImportDialog = true}>
                Import Inventory
              </button>
            </div>
          {:else if viewMode === 'list'}
            <!-- List view -->
            <FancyTable
              columns={listColumns}
              data={filteredItems}
              rowHeight={32}
              compact={true}
              emptyMessage="No items match your filters"
              defaultSort={{ column: 'item_name', order: 'ASC' }}
            >
              <svelte:fragment slot="cell" let:column let:row>
                {#if column.key === 'item_name'}
                  <!-- svelte-ignore a11y-click-events-have-key-events -->
                  <span class="item-name-link" on:click={() => openItemDialog(row)}>
                    {@html `${row.item_name}${row._slim ? itemTypeBadge(row._type) : ''}${sellBadge(row)}`}
                  </span>
                {:else if column.key === '_markup'}
                  {#if editingMarkupId === row.item_id}
                    <!-- svelte-ignore a11y-autofocus -->
                    <input
                      type="number"
                      class="markup-input"
                      bind:value={editingMarkupValue}
                      on:input={handleMarkupInput}
                      on:blur={finishMarkupEdit}
                      on:keydown={(e) => e.key === 'Enter' && finishMarkupEdit()}
                      autofocus
                      step="0.01"
                      placeholder={row._isAbsolute ? '+0' : '100%'}
                    />
                  {:else}
                    <!-- svelte-ignore a11y-click-events-have-key-events -->
                    <span
                      class="markup-cell"
                      class:has-markup={row._markup != null}
                      class:has-market={row._markup == null && row._marketPrice != null}
                      on:click={() => row.item_id > 0 && startMarkupEdit(row)}
                      title="Click to edit markup"
                    >
                      {#if row._markup != null}
                        {row._isAbsolute ? formatMarkupValue(row._markup, true) : formatMarkupValue(row._markup, false)}
                      {:else if row._marketPrice != null}
                        {row._isAbsolute ? formatMarkupValue(row._marketPrice, true) : formatMarkupValue(row._marketPrice, false)}
                      {:else}
                        <span class="text-muted">{row._isAbsolute ? '+0' : '100%'}</span>
                      {/if}
                    </span>
                  {/if}
                {/if}
              </svelte:fragment>
            </FancyTable>

          {:else if viewMode === 'grid'}
            <!-- Grid view (virtualized) -->
            <div class="grid-padding">
            <VirtualGrid items={filteredItems} minCardWidth={200} cardHeight={180} gap={12} let:item>
              <!-- svelte-ignore a11y-click-events-have-key-events -->
              <div class="grid-card" on:click={() => openItemDialog(item)}>
                <div class="grid-card-header">
                  {#if getItemImageUrl(item, 48) && !failedImages.has(item.item_id)}
                    <img
                      src={getItemImageUrl(item, 48)}
                      width="48" height="48"
                      loading="lazy"
                      alt=""
                      class="grid-card-thumb"
                      on:error={() => { failedImages.add(item.item_id); failedImages = failedImages; }}
                    />
                  {:else}
                    <span class="grid-card-thumb grid-card-thumb-placeholder"></span>
                  {/if}
                  <div class="grid-card-title">
                    <span class="grid-card-name" title={item.item_name}>{item.item_name}</span>
                    {#if item._category !== 'Other'}
                      <span class="badge badge-subtle badge-info grid-card-category">{item._category}</span>
                    {/if}
                  </div>
                </div>
                <div class="grid-card-body">
                  <div class="grid-stat">
                    <span class="grid-stat-label">Qty</span>
                    <span class="grid-stat-value">{item.quantity?.toLocaleString()}</span>
                  </div>
                  <div class="grid-stat">
                    <span class="grid-stat-label">TT</span>
                    <span class="grid-stat-value">{item._ttValue != null ? formatPedRaw(item._ttValue) : '-'}</span>
                  </div>
                  <div class="grid-stat">
                    <span class="grid-stat-label">MU</span>
                    <span class="grid-stat-value grid-mu-cell">
                      {#if editingMarkupId === item.item_id}
                        <!-- svelte-ignore a11y-autofocus -->
                        <input
                          type="number"
                          class="grid-mu-input"
                          bind:value={editingMarkupValue}
                          on:input={handleMarkupInput}
                          on:blur={finishMarkupEdit}
                          on:keydown={(e) => e.key === 'Enter' && finishMarkupEdit()}
                          on:click|stopPropagation
                          autofocus
                          step="0.01"
                          placeholder={item._isAbsolute ? '+0' : '100%'}
                        />
                      {:else}
                        <!-- svelte-ignore a11y-click-events-have-key-events -->
                        <span
                          class="markup-cell"
                          class:has-markup={item._markup != null}
                          class:has-market={item._markup == null && item._marketPrice != null}
                          on:click|stopPropagation={() => item.item_id > 0 && startMarkupEdit(item)}
                          title="Click to edit markup"
                        >
                          {#if item._markup != null}
                            {item._isAbsolute ? formatMarkupValue(item._markup, true) : formatMarkupValue(item._markup, false)}
                          {:else if item._marketPrice != null}
                            {item._isAbsolute ? formatMarkupValue(item._marketPrice, true) : formatMarkupValue(item._marketPrice, false)}
                          {:else}
                            <span class="text-muted">{item._isAbsolute ? '+0' : '100%'}</span>
                          {/if}
                        </span>
                      {/if}
                    </span>
                  </div>
                  <div class="grid-stat">
                    <span class="grid-stat-label">Value</span>
                    <span class="grid-stat-value" class:value-custom={item._valueSource === 'custom'} class:value-market={item._valueSource === 'market'} class:text-muted={item._valueSource === 'default' || item._totalValue == null}>
                      {item._totalValue != null ? formatPedRaw(item._totalValue) : '-'}
                    </span>
                  </div>
                </div>
                {#if item.container || item._sellOrders?.length}
                  <div class="grid-card-footer">
                    {#if item.container}<span>{item.container}</span>{/if}
                    {#if item._sellOrders?.length}
                      <span class="badge badge-subtle badge-success" style="font-size:0.6rem;padding:1px 4px;">SALE</span>
                    {/if}
                  </div>
                {/if}
              </div>
              <svelte:fragment slot="empty">
                <p class="text-muted grid-empty">No items match your filters</p>
              </svelte:fragment>
            </VirtualGrid>
            </div>

          {:else if viewMode === 'tree'}
            <!-- Tree view -->
            <ContainerTreeView
              items={filteredItems}
              {editingMarkupId}
              {editingMarkupValue}
              {containerNames}
              on:rowClick={(e) => openItemDialog(e.detail.row)}
              on:startMarkupEdit={(e) => startMarkupEdit(e.detail.item)}
              on:markupInput={(e) => { editingMarkupValue = e.detail.value; handleMarkupInput(); }}
              on:finishMarkupEdit={finishMarkupEdit}
              on:saveContainerName={handleSaveContainerName}
              on:deleteContainerName={handleDeleteContainerName}
            />
          {/if}
          </div>
        </div>
      </div>
    {/if}
  </div>
</div>

<!-- Import history panel -->
{#if showHistoryPanel}
  <ImportHistory on:close={() => showHistoryPanel = false} />
{/if}

<!-- Import dialog -->
{#if showImportDialog}
  <InventoryImportDialog
    show={showImportDialog}
    allItems={allSlimItems}
    on:close={() => showImportDialog = false}
    on:imported={handleImported}
  />
{/if}

<!-- Item detail dialog -->
{#if showDetailDialog && detailItem}
  <ItemDetailDialog
    show={showDetailDialog}
    item={detailItem}
    allItems={allSlimItems}
    on:close={() => { showDetailDialog = false; detailItem = null; }}
    on:edit={handleEditFromDetail}
  />
{/if}

<!-- Item edit dialog -->
{#if showItemDialog && editingItem}
  <InventoryItemDialog
    show={showItemDialog}
    item={editingItem}
    slimItem={itemLookup.get(editingItem.item_id)}
    on:close={() => { showItemDialog = false; editingItem = null; }}
    on:updated={(e) => {
      const idx = inventoryItems.findIndex(i => i.id === e.detail.id);
      if (idx >= 0) inventoryItems[idx] = { ...inventoryItems[idx], ...e.detail };
      inventoryItems = inventoryItems;
    }}
  />
{/if}

<!-- Bulk markup dialog -->
{#if showBulkMarkupDialog}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-overlay" on:click|self={() => showBulkMarkupDialog = false}>
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-header">
        <h3>Set Markup for {selectedItems.size} Items</h3>
        <button class="close-btn" on:click={() => showBulkMarkupDialog = false}>&times;</button>
      </div>
      <p class="text-muted">
        Markup type (% or +PED) is determined automatically per item type.
      </p>
      <div class="form-group">
        <label for="bulk-markup">Markup value</label>
        <input
          id="bulk-markup"
          type="number"
          step="0.01"
          bind:value={bulkMarkupValue}
          placeholder="e.g., 120 for 120% or 5 for +5 PED"
        />
      </div>
      <div class="actions">
        <button class="btn btn-ghost" on:click={() => showBulkMarkupDialog = false}>Cancel</button>
        <button class="btn btn-primary" on:click={applyBulkMarkup}>Apply</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .scroll-container {
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .page-container {
    max-width: 1200px;
    width: 100%;
    margin: 0 auto;
    padding: 1rem;
    padding-bottom: 1.5rem;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  /* Header */
  .inventory-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
    flex-shrink: 0;
  }

  .inventory-header h1 {
    margin: 0;
    font-size: 1.5rem;
  }

  .header-actions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  /* Summary bar */
  .summary-bar {
    display: flex;
    gap: 1.5rem;
    padding: 0.75rem 1rem;
    background: var(--secondary-color);
    border-radius: 8px;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
    flex-shrink: 0;
  }

  .summary-item {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }

  .summary-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    color: var(--text-muted);
    letter-spacing: 0.5px;
  }

  .summary-value {
    font-size: 0.95rem;
    font-weight: 500;
  }

  /* Delta panel */
  .delta-panel {
    background: var(--secondary-color);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.75rem;
    border-left: 3px solid var(--accent-color);
    flex-shrink: 0;
  }

  .delta-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
  }

  .delta-table {
    max-height: 300px;
    overflow-y: auto;
  }

  /* Layout */
  .inventory-layout {
    display: flex;
    gap: 1rem;
    position: relative;
    flex: 1;
    min-height: 0;
  }

  .inventory-sidebar {
    width: 220px;
    flex-shrink: 0;
    overflow-y: auto;
  }

  .inventory-main {
    flex: 1;
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  /* Sidebar sections */
  .sidebar-section {
    margin-bottom: 1rem;
  }

  .sidebar-heading {
    font-size: 0.75rem;
    text-transform: uppercase;
    color: var(--text-muted);
    letter-spacing: 0.5px;
    margin: 0 0 0.5rem 0;
  }

  /* Planet pills */
  .planet-pills {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .planet-pill {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.35rem 0.6rem;
    border: none;
    background: transparent;
    color: var(--text-color);
    cursor: pointer;
    border-radius: 4px;
    font-size: 0.85rem;
    text-align: left;
  }

  .planet-pill:hover {
    background: var(--hover-color);
  }

  .planet-pill.active {
    background: var(--accent-color);
    color: #fff;
  }

  .pill-count {
    font-size: 0.75rem;
    opacity: 0.7;
  }

  /* Category list */
  .category-list {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .category-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.3rem 0.6rem;
    border: none;
    background: transparent;
    color: var(--text-color);
    cursor: pointer;
    border-radius: 4px;
    font-size: 0.82rem;
    text-align: left;
  }

  .category-item:hover {
    background: var(--hover-color);
  }

  .category-item.active {
    background: var(--accent-color);
    color: #fff;
  }

  .cat-count {
    font-size: 0.7rem;
    opacity: 0.6;
  }

  /* Toolbar */
  .inventory-content {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .inventory-content-scroll {
    overflow-y: auto;
    padding-bottom: 1rem;
  }

  .inventory-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
    flex-shrink: 0;
  }

  .toolbar-left {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex: 1;
    min-width: 200px;
  }

  .toolbar-right {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .search-input {
    flex: 1;
    min-width: 150px;
    max-width: 300px;
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 0.85rem;
  }

  .search-input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .markup-filter {
    padding: 0.4rem 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 0.82rem;
  }

  /* Toggle groups */
  .toggle-group {
    display: flex;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .toggle-btn {
    padding: 0.35rem 0.6rem;
    border: none;
    border-right: 1px solid var(--border-color);
    background: var(--primary-color);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 0.78rem;
    white-space: nowrap;
  }

  .toggle-btn:last-child {
    border-right: none;
  }

  .toggle-btn:hover {
    background: var(--hover-color);
    color: var(--text-color);
  }

  .toggle-btn.active {
    background: var(--accent-color);
    color: #fff;
  }

  /* Item name link */
  .item-name-link {
    cursor: pointer;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: block;
  }

  .item-name-link:hover {
    text-decoration: underline;
  }

  /* Markup cell */
  .markup-cell {
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 3px;
    border: 1px dashed var(--border-color);
  }

  .markup-cell:hover {
    background: var(--hover-color);
    border-color: var(--accent-color);
  }

  .markup-cell.has-markup {
    color: var(--accent-color);
    border-color: transparent;
  }

  .markup-cell.has-market {
    color: var(--text-color);
    border-color: transparent;
  }

  .markup-cell.has-markup:hover {
    border-color: var(--accent-color);
  }

  .markup-input {
    width: 100%;
    padding: 2px 4px;
    box-sizing: border-box;
    border: 1px solid var(--accent-color);
    border-radius: 3px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 0.82rem;
    text-align: right;
  }

  /* Grid view */
  .grid-padding {
    padding: 0.5rem;
  }

  .grid-card {
    background: var(--secondary-color);
    border-radius: 8px;
    padding: 0.75rem;
    cursor: pointer;
    border: 1px solid transparent;
    transition: border-color 0.15s;
    height: 100%;
    box-sizing: border-box;
    overflow: hidden;
  }

  .grid-card:hover {
    border-color: var(--accent-color);
  }

  .grid-card-header {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .grid-card-thumb {
    border-radius: 4px;
    object-fit: cover;
    flex-shrink: 0;
    width: 48px;
    height: 48px;
  }

  .grid-card-thumb-placeholder {
    display: block;
    background: var(--primary-color);
    border: 1px solid var(--border-color);
  }

  .grid-card-title {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    min-width: 0;
  }

  .grid-card-name {
    font-size: 0.85rem;
    font-weight: 500;
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .grid-card-category {
    font-size: 0.65rem;
    flex-shrink: 0;
    align-self: flex-start;
  }

  .grid-card-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.35rem;
  }

  .grid-stat {
    display: flex;
    flex-direction: column;
  }

  .grid-stat-label {
    font-size: 0.65rem;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .grid-mu-cell {
    min-height: 1.2em;
  }

  .grid-mu-input {
    width: 100%;
    padding: 1px 3px;
    border: 1px solid var(--accent-color);
    border-radius: 3px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 0.78rem;
    text-align: right;
    box-sizing: border-box;
  }

  .grid-mu-input:focus {
    outline: none;
  }

  .grid-stat-value {
    font-size: 0.82rem;
  }

  .value-custom {
    color: var(--accent-color);
  }

  .value-market {
    color: var(--text-color);
  }

  .grid-card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.25rem;
    margin-top: 0.5rem;
    padding-top: 0.35rem;
    border-top: 1px solid var(--border-color);
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .grid-empty {
    grid-column: 1 / -1;
    text-align: center;
    padding: 2rem;
  }

  /* States */
  .loading-state {
    padding: 1rem 0;
  }

  .skeleton-rows {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .skeleton-row {
    height: 40px;
    background: var(--secondary-color);
    border-radius: 4px;
    animation: pulse 1.5s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 0.3; }
  }

  .empty-state {
    text-align: center;
    padding: 3rem 1rem;
  }

  .empty-state h2 {
    margin: 0 0 0.5rem;
  }

  .empty-state p {
    color: var(--text-muted);
    margin: 0 0 1.5rem;
  }

  .inventory-error {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--error-color);
  }

  /* Modal overlay */
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1000;
  }

  .modal {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    width: 400px;
    max-width: calc(100% - 32px);
    max-height: 90vh;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .modal-header h3 {
    margin: 0;
    font-size: 18px;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 22px;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
    flex-shrink: 0;
  }

  .close-btn:hover {
    color: var(--text-color);
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group label {
    display: block;
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-bottom: 0.25rem;
  }

  .form-group input {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--bg-color);
    color: var(--text-color);
    box-sizing: border-box;
  }

  .form-group input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 0.5rem;
  }

  /* Mobile sidebar */
  .sidebar-toggle {
    display: none;
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 60;
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 20px;
    background: var(--accent-color);
    color: #fff;
    cursor: pointer;
    font-size: 0.85rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }

  .sidebar-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 69;
  }

  /* Buttons */
  .btn {
    padding: 0.4rem 0.8rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
  }

  .btn-sm {
    padding: 0.3rem 0.6rem;
    font-size: 0.8rem;
  }

  .btn-xs {
    padding: 0.2rem 0.4rem;
    font-size: 0.75rem;
  }

  .btn-primary {
    background: var(--accent-color);
    color: #fff;
  }

  .btn-primary:hover {
    background: var(--accent-color-hover);
  }

  .btn-ghost {
    background: transparent;
    color: var(--text-muted);
    border: 1px solid var(--border-color);
  }

  .btn-ghost:hover {
    background: var(--hover-color);
    color: var(--text-color);
  }

  .btn-accent {
    background: var(--accent-color);
    color: #fff;
  }

  .text-muted {
    color: var(--text-muted);
  }

  /* Split cell for market orders */
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
  :global(.market-link) {
    text-decoration: none;
    color: inherit;
    display: block;
    padding: 2px 4px;
    border-radius: 3px;
  }
  :global(.market-link:hover) {
    background: var(--hover-color);
  }
  :global(.text-center) {
    justify-content: center;
  }

  /* Responsive */
  @media (max-width: 900px) {
    .sidebar-toggle {
      display: flex;
    }

    .sidebar-overlay {
      display: block;
    }

    .inventory-sidebar {
      position: fixed;
      top: 0;
      left: 0;
      bottom: 0;
      width: 260px;
      background: var(--primary-color);
      z-index: 70;
      padding: 1rem;
      overflow-y: auto;
      transform: translateX(-100%);
      transition: transform 0.3s ease;
      border-right: 1px solid var(--border-color);
    }

    .inventory-sidebar.mobile-open {
      transform: translateX(0);
    }

    .toolbar-left {
      min-width: 0;
    }

    .search-input {
      max-width: none;
    }
  }

  @media (max-width: 600px) {
    .summary-bar {
      gap: 1rem;
    }

    .toolbar-right {
      width: 100%;
      justify-content: flex-start;
    }
  }
</style>

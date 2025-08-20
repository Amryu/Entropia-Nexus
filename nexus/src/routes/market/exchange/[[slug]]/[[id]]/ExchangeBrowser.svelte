<script lang="ts">
  // @ts-nocheck
  import { onMount } from "svelte";

  import CategoryTree from "./CategoryTree.svelte";
  import Table from "$lib/components/Table.svelte";
  import OrderDialog from './OrderDialog.svelte';

  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { apiCall, getItemLink, hasItemTag } from "$lib/util.js";
  import { isBlueprint, isItemTierable, isLimited, itemHasCondition, getMaxTT } from '../../orderUtils';


  let searchTerm = "";
  let selectedCategory = "All";
  let selectedCategorySlug = "all";
  let selectedPlanet = "All Planets";
  let selectedLimited = "all";
  let selectedSex = "both";
  let filteredItems = [];
  let selectedItems = [];
  let tableRows = [];
  let loading = false;
  let showOrderDialog = false;
  let orderDialogType = null; // 'buy' | 'sell'
  let orderDialogRef;
  // Title bar filters for tierable items
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

  // Helpers to translate between display paths and slugs
  function slugFromDisplayPath(pathStr) {
    if (!pathStr || pathStr === "All") return "all";
    return pathStr
      .toLowerCase()
      .replace(/\s*>\s*/g, "-")
      .replace(/[^a-z0-9-]/g, "-");
  }
  function displayPathFromSlug(slug) {
    if (!slug || slug === "all") return "All";
    return slug
      .split("-")
      .map((p) => (p ? p[0].toUpperCase() + p.slice(1) : p))
      .join(" > ");
  }
  function gatherItemsAtPath(obj, parts) {
    if (!obj || !parts || parts.length === 0) return [];
    const toSlugKey = (k) =>
      String(k)
        .toLowerCase()
        .replace(/\s*>\s*/g, "-")
        .replace(/[^a-z0-9-]/g, "-");
    let node = obj;
    for (const p of parts) {
      if (!node) return [];
      if (Array.isArray(node)) return node;
      const key = Object.keys(node).find((k) => toSlugKey(k) === p);
      if (!key) return [];
      node = node[key];
    }
    if (Array.isArray(node)) return node;
    // If it's a nested object, flatten its arrays
    return flattenItems(node);
  }

  // Current route params
  $: routeSlug = $page?.params?.slug || "all";
  $: selectedItemKey = $page?.params?.id ?? "";
  $: isDetailView = selectedItemKey != null && selectedItemKey !== "";

  $: selectedItem = (() => {
      if (!isDetailView) return null;
      const key = selectedItemKey;
      const all = allItems || [];
      if (!Array.isArray(all) || all.length === 0) return null;
      if (/^\d+$/.test(String(key))) {
        const idNum = Number(key);
        const found = all.find((it) => it?.i === idNum) || null;
        console.log('[ExchangeBrowser] selectedItem set by id:', found);
        return found;
      }
      try {
        const name = decodeURIComponent(key);
        const found = all.find((it) => it?.n === name) || null;
        console.log('[ExchangeBrowser] selectedItem set by name:', found);
        return found;
      } catch {
        const found = all.find((it) => it?.n === key) || null;
        console.log('[ExchangeBrowser] selectedItem set by fallback:', found);
        return found;
      }
    })();

  // Build a root "All" node with every item flattened
  $: allItems = flattenItems(categorizedItems);
  $: categoriesWithAll = { all: allItems, ...categorizedItems };

  // Sync category selection from URL slug
  $: {
    const slug = routeSlug || "all";
    selectedCategorySlug = slug;
    const display = displayPathFromSlug(slug);
    selectedCategory = display;
    if (slug === "all") {
      selectedItems = allItems;
    } else {
      const parts = slug.split("-");
      selectedItems = gatherItemsAtPath(categorizedItems, parts);
    }
  }

  // Prefetch full item details for link building and MU rules
  $: (async () => {
      try {
        if (!selectedItem || !selectedItem?.i) {
          selectedItemDetails = null;
          console.log('[ExchangeBrowser] selectedItemDetails set to null (no selectedItem or no id)');
          return;
        }
        const it = await apiCall(window.fetch, `/items/${selectedItem.i}`);
        selectedItemDetails = it || null;
        console.log('[ExchangeBrowser] selectedItemDetails loaded:', selectedItemDetails);
      } catch (e) {
        selectedItemDetails = null;
        console.log('[ExchangeBrowser] selectedItemDetails error:', e);
      }
    })();

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

  // Map filtered items to table rows
  $: tableRows = (filteredItems || []).map((item) => ({
    detail: item,
    values: [item.n, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"],
  }));

  // Header for the main list view
  const tableHeader = {
    values: ["Item", "Median", "10%", "WAP", "Buys", "Sells", "Last Update"],
    widths: ["1fr", "120px", "90px", "90px", "100px", "100px", "140px"],
  };

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

  function handleCategorySelect(categoryPath, items) {
    selectedCategory = categoryPath;
    selectedCategorySlug = slugFromDisplayPath(categoryPath);
    selectedItems = Array.isArray(items) ? items : [];
    // Update URL to reflect category; clear any detail id to show listing
    goto(`/market/exchange/${selectedCategorySlug}`);
  }

  function formatPrice(value) {
    return value ? `${value.toFixed(2)} PED` : "N/A";
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

  // Load orders for detail view (placeholder wires)
  $: if (isDetailView) {
    loadOrders(selectedItemKey, selectedPlanet);
  }

  let ordersLoading = false;
  let ordersLoadedKey = "";
  async function loadOrders(itemId, planet) {
    const key = `${itemId}::${planet}`;
    if (ordersLoadedKey === key) return;
    ordersLoadedKey = key;
    ordersLoading = true;
    try {
      // TODO wire real API
      buyOrders = [];
      sellOrders = [];
    } catch (e) {
      buyOrders = [];
      sellOrders = [];
    } finally {
      ordersLoading = false;
    }
  }

  $: currentUser = $page?.data?.session?.user ?? null;

  function mapOrderRow(o) {
    const mine = currentUser && getSellerId(o) === currentUser.id;
    const cellStyle = mine
      ? "background-color: var(--hover-color); border-left: 2px solid #4caf50; border-right: 2px solid #4caf50;"
      : "";
    const qty = o?.Quantity ?? o?.quantity ?? 0;
    const unit = getPrice(o) ?? o?.UnitPrice ?? o?.unit_price ?? null;
    const ttUnit = o?.TTValue ?? o?.Value ?? o?.tt_value ?? null;
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
    const isCond = hasCondition(selectedItemDetails);
    const fmt = (x, digits = 2) =>
      typeof x === "number" && isFinite(x) ? x.toFixed(digits) : "N/A";
    const muText = isCond
      ? absMu != null
        ? `+${fmt(absMu)}`
        : "N/A"
      : muPct != null
        ? `${fmt(muPct, 1)}%`
        : "N/A";

    const type =
      selectedItemDetails?.Properties?.Type || selectedItem?.t || null;
    const isTierable = tierableTypes.has(type);
    const tier = o?.Tier ?? o?.tier ?? null;
    const tir = o?.TiR ?? o?.tir ?? o?.TIR ?? null;

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

    return { values, tdStyles };
  }

  $: filteredSellOrders = (sellOrders || [])
    .filter(
      (o) =>
        selectedPlanet === "All Planets" ||
        (o?.Planet || o?.planet) === selectedPlanet
    )
    .filter((o) => {
      if (!isItemTierable) return true;
      if (!isLimited) {
        if (selectedTierFilter === "All") return true;
        const t = Number(o?.Tier ?? o?.tier);
        return isFinite(t)
          ? Math.floor(t) === Number(selectedTierFilter)
          : true;
      } else {
        if (selectedTiRRange === "All") return true;
        const tir = Number(o?.TiR ?? o?.tir ?? o?.TIR);
        const [min, max] = (selectedTiRRange || "0-500").split("-").map(Number);
        return isFinite(tir) ? tir >= min && tir <= max : true;
      }
    })
    .filter((o) =>
      lastUpdateFilter === "all"
        ? true
        : classifyFreshness(getUpdatedAt(o)) === lastUpdateFilter
    )
    .sort((a, b) => (getPrice(a) ?? Infinity) - (getPrice(b) ?? Infinity))
    .map(mapOrderRow);

  $: filteredBuyOrders = (buyOrders || [])
    .filter(
      (o) =>
        selectedPlanet === "All Planets" ||
        (o?.Planet || o?.planet) === selectedPlanet
    )
    .filter((o) => {
      if (!isItemTierable) return true;
      if (!isLimited) {
        if (selectedTierFilter === "All") return true;
        const t = Number(o?.Tier ?? o?.tier);
        return isFinite(t)
          ? Math.floor(t) === Number(selectedTierFilter)
          : true;
      } else {
        if (selectedTiRRange === "All") return true;
        const tir = Number(o?.TiR ?? o?.tir ?? o?.TIR);
        const [min, max] = (selectedTiRRange || "0-500").split("-").map(Number);
        return isFinite(tir) ? tir >= min && tir <= max : true;
      }
    })
    .filter((o) =>
      lastUpdateFilter === "all"
        ? true
        : classifyFreshness(getUpdatedAt(o)) === lastUpdateFilter
    )
    .sort((a, b) => (getPrice(b) ?? -Infinity) - (getPrice(a) ?? -Infinity))
    .map(mapOrderRow);

  $: hasMySellOrder =
    currentUser &&
    (sellOrders || []).some((o) => getSellerId(o) === currentUser.id);
  $: hasMyBuyOrder =
    currentUser &&
    (buyOrders || []).some((o) => getSellerId(o) === currentUser.id);

  // (deduped above)

  function openOrderDialog(type) {
    // Use selectedItemDetails if available, else fallback to selectedItem
    const item = selectedItemDetails || selectedItem;
    if (!item) return;
    orderDialogType = type;
    // Wait for dialog to mount, then init
    setTimeout(() => {
      orderDialogRef?.initOrder(item, type, 'create');
      showOrderDialog = true;
    }, 0);
  }
  function closeOrderDialog() {
    showOrderDialog = false;
    orderDialogType = null;
  }

  function onSubmitOrder() {
    // Placeholder: wire to API when available
    closeOrderDialog();
  }

  // Detail tables header (adds Tier/TiR for tierable types)
  $: orderHeader = (() => {
    const base = {
      values: [
        "Qty",
        "Value",
        "MU",
        "Total",
        "Planet",
        "Seller",
        "Last Update",
      ],
      widths: ["80px", "120px", "90px", "120px", "150px", "1fr", "140px"],
    };
    const type =
      selectedItemDetails?.Properties?.Type || selectedItem?.t || null;
    const isTierable = tierableTypes.has(type);
    if (!isTierable) return base;
    return {
      values: ["Tier", "TiR", ...base.values],
      widths: ["60px", "80px", ...base.widths],
    };
  })();

  $: isBlueprintDetail = selectedItemDetails && isBlueprint(selectedItemDetails);
</script>

<div class="exchange-browser">
  <div class="content">
    <div class="sidebar">
      <h1 class="sidebar-title">Exchange</h1>
      <h3>Categories</h3>
      <div class="category-scroll">
        <CategoryTree
          categories={categoriesWithAll}
          onSelectCategory={handleCategorySelect}
          selectedPath={selectedCategory}
        />
      </div>
    </div>

    <div class="main-content">
      {#if !isDetailView}
        <div class="filters">
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
            <option>Calypso</option>
            <option>Arkadia</option>
            <option>Cyrene</option>
            <option>Rocktropia</option>
            <option>Next Island</option>
            <option>Monria</option>
            <option>Toulan</option>
            <option>Other</option>
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
            <button class="action-btn" title="My Offers">My Offers</button>
            <button class="action-btn" title="Import">Import</button>
          </div>
        </div>

        {#if tableRows.length > 0}
          <div class="table-wrapper">
            <Table
              header={tableHeader}
              data={tableRows}
              options={{ searchable: false, sortable: true, virtual: true }}
              style="width: 100%; height: 100%; text-align: left; white-space: nowrap; text-overflow: ellipsis;"
              on:rowClick={(evt) => {
                const d = evt?.detail;
                const row = d?.data ? d : d?.detail?.data ? d.detail : d;
                const item = row?.data?.detail ?? row?.detail ?? null;
                console.log("rowClick", { evtDetail: evt.detail, row, item });
                if (item?.n) {
                  const slug =
                    selectedCategory && selectedCategory !== "All"
                      ? slugFromDisplayPath(selectedCategory)
                      : "all";
                  goto(
                    `/market/exchange/${slug}/${encodeURIComponent(item.n)}`
                  );
                } else if (item?.i != null) {
                  const slug =
                    selectedCategory && selectedCategory !== "All"
                      ? slugFromDisplayPath(selectedCategory)
                      : "all";
                  goto(`/market/exchange/${slug}/${item.i}`);
                }
              }}
            />
            {#if loading}
              <div class="overlay"><div class="loader">Loading…</div></div>
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
          <select
            class="filter-select"
            bind:value={selectedPlanet}
            on:change={() => loadOrders(selectedItemKey, selectedPlanet)}
          >
            <option>All Planets</option>
            <option>Calypso</option>
            <option>Arkadia</option>
            <option>Cyrene</option>
            <option>Rocktropia</option>
            <option>Next Island</option>
            <option>Monria</option>
            <option>Toulan</option>
            <option>Other</option>
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
            <button
              class="action-btn"
              on:click={() => openOrderDialog("buy")}
              disabled={hasMyBuyOrder}
              title={hasMyBuyOrder
                ? "You already have a buy order for this item"
                : "Create Buy Order"}>Buy</button
            >
            <button
              class="action-btn"
              on:click={() => openOrderDialog("sell")}
              disabled={hasMySellOrder}
              title={hasMySellOrder
                ? "You already have a sell order for this item"
                : "Create Sell Order"}>Sell</button
            >
          </div>
        </div>
        <div class="detail-title">
          <button
            class="action-btn"
            on:click={() =>
              goto(`/market/exchange/${selectedCategorySlug || "all"}`)}
            title="Back to list">Back</button
          >
          <div class="detail-title-name" title={selectedItem?.n || ""}>
            {selectedItem?.n || ""}
          </div>
          {#if isItemTierable}
            {#if !isLimited}
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
          {#if isBlueprintDetail}
            <div class="tier-filter" title="Filter by QR range (Blueprints)">
              <label for="qrRangeSelect">QR</label>
              <select
                id="qrRangeSelect"
                bind:value={selectedQRRange}
                class="filter-select tier-select"
                disabled={selectedLimited === 'L'}
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
                >{typeof selectedItem?.m === "number"
                  ? selectedItem.m.toFixed(2)
                  : "N/A"}</span
              >
            </div>
            <div class="metric">
              10%:<br /><span class="metric-value"
                >{typeof selectedItem?.p === "number"
                  ? selectedItem.p.toFixed(2)
                  : "N/A"}</span
              >
            </div>
            <div class="metric">
              WAP:<br /><span class="metric-value"
                >{typeof selectedItem?.w === "number"
                  ? selectedItem.w.toFixed(2)
                  : "N/A"}</span
              >
            </div>
            <button
              class="action-btn"
              disabled={!selectedItemDetails && !selectedItem}
              on:click={() => {
                const item = selectedItemDetails || selectedItem;
                const link = item ? getItemLink(item) : null;
                if (link) window.open(link, "_blank");
              }}
              title="Open item page">Item Page</button>
          </div>
        </div>

        <div class="detail-wrapper">
          {#if tableMode !== "buy"}
            <div class="detail-table">
              <Table
                title={`Sell Orders${ordersLoading ? " (loading...)" : ""}`}
                header={orderHeader}
                data={filteredSellOrders}
                options={{ searchable: false, sortable: true }}
                style="width:100%; height:100%"
              />
            </div>
          {/if}
          {#if tableMode !== "sell"}
            <div class="detail-table">
              <Table
                title={`Buy Orders${ordersLoading ? " (loading...)" : ""}`}
                header={orderHeader}
                data={filteredBuyOrders}
                options={{ searchable: false, sortable: true }}
                style="width:100%; height:100%"
              />
            </div>
          {/if}
          {#if initialLoading}
            <div class="overlay">
              <div class="loader">Loading exchange…</div>
            </div>
          {/if}
        </div>

        <OrderDialog
          bind:this={orderDialogRef}
          show={showOrderDialog}
          on:close={closeOrderDialog}
          on:submit={onSubmitOrder}
        />
      {/if}
    </div>
  </div>
</div>

<style>
  .exchange-browser {
    padding: 12px 16px;
    width: 100%;
    box-sizing: border-box;
    height: calc(100vh - 82px); /* account for top menu height */
  }

  .search-input {
    width: 100%;
    padding: 10px;
    border: 1px solid var(--text-color);
    border-radius: 4px;
    font-size: 14px;
    background-color: var(--primary-color);
    color: var(--text-color);
    flex: 1 1 auto;
    min-width: 160px;
  }

  .content {
    display: flex;
    gap: 0;
    width: 100%;
    height: 100%; /* use available slot height under the top menu */
    box-sizing: border-box;
    min-height: 0;
  }

  .sidebar {
    flex: 0 0 280px;
    display: flex;
    flex-direction: column;
    background: var(--secondary-color);
    padding: 12px;
    border-radius: 4px;
    border: 1px solid var(--text-color);
    height: calc(100% - 12px);
    margin: 6px 6px 6px 0px; /* ensures 12px outer margins and 12px total between columns */
    box-sizing: border-box;
    min-height: 0;
  }

  .sidebar h3 {
    margin: 0 0 10px 0;
    color: var(--text-color);
    text-align: center;
  }

  .sidebar-title {
    color: var(--text-color);
    text-align: center;
    margin: 0 0 8px 0;
    font-size: 32px;
    line-height: 40px;
  }

  .category-scroll {
    flex: 1 1 auto;
    overflow: auto;
    min-height: 0;
  }

  .main-content {
    flex: 1;
    min-width: 0;
    position: relative;
    display: flex;
    flex-direction: column;
  }

  .filters {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 6px 0 6px 6px; /* align with table margins */
    flex-wrap: wrap;
  }

  .actions-right {
    margin-left: auto;
    display: flex;
    gap: 8px;
    flex: 1 0 auto;
    justify-content: flex-end;
  }

  .filter-select {
    padding: 10px;
    border: 1px solid var(--text-color);
    border-radius: 4px;
    background-color: var(--primary-color);
    color: var(--text-color);
    font-size: 14px;
    flex: 0 0 200px; /* fixed width so search scales */
  }
  
  .action-btn {
    padding: 10px;
    border: 1px solid var(--text-color);
    border-radius: 4px;
    background-color: var(--primary-color);
    color: var(--text-color);
    font-size: 14px;
    flex: 0 0 100px; /* half the dropdown width */
    height: 38px; /* match input/select height visually */
  }

  .table-wrapper {
    display: flex;
    overflow: hidden; /* match detail-wrapper */
    height: calc(100% - 54px); /* fill remaining below filters */
    width: calc(100% - 6px); /* match detail-wrapper width calc */
    margin: 6px 12px 6px 6px; /* match detail-wrapper margins */
    box-sizing: border-box;
    position: relative;
    flex: 1 1 auto; /* match detail-wrapper growth */
    /* Box styling to match .detail-table */
    background: var(--secondary-color);
    border: 1px solid var(--text-color);
    border-radius: 4px;
    padding: 8px;
    flex-direction: column;
  }

  .table-wrapper :global(table) {
    height: 100%;
  }

  /* Action buttons inside last two columns */
  :global(.table-wrapper a) {
    text-decoration: none;
    display: block;
    width: 100%;
    height: 100%;
  }
  :global(.cell-button) {
    display: block;
    width: 100%;
    height: 100%;
    text-align: center;
    background-color: var(--primary-color);
    border: 1px solid var(--text-color);
    line-height: 17px; /* match VirtualTable row cell height */
    color: var(--text-color);
  }

  .empty-state,
  .welcome-state {
    text-align: center;
    padding: 40px 20px;
    color: var(--text-color);
    opacity: 0.7;
  }

  .welcome-state h3 {
    color: var(--text-color);
    margin-bottom: 10px;
  }

  .overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.35);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 2;
  }

  .loader {
    padding: 8px 12px;
    border: 1px solid var(--text-color);
    background-color: var(--secondary-color);
    color: var(--text-color);
    border-radius: 4px;
    font-size: 14px;
  }

  .detail-wrapper {
    display: grid;
    grid-template-rows: 1fr 1fr;
    gap: 12px;
    overflow: hidden;
    height: calc(100% - 108px);
    width: calc(100% - 6px);
    margin: 12px 12px 6px 6px;
    box-sizing: border-box;
    flex: 1 1 auto;
  }

  .detail-table {
    background: var(--secondary-color);
    border: 1px solid var(--text-color);
    border-radius: 4px;
    padding: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .detail-table :global(table) {
    height: 100%;
  }

  .detail-title {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--secondary-color);
    border: 1px solid var(--text-color);
    border-radius: 4px;
    padding: 8px;
    margin: 6px 0 0 6px;
    min-width: 0; /* allow middle title to shrink */
    flex-wrap: wrap; /* allow right-side to wrap below title on small widths */
  }

  .detail-title-name {
    flex: 1 1 auto; /* take remaining space between back button and right tools */
    min-width: 0; /* enable text truncation */
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-weight: 600;
    padding: 0 4px;
    font-size: 24px; /* larger, per request */
    line-height: 1.25;
  }

  .detail-title-right {
    margin-left: auto; /* push to the far right when space allows */
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap; /* wrap metrics/buttons within this area if needed */
    flex: 0 0 auto; /* do not grow over the title */
    max-width: 100%; /* never overflow parent */
  }

  .tier-filter {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex: 0 0 auto; /* reserve its own width */
  }
  .tier-filter label {
    font-size: 12px;
    opacity: 0.8;
  }
  .tier-select {
    flex: 0 0 auto;
    width: 110px; /* compact to avoid pushing into metrics */
    padding: 6px 8px;
    height: 32px;
  }

  /* Metric blocks: allow shrinking and wrapping instead of forcing overflow */
  .detail-title-right .metric {
    flex: 0 1 auto;
    min-width: 80px;
  }

  .detail-title-right .action-btn {
    flex: 0 0 auto;
    white-space: nowrap;
  }

  .metric .metric-value {
    font-weight: 600;
    text-align: right;
  }

  .modal-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 3;
  }
  .modal {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--text-color);
    border-radius: 6px;
    padding: 16px;
    width: 420px;
    max-width: calc(100% - 32px);
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }
  .form-row {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 8px;
    align-items: center;
    margin: 8px 0;
  }
  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 12px;
  }
</style>

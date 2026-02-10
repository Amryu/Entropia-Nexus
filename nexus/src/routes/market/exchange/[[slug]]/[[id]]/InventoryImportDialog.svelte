<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { slide } from 'svelte/transition';
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { hasItemTag, removeItemTag } from '$lib/util.js';
  import { myOrders, inventory, enrichOrders } from '../../exchangeStore.js';
  import { formatPedRaw } from '../../orderUtils';

  export let show = false;
  /** Flattened item list from ExchangeBrowser for name→id resolution: [{i, n}, ...] */
  export let allItems = [];

  const dispatch = createEventDispatcher();
  const MAX_ITEMS = 30000;

  let step = 'paste'; // 'paste' | 'preview' | 'done'
  let rawInput = '';
  let parseError = null;
  let parsedItems = [];
  let unresolvedItems = [];
  let rawItemCount = 0;
  let importing = false;
  let importResult = null;
  let importError = null;
  let showHelp = false;
  let showUnresolved = false;
  let inputMode = 'text'; // 'text' | 'file'
  let fileInput;

  // Diff state (computed in preview)
  let diffSummary = { added: 0, changed: 0, removed: 0, unchanged: 0 };

  // Order coverage state (computed after import)
  let discrepancies = [];
  let checkingCoverage = false;
  let adjustingAll = false;
  let cancellingAll = false;

  // --- Name → ID resolution ---

  function normalizeName(name) {
    return name.replace(/\s+/g, ' ').trim().toLowerCase();
  }

  function buildNameLookup() {
    const map = new Map();
    for (const item of (allItems || [])) {
      if (item.i && item.n) {
        map.set(normalizeName(item.n), item.i);
      }
    }
    return map;
  }

  // --- Container hierarchy resolution ---

  function resolveStorageLocation(itemId, containerMap, visited) {
    if (!containerMap.has(itemId)) return null;
    if (visited.has(itemId)) return null; // cycle detection
    visited.add(itemId);

    const entry = containerMap.get(itemId);
    if (entry.containerRefId == null || !containerMap.has(entry.containerRefId)) {
      return entry.container; // return the root's storage location (STORAGE/CARRIED)
    }
    return resolveStorageLocation(entry.containerRefId, containerMap, visited);
  }

  function extractPlanet(storageLocation) {
    if (!storageLocation) return null;
    const match = storageLocation.match(/^STORAGE \(([^)]+)\)$/i);
    return match ? match[1].trim() : null;
  }

  // --- TSV parsing ---

  function parseTsvField(field) {
    // Handle quoted fields: "Pitbull Mk. 1 (C,L)" → Pitbull Mk. 1 (C,L)
    field = field.trim();
    if (field.startsWith('"') && field.endsWith('"')) {
      return field.slice(1, -1).replace(/""/g, '"');
    }
    return field;
  }

  function detectAndParseTsv(text) {
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    if (lines.length < 2) return null;

    // Check if the first line looks like a TSV header with expected columns
    const header = lines[0].split('\t');
    if (header.length < 3) return null;

    // Normalize header names to find column indices
    const headerMap = {};
    for (let i = 0; i < header.length; i++) {
      const h = header[i].trim().toLowerCase().replace(/[^a-z0-9]/g, '');
      headerMap[h] = i;
    }

    // Must have at least Name and Quantity columns
    const nameIdx = headerMap['name'] ?? headerMap['itemname'] ?? -1;
    const qtyIdx = headerMap['quantity'] ?? headerMap['qty'] ?? -1;
    if (nameIdx < 0 || qtyIdx < 0) return null;

    const idIdx = headerMap['id'] ?? -1;
    const valueIdx = headerMap['valueped'] ?? headerMap['value'] ?? -1;
    const containerIdx = headerMap['container'] ?? -1;
    const containerRefIdx = headerMap['containerrefid'] ?? headerMap['containerref'] ?? -1;

    const items = [];
    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split('\t');
      if (cols.length < Math.max(nameIdx, qtyIdx) + 1) continue;

      const name = parseTsvField(cols[nameIdx]);
      if (!name) continue;

      const qty = parseInt(cols[qtyIdx], 10);
      const value = valueIdx >= 0 ? parseFloat(cols[valueIdx]) : null;
      const container = containerIdx >= 0 ? parseTsvField(cols[containerIdx]) : null;
      const containerRefId = containerRefIdx >= 0 ? cols[containerRefIdx]?.trim() : null;
      const id = idIdx >= 0 ? parseInt(cols[idIdx], 10) : i;

      items.push({
        id: isFinite(id) ? id : i,
        item_name: name,
        quantity: isFinite(qty) ? qty : 1,
        value: isFinite(value) ? value : null,
        container: container || null,
        containerRefId: (containerRefId && containerRefId !== 'null') ? parseInt(containerRefId, 10) : null,
      });
    }

    return items.length > 0 ? items : null;
  }

  // --- Parse pipeline ---

  function handleParse() {
    parseError = null;
    parsedItems = [];
    unresolvedItems = [];
    rawItemCount = 0;

    const text = rawInput.trim();
    if (!text) {
      parseError = 'Please paste some data.';
      return;
    }

    // Try TSV first
    const tsvData = detectAndParseTsv(text);
    if (tsvData) {
      return processItems(tsvData);
    }

    try {
      let data = JSON.parse(text);

      // Handle wrapped formats
      if (data && !Array.isArray(data)) {
        if (Array.isArray(data.items)) data = data.items;
        else if (Array.isArray(data.inventory)) data = data.inventory;
        else if (Array.isArray(data.Items)) data = data.Items;
        else if (Array.isArray(data.Inventory)) data = data.Inventory;
        else {
          parseError = 'JSON must be an array of items or an object with an "items" array.';
          return;
        }
      }

      if (!Array.isArray(data) || data.length === 0) {
        parseError = 'No items found in the pasted data.';
        return;
      }

      if (data.length > MAX_ITEMS) {
        parseError = `Too many items (${data.length}). Maximum ${MAX_ITEMS.toLocaleString()} items per import.`;
        return;
      }

      processItems(data);
    } catch (e) {
      parseError = e.message;
    }
  }

  function processItems(data) {
    if (data.length > MAX_ITEMS) {
      parseError = `Too many items (${data.length}). Maximum ${MAX_ITEMS.toLocaleString()} items per import.`;
      return;
    }

    rawItemCount = data.length;

    // 1. Build container map for hierarchy resolution
    const containerMap = new Map();
    for (const raw of data) {
      if (raw.id != null) {
        const rawContainer = raw.container ?? raw.Container ?? null;
        containerMap.set(raw.id, {
          container: typeof rawContainer === 'string' ? rawContainer.trim() : null,
          containerRefId: raw.containerRefId ?? raw.container_ref_id ?? null,
        });
      }
    }

    // 2. Normalize items and resolve containers
    const normalized = [];
    for (let i = 0; i < data.length; i++) {
      const raw = data[i];
      const itemName = raw.item_name ?? raw.ItemName ?? raw.Name ?? raw.name ?? '';
      const quantity = raw.quantity ?? raw.Quantity ?? raw.qty ?? raw.Qty ?? 1;
      const value = raw.value ?? raw.Value ?? null;
      const instanceKey = raw.instance_key ?? raw.InstanceKey ?? raw.instanceKey ?? null;
      const details = raw.details ?? raw.Details ?? null;

      if (!itemName) continue; // skip empty-name entries (containers without items)

      // Skip blueprint books — not real tradeable items
      const trimmedName = String(itemName).trim();
      if (/\(Vol\.\s*\d+\)/.test(trimmedName) || trimmedName.startsWith('Blueprints:')) continue;

      // Resolve storage location (STORAGE/CARRIED)
      const containerRefId = raw.containerRefId ?? raw.container_ref_id ?? null;
      const explicitContainer = raw.container ?? raw.Container ?? null;
      let storageLocation = null;

      if (containerRefId != null) {
        // Item is inside another item — walk up the chain to find root storage
        storageLocation = resolveStorageLocation(containerRefId, containerMap, new Set());
      }
      if (!storageLocation && typeof explicitContainer === 'string') {
        // Item directly in STORAGE/CARRIED (no parent container)
        storageLocation = explicitContainer.trim() || null;
      }

      // Skip items currently on auction — not in player inventory
      if (storageLocation && storageLocation.toUpperCase() === 'AUCTION') continue;

      const planet = extractPlanet(storageLocation);

      normalized.push({
        item_name: String(itemName).replace(/\s+/g, ' ').trim(),
        quantity: Math.max(0, Number(quantity) || 0),
        value: value != null ? Number(value) : null,
        instance_key: instanceKey || null,
        details: details || null,
        container: planet || null,
        _planet: planet,
      });
    }

    // 3. Resolve name → item_id (before combining, so we know item types)
    const nameLookup = buildNameLookup();

    function resolveItemId(itemName) {
      const lookupName = normalizeName(itemName);
      let itemId = nameLookup.get(lookupName) ?? 0;
      if (itemId === 0 && (hasItemTag(itemName, 'M') || hasItemTag(itemName, 'F'))) {
        const stripped = removeItemTag(removeItemTag(itemName, 'M'), 'F');
        itemId = nameLookup.get(normalizeName(stripped)) ?? 0;
      }
      if (itemId === 0 && lookupName.endsWith(' pet')) {
        itemId = nameLookup.get(lookupName.slice(0, -4)) ?? 0;
      }
      if (itemId === 0 && lookupName.includes("'")) {
        itemId = nameLookup.get(lookupName.replace(/'/g, '')) ?? 0;
      }
      return itemId;
    }

    // Stackable item types by ID range (from api/endpoints/constants.js offsets)
    // Non-(L) blueprints are non-fungible (individual QR) and should not be stacked
    function isStackable(itemId, itemName) {
      if (itemId === 0) return false;
      if (itemId >= 1000000 && itemId < 2000000) return true;    // Materials
      if (itemId >= 6000000 && itemId < 7000000) {               // Blueprints
        return hasItemTag(itemName, 'L');                           // Only (L) blueprints stack
      }
      if (itemId >= 10000000 && itemId < 10200000) return true;  // Consumables, Capsules
      return false;
    }

    // 4. Combine all resolved items by (item_id, planet); keep unresolved individual
    const stackMap = new Map();
    const individuals = [];

    for (const item of normalized) {
      const itemId = resolveItemId(item.item_name);

      if (item.instance_key) {
        // Already has an instance key — keep as-is
        individuals.push({ ...item, _itemId: itemId });
        continue;
      }

      if (itemId > 0) {
        // Combine by (item_id, planet)
        const key = `${itemId}::${item._planet || ''}`;
        const stackable = isStackable(itemId, item.item_name);
        if (stackMap.has(key)) {
          const existing = stackMap.get(key);
          existing.quantity += item.quantity || 1;
          if (item.value != null) {
            existing.value = (existing.value || 0) + item.value;
          }
        } else {
          stackMap.set(key, {
            ...item,
            _itemId: itemId,
            quantity: item.quantity || 1,
            // Non-stackable items use planet-based instance_key for DB uniqueness
            instance_key: stackable ? null : `stack:${item._planet || 'inventory'}`,
          });
        }
      } else {
        // Unresolved: keep individual
        individuals.push({ ...item, _itemId: itemId });
      }
    }

    // 5. Build final resolved/unresolved lists
    const resolved = [];
    const unresolved = [];
    const allEntries = [...stackMap.values(), ...individuals];

    for (const item of allEntries) {
      const itemId = item._itemId;
      const entry = {
        item_id: itemId,
        item_name: item.item_name,
        quantity: item.quantity,
        value: item.value,
        instance_key: item.instance_key,
        details: item.details,
        container: item.container,
        _planet: item._planet,
      };
      if (itemId === 0) {
        unresolved.push(entry);
      } else {
        resolved.push(entry);
      }
    }

    parsedItems = resolved;
    // Deduplicate unresolved by name
    const seenNames = new Set();
    unresolvedItems = unresolved.filter(item => {
      const lower = item.item_name.toLowerCase();
      if (seenNames.has(lower)) return false;
      seenNames.add(lower);
      return true;
    });

    // 6. Compute diff against current inventory
    computeDiff();

    step = 'preview';
  }

  // --- Diff computation ---

  function diffKey(item) {
    return item.instance_key
      ? `${item.item_id}::${item.instance_key}`
      : `${item.item_id}::${item.container || ''}`;
  }

  function computeDiff() {
    const currentItems = $inventory || [];
    const currentMap = new Map();
    for (const item of currentItems) {
      currentMap.set(diffKey(item), item);
    }

    let added = 0, changed = 0, unchanged = 0;
    const newKeys = new Set();

    for (const item of parsedItems) {
      const key = diffKey(item);
      newKeys.add(key);

      const existing = currentMap.get(key);
      if (!existing) {
        item._status = 'new';
        added++;
      } else if (existing.quantity !== item.quantity) {
        item._status = 'changed';
        item._oldQty = existing.quantity;
        changed++;
      } else {
        item._status = 'same';
        unchanged++;
      }
    }

    // Items in current inventory but not in new import = will be removed
    let removed = 0;
    for (const [key] of currentMap) {
      if (!newKeys.has(key)) removed++;
    }

    diffSummary = { added, changed, removed, unchanged };
  }

  // --- Import ---

  async function handleImport() {
    importing = true;
    importError = null;
    importResult = null;

    try {
      const res = await fetch('/api/users/inventory', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: parsedItems, sync: true }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Import failed');
      }
      importResult = data;
      // Update the inventory store with the imported items
      inventory.set(parsedItems.map((item, i) => ({ ...item, id: i + 1 })));
      step = 'done';
      dispatch('imported', data);

      // Check order coverage
      checkingCoverage = true;
      await checkOrderCoverage();
      checkingCoverage = false;
    } catch (e) {
      importError = e.message;
    } finally {
      importing = false;
    }
  }

  // --- Order coverage checking ---

  async function checkOrderCoverage() {
    // Ensure orders are loaded
    let orders = $myOrders;
    if (!orders || orders.length === 0) {
      try {
        const res = await fetch('/api/market/exchange/orders');
        if (res.ok) {
          orders = enrichOrders(await res.json());
          myOrders.set(orders);
        }
      } catch {}
    }

    // Only check SELL orders
    const sellOrders = (orders || []).filter(o => o.type === 'SELL');
    if (sellOrders.length === 0) {
      discrepancies = [];
      return;
    }

    // Build inventory quantity map by item_id
    const invQtyMap = new Map();
    for (const item of parsedItems) {
      if (item.item_id > 0) {
        invQtyMap.set(item.item_id, (invQtyMap.get(item.item_id) || 0) + item.quantity);
      }
    }

    discrepancies = sellOrders
      .map(order => {
        const invQty = invQtyMap.get(order.item_id) || 0;
        if (order.quantity > invQty) {
          return {
            order,
            orderQty: order.quantity,
            invQty,
            deficit: order.quantity - invQty,
            item_name: order.details?.item_name || `Item #${order.item_id}`,
            _processing: false,
          };
        }
        return null;
      })
      .filter(Boolean);
  }

  // --- Discrepancy actions ---

  async function adjustOrder(disc) {
    disc._processing = true;
    discrepancies = discrepancies;
    try {
      const newQty = disc.invQty;
      if (newQty <= 0) {
        await cancelOrder(disc);
        return;
      }
      const res = await fetch(`/api/market/exchange/orders/${disc.order.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quantity: newQty,
          markup: disc.order.markup,
          planet: disc.order.planet,
          min_quantity: disc.order.min_quantity ? Math.min(disc.order.min_quantity, newQty) : null,
          details: disc.order.details,
        }),
      });
      if (!res.ok) throw new Error('Failed to adjust order');
      discrepancies = discrepancies.filter(d => d !== disc);
      refreshOrders();
    } catch (e) {
      disc._processing = false;
      discrepancies = discrepancies;
    }
  }

  async function cancelOrder(disc) {
    disc._processing = true;
    discrepancies = discrepancies;
    try {
      const res = await fetch(`/api/market/exchange/orders/${disc.order.id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to cancel order');
      discrepancies = discrepancies.filter(d => d !== disc);
      refreshOrders();
    } catch (e) {
      disc._processing = false;
      discrepancies = discrepancies;
    }
  }

  async function adjustAll() {
    adjustingAll = true;
    const toProcess = [...discrepancies];
    for (const disc of toProcess) {
      await adjustOrder(disc);
    }
    adjustingAll = false;
  }

  async function cancelAll() {
    cancellingAll = true;
    const toProcess = [...discrepancies];
    for (const disc of toProcess) {
      await cancelOrder(disc);
    }
    cancellingAll = false;
  }

  async function refreshOrders() {
    try {
      const res = await fetch('/api/market/exchange/orders');
      if (res.ok) myOrders.set(enrichOrders(await res.json()));
    } catch {}
  }

  // --- UI helpers ---

  const previewColumns = [
    { key: 'item_name', header: 'Item', main: true, width: '1fr', sortable: true, searchable: true },
    {
      key: 'quantity', header: 'Qty', width: '80px', sortable: true, searchable: false,
      formatter: (val, row) => {
        if (row?._status === 'changed' && row._oldQty != null) {
          return `<span style="text-decoration:line-through;opacity:0.5">${row._oldQty}</span> ${val}`;
        }
        return val ?? 0;
      }
    },
    {
      key: 'value', header: 'Value', width: '80px', sortable: true, searchable: false,
      formatter: (val) => val != null ? formatPedRaw(val) : '<span style="opacity:0.4">&mdash;</span>'
    },
    {
      key: '_planet', header: 'Planet', width: '100px', sortable: true, searchable: false,
      hideOnMobile: true,
      formatter: (val) => val || '<span style="opacity:0.4">Inventory</span>'
    },
    {
      key: '_status', header: 'Status', width: '70px', sortable: true, searchable: false,
      formatter: (val) => {
        if (val === 'new') return '<span class="badge badge-subtle badge-success">new</span>';
        if (val === 'changed') return '<span class="badge badge-subtle badge-warning">changed</span>';
        return '<span style="opacity:0.4">same</span>';
      }
    },
  ];

  function handleClose() {
    step = 'paste';
    rawInput = '';
    parseError = null;
    parsedItems = [];
    unresolvedItems = [];
    importResult = null;
    importError = null;
    discrepancies = [];
    showHelp = false;
    showUnresolved = false;
    inputMode = 'text';
    dispatch('close');
  }

  function handleBack() {
    if (step === 'preview') {
      step = 'paste';
      parsedItems = [];
      unresolvedItems = [];
    } else if (step === 'done') {
      handleClose();
    }
  }

  function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      rawInput = /** @type {string} */ (reader.result);
      handleParse();
    };
    reader.readAsText(file);
  }

  function handleDrop(e) {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      rawInput = /** @type {string} */ (reader.result);
      handleParse();
    };
    reader.readAsText(file);
  }

  function copyToClipboard(text) {
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
    } else {
      fallbackCopy(text);
    }
  }

  function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }

  function copyUnresolved() {
    const names = unresolvedItems.map(i => i.item_name).join('\n');
    copyToClipboard(names);
  }
</script>

{#if show}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class="modal-overlay"
    on:click={(e) => { if (e.target.classList.contains('modal-overlay')) handleClose(); }}
    on:keydown={(e) => { if (e.key === 'Escape') handleClose(); }}
  >
    <div class="modal" class:modal-wide={step === 'done' && discrepancies.length > 0}>
      <div class="modal-header">
        <h3 class="modal-title">
          {#if step === 'paste'}
            Import Inventory
          {:else if step === 'preview'}
            Preview Import ({parsedItems.length} item{parsedItems.length !== 1 ? 's' : ''})
          {:else}
            Import Complete
          {/if}
        </h3>
        <button class="close-btn" on:click={handleClose}>&times;</button>
      </div>

      {#if step === 'paste'}
        <!-- How to get items -->
        <button class="help-toggle" on:click={() => showHelp = !showHelp}>
          {showHelp ? '\u25BC' : '\u25B6'} How do I get my items?
        </button>

        {#if showHelp}
          <div class="help-panel" transition:slide={{ duration: 200 }}>
            <div class="help-method">
              <ol>
                <li>Go to <a href="https://account.entropiauniverse.com/account/inventory" target="_blank" rel="noopener noreferrer">account.entropiauniverse.com/account/inventory</a> and log in</li>
                <li>Click the <strong>"Copy to CSV"</strong> button</li>
                <li>Paste the copied data into the text box below</li>
              </ol>
            </div>
          </div>
        {/if}

        {#if inputMode === 'file'}
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div
            class="file-drop-zone"
            on:click={() => fileInput?.click()}
            on:dragover|preventDefault
            on:drop={handleDrop}
          >
            <input
              bind:this={fileInput}
              type="file"
              accept=".json,.tsv,.csv,.txt,application/json,text/tab-separated-values,text/csv,text/plain"
              on:change={handleFileUpload}
              style="display:none"
            />
            <div class="file-drop-label">
              Drop inventory file here or click to browse
            </div>
          </div>
        {:else}
          <textarea
            class="json-input"
            bind:value={rawInput}
            placeholder="Paste your inventory data here (TSV from Copy to CSV, or JSON)..."
            rows="10"
          ></textarea>
        {/if}
        {#if parseError}
          <div class="error-msg">{parseError}</div>
        {/if}
        <div class="modal-actions">
          <button class="btn-link" on:click={() => inputMode = inputMode === 'file' ? 'text' : 'file'}>
            {inputMode === 'file' ? 'Paste text instead' : 'Upload file instead'}
          </button>
          <div class="actions-right">
            <button class="btn-secondary" on:click={handleClose}>Cancel</button>
            {#if inputMode === 'text'}
              <button class="btn-primary" on:click={handleParse} disabled={!rawInput.trim()}>Parse</button>
            {/if}
          </div>
        </div>

      {:else if step === 'preview'}
        <div class="summary-bar">
          <span>{rawItemCount.toLocaleString()} raw items &rarr; {parsedItems.length.toLocaleString()} unique items after combining stacks</span>
        </div>

        <div class="diff-summary">
          {#if diffSummary.added > 0}
            <span class="diff-badge diff-added">{diffSummary.added} new</span>
          {/if}
          {#if diffSummary.changed > 0}
            <span class="diff-badge diff-changed">{diffSummary.changed} changed</span>
          {/if}
          {#if diffSummary.removed > 0}
            <span class="diff-badge diff-removed">{diffSummary.removed} removed</span>
          {/if}
          {#if diffSummary.unchanged > 0}
            <span class="diff-badge diff-unchanged">{diffSummary.unchanged} unchanged</span>
          {/if}
        </div>

        {#if unresolvedItems.length > 0}
          <div class="unresolved-header">
            <button class="help-toggle warn" on:click={() => showUnresolved = !showUnresolved}>
              {showUnresolved ? '\u25BC' : '\u25B6'} {unresolvedItems.length} item{unresolvedItems.length !== 1 ? 's' : ''} not in our database
            </button>
            {#if showUnresolved}
              <button class="copy-btn" on:click={copyUnresolved} title="Copy item names">Copy</button>
            {/if}
          </div>
          {#if showUnresolved}
            <div class="unresolved-list" transition:slide={{ duration: 150 }}>
              {#each unresolvedItems as item}
                <span class="unresolved-item">{item.item_name}</span>
              {/each}
            </div>
          {/if}
        {/if}

        <div class="preview-table">
          <FancyTable
            columns={previewColumns}
            data={parsedItems}
            rowHeight={32}
            compact={true}
            sortable={true}
            searchable={true}
            emptyMessage="No items to import"
          />
        </div>
        {#if importError}
          <div class="error-msg">{importError}</div>
        {/if}
        <div class="modal-actions">
          <button class="btn-secondary" on:click={handleBack}>Back</button>
          <button class="btn-primary" on:click={handleImport} disabled={importing || parsedItems.length === 0}>
            {importing ? 'Importing...' : `Import ${parsedItems.length.toLocaleString()} item${parsedItems.length !== 1 ? 's' : ''}`}
          </button>
        </div>

      {:else}
        <!-- Done step -->
        <div class="success-msg">
          {#if importResult}
            Added {importResult.added ?? 0}, updated {importResult.updated ?? 0}, removed {importResult.removed ?? 0} items
            ({importResult.total ?? parsedItems.length} total).
          {:else}
            Import complete.
          {/if}
        </div>

        <!-- Order coverage -->
        {#if checkingCoverage}
          <div class="coverage-loading">Checking sell order coverage...</div>
        {:else if discrepancies.length > 0}
          <div class="discrepancy-section">
            <h4 class="discrepancy-title">Sell orders exceeding inventory</h4>
            <p class="discrepancy-desc">
              These sell orders advertise more items than you currently have.
            </p>
            <div class="bulk-actions">
              <button
                class="btn-adjust"
                on:click={adjustAll}
                disabled={adjustingAll || cancellingAll}
              >Adjust All</button>
              <button
                class="btn-cancel"
                on:click={cancelAll}
                disabled={adjustingAll || cancellingAll}
              >Cancel All</button>
            </div>
            <div class="discrepancy-table">
              <table>
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Order</th>
                    <th>Inventory</th>
                    <th>Deficit</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {#each discrepancies as disc}
                    <tr>
                      <td class="disc-name">{disc.item_name}</td>
                      <td>{disc.orderQty}</td>
                      <td>{disc.invQty}</td>
                      <td class="disc-deficit">-{disc.deficit}</td>
                      <td class="disc-actions">
                        {#if disc._processing}
                          <span class="processing">...</span>
                        {:else}
                          <button class="disc-btn adjust" on:click={() => adjustOrder(disc)}
                            title={disc.invQty > 0 ? `Set to ${disc.invQty}` : 'Cancel (no inventory)'}>
                            {disc.invQty > 0 ? 'Adjust' : 'Cancel'}
                          </button>
                          {#if disc.invQty > 0}
                            <button class="disc-btn cancel" on:click={() => cancelOrder(disc)}>Cancel</button>
                          {/if}
                        {/if}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          </div>
        {:else if $myOrders.some(o => o.type === 'SELL')}
          <div class="coverage-ok">All sell orders are covered by your inventory.</div>
        {/if}

        <div class="modal-actions">
          <button class="btn-primary" on:click={handleClose} disabled={checkingCoverage}>Done</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
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
    width: 650px;
    max-width: calc(100% - 32px);
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
    overflow-y: auto;
  }
  .modal-wide {
    width: 750px;
  }
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }
  .modal-title {
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
  }
  .close-btn:hover { color: var(--text-color); }

  /* Help panel */
  .help-toggle {
    background: none;
    border: none;
    color: var(--accent-color);
    cursor: pointer;
    font-size: 13px;
    padding: 4px 0;
    text-align: left;
    margin-bottom: 8px;
  }
  .help-toggle:hover { text-decoration: underline; }
  .help-toggle.warn { color: var(--warning-color, #f59e0b); }
  .help-panel {
    background: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 12px;
    font-size: 13px;
    line-height: 1.6;
  }
  .help-method {
    margin-bottom: 12px;
  }
  .help-method:last-child {
    margin-bottom: 0;
  }
  .help-method strong {
    display: block;
    margin-bottom: 4px;
    color: var(--text-color);
  }
  .help-method ol {
    margin: 4px 0 0 0;
    padding-left: 20px;
  }
  .help-method ol li {
    margin-bottom: 6px;
  }
  .help-method ul {
    margin: 2px 0;
    padding-left: 16px;
    font-size: 12px;
  }
  .help-method a {
    color: var(--accent-color);
  }
  .copy-btn {
    flex-shrink: 0;
    padding: 4px 10px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--bg-color);
    color: var(--text-color);
    font-size: 12px;
    cursor: pointer;
  }
  .copy-btn:hover { background: var(--hover-color); }

  /* File drop zone */
  .file-drop-zone {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 120px;
    border: 2px dashed var(--border-color);
    border-radius: 6px;
    background: var(--bg-color);
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }
  .file-drop-zone:hover {
    border-color: var(--accent-color);
    background: var(--hover-color);
  }
  .file-drop-label {
    font-size: 14px;
    color: var(--text-muted);
    text-align: center;
    padding: 16px;
  }

  /* JSON input */
  .json-input {
    width: 100%;
    padding: 10px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    font-family: monospace;
    font-size: 12px;
    resize: vertical;
    box-sizing: border-box;
  }
  .json-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  /* Summary & diff */
  .summary-bar {
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 8px;
  }
  .diff-summary {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }
  .diff-badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
  }
  .diff-added { background: var(--success-bg); color: var(--success-color); }
  .diff-changed { background: var(--warning-bg); color: var(--warning-color); }
  .diff-removed { background: var(--error-bg); color: var(--error-color); }
  .diff-unchanged { background: var(--hover-color); color: var(--text-muted); }

  /* Unresolved items */
  .unresolved-header {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 4px;
  }
  .unresolved-list {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
    max-height: 120px;
    overflow-y: auto;
    padding: 8px;
    background: var(--hover-color);
    border-radius: 4px;
  }
  .unresolved-item {
    background: var(--warning-bg);
    color: var(--warning-color);
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 11px;
  }
  .unresolved-more {
    font-size: 11px;
    color: var(--text-muted);
    padding: 1px 6px;
  }

  /* Preview table */
  .preview-table {
    height: 350px;
    min-height: 200px;
    margin-bottom: 12px;
  }

  /* Messages */
  .error-msg {
    margin: 8px 0;
    padding: 0.75rem 1rem;
    background: var(--error-bg);
    border: 1px solid var(--error-color);
    border-radius: 4px;
    color: var(--error-color);
    font-size: 13px;
  }
  .success-msg {
    margin: 8px 0 12px 0;
    padding: 0.75rem 1rem;
    background: var(--success-bg);
    border: 1px solid var(--success-color);
    border-radius: 4px;
    color: var(--success-color);
    font-size: 14px;
    text-align: center;
  }
  .coverage-loading {
    margin: 8px 0;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    color: var(--text-muted);
    font-size: 13px;
    text-align: center;
  }

  .coverage-ok {
    margin: 8px 0;
    padding: 0.5rem 1rem;
    background: var(--success-bg);
    border-radius: 4px;
    color: var(--success-color);
    font-size: 13px;
    text-align: center;
  }

  /* Discrepancy section */
  .discrepancy-section {
    margin: 8px 0;
    padding: 12px;
    background: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
  }
  .discrepancy-title {
    margin: 0 0 4px 0;
    font-size: 14px;
    color: var(--warning-color, #f59e0b);
  }
  .discrepancy-desc {
    margin: 0 0 8px 0;
    font-size: 12px;
    color: var(--text-muted);
  }
  .bulk-actions {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
  }
  .btn-adjust, .btn-cancel {
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    border: 1px solid var(--border-color);
  }
  .btn-adjust {
    background: var(--warning-bg);
    color: var(--warning-color);
    border-color: var(--warning-color);
  }
  .btn-adjust:hover:not(:disabled) { opacity: 0.85; }
  .btn-cancel {
    background: var(--error-bg);
    color: var(--error-color);
    border-color: var(--error-color);
  }
  .btn-cancel:hover:not(:disabled) { opacity: 0.85; }
  .btn-adjust:disabled, .btn-cancel:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .discrepancy-table {
    max-height: 200px;
    overflow-y: auto;
  }
  .discrepancy-table table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .discrepancy-table th {
    text-align: left;
    padding: 4px 8px;
    border-bottom: 1px solid var(--border-color);
    font-weight: 500;
    color: var(--text-muted);
    font-size: 11px;
  }
  .discrepancy-table td {
    padding: 4px 8px;
    border-bottom: 1px solid var(--border-color);
  }
  .disc-name {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .disc-deficit {
    color: var(--error-color);
    font-weight: 600;
  }
  .disc-actions {
    display: flex;
    gap: 4px;
  }
  .disc-btn {
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 11px;
    cursor: pointer;
    border: 1px solid var(--border-color);
    background: transparent;
    color: var(--text-color);
  }
  .disc-btn.adjust {
    color: var(--warning-color);
    border-color: var(--warning-color);
  }
  .disc-btn.cancel {
    color: var(--error-color);
    border-color: var(--error-color);
  }
  .disc-btn:hover { opacity: 0.8; }
  .processing {
    color: var(--text-muted);
    font-size: 11px;
  }

  /* Actions */
  .modal-actions {
    display: flex;
    gap: 8px;
    justify-content: space-between;
    align-items: center;
    margin-top: 12px;
  }
  .actions-right {
    display: flex;
    gap: 8px;
  }
  .btn-link {
    background: none;
    border: none;
    color: var(--accent-color);
    font-size: 13px;
    cursor: pointer;
    padding: 0;
  }
  .btn-link:hover {
    text-decoration: underline;
  }
  .btn-primary, .btn-secondary {
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    border: 1px solid var(--border-color);
  }
  .btn-primary {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }
  .btn-primary:hover:not(:disabled) {
    background-color: var(--accent-color-hover);
  }
  .btn-primary:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
  .btn-secondary {
    background: transparent;
    color: var(--text-color);
  }
  .btn-secondary:hover {
    background: var(--hover-color);
  }

  @media (max-width: 600px) {
    .modal {
      padding: 1rem;
    }
    .snippet-row {
      flex-direction: column;
    }
    .disc-name {
      max-width: 120px;
    }
  }
</style>

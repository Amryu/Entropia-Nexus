<!--
  @component BlueprintMaterials
  Editable blueprint materials component with markup calculator.
  Supports add/edit/remove materials in wiki edit mode.
  Compact grid layout matching TieringEditor with markup source toggle and persistence.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { clampDecimals, getItemLink } from '$lib/util';
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';
  import { fetchExchangeWapByName, fetchInventoryMarkups, fetchInGamePrices } from '$lib/markupSources.js';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';
  import '$lib/style.css';

  

  
  /**
   * @typedef {Object} Props
   * @property {object} blueprint
   * @property {Array} Available materials for dropdown [{Id, Name, Properties} [availableMaterials]
   */

  /** @type {Props} */
  let { blueprint, availableMaterials = [] } = $props();

  const PREF_KEY = 'wiki.blueprintMarkups';
  const SAVE_DEBOUNCE_MS = 500;

  // Markup source toggle: 'custom' | 'inventory' | 'ingame' | 'exchange'
  let markupSource = $state('custom');
  let nameToWapMap = $state(new Map());
  let nameToIdMap = $state(new Map());
  let inventoryMarkupMap = $state(new Map());
  let ingameMarkupMap = $state(new Map());

  // Custom markups keyed by material name (persisted)
  let customMarkups = $state({});
  let saveTimer = null;
  let prefCache = null;

  function getMarkupInputValue(matName) {
    return String(customMarkups[matName] ?? 100);
  }

  function handleMarkupChange(matName, value) {
    const trimmed = value.trim();
    const num = parseFloat(trimmed);
    if (trimmed === '' || isNaN(num)) return;
    const clamped = Math.max(0, Math.min(100000, num));
    customMarkups[matName] = clamped;
    debounceSaveMarkups();
  }

  /**
   * Resolve the effective markup for a material based on the active source.
   * Falls back: selected source → custom value → 100
   */
  function getResolvedMarkup(matName) {
    if (markupSource === 'exchange') {
      return nameToWapMap.get(matName) ?? customMarkups[matName] ?? 100;
    }
    if (markupSource === 'ingame') {
      return ingameMarkupMap.get(matName) ?? customMarkups[matName] ?? 100;
    }
    if (markupSource === 'inventory') {
      const itemId = nameToIdMap.get(matName);
      const inv = itemId != null ? inventoryMarkupMap.get(itemId) : undefined;
      return inv ?? customMarkups[matName] ?? 100;
    }
    return customMarkups[matName] ?? 100;
  }

  // Persistence
  async function loadMarkups() {
    try {
      const res = await fetch(`/api/users/preferences/${encodeURIComponent(PREF_KEY)}`);
      if (!res.ok) return;
      const result = await res.json();
      prefCache = result?.data || {};
      if (prefCache._source) markupSource = prefCache._source === 'market' ? 'exchange' : prefCache._source;
      const loaded = {};
      for (const [key, value] of Object.entries(prefCache)) {
        if (key === '_source') continue;
        if (typeof value === 'number') loaded[key] = value;
      }
      customMarkups = loaded;
    } catch (e) {
      // Non-critical
    }
  }

  async function saveMarkups() {
    const toSave = {};
    for (const [name, value] of Object.entries(customMarkups)) {
      if (value !== 100) toSave[name] = value;
    }
    if (markupSource !== 'custom') toSave._source = markupSource;
    prefCache = toSave;
    try {
      await fetch('/api/users/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: PREF_KEY, data: toSave })
      });
    } catch (e) {
      // Non-critical
    }
  }

  function debounceSaveMarkups() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(saveMarkups, SAVE_DEBOUNCE_MS);
  }

  async function loadMarkupSourceData() {
    try {
      const { wapByName, nameToId } = await fetchExchangeWapByName();
      nameToWapMap = wapByName;
      nameToIdMap = nameToId;
    } catch { /* non-critical */ }
    try {
      inventoryMarkupMap = await fetchInventoryMarkups();
    } catch { /* not logged in or not verified */ }
    try {
      ingameMarkupMap = await fetchInGamePrices();
    } catch { /* non-critical */ }
  }

  onMount(() => {
    loadMarkups();
    loadMarkupSourceData();
    return () => {
      if (saveTimer) clearTimeout(saveTimer);
    };
  });

  // Calculate totals
  let totalTT = $derived((blueprint?.Materials ?? []).reduce((acc, mat) => {
    const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
    return acc + (matTT * (mat.Amount || 0));
  }, 0));

  let totalWithMarkup = $derived((() => {
    void (markupSource, nameToWapMap, inventoryMarkupMap, nameToIdMap, customMarkups);
    return (blueprint?.Materials ?? []).reduce((acc, mat) => {
      const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
      const matName = mat.Item?.Name || '';
      return acc + (matTT * (mat.Amount || 0) * getResolvedMarkup(matName) / 100);
    }, 0);
  })());

  let weightedAvgMU = $derived((() => {
    void (markupSource, nameToWapMap, inventoryMarkupMap, nameToIdMap, customMarkups);
    const sumTTxMU = (blueprint?.Materials ?? []).reduce((acc, mat) => {
      const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
      const tt = matTT * (mat.Amount || 0);
      const matName = mat.Item?.Name || '';
      return acc + (tt * getResolvedMarkup(matName));
    }, 0);
    return totalTT > 0 ? sumTTxMU / totalTT : 100;
  })());

  function getLineTT(mat) {
    const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
    return matTT * (mat.Amount || 0);
  }

  function getLineTotal(mat) {
    const matName = mat.Item?.Name || '';
    return getLineTT(mat) * getResolvedMarkup(matName) / 100;
  }

  // === Material CRUD Operations ===
  function updateMaterial(index, field, value) {
    const newMaterials = [...(blueprint?.Materials || [])];

    if (field === 'Item') {
      const selectedName = typeof value === 'string' ? value : value?.Name;
      const selectedMaterial = availableMaterials.find(m =>
        m.Id === value || m.Name === selectedName
      );
      if (selectedMaterial) {
        newMaterials[index] = {
          ...newMaterials[index],
          Item: selectedMaterial,
          ItemId: selectedMaterial.Id
        };
      } else {
        newMaterials[index] = {
          ...newMaterials[index],
          Item: selectedName ? { Name: selectedName } : { Name: '' },
          ItemId: null
        };
      }
    } else if (field === 'Amount') {
      newMaterials[index] = {
        ...newMaterials[index],
        Amount: parseFloat(value) || 0
      };
    }

    updateField('Materials', newMaterials);
  }

  function addMaterial() {
    const newMaterials = [...(blueprint?.Materials || []), { Item: { Name: '' }, ItemId: null, Amount: 1 }];
    updateField('Materials', newMaterials);
  }

  function removeMaterial(index) {
    const newMaterials = (blueprint?.Materials || []).filter((_, i) => i !== index);
    updateField('Materials', newMaterials);
  }

  let materialNames = $derived(availableMaterials.map(m => m.Name));
  let hasMaterials = $derived((blueprint?.Materials?.length > 0) || $editMode);
</script>

{#if hasMaterials}
  <div class="materials-wrapper">
    <!-- Markup Source Toggle -->
    {#if !$editMode && (blueprint?.Materials?.length > 0)}
      <div class="markup-source-toggle">
        <span class="markup-source-label">MU Source:</span>
        <div class="markup-source-buttons">
          <button class="source-btn" class:active={markupSource === 'custom'}
            onclick={() => { markupSource = 'custom'; debounceSaveMarkups(); }}>Custom</button>
          <button class="source-btn" class:active={markupSource === 'inventory'}
            disabled={inventoryMarkupMap.size === 0}
            onclick={() => { markupSource = 'inventory'; debounceSaveMarkups(); }}>Inventory</button>
          <button class="source-btn" class:active={markupSource === 'ingame'}
            disabled={ingameMarkupMap.size === 0}
            onclick={() => { markupSource = 'ingame'; debounceSaveMarkups(); }}>In-Game</button>
          <button class="source-btn" class:active={markupSource === 'exchange'}
            disabled={nameToWapMap.size === 0}
            onclick={() => { markupSource = 'exchange'; debounceSaveMarkups(); }}>Exchange</button>
        </div>
      </div>
    {/if}

    <div class="fancy-table-container">
      {#if $editMode}
        <!-- Edit mode -->
        <div class="table-header">
          <div class="header-row edit-mode">
            <div class="header-cell col-material">Ingredient</div>
            <div class="header-cell col-amount">Amount</div>
            <div class="header-cell col-actions"></div>
          </div>
        </div>
        <div class="table-body">
          {#each blueprint?.Materials ?? [] as material, index}
            <div class="table-row edit-mode" class:even={index % 2 === 0} class:odd={index % 2 === 1}>
              <div class="table-cell col-material">
                <SearchInput
                  value={material.Item?.Name || ''}
                  placeholder="Search material..."
                  apiEndpoint="/search/items"
                  displayFn={(item) => item?.Name || ''}
                  allowedTypes={['Material']}
                  allowedNames={materialNames}
                  validValues={materialNames}
                  onchange={(e) => updateMaterial(index, 'Item', e.value)}
                  onselect={(e) => updateMaterial(index, 'Item', e.data || e.value)}
                />
              </div>
              <div class="table-cell col-amount">
                <input type="number" class="amount-input" value={material.Amount}
                  min="0" step="1"
                  onchange={(e) => updateMaterial(index, 'Amount', e.target.value)} />
              </div>
              <div class="table-cell col-actions">
                <button class="btn-remove" onclick={() => removeMaterial(index)} title="Remove material">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            </div>
          {/each}
          <div class="add-row">
            <button class="btn-add" onclick={addMaterial}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Add Material
            </button>
          </div>
        </div>
      {:else}
        <!-- View mode -->
        <div class="table-header">
          <div class="header-row">
            <div class="header-cell col-material">Ingredient</div>
            <div class="header-cell col-tt mobile-hide">TT</div>
            <div class="header-cell col-amount">Amt</div>
            <div class="header-cell col-markup mobile-hide">MU %</div>
            <div class="header-cell col-cost">Total</div>
          </div>
        </div>
        <div class="table-body">
          {#each blueprint?.Materials ?? [] as material, index}
            {@const matName = material.Item?.Name || ''}
            {@const isFallback = markupSource !== 'custom' && (
              markupSource === 'exchange' ? !nameToWapMap.has(matName) :
              markupSource === 'ingame' ? !ingameMarkupMap.has(matName) :
              !inventoryMarkupMap.has(nameToIdMap.get(matName))
            )}
            <div class="table-row" class:even={index % 2 === 0} class:odd={index % 2 === 1}>
              <div class="table-cell col-material">
                <a href="{getItemLink(material.Item)}">{matName || 'Unknown'}</a>
              </div>
              <div class="table-cell col-tt mobile-hide">{clampDecimals(material.Item?.Properties?.Economy?.MaxTT || 0, 2, 8)}</div>
              <div class="table-cell col-amount">{material.Amount}</div>
              <div class="table-cell col-markup mobile-hide">
                {#if markupSource === 'custom'}
                  <input type="text" class="markup-input" inputmode="decimal"
                    value={getMarkupInputValue(matName)}
                    oninput={(e) => handleMarkupChange(matName, e.target.value)}
                    onblur={(e) => { e.target.value = getMarkupInputValue(matName); }} />
                {:else}
                  {@const resolved = getResolvedMarkup(matName)}
                  <span class="markup-value-readonly" class:is-fallback={isFallback}>
                    {resolved}
                  </span>
                  {#if isFallback}
                    <span class="markup-fallback-note" title="No {markupSource} data; using custom value">*</span>
                  {/if}
                {/if}
              </div>
              <div class="table-cell col-cost">{clampDecimals(getLineTotal(material), 2, 8)}</div>
            </div>
          {/each}
        </div>

        <!-- Desktop footer -->
        <div class="table-footer desktop-only">
          <div class="footer-row">
            <div class="footer-cell col-material label-cell">Sum:</div>
            <div class="footer-cell col-tt">{clampDecimals(totalTT, 2, 8)} PED</div>
            <div class="footer-cell col-amount"></div>
            <div class="footer-cell col-markup">{clampDecimals(weightedAvgMU, 1, 4)}%</div>
            <div class="footer-cell col-cost total">{clampDecimals(totalWithMarkup, 2, 8)} PED</div>
          </div>
        </div>
        <!-- Mobile footer -->
        <div class="table-footer mobile-only">
          <div class="footer-row">
            <div class="footer-cell col-material label-cell">TT Total</div>
            <div class="footer-cell col-amount"></div>
            <div class="footer-cell col-cost total">{clampDecimals(totalTT, 2, 8)} PED</div>
          </div>
        </div>
      {/if}
    </div>

    <div class="product-row">
      <span class="product-label">Product:</span>
      {#if blueprint?.Product?.Name}
        <a href={getItemLink(blueprint.Product)} class="product-link">{blueprint.Product.Name}</a>
      {:else}
        <span class="text-muted">N/A</span>
      {/if}
    </div>
  </div>
{:else}
  <div class="no-materials">
    <span class="text-muted">No materials defined</span>
  </div>
{/if}

<style>
  .materials-wrapper {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  /* FancyTable-style grid layout (compact, 32px rows) */
  .fancy-table-container {
    display: flex;
    flex-direction: column;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    font-size: 13px;
  }

  .table-header {
    flex-shrink: 0;
    background-color: var(--hover-color);
    border-bottom: 1px solid var(--border-color);
  }

  .header-row {
    display: grid;
    grid-template-columns: 1fr 110px 90px 110px 120px;
    align-items: stretch;
  }

  .header-row.edit-mode {
    grid-template-columns: 1fr 90px 40px;
  }

  .header-cell {
    padding: 6px 10px;
    font-weight: 600;
    color: var(--text-muted, #999);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    border-right: 1px solid var(--border-color);
    box-sizing: border-box;
  }

  .header-cell:last-child {
    border-right: none;
  }

  .table-body {
    flex-shrink: 0;
  }

  .table-row {
    display: grid;
    grid-template-columns: 1fr 110px 90px 110px 120px;
    align-items: stretch;
    border-bottom: 1px solid var(--border-color);
  }

  .table-row.edit-mode {
    grid-template-columns: 1fr 90px 40px;
  }

  .table-row:last-child {
    border-bottom: none;
  }

  .table-row.even {
    background-color: var(--secondary-color);
  }

  .table-row.odd {
    background-color: var(--primary-color);
  }

  .table-cell {
    padding: 4px 10px;
    color: var(--text-color);
    display: flex;
    align-items: center;
    border-right: 1px solid var(--border-color);
    box-sizing: border-box;
    min-height: 32px;
  }

  .table-cell:last-child {
    border-right: none;
  }

  .table-cell.col-tt,
  .table-cell.col-amount,
  .table-cell.col-cost {
    justify-content: flex-end;
    font-family: monospace;
  }

  .table-cell.col-markup {
    justify-content: center;
  }

  .table-cell.col-actions {
    justify-content: center;
  }

  .table-cell a {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .table-cell a:hover {
    text-decoration: underline;
  }

  /* Footer */
  .table-footer {
    flex-shrink: 0;
    background-color: var(--hover-color);
    border-top: 2px solid var(--border-color);
  }

  .footer-row {
    display: grid;
    grid-template-columns: 1fr 110px 90px 110px 120px;
    align-items: stretch;
    border-bottom: 1px solid var(--border-color);
  }

  .footer-row:last-child {
    border-bottom: none;
  }

  .footer-cell {
    padding: 6px 10px;
    font-weight: 600;
    color: var(--text-color);
    display: flex;
    align-items: center;
    border-right: 1px solid var(--border-color);
    box-sizing: border-box;
    font-size: 12px;
  }

  .footer-cell:last-child {
    border-right: none;
  }

  .footer-cell.label-cell {
    color: var(--text-muted);
    font-weight: 500;
  }

  .footer-cell.col-tt,
  .footer-cell.col-amount,
  .footer-cell.col-markup,
  .footer-cell.col-cost {
    justify-content: flex-end;
    font-family: monospace;
  }

  .footer-cell.total {
    color: var(--accent-color, #4a9eff);
  }

  /* Markup input */
  .markup-input {
    width: 80px;
    padding: 5px 8px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--bg-color);
    color: var(--text-color);
    font-size: 12px;
    text-align: right;
  }

  .markup-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .markup-value-readonly {
    font-size: 13px;
    color: var(--text-color);
    font-family: monospace;
  }

  .markup-value-readonly.is-fallback {
    opacity: 0.6;
  }

  .markup-fallback-note {
    font-size: 10px;
    color: var(--text-muted, #999);
    margin-left: 2px;
  }

  /* Markup source toggle */
  .markup-source-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    align-self: flex-end;
  }

  .markup-source-label {
    color: var(--text-muted, #999);
    font-size: 12px;
  }

  .markup-source-buttons {
    display: flex;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    overflow: hidden;
  }

  .source-btn {
    padding: 3px 8px;
    font-size: 11px;
    border: none;
    border-right: 1px solid var(--border-color, #555);
    background: var(--bg-color);
    color: var(--text-muted, #999);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .source-btn:last-child {
    border-right: none;
  }

  .source-btn:hover:not(:disabled) {
    background: var(--hover-color);
    color: var(--text-color);
  }

  .source-btn.active {
    background: var(--accent-color, #4a9eff);
    color: white;
  }

  .source-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* Amount input (edit mode) */
  .amount-input {
    width: 60px;
    padding: 4px 8px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 13px;
    text-align: left;
  }

  .amount-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  /* Remove button */
  .btn-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    padding: 0;
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--error-color, #ff6b6b);
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-remove:hover {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  /* Add material row */
  .add-row {
    padding: 8px 10px;
  }

  .btn-add {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 100%;
    padding: 8px 12px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-add:hover {
    background-color: var(--hover-color);
    color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
  }

  /* Product row */
  .product-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
  }

  .product-label {
    font-weight: 500;
    color: var(--text-muted, #999);
  }

  .product-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
    font-weight: 500;
  }

  .product-link:hover {
    text-decoration: underline;
  }

  .no-materials {
    padding: 16px;
    text-align: center;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
  }

  .text-muted {
    color: var(--text-muted, #999);
  }

  /* Desktop-only and mobile-only visibility */
  .mobile-only {
    display: none;
  }

  .table-footer.mobile-only {
    display: none;
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .mobile-hide {
      display: none !important;
    }

    .mobile-only {
      display: block;
    }

    .desktop-only,
    .table-footer.desktop-only {
      display: none !important;
    }

    .table-footer.mobile-only {
      display: block;
    }

    /* 3-column grid for mobile: Material, Amount, Total */
    .header-row,
    .table-row {
      grid-template-columns: 1fr 90px 110px;
    }

    .table-footer.mobile-only .footer-row {
      grid-template-columns: 1fr 90px 110px;
    }

    .header-cell {
      padding: 6px 8px;
      font-size: 11px;
    }

    .table-cell {
      padding: 4px 8px;
      font-size: 12px;
    }

    .footer-cell {
      padding: 6px 8px;
      font-size: 12px;
    }

  }
</style>

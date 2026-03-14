<!--
  @component TieringEditor
  Generic tiering editor component for items with tier upgrades.
  Supports: Weapon, ArmorSet, MedicalTool, Finder, Excavator
  Shows materials needed per tier with markup calculator.
  Extrapolates missing tiers from known data.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { clampDecimals, getTypeLink } from '$lib/util';
  import {
    genericMats,
    weaponMats,
    armorMats,
    medicalToolMats,
    finderMats,
    excavatorMats,
    matValues,
    getTierMaterial
  } from '$lib/tieringUtil.js';
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';
  import { fetchExchangeWapByName, fetchInventoryMarkups, fetchInGamePrices, saveInventoryMarkup } from '$lib/markupSources.js';
  import MarkupSourceHelp from './MarkupSourceHelp.svelte';

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {object} [entity]
   * @property {string} [entityType]
   * @property {Array} [tierInfo]
   * @property {boolean} [compact]
   * @property {number} [setPieceCount]
   */

  /** @type {Props} */
  let {
    entity = null,
    entityType = 'Weapon',
    tierInfo = [],
    compact = false,
    setPieceCount = 1
  } = $props();

  const MAX_TIERS = 10;

  // Display sort priorities for tier materials
  // Order: Material1 (ore), Material2 (enmatter), Pile of XXX, Blazar Fragment, Tier Component
  const MAT_SORT_MATERIAL1 = 0;
  const MAT_SORT_MATERIAL2 = 1;
  const MAT_SORT_GEM = 2;
  const MAT_SORT_BLAZAR = 3;
  const MAT_SORT_COMPONENT = 4;
  const MAT_SORT_UNKNOWN = 5;

  // Classify a material by name to determine its display sort order
  function classifyMaterial(matName) {
    if (!matName || matName === '<Unknown Material>') return MAT_SORT_UNKNOWN;
    if (matName === 'Blazar Fragment') return MAT_SORT_BLAZAR;
    if (matName.startsWith('Pile of ')) return MAT_SORT_GEM;
    if (/^Tier \d+ Component$/.test(matName)) return MAT_SORT_COMPONENT;
    if (materialArrays?.Material1?.includes(matName)) return MAT_SORT_MATERIAL1;
    if (materialArrays?.Material2?.includes(matName)) return MAT_SORT_MATERIAL2;
    return MAT_SORT_UNKNOWN;
  }

  // Get material arrays based on entity type
  function getMaterialArrays(type) {
    switch (type) {
      case 'Weapon':
        return weaponMats;
      case 'ArmorSet':
        return armorMats;
      case 'MedicalTool':
        return medicalToolMats;
      case 'Finder':
        return finderMats;
      case 'Excavator':
        return excavatorMats;
      default:
        return weaponMats;
    }
  }


  // Format PED values - avoid negative zero and ensure consistent decimals
  function formatPED(value) {
    if (value === null || value === undefined) return 'N/A';
    // Round to avoid floating point issues, then handle negative zero
    const rounded = Math.round(value * 100) / 100;
    const result = Object.is(rounded, -0) ? 0 : rounded;
    return result.toFixed(2);
  }

  const DEFAULT_MARKUPS = [null, null, null, null, null];
  const PREF_KEY = 'wiki.tierMarkups';
  const SAVE_DEBOUNCE_MS = 500;

  // Selected tier for material display
  let selectedTier = $state(1);

  // Per-tier markups: { [tierNum]: [mu1, mu2, mu3, mu4, mu5] }
  let allMarkups = $state({});
  let saveTimer = null;
  let prefCache = null;

  // Markup source toggle: 'custom' | 'inventory' | 'ingame' | 'exchange'
  let markupSource = $state('custom');
  let nameToWapMap = $state(new Map());
  let nameToIdMap = $state(new Map());
  let inventoryMarkupMap = $state(new Map());
  let ingameMarkupMap = $state(new Map());
  let showMuHelp = $state(false);
  let editingMarkup = $state(null); // { idx, matName } for click-to-edit

  function autofocus(node) { node.focus(); node.select(); }

  /**
   * Resolve the effective markup for a material based on the active source.
   * Custom falls back: custom → inventory → in-game → exchange → 100
   */
  function getResolvedMarkup(matName, idx, tierMarkups) {
    const mu = tierMarkups || markups;
    const itemId = nameToIdMap.get(matName);
    const inv = itemId != null ? inventoryMarkupMap.get(itemId) : undefined;
    const igm = ingameMarkupMap.get(matName);
    const exc = nameToWapMap.get(matName);

    if (markupSource === 'exchange') return exc ?? 100;
    if (markupSource === 'ingame') return igm ?? 100;
    if (markupSource === 'inventory') return inv ?? 100;
    // Custom: custom → inventory → in-game → exchange → 100
    return mu[idx] ?? inv ?? igm ?? exc ?? 100;
  }

  /**
   * Determine the source badge for a resolved value in custom mode.
   * Returns null if the value comes from the custom setting itself.
   */
  function getCustomFallbackSource(matName, idx, tierMarkups) {
    const mu = tierMarkups || markups;
    if (mu[idx] != null) return null;
    const itemId = nameToIdMap.get(matName);
    const inv = itemId != null ? inventoryMarkupMap.get(itemId) : undefined;
    if (inv != null) return 'INV';
    if (ingameMarkupMap.get(matName) != null) return 'IGM';
    if (nameToWapMap.get(matName) != null) return 'EXC';
    return null;
  }

  function handleMarkupInput(event, idx) {
    const value = event.target.value;
    const num = parseFloat(value);
    if (!isNaN(num) && num >= 100) {
      if (!allMarkups[selectedTier]) {
        allMarkups[selectedTier] = [...DEFAULT_MARKUPS];
      }
      allMarkups[selectedTier][idx] = num;
      debounceSaveMarkups();
    }
  }

  function startEdit(idx, matName) {
    if (markupSource !== 'custom' && markupSource !== 'inventory') return;
    editingMarkup = { idx, matName };
  }

  function commitEdit(event, idx, matName) {
    const value = event.target.value;
    const num = parseFloat(value);
    editingMarkup = null;
    if (isNaN(num) || num < 0) return;
    const clamped = Math.min(100000, num);

    if (markupSource === 'inventory') {
      const itemId = nameToIdMap.get(matName);
      if (itemId == null) return;
      inventoryMarkupMap.set(itemId, clamped);
      inventoryMarkupMap = new Map(inventoryMarkupMap);
      saveInventoryMarkup(itemId, clamped);
    } else {
      // Custom mode
      if (clamped >= 100) handleMarkupInput(event, idx);
    }
  }

  function handleEditKeydown(event, idx, matName) {
    if (event.key === 'Enter') {
      event.target.blur();
    } else if (event.key === 'Escape') {
      editingMarkup = null;
    }
  }

  // Persistence: save/load markups to user preferences (keyed by entity type, not individual item)
  async function loadMarkups() {
    if (!entityType) return;
    try {
      const res = await fetch(`/api/users/preferences/${encodeURIComponent(PREF_KEY)}`);
      if (!res.ok) return;
      const result = await res.json();
      prefCache = result?.data || {};
      const stored = prefCache[entityType];
      if (stored) {
        // Load markup source preference
        if (stored._source) markupSource = stored._source === 'market' ? 'exchange' : stored._source;
        const loaded = {};
        for (const [tier, values] of Object.entries(stored)) {
          if (tier === '_source') continue;
          if (Array.isArray(values)) {
            loaded[Number(tier)] = [...values];
          }
        }
        allMarkups = loaded;
      }
    } catch (e) {
      // Non-critical — use defaults
    }
  }

  async function saveMarkups() {
    if (!entityType) return;
    const toSave = {};
    for (const [tier, values] of Object.entries(allMarkups)) {
      if (values.some((v, i) => v !== DEFAULT_MARKUPS[i])) {
        toSave[tier] = values;
      }
    }
    if (markupSource !== 'custom') {
      toSave._source = markupSource;
    }
    const data = prefCache || {};
    if (Object.keys(toSave).length > 0) {
      data[entityType] = toSave;
    } else {
      delete data[entityType];
    }
    prefCache = data;
    try {
      await fetch('/api/users/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: PREF_KEY, data })
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

  // Full set toggle for armor
  let fullSet = $state(false);






  // Extrapolate missing tiers based on known data
  function extrapolateTiers(info) {
    if (!info || info.length === 0) return [];

    let result = [...info];

    // Find the tier with most complete material data
    const testTier = result.reduce((prev, current) => {
      const prevMats = prev.Materials?.length || 0;
      const currMats = current.Materials?.length || 0;
      return currMats > prevMats ? current : prev;
    }, result[0]);

    if (!testTier?.Materials || testTier.Materials.length < 3) return result;

    // Extract base name from tier
    const match = testTier.Name?.match(/^(.*?)(?=Tier [1-9]|Tier 10)/);
    const baseName = match ? match[1].trim() : entity?.Name || 'Unknown';

    // Find blazar fragment to calculate base ratios
    const blazarMat = testTier.Materials.find(m => m.Material?.Name === 'Blazar Fragment');
    const blazarCount = blazarMat?.Amount || 1;
    const baseTierNum = testTier.Properties?.Tier || 1;
    const minBlazar = Math.round(blazarCount / baseTierNum);

    // Calculate base material values per blazar
    const minMatValues = {};
    testTier.Materials.forEach(mat => {
      const matName = mat.Material?.Name;
      const matTT = mat.Material?.Properties?.Economy?.MaxTT || matValues[matName] || 0;
      if (matName && matTT) {
        minMatValues[matName] = (mat.Amount * matTT) / blazarCount;
      }
    });

    // Fill in missing tiers 1-10
    for (let i = 1; i <= MAX_TIERS; i++) {
      const existingTier = result.find(t => (t.Properties?.Tier || t.Tier) === i);
      if (existingTier && existingTier.Materials?.length >= 3) continue;

      // Create extrapolated tier
      const newTier = {
        Name: `${baseName} Tier ${i}`,
        Properties: {
          Tier: i,
          IsExtrapolated: true,
        },
        Materials: [
          {
            Material: {
              Name: genericMats.Components[i - 1],
              Properties: { Type: 'Enhancer Component', Economy: { MaxTT: matValues[genericMats.Components[i - 1]] || 0 } }
            },
            Amount: Math.round((minMatValues[genericMats.Components[baseTierNum - 1]] || 0.1) * minBlazar * i / (matValues[genericMats.Components[i - 1]] || 0.1))
          },
          {
            Material: {
              Name: genericMats.Gems[i - 1],
              Properties: { Type: 'Precious Stones', Economy: { MaxTT: matValues[genericMats.Gems[i - 1]] || 0 } }
            },
            Amount: Math.round((minMatValues[genericMats.Gems[baseTierNum - 1]] || 0.15) * minBlazar * i / (matValues[genericMats.Gems[i - 1]] || 0.15))
          },
          {
            Material: {
              Name: 'Blazar Fragment',
              Properties: { Type: 'Fragment', Economy: { MaxTT: matValues['Blazar Fragment'] || 0.00001 } }
            },
            Amount: minBlazar * i
          },
          {
            Material: {
              Name: materialArrays.Material1[i - 1],
              Properties: { Economy: { MaxTT: matValues[materialArrays.Material1[i - 1]] || 0 } }
            },
            Amount: Math.round((minMatValues[materialArrays.Material1[baseTierNum - 1]] || 0.1) * minBlazar * i / (matValues[materialArrays.Material1[i - 1]] || 0.1))
          },
          {
            Material: {
              Name: materialArrays.Material2[i - 1],
              Properties: { Economy: { MaxTT: matValues[materialArrays.Material2[i - 1]] || 0 } }
            },
            Amount: Math.round((minMatValues[materialArrays.Material2[baseTierNum - 1]] || 0.1) * minBlazar * i / (matValues[materialArrays.Material2[i - 1]] || 0.1))
          }
        ]
      };

      result.push(newTier);
    }

    // Sort by tier number
    result.sort((a, b) => (a.Properties?.Tier || a.Tier || 0) - (b.Properties?.Tier || b.Tier || 0));
    return result;
  }





  function selectTier(tier) {
    selectedTier = tier;
  }


  function getEditableTier(tierNum) {
    return entityTiers.find(t => (t.Properties?.Tier || t.Tier) === tierNum);
  }

  function updateMaterialAmount(tierNum, materialIndex, newAmount) {
    let newTiers = [...entityTiers];
    let tierIdx = newTiers.findIndex(t => (t.Properties?.Tier || t.Tier) === tierNum);

    if (tierIdx === -1) {
      // Create new tier entry
      const newTier = {
        Name: `${entity?.Name || 'Unknown'} Tier ${tierNum}`,
        Properties: { Tier: tierNum },
        Materials: []
      };
      // Initialize all 5 materials with 0 amounts
      for (let i = 0; i < 5; i++) {
        newTier.Materials.push({
          Material: {
            Name: getTierMaterial(entityType, tierNum, i),
            Properties: { Economy: { MaxTT: matValues[getTierMaterial(entityType, tierNum, i)] || 0 } }
          },
          Amount: 0
        });
      }
      newTiers.push(newTier);
      tierIdx = newTiers.length - 1;
    }

    // Ensure Materials array exists and has enough entries
    if (!newTiers[tierIdx].Materials) {
      newTiers[tierIdx].Materials = [];
    }
    while (newTiers[tierIdx].Materials.length <= materialIndex) {
      const idx = newTiers[tierIdx].Materials.length;
      newTiers[tierIdx].Materials.push({
        Material: {
          Name: getTierMaterial(entityType, tierNum, idx),
          Properties: { Economy: { MaxTT: matValues[getTierMaterial(entityType, tierNum, idx)] || 0 } }
        },
        Amount: 0
      });
    }

    // Update the amount
    newTiers[tierIdx].Materials[materialIndex] = {
      ...newTiers[tierIdx].Materials[materialIndex],
      Amount: newAmount
    };

    // Sort tiers by tier number
    newTiers.sort((a, b) => (a.Properties?.Tier || a.Tier || 0) - (b.Properties?.Tier || b.Tier || 0));

    updateField('Tiers', newTiers);
  }

  function getEntityTierMaterialAmount(tierNum, materialIndex) {
    const tier = getEditableTier(tierNum);
    if (!tier?.Materials?.[materialIndex]) return 0;
    return tier.Materials[materialIndex].Amount || 0;
  }

  function getDefaultTierMaterials(tierNum) {
    const materials = [];
    for (let i = 0; i < 5; i++) {
      const matName = getTierMaterial(entityType, tierNum, i);
      materials.push({
        Material: {
          Name: matName,
          Properties: { Economy: { MaxTT: matValues[matName] || 0 } }
        },
        Amount: 0
      });
    }
    return materials;
  }



  let materialArrays = $derived(getMaterialArrays(entityType));
  // Markups for the currently selected tier
  let markups = $derived(allMarkups[selectedTier] || DEFAULT_MARKUPS);
  // Get current tier from entity
  let currentTier = $derived(entity?.Properties?.Tier || null);
  // Use tierInfo if available, otherwise fall back to entity.Tiers
  let rawTiers = $derived((tierInfo && tierInfo.length > 0) ? tierInfo : (entity?.Tiers || []));
  // Check if entity can be tiered (not (L) tagged)
  let canBeTiered = $derived(entity && !entity.Name?.includes('(L)'));
  // Process and extrapolate tier data
  let processedTierInfo = $derived((() => {
    if (!rawTiers || rawTiers.length === 0) return [];
    return extrapolateTiers(rawTiers);
  })());
  // Build a map of known tier data by tier number
  let tierDataMap = $derived((() => {
    const map = new Map();
    rawTiers.forEach((tier, idx) => {
      const tierNum = tier.Properties?.Tier || tier.Tier || idx + 1;
      map.set(tierNum, tier);
    });
    return map;
  })());
  // Get tier info for selected tier
  let selectedTierInfo = $derived(processedTierInfo.find(t => (t.Properties?.Tier || t.Tier) === selectedTier));
  // Calculate tier costs
  let tierCost = $derived((() => {
    // Declare reactive deps hidden inside getResolvedMarkup
    void (markups, markupSource, nameToWapMap, inventoryMarkupMap, nameToIdMap);
    if (!selectedTierInfo?.Materials) return { tt: 0, mu: 0, total: 0 };
    let tt = 0;
    let total = 0;
    selectedTierInfo.Materials.forEach((mat, idx) => {
      const matTT = mat.Material?.Properties?.Economy?.MaxTT || matValues[mat.Material?.Name] || 0;
      const cost = matTT * mat.Amount;
      tt += cost;
      total += cost * getResolvedMarkup(mat.Material?.Name, idx) / 100;
    });
    return { tt, mu: total - tt, total };
  })());
  // Calculate cumulative cost up to selected tier (using per-tier markups)
  let cumulativeCost = $derived((() => {
    // Declare reactive deps hidden inside getResolvedMarkup
    void (markupSource, nameToWapMap, inventoryMarkupMap, nameToIdMap);
    let tt = 0;
    let total = 0;
    for (let i = 1; i <= selectedTier; i++) {
      const tierData = processedTierInfo.find(t => (t.Properties?.Tier || t.Tier) === i);
      if (tierData?.Materials) {
        const tierMarkups = allMarkups[i] || DEFAULT_MARKUPS;
        tierData.Materials.forEach((mat, idx) => {
          const matTT = mat.Material?.Properties?.Economy?.MaxTT || matValues[mat.Material?.Name] || 0;
          const cost = matTT * mat.Amount;
          tt += cost;
          total += cost * getResolvedMarkup(mat.Material?.Name, idx, tierMarkups) / 100;
        });
      }
    }
    return { tt, mu: total - tt, total };
  })());
  // Apply set piece multiplier for armor
  let setMultiplier = $derived((entityType === 'ArmorSet' && fullSet) ? setPieceCount : 1);
  // === Edit Mode Functions ===
  let entityTiers = $derived(entity?.Tiers || []);
  let displayMaterials = $derived((() => {
    if (selectedTierInfo?.Materials && selectedTierInfo.Materials.length > 0) {
      return selectedTierInfo.Materials;
    }
    if ($editMode) {
      return getDefaultTierMaterials(selectedTier);
    }
    return [];
  })());
  // Transform materials data for table display (sorted by material category)
  let materialTableData = $derived((() => {
    // Declare reactive deps hidden inside getResolvedMarkup
    void (markups, markupSource, nameToWapMap, inventoryMarkupMap, nameToIdMap);
    return displayMaterials
      .map((mat, origIdx) => {
        const matName = mat.Material?.Name || 'Unknown';
        const matTT = mat.Material?.Properties?.Economy?.MaxTT || matValues[matName] || 0;
        const amount = mat.Amount;
        const baseCost = matTT * amount;
        const totalCost = baseCost * getResolvedMarkup(matName, origIdx) / 100;

        return {
          _idx: origIdx,
          _matName: matName,
          _sort: classifyMaterial(matName),
          tt: formatPED(matTT),
          amount: amount,
          cost: formatPED(totalCost)
        };
      })
      .sort((a, b) => a._sort - b._sort);
  })());
  // Sorted material entries for edit mode (preserves original indices for data operations)
  let orderedEditMaterials = $derived(displayMaterials
    .map((mat, origIdx) => ({ mat, origIdx, sort: classifyMaterial(mat.Material?.Name) }))
    .sort((a, b) => a.sort - b.sort));
</script>

{#if canBeTiered}
  <div class="tiering-editor" class:compact>
    <!-- Markup Source Toggle -->
    {#if !$editMode && displayMaterials.length > 0}
      <div class="markup-source-toggle">
        <span class="markup-source-label">MU Source:</span>
        <div class="markup-source-buttons">
          <button
            class="source-btn"
            class:active={markupSource === 'custom'}
            onclick={() => { markupSource = 'custom'; debounceSaveMarkups(); }}
          >Custom</button>
          <button
            class="source-btn"
            class:active={markupSource === 'inventory'}
            disabled={inventoryMarkupMap.size === 0}
            onclick={() => { markupSource = 'inventory'; debounceSaveMarkups(); }}
          >Inventory</button>
          <button
            class="source-btn"
            class:active={markupSource === 'ingame'}
            disabled={ingameMarkupMap.size === 0}
            onclick={() => { markupSource = 'ingame'; debounceSaveMarkups(); }}
          >In-Game</button>
          <button
            class="source-btn"
            class:active={markupSource === 'exchange'}
            disabled={nameToWapMap.size === 0}
            onclick={() => { markupSource = 'exchange'; debounceSaveMarkups(); }}
          >Exchange</button>
        </div>
        <MarkupSourceHelp bind:show={showMuHelp} />
      </div>
    {/if}

    <!-- Tier Selection Buttons -->
    <div class="tier-buttons">
      {#each Array(MAX_TIERS) as _, i}
        {@const tierNum = i + 1}
        {@const hasTierData = processedTierInfo.some(t => (t.Properties?.Tier || t.Tier) === tierNum)}
        {@const isClickable = hasTierData || $editMode}
        <button
          class="tier-btn"
          class:selected={selectedTier === tierNum}
          class:current={currentTier === tierNum}
          class:disabled={!isClickable}
          class:no-data={!hasTierData && $editMode}
          disabled={!isClickable}
          onclick={() => selectTier(tierNum)}
        >
          {tierNum}
        </button>
      {/each}
    </div>

    <!-- Materials Table for Selected Tier -->
    {#if displayMaterials.length > 0}
      {#if $editMode}
        <!-- Compact edit view -->
        <div class="materials-edit-list">
          {#each orderedEditMaterials as { mat, origIdx } (origIdx)}
            {@const matName = mat.Material?.Name || 'Unknown'}
            {@const editAmount = getEntityTierMaterialAmount(selectedTier, origIdx)}
            <div class="material-edit-row">
              <span class="mat-edit-name">{matName}</span>
              <input
                type="number"
                value={editAmount}
                min="0"
                step="1"
                class="amount-input-compact"
                onchange={(e) => updateMaterialAmount(selectedTier, origIdx, parseInt(e.target.value) || 0)}
              />
            </div>
          {/each}
        </div>
      {:else}
        <!-- FancyTable-styled materials grid with interactive markup inputs -->
        <div class="fancy-table-container">
          <!-- Header -->
          <div class="table-header">
            <div class="header-row">
              <div class="header-cell col-material">Material</div>
              <div class="header-cell col-tt mobile-hide">TT</div>
              <div class="header-cell col-amount">Amt</div>
              <div class="header-cell col-markup mobile-hide">MU %</div>
              <div class="header-cell col-cost">Cost</div>
            </div>
          </div>

          <!-- Body -->
          <div class="table-body">
            {#each materialTableData as row, idx}
              {@const resolved = getResolvedMarkup(row._matName, row._idx)}
              {@const isEditable = markupSource === 'custom' || (markupSource === 'inventory' && nameToIdMap.has(row._matName))}
              {@const isEditing = editingMarkup?.idx === row._idx && editingMarkup?.matName === row._matName}
              <div class="table-row" class:even={idx % 2 === 0} class:odd={idx % 2 === 1}>
                <div class="table-cell col-material">
                  <a href={getTypeLink(row._matName, 'Material')} class="material-link">{row._matName}</a>
                </div>
                <div class="table-cell col-tt mobile-hide">{row.tt}</div>
                <div class="table-cell col-amount">{row.amount}</div>
                <div class="table-cell col-markup mobile-hide">
                  {#if isEditing}
                    <input
                      type="number"
                      value={resolved}
                      class="markup-input"
                      inputmode="decimal"
                      min="0"
                      step="1"
                      onblur={(e) => commitEdit(e, row._idx, row._matName)}
                      onkeydown={(e) => handleEditKeydown(e, row._idx, row._matName)}
                      use:autofocus
                    />
                  {:else if isEditable}
                    {@const fallbackSrc = markupSource === 'custom' ? getCustomFallbackSource(row._matName, row._idx) : null}
                    {@const isFallback = markupSource === 'inventory' && !inventoryMarkupMap.has(nameToIdMap.get(row._matName))}
                    <span
                      class="markup-value-editable"
                      class:is-fallback={isFallback}
                      role="button"
                      tabindex="0"
                      onclick={() => startEdit(row._idx, row._matName)}
                      onkeydown={(e) => { if (e.key === 'Enter') startEdit(row._idx, row._matName); }}
                    >
                      {resolved}
                    </span>
                    {#if fallbackSrc}
                      <span class="markup-source-badge" title="Using {fallbackSrc === 'INV' ? 'inventory' : fallbackSrc === 'IGM' ? 'in-game' : 'exchange'} value">{fallbackSrc}</span>
                    {/if}
                    {#if isFallback}
                      <span class="markup-fallback-note" title="No inventory data">*</span>
                    {/if}
                  {:else}
                    {@const isFallback = markupSource === 'exchange' ? !nameToWapMap.has(row._matName) : markupSource === 'ingame' ? !ingameMarkupMap.has(row._matName) : false}
                    <span class="markup-value-readonly" class:is-fallback={isFallback}>
                      {resolved}
                    </span>
                    {#if isFallback}
                      <span class="markup-fallback-note" title="No {markupSource} data">*</span>
                    {/if}
                  {/if}
                </div>
                <div class="table-cell col-cost">{row.cost}</div>
              </div>
            {/each}
          </div>

          <!-- Footer with cost summary -->
          <div class="table-footer desktop-only">
            <div class="footer-row">
              <div class="footer-cell col-material label-cell">
                {#if entityType === 'ArmorSet' && setPieceCount > 1}
                  <label class="full-set-toggle">
                    <input type="checkbox" bind:checked={fullSet} />
                    <span>Full Set ({setPieceCount} pcs)</span>
                  </label>
                {:else}
                  Current Tier
                {/if}
              </div>
              <div class="footer-cell col-tt">{formatPED(tierCost.tt * setMultiplier)} PED</div>
              <div class="footer-cell col-amount"></div>
              <div class="footer-cell col-markup">{formatPED(tierCost.mu * setMultiplier)} PED</div>
              <div class="footer-cell col-cost total">{formatPED(tierCost.total * setMultiplier)} PED</div>
            </div>
            <div class="footer-row">
              <div class="footer-cell col-material label-cell">Up To Tier {selectedTier}</div>
              <div class="footer-cell col-tt">{formatPED(cumulativeCost.tt * setMultiplier)} PED</div>
              <div class="footer-cell col-amount"></div>
              <div class="footer-cell col-markup">{formatPED(cumulativeCost.mu * setMultiplier)} PED</div>
              <div class="footer-cell col-cost total">{formatPED(cumulativeCost.total * setMultiplier)} PED</div>
            </div>
          </div>
          <!-- Simplified mobile footer showing just totals -->
          <div class="table-footer mobile-only">
            <div class="footer-row">
              <div class="footer-cell col-material label-cell">Total (TT)</div>
              <div class="footer-cell col-amount"></div>
              <div class="footer-cell col-cost total">{formatPED(tierCost.tt * setMultiplier)} PED</div>
            </div>
          </div>
        </div>
      {/if}
    {:else}
      <div class="no-materials">
        No material information available for this tier.
      </div>
    {/if}

    {#if !compact && currentTier}
      <div class="current-tier-info">
        <span class="current-tier-badge">Current: Tier {currentTier}</span>
        {#if processedTierInfo.some(t => t.Properties?.IsExtrapolated)}
          <span class="legend-item">
            <span class="extrapolated-marker">*</span> Extrapolated values
          </span>
        {/if}
      </div>
    {/if}
  </div>
{:else}
  <div class="no-tiers">
    <span>This item cannot be tiered (Limited item)</span>
  </div>
{/if}

<style>
  .tiering-editor {
    display: flex;
    flex-direction: column;
    gap: 16px;
    position: relative;
  }

  /* Tier Selection Buttons */
  .tier-buttons {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .tier-btn {
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    font-weight: 600;
    font-size: 14px;
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s;
  }

  .tier-btn:hover:not(.disabled) {
    background-color: var(--hover-color);
  }

  .tier-btn.selected {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .tier-btn.current {
    border-color: var(--success-color, #4ade80);
    box-shadow: 0 0 0 2px var(--success-color, #4ade80);
  }

  .tier-btn.disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .tier-btn.no-data {
    border-style: dashed;
    opacity: 0.7;
  }

  .tier-btn.no-data:hover {
    opacity: 1;
  }

  /* Compact edit view */
  .materials-edit-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: 280px;
  }

  .material-edit-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 0;
  }

  .mat-edit-name {
    flex: 1;
    font-size: 13px;
    color: var(--text-color);
  }

  .amount-input-compact {
    width: 70px;
    padding: 6px 8px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 13px;
    text-align: left;
  }

  .amount-input-compact:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
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

  .material-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .material-link:hover {
    text-decoration: underline;
  }

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

  /* Markup source toggle */
  .markup-source-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    position: absolute;
    top: 0;
    right: 0;
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

  .markup-value-readonly {
    font-size: 13px;
    color: var(--text-color);
    font-family: monospace;
  }

  .markup-value-readonly.is-fallback {
    opacity: 0.6;
  }

  .markup-value-editable {
    font-size: 13px;
    color: var(--text-color);
    font-family: monospace;
    border-bottom: 1px dashed var(--text-muted, #999);
    cursor: pointer;
    padding-bottom: 1px;
  }

  .markup-value-editable:hover {
    border-bottom-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }

  .markup-value-editable.is-fallback {
    opacity: 0.6;
  }

  .markup-source-badge {
    font-size: 9px;
    color: var(--text-muted, #999);
    margin-left: 3px;
    padding: 0 3px;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    vertical-align: middle;
  }

  .markup-fallback-note {
    font-size: 10px;
    color: var(--text-muted, #999);
    margin-left: 2px;
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

  .full-set-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    font-weight: 500;
    font-size: 12px;
    color: var(--text-color);
  }

  .full-set-toggle input[type="checkbox"] {
    width: 14px;
    height: 14px;
    cursor: pointer;
    accent-color: var(--accent-color, #4a9eff);
  }

  .no-materials {
    padding: 16px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 13px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  /* Current tier info */
  .current-tier-info {
    display: flex;
    align-items: center;
    gap: 16px;
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-top: 8px;
  }

  .current-tier-badge {
    padding: 4px 10px;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .extrapolated-marker {
    color: #b45309;
    font-weight: 700;
  }

  .no-tiers {
    padding: 16px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 14px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  /* Compact mode */
  .tiering-editor.compact .tier-btn {
    width: 32px;
    height: 32px;
    font-size: 12px;
  }

  .tiering-editor.compact {
    padding: 12px;
  }

  .tiering-editor.compact .header-cell {
    padding: 6px 10px;
    font-size: 11px;
  }

  .tiering-editor.compact .table-cell {
    padding: 4px 10px;
  }

  .tiering-editor.compact .footer-cell {
    padding: 6px 10px;
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
    .tier-btn {
      width: 36px;
      height: 36px;
      font-size: 12px;
    }

    /* Hide columns on mobile */
    .mobile-hide {
      display: none !important;
    }

    /* Show/hide elements based on mobile/desktop */
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

    /* 3-column grid for mobile: Material, Amount, Cost */
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

    .markup-source-toggle {
      position: static;
      align-self: flex-end;
    }
  }
</style>

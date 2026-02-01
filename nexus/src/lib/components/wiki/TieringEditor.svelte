<!--
  @component TieringEditor
  Generic tiering editor component for items with tier upgrades.
  Supports: Weapon, ArmorSet, MedicalTool, Finder, Excavator
  Shows materials needed per tier with markup calculator.
  Extrapolates missing tiers from known data.
-->
<script>
  // @ts-nocheck
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

  /** @type {object} Entity being displayed/edited */
  export let entity = null;

  /** @type {string} Entity type: 'Weapon', 'ArmorSet', 'MedicalTool', 'Finder', 'Excavator' */
  export let entityType = 'Weapon';

  /** @type {Array} Tier information from additional data (server-side enriched) */
  export let tierInfo = [];

  /** @type {boolean} Compact view */
  export let compact = false;

  /** @type {number} Number of pieces in set (for armor set cost calculation) */
  export let setPieceCount = 1;

  const MAX_TIERS = 10;

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

  $: materialArrays = getMaterialArrays(entityType);

  // Format PED values - avoid negative zero and ensure consistent decimals
  function formatPED(value) {
    if (value === null || value === undefined) return 'N/A';
    // Round to avoid floating point issues, then handle negative zero
    const rounded = Math.round(value * 100) / 100;
    const result = Object.is(rounded, -0) ? 0 : rounded;
    return result.toFixed(2);
  }

  // Markup handling
  function handleMarkupInput(event, idx) {
    const value = event.target.value;
    const num = parseFloat(value);
    if (!isNaN(num) && num >= 100) {
      markups[idx] = num;
    }
  }

  // Selected tier for material display
  let selectedTier = 1;

  // Markup percentages for each material (default 100%)
  let markups = Array(5).fill(100);

  // Full set toggle for armor
  let fullSet = false;

  // Get current tier from entity
  $: currentTier = entity?.Properties?.Tier || null;

  // Use tierInfo if available, otherwise fall back to entity.Tiers
  $: rawTiers = (tierInfo && tierInfo.length > 0) ? tierInfo : (entity?.Tiers || []);

  // Check if entity can be tiered (not (L) tagged)
  $: canBeTiered = entity && !entity.Name?.includes('(L)');

  // Process and extrapolate tier data
  $: processedTierInfo = (() => {
    if (!rawTiers || rawTiers.length === 0) return [];
    return extrapolateTiers(rawTiers);
  })();

  // Build a map of known tier data by tier number
  $: tierDataMap = (() => {
    const map = new Map();
    rawTiers.forEach((tier, idx) => {
      const tierNum = tier.Properties?.Tier || tier.Tier || idx + 1;
      map.set(tierNum, tier);
    });
    return map;
  })();

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

  // Get tier info for selected tier
  $: selectedTierInfo = processedTierInfo.find(t => (t.Properties?.Tier || t.Tier) === selectedTier);

  // Calculate tier costs
  $: tierCost = (() => {
    if (!selectedTierInfo?.Materials) return { tt: 0, mu: 0, total: 0 };
    let tt = 0;
    let total = 0;
    selectedTierInfo.Materials.forEach((mat, idx) => {
      const matTT = mat.Material?.Properties?.Economy?.MaxTT || matValues[mat.Material?.Name] || 0;
      const cost = matTT * mat.Amount;
      tt += cost;
      total += cost * (markups[idx] || 100) / 100;
    });
    return { tt, mu: total - tt, total };
  })();

  // Calculate cumulative cost up to selected tier
  $: cumulativeCost = (() => {
    let tt = 0;
    let total = 0;
    for (let i = 1; i <= selectedTier; i++) {
      const tierData = processedTierInfo.find(t => (t.Properties?.Tier || t.Tier) === i);
      if (tierData?.Materials) {
        tierData.Materials.forEach((mat, idx) => {
          const matTT = mat.Material?.Properties?.Economy?.MaxTT || matValues[mat.Material?.Name] || 0;
          const cost = matTT * mat.Amount;
          tt += cost;
          total += cost * (markups[idx] || 100) / 100;
        });
      }
    }
    return { tt, mu: total - tt, total };
  })();

  // Apply set piece multiplier for armor
  $: setMultiplier = (entityType === 'ArmorSet' && fullSet) ? setPieceCount : 1;

  function selectTier(tier) {
    selectedTier = tier;
  }

  // === Edit Mode Functions ===
  $: entityTiers = entity?.Tiers || [];

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

  $: displayMaterials = (() => {
    if (selectedTierInfo?.Materials && selectedTierInfo.Materials.length > 0) {
      return selectedTierInfo.Materials;
    }
    if ($editMode) {
      return getDefaultTierMaterials(selectedTier);
    }
    return [];
  })();

  // Transform materials data for table display
  $: materialTableData = displayMaterials.map((mat, idx) => {
    const matName = mat.Material?.Name || 'Unknown';
    const matTT = mat.Material?.Properties?.Economy?.MaxTT || matValues[matName] || 0;
    const amount = mat.Amount;
    const baseCost = matTT * amount;
    const totalCost = baseCost * (markups[idx] || 100) / 100;

    return {
      _idx: idx,
      _matName: matName,
      tt: formatPED(matTT),
      amount: amount,
      cost: formatPED(totalCost)
    };
  });
</script>

{#if canBeTiered}
  <div class="tiering-editor" class:compact>
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
          on:click={() => selectTier(tierNum)}
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
          {#each displayMaterials as mat, idx}
            {@const matName = mat.Material?.Name || 'Unknown'}
            {@const editAmount = getEntityTierMaterialAmount(selectedTier, idx)}
            <div class="material-edit-row">
              <span class="mat-edit-name">{matName}</span>
              <input
                type="number"
                value={editAmount}
                min="0"
                step="1"
                class="amount-input-compact"
                on:change={(e) => updateMaterialAmount(selectedTier, idx, parseInt(e.target.value) || 0)}
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
              <div class="table-row" class:even={idx % 2 === 0} class:odd={idx % 2 === 1}>
                <div class="table-cell col-material">
                  <a href={getTypeLink(row._matName, 'Material')} class="material-link">{row._matName}</a>
                </div>
                <div class="table-cell col-tt mobile-hide">{row.tt}</div>
                <div class="table-cell col-amount">{row.amount}</div>
                <div class="table-cell col-markup mobile-hide">
                  <input
                    type="text"
                    value={markups[row._idx]}
                    on:input={(e) => handleMarkupInput(e, row._idx)}
                    on:blur={(e) => handleMarkupInput(e, row._idx)}
                    class="markup-input"
                    inputmode="decimal"
                  />
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

  /* FancyTable-style grid layout */
  .fancy-table-container {
    display: flex;
    flex-direction: column;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    font-size: 14px;
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
    padding: 12px 14px;
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
    padding: 12px 14px;
    color: var(--text-color);
    display: flex;
    align-items: center;
    border-right: 1px solid var(--border-color);
    box-sizing: border-box;
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
    padding: 12px 14px;
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

  .tiering-editor.compact .header-cell,
  .tiering-editor.compact .table-cell,
  .tiering-editor.compact .footer-cell {
    padding: 10px 12px;
    font-size: 12px;
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

    .header-cell,
    .table-cell,
    .footer-cell {
      padding: 10px 8px;
      font-size: 12px;
    }
  }
</style>

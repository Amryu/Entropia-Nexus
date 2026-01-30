<!--
  @component WeaponTiers
  Displays weapon tier progression table with 10 tiers.
  Shows materials needed for each tier with TT values and markup calculator.
  Extrapolates missing tiers and shows "No data" where appropriate.
-->
<script>
  // @ts-nocheck
  import { clampDecimals, getTypeLink } from '$lib/util';
  import { genericMats, weaponMats, matValues } from '$lib/tieringUtil.js';

  // Format PED values - 2 decimals unless it's a very small number
  function formatPED(value) {
    if (value === null || value === undefined) return 'N/A';
    // For very small numbers like 0.00001, show more decimals
    if (value > 0 && value < 0.01) {
      return value.toFixed(5);
    }
    return value.toFixed(2);
  }

  // Validate and parse markup input
  function handleMarkupInput(event, idx) {
    const value = event.target.value;
    const num = parseFloat(value);
    if (!isNaN(num) && num >= 100) {
      markups[idx] = num;
    }
  }

  /** @type {object} Weapon entity */
  export let weapon = null;

  /** @type {Array} Tier information from additional data */
  export let tierInfo = [];

  /** @type {boolean} Compact view */
  export let compact = false;

  const MAX_TIERS = 10;

  // Selected tier for material display
  let selectedTier = 1;

  // Markup percentages for each material (default 100%)
  let markups = Array(5).fill(100);

  // Get current tier from weapon
  $: currentTier = weapon?.Properties?.Tier || null;

  // Use tierInfo if available, otherwise fall back to weapon.Tiers
  $: rawTiers = tierInfo.length > 0 ? tierInfo : (weapon?.Tiers || []);

  // Check if weapon can be tiered (not (L) tagged)
  $: canBeTiered = weapon && !weapon.Name?.includes('(L)');

  // Process and extrapolate tier data
  $: processedTierInfo = (() => {
    if (!rawTiers || rawTiers.length === 0) return [];
    return extrapolateTiers(rawTiers);
  })();

  // Build a map of known tier data by tier number (for stats display)
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
    const baseName = match ? match[1].trim() : weapon?.Name || 'Unknown';

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
              Name: weaponMats.Material1[i - 1],
              Properties: { Economy: { MaxTT: matValues[weaponMats.Material1[i - 1]] || 0 } }
            },
            Amount: Math.round((minMatValues[weaponMats.Material1[baseTierNum - 1]] || 0.1) * minBlazar * i / (matValues[weaponMats.Material1[i - 1]] || 0.1))
          },
          {
            Material: {
              Name: weaponMats.Material2[i - 1],
              Properties: { Economy: { MaxTT: matValues[weaponMats.Material2[i - 1]] || 0 } }
            },
            Amount: Math.round((minMatValues[weaponMats.Material2[baseTierNum - 1]] || 0.1) * minBlazar * i / (matValues[weaponMats.Material2[i - 1]] || 0.1))
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

  // Calculate stat changes between tiers
  function getStatChange(current, previous, key) {
    if (!current?.data || !previous?.data) return null;
    const currentVal = current.data[key] || 0;
    const prevVal = previous.data[key] || 0;
    const diff = currentVal - prevVal;
    if (diff === 0) return null;
    return diff > 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1);
  }

  // Build full 10-tier array for stats table
  $: allTiers = (() => {
    const result = [];
    for (let i = 1; i <= MAX_TIERS; i++) {
      const tierData = tierDataMap.get(i);
      if (tierData) {
        result.push({ tier: i, data: tierData, isExtrapolated: false, hasData: true });
      } else {
        // Try to find extrapolated data
        const extrapolated = processedTierInfo.find(t => (t.Properties?.Tier || t.Tier) === i);
        if (extrapolated?.Properties?.IsExtrapolated) {
          result.push({ tier: i, data: extrapolated, isExtrapolated: true, hasData: false });
        } else if (extrapolated) {
          result.push({ tier: i, data: extrapolated, isExtrapolated: false, hasData: true });
        } else {
          result.push({ tier: i, data: null, isExtrapolated: false, hasData: false });
        }
      }
    }
    return result;
  })();

  // Format value with fallback
  function formatValue(tierEntry, key, suffix = '', decimals = 1) {
    if (!tierEntry.data) return 'No data';
    const value = tierEntry.data[key] || tierEntry.data.Properties?.[key];
    if (value === null || value === undefined) return 'No data';
    return typeof value === 'number' ? value.toFixed(decimals) + suffix : value + suffix;
  }

  function selectTier(tier) {
    selectedTier = tier;
  }
</script>

{#if canBeTiered}
  <div class="weapon-tiers" class:compact>
    <!-- Tier Selection Buttons -->
    <div class="tier-buttons">
      {#each Array(MAX_TIERS) as _, i}
        {@const tierNum = i + 1}
        {@const hasTierData = processedTierInfo.some(t => (t.Properties?.Tier || t.Tier) === tierNum)}
        <button
          class="tier-btn"
          class:selected={selectedTier === tierNum}
          class:current={currentTier === tierNum}
          class:disabled={!hasTierData}
          disabled={!hasTierData}
          on:click={() => selectTier(tierNum)}
        >
          {tierNum}
        </button>
      {/each}
    </div>

    <!-- Materials Table for Selected Tier -->
    {#if selectedTierInfo?.Materials && selectedTierInfo.Materials.length > 0}
      <div class="materials-section">
        <h4 class="materials-title">
          Tier {selectedTier} Materials
          {#if selectedTierInfo.Properties?.IsExtrapolated}
            <span class="extrapolated-badge" title="Values are extrapolated from available data">*Extrapolated</span>
          {/if}
        </h4>
        <table class="materials-table">
          <thead>
            <tr>
              <th class="col-material">Material</th>
              <th class="col-tt">TT</th>
              <th class="col-amount">Amt</th>
              <th class="col-markup">MU %</th>
              <th class="col-cost">Cost</th>
            </tr>
          </thead>
          <tbody>
            {#each selectedTierInfo.Materials as mat, idx}
              {@const matName = mat.Material?.Name || 'Unknown'}
              {@const matTT = mat.Material?.Properties?.Economy?.MaxTT || matValues[matName] || 0}
              {@const baseCost = matTT * mat.Amount}
              {@const totalCost = baseCost * (markups[idx] || 100) / 100}
              <tr>
                <td class="mat-name">
                  <a href={getTypeLink(matName, 'Material')} class="material-link">{matName}</a>
                </td>
                <td class="mat-tt">{formatPED(matTT)}</td>
                <td class="mat-amount">{mat.Amount}</td>
                <td class="mat-markup">
                  <input
                    type="text"
                    value={markups[idx]}
                    on:input={(e) => handleMarkupInput(e, idx)}
                    on:blur={(e) => handleMarkupInput(e, idx)}
                    class="markup-input"
                    inputmode="decimal"
                  />
                </td>
                <td class="mat-cost">{formatPED(totalCost)}</td>
              </tr>
            {/each}
          </tbody>
        </table>

        <!-- Cost Summary -->
        <div class="cost-summary">
          <table class="cost-table">
            <thead>
              <tr>
                <th></th>
                <th>TT</th>
                <th>MU</th>
                <th>TT+MU</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Current Tier</td>
                <td>{formatPED(tierCost.tt)} PED</td>
                <td>{formatPED(tierCost.mu)} PED</td>
                <td class="total">{formatPED(tierCost.total)} PED</td>
              </tr>
              <tr>
                <td>Up To Tier {selectedTier}</td>
                <td>{formatPED(cumulativeCost.tt)} PED</td>
                <td>{formatPED(cumulativeCost.mu)} PED</td>
                <td class="total">{formatPED(cumulativeCost.total)} PED</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    {:else}
      <div class="no-materials">
        No material information available for this tier.
      </div>
    {/if}

    {#if !compact && currentTier}
      <!-- Current Tier Indicator -->
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
    <span>This weapon cannot be tiered (Limited item)</span>
  </div>
{/if}

<style>
  .weapon-tiers {
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

  /* Materials Section */
  .materials-section {
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 8px;
    padding: 16px;
  }

  .materials-title {
    font-size: 14px;
    font-weight: 600;
    margin: 0 0 12px 0;
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .extrapolated-badge {
    font-size: 11px;
    font-weight: 500;
    padding: 2px 6px;
    background-color: #b45309;
    color: white;
    border-radius: 4px;
  }

  .materials-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin-bottom: 16px;
  }

  .materials-table th,
  .materials-table td {
    padding: 8px 10px;
    text-align: left;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .materials-table th {
    font-weight: 600;
    color: var(--text-muted, #999);
    font-size: 11px;
    text-transform: uppercase;
  }

  /* Column widths */
  .col-material { width: auto; }
  .col-tt { width: 80px; }
  .col-amount { width: 60px; }
  .col-markup { width: 70px; }
  .col-cost { width: 80px; }

  .mat-name {
    font-weight: 500;
  }

  .material-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .material-link:hover {
    text-decoration: underline;
  }

  .mat-tt,
  .mat-amount,
  .mat-cost {
    text-align: right;
    font-family: monospace;
  }

  .mat-markup {
    text-align: center;
  }

  .markup-input {
    width: 60px;
    padding: 4px 6px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 12px;
    text-align: right;
  }

  .markup-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  /* Cost Summary */
  .cost-summary {
    border-top: 1px dashed var(--border-color, #555);
    padding-top: 12px;
  }

  .cost-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .cost-table th,
  .cost-table td {
    padding: 6px 10px;
    text-align: right;
  }

  .cost-table th {
    font-weight: 600;
    color: var(--text-muted, #999);
    font-size: 11px;
    text-transform: uppercase;
  }

  .cost-table td:first-child {
    text-align: left;
    color: var(--text-muted, #999);
  }

  .cost-table .total {
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
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
  .weapon-tiers.compact .tier-btn {
    width: 32px;
    height: 32px;
    font-size: 12px;
  }

  .weapon-tiers.compact .materials-section {
    padding: 12px;
  }

  .weapon-tiers.compact .materials-table th,
  .weapon-tiers.compact .materials-table td {
    padding: 6px 8px;
    font-size: 12px;
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .tier-btn {
      width: 36px;
      height: 36px;
      font-size: 12px;
    }

    .materials-table th,
    .materials-table td {
      padding: 6px 6px;
      font-size: 12px;
    }

    .col-tt { width: 60px; }
    .col-amount { width: 50px; }
    .col-markup { width: 55px; }
    .col-cost { width: 60px; }

    .markup-input {
      width: 50px;
    }
  }
</style>

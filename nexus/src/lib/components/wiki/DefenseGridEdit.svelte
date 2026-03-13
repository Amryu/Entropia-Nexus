<!--
  @component DefenseGridEdit
  Editable grid for defense values (Block, Impact, Cut, Stab, etc.).
  Styled like WeaponDamageGrid with colored bars showing proportions.
  Block is special - displayed as percentage with its own bar.
-->
<script>
  // @ts-nocheck
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';

  

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {object} Defense object {Block, Impact, Cut, Stab, etc.} [defense]
   * @property {string} [fieldPath]
   * @property {string} [title]
   * @property {boolean} [compact]
   * @property {string[]|null} [types]
   * @property {boolean} [showBlockSeparately]
   */

  /** @type {Props} */
  let {
    defense = {},
    fieldPath = 'Properties.Defense',
    title = 'Defense',
    compact = false,
    types = null,
    showBlockSeparately = true
  } = $props();

  // Defense types (excluding Block for normal display)
  const normalDefenseTypes = ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];
  const allDefenseTypes = ['Block', ...normalDefenseTypes];

  // Defense type colors use global CSS variables defined in style.css
  const defenseColorVars = {
    Block: '--damage-block',
    Impact: '--damage-impact',
    Cut: '--damage-cut',
    Stab: '--damage-stab',
    Penetration: '--damage-penetration',
    Shrapnel: '--damage-shrapnel',
    Burn: '--damage-burn',
    Cold: '--damage-cold',
    Acid: '--damage-acid',
    Electric: '--damage-electric'
  };

  // Use custom types if provided, otherwise use defaults
  let activeTypes = $derived(types || (showBlockSeparately ? normalDefenseTypes : allDefenseTypes));

  // Calculate total defense (excluding Block)
  let totalDefense = $derived(normalDefenseTypes.reduce((sum, type) => sum + (defense?.[type] ?? 0), 0));

  // Find maximum defense value for bar scaling (excluding Block)
  let maxDefense = $derived(Math.max(...normalDefenseTypes.map(type => defense?.[type] ?? 0), 0));

  // Block value
  let blockValue = $derived(defense?.Block ?? 0);
  let hasBlock = $derived(blockValue > 0 || $editMode);

  // Check if has any defense values
  let hasDefense = $derived(totalDefense > 0 || blockValue > 0 || $editMode);

  // Filter to only show non-zero values in view mode (always show all in edit mode)
  let visibleTypes = $derived($editMode
    ? activeTypes
    : activeTypes.filter(type => (defense?.[type] ?? 0) > 0));

  // Get bar percentage relative to max value (highest = 100%, Block uses its own 0-100 scale)
  function getDefensePercentage(type, value) {
    if (type === 'Block') {
      // Block is already a percentage (0-100)
      return Math.min(value ?? 0, 100);
    }
    if (!maxDefense || !value) return 0;
    return (value / maxDefense) * 100;
  }

  function updateDefenseValue(type, value) {
    const newDefense = {
      ...defense,
      [type]: parseFloat(value) || 0
    };
    updateField(fieldPath, newDefense);
  }

  // Format value (Block is percentage, others are flat)
  function formatValue(type, value) {
    if (type === 'Block') {
      return `${(value ?? 0).toFixed(1)}%`;
    }
    return (value ?? 0).toFixed(1);
  }

  // Get CSS variable reference for defense type color
  function getColorVar(type) {
    return defenseColorVars[type] || '--text-color';
  }
</script>

{#if hasDefense}
  <div class="defense-grid" class:compact class:editing={$editMode}>
    <!-- Total Defense section - styled like WeaponDamageGrid -->
    {#if !compact}
      <div class="defense-total">
        <span class="total-label">{title}</span>
        <span class="total-value">{totalDefense.toFixed(1)}</span>
      </div>
    {/if}

    {#if $editMode}
      <!-- Block % editor - special styling -->
      {#if showBlockSeparately && hasBlock}
        <div class="block-edit-container">
          <div class="block-edit-header">
            <svg class="block-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span class="block-edit-title">Block Chance</span>
            <span class="block-edit-hint">Negates all damage</span>
          </div>
          <div class="block-edit-input">
            <input
              type="number"
              class="defense-input block-input"
              value={blockValue}
              step="0.1"
              min="0"
              max="100"
              onchange={(e) => updateDefenseValue('Block', e.target.value)}
            />
            <span class="unit">%</span>
          </div>
        </div>
      {/if}

      <!-- Edit mode: compact 3-column grid for damage types -->
      <div class="defense-edit-grid">
        {#each activeTypes as type}
          {@const value = defense?.[type] ?? 0}
          <div class="defense-edit-item" class:has-value={value > 0}>
            <label class="defense-edit-label" style="color: var({getColorVar(type)})">
              {type.substring(0, 3)}
              <input
              type="number"
              class="defense-input"
              value={value}
              step="0.1"
              min="0"
              max={type === 'Block' ? 100 : undefined}
              onchange={(e) => updateDefenseValue(type, e.target.value)}
            />
            </label>
          </div>
        {/each}
      </div>
      <div class="total-row">
        <span class="total-label">Total (excl. Block):</span>
        <span class="total-value">{totalDefense.toFixed(1)}</span>
      </div>
    {:else}
      <!-- View mode: styled list with bars -->

      <!-- Block % displayed as special circular gauge -->
      {#if showBlockSeparately && blockValue > 0}
        <div class="block-display">
          <div class="block-gauge">
            <svg viewBox="0 0 36 36" class="block-circle">
              <!-- Background circle -->
              <path
                class="circle-bg"
                d="M18 2.0845
                   a 15.9155 15.9155 0 0 1 0 31.831
                   a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <!-- Progress arc -->
              <path
                class="circle-progress"
                stroke-dasharray="{blockValue}, 100"
                d="M18 2.0845
                   a 15.9155 15.9155 0 0 1 0 31.831
                   a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <div class="block-gauge-value">{blockValue.toFixed(1)}%</div>
          </div>
          <div class="block-info">
            <div class="block-title">
              <svg class="block-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              <span>Block Chance</span>
            </div>
            <div class="block-description">Chance to negate all damage</div>
          </div>
        </div>
      {/if}

      <!-- Defense types with bars -->
      <div class="defense-types">
        {#each visibleTypes as type}
          {@const value = defense?.[type] ?? 0}
          {@const percentage = getDefensePercentage(type, value)}
          <div class="defense-item" class:has-value={value > 0}>
            <div class="item-header">
              <span class="defense-label" style="color: var({getColorVar(type)})">{type}</span>
              <span class="defense-value">{formatValue(type, value)}</span>
            </div>
            <div class="defense-bar-bg">
              <div
                class="defense-bar"
                style="width: {percentage}%; background-color: var({getColorVar(type)})"
              ></div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .defense-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  /* Total Defense - styled like WeaponDamageGrid */
  .defense-total {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 10px 14px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
    font-size: 15px;
  }

  .total-label {
    font-weight: 500;
    color: var(--text-color);
  }

  .total-value {
    font-weight: 700;
    font-size: 18px;
    color: var(--success-color, #4ade80);
  }

  /* Block display - special circular gauge style */
  .block-display {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 14px;
    background: linear-gradient(135deg,
      color-mix(in srgb, var(--damage-block) 15%, var(--bg-color, var(--primary-color))),
      color-mix(in srgb, var(--damage-block) 8%, var(--bg-color, var(--primary-color)))
    );
    border-radius: 8px;
    border: 1px solid color-mix(in srgb, var(--damage-block) 30%, transparent);
  }

  .block-gauge {
    position: relative;
    width: 52px;
    height: 52px;
    flex-shrink: 0;
  }

  .block-circle {
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
  }

  .circle-bg {
    fill: none;
    stroke: var(--secondary-color);
    stroke-width: 3;
  }

  .circle-progress {
    fill: none;
    stroke: var(--damage-block);
    stroke-width: 3;
    stroke-linecap: round;
    transition: stroke-dasharray 0.3s ease;
  }

  .block-gauge-value {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 11px;
    font-weight: 700;
    color: var(--damage-block);
  }

  .block-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .block-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 600;
    color: var(--damage-block);
  }

  .block-icon {
    opacity: 0.9;
  }

  .block-description {
    font-size: 11px;
    color: var(--text-muted, #999);
    font-style: italic;
  }

  /* Defense types list */
  .defense-types {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .defense-item {
    padding: 8px 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
  }

  .defense-item:not(.has-value) {
    opacity: 0.5;
  }

  .item-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 4px;
  }

  .defense-label {
    font-size: 13px;
    font-weight: 500;
  }

  .defense-value {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  /* Progress bars */
  .defense-bar-bg {
    height: 4px;
    background-color: var(--secondary-color);
    border-radius: 2px;
    overflow: hidden;
  }

  .defense-bar {
    height: 100%;
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  /* Edit mode grid */
  .defense-edit-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
  }

  .defense-edit-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 6px 8px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
  }

  .defense-edit-item:not(.has-value) {
    opacity: 0.6;
  }

  /* Block edit - special container */
  .block-edit-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 14px;
    background: linear-gradient(135deg,
      color-mix(in srgb, var(--damage-block) 15%, var(--bg-color, var(--primary-color))),
      color-mix(in srgb, var(--damage-block) 8%, var(--bg-color, var(--primary-color)))
    );
    border-radius: 8px;
    border: 1px solid color-mix(in srgb, var(--damage-block) 30%, transparent);
    margin-bottom: 6px;
  }

  .block-edit-header {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
  }

  .block-edit-header .block-icon {
    color: var(--damage-block);
    flex-shrink: 0;
  }

  .block-edit-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--damage-block);
  }

  .block-edit-hint {
    font-size: 11px;
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .block-edit-input {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .block-input {
    width: 65px;
    text-align: center;
    font-weight: 600;
  }

  .defense-edit-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .defense-input {
    width: 100%;
    padding: 4px 6px;
    font-size: 13px;
    text-align: left;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    box-sizing: border-box;
  }

  .defense-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .unit {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .total-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 10px;
    background-color: var(--hover-color);
    border-radius: 4px;
    font-weight: 600;
  }

  .total-row .total-label {
    font-size: 13px;
    color: var(--text-muted, #999);
  }

  .total-row .total-value {
    font-size: 14px;
  }

  /* Compact mode */
  .compact .defense-types {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 4px;
  }

  .compact .defense-item {
    padding: 6px 10px;
  }

  .compact .item-header {
    margin-bottom: 2px;
  }

  .compact .defense-label,
  .compact .defense-value {
    font-size: 12px;
  }

  .compact .defense-bar-bg {
    height: 3px;
  }

  /* Responsive: 2 columns on very narrow */
  @media (max-width: 350px) {
    .defense-edit-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .block-edit-container {
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
    }

    .block-edit-header {
      flex-wrap: wrap;
    }

    .block-gauge {
      width: 44px;
      height: 44px;
    }
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .defense-types {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 4px;
    }

    .defense-item {
      padding: 6px 10px;
    }

    .item-header {
      margin-bottom: 2px;
    }

    .defense-label,
    .defense-value {
      font-size: 12px;
    }

    .defense-bar-bg {
      height: 3px;
    }

    /* Keep 3 columns on mobile for edit grid */
    .defense-edit-grid {
      gap: 4px;
    }

    .defense-edit-item {
      padding: 4px 6px;
    }

    .defense-edit-label {
      font-size: 10px;
    }

    .defense-input {
      padding: 3px 4px;
      font-size: 12px;
    }

    .block-display {
      gap: 10px;
      padding: 10px 12px;
    }

    .block-gauge {
      width: 44px;
      height: 44px;
    }

    .block-gauge-value {
      font-size: 10px;
    }

    .block-title {
      font-size: 13px;
    }

    .block-edit-container {
      padding: 8px 12px;
    }

    .block-edit-hint {
      display: none;
    }
  }
</style>

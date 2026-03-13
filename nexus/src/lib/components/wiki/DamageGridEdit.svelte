<!--
  @component DamageGridEdit
  Editable grid for damage values (Impact, Cut, Stab, etc.).
  Used by weapon amplifiers and other damage-dealing attachments.
-->
<script>
  // @ts-nocheck
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {object} Damage object {Impact, Cut, Stab, etc.} [damage]
   * @property {string} [fieldPath]
   * @property {string} [title]
   * @property {boolean} [compact]
   */

  /** @type {Props} */
  let {
    damage = {},
    fieldPath = 'Properties.Damage',
    title = 'Damage',
    compact = false
  } = $props();

  // Damage types in order
  const damageTypes = ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];

  // Calculate total damage
  let totalDamage = $derived(damageTypes.reduce((sum, type) => sum + (damage?.[type] ?? 0), 0));

  // Check if has any damage values
  let hasDamage = $derived(totalDamage > 0 || $editMode);

  // Filter to only show non-zero values in view mode
  let visibleTypes = $derived($editMode
    ? damageTypes
    : damageTypes.filter(type => (damage?.[type] ?? 0) > 0));

  function updateDamageValue(type, value) {
    const newDamage = {
      ...damage,
      [type]: parseFloat(value) || 0
    };
    updateField(fieldPath, newDamage);
  }

  // Get icon color for damage type
  function getDamageColor(type) {
    switch (type) {
      case 'Impact':
      case 'Cut':
      case 'Stab':
      case 'Penetration':
        return 'var(--text-color)';
      case 'Shrapnel':
        return '#a78bfa';
      case 'Burn':
        return '#f97316';
      case 'Cold':
        return '#38bdf8';
      case 'Acid':
        return '#84cc16';
      case 'Electric':
        return '#facc15';
      default:
        return 'var(--text-color)';
    }
  }
</script>

{#if hasDamage}
  <div class="damage-grid" class:compact class:editing={$editMode}>
    <h4 class="grid-title">
      <span class="grid-icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14.5 17.5 3 6V3h3l11.5 11.5" />
          <path d="m13 19 6-6" />
          <path d="m16 16 4 4" />
        </svg>
      </span>
      {title}
      {#if !$editMode && totalDamage > 0}
        <span class="total-badge">{totalDamage.toFixed(1)}</span>
      {/if}
    </h4>

    <div class="damage-items">
      {#each visibleTypes as type}
        <div class="damage-item" style="--damage-color: {getDamageColor(type)}">
          <span class="damage-label">{type}</span>
          {#if $editMode}
            <input
              type="number"
              class="damage-input"
              value={damage?.[type] ?? 0}
              step="0.1"
              min="0"
              onchange={(e) => updateDamageValue(type, e.target.value)}
            />
          {:else}
            <span class="damage-value">{(damage?.[type] ?? 0).toFixed(1)}</span>
          {/if}
        </div>
      {/each}
    </div>

    {#if $editMode}
      <div class="total-row">
        <span class="total-label">Total:</span>
        <span class="total-value">{totalDamage.toFixed(1)}</span>
      </div>
    {/if}
  </div>
{/if}

<style>
  .damage-grid {
    width: 100%;
  }

  .grid-title {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0 0 8px 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .grid-icon {
    display: flex;
    color: var(--error-color, #ff6b6b);
  }

  .total-badge {
    margin-left: auto;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 600;
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-radius: 10px;
  }

  .damage-items {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .damage-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 10px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
    border-left: 3px solid var(--damage-color, var(--error-color));
  }

  .damage-label {
    font-size: 13px;
    color: var(--text-color);
    font-weight: 500;
  }

  .damage-value {
    font-size: 13px;
    font-weight: 600;
    color: var(--damage-color, var(--accent-color));
  }

  .damage-input {
    width: 70px;
    padding: 4px 8px;
    font-size: 13px;
    text-align: right;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .damage-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .total-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 10px;
    margin-top: 8px;
    background-color: var(--hover-color);
    border-radius: 4px;
    font-weight: 600;
  }

  .total-label {
    font-size: 13px;
    color: var(--text-muted, #999);
  }

  .total-value {
    font-size: 14px;
    color: var(--error-color, #ff6b6b);
  }

  /* Compact mode */
  .compact .damage-items {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 4px;
  }

  .compact .damage-item {
    padding: 4px 8px;
  }

  .compact .damage-label {
    font-size: 11px;
  }

  .compact .damage-value {
    font-size: 12px;
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .damage-items {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 4px;
    }

    .damage-item {
      padding: 4px 8px;
    }

    .damage-input {
      width: 55px;
      padding: 3px 6px;
      font-size: 12px;
    }
  }
</style>

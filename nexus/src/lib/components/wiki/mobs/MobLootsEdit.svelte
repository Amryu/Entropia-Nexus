<!--
  @component MobLootsEdit
  Array editor for mob loot drops.
  Supports item search autocomplete, maturity selection, and frequency dropdown.
  Uses SearchInput for item name search with validation.
-->
<script>
  // @ts-nocheck
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {Array} [loots]
   * @property {string} [fieldPath]
   * @property {Array} [maturities]
   * @property {Array} [allItems]
   */

  /** @type {Props} */
  let {
    loots = [],
    fieldPath = 'Loots',
    maturities = [],
    allItems = []
  } = $props();

  // Frequency options (from legacy config)
  const FREQUENCY_OPTIONS = [
    'Always',
    'Very often',
    'Often',
    'Common',
    'Uncommon',
    'Rare',
    'Very rare',
    'Extremely rare',
    'Discontinued'
  ];

  // Color mapping for frequencies
  const FREQUENCY_COLORS = {
    'Always': { bg: 'rgba(22, 163, 74, 0.25)', color: '#22c55e' },
    'Very often': { bg: 'rgba(34, 197, 94, 0.25)', color: '#4ade80' },
    'Often': { bg: 'rgba(101, 163, 13, 0.25)', color: '#84cc16' },
    'Common': { bg: 'rgba(202, 138, 4, 0.25)', color: '#eab308' },
    'Uncommon': { bg: 'rgba(234, 88, 12, 0.25)', color: '#f97316' },
    'Rare': { bg: 'rgba(220, 38, 38, 0.25)', color: '#ef4444' },
    'Very rare': { bg: 'rgba(190, 18, 60, 0.25)', color: '#f43f5e' },
    'Extremely rare': { bg: 'rgba(147, 51, 234, 0.25)', color: '#a855f7' },
    'Discontinued': { bg: 'rgba(107, 114, 128, 0.25)', color: '#6b7280' }
  };

  // Item name lookup set for validation
  let itemNamesSet = $derived(new Set((allItems || []).map(i => i.Name)));

  // === Loot Constructor ===
  function createLoot() {
    return {
      Item: {
        Name: ''
      },
      Maturity: {
        Name: null
      },
      Frequency: 'Common',
      IsEvent: false
    };
  }

  // === CRUD Operations ===
  function addLoot() {
    const newLoot = createLoot();
    updateField(fieldPath, [...loots, newLoot]);
  }

  function removeLoot(index) {
    updateField(fieldPath, loots.filter((_, i) => i !== index));
  }

  function updateLootField(index, field, value) {
    const newList = [...loots];
    const loot = newList[index];

    if (field === 'Item.Name') {
      if (!loot.Item) loot.Item = {};
      loot.Item.Name = value;
    } else if (field === 'Maturity.Name') {
      if (!loot.Maturity) loot.Maturity = {};
      loot.Maturity.Name = value;
    } else {
      loot[field] = value;
    }

    updateField(fieldPath, newList);
  }

  // Validate item name against items list
  function isValidItem(itemName) {
    if (!itemName) return false;
    return itemNamesSet.has(itemName);
  }

  function getFrequencyStyle(frequency) {
    const style = FREQUENCY_COLORS[frequency] || { bg: 'var(--hover-color)', color: 'var(--text-muted)' };
    return `background-color: ${style.bg}; color: ${style.color};`;
  }
</script>

<div class="loots-edit">
  <div class="section-header">
    <h4 class="section-title">Loots ({loots?.length || 0})</h4>
  </div>

  <div class="loots-list">
    {#each loots as loot, index (index)}
      <div class="loot-item" class:invalid-item={loot.Item?.Name && !isValidItem(loot.Item.Name)}>
        <div class="loot-fields">
          <div class="field item-field">
            <span class="field-label">Item Name</span>
            <SearchInput
              value={loot.Item?.Name || ''}
              placeholder="Search item..."
              apiEndpoint="/search/items"
              apiParams={{ armorParts: 'true' }}
              displayFn={(item) => item?.Name || ''}
              validValues={itemNamesSet}
              on:change={(e) => updateLootField(index, 'Item.Name', e.detail.value)}
              on:select={(e) => updateLootField(index, 'Item.Name', e.detail.data?.Name || e.detail.value)}
            />
          </div>

          <label class="field">
            <span class="field-label">Least Maturity</span>
            <select
              value={loot.Maturity?.Name || ''}
              onchange={(e) => updateLootField(index, 'Maturity.Name', e.target.value)}
            >
              <option value="">-- Any --</option>
              {#each maturities as mat}
                <option value={mat.Name}>{mat.Name}</option>
              {/each}
            </select>
          </label>

          <label class="field">
            <span class="field-label">Frequency</span>
            <select
              value={loot.Frequency || 'Common'}
              onchange={(e) => updateLootField(index, 'Frequency', e.target.value)}
              style={getFrequencyStyle(loot.Frequency)}
            >
              {#each FREQUENCY_OPTIONS as freq}
                <option value={freq}>{freq}</option>
              {/each}
            </select>
          </label>

          <label class="field checkbox-field">
            <input
              type="checkbox"
              checked={loot.IsEvent || false}
              onchange={(e) => updateLootField(index, 'IsEvent', e.target.checked)}
            />
            <span class="field-label">Event</span>
          </label>
        </div>

        <button
          class="btn-icon danger"
          onclick={() => removeLoot(index)}
          title="Remove loot"
          type="button"
        >×</button>
      </div>
    {/each}

    <button class="btn-add" onclick={addLoot} type="button">
      <span>+</span> Add Loot
    </button>
  </div>
</div>

<style>
  .loots-edit {
    width: 100%;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .section-title {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .loots-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .loot-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
  }

  .loot-item.invalid-item {
    border-color: var(--error-color, #ef4444);
    background-color: rgba(239, 68, 68, 0.05);
  }

  .loot-fields {
    display: flex;
    gap: 6px;
    flex: 1;
    flex-wrap: wrap;
    align-items: flex-end;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }

  .field.item-field {
    flex: 2;
    min-width: 140px;
    max-width: 220px;
  }

  .field:not(.item-field):not(.checkbox-field) {
    flex: 1;
    min-width: 90px;
    max-width: 130px;
  }

  .field-label {
    font-size: 12px;
    color: var(--text-muted, #999);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .field select {
    padding: 4px 6px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    width: 100%;
    box-sizing: border-box;
    height: 28px;
  }

  .field select option {
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
  }

  .field select:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .checkbox-field {
    flex-direction: row;
    align-items: center;
    gap: 4px;
    min-width: auto;
    flex: 0 0 auto;
    height: 28px;
    margin-top: auto;
  }

  .checkbox-field .field-label {
    margin-top: 0;
  }

  .checkbox-field input[type="checkbox"] {
    width: 14px;
    height: 14px;
    cursor: pointer;
    flex-shrink: 0;
  }

  /* Buttons */
  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    background: none;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-icon:hover:not(:disabled) {
    background-color: var(--hover-color);
    color: var(--text-color);
    border-color: var(--text-color);
  }

  .btn-icon.danger:hover:not(:disabled) {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-add {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px 12px;
    font-size: 12px;
    line-height: 1;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
    margin-top: 4px;
  }

  .btn-add:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color);
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .loot-item {
      flex-direction: column;
      align-items: stretch;
      gap: 6px;
    }

    .loot-fields {
      flex-direction: column;
      align-items: stretch;
    }

    .field,
    .field.item-field,
    .field:not(.item-field):not(.checkbox-field) {
      max-width: none;
      width: 100%;
    }

    .checkbox-field {
      align-self: flex-start;
    }

    .btn-icon {
      align-self: flex-end;
    }
  }
</style>

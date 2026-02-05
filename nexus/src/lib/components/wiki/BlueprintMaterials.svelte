<!--
  @component BlueprintMaterials
  Editable blueprint materials component with markup calculator.
  Supports add/edit/remove materials in wiki edit mode.
  Based on Construction.svelte pattern with wikiEditState integration.
-->
<script>
  // @ts-nocheck
  import { clampDecimals, getItemLink } from '$lib/util';
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';
  import '$lib/style.css';

  /** @type {object} Blueprint entity */
  export let blueprint;

  /** @type {Array} Available materials for dropdown [{Id, Name, Properties}] */
  export let availableMaterials = [];

  let markup;
  let markupInputs;

  $: if (blueprint) {
    resetMarkup();
  }

  function resetMarkup() {
    markup = new Array(blueprint?.Materials?.length ?? 0).fill(100);
    markupInputs = markup.map(v => String(v));
  }

  // Validate and update markup value (local state only - for calculator)
  function handleMarkupChange(index, value) {
    const trimmed = value.trim();
    const num = parseFloat(trimmed);

    if (trimmed === '' || isNaN(num)) {
      markupInputs[index] = String(markup[index]);
      markupInputs = markupInputs;
      return;
    }

    const clamped = Math.max(0, Math.min(100000, num));
    markup[index] = clamped;
    markup = markup;
    markupInputs[index] = String(clamped);
    markupInputs = markupInputs;
  }

  function handleMarkupBlur(index) {
    markupInputs[index] = String(markup[index]);
    markupInputs = markupInputs;
  }

  // Calculate totals
  $: totalTT = (blueprint?.Materials ?? []).reduce((acc, mat) => {
    const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
    return acc + (matTT * (mat.Amount || 0));
  }, 0);

  $: totalWithMarkup = (blueprint?.Materials ?? []).reduce((acc, mat, i) => {
    const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
    return acc + (matTT * (mat.Amount || 0) * (markup[i] || 100) / 100);
  }, 0);

  $: weightedAvgMU = (() => {
    const sumTTxMU = (blueprint?.Materials ?? []).reduce((acc, mat, i) => {
      const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
      const tt = matTT * (mat.Amount || 0);
      return acc + (tt * (markup[i] || 100));
    }, 0);
    return totalTT > 0 ? sumTTxMU / totalTT : 100;
  })();

  function getLineTT(mat) {
    const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
    return matTT * (mat.Amount || 0);
  }

  function getLineTotal(mat, mu) {
    return getLineTT(mat) * (mu || 100) / 100;
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
    const defaultMaterial = availableMaterials[0] || { Id: null, Name: '', Properties: {} };
    const newMaterial = {
      Item: defaultMaterial,
      ItemId: defaultMaterial.Id,
      Amount: 1
    };

    const newMaterials = [...(blueprint?.Materials || []), newMaterial];
    updateField('Materials', newMaterials);

    // Add markup entry for new material
    markup = [...markup, 100];
    markupInputs = [...markupInputs, '100'];
  }

  function removeMaterial(index) {
    const newMaterials = (blueprint?.Materials || []).filter((_, i) => i !== index);
    updateField('Materials', newMaterials);

    // Remove markup entry
    markup = markup.filter((_, i) => i !== index);
    markupInputs = markupInputs.filter((_, i) => i !== index);
  }

  // Group materials by Name for dropdown
  $: materialOptions = availableMaterials.map(m => ({
    value: m.Id || m.Name,
    label: m.Name
  }));
  $: materialNames = availableMaterials.map(m => m.Name);

  // Check if we have materials or are in edit mode
  $: hasMaterials = (blueprint?.Materials?.length > 0) || $editMode;
</script>

{#if hasMaterials}
  <div class="materials-wrapper">
    <div class="table-container">
      <table class="materials-table">
        <thead>
          <tr>
            <th>Ingredient</th>
            <th class="text-right hide-mobile">Amount</th>
            {#if !$editMode}
              <th class="text-right">TT</th>
              <th class="text-right">MU (%)</th>
              <th class="text-right">Total</th>
            {/if}
            {#if $editMode}
              <th class="actions-col"></th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each blueprint?.Materials ?? [] as material, index}
            <tr>
              <td>
                {#if $editMode}
                  <SearchInput
                    value={material.Item?.Name || ''}
                    placeholder="Search material..."
                    apiEndpoint="/search/items"
                    displayFn={(item) => item?.Name || ''}
                    allowedTypes={['Material']}
                    allowedNames={materialNames}
                    on:change={(e) => updateMaterial(index, 'Item', e.detail.value)}
                    on:select={(e) => updateMaterial(index, 'Item', e.detail.data || e.detail.value)}
                  />
                {:else}
                  <a href="{getItemLink(material.Item)}">{material.Item?.Name || 'Unknown'}</a>
                {/if}
              </td>
              <td class="text-right hide-mobile">
                {#if $editMode}
                  <input
                    type="number"
                    class="amount-input"
                    value={material.Amount}
                    min="0"
                    step="1"
                    on:change={(e) => updateMaterial(index, 'Amount', e.target.value)}
                  />
                {:else}
                  {material.Amount}
                {/if}
              </td>
              {#if !$editMode}
                <td class="text-right">{clampDecimals(getLineTT(material), 2, 8)}</td>
                <td class="text-right">
                  <input
                    type="text"
                    class="markup-input"
                    bind:value={markupInputs[index]}
                    on:change={(e) => handleMarkupChange(index, e.target.value)}
                    on:blur={() => handleMarkupBlur(index)}
                  />
                </td>
                <td class="text-right">{clampDecimals(getLineTotal(material, markup[index]), 2, 8)}</td>
              {/if}
              {#if $editMode}
                <td class="actions-col">
                  <button class="btn-remove" on:click={() => removeMaterial(index)} title="Remove material">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </td>
              {/if}
            </tr>
          {/each}
          {#if $editMode}
            <tr class="add-row">
              <td colspan="3">
                <button class="btn-add" on:click={addMaterial}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                  Add Material
                </button>
              </td>
            </tr>
          {/if}
        </tbody>
        <tfoot>
          {#if !$editMode}
            <tr>
              <td class="text-muted">Sum:</td>
              <td class="hide-mobile"></td>
              <td class="text-right">{clampDecimals(totalTT, 2, 8)} PED</td>
              <td class="text-right">{clampDecimals(weightedAvgMU, 1, 4)}%</td>
              <td class="text-right">{clampDecimals(totalWithMarkup, 2, 8)} PED</td>
            </tr>
          {/if}
        </tfoot>
      </table>
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
    gap: 16px;
  }

  .table-container {
    border-radius: 6px;
    overflow: hidden;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
  }

  .materials-table {
    width: 100%;
    border-collapse: collapse;
  }

  .materials-table th {
    padding: 12px 16px;
    text-align: left;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-color);
    background-color: var(--hover-color);
    border-bottom: 1px solid var(--border-color, #555);
    border-right: 1px solid var(--border-color, #555);
  }

  .materials-table th:last-child {
    border-right: none;
  }

  .materials-table td {
    padding: 10px 16px;
    font-size: 14px;
    color: var(--text-color);
    border-bottom: 1px solid var(--border-color, #555);
    border-right: 1px solid var(--border-color, #555);
  }

  .materials-table td:last-child {
    border-right: none;
  }

  .materials-table tbody tr:nth-child(odd) {
    background-color: var(--primary-color);
  }

  .materials-table tbody tr:nth-child(even) {
    background-color: var(--secondary-color);
  }

  .materials-table tbody tr:hover {
    background-color: rgba(59, 130, 246, 0.1);
  }

  .materials-table tbody tr:last-child td {
    border-bottom: none;
  }

  .materials-table tfoot tr {
    background-color: var(--hover-color);
    font-weight: 600;
  }

  .materials-table tfoot td {
    border-bottom: none;
    border-top: 2px solid var(--border-color, #555);
  }

  .materials-table a {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .materials-table a:hover {
    text-decoration: underline;
  }

  .markup-input {
    width: 70px;
    padding: 4px 8px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    font-size: 13px;
    text-align: left;
  }

  .markup-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .material-select {
    width: 100%;
    min-width: 120px;
    padding: 6px 8px;
    font-size: 13px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .amount-input {
    width: 60px;
    padding: 4px 8px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--input-bg, var(--secondary-color));
    color: var(--text-color);
    font-size: 13px;
    text-align: left;
  }

  .amount-input:focus,
  .material-select:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .text-right {
    text-align: right;
  }

  .text-muted {
    color: var(--text-muted, #999);
  }

  .actions-col {
    width: 40px;
    text-align: center;
  }

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

  .add-row {
    background-color: transparent !important;
  }

  .add-row td {
    padding: 8px 16px;
    border-bottom: none;
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

  /* Mobile responsiveness */
  @media (max-width: 600px) {
    .materials-table th,
    .materials-table td {
      padding: 8px 10px;
      font-size: 12px;
    }

    .markup-input {
      width: 55px;
      padding: 3px 6px;
      font-size: 12px;
    }

    .material-select {
      min-width: 80px;
      padding: 4px 6px;
      font-size: 12px;
    }

    .amount-input {
      width: 50px;
      padding: 3px 6px;
      font-size: 12px;
    }

    .hide-mobile {
      display: none;
    }
  }
</style>

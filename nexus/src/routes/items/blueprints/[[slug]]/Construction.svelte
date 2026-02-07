<script>
  // @ts-nocheck
  import { clampDecimals, getItemLink } from '$lib/util';
  import '$lib/style.css';

  export let blueprint;

  let markup;
  let markupInputs;

  $: if (blueprint) {
    resetMarkup();
  }

  function resetMarkup() {
    markup = new Array(blueprint.Materials?.length ?? 0).fill(100);
    markupInputs = markup.map(v => String(v));
  }

  // Validate and update markup value
  function handleMarkupChange(index, value) {
    const trimmed = value.trim();
    const num = parseFloat(trimmed);

    if (trimmed === '' || isNaN(num)) {
      // Keep the old value if invalid
      markupInputs[index] = String(markup[index]);
      markupInputs = markupInputs;
      return;
    }

    // Clamp to reasonable range
    const clamped = Math.max(0, Math.min(100000, num));
    markup[index] = clamped;
    markup = markup;
    markupInputs[index] = String(clamped);
    markupInputs = markupInputs;
  }

  // Handle blur to format the value
  function handleMarkupBlur(index) {
    markupInputs[index] = String(markup[index]);
    markupInputs = markupInputs;
  }

  // Calculate totals
  $: totalTT = (blueprint.Materials ?? []).reduce((acc, mat) => {
    const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
    return acc + (matTT * (mat.Amount || 0));
  }, 0);

  $: totalWithMarkup = (blueprint.Materials ?? []).reduce((acc, mat, i) => {
    const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
    return acc + (matTT * (mat.Amount || 0) * (markup[i] || 100) / 100);
  }, 0);

  // Weighted average MU: sum(tt * mu) / sum(tt)
  $: weightedAvgMU = (() => {
    const sumTTxMU = (blueprint.Materials ?? []).reduce((acc, mat, i) => {
      const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
      const tt = matTT * (mat.Amount || 0);
      return acc + (tt * (markup[i] || 100));
    }, 0);
    return totalTT > 0 ? sumTTxMU / totalTT : 100;
  })();

  // Helper to get line TT
  function getLineTT(mat) {
    const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
    return matTT * (mat.Amount || 0);
  }

  // Helper to get line total with markup
  function getLineTotal(mat, mu) {
    return getLineTT(mat) * (mu || 100) / 100;
  }
</script>

<style>
  .construction-wrapper {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .table-container {
    border-radius: 6px;
    overflow-x: auto;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
  }

  .construction-table {
    width: 100%;
    border-collapse: collapse;
  }

  .construction-table th {
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

  .construction-table th:last-child {
    border-right: none;
  }

  .construction-table td {
    padding: 10px 16px;
    font-size: 14px;
    color: var(--text-color);
    border-bottom: 1px solid var(--border-color, #555);
    border-right: 1px solid var(--border-color, #555);
  }

  .construction-table td:last-child {
    border-right: none;
  }

  .construction-table tbody tr:nth-child(odd) {
    background-color: var(--primary-color);
  }

  .construction-table tbody tr:nth-child(even) {
    background-color: var(--secondary-color);
  }

  .construction-table tbody tr:hover {
    background-color: rgba(59, 130, 246, 0.1);
  }

  .construction-table tbody tr:last-child td {
    border-bottom: none;
  }

  .construction-table tfoot tr {
    background-color: var(--hover-color);
    font-weight: 600;
  }

  .construction-table tfoot td {
    border-bottom: none;
    border-top: 2px solid var(--border-color, #555);
  }

  .construction-table a {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .construction-table a:hover {
    text-decoration: underline;
  }

  .construction-table input[type="text"] {
    width: 70px;
    padding: 4px 8px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    font-size: 13px;
    text-align: right;
  }

  .construction-table input[type="text"]:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .text-right {
    text-align: right;
  }

  .text-muted {
    color: var(--text-muted, #999);
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

  /* Mobile responsiveness */
  @media (max-width: 600px) {
    .construction-table th,
    .construction-table td {
      padding: 8px 10px;
      font-size: 12px;
    }

    .construction-table input[type="text"] {
      width: 55px;
      padding: 3px 6px;
      font-size: 12px;
    }

    .hide-mobile {
      display: none;
    }
  }
</style>

<div class="construction-wrapper">
  <div class="table-container">
    <table class="construction-table">
      <thead>
        <tr>
          <th>Ingredient</th>
          <th class="text-right hide-mobile">Amount</th>
          <th class="text-right">TT</th>
          <th class="text-right">MU (%)</th>
          <th class="text-right">Total</th>
        </tr>
      </thead>
      <tbody>
        {#each blueprint.Materials ?? [] as material, index}
          <tr>
            <td><a href="{getItemLink(material.Item)}">{material.Item.Name}</a></td>
            <td class="text-right hide-mobile">{material.Amount}</td>
            <td class="text-right">{clampDecimals(getLineTT(material), 2, 8)}</td>
            <td class="text-right">
              <input
                type="text"
                bind:value={markupInputs[index]}
                on:change={(e) => handleMarkupChange(index, e.target.value)}
                on:blur={() => handleMarkupBlur(index)}
              />
            </td>
            <td class="text-right">{clampDecimals(getLineTotal(material, markup[index]), 2, 8)}</td>
          </tr>
        {/each}
      </tbody>
      <tfoot>
        <tr>
          <td class="text-muted">Sum:</td>
          <td class="hide-mobile"></td>
          <td class="text-right">{clampDecimals(totalTT, 2, 8)} PED</td>
          <td class="text-right">{clampDecimals(weightedAvgMU, 1, 4)}%</td>
          <td class="text-right">{clampDecimals(totalWithMarkup, 2, 8)} PED</td>
        </tr>
      </tfoot>
    </table>
  </div>

  <div class="product-row">
    <span class="product-label">Product:</span>
    {#if blueprint.Product?.Name}
      <a href={getItemLink(blueprint.Product)} class="product-link">{blueprint.Product.Name}</a>
    {:else}
      <span>N/A</span>
    {/if}
  </div>
</div>

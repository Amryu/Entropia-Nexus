<script lang="ts">
  // @ts-nocheck
  import { createEventDispatcher } from "svelte";
  import { isBlueprint, isItemTierable, isLimited, itemHasCondition } from "../../orderUtils";
  export let show = false;
  export let mode = 'create'; // 'create' | 'edit'
  export let order = null;
  // Dialog-local calculations
  let unitPrice = 0;
  let totalPrice = 0;
  let muLabel = '';
  let ttValueDisplay = '';

  // Helper for rounding
  function clamp2(n) {
    return Math.round((Number(n) || 0) * 100) / 100;
  }

  // Initialize order object for dialog
  /**
   * @param {object} itemOrOrder - Item (for create) or order (for edit)
   * @param {string} type - 'buy' | 'sell'
   * @param {string} mode - 'create' | 'edit'
   */
  export function initOrder(itemOrOrder, type, mode = 'create') {
    if (mode === 'edit' && itemOrOrder && itemOrOrder.Type) {
      // Editing: clone the order
      order = JSON.parse(JSON.stringify(itemOrOrder));
    } else {
      // Creating: build from item
      const item = itemOrOrder;
      order = {
        Type: type === 'buy' ? 'Buy' : 'Sell',
        Item: {
          Name: item?.n ?? null,
          Type: item?.t ?? null,
          MaxTT: item?.MaxTT ?? item?.maxTT ?? null,
        },
        Planet: 'Calypso',
        Quantity: 1,
        CurrentTT: null,
        Markup: null,
        Tiering: {
          Tier: null,
          TierIncreaseRate: null
        },
        Blueprint: {
          QualityRating: null
        }
      };
      // Set defaults for condition/tier/blueprint
      if (isItemTierable(item)) {
        order.Tiering.Tier = 0;
        order.Tiering.TierIncreaseRate = 1;
      }
      if (isBlueprint(item)) {
        order.Blueprint.QualityRating = 1;
      }
      if (itemHasCondition(item) && !isBlueprint(item) && order.Item.MaxTT != null) {
        order.CurrentTT = order.Item.MaxTT;
      }
      order.Markup = 0;
    }
    // After init, recalc prices
    recalcPrices();
  }

  // Recalculate dialog-local price fields
  function recalcPrices() {
    if (!order) return;
    const item = order.Item;
    const isBp = isBlueprint(item);
    const isTier = isItemTierable(item);
    const isLim = isLimited(item);
    const hasCond = itemHasCondition(item);
    const maxTT = Number(item?.MaxTT) || 0;
    const qty = isTier ? 1 : Math.max(0, Number(order.Quantity) || 0);
    let mu = Number(order.Markup) || 0;
    let value = Number(order.CurrentTT) || 0;
    let qr = Number(order.Blueprint?.QualityRating) || 0;
    // Unit price
    if (hasCond) {
      if (isBp) {
        unitPrice = clamp2(qr / 100 + mu);
      } else {
        unitPrice = clamp2(value + mu);
      }
    } else {
      unitPrice = clamp2(maxTT * (mu / 100));
    }
    totalPrice = clamp2(qty * unitPrice);
    muLabel = hasCond ? `+${clamp2(mu).toFixed(2)} PED` : `${Math.max(0, mu).toFixed(0)}% of Max TT`;
    ttValueDisplay = !hasCond
      ? `Max TT: ${maxTT || 'N/A'}`
      : isBp
        ? `QR ${qr.toFixed(2)} (=${clamp2(qr / 100).toFixed(2)} PED)`
        : `Current TT: ${clamp2(value).toFixed(2)} PED`;
  }

  // Watch for changes to recalc
  $: if (order) recalcPrices();
  export let  planets = [
    'Calypso', 'Arkadia', 'Cyrene', 'Rocktropia', 'Next Island', 'Monria', 'Toulan', 'Other'
  ];
  const dispatch = createEventDispatcher();

  function close() {
    dispatch('close');
  }
  function submit() {
    dispatch('submit');
  }
</script>

{#if show}
  <div
    class="modal-overlay"
    role="button"
    tabindex="0"
    on:click={(e) => {
      if (e.target.classList.contains('modal-overlay')) close();
    }}
    on:keydown={(e) => {
      if (e.key === 'Escape' || e.key === 'Enter') close();
    }}
  >
    <div class="modal">
      <h3 style="margin-top:0;">
        {mode === 'create' ? 'Create' : 'Edit'} {order.Type} Order
      </h3>
      <div class="form-row">
        <div class="form-label">Item</div>
        <div>{order.Item?.Name}</div>
      </div>
      <div class="form-row">
        <label for="planetSelect">Planet</label>
        <select
          id="planetSelect"
          bind:value={order.Planet}
          class="filter-select select-center">
          {#each planets as p}
            <option>{p}</option>
          {/each}
        </select>
      </div>
      {#if !isItemTierable(order.Item)}
        <div class="form-row">
          <label for="qtyInput">Quantity</label>
          <input
            id="qtyInput"
            type="number"
            min="1"
            bind:value={order.Quantity}
            on:input={recalcPrices}
          />
        </div>
      {/if}
      {#if isItemTierable(order.Item)}
        <div class="form-row">
          <label for="tierInput">Tier</label>
          <input
            id="tierInput"
            type="number"
            min="0"
            max="10"
            step="0.01"
            bind:value={order.Tiering.Tier}
            on:input={recalcPrices}
          />
        </div>
        <div class="form-row">
          <label for="tirInput">TiR</label>
          <input
            id="tirInput"
            type="number"
            min=1
            max={isLimited(order.Item) ? 4000 : 200}
            step="1"
            bind:value={order.Tiering.TierIncreaseRate}
            on:input={recalcPrices}
          />
        </div>
      {/if}
      {#if itemHasCondition(order.Item)}
        {#if isBlueprint(order.Item)}
          <div class="form-row">
            <label for="bpCond">QR</label>
            <input
              id="bpCond"
              type="number"
              min="1"
              max="100"
              step="0.0001"
              bind:value={order.Blueprint.QualityRating}
              on:input={recalcPrices}
            />
          </div>
        {:else}
          <div class="form-row">
            <label for="valueInput">Current TT (PED)</label>
            <input
              id="valueInput"
              type="number"
              min="0"
              step="0.01"
              bind:value={order.CurrentTT}
              on:input={recalcPrices}
            />
          </div>
        {/if}
        <div class="form-row">
          <label for="muPlus">Markup (+PED)</label>
          <input
            id="muPlus"
            type="number"
            min="0"
            step="0.01"
            bind:value={order.Markup}
            on:input={recalcPrices}
          />
        </div>
      {:else}
        <div class="form-row">
          <label for="muPct">Markup (%)</label>
          <input
            id="muPct"
            type="number"
            min="100"
            step="1"
            bind:value={order.Markup}
            on:input={recalcPrices}
          />
        </div>
      {/if}
      <div class="form-row">
        <div class="form-label">Calculation</div>
        <div>
          {#if itemHasCondition(order.Item)}
            {#if isBlueprint(order.Item)}
              {`Unit: ${(Number(order.Blueprint.QualityRating) / 100).toFixed(2)} + MU = ${unitPrice.toFixed(2)} | Total: ${isItemTierable(order.Item) ? 1 : Number(order.Quantity) || 0}×${unitPrice.toFixed(2)} = ${totalPrice.toFixed(2)} PED`}
            {:else}
              {`Unit: ${(Number(order.CurrentTT) || 0).toFixed(2)} + MU = ${unitPrice.toFixed(2)} | Total: ${isItemTierable(order.Item) ? 1 : Number(order.Quantity) || 0}×${unitPrice.toFixed(2)} = ${totalPrice.toFixed(2)} PED`}
            {/if}
          {:else}
            {`Unit: ${(Number(order.Item.MaxTT) || 0).toFixed(2)} × ${(Number(order.Markup) || 0).toFixed(0)}% = ${unitPrice.toFixed(2)} | Total: ${isItemTierable(order.Item) ? 1 : Number(order.Quantity) || 0}×${unitPrice.toFixed(2)} = ${totalPrice.toFixed(2)} PED`}
          {/if}
        </div>
      </div>
      <div class="actions">
        <button on:click={close}>Cancel</button>
        <button on:click={submit} title="Save order">Submit</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 3;
  }
  .modal {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--text-color);
    border-radius: 6px;
    padding: 16px;
    width: 420px;
    max-width: calc(100% - 32px);
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }
  .form-row {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 8px;
    align-items: center;
    margin: 8px 0;
  }
  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 12px;
  }
</style>

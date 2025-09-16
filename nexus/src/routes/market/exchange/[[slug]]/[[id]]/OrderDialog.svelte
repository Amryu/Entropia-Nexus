<script lang="ts">
  // @ts-nocheck
  import { createEventDispatcher } from "svelte";
  import { isBlueprint, isItemTierable, isLimited, itemHasCondition, isPercentMarkup, getMaxTT } from "../../orderUtils";
  import { hasItemTag, apiCall } from "$lib/util";
  export let show = false;
  export let mode = 'create'; // 'create' | 'edit'
  export let order = null;
  // Dialog-local calculations
  let unitPrice = 0;
  let totalPrice = 0;
  let muLabel = '';
  let ttValueDisplay = '';
  // Pet skills data and selection state
  let petSkillOptions = [];
  let selectedSkillKey = '';
  let selectedSkillUnlocked = false;
  let selectedSkillCriteria = 0; // percent
  let lastLoadedPetKey = null; // track to avoid refetch loops

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
      // Ensure pet metadata scaffolding when editing
      if (order?.Item?.Type === 'Pet') {
        order.Metadata = order.Metadata || {};
        order.Metadata.Pet = order.Metadata.Pet || { Level: 1, Experience: 0, Skills: [], Food: 0 };
        order.Item.Metadata = order.Item.Metadata || {};
        order.Item.Metadata.Skills = Array.isArray(order.Item.Metadata.Skills) ? order.Item.Metadata.Skills : [];
        const key = order?.Item?.Id ?? order?.Item?.Name ?? null;
        if (key != null) loadPetSkills(String(key));
      }
    } else {
      // Creating: build from item
      const item = itemOrOrder;
      order = {
        Type: type === 'buy' ? 'Buy' : 'Sell',
        Item: {
          Name: item?.Name ?? item?.n ?? null,
          Type: item?.Type ?? item?.Properties?.Type ?? item?.t ?? null,
          MaxTT: getMaxTT(item),
        },
        Planet: 'Calypso',
        Quantity: 1,
        CurrentTT: null,
        // Default MU: 100% for L/stackables, 0 otherwise; will be refined by field mode
        Markup: hasItemTag(item?.Name || item?.n, "L") ? 100 : 0,
        Metadata: {}
      };
      // Set defaults for condition/tier/blueprint
      if (isItemTierable(item)) {
        order.Metadata.Tier = 0;
        order.Metadata.TierIncreaseRate = 1;
      }
      if (isBlueprint(item)) {
        order.Metadata.QualityRating = 1;
      }
      if (item?.Properties?.Type === 'Pet' || item?.Type === 'Pet' || item?.t === 'Pet') {
        order.Metadata.Pet = {
          Level: 1,
          Experience: 0,
          Skills: [],
          Food: 0,
        };
        order.Item.Metadata = order.Item.Metadata || {};
        order.Item.Metadata.Skills = Array.isArray(order.Item.Metadata.Skills) ? order.Item.Metadata.Skills : [];
        // Kick off pet skills loading (by name as fallback id)
        const key = item?.Id ?? item?.i ?? item?.Name ?? item?.n ?? null;
        if (key != null) loadPetSkills(String(key));
      }
      
      if (itemHasCondition(item) && !isBlueprint(item) && order.Item.MaxTT != null) {
        order.CurrentTT = order.Item.MaxTT;
      }
      // For non-L or absolute MU items, default MU to 0
      if (!hasItemTag(item?.Name || item?.n, "L")) {
        order.Markup = 0;
      }
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
  // Any item with instance-specific metadata (tier/condition/blueprint/pet or explicit metadata) is non-fungible => qty fixed to 1
  const hasMetaKeys = !!order?.Metadata && Object.keys(order.Metadata).length > 0;
  const hasItemMetaKeys = !!order?.Item?.Metadata && Object.keys(order.Item.Metadata).length > 0;
  const isInstanceItem = isTier || hasCond || isBp || (item?.Type === 'Pet') || hasMetaKeys || hasItemMetaKeys;
    const qty = isInstanceItem ? 1 : Math.max(0, Number(order.Quantity) || 0);
    if (isInstanceItem && order.Quantity !== 1) {
      order.Quantity = 1;
    }
    let mu = Number(order.Markup) || 0;
    let value = Number(order.CurrentTT) || 0;
  let qr = Number(order.Metadata?.QualityRating) || 0;
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
  // When pet level changes, refresh disabled/color state (options re-compute from order state)
  $: petSkillOptions = petSkillOptions.sort((a, b) => a.level - b.level);

  // Derived flags for template: show Quantity only for fungible items (no instance metadata)
  $: showQuantity = (() => {
    if (!order) return false;
    const item = order.Item || {};
    const hasMetaKeys = !!order?.Metadata && Object.keys(order.Metadata).length > 0;
    const hasItemMetaKeys = !!order?.Item?.Metadata && Object.keys(order.Item.Metadata).length > 0;
    const isInstanceItem = isItemTierable(item) || itemHasCondition(item) || isBlueprint(item) || (item?.Type === 'Pet') || hasMetaKeys || hasItemMetaKeys;
    return !isInstanceItem;
  })();

  async function loadPetSkills(idOrName) {
    try {
      const key = String(idOrName || '');
      if (!key) return;
      if (lastLoadedPetKey === key) return; // avoid refetch if same pet
      const path = `/pets/${encodeURIComponent(key)}`;
      let data = await apiCall(window.fetch, path);
      // Dev fallback: if nothing returned and running locally, try explicit localhost API
      if (!data && typeof window !== 'undefined' && window.location.hostname === 'localhost') {
        data = await apiCall(window.fetch, path, 'http://localhost:3000');
      }
      // API returns a Pet object with an Effects array
      const list = Array.isArray(data)
        ? data
        : (Array.isArray(data?.Effects)
            ? data.Effects
            : (Array.isArray(data?.Skills) ? data.Skills : []));
      // Normalize into options: duplicate IDs allowed for different unlock levels
      petSkillOptions = (list || [])
        .map((e, idx) => {
          const eff = e || {};
          const id = eff.Id ?? idx;
          const name = eff.Name ?? 'Unknown';
          const unlockLvl = Number(eff?.Properties?.Unlock?.Level ?? eff.Unlock?.Level ?? 0) || 0;
          const strength = eff?.Properties?.Strength ?? eff.Strength ?? null;
          const unit = eff?.Properties?.Unit ?? eff.Unit ?? '';
          const key = `${id}@${unlockLvl}`;
          return {
            key,
            id,
            name,
            level: unlockLvl,
            strength,
            unit: unit || '',
            // label computed later using current order state
          };
        })
        .sort((a, b) => a.level - b.level);
  // Mark loaded only after success
  lastLoadedPetKey = key;
      // Reset selection UI
      selectedSkillKey = '';
      selectedSkillUnlocked = false;
      selectedSkillCriteria = 0;
    } catch (e) {
      // On error, clear
      petSkillOptions = [];
    }
  }

  // Reflect the popup state into order.Item.Metadata.Skills
  function updateSkillMetadata() {
    if (!order) return;
    order.Item = order.Item || {};
    order.Item.Metadata = order.Item.Metadata || {};
    const arr = Array.isArray(order.Item.Metadata.Skills)
      ? order.Item.Metadata.Skills
      : (order.Item.Metadata.Skills = []);
    // Identify current option
    const opt = petSkillOptions.find(o => o.key === selectedSkillKey);
    if (!opt) return;
    const existsIdx = arr.findIndex(s => s?.Level === opt.level && s?.Name === opt.name);
    const shouldHave = !!selectedSkillKey && (selectedSkillUnlocked || (Number(selectedSkillCriteria) || 0) > 0);
    if (shouldHave) {
      const entry = { Level: opt.level, Name: opt.name };
      if (existsIdx >= 0) arr[existsIdx] = entry; else arr.push(entry);
    } else if (existsIdx >= 0) {
      arr.splice(existsIdx, 1);
    }
  }

  $: if (selectedSkillKey !== undefined) updateSkillMetadata();
  $: if (selectedSkillUnlocked !== undefined) updateSkillMetadata();
  $: if (selectedSkillCriteria !== undefined) updateSkillMetadata();
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
  {#if showQuantity}
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
      {#if order.Item.Type === 'Pet'}
        <div class="form-row">
          <label for="petLevel">Level</label>
          <input
            id="petLevel"
            type="number"
            min="1"
            bind:value={order.Metadata.Pet.Level}
            on:input={recalcPrices}
          />
        </div>
        <div class="form-row">
          <label for="petExperience">Experience</label>
          <input
            id="petExperience"
            type="number"
            min="0"
            bind:value={order.Metadata.Pet.Experience}
            on:input={recalcPrices}
          />
        </div>
        <div class="form-row skill-row">
          <label for="petSkillSelect">Pet Skill</label>
          <div class="skill-select-wrap">
            <select
              id="petSkillSelect"
              class="filter-select select-center"
              bind:value={selectedSkillKey}
              on:change={() => {
                // Reset popup toggles for new selection
                selectedSkillUnlocked = false;
                selectedSkillCriteria = 0;
              }}
            >
              <option value="">-- none --</option>
              {#each petSkillOptions as opt}
                {#key opt.key}
                  {#if true}
                    <option
                      value={opt.key}
                      disabled={Number(order?.Metadata?.Pet?.Level||0) < opt.level}
                      class={
                        (Number(order?.Metadata?.Pet?.Level||0) < opt.level)
                          ? 'opt-disabled'
                          : (Array.isArray(order?.Item?.Metadata?.Skills) && order.Item.Metadata.Skills.some(s => s.Level === opt.level && s.Name === opt.name))
                            ? 'opt-unlocked'
                            : 'opt-locked'
                      }
                      style={
                        Number(order?.Metadata?.Pet?.Level||0) < opt.level
                          ? 'color: var(--text-color); opacity: 0.6;'
                          : (Array.isArray(order?.Item?.Metadata?.Skills) && order.Item.Metadata.Skills.some(s => s.Level === opt.level && s.Name === opt.name))
                            ? 'color: var(--success-color, #34c759);'
                            : 'color: var(--danger-color, #ff6b6b);'
                      }
                    >
                      {`L${opt.level}: ${opt.name} (${opt.strength ?? ''}${opt.unit ?? ''})`}
                    </option>
                  {/if}
                {/key}
              {/each}
            </select>

            {#if selectedSkillKey}
              <div class="skill-popover" role="dialog" aria-label="Skill options">
                <div class="row">
                  <label class="cbx">
                    <input type="checkbox" bind:checked={selectedSkillUnlocked} />
                    <span>Unlocked</span>
                  </label>
                </div>
                {#if !selectedSkillUnlocked}
                  <div class="row">
                    <label for="criteriaPct">Criteria (%)</label>
                    <input id="criteriaPct" type="number" min="0" max="100" step="1" bind:value={selectedSkillCriteria} />
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        </div>
        <div class="form-row">
          <label for="petFood">Food</label>
          <input
            id="petFood"
            type="number"
            min="0"
            bind:value={order.Metadata.Pet.Food}
            on:input={recalcPrices}
          />
        </div>
      {/if}
      {#if isItemTierable(order.Item)}
        <div class="form-row">
          <label for="tierInput">{order.Type === 'Buy' ? 'Min. ' : ''}Tier</label>
          <input
            id="tierInput"
            type="number"
            min="0"
            max="10"
            step="0.01"
            bind:value={order.Metadata.Tier}
            on:input={recalcPrices}
          />
        </div>
        <div class="form-row">
          <label for="tirInput">{order.Type === 'Buy' ? 'Min. ' : ''}TiR</label>
          <input
            id="tirInput"
            type="number"
            min=1
            max={isLimited(order.Item) ? 4000 : 200}
            step="1"
            bind:value={order.Metadata.TierIncreaseRate}
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
              bind:value={order.Metadata.QualityRating}
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
      {/if}
      {#if isPercentMarkup(order.Item)}
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
      {:else}
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
      {/if}
      <div class="form-row">
        <div class="form-label">Calculation</div>
        <div>
          {#if itemHasCondition(order.Item)}
            {#if isBlueprint(order.Item)}
              {@html `Unit: ${(Number(order.Metadata?.QualityRating) / 100).toFixed(2)} + MU = ${unitPrice.toFixed(2)}<br />Total: ${showQuantity ? (Number(order.Quantity) || 0) : 1}×${unitPrice.toFixed(2)} = ${totalPrice.toFixed(2)} PED`}
            {:else}
              {@html `Unit: ${(Number(order.CurrentTT) || 0).toFixed(2)} + MU = ${unitPrice.toFixed(2)}<br />Total: ${showQuantity ? (Number(order.Quantity) || 0) : 1}×${unitPrice.toFixed(2)} = ${totalPrice.toFixed(2)} PED`}
            {/if}
          {:else}
            {@html `Unit: ${(Number(order.Item.MaxTT) || 0).toFixed(2)} × ${(Number(order.Markup) || 0).toFixed(0)}% = ${unitPrice.toFixed(2)}<br />Total: ${showQuantity ? (Number(order.Quantity) || 0) : 1}×${unitPrice.toFixed(2)} = ${totalPrice.toFixed(2)} PED`}
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
  .skill-row .skill-select-wrap {
    position: relative;
    display: flex;
    align-items: flex-start;
    gap: 8px;
  }
  .skill-row select {
    width: 100%;
  }
  .skill-popover {
    position: absolute;
    top: 0; /* align to dropdown height position */
    left: calc(100% + 8px);
    min-width: 220px;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--text-color);
    border-radius: 6px;
    padding: 8px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
    z-index: 5;
  }
  .skill-popover .row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 6px 0;
  }
  .skill-popover .cbx {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  /* Option classes as fallback; some browsers ignore them in <option> */
  .opt-disabled { opacity: 0.6; }
  .opt-locked { color: #ff6b6b; }
  .opt-unlocked { color: #34c759; }
</style>

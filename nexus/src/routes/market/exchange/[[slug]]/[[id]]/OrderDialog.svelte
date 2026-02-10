<script lang="ts">
  // @ts-nocheck
  import { createEventDispatcher } from "svelte";
  import { isBlueprint, isItemTierable, isLimited, itemHasCondition, isPercentMarkup, getMaxTT } from "../../orderUtils";
  import { hasItemTag, apiCall } from "$lib/util";
  import { getPercentUndercutAmount, getAbsoluteUndercutAmount, DEFAULT_PARTIAL_RATIO } from '../../exchangeConstants.js';
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

  // Price suggestions
  let suggestions = null; // { bestBuy, bestSell }
  let suggestionsLoading = false;
  let dailyAverage = null;

  // Partial trade state
  let allowPartial = true;

  /** @type {number} How many orders already exist for this item+side */
  export let existingOrderCount = 0;

  /** @type {number} Max orders allowed per item */
  export let maxOrdersPerItem = 5;

  /** @type {boolean} Whether this is a non-fungible item (allows multiple orders) */
  export let isNonFungible = false;

  // Track orders created in this multi-order session
  let sessionOrderCount = 0;

  async function loadSuggestions(itemId) {
    if (!itemId) return;
    suggestionsLoading = true;
    suggestions = null;
    try {
      const res = await fetch(`/api/market/exchange/orders/item/${encodeURIComponent(itemId)}`);
      if (res.ok) {
        const data = await res.json();
        const buyOrders = data.buy || [];
        const sellOrders = data.sell || [];
        // Best buy = highest markup among buy orders
        const bestBuy = buyOrders.length > 0
          ? Math.max(...buyOrders.map(o => Number(o.markup) || 0))
          : null;
        // Best sell = lowest markup among sell orders
        const bestSell = sellOrders.length > 0
          ? Math.min(...sellOrders.map(o => Number(o.markup) || 0))
          : null;
        suggestions = { bestBuy, bestSell };
      }
    } catch (e) {
      // Silently fail - suggestions are optional
    } finally {
      suggestionsLoading = false;
    }
  }

  async function loadDailyAverage(itemId) {
    if (!itemId) return;
    dailyAverage = null;
    try {
      const now = new Date();
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      const res = await fetch(
        `/api/market/prices/${encodeURIComponent(itemId)}?granularity=day&from=${weekAgo.toISOString()}&to=${now.toISOString()}&limit=1`
      );
      if (res.ok) {
        const data = await res.json();
        if (data.data?.length > 0) {
          const latest = data.data[data.data.length - 1];
          dailyAverage = latest.avg ?? latest.wap ?? null;
        }
      }
    } catch {
      // Silently fail
    }
  }

  function applySuggestion(value) {
    if (!order || value == null) return;
    order.Markup = value;
    recalcPrices();
  }

  function computeUndercutValue(bestMarkup, orderType) {
    const isPct = isPercentMarkup(order?.Item);
    const undercutAmt = isPct
      ? getPercentUndercutAmount(bestMarkup)
      : getAbsoluteUndercutAmount(bestMarkup);
    if (orderType === 'Sell') {
      return Math.max(isPct ? 100 : 0, clamp2(bestMarkup - undercutAmt));
    }
    return clamp2(bestMarkup + undercutAmt);
  }

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
  export function initOrder(itemOrOrder, type, dialogMode = 'create') {
    mode = dialogMode;
    sessionOrderCount = 0;
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
    } else if (itemOrOrder?.Item?.Name != null) {
      // Pre-built order object (e.g. from inventory sell) — clone and apply defaults
      order = JSON.parse(JSON.stringify(itemOrOrder));
      order.Type = order.Type || (type === 'buy' ? 'Buy' : 'Sell');
      order.Planet = order.Planet || 'Calypso';
      order.Quantity = order.Quantity || 1;
      order.CurrentTT = order.CurrentTT ?? null;
      order.Metadata = order.Metadata || {};
      order.MinQuantity = order.MinQuantity ?? null;

      // Derive item-type-aware defaults from the nested Item
      const itemType = order.Item?.Type;
      const itemRef = { Type: itemType, Properties: { Type: itemType } };
      if (order.Markup == null || order.Markup === 0) {
        order.Markup = isPercentMarkup(itemRef) ? 100 : 0;
      }
      if (isItemTierable(itemRef)) {
        if (order.Metadata.Tier == null) order.Metadata.Tier = 0;
        if (order.Metadata.TierIncreaseRate == null) order.Metadata.TierIncreaseRate = 1;
      }
      if (isBlueprint(itemRef)) {
        if (order.Metadata.QualityRating == null) order.Metadata.QualityRating = type === 'buy' ? '0' : 1;
      }
      if (itemType === 'Pet') {
        order.Metadata.Pet = order.Metadata.Pet || { Level: 1, Experience: 0, Skills: [], Food: 0 };
        order.Item.Metadata = order.Item.Metadata || {};
        order.Item.Metadata.Skills = Array.isArray(order.Item.Metadata.Skills) ? order.Item.Metadata.Skills : [];
        const key = order.Item?.Id ?? order.Item?.Name ?? null;
        if (key != null) loadPetSkills(String(key));
      }
      if (itemHasCondition(itemRef) && !isBlueprint(itemRef) && order.Item.MaxTT != null && order.CurrentTT == null) {
        order.CurrentTT = order.Item.MaxTT;
      }
      allowPartial = true;
      order.MinQuantity = order.MinQuantity ?? Math.max(1, Math.floor((order.Quantity || 1) * DEFAULT_PARTIAL_RATIO));
    } else {
      // Creating: build from raw item
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
        Markup: isPercentMarkup(item) ? 100 : 0,
        MinQuantity: null,
        Metadata: {}
      };
      // Set defaults for condition/tier/blueprint
      if (isItemTierable(item)) {
        order.Metadata.Tier = 0;
        order.Metadata.TierIncreaseRate = 1;
      }
      if (isBlueprint(item)) {
        order.Metadata.QualityRating = type === 'buy' ? '0' : 1;
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
      allowPartial = true;
      order.MinQuantity = Math.max(1, Math.floor((order.Quantity || 1) * DEFAULT_PARTIAL_RATIO));
    }

    // Restore partial trade state for edit mode
    if (mode === 'edit') {
      const existingMin = itemOrOrder?.MinQuantity ?? itemOrOrder?.min_quantity ?? null;
      allowPartial = existingMin != null && existingMin > 0;
      if (allowPartial && !order.MinQuantity && existingMin) order.MinQuantity = existingMin;
      if (!allowPartial) order.MinQuantity = null;
    }

    // After init, recalc prices
    recalcPrices();

    // Load price suggestions and daily average
    const suggestId = itemOrOrder?.Id ?? itemOrOrder?.i ?? itemOrOrder?.ItemId ?? itemOrOrder?.Item?.Id ?? null;
    if (suggestId) {
      loadSuggestions(suggestId);
      loadDailyAverage(suggestId);
    }
  }

  // Recalculate dialog-local price fields
  function recalcPrices() {
    if (!order) return;
    const item = order.Item;
    const isBp = isBlueprint(item);
    const isTier = isItemTierable(item);
    const hasCond = itemHasCondition(item);
    const isPctMu = isPercentMarkup(item);
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
    const isBuyOrder = order.Type === 'Buy';
    // Unit price
    if (isBp) {
      // Blueprints: buy orders have QR range, sell uses QR value + absolute markup
      unitPrice = isBuyOrder ? clamp2(mu) : clamp2(qr / 100 + mu);
    } else if (isPctMu) {
      // Percent markup: MaxTT × markup%
      unitPrice = clamp2(maxTT * (mu / 100));
    } else if (hasCond) {
      // Absolute markup with condition: CurrentTT + markup PED
      unitPrice = clamp2(value + mu);
    } else {
      // Absolute markup without condition: MaxTT + markup PED
      unitPrice = clamp2(maxTT + mu);
    }
    totalPrice = clamp2(qty * unitPrice);
    muLabel = isPctMu ? `${Math.max(0, mu).toFixed(0)}% of Max TT` : `+${clamp2(mu).toFixed(2)} PED`;
    ttValueDisplay = isPctMu
      ? `Max TT: ${maxTT || 'N/A'}`
      : isBp
        ? (isBuyOrder ? `QR range filter` : `QR ${qr.toFixed(2)} (=${clamp2(qr / 100).toFixed(2)} PED)`)
        : hasCond
          ? `Current TT: ${clamp2(value).toFixed(2)} PED`
          : `Max TT: ${maxTT || 'N/A'}`;
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
    'Calypso', 'Arkadia', 'Cyrene', 'Rocktropia', 'Next Island', 'Monria', 'Toulan', 'Howling Mine (Space)'
  ];
  // QR range options for buy orders (matching the exchange filter pattern)
  const qrRangeOptions = [
    ...Array.from({ length: 10 }, (_, i) => ({
      label: `${i * 10 + 1}-${i * 10 + 9}`,
      value: `${i * 10}`
    })),
    { label: "100", value: "100" }
  ];


  // Inventory-sourced warnings
  $: inventoryWarning = order?._inventoryWarning || null;
  $: inventoryQty = order?._inventoryQty ?? null;
  $: totalOrdersIfSubmitted = existingOrderCount + sessionOrderCount + 1;
  $: canCreateMore = isNonFungible && totalOrdersIfSubmitted < maxOrdersPerItem && mode === 'create';
  $: orderLimitReached = totalOrdersIfSubmitted >= maxOrdersPerItem;
  // For inventory sell: warn if total sell orders exceed inventory qty
  $: totalSellQty = (() => {
    if (inventoryQty == null || order?.Type !== 'Sell') return null;
    return (existingOrderCount + sessionOrderCount + 1);
  })();
  $: qtyExceedsInventory = inventoryQty != null && totalSellQty != null && totalSellQty > inventoryQty;

  /** @type {boolean} Prevent double-click submission */
  export let submitting = false;

  const dispatch = createEventDispatcher();

  function close() {
    sessionOrderCount = 0;
    dispatch('close');
  }
  function submit() {
    if (submitting) return;
    dispatch('submit', { order });
    sessionOrderCount = 0;
  }
  function submitAndNext() {
    if (submitting) return;
    dispatch('next', { order });
    sessionOrderCount++;
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
      {#if inventoryWarning}
        <div class="inv-warning-banner">{inventoryWarning}</div>
      {/if}
      {#if qtyExceedsInventory}
        <div class="inv-warning-banner">Order quantity exceeds your inventory ({inventoryQty} available)</div>
      {/if}
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
            on:input={() => {
              recalcPrices();
              if (allowPartial && order.MinQuantity > order.Quantity) {
                order.MinQuantity = order.Quantity;
              }
            }}
          />
        </div>
        <div class="form-row">
          <label class="partial-label">
            <input type="checkbox" bind:checked={allowPartial} on:change={() => {
              if (allowPartial) {
                order.MinQuantity = Math.max(1, Math.floor((order.Quantity || 1) * DEFAULT_PARTIAL_RATIO));
              } else {
                order.MinQuantity = null;
              }
            }} />
            Allow Partial
          </label>
          <input
            type="number"
            min="1"
            max={order.Quantity || 1}
            bind:value={order.MinQuantity}
            placeholder="Min qty"
            disabled={!allowPartial}
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
            step="1"
            bind:value={order.Metadata.Tier}
            on:input={recalcPrices}
            on:blur={() => { order.Metadata.Tier = Math.max(0, Math.min(10, Math.round(Number(order.Metadata.Tier) || 0))); recalcPrices(); }}
          />
        </div>
        <div class="form-row">
          <label for="tirInput">{order.Type === 'Buy' ? 'Min. ' : ''}TiR</label>
          <input
            id="tirInput"
            type="number"
            min="0"
            max={isLimited(order.Item) ? 4000 : 200}
            step="1"
            bind:value={order.Metadata.TierIncreaseRate}
            on:input={recalcPrices}
            on:blur={() => { const maxTir = isLimited(order.Item) ? 4000 : 200; order.Metadata.TierIncreaseRate = Math.max(0, Math.min(maxTir, Math.round(Number(order.Metadata.TierIncreaseRate) || 0))); recalcPrices(); }}
          />
        </div>
      {/if}
      {#if itemHasCondition(order.Item)}
        {#if isBlueprint(order.Item)}
          <div class="form-row">
            <label for="bpCond">QR</label>
            {#if order.Type === 'Sell'}
              <input
                id="bpCond"
                type="number"
                min="1"
                max="100"
                step="1"
                bind:value={order.Metadata.QualityRating}
                on:input={recalcPrices}
                on:blur={() => { order.Metadata.QualityRating = Math.max(1, Math.min(100, Math.round(Number(order.Metadata.QualityRating) || 1))); recalcPrices(); }}
              />
            {:else}
              <select
                id="bpCond"
                class="filter-select select-center"
                bind:value={order.Metadata.QualityRating}
                on:change={recalcPrices}
              >
                {#each qrRangeOptions as opt}
                  <option value={opt.value}>{opt.label}</option>
                {/each}
              </select>
            {/if}
          </div>
        {:else}
          <div class="form-row max-tt-row">
            <label>Max TT</label>
            <div class="static-value">{order.Item.MaxTT != null ? `${Number(order.Item.MaxTT).toFixed(2)} PED` : 'N/A'}</div>
          </div>
          <div class="form-row">
            <label for="valueInput">Current TT (PED)</label>
            <input
              id="valueInput"
              type="number"
              min="0"
              max={order.Item.MaxTT ?? undefined}
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
      {#if suggestions || dailyAverage != null}
        <div class="form-row">
          <div class="form-label">Suggestions</div>
          <div class="suggestions">
            {#if order.Type === 'Sell'}
              {#if suggestions?.bestSell != null}
                <button class="suggest-btn" on:click={() => applySuggestion(suggestions.bestSell)} title="Match the lowest sell order">
                  Match Best ({suggestions.bestSell.toFixed(isPercentMarkup(order.Item) ? 0 : 2)})
                </button>
                <button class="suggest-btn undercut" on:click={() => applySuggestion(computeUndercutValue(suggestions.bestSell, 'Sell'))} title="Undercut the lowest sell by ~2%">
                  Undercut
                </button>
              {:else if suggestions}
                <span class="suggest-hint">No sell orders yet</span>
              {/if}
            {:else}
              {#if suggestions?.bestBuy != null}
                <button class="suggest-btn" on:click={() => applySuggestion(suggestions.bestBuy)} title="Match the highest buy order">
                  Match Best ({suggestions.bestBuy.toFixed(isPercentMarkup(order.Item) ? 0 : 2)})
                </button>
                <button class="suggest-btn outbid" on:click={() => applySuggestion(computeUndercutValue(suggestions.bestBuy, 'Buy'))} title="Outbid the highest buy by ~2%">
                  Outbid
                </button>
              {:else if suggestions}
                <span class="suggest-hint">No buy orders yet</span>
              {/if}
            {/if}
            {#if dailyAverage != null}
              <button class="suggest-btn daily" on:click={() => applySuggestion(dailyAverage)} title="Use the daily average markup">
                Daily Avg ({dailyAverage.toFixed(isPercentMarkup(order.Item) ? 0 : 2)})
              </button>
            {/if}
          </div>
        </div>
      {/if}
      <div class="calc-grid">
        <span class="calc-label">{showQuantity ? 'Unit' : 'Price'}</span>
        <span class="calc-value">
          {#if isBlueprint(order.Item)}
            {#if order.Type === 'Buy'}
              MU = {unitPrice.toFixed(2)} PED
            {:else}
              {(Number(order.Metadata?.QualityRating) / 100).toFixed(2)} + {(Number(order.Markup) || 0).toFixed(2)} = {unitPrice.toFixed(2)} PED
            {/if}
          {:else if isPercentMarkup(order.Item)}
            {(Number(order.Item.MaxTT) || 0).toFixed(2)} &times; {(Number(order.Markup) || 0).toFixed(0)}% = {unitPrice.toFixed(2)} PED
          {:else if itemHasCondition(order.Item)}
            {(Number(order.CurrentTT) || 0).toFixed(2)} + {(Number(order.Markup) || 0).toFixed(2)} = {unitPrice.toFixed(2)} PED
          {:else}
            {(Number(order.Item.MaxTT) || 0).toFixed(2)} + {(Number(order.Markup) || 0).toFixed(2)} = {unitPrice.toFixed(2)} PED
          {/if}
        </span>
        {#if showQuantity}
          <span class="calc-label">Total</span>
          <span class="calc-value">
            {Number(order.Quantity) || 0} &times; {unitPrice.toFixed(2)} = {totalPrice.toFixed(2)} PED
          </span>
        {/if}
      </div>
      {#if qtyExceedsInventory}
        <div class="inventory-warning">You are creating more sell orders than you have in your inventory ({inventoryQty}).</div>
      {/if}
      {#if isNonFungible && mode === 'create' && (existingOrderCount + sessionOrderCount > 0)}
        <div class="order-count-indicator">Order {existingOrderCount + sessionOrderCount + 1} of {maxOrdersPerItem}</div>
      {/if}
      <div class="actions">
        {#if mode === 'edit'}
          <button class="delete-btn" on:click={() => dispatch('delete', { order })} title="Delete this order">Delete</button>
        {/if}
        <span class="actions-spacer"></span>
        <button on:click={close} disabled={submitting}>{sessionOrderCount > 0 ? 'Done' : 'Cancel'}</button>
        {#if canCreateMore && !orderLimitReached}
          <button class="next-btn" on:click={submitAndNext} disabled={submitting} title="Create this order and set up the next one">{submitting ? 'Saving...' : 'Next'}</button>
        {/if}
        <button on:click={submit} disabled={orderLimitReached || submitting} title={mode === 'edit' ? 'Save changes' : 'Submit order'}>{submitting ? 'Saving...' : (mode === 'edit' ? 'Save' : 'Submit')}</button>
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
    z-index: 20;
  }
  .modal {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    width: 440px;
    max-width: calc(100% - 32px);
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }
  .modal h3 {
    font-size: 16px;
    font-weight: 600;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 12px;
  }
  .form-row {
    display: grid;
    grid-template-columns: 110px 1fr;
    gap: 8px;
    align-items: center;
    margin: 8px 0;
    font-size: 13px;
  }
  .form-row label,
  .form-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
  }
  .form-row input,
  .form-row select {
    padding: 6px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    font-size: 13px;
    transition: border-color 0.2s ease;
  }
  .form-row input:focus,
  .form-row select:focus {
    border-color: var(--accent-color);
    outline: none;
  }
  .form-row input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .static-value {
    padding: 6px 10px;
    font-size: 13px;
    color: var(--text-muted);
    min-height: 33px;
    display: flex;
    align-items: center;
  }
  .calc-grid {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 2px 10px;
    font-size: 12px;
    padding: 8px 10px;
    background: var(--hover-color);
    border-radius: 6px;
    border: 1px solid var(--border-color);
  }
  .calc-label {
    color: var(--text-muted);
    font-weight: 500;
    white-space: nowrap;
  }
  .calc-value {
    color: var(--text-color);
    text-align: right;
  }
  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 1rem;
    padding-top: 12px;
    border-top: 1px solid var(--border-color);
  }
  .actions button {
    padding: 8px 18px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }
  .actions button:hover:not(:disabled) {
    background: var(--hover-color);
  }
  .actions button:last-child {
    background: var(--accent-color);
    border: 1px solid var(--accent-color);
    color: white;
  }
  .actions button:last-child:hover {
    background: var(--accent-color-hover);
  }
  .actions-spacer {
    flex: 1;
  }
  .actions .delete-btn {
    background: transparent;
    border: 1px solid var(--error-color, #ef4444);
    color: var(--error-color, #ef4444);
  }
  .actions .delete-btn:hover {
    background: rgba(239, 68, 68, 0.1);
  }
  .suggestions {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
    background: var(--hover-color);
    border-radius: 6px;
    padding: 6px 8px;
  }
  .suggest-btn {
    padding: 4px 10px;
    border: 1px solid var(--accent-color);
    border-radius: 4px;
    background: transparent;
    color: var(--accent-color);
    font-size: 12px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s ease;
  }
  .suggest-btn:hover {
    background: rgba(59, 130, 246, 0.15);
  }
  .suggest-btn.undercut,
  .suggest-btn.outbid {
    border-color: var(--warning-color, #f59e0b);
    color: var(--warning-color, #f59e0b);
  }
  .suggest-btn.undercut:hover,
  .suggest-btn.outbid:hover {
    background: rgba(245, 158, 11, 0.15);
  }
  .suggest-btn.daily {
    border-color: var(--text-muted);
    color: var(--text-muted);
  }
  .suggest-btn.daily:hover {
    background: var(--hover-color);
    color: var(--text-color);
  }
  .suggest-hint {
    font-size: 12px;
    color: var(--text-muted);
  }
  .partial-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
  }
  .partial-label input[type="checkbox"] {
    margin: 0;
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
    top: 0;
    left: calc(100% + 8px);
    min-width: 220px;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 10px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
    z-index: 5;
  }
  .skill-popover .row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 6px 0;
    font-size: 13px;
  }
  .skill-popover .cbx {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  /* Option classes as fallback; some browsers ignore them in <option> */
  .opt-disabled { opacity: 0.6; }
  .opt-locked { color: var(--error-color, #ff6b6b); }
  .opt-unlocked { color: var(--success-color, #34c759); }

  /* Tab bar */
  .tab-bar {
    display: flex;
    gap: 0;
    margin-bottom: 1rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
  }
  .tab {
    flex: 1;
    padding: 6px 12px;
    background: var(--bg-color);
    border: none;
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }
  .tab:not(:last-child) {
    border-right: 1px solid var(--border-color);
  }
  .tab.active {
    background: var(--accent-color);
    color: white;
  }
  .tab:hover:not(.active) {
    background: var(--hover-color);
  }
  .inv-warning-banner {
    background: var(--warning-bg);
    color: var(--warning-color);
    padding: 6px 10px;
    border-radius: 4px;
    border: 1px solid var(--warning-color);
    font-size: 12px;
    margin-bottom: 8px;
  }
  .inventory-warning {
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 12px;
    color: var(--warning-color, #f59e0b);
    background: rgba(245, 158, 11, 0.1);
    border: 1px solid var(--warning-color, #f59e0b);
  }
  .order-count-indicator {
    text-align: center;
    font-size: 12px;
    color: var(--text-muted);
    padding: 4px 0;
  }
  .next-btn {
    background: transparent;
    border: 1px solid var(--accent-color);
    color: var(--accent-color);
    padding: 8px 18px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s ease;
  }
  .next-btn:hover {
    background: var(--accent-color);
    color: white;
  }
</style>

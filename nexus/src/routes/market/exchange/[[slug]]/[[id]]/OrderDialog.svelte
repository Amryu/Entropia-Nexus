<script lang="ts">
  // @ts-nocheck
  import { isBlueprint, isItemTierable, isItemStackable, isLimited, itemHasCondition, isPercentMarkup, isPet, getMaxTT, formatPedRaw, PET_DEFAULT_MAX_TT, itemTypeBadge } from "../../orderUtils";
  import { getPercentUndercutAmount, getAbsoluteUndercutAmount, DEFAULT_PARTIAL_RATIO } from '../../exchangeConstants.js';
  import { PLATE_SET_SIZE } from '$lib/common/itemTypes.js';
  import { env } from '$env/dynamic/public';
  import TurnstileWidget from '$lib/components/TurnstileWidget.svelte';
  import { addToast } from '$lib/stores/toasts.js';

  let turnstileToken = $state(null);
  let resetTurnstile = $state(false);

  

  // Dialog-local calculations
  let unitPrice = $state(0);
  let totalPrice = $state(0);
  let muLabel = '';
  let ttValueDisplay = '';
  let singlePieceMaxTT = null; // Original single-piece MaxTT for set toggle reference
  // Price suggestions
  let suggestions = $state(null); // { bestBuy, bestSell }
  let suggestionsLoading = false;
  let dailyAverage = $state(null);

  // Partial trade state
  let allowPartial = $state(true);

  

  

  

  // Track orders created in this multi-order session
  let sessionOrderCount = $state(0);

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
        order.Metadata.Pet = order.Metadata.Pet || { Level: 0 };
      }
      // Store single-piece MaxTT; for set orders the stored MaxTT is single-piece
      singlePieceMaxTT = order.Item?.MaxTT != null ? Number(order.Item.MaxTT) : null;
      // If editing an existing set order, inflate MaxTT to set value
      if (order.Metadata?.is_set && order.Item?.Type === 'ArmorPlating' && singlePieceMaxTT != null) {
        order.Item.MaxTT = singlePieceMaxTT * PLATE_SET_SIZE;
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

      // Store single-piece MaxTT
      singlePieceMaxTT = order.Item?.MaxTT != null ? Number(order.Item.MaxTT) : null;

      // Derive item-type-aware defaults from the nested Item
      const itemType = order.Item?.Type;
      const itemRef = { Type: itemType, Properties: { Type: itemType }, Name: order.Item?.Name, st: order.Item?.st ?? null };
      if (order.Markup == null || order.Markup === 0) {
        order.Markup = isPercentMarkup(itemRef) ? 100 : 0;
      }
      if (isItemTierable(itemRef)) {
        if (order.Metadata.Tier == null) order.Metadata.Tier = 0;
        if (order.Metadata.TierIncreaseRate == null) order.Metadata.TierIncreaseRate = 1;
      }
      if (isBlueprint(itemRef) && !isLimited(itemRef)) {
        if (order.Metadata.QualityRating == null) order.Metadata.QualityRating = type === 'buy' ? '0' : 1;
      }
      if (itemType === 'Pet') {
        order.Metadata.Pet = order.Metadata.Pet || { Level: 0 };
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
          st: item?.st ?? null,
        },
        Planet: 'Calypso',
        Quantity: 1,
        CurrentTT: null,
        Markup: isPercentMarkup(item) ? 100 : 0,
        MinQuantity: null,
        Metadata: {}
      };
      // Store single-piece MaxTT
      singlePieceMaxTT = order.Item.MaxTT;

      // Set defaults for condition/tier/blueprint
      if (isItemTierable(item)) {
        order.Metadata.Tier = 0;
        order.Metadata.TierIncreaseRate = 1;
      }
      if (isBlueprint(item) && !isLimited(item)) {
        order.Metadata.QualityRating = type === 'buy' ? '0' : 1;
      }
      if (item?.Properties?.Type === 'Pet' || item?.Type === 'Pet' || item?.t === 'Pet') {
        order.Metadata.Pet = { Level: 0 };
      }

      if (itemHasCondition(item) && !isBlueprint(item) && order.Item.MaxTT != null) {
        order.CurrentTT = order.Item.MaxTT;
      }
      allowPartial = true;
      order.MinQuantity = Math.max(1, Math.floor((order.Quantity || 1) * DEFAULT_PARTIAL_RATIO));
    }

    // Set gender based on item gender classification
    if (showGenderSelect) {
      if (!order.Metadata) order.Metadata = {};
      if (genderFixed) {
        order.Metadata.Gender = itemGender;
      } else if (mode !== 'edit' && !order.Metadata.Gender) {
        // Default to 'Male' for 'Both' items when creating
        order.Metadata.Gender = 'Male';
      }
    } else if (order.Metadata?.Gender) {
      // Strip gender for non-gendered or neutral items
      delete order.Metadata.Gender;
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

  // Handle toggling the "Full set" checkbox for ArmorPlating
  function handleSetToggle() {
    if (!order || singlePieceMaxTT == null) { recalcPrices(); return; }

    if (order.Metadata.is_set) {
      // Toggling ON → multiply MaxTT by PLATE_SET_SIZE
      const oldMaxTT = order.Item.MaxTT;
      order.Item.MaxTT = singlePieceMaxTT * PLATE_SET_SIZE;
      // Adjust CurrentTT if still at the single-piece default
      if (order.CurrentTT != null && order.CurrentTT === oldMaxTT) {
        order.CurrentTT = order.Item.MaxTT;
      }
    } else {
      // Toggling OFF → revert to single piece
      const oldMaxTT = order.Item.MaxTT;
      order.Item.MaxTT = singlePieceMaxTT;
      // Adjust CurrentTT if still at the set default
      if (order.CurrentTT != null && order.CurrentTT === oldMaxTT) {
        order.CurrentTT = order.Item.MaxTT;
      }
      // Clamp CurrentTT to new (lower) MaxTT
      if (order.CurrentTT != null && order.CurrentTT > order.Item.MaxTT) {
        order.CurrentTT = order.Item.MaxTT;
      }
    }
    recalcPrices();
  }

  // Recalculate dialog-local price fields
  function recalcPrices() {
    if (!order) return;
    const item = order.Item;
    const isBp = isBlueprint(item) && !isLimited(item); // (L) BPs are stackable, use percent markup
    const isTier = isItemTierable(item);
    const hasCond = itemHasCondition(item);
    const isPctMu = isPercentMarkup(item);
    const maxTT = Number(item?.MaxTT) || 0;
    // Non-stackable items are always qty 1 (single instance per order)
    const stackable = isItemStackable(item);
    const qty = stackable ? Math.max(0, Number(order.Quantity) || 0) : 1;
    if (!stackable && order.Quantity !== 1) {
      order.Quantity = 1;
    }
    let mu = Number(order.Markup) || 0;
    let value = Number(order.CurrentTT) || 0;
    let qr = Number(order.Metadata?.QualityRating) || 0;
    const isBuyOrder = order.Type === 'Buy';
    // Unit price — preserve precision for small values
    if (isBp) {
      unitPrice = isBuyOrder ? mu : qr / 100 + mu;
    } else if (isPctMu) {
      unitPrice = maxTT * (mu / 100);
    } else if (hasCond) {
      unitPrice = value + mu;
    } else {
      unitPrice = maxTT + mu;
    }
    totalPrice = qty * unitPrice;
    muLabel = isPctMu ? `${Math.max(0, mu).toFixed(2)}% of Max TT` : `+${formatPedRaw(mu)} PED`;
    ttValueDisplay = isPctMu
      ? `Max TT: ${maxTT || 'N/A'}`
      : isBp
        ? (isBuyOrder ? `QR range filter` : `QR ${qr.toFixed(2)} (=${formatPedRaw(qr / 100)} PED)`)
        : hasCond
          ? `Current TT: ${formatPedRaw(value)} PED`
          : `Max TT: ${maxTT || 'N/A'}`;
  }


  // QR range options for buy orders (matching the exchange filter pattern)
  const qrRangeOptions = [
    ...Array.from({ length: 10 }, (_, i) => ({
      label: `${i * 10 + 1}-${i * 10 + 9}`,
      value: `${i * 10}`
    })),
    { label: "100", value: "100" }
  ];



  
  interface Props {
    show?: boolean;
    mode?: string; // 'create' | 'edit'
    order?: any;
    itemGender?: string|undefined;
    existingOrderCount?: number;
    maxOrdersPerItem?: number;
    isNonFungible?: boolean;
    planets?: any;
    submitting?: boolean;
    onclose?: () => void;
    onsubmit?: (data: any) => void;
    onnext?: (data: any) => void;
    ondelete?: (data: any) => void;
  }

  let {
    show = false,
    mode = $bindable('create'),
    order = $bindable(null),
    itemGender = undefined,
    existingOrderCount = 0,
    maxOrdersPerItem = 5,
    isNonFungible = false,
    planets = [
    'Calypso', 'Arkadia', 'Cyrene', 'Rocktropia', 'Next Island', 'Monria', 'Toulan', 'Howling Mine (Space)'
  ],
    submitting = false,
    onclose,
    onsubmit,
    onnext,
    ondelete,
  }: Props = $props();

  function close() {
    sessionOrderCount = 0;
    onclose?.();
  }
  function submit() {
    if (submitting) return;
    if (env.PUBLIC_TURNSTILE_SITE_KEY && !turnstileToken) {
      addToast('Please complete the captcha verification', { type: 'warning' });
      return;
    }
    onsubmit?.({ order, turnstileToken });
    sessionOrderCount = 0;
    resetTurnstile = true;
  }
  function submitAndNext() {
    if (submitting) return;
    if (env.PUBLIC_TURNSTILE_SITE_KEY && !turnstileToken) {
      addToast('Please complete the captcha verification', { type: 'warning' });
      return;
    }
    onnext?.({ order, turnstileToken });
    sessionOrderCount++;
    resetTurnstile = true;
  }
  let isGenderedItem = $derived(itemGender !== undefined);
  let showGenderSelect = $derived(isGenderedItem && itemGender !== 'Neutral' && itemGender !== null);
  let genderFixed = $derived(itemGender === 'Male' || itemGender === 'Female');
  // Watch for changes to recalc
  $effect(() => {
    if (order) recalcPrices();
  });
  // When pet level changes, refresh disabled/color state (options re-compute from order state)
  // Derived flags for template: show Quantity only for fungible items (no instance metadata)
  let showQuantity = $derived(order ? isItemStackable(order.Item) : false);
  let isArmorPlating = $derived(order?.Item?.Type === 'ArmorPlating');
  // Inventory-sourced warnings
  let inventoryWarning = $derived(order?._inventoryWarning || null);
  let inventoryQty = $derived(order?._inventoryQty ?? null);
  let totalOrdersIfSubmitted = $derived(existingOrderCount + sessionOrderCount + 1);
  let canCreateMore = $derived(isNonFungible && totalOrdersIfSubmitted < maxOrdersPerItem && mode === 'create');
  let orderLimitReached = $derived(totalOrdersIfSubmitted >= maxOrdersPerItem);
  // For inventory sell: warn if total sell orders exceed inventory qty
  let totalSellQty = $derived((() => {
    if (inventoryQty == null || order?.Type !== 'Sell') return null;
    return (existingOrderCount + sessionOrderCount + 1);
  })());
  let qtyExceedsInventory = $derived(inventoryQty != null && totalSellQty != null && totalSellQty > inventoryQty);
</script>

{#if show}
  <div
    class="modal-overlay"
    role="button"
    tabindex="0"
    onclick={(e) => {
      if (e.target.classList.contains('modal-overlay')) close();
    }}
    onkeydown={(e) => {
      if (e.key === 'Escape' || e.key === 'Enter') close();
    }}
  >
    <div class="modal">
      <h3 style="margin-top:0;">
        {mode === 'create' ? 'Create' : 'Edit'} {order.Type} Order
      </h3>
      <div class="form-row">
        <div class="form-label">Item</div>
        <div>{order.Item?.Name}{@html itemTypeBadge(order.Item?.Type)}</div>
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
      {#if showGenderSelect}
        <div class="form-row">
          <label for="genderSelect">Gender</label>
          <select
            id="genderSelect"
            bind:value={order.Metadata.Gender}
            class="filter-select select-center"
            disabled={genderFixed}
            onchange={recalcPrices}
          >
            <option value="Male">Male</option>
            <option value="Female">Female</option>
          </select>
        </div>
      {/if}
  {#if showQuantity}
        <div class="form-row">
          <label for="qtyInput">Quantity</label>
          <input
            id="qtyInput"
            type="number"
            min="1"
            bind:value={order.Quantity}
            oninput={() => {
              recalcPrices();
              if (allowPartial && order.MinQuantity > order.Quantity) {
                order.MinQuantity = order.Quantity;
              }
            }}
          />
        </div>
        <div class="form-row">
          <label class="partial-label">
            <input type="checkbox" bind:checked={allowPartial} onchange={() => {
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
            min="0"
            bind:value={order.Metadata.Pet.Level}
            oninput={recalcPrices}
            onblur={() => { order.Metadata.Pet.Level = Math.max(0, Math.round(Number(order.Metadata.Pet.Level) || 0)); recalcPrices(); }}
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
            oninput={recalcPrices}
            onblur={() => { order.Metadata.Tier = Math.max(0, Math.min(10, Math.round(Number(order.Metadata.Tier) || 0))); recalcPrices(); }}
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
            oninput={recalcPrices}
            onblur={() => { const maxTir = isLimited(order.Item) ? 4000 : 200; order.Metadata.TierIncreaseRate = Math.max(0, Math.min(maxTir, Math.round(Number(order.Metadata.TierIncreaseRate) || 0))); recalcPrices(); }}
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
                oninput={recalcPrices}
                onblur={() => { order.Metadata.QualityRating = Math.max(1, Math.min(100, Math.round(Number(order.Metadata.QualityRating) || 1))); recalcPrices(); }}
              />
            {:else}
              <select
                id="bpCond"
                class="filter-select select-center"
                bind:value={order.Metadata.QualityRating}
                onchange={recalcPrices}
              >
                {#each qrRangeOptions as opt}
                  <option value={opt.value}>{opt.label}</option>
                {/each}
              </select>
            {/if}
          </div>
        {:else}
          <div class="form-row max-tt-row">
            <span class="form-label">{isPet(order.Item) ? 'Nutrio Cap.' : 'Max TT'}</span>
            <div class="static-value">
              {order.Item.MaxTT != null ? `${formatPedRaw(Number(order.Item.MaxTT))} PED` : 'N/A'}
              {#if isPet(order.Item) && Number(order.Item.MaxTT) === PET_DEFAULT_MAX_TT}
                <span class="fallback-hint">(fallback)</span>
              {/if}
            </div>
            {#if isArmorPlating}
              <label class="set-label">
                <input type="checkbox" bind:checked={order.Metadata.is_set} onchange={handleSetToggle} />
                Full set ({PLATE_SET_SIZE})
              </label>
            {/if}
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
              oninput={recalcPrices}
              onblur={() => { const max = order.Item.MaxTT ?? Infinity; order.CurrentTT = Math.max(0, Math.min(max, Math.round((Number(order.CurrentTT) || 0) * 100) / 100)); recalcPrices(); }}
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
            step="0.01"
            bind:value={order.Markup}
            oninput={recalcPrices}
            onblur={() => { order.Markup = Math.max(100, Math.round((Number(order.Markup) || 100) * 100) / 100); recalcPrices(); }}
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
            oninput={recalcPrices}
            onblur={() => { order.Markup = Math.max(0, Math.round((Number(order.Markup) || 0) * 100) / 100); recalcPrices(); }}
          />
        </div>
      {/if}
      {#if suggestions || dailyAverage != null}
        <div class="form-row">
          <div class="form-label">Suggestions</div>
          <div class="suggestions">
            {#if order.Type === 'Sell'}
              {#if suggestions?.bestSell != null}
                <button class="suggest-btn" onclick={() => applySuggestion(suggestions.bestSell)} title="Match the lowest sell order">
                  Match Best ({isPercentMarkup(order.Item) ? suggestions.bestSell.toFixed(2) : formatPedRaw(suggestions.bestSell)})
                </button>
                <button class="suggest-btn undercut" onclick={() => applySuggestion(computeUndercutValue(suggestions.bestSell, 'Sell'))} title="Undercut the lowest sell by ~2%">
                  Undercut
                </button>
              {:else if suggestions}
                <span class="suggest-hint">No sell orders yet</span>
              {/if}
            {:else}
              {#if suggestions?.bestBuy != null}
                <button class="suggest-btn" onclick={() => applySuggestion(suggestions.bestBuy)} title="Match the highest buy order">
                  Match Best ({isPercentMarkup(order.Item) ? suggestions.bestBuy.toFixed(2) : formatPedRaw(suggestions.bestBuy)})
                </button>
                <button class="suggest-btn outbid" onclick={() => applySuggestion(computeUndercutValue(suggestions.bestBuy, 'Buy'))} title="Outbid the highest buy by ~2%">
                  Outbid
                </button>
              {:else if suggestions}
                <span class="suggest-hint">No buy orders yet</span>
              {/if}
            {/if}
            {#if dailyAverage != null}
              <button class="suggest-btn daily" onclick={() => applySuggestion(dailyAverage)} title="Use the daily average markup">
                Daily Avg ({isPercentMarkup(order.Item) ? dailyAverage.toFixed(2) : formatPedRaw(dailyAverage)})
              </button>
            {/if}
          </div>
        </div>
      {/if}
      <div class="calc-grid">
        <span class="calc-label">{showQuantity ? 'Unit' : 'Price'}</span>
        <span class="calc-value">
          {#if isBlueprint(order.Item) && !isLimited(order.Item)}
            {#if order.Type === 'Buy'}
              MU = {formatPedRaw(unitPrice)} PED
            {:else}
              {formatPedRaw(Number(order.Metadata?.QualityRating) / 100)} + {formatPedRaw(Number(order.Markup) || 0)} = {formatPedRaw(unitPrice)} PED
            {/if}
          {:else if isPercentMarkup(order.Item)}
            {formatPedRaw(Number(order.Item.MaxTT) || 0)} &times; {(Number(order.Markup) || 0).toFixed(2)}% = {formatPedRaw(unitPrice)} PED
          {:else if itemHasCondition(order.Item)}
            {formatPedRaw(Number(order.CurrentTT) || 0)} + {formatPedRaw(Number(order.Markup) || 0)} = {formatPedRaw(unitPrice)} PED
          {:else}
            {formatPedRaw(Number(order.Item.MaxTT) || 0)} + {formatPedRaw(Number(order.Markup) || 0)} = {formatPedRaw(unitPrice)} PED
          {/if}
        </span>
        {#if showQuantity}
          <span class="calc-label">Total</span>
          <span class="calc-value">
            {Number(order.Quantity) || 0} &times; {formatPedRaw(unitPrice)} = {formatPedRaw(totalPrice)} PED
          </span>
        {/if}
      </div>
      {#if qtyExceedsInventory}
        <div class="inventory-warning">You are creating more sell orders than you have in your inventory ({inventoryQty}).</div>
      {/if}
      {#if isNonFungible && mode === 'create' && (existingOrderCount + sessionOrderCount > 0)}
        <div class="order-count-indicator">Order {existingOrderCount + sessionOrderCount + 1} of {maxOrdersPerItem}</div>
      {/if}
      {#if env.PUBLIC_TURNSTILE_SITE_KEY}
        <TurnstileWidget
          siteKey={env.PUBLIC_TURNSTILE_SITE_KEY}
          bind:token={turnstileToken}
          bind:reset={resetTurnstile}
        />
      {/if}
      <div class="actions">
        {#if mode === 'edit'}
          <button class="delete-btn" onclick={() => { if (env.PUBLIC_TURNSTILE_SITE_KEY && !turnstileToken) { addToast('Please complete the captcha verification', { type: 'warning' }); return; } ondelete?.({ order, turnstileToken }); resetTurnstile = true; }} title="Delete this order">Delete</button>
        {/if}
        <span class="actions-spacer"></span>
        <button onclick={close} disabled={submitting}>{sessionOrderCount > 0 ? 'Done' : 'Cancel'}</button>
        {#if canCreateMore && !orderLimitReached}
          <button class="next-btn" onclick={submitAndNext} disabled={submitting} title="Create this order and set up the next one">{submitting ? 'Saving...' : 'Next'}</button>
        {/if}
        <button onclick={submit} disabled={orderLimitReached || submitting} title={mode === 'edit' ? 'Save changes' : 'Submit order'}>{submitting ? 'Saving...' : (mode === 'edit' ? 'Save' : 'Submit')}</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1000;
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
    grid-template-columns: 120px 1fr;
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
    width: 100%;
    box-sizing: border-box;
    padding: 6px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    font-size: 13px;
    transition: border-color 0.2s ease;
  }
  .form-row input[type="checkbox"] {
    width: auto;
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
    gap: 6px;
  }
  .fallback-hint {
    font-size: 11px;
    opacity: 0.7;
    font-style: italic;
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
  .max-tt-row {
    grid-template-columns: 120px 1fr auto;
  }
  .set-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    cursor: pointer;
    white-space: nowrap;
  }
  .set-label input[type="checkbox"] {
    margin: 0;
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
  :global(.turnstile-container) {
    margin-top: 1rem;
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

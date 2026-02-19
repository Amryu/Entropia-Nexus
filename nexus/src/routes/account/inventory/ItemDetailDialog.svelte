<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { apiCall, getTypeLink } from '$lib/util.js';
  import {
    formatPedRaw, formatMarkupValue, itemTypeBadge
  } from '../../market/exchange/orderUtils';

  export let show = false;
  export let item = null;   // enriched inventory item
  export let allItems = [];  // flat slim items

  const dispatch = createEventDispatcher();

  let wikiData = null;
  let loading = false;

  const wikiCache = new Map();

  $: if (show && item) loadWikiData(item.item_id);

  async function loadWikiData(itemId) {
    if (!itemId || itemId <= 0) { wikiData = null; return; }
    if (wikiCache.has(itemId)) { wikiData = wikiCache.get(itemId); return; }

    loading = true;
    try {
      const data = await apiCall(window.fetch, `/items/${itemId}`);
      wikiData = data;
      if (data) wikiCache.set(itemId, data);
    } catch {
      wikiData = null;
    } finally {
      loading = false;
    }
  }

  $: type = item?._type || wikiData?.Properties?.Type || wikiData?.Type || null;
  $: imageUrl = item?._type && item?.item_id > 0
    ? `/api/img/${item._type.toLowerCase()}/${item.item_id}?size=128`
    : null;
  $: wikiLink = wikiData ? getTypeLink(wikiData.Name || item?.item_name, type) : null;
  $: stats = wikiData ? getStatsForType(wikiData, type) : [];

  function getStatsForType(data, itemType) {
    const s = [];
    const p = data.Properties || {};
    const eco = p.Economy || {};

    // Common: MaxTT
    if (eco.MaxTT != null) s.push({ label: 'Max TT', value: `${eco.MaxTT} PED` });

    switch (itemType) {
      case 'Weapon': {
        if (p.Class) s.push({ label: 'Class', value: p.Class });
        if (p.Type) s.push({ label: 'Type', value: p.Type });
        // Total damage
        const dmg = p.Damage || {};
        const totalDmg = Object.values(dmg).reduce((a, v) => a + (v || 0), 0);
        if (totalDmg > 0) s.push({ label: 'Damage', value: totalDmg.toFixed(1) });
        if (p.UsesPerMinute) {
          s.push({ label: 'Attacks/min', value: p.UsesPerMinute });
          if (totalDmg > 0) s.push({ label: 'DPS', value: ((totalDmg * p.UsesPerMinute) / 60).toFixed(2) });
        }
        if (p.Range) s.push({ label: 'Range', value: `${p.Range} m` });
        if (eco.Decay != null) s.push({ label: 'Decay', value: `${eco.Decay} PED` });
        if (eco.AmmoBurn != null) s.push({ label: 'Ammo/shot', value: eco.AmmoBurn });
        if (eco.Efficiency != null) s.push({ label: 'Economy', value: `${eco.Efficiency}%` });
        if (data.Ammo?.Name) s.push({ label: 'Ammo', value: data.Ammo.Name });
        break;
      }
      case 'Armor':
      case 'ArmorSet': {
        const def = p.Defense || {};
        const totalDef = Object.values(def).reduce((a, v) => a + (v || 0), 0);
        if (totalDef > 0) s.push({ label: 'Total Def', value: totalDef.toFixed(1) });
        if (eco.Durability != null) s.push({ label: 'Durability', value: eco.Durability });
        // Top defense types
        const defEntries = Object.entries(def).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
        for (const [k, v] of defEntries.slice(0, 3)) {
          s.push({ label: k, value: v.toFixed(1) });
        }
        break;
      }
      case 'Pet': {
        if (p.Rarity) s.push({ label: 'Rarity', value: p.Rarity });
        if (p.TamingLevel != null) s.push({ label: 'Taming Lvl', value: p.TamingLevel });
        if (p.TrainingDifficulty) s.push({ label: 'Training', value: p.TrainingDifficulty });
        if (p.NutrioCapacity != null) s.push({ label: 'Nutrio Cap', value: p.NutrioCapacity });
        if (data.Effects?.length) s.push({ label: 'Effects', value: `${data.Effects.length} skills` });
        break;
      }
      case 'Blueprint': {
        if (p.Type) s.push({ label: 'BP Type', value: p.Type });
        if (p.Level != null) s.push({ label: 'Level', value: p.Level });
        if (data.Product?.Name) s.push({ label: 'Product', value: data.Product.Name });
        if (data.Materials?.length) s.push({ label: 'Materials', value: `${data.Materials.length} types` });
        if (data.Book?.Name) s.push({ label: 'Book', value: data.Book.Name });
        break;
      }
      case 'Vehicle': {
        if (p.Type) s.push({ label: 'Type', value: p.Type });
        if (p.MaxSpeed != null) s.push({ label: 'Speed', value: `${p.MaxSpeed} km/h` });
        if (p.PassengerCount != null) s.push({ label: 'Passengers', value: p.PassengerCount });
        if (p.ItemCapacity != null) s.push({ label: 'Item Cap', value: p.ItemCapacity });
        if (eco.Durability != null) s.push({ label: 'Durability', value: eco.Durability });
        break;
      }
      case 'Material': {
        if (p.Type) s.push({ label: 'Type', value: p.Type });
        if (p.Weight != null) s.push({ label: 'Weight', value: `${p.Weight} kg` });
        break;
      }
      default: {
        // Generic stats for tools, etc.
        if (p.Type) s.push({ label: 'Type', value: p.Type });
        if (p.UsesPerMinute) s.push({ label: 'Uses/min', value: p.UsesPerMinute });
        if (p.Range) s.push({ label: 'Range', value: `${p.Range} m` });
        if (eco.Decay != null) s.push({ label: 'Decay', value: `${eco.Decay} PED` });
        if (p.Weight != null) s.push({ label: 'Weight', value: `${p.Weight} kg` });
        break;
      }
    }
    return s;
  }

  function handleClose() {
    dispatch('close');
  }

  function handleEdit() {
    dispatch('edit');
  }

  function openWiki() {
    if (wikiLink) window.open(wikiLink, '_blank');
  }

  function openOrders() {
    if (item?.item_id) window.open(`/market/exchange/listings/${item.item_id}`, '_blank');
  }
</script>

{#if show && item}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-overlay" on:click|self={handleClose}>
    <div class="modal">
      <!-- Item identity header -->
      <div class="item-identity">
        {#if imageUrl}
          <img
            src={imageUrl}
            width="64" height="64"
            alt=""
            class="item-thumb"
            on:error={(e) => {
              const placeholder = document.createElement('span');
              placeholder.className = 'item-thumb item-thumb-placeholder';
              e.target.replaceWith(placeholder);
            }}
          />
        {:else}
          <span class="item-thumb item-thumb-placeholder"></span>
        {/if}
        <div class="item-info">
          <h3 class="item-name">{item.item_name || 'Unknown Item'}</h3>
          <div class="item-meta">
            {#if type}
              <span class="badge badge-subtle badge-info">{@html itemTypeBadge(type) || type}</span>
            {/if}
            {#if item.container}
              <span class="text-muted">{item.container}</span>
            {/if}
          </div>
        </div>
        <button class="close-btn" on:click={handleClose}>&times;</button>
      </div>

      <!-- Wiki stats -->
      {#if loading}
        <p class="loading-msg">Loading item data...</p>
      {:else if stats.length > 0}
        <div class="stats-grid">
          {#each stats as stat}
            <div class="stat-item">
              <span class="stat-label">{stat.label}</span>
              <span class="stat-value">{stat.value}</span>
            </div>
          {/each}
        </div>
      {/if}

      <!-- Inventory info -->
      <div class="inv-info">
        <div class="form-row">
          <span class="form-label">Quantity</span>
          <span>{item.quantity?.toLocaleString() ?? '-'}</span>
        </div>
        {#if item._ttValue != null}
          <div class="form-row">
            <span class="form-label">TT Value</span>
            <span>{formatPedRaw(item._ttValue)} PED</span>
          </div>
        {/if}
        {#if item._markup != null}
          <div class="form-row">
            <span class="form-label">Markup</span>
            <span>{item._isAbsolute ? formatMarkupValue(item._markup, true) : formatMarkupValue(item._markup, false)}</span>
          </div>
        {/if}
        {#if item._totalValue != null && item._totalValue !== item._ttValue}
          <div class="form-row">
            <span class="form-label">Est. Total</span>
            <span class="accent-value">{formatPedRaw(item._totalValue)} PED</span>
          </div>
        {/if}
        {#if item.details}
          {@const det = typeof item.details === 'string' ? JSON.parse(item.details) : item.details}
          {#if det.Tier != null}
            <div class="form-row">
              <span class="form-label">Tier</span>
              <span>{det.Tier}</span>
            </div>
          {/if}
          {#if det.TierIncreaseRate != null}
            <div class="form-row">
              <span class="form-label">TiR</span>
              <span>{det.TierIncreaseRate}</span>
            </div>
          {/if}
          {#if det.QualityRating != null}
            <div class="form-row">
              <span class="form-label">QR</span>
              <span>{det.QualityRating}</span>
            </div>
          {/if}
          {#if det.Level != null}
            <div class="form-row">
              <span class="form-label">Level</span>
              <span>{det.Level}</span>
            </div>
          {/if}
        {/if}
      </div>

      <!-- Action buttons -->
      <div class="actions">
        {#if wikiLink}
          <button on:click={openWiki}>Wiki Page</button>
        {/if}
        {#if item._sellOrders?.length}
          <button on:click={openOrders}>View Orders</button>
        {/if}
        <span class="actions-spacer"></span>
        <button on:click={handleClose}>Close</button>
        <button on:click={handleEdit}>Edit</button>
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

  /* Header: image + name + close */
  .item-identity {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 12px;
  }

  .item-thumb {
    border-radius: 6px;
    object-fit: cover;
    flex-shrink: 0;
    width: 64px;
    height: 64px;
    background: var(--bg-color);
  }

  .item-thumb-placeholder {
    display: block;
    border: 1px solid var(--border-color);
  }

  .item-info {
    min-width: 0;
    flex: 1;
  }

  .item-name {
    margin: 0 0 4px;
    font-size: 16px;
    font-weight: 600;
    line-height: 1.2;
    word-wrap: break-word;
  }

  .item-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    font-size: 12px;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 22px;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
    flex-shrink: 0;
  }

  .close-btn:hover {
    color: var(--text-color);
  }

  /* Wiki stats */
  .loading-msg {
    color: var(--text-muted);
    font-size: 13px;
    text-align: center;
    padding: 0.75rem 0;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2px 10px;
    padding: 8px 10px;
    background: var(--hover-color);
    border-radius: 6px;
    border: 1px solid var(--border-color);
    margin-bottom: 10px;
    font-size: 12px;
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }

  .stat-label {
    color: var(--text-muted);
    font-weight: 500;
  }

  .stat-value {
    font-weight: 500;
    text-align: right;
  }

  /* Inventory info using form-row grid */
  .inv-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 4px;
  }

  .form-row {
    display: grid;
    grid-template-columns: 90px 1fr;
    gap: 8px;
    align-items: center;
    font-size: 13px;
    margin: 2px 0;
  }

  .form-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
  }

  .accent-value {
    color: var(--accent-color);
    font-weight: 600;
  }

  .text-muted {
    color: var(--text-muted);
  }

  /* Actions: matches OrderDialog pattern */
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

  .actions button:hover {
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

  @media (max-width: 480px) {
    .modal {
      width: 100%;
      border-radius: 8px 8px 0 0;
      max-height: 85vh;
    }

    .stats-grid {
      grid-template-columns: 1fr;
    }
  }
</style>

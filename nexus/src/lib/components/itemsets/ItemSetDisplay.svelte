<!--
  @component ItemSetDisplay
  Read-only viewer for an item set.
  Shows items with metadata badges in a compact format.
-->
<script>
  // @ts-nocheck
  import { TIERABLE_TYPES, CONDITION_TYPES, isLimitedByName } from '$lib/common/itemTypes.js';
  import { getTypeLink } from '$lib/util.js';

  /** @type {object} Full item set object with data */
  export let itemSet;

  /** @type {boolean} Whether to show the set name as a header */
  export let showHeader = true;

  /** @type {boolean} Whether to render item names as links */
  export let linkItems = false;

  function getItemHref(name, type) {
    if (!linkItems) return null;
    return getTypeLink(name, type) || null;
  }

  $: items = itemSet?.data?.items || [];

  function formatTT(value) {
    if (value == null) return null;
    return Number(value).toFixed(2);
  }

  function formatQR(value) {
    if (value == null) return null;
    return (value * 100).toFixed(2);
  }

  function getMetaBadges(item) {
    if (item.setType) return [];
    const badges = [];
    const meta = item.meta || {};
    const type = item.type || '';
    const name = item.name || '';
    const isLimited = isLimitedByName(name);

    if (TIERABLE_TYPES.has(type) && !isLimited) {
      if (meta.tier != null) badges.push({ label: `T${meta.tier}`, type: 'tier' });
      if (meta.tiR != null) badges.push({ label: `TiR ${meta.tiR}`, type: 'tier' });
    }
    if (CONDITION_TYPES.has(type) && meta.currentTT != null) {
      badges.push({ label: `TT ${formatTT(meta.currentTT)}`, type: 'tt' });
    }
    if (type === 'Blueprint' && !isLimited && meta.qr != null) {
      badges.push({ label: `QR ${formatQR(meta.qr)}`, type: 'qr' });
    }
    if (meta.gender) {
      badges.push({ label: meta.gender === 'Male' ? '(M)' : '(F)', type: 'gender' });
    }
    if (type === 'Pet' && meta.pet) {
      if (meta.pet.level != null) badges.push({ label: `Lv.${meta.pet.level}`, type: 'pet' });
      if (meta.pet.currentTT != null) badges.push({ label: `Fed ${formatTT(meta.pet.currentTT)}`, type: 'pet' });
    }
    return badges;
  }
</script>

<div class="item-set-display">
  {#if showHeader && itemSet?.name}
    <div class="set-header">
      <span class="set-name">{itemSet.name}</span>
      <span class="set-count">{items.length} item{items.length !== 1 ? 's' : ''}</span>
    </div>
  {/if}

  {#if items.length === 0}
    <div class="empty">No items in this set.</div>
  {:else}
    <div class="item-list">
      {#each items as item}
        {#if item.setType}
          <!-- Set entry -->
          <div class="display-set-entry">
            <div class="display-set-header">
              <span class="set-type-badge">{item.setType === 'ArmorSet' ? 'Armor' : 'Clothing'}</span>
              {@const setHref = getItemHref(item.setName, item.setType)}
              {#if setHref}
                <a href={setHref} class="display-set-name item-link">{item.setName}</a>
              {:else}
                <span class="display-set-name">{item.setName}</span>
              {/if}
              {#if item.gender}
                <span class="badge badge-gender">{item.gender === 'Male' ? '(M)' : '(F)'}</span>
              {/if}
              <span class="display-piece-count">{item.pieces?.length || 0}pc</span>
            </div>
            {#if item.pieces?.length > 0}
              <div class="display-pieces">
                {#each item.pieces as piece}
                  <div class="display-piece">
                    <span class="piece-connector"></span>
                    <span class="piece-name">{piece.name}</span>
                    {#if piece.meta?.currentTT != null}
                      <span class="badge badge-tt">TT {formatTT(piece.meta.currentTT)}</span>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {:else}
          <!-- Regular item -->
          <div class="display-item">
            {@const itemHref = getItemHref(item.name, item.type)}
            {#if itemHref}
              <a href={itemHref} class="display-item-name item-link">{item.name}</a>
            {:else}
              <span class="display-item-name">{item.name}</span>
            {/if}
            {#if item.quantity > 1}
              <span class="display-quantity">x{item.quantity}</span>
            {/if}
            {#each getMetaBadges(item) as badge}
              <span class="badge badge-{badge.type}">{badge.label}</span>
            {/each}
          </div>
        {/if}
      {/each}
    </div>
  {/if}
</div>

<style>
  .item-set-display {
    width: 100%;
  }

  .set-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .set-name {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-color);
  }

  .set-count {
    font-size: 12px;
    color: var(--text-muted);
  }

  .empty {
    padding: 16px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }

  .item-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  /* Regular item */
  .display-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background-color: var(--primary-color);
    border-radius: 4px;
    font-size: 13px;
  }

  .display-item-name {
    color: var(--text-color);
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-link {
    color: var(--accent-color);
    text-decoration: none;
  }

  .item-link:hover {
    text-decoration: underline;
  }

  .display-quantity {
    font-size: 12px;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  /* Badges */
  .badge {
    font-size: 10px;
    font-weight: 600;
    padding: 1px 5px;
    border-radius: 3px;
    flex-shrink: 0;
    white-space: nowrap;
  }

  .badge-tier {
    background-color: var(--accent-color);
    color: white;
  }

  .badge-tt {
    background-color: var(--success-bg);
    color: var(--success-color);
  }

  .badge-qr {
    background-color: var(--warning-bg);
    color: var(--warning-color);
  }

  .badge-gender {
    background-color: var(--hover-color);
    color: var(--text-muted);
  }

  .badge-pet {
    background-color: #2d1f4e;
    color: #c084fc;
  }

  /* Set entry */
  .display-set-entry {
    background-color: var(--primary-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .display-set-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    font-size: 13px;
  }

  .set-type-badge {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 1px 5px;
    border-radius: 3px;
    background-color: var(--accent-color);
    color: white;
    flex-shrink: 0;
  }

  .display-set-name {
    color: var(--text-color);
    font-weight: 500;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .display-piece-count {
    font-size: 11px;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .display-pieces {
    padding: 2px 10px 6px 24px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .display-piece {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
  }

  .piece-connector {
    width: 8px;
    height: 1px;
    background-color: var(--border-color);
    flex-shrink: 0;
  }

  .piece-name {
    color: var(--text-muted);
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  @media (max-width: 899px) {
    .display-item,
    .display-set-header {
      padding: 5px 8px;
    }

    .display-pieces {
      padding-left: 16px;
    }
  }
</style>

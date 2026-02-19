<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { inventory } from '../../exchangeStore.js';
  import { isBlueprint, isItemTierable, isLimited, itemHasCondition } from '../../orderUtils';
  import { apiCall } from '$lib/util.js';

  export let show = false;
  export let item = null;
  export let allItems = [];

  const dispatch = createEventDispatcher();

  let itemDetails = null;
  let loadingDetails = false;
  let saving = false;
  let saved = false;
  let saveTimeout = null;
  let error = null;

  // Editable fields — bound to inputs
  let editQuantity = 0;
  let editValue = '';
  let editTier = '';
  let editTiR = '';
  let editQR = '';
  let editLevel = '';
  let editUnlockedSkills = [];

  // Cache fetched item details by item_id
  const detailsCache = new Map();

  $: if (show && item) openItem(item);

  async function openItem(inv) {
    error = null;
    saved = false;

    // Populate edit fields from current item
    editQuantity = inv.quantity ?? 0;
    editValue = inv.value != null ? String(inv.value) : '';
    const details = typeof inv.details === 'string' ? JSON.parse(inv.details) : (inv.details || {});
    editTier = details.Tier != null ? String(details.Tier) : '';
    editTiR = details.TierIncreaseRate != null ? String(details.TierIncreaseRate) : '';
    editQR = details.QualityRating != null ? String(details.QualityRating) : '';
    editLevel = details.Level != null ? String(details.Level) : '';
    editUnlockedSkills = details.UnlockedSkills || [];

    // Resolve item type
    await loadItemDetails(inv.item_id);
  }

  async function loadItemDetails(itemId) {
    if (detailsCache.has(itemId)) {
      itemDetails = detailsCache.get(itemId);
      return;
    }

    // Try allItems first for basic type info
    const slim = allItems.find(it => it.i === itemId);

    loadingDetails = true;
    try {
      const full = await apiCall(window.fetch, `/items/${itemId}`);
      if (full) {
        itemDetails = full;
        detailsCache.set(itemId, full);
      } else if (slim) {
        // Fallback to slim item
        itemDetails = { Type: slim.t, Name: slim.n, i: slim.i };
        detailsCache.set(itemId, itemDetails);
      } else {
        itemDetails = null;
      }
    } catch {
      // Fallback to slim
      if (slim) {
        itemDetails = { Type: slim.t, Name: slim.n, i: slim.i };
        detailsCache.set(itemId, itemDetails);
      } else {
        itemDetails = null;
      }
    } finally {
      loadingDetails = false;
    }
  }

  $: isFungible = item && !item.instance_key;
  $: tierable = itemDetails && isItemTierable(itemDetails);
  $: blueprint = itemDetails && isBlueprint(itemDetails);
  $: limited = itemDetails && isLimited(itemDetails);
  $: hasCondition = itemDetails && itemHasCondition(itemDetails);
  $: showValue = !isFungible && hasCondition;
  $: showTier = tierable;
  $: showTiR = tierable;
  $: showQR = blueprint && !limited;
  $: tirMax = limited ? 4000 : 200;
  $: isPetItem = itemDetails?.Properties?.Type === 'Pet' || itemDetails?.Type === 'Pet';
  $: petEffects = isPetItem && itemDetails?.Effects ? itemDetails.Effects : [];

  function scheduleSave() {
    saved = false;
    error = null;
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => doSave(), 400);
  }

  async function doSave() {
    if (!item) return;
    saving = true;
    error = null;

    const body = {};

    // Quantity (fungible only)
    if (isFungible) {
      const qty = parseInt(editQuantity, 10);
      if (Number.isFinite(qty) && qty >= 0) body.quantity = qty;
    }

    // Value (only for non-fungible condition items)
    if (showValue) {
      if (editValue === '' || editValue === null) {
        body.value = null;
      } else {
        const val = parseFloat(editValue);
        if (Number.isFinite(val) && val >= 0) body.value = val;
      }
    }

    // Details
    const details = {};
    if (showTier && editTier !== '') {
      const t = parseFloat(editTier);
      if (Number.isFinite(t) && t >= 0 && t <= 10) details.Tier = t;
    }
    if (showTiR && editTiR !== '') {
      const t = parseInt(editTiR, 10);
      if (Number.isFinite(t) && t >= 1 && t <= tirMax) details.TierIncreaseRate = t;
    }
    if (showQR && editQR !== '') {
      const q = parseFloat(editQR);
      if (Number.isFinite(q) && q >= 0 && q <= 100) details.QualityRating = q;
    }
    if (isPetItem) {
      if (editLevel !== '') {
        const lvl = parseInt(editLevel, 10);
        if (Number.isFinite(lvl) && lvl >= 0 && lvl <= 200) details.Level = lvl;
      }
      if (editUnlockedSkills.length > 0) {
        details.UnlockedSkills = editUnlockedSkills;
      }
    }

    body.details = Object.keys(details).length > 0 ? details : null;

    try {
      const res = await fetch(`/api/users/inventory/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json();
        error = data.error || 'Save failed';
        saving = false;
        return;
      }
      const updated = await res.json();

      // Update inventory store
      inventory.update(inv =>
        inv.map(i => i.id === updated.id ? updated : i)
      );
      // Update local item reference
      item = updated;

      saved = true;
      setTimeout(() => { saved = false; }, 1500);
    } catch (e) {
      error = e.message || 'Save failed';
    } finally {
      saving = false;
    }
  }

  function handleClose() {
    if (saveTimeout) clearTimeout(saveTimeout);
    dispatch('close');
  }
</script>

{#if show && item}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-overlay" on:click|self={handleClose}>
    <div class="modal">
      <div class="modal-header">
        <h3 class="modal-title">{item.item_name || 'Item'}</h3>
        <div class="save-indicator">
          {#if saving}<span class="indicator saving">Saving...</span>{/if}
          {#if saved}<span class="indicator saved">Saved</span>{/if}
        </div>
        <button class="close-btn" on:click={handleClose}>&times;</button>
      </div>

      {#if error}
        <div class="error-banner">{error}</div>
      {/if}

      {#if loadingDetails}
        <p class="loading-msg">Loading item details...</p>
      {:else}
        <div class="fields">
          {#if isFungible}
            <div class="form-row">
              <label for="inv-qty">Quantity</label>
              <input
                id="inv-qty"
                type="number"
                min="0"
                step="1"
                bind:value={editQuantity}
                on:input={scheduleSave}
              />
            </div>
          {/if}

          {#if showValue}
            <div class="form-row">
              <label for="inv-value">Value (PED)</label>
              <input
                id="inv-value"
                type="number"
                min="0"
                step="0.01"
                placeholder="—"
                bind:value={editValue}
                on:input={scheduleSave}
              />
            </div>
          {/if}

          {#if showTier}
            <div class="form-row">
              <label for="inv-tier">Tier</label>
              <input
                id="inv-tier"
                type="number"
                min="0"
                max="10"
                step="0.01"
                placeholder="0.00"
                bind:value={editTier}
                on:input={scheduleSave}
              />
            </div>
          {/if}

          {#if showTiR}
            <div class="form-row">
              <label for="inv-tir">TiR</label>
              <input
                id="inv-tir"
                type="number"
                min="1"
                max={tirMax}
                step="1"
                placeholder="1"
                bind:value={editTiR}
                on:input={scheduleSave}
              />
              <span class="field-hint">max {tirMax}</span>
            </div>
          {/if}

          {#if showQR}
            <div class="form-row">
              <label for="inv-qr">QR</label>
              <input
                id="inv-qr"
                type="number"
                min="0"
                max="100"
                step="0.1"
                placeholder="0"
                bind:value={editQR}
                on:input={scheduleSave}
              />
            </div>
          {/if}

          {#if isPetItem}
            <div class="form-row">
              <label for="inv-level">Level</label>
              <input
                id="inv-level"
                type="number"
                min="0"
                max="200"
                step="1"
                placeholder="0"
                bind:value={editLevel}
                on:input={scheduleSave}
              />
            </div>

            {#if petEffects.length > 0}
              <div class="skill-section">
                <label class="skill-label">Unlocked Skills</label>
                <div class="skill-list">
                  {#each petEffects as effect}
                    {@const effectName = effect.Name || effect._newEffect?.CanonicalName || 'Unknown'}
                    {@const strength = effect.Properties?.Strength}
                    {@const unit = effect._newEffect?.Unit || ''}
                    <label class="skill-checkbox">
                      <input
                        type="checkbox"
                        checked={editUnlockedSkills.includes(effectName)}
                        on:change={(e) => {
                          if (e.target.checked) {
                            editUnlockedSkills = [...editUnlockedSkills, effectName];
                          } else {
                            editUnlockedSkills = editUnlockedSkills.filter(s => s !== effectName);
                          }
                          scheduleSave();
                        }}
                      />
                      <span>{effectName}{strength != null ? ` (${strength}${unit})` : ''}</span>
                    </label>
                  {/each}
                </div>
              </div>
            {/if}
          {/if}

          {#if !isFungible && !showValue && !showTier && !showQR && !isPetItem}
            <p class="no-extra-fields">No additional metadata for this item type.</p>
          {/if}
        </div>
      {/if}

      <div class="modal-actions">
        <button class="btn-primary" on:click={handleClose}>Done</button>
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
    width: 380px;
    max-width: calc(100% - 32px);
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }
  .modal-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
  }
  .modal-title {
    margin: 0;
    font-size: 16px;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
  .close-btn:hover { color: var(--text-color); }

  .save-indicator {
    flex-shrink: 0;
  }
  .indicator {
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 3px;
  }
  .indicator.saving {
    color: var(--text-muted);
  }
  .indicator.saved {
    color: var(--success-color);
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 6px 10px;
    border-radius: 4px;
    border: 1px solid var(--error-color);
    font-size: 13px;
    margin-bottom: 8px;
  }

  .loading-msg {
    color: var(--text-muted);
    font-size: 13px;
    text-align: center;
    padding: 1rem 0;
  }

  .fields {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .form-row {
    display: grid;
    grid-template-columns: 90px 1fr auto;
    gap: 8px;
    align-items: center;
  }
  .form-row label {
    font-size: 13px;
    color: var(--text-muted);
    font-weight: 500;
  }
  .form-row input {
    width: 100%;
    padding: 6px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    font-size: 13px;
    box-sizing: border-box;
  }
  .form-row input:focus {
    border-color: var(--accent-color);
    outline: none;
  }
  .field-hint {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .skill-section {
    margin-top: 4px;
  }
  .skill-label {
    font-size: 13px;
    color: var(--text-muted);
    font-weight: 500;
    display: block;
    margin-bottom: 4px;
  }
  .skill-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 180px;
    overflow-y: auto;
  }
  .skill-checkbox {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    cursor: pointer;
  }
  .skill-checkbox input {
    margin: 0;
    cursor: pointer;
  }
  .skill-checkbox span {
    line-height: 1.3;
  }

  .no-extra-fields {
    font-size: 13px;
    color: var(--text-muted);
    text-align: center;
    padding: 0.5rem 0;
    margin: 0;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 12px;
  }
  .btn-primary {
    padding: 6px 16px;
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
    border: 1px solid var(--accent-color);
    background: var(--accent-color);
    color: white;
  }
  .btn-primary:hover { opacity: 0.9; }
</style>

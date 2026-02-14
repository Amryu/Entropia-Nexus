<!--
  @component Rental Create Page
  Form to create a new rental offer. Creates as draft, redirects to edit page.
  Item sets are created inline (1:1 with rental) — no dropdown selection.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto } from '$app/navigation';
  import { apiPost, apiCall, apiDelete } from '$lib/util';
  import { RENTAL_ALLOWED_ITEM_TYPES } from '$lib/common/itemTypes.js';
  import RentalPricingEditor from '$lib/components/rental/RentalPricingEditor.svelte';
  import ItemSetDialog from '$lib/components/itemsets/ItemSetDialog.svelte';
  import { addToast } from '$lib/stores/toasts';

  export let data;

  $: planets = data.planets || [];
  $: loadouts = data.loadouts || [];
  $: availableLoadouts = loadouts.filter(l => !l.linked_item_set);

  let saving = false;
  let error = '';
  let showItemSetDialog = false;
  let showLoadoutPicker = false;
  let creatingFromLoadout = null;
  let removingItemSet = false;

  // The created item set for this rental (1:1 relationship)
  let itemSet = null;       // { id, items, loadoutId? }

  function handleItemSetCreated(e) {
    const result = e.detail;
    itemSet = {
      id: result.id,
      items: result.data?.items || []
    };
    addToast('Item set created.', { type: 'success' });
  }

  async function removeItemSet() {
    if (!itemSet || removingItemSet) return;
    removingItemSet = true;

    try {
      const result = await apiDelete(fetch, `/api/itemsets/${itemSet.id}`);
      if (result?.error) {
        addToast(result.error);
        return;
      }
      itemSet = null;
    } catch (err) {
      addToast('Failed to remove item set.');
    } finally {
      removingItemSet = false;
    }
  }

  function handleKeydown(e) {
    if (showLoadoutPicker && !creatingFromLoadout && e.key === 'Escape') showLoadoutPicker = false;
  }

  function handleLoadoutPickerBackdrop(e) {
    if (!creatingFromLoadout && e.target === e.currentTarget) showLoadoutPicker = false;
  }

  // === Loadout → Item Set conversion ===
  const ARMOR_SLOTS = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];

  function extractItemsFromLoadout(gear) {
    if (!gear) return [];
    const items = [];

    // Weapon + attachments
    if (gear.Weapon?.Name) {
      items.push({ type: 'Weapon', name: gear.Weapon.Name, quantity: 1, meta: {} });
    }
    if (gear.Weapon?.Amplifier?.Name) {
      items.push({ type: 'WeaponAmplifier', name: gear.Weapon.Amplifier.Name, quantity: 1, meta: {} });
    }
    if (gear.Weapon?.Scope?.Name) {
      items.push({ type: 'WeaponVisionAttachment', name: gear.Weapon.Scope.Name, quantity: 1, meta: {} });
    }
    if (gear.Weapon?.Sight?.Name) {
      items.push({ type: 'WeaponVisionAttachment', name: gear.Weapon.Sight.Name, quantity: 1, meta: {} });
    }
    if (gear.Weapon?.Absorber?.Name) {
      items.push({ type: 'Absorber', name: gear.Weapon.Absorber.Name, quantity: 1, meta: {} });
    }
    if (gear.Weapon?.Implant?.Name) {
      items.push({ type: 'MindforceImplant', name: gear.Weapon.Implant.Name, quantity: 1, meta: {} });
    }

    // Armor pieces + plates
    for (const slot of ARMOR_SLOTS) {
      const piece = gear.Armor?.[slot];
      if (piece?.Name) {
        items.push({ type: 'Armor', name: piece.Name, quantity: 1, meta: {} });
      }
      if (piece?.Plate?.Name) {
        items.push({ type: 'ArmorPlating', name: piece.Plate.Name, quantity: 1, meta: {} });
      }
    }

    // Clothing
    if (Array.isArray(gear.Clothing)) {
      for (const c of gear.Clothing) {
        if (c?.Name) {
          items.push({ type: 'Clothing', name: c.Name, quantity: 1, meta: {} });
        }
      }
    }

    // Pet
    if (gear.Pet?.Name) {
      items.push({ type: 'Pet', name: gear.Pet.Name, quantity: 1, meta: {} });
    }

    return items;
  }

  async function createItemSetFromLoadout(loadout) {
    creatingFromLoadout = loadout.id;

    try {
      const loadoutData = await apiCall(fetch, `/api/tools/loadout/${loadout.id}`);
      if (!loadoutData?.data?.Gear) {
        addToast('Failed to load loadout data.');
        return;
      }

      const items = extractItemsFromLoadout(loadoutData.data.Gear);
      if (items.length === 0) {
        addToast('No rental-compatible items found in this loadout.', { type: 'info' });
        return;
      }

      const result = await apiPost(fetch, '/api/itemsets', {
        name: '',
        data: { items },
        loadout_id: loadout.id
      });

      if (result?.error) {
        addToast(result.error);
        return;
      }

      itemSet = {
        id: result.id,
        items: result.data?.items || items,
        loadoutName: loadout.name
      };
      showLoadoutPicker = false;
      addToast('Item set created from loadout.', { type: 'success' });
    } catch (err) {
      addToast('Failed to create item set from loadout.');
    } finally {
      creatingFromLoadout = null;
    }
  }

  // Form data
  let title = '';
  let description = '';
  let planetId = '';
  let location = '';
  let pricePerDay = 0;
  let discounts = [];
  let deposit = 0;

  function handlePricingChange(e) {
    pricePerDay = e.detail.pricePerDay;
    discounts = e.detail.discounts;
    deposit = e.detail.deposit;
  }

  async function handleSubmit() {
    if (!title.trim()) {
      error = 'Title is required.';
      return;
    }
    if (!itemSet) {
      error = 'Please create an item set.';
      return;
    }
    if (pricePerDay <= 0) {
      error = 'Price per day must be greater than 0.';
      return;
    }

    error = '';
    saving = true;

    try {
      const result = await apiPost(fetch, '/api/rental', {
        title: title.trim(),
        description: description || null,
        item_set_id: itemSet.id,
        planet_id: planetId ? parseInt(planetId) : null,
        location: location.trim() || null,
        price_per_day: pricePerDay,
        discounts,
        deposit
      });

      if (result?.error) {
        error = result.error;
        return;
      }

      addToast('Rental offer created as draft.', { type: 'success' });
      goto(`/market/rental/${result.id}/edit?new=1`);
    } catch (err) {
      error = 'Failed to create rental offer.';
    } finally {
      saving = false;
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<svelte:head>
  <title>Create Rental Offer - Market - Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <a href="/market/rental">Item Rentals</a>
      <span>/</span>
      <span>Create Offer</span>
    </div>

    <button class="back-btn" on:click={() => goto('/market/rental')}>
      &larr; Back to Listings
    </button>

    <h1>Create Rental Offer</h1>

    <form on:submit|preventDefault={handleSubmit} class="create-form">
      {#if error}
        <div class="error-banner">{error}</div>
      {/if}

      <!-- Title & Description -->
      <div class="form-section">
        <h2>Basic Info</h2>

        <div class="form-group">
          <label for="title">Title *</label>
          <input
            type="text"
            id="title"
            bind:value={title}
            placeholder="e.g. Adjusted Abrer for Rent"
            maxlength="120"
          />
        </div>

        <div class="form-group">
          <label>Description</label>
          {#await import('$lib/components/wiki/RichTextEditor.svelte') then { default: RichTextEditor }}
            <RichTextEditor
              content={description}
              placeholder="Describe the rental terms, conditions, etc."
              showHeadings={false}
              showCodeBlock={false}
              showVideo={false}
              showImages={false}
              on:change={(e) => description = e.detail}
            />
          {/await}
        </div>
      </div>

      <!-- Item Set -->
      <div class="form-section">
        <h2>Items *</h2>

        {#if !itemSet}
          <p class="section-hint">Create the set of items included in this rental. The item set cannot be changed after the offer is created.</p>
          <div class="item-set-actions">
            <button type="button" class="btn-create-set" on:click={() => showItemSetDialog = true}>
              Create Item Set
            </button>
            {#if availableLoadouts.length > 0}
              <button type="button" class="btn-from-loadout" on:click={() => showLoadoutPicker = true}>
                From Loadout
              </button>
            {/if}
          </div>
        {:else}
          <div class="item-set-preview">
            <div class="preview-header">
              <span class="preview-count">{itemSet.items.length} item{itemSet.items.length !== 1 ? 's' : ''}</span>
              {#if itemSet.loadoutName}
                <span class="preview-source">from {itemSet.loadoutName}</span>
              {/if}
              <button
                type="button"
                class="btn-remove-set"
                disabled={removingItemSet}
                on:click={removeItemSet}
              >
                {removingItemSet ? 'Removing...' : 'Remove'}
              </button>
            </div>
            <ul class="preview-items">
              {#each itemSet.items as item}
                <li>
                  <span class="item-type">{item.type}</span>
                  <span class="item-name">{item.name}</span>
                  {#if item.quantity > 1}
                    <span class="item-qty">x{item.quantity}</span>
                  {/if}
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>

      <!-- Location -->
      <div class="form-section">
        <h2>Location</h2>

        <div class="form-group">
          <label for="planet">Planet</label>
          <select id="planet" bind:value={planetId}>
            <option value="">— Any Planet —</option>
            {#each planets as planet}
              <option value={planet.Id}>{planet.Name}</option>
            {/each}
          </select>
        </div>

        <div class="form-group">
          <label for="location">Pickup/Return Location</label>
          <input
            type="text"
            id="location"
            bind:value={location}
            placeholder="e.g. Twin Peaks Teleporter"
            maxlength="200"
          />
        </div>
      </div>

      <!-- Pricing -->
      <div class="form-section">
        <h2>Pricing</h2>
        <RentalPricingEditor
          {pricePerDay}
          {discounts}
          {deposit}
          on:change={handlePricingChange}
        />
      </div>

      <!-- Submit -->
      <div class="form-actions">
        <button type="button" class="cancel-btn" on:click={() => goto('/market/rental')}>
          Cancel
        </button>
        <button type="submit" class="save-btn" disabled={saving}>
          {saving ? 'Creating...' : 'Create as Draft'}
        </button>
      </div>
    </form>
  </div>
</div>

{#if showLoadoutPicker}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="picker-backdrop" on:click={handleLoadoutPickerBackdrop}>
    <div class="picker-dialog" role="dialog" aria-modal="true" aria-label="Select Loadout">
      <div class="picker-header">
        <h3>Select Loadout</h3>
        <button class="picker-close" disabled={creatingFromLoadout != null} on:click={() => showLoadoutPicker = false}>&times;</button>
      </div>
      <div class="picker-body">
        <p class="picker-hint">Create a new item set from one of your loadouts.</p>
        {#each availableLoadouts as loadout}
          <button
            class="picker-item"
            disabled={creatingFromLoadout != null}
            on:click={() => createItemSetFromLoadout(loadout)}
          >
            {#if creatingFromLoadout === loadout.id}
              Creating...
            {:else}
              {loadout.name}
            {/if}
          </button>
        {/each}
      </div>
    </div>
  </div>
{/if}

<ItemSetDialog
  bind:show={showItemSetDialog}
  hideName={true}
  allowedItemTypes={RENTAL_ALLOWED_ITEM_TYPES}
  on:save={handleItemSetCreated}
/>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 1rem;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .back-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    cursor: pointer;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .back-btn:hover {
    background: var(--hover-color);
    border-color: var(--border-hover);
  }

  h1 {
    margin: 0 0 1.5rem;
    font-size: 1.75rem;
  }

  .create-form {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .form-section {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.25rem;
  }

  .form-section h2 {
    margin: 0 0 1rem;
    font-size: 1.1rem;
    font-weight: 600;
  }

  .section-hint {
    margin: 0 0 0.75rem;
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group:last-child {
    margin-bottom: 0;
  }

  .form-group label {
    display: block;
    font-weight: 500;
    font-size: 0.9rem;
    color: var(--text-color);
    margin-bottom: 0.25rem;
  }

  .form-group input,
  .form-group select,
  .form-group textarea {
    width: 100%;
    padding: 0.5rem;
    background: var(--primary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.9rem;
    box-sizing: border-box;
    font-family: inherit;
  }

  .form-group textarea {
    resize: vertical;
  }

  .form-group input:focus,
  .form-group select:focus,
  .form-group textarea:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .form-group small {
    display: block;
    margin-top: 0.25rem;
    color: var(--text-muted);
    font-size: 0.8rem;
  }

  /* Item Set Actions (no set yet) */
  .item-set-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .btn-create-set {
    padding: 0.5rem 1rem;
    background: transparent;
    border: 1px solid var(--accent-color);
    color: var(--accent-color);
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .btn-create-set:hover {
    background: var(--accent-color);
    color: white;
  }

  .btn-from-loadout {
    padding: 0.5rem 1rem;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .btn-from-loadout:hover {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }

  /* Item Set Preview (set created) */
  .item-set-preview {
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
  }

  .preview-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 0.75rem;
    border-bottom: 1px solid var(--border-color);
  }

  .preview-count {
    font-weight: 600;
    font-size: 0.9rem;
  }

  .preview-source {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .btn-remove-set {
    margin-left: auto;
    padding: 0.25rem 0.6rem;
    background: transparent;
    border: 1px solid var(--error-color);
    color: var(--error-color);
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 500;
  }

  .btn-remove-set:hover:not(:disabled) {
    background: var(--error-color);
    color: white;
  }

  .btn-remove-set:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .preview-items {
    list-style: none;
    margin: 0;
    padding: 0.5rem 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    max-height: 240px;
    overflow-y: auto;
  }

  .preview-items li {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    padding: 0.2rem 0;
  }

  .item-type {
    font-size: 0.75rem;
    color: var(--text-muted);
    background: var(--hover-color);
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    white-space: nowrap;
  }

  .item-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-qty {
    font-size: 0.8rem;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  /* Loadout Picker Dialog */
  .picker-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 1rem;
  }

  .picker-dialog {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 100%;
    max-width: 400px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }

  .picker-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--border-color);
  }

  .picker-header h3 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
  }

  .picker-close {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }

  .picker-close:hover {
    color: var(--text-color);
  }

  .picker-body {
    padding: 1rem 1.25rem;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .picker-hint {
    margin: 0 0 0.25rem;
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .picker-item {
    display: block;
    width: 100%;
    padding: 0.65rem 0.75rem;
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    font-size: 0.9rem;
    cursor: pointer;
    text-align: left;
  }

  .picker-item:hover:not(:disabled) {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }

  .picker-item:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    border: 1px solid var(--error-color);
  }

  .form-actions {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
    padding-top: 0.5rem;
  }

  .cancel-btn, .save-btn {
    padding: 0.5rem 1.25rem;
    border-radius: 4px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
  }

  .cancel-btn {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .cancel-btn:hover {
    background: var(--hover-color);
  }

  .save-btn {
    background: var(--accent-color);
    color: white;
    border: none;
  }

  .save-btn:hover:not(:disabled) {
    background: var(--accent-color-hover);
  }

  .save-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 768px) {
    .form-actions {
      flex-direction: column-reverse;
    }

    .cancel-btn, .save-btn {
      width: 100%;
      text-align: center;
    }

    .item-set-actions {
      flex-direction: column;
    }

    .btn-create-set, .btn-from-loadout {
      width: 100%;
      text-align: center;
    }
  }
</style>

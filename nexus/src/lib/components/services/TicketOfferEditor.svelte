<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';

  export let offer = null; // null for create, object for edit
  export let saving = false;
  export let serviceMode = 'on_demand'; // 'on_demand', 'scheduled', or 'both'

  const dispatch = createEventDispatcher();

  // Form state
  let offerType = offer?.uses_count ? 'uses' : (offer?.validity_days ? 'duration' : 'uses');
  let usesCount = offer?.uses_count || 1;
  let validityDays = offer?.validity_days || 30;
  let price = offer?.price ? parseFloat(offer.price).toFixed(2) : '';
  let waivesPickupFee = offer?.waives_pickup_fee || false;
  let description = offer?.description || '';

  // Auto-generate name based on type and amount
  $: name = offerType === 'uses'
    ? `${usesCount}-Trip Pass`
    : `${validityDays}-Day Pass`;

  function handleSubmit() {

    if (!price || isNaN(parseFloat(price)) || parseFloat(price) < 0) {
      alert('Please enter a valid price.');
      return;
    }

    const offerData = {
      name: name.trim(),
      uses_count: offerType === 'uses' ? parseInt(usesCount) : null,
      validity_days: offerType === 'duration' ? parseInt(validityDays) : null,
      price: parseFloat(price),
      waives_pickup_fee: waivesPickupFee,
      description: description.trim() || null
    };

    if (offer) {
      offerData.id = offer.id;
    }

    dispatch('save', offerData);
  }

  function handleCancel() {
    dispatch('cancel');
  }

  function handleDelete() {
    if (confirm('Are you sure you want to delete this ticket offer? Existing tickets will still be valid.')) {
      dispatch('delete', { id: offer.id });
    }
  }
</script>

<div class="ticket-offer-editor">
  <h3>{offer ? 'Edit Ticket Offer' : 'Create Ticket Offer'}</h3>

  <form on:submit|preventDefault={handleSubmit}>
    <div class="form-group">
      <label>Ticket Name</label>
      <div class="auto-name">{name}</div>
      <small>Auto-generated based on type and amount</small>
    </div>

    <div class="form-group">
      <label>Ticket Type *</label>
      <div class="radio-group">
        <label class="radio-label">
          <input type="radio" bind:group={offerType} value="uses" />
          Uses-based (fixed number of trips)
        </label>
        <label class="radio-label">
          <input type="radio" bind:group={offerType} value="duration" />
          Duration-based (unlimited trips for a period)
        </label>
      </div>
    </div>

    {#if offerType === 'uses'}
      <div class="form-group">
        <label for="usesCount">Number of Uses *</label>
        <input type="number" id="usesCount" bind:value={usesCount} min="1" max="100" />
        <small>How many trips this ticket provides</small>
      </div>
    {:else}
      <div class="form-group">
        <label for="validityDays">Validity Period (Days) *</label>
        <input type="number" id="validityDays" bind:value={validityDays} min="1" max="365" />
        <small>Ticket expires this many days after first use</small>
      </div>
    {/if}

    <div class="form-group">
      <label for="price">Price (PED) *</label>
      <input type="number" id="price" bind:value={price} step="0.01" min="0" placeholder="0.00" />
    </div>

    {#if serviceMode === 'on_demand' || serviceMode === 'both'}
      <div class="form-group checkbox-group">
        <label>
          <input type="checkbox" bind:checked={waivesPickupFee} />
          Waives pickup fee for on-demand requests
        </label>
        <small>When checked, customers with this ticket won't pay the pickup fee</small>
      </div>
    {/if}

    <div class="form-group">
      <label for="description">Description</label>
      <textarea id="description" bind:value={description} rows="2" placeholder="Optional details about this ticket offer..."></textarea>
    </div>

    <div class="form-actions">
      {#if offer}
        <button type="button" class="delete-btn" on:click={handleDelete} disabled={saving}>
          Delete
        </button>
      {/if}
      <div class="right-actions">
        <button type="button" class="cancel-btn" on:click={handleCancel} disabled={saving}>
          Cancel
        </button>
        <button type="submit" class="save-btn" disabled={saving}>
          {saving ? 'Saving...' : (offer ? 'Update Offer' : 'Create Offer')}
        </button>
      </div>
    </div>
  </form>
</div>

<style>
  .ticket-offer-editor {
    background: var(--secondary-color);
    border: 1px solid #666;
    border-radius: 8px;
    padding: 1.5rem;
  }

  h3 {
    margin: 0 0 1rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #666;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.25rem;
    font-weight: 500;
  }

  .form-group input[type="text"],
  .form-group input[type="number"],
  .form-group textarea {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    font-size: 1rem;
    box-sizing: border-box;
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
  }

  .form-group textarea {
    resize: none;
  }

  .form-group small {
    display: block;
    margin-top: 0.25rem;
    color: var(--text-muted, #888);
    font-size: 0.85rem;
  }

  .auto-name {
    padding: 0.5rem;
    background: var(--bg-color, #1a1a1a);
    border: 1px solid #555;
    border-radius: 4px;
    font-weight: 500;
    color: var(--text-color);
  }

  .radio-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .radio-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: normal;
    cursor: pointer;
  }

  .radio-label input[type="radio"] {
    width: auto;
    margin: 0;
  }

  .checkbox-group label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: normal;
    cursor: pointer;
  }

  .checkbox-group input[type="checkbox"] {
    width: auto;
  }

  .form-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 1.5rem;
    padding-top: 1rem;
    border-top: 1px solid #555;
  }

  .right-actions {
    display: flex;
    gap: 0.75rem;
  }

  .cancel-btn, .save-btn, .delete-btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    font-size: 0.95rem;
    cursor: pointer;
  }

  .cancel-btn {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid #666;
  }

  .cancel-btn:hover:not(:disabled) {
    background: var(--hover-color);
  }

  .save-btn {
    background: #4a9eff;
    color: white;
  }

  .save-btn:hover:not(:disabled) {
    background: #3a8eef;
  }

  .delete-btn {
    background: #e74c3c;
    color: white;
  }

  .delete-btn:hover:not(:disabled) {
    background: #c0392b;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>

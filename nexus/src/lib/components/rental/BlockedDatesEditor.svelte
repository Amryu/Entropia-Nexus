<!--
  @component BlockedDatesEditor
  Manage blocked date ranges for a rental offer.
  Owner can add and remove date ranges when the item is unavailable.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { formatDateDisplay } from '$lib/utils/rentalPricing.js';

  const dispatch = createEventDispatcher();

  /** @type {number} Rental offer ID */
  export let offerId;

  /** @type {Array<{id: number, start_date: string, end_date: string, reason: string|null}>} */
  export let blockedDates = [];

  /** @type {boolean} */
  export let loading = false;

  let newStart = '';
  let newEnd = '';
  let newReason = '';
  let adding = false;
  let error = '';

  function toDateStr(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  $: minDate = toDateStr(new Date());

  async function handleAdd() {
    if (!newStart || !newEnd) {
      error = 'Please select both start and end dates.';
      return;
    }
    if (newEnd < newStart) {
      error = 'End date must be on or after start date.';
      return;
    }

    error = '';
    adding = true;

    try {
      const res = await fetch(`/api/rental/${offerId}/blocked-dates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_date: newStart,
          end_date: newEnd,
          reason: newReason.trim() || null
        })
      });

      if (!res.ok) {
        const data = await res.json();
        error = data.error || 'Failed to add blocked dates.';
        return;
      }

      const created = await res.json();
      blockedDates = [...blockedDates, created];
      newStart = '';
      newEnd = '';
      newReason = '';
      dispatch('change', { blockedDates });
    } catch (err) {
      error = 'Failed to add blocked dates.';
    } finally {
      adding = false;
    }
  }

  async function handleRemove(id) {
    try {
      const res = await fetch(`/api/rental/${offerId}/blocked-dates`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
      });

      if (!res.ok) {
        const data = await res.json();
        error = data.error || 'Failed to remove blocked dates.';
        return;
      }

      blockedDates = blockedDates.filter(d => d.id !== id);
      dispatch('change', { blockedDates });
    } catch (err) {
      error = 'Failed to remove blocked dates.';
    }
  }

</script>

<div class="blocked-dates-editor">
  <div class="add-form">
    <div class="date-inputs">
      <div class="date-field">
        <label for="block-start">From</label>
        <input type="date" id="block-start" bind:value={newStart} min={minDate} />
      </div>
      <div class="date-field">
        <label for="block-end">To</label>
        <input type="date" id="block-end" bind:value={newEnd} min={newStart || minDate} />
      </div>
    </div>
    <div class="reason-field">
      <label for="block-reason">Reason (optional)</label>
      <input
        type="text"
        id="block-reason"
        bind:value={newReason}
        placeholder="e.g. Personal use, maintenance"
        maxlength="200"
      />
    </div>
    <button type="button" class="add-btn" on:click={handleAdd} disabled={adding || !newStart || !newEnd}>
      {adding ? 'Adding...' : 'Block Dates'}
    </button>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if loading}
    <p class="loading-text">Loading blocked dates...</p>
  {:else if blockedDates.length === 0}
    <p class="empty-text">No blocked dates. Items are available on all non-booked days.</p>
  {:else}
    <div class="dates-list">
      {#each blockedDates as range}
        <div class="date-range">
          <div class="range-info">
            <span class="range-dates">
              {formatDateDisplay(range.start_date)} &ndash; {formatDateDisplay(range.end_date)}
            </span>
            {#if range.reason}
              <span class="range-reason">{range.reason}</span>
            {/if}
          </div>
          <button type="button" class="remove-btn" on:click={() => handleRemove(range.id)} title="Remove blocked dates">
            &times;
          </button>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .blocked-dates-editor {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .add-form {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.75rem;
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .date-inputs {
    display: flex;
    gap: 0.5rem;
  }

  .date-field {
    flex: 1;
  }

  .date-field label, .reason-field label {
    display: block;
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-bottom: 0.15rem;
  }

  .date-field input, .reason-field input {
    width: 100%;
    padding: 0.4rem;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.85rem;
    box-sizing: border-box;
  }

  .date-field input:focus, .reason-field input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .reason-field {
    flex: 1;
  }

  .add-btn {
    align-self: flex-start;
    background: var(--accent-color);
    color: white;
    border: none;
    padding: 0.4rem 0.8rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
  }

  .add-btn:hover:not(:disabled) {
    background: var(--accent-color-hover);
  }

  .add-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.5rem 0.75rem;
    border-radius: 4px;
    border: 1px solid var(--error-color);
    font-size: 0.85rem;
  }

  .loading-text, .empty-text {
    color: var(--text-muted);
    font-size: 0.85rem;
    margin: 0;
  }

  .dates-list {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .date-range {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 0.75rem;
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .range-info {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .range-dates {
    font-size: 0.9rem;
    font-weight: 500;
  }

  .range-reason {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .remove-btn {
    background: transparent;
    border: 1px solid var(--error-color);
    color: var(--error-color);
    width: 26px;
    height: 26px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1.1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .remove-btn:hover {
    background: var(--error-color);
    color: white;
  }

  @media (max-width: 480px) {
    .date-inputs {
      flex-direction: column;
    }
  }
</style>

<!--
  @component RentalRequestDialog
  Modal dialog for creating a rental request.
  Contains date picker, pricing breakdown, and optional note.
-->
<script>
  import { run } from 'svelte/legacy';

  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import DateRangePicker from './DateRangePicker.svelte';
  import { countDays } from '$lib/utils/rentalPricing.js';

  const dispatch = createEventDispatcher();

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {boolean} [show]
   * @property {object} offer
   * @property {Set<string>} [unavailableDates]
   * @property {string|null} [initialStart]
   * @property {string|null} [initialEnd]
   */

  /** @type {Props} */
  let {
    show = $bindable(false),
    offer,
    unavailableDates = new Set(),
    initialStart = null,
    initialEnd = null
  } = $props();

  let selectedStart = $state(null);
  let selectedEnd = $state(null);
  let note = $state('');
  let submitting = $state(false);
  let error = $state('');

  // Initialize from calendar selection when dialog opens
  let initialized = $state(false);


  function checkConflict(start, end) {
    const s = new Date(start + 'T00:00:00');
    const e = new Date(end + 'T00:00:00');
    for (let d = new Date(s); d <= e; d.setDate(d.getDate() + 1)) {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      if (unavailableDates.has(`${y}-${m}-${day}`)) return true;
    }
    return false;
  }

  function handleDateChange(e) {
    selectedStart = e.detail.start;
    selectedEnd = e.detail.end;
    error = '';
  }

  function close() {
    show = false;
    selectedStart = null;
    selectedEnd = null;
    note = '';
    error = '';
    submitting = false;
    dispatch('close');
  }

  async function handleSubmit() {
    if (!canSubmit) return;

    error = '';
    submitting = true;

    try {
      const res = await fetch(`/api/rental/${offer.id}/requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_date: selectedStart,
          end_date: selectedEnd,
          note: note.trim() || null
        })
      });

      const data = await res.json();

      if (!res.ok) {
        error = data.error || 'Failed to submit rental request.';
        return;
      }

      dispatch('submit', data);
      close();
    } catch (err) {
      error = 'Failed to submit rental request.';
    } finally {
      submitting = false;
    }
  }

  function handleOverlayClick(e) {
    if (e.target.classList.contains('modal-overlay')) close();
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') close();
  }
  run(() => {
    if (show && !initialized) {
      selectedStart = initialStart || null;
      selectedEnd = initialEnd || null;
      initialized = true;
    } else if (!show) {
      initialized = false;
    }
  });
  let totalDays = $derived(selectedStart && selectedEnd ? countDays(selectedStart, selectedEnd) : 0);
  let hasConflict = $derived(selectedStart && selectedEnd ? checkConflict(selectedStart, selectedEnd) : false);
  let canSubmit = $derived(selectedStart && selectedEnd && totalDays > 0 && !submitting && !hasConflict);
</script>

{#if show}
  <div
    class="modal-overlay"
    role="button"
    tabindex="0"
    onclick={handleOverlayClick}
    onkeydown={handleKeydown}
  >
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="rental-request-title">
      <h3 id="rental-request-title">Request Rental</h3>
      <p class="offer-title">{offer.title}</p>

      <div class="dialog-content">
        <DateRangePicker
          bind:selectedStart
          bind:selectedEnd
          pricePerDay={Number(offer.price_per_day)}
          discounts={offer.discounts || []}
          deposit={Number(offer.deposit)}
          {unavailableDates}
          on:change={handleDateChange}
        />

        <div class="note-field">
          <label for="request-note">Message to Owner (optional)</label>
          <textarea
            id="request-note"
            bind:value={note}
            placeholder="Any details about your rental needs..."
            maxlength="1000"
            rows="3"
          ></textarea>
        </div>

        {#if error}
          <div class="error-banner">{error}</div>
        {/if}
      </div>

      <div class="actions">
        <button type="button" onclick={close}>Cancel</button>
        <button
          type="button"
          class="btn-primary"
          onclick={handleSubmit}
          disabled={!canSubmit}
        >
          {submitting ? 'Submitting...' : 'Submit Request'}
        </button>
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
    z-index: 100;
  }

  .modal {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    width: 480px;
    max-width: calc(100% - 32px);
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }

  .modal h3 {
    margin-top: 0;
    margin-bottom: 0.25rem;
  }

  .offer-title {
    color: var(--text-muted);
    font-size: 0.9rem;
    margin: 0 0 1rem;
  }

  .dialog-content {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .note-field {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .note-field label {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-muted);
  }

  .note-field textarea {
    padding: 0.5rem;
    background: var(--primary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.9rem;
    resize: vertical;
    font-family: inherit;
    box-sizing: border-box;
  }

  .note-field textarea:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.5rem 0.75rem;
    border-radius: 4px;
    border: 1px solid var(--error-color);
    font-size: 0.85rem;
  }

  .actions {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
    margin-top: 1.25rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
  }

  .actions button {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
  }

  .actions button:first-child {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .actions button:first-child:hover {
    background: var(--hover-color);
  }

  .btn-primary {
    background: var(--accent-color);
    color: white;
    border: none;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--accent-color-hover);
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 480px) {
    .modal {
      padding: 1rem;
    }
  }
</style>

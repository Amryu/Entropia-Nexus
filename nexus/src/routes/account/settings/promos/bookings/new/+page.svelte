<!--
  @component New Booking
  Form for creating a new promo booking with promo selector, slot type, date picker, and weeks.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto } from '$app/navigation';
  import { addToast } from '$lib/stores/toasts';

  let { data } = $props();

  let promos = $derived(data.promos ?? []);
  let submitting = $state(false);

  // Form fields
  let selectedPromoId = $state('');
  let slotType = $state('');
  let startDate = $state('');
  let weeks = $state(1);

  const MIN_WEEKS = 1;
  const MAX_WEEKS = 52;

  // Map promo_type to valid slot types
  const PROMO_TYPE_SLOTS = {
    placement: [
      { value: 'left', label: 'Left sidebar' },
      { value: 'right', label: 'Right sidebar' }
    ],
    featured_post: [
      { value: 'featured_post', label: 'Featured post' }
    ]
  };

  let selectedPromo = $derived(promos.find(p => String(p.id) === String(selectedPromoId)) || null);
  let availableSlots = $derived(selectedPromo ? (PROMO_TYPE_SLOTS[selectedPromo.promo_type] || []) : []);

  // Auto-set slot type when there's only one option
  $effect(() => {
    if (availableSlots.length === 1 && slotType !== availableSlots[0].value) {
      slotType = availableSlots[0].value;
    } else if (availableSlots.length === 0) {
      slotType = '';
    }
  });

  // Set default start date to today
  $effect(() => {
    if (!startDate) {
      const today = new Date();
      startDate = today.toISOString().split('T')[0];
    }
  });

  let endDateDisplay = $derived(() => {
    if (!startDate || !weeks) return '';
    const start = new Date(startDate);
    if (isNaN(start.getTime())) return '';
    const end = new Date(start.getTime() + weeks * 7 * 24 * 60 * 60 * 1000);
    return end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  });

  async function createBooking() {
    if (!selectedPromoId) {
      addToast('Please select a promo', 'error');
      return;
    }
    if (!slotType) {
      addToast('Please select a slot type', 'error');
      return;
    }
    if (!startDate) {
      addToast('Please select a start date', 'error');
      return;
    }
    if (weeks < MIN_WEEKS || weeks > MAX_WEEKS) {
      addToast(`Weeks must be between ${MIN_WEEKS} and ${MAX_WEEKS}`, 'error');
      return;
    }

    submitting = true;
    try {
      const res = await fetch('/api/promos/bookings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          promo_id: parseInt(selectedPromoId),
          slot_type: slotType,
          start_date: startDate,
          weeks
        })
      });

      const result = await res.json();
      if (!res.ok) {
        addToast(result?.error || 'Failed to create booking', 'error');
        return;
      }

      addToast('Booking created successfully', 'success');
      goto(`/account/settings/promos/bookings/${result.id}`);
    } catch {
      addToast('Network error', 'error');
    } finally {
      submitting = false;
    }
  }
</script>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/account">Account</a>
      <span>/</span>
      <a href="/account/settings/promos">Promos</a>
      <span>/</span>
      <a href="/account/settings/promos/bookings">Bookings</a>
      <span>/</span>
      <span>New</span>
    </div>

    <h1>New Booking</h1>

    {#if promos.length === 0}
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
        <p>You need to create a promo before booking a slot.</p>
        <a href="/account/settings/promos/library/new" class="btn-primary">Create Promo</a>
      </div>
    {:else}
      <div class="form-section">
        <label class="form-label">
          <span>Select Promo <span class="required">*</span></span>
          <select class="form-select" bind:value={selectedPromoId}>
            <option value="">Choose a promo...</option>
            {#each promos as promo}
              <option value={promo.id}>{promo.name} ({promo.promo_type === 'placement' ? 'Placement' : 'Featured Post'})</option>
            {/each}
          </select>
        </label>

        {#if selectedPromo}
          <label class="form-label">
            <span>Slot Type <span class="required">*</span></span>
            <select class="form-select" bind:value={slotType}>
              {#if availableSlots.length > 1}
                <option value="">Choose a slot...</option>
              {/if}
              {#each availableSlots as slot}
                <option value={slot.value}>{slot.label}</option>
              {/each}
            </select>
          </label>
        {/if}

        <label class="form-label">
          <span>Start Date <span class="required">*</span></span>
          <input class="form-input" type="date" bind:value={startDate} min={new Date().toISOString().split('T')[0]} />
        </label>

        <label class="form-label">
          <span>Duration (weeks) <span class="required">*</span></span>
          <input class="form-input" type="number" bind:value={weeks} min={MIN_WEEKS} max={MAX_WEEKS} />
        </label>

        {#if endDateDisplay()}
          <div class="info-row">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            <span>End date: <strong>{endDateDisplay()}</strong></span>
          </div>
        {/if}
      </div>

      <div class="form-actions">
        <a href="/account/settings/promos/bookings" class="btn-secondary">Cancel</a>
        <button class="btn-primary" disabled={submitting} onclick={createBooking}>
          {submitting ? 'Creating...' : 'Create Booking'}
        </button>
      </div>
    {/if}
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    max-width: 600px;
    margin: 0 auto;
    padding: 1.5rem;
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

  h1 {
    margin: 0 0 1.5rem;
    font-size: 1.75rem;
    color: var(--text-color);
  }

  .form-section {
    margin-bottom: 2rem;
  }

  .form-label {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-color);
    margin-bottom: 1rem;
  }

  .required {
    color: #ef4444;
  }

  .form-input,
  .form-select {
    padding: 0.5rem 0.75rem;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 0.875rem;
    font-family: inherit;
  }

  .form-input:focus,
  .form-select:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .info-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8125rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
  }

  .info-row strong {
    color: var(--text-color);
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 3rem 1rem;
    gap: 1rem;
    color: var(--text-muted);
  }

  .empty-state p {
    margin: 0;
    max-width: 300px;
    font-size: 0.9rem;
  }

  .form-actions {
    display: flex;
    gap: 0.75rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
  }

  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1.25rem;
    background: var(--accent-color);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 600;
    text-decoration: none;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.5rem 1rem;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 0.875rem;
    text-decoration: none;
    cursor: pointer;
    transition: border-color 0.15s;
  }

  .btn-secondary:hover {
    border-color: var(--accent-color);
  }

  @media (max-width: 768px) {
    .form-actions {
      flex-direction: column;
    }
  }
</style>

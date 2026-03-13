<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import { goto } from '$app/navigation';
  import { apiPut } from '$lib/util';
  import AvailabilityCalendar from '$lib/components/services/AvailabilityCalendar.svelte';

  let { data } = $props();

  let service = $derived(data.service);
  let availability = $derived(Array.isArray(data.availability) ? data.availability : []);

  let saving = $state(false);
  let saveStatus = $state(''); // '', 'success', 'error'
  let hasChanges = $state(false);

  // Track the current state - re-sync from page data on navigation
  let currentSlots = $state([]);

  $effect(() => {
    currentSlots = [...availability];
    hasChanges = false;
  });

  function handleUpdate(data) {
    currentSlots = data;
    hasChanges = true;
    saveStatus = '';
  }

  async function saveAvailability() {
    saveStatus = '';
    saving = true;

    console.log('Saving availability:', {
      slotsCount: currentSlots.length,
      sampleSlots: currentSlots.slice(0, 3)
    });

    try {
      const result = await apiPut(fetch, `/api/services/${service.id}/availability`, {
        slots: currentSlots
      });

      console.log('Save result:', result);

      if (!result) {
        saveStatus = 'error';
        saving = false;
        setTimeout(() => { saveStatus = ''; }, 3000);
        return;
      }

      if (result.error) {
        saveStatus = 'error';
        saving = false;
        setTimeout(() => { saveStatus = ''; }, 3000);
        return;
      }

      // Normalize times in server response (strip seconds)
      const normalizedResult = Array.isArray(result) 
        ? result.map(slot => ({
            ...slot,
            start_time: slot.start_time.substring(0, 5),
            end_time: slot.end_time.substring(0, 5)
          }))
        : [];

      console.log('Normalized result:', {
        count: normalizedResult.length,
        sample: normalizedResult.slice(0, 3)
      });

      // Update the current slots with the normalized server response
      currentSlots = [...normalizedResult];
      
      hasChanges = false;
      saveStatus = 'success';
      saving = false;
      setTimeout(() => { saveStatus = ''; }, 3000);
    } catch (e) {
      console.error('Save availability error:', e);
      saveStatus = 'error';
      saving = false;
      setTimeout(() => { saveStatus = ''; }, 3000);
    }
  }

  function scrollToTop() {
    const scrollContainer = document.querySelector('.scroll-container');
    if (scrollContainer) {
      scrollContainer.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    }
  }

  function discardChanges() {
    currentSlots = [...availability];
    hasChanges = false;
    saveStatus = '';
  }
</script>

<svelte:head>
  <title>Edit Availability - {service.title} | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="header-row">
      <a href="/market/services/{service.id}" class="back-link">&larr; Back to Service</a>
    </div>

  <h1>Edit Availability of "{service.title}"</h1>

  <p class="description">
    Set your weekly availability schedule. Click or drag to select time slots when you're available to provide this service.
    Times are in <strong>MA Time (UTC+1/CET)</strong>.
  </p>

  <div class="calendar-section">
    <AvailabilityCalendar
      availability={currentSlots}
      onupdate={handleUpdate}
    />
  </div>

  <div class="form-actions">
    <div class="left-actions">
      {#if hasChanges}
        <span class="unsaved-indicator">Unsaved changes</span>
      {/if}
    </div>
    <div class="right-actions">
      <button type="button" class="cancel-btn" onclick={discardChanges} disabled={!hasChanges || saving}>
        Discard Changes
      </button>
      <button 
        type="button" 
        class="save-btn" 
        class:success={saveStatus === 'success'}
        class:error={saveStatus === 'error'}
        onclick={saveAvailability} 
        disabled={!hasChanges || saving}
      >
        {#if saving}
          Saving...
        {:else if saveStatus === 'success'}
          ✓ Saved Successfully
        {:else if saveStatus === 'error'}
          ✗ Save Failed
        {:else}
          Save Availability
        {/if}
      </button>
    </div>
  </div>

  <div class="help-section">
    <h3>Tips</h3>
    <ul>
      <li><strong>Click the hour</strong> (e.g., "09:00") to toggle that hour for all days</li>
      <li><strong>Click the arrow ▼</strong> to expand and see 15-minute slots</li>
      <li><strong>Click and drag</strong> on expanded slots to select multiple at once</li>
      <li>Use the <strong>quick action buttons</strong> to set common schedules</li>
      <li>Use the <strong>+ / -</strong> buttons on day headers to select/clear entire days</li>
    </ul>
  </div>
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    padding: 1rem;
    padding-bottom: 2rem;
    max-width: 900px;
    margin: 0 auto;
    box-sizing: border-box;
  }

  .header-row {
    margin-bottom: 1rem;
  }

  .back-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .back-link:hover {
    text-decoration: underline;
  }

  h1 {
    margin: 0 0 1rem 0;
    font-size: 1.5rem;
  }

  .description {
    color: var(--text-color);
    margin-bottom: 1.5rem;
    line-height: 1.5;
  }

  .calendar-section {
    background: var(--secondary-color);
    border: 1px solid #666;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1.5rem;
  }

  .form-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
    flex-wrap: wrap;
    gap: 1rem;
  }

  .left-actions {
    display: flex;
    align-items: center;
  }

  .unsaved-indicator {
    color: #856404;
    background: #fff3cd;
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    font-size: 0.9rem;
  }

  .right-actions {
    display: flex;
    gap: 1rem;
  }

  .cancel-btn, .save-btn {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 4px;
    font-size: 1rem;
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
    transition: background-color 0.3s ease;
  }

  .save-btn:hover:not(:disabled) {
    background: #3a8eef;
  }

  .save-btn.success {
    background: #28a745;
  }

  .save-btn.success:hover:not(:disabled) {
    background: #28a745;
  }

  .save-btn.error {
    background: #dc3545;
  }

  .save-btn.error:hover:not(:disabled) {
    background: #dc3545;
  }

  .cancel-btn:disabled, .save-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .help-section {
    background: var(--secondary-color);
    border: 1px solid #666;
    border-radius: 8px;
    padding: 1rem 1.5rem;
  }

  .help-section h3 {
    margin: 0 0 0.75rem 0;
    font-size: 1rem;
  }

  .help-section ul {
    margin: 0;
    padding-left: 1.25rem;
  }

  .help-section li {
    margin-bottom: 0.5rem;
    line-height: 1.4;
  }

  .help-section li:last-child {
    margin-bottom: 0;
  }

  @media (max-width: 600px) {
    .page-container {
      padding: 0.75rem;
    }

    h1 {
      font-size: 1.25rem;
    }

    .form-actions {
      flex-direction: column;
      align-items: stretch;
    }

    .left-actions {
      justify-content: center;
    }

    .right-actions {
      flex-direction: column;
    }

    .cancel-btn, .save-btn {
      width: 100%;
    }

    .calendar-section {
      padding: 0.5rem;
    }

    .help-section {
      padding: 0.75rem 1rem;
    }
  }
</style>

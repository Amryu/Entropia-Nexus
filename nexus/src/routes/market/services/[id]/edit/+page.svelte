<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { apiPut } from '$lib/util';
  import EquipmentEditor from '$lib/components/services/EquipmentEditor.svelte';
  import PilotManager from '$lib/components/services/PilotManager.svelte';
  import { loadEntity } from '$lib/utils/entityLoader';

  export let data;

  // Check if this is a newly created service
  $: isNewService = $page.url.searchParams.get('new') === '1';

  $: planets = data.planets || [];
  $: service = data.service;
  $: pilots = data.pilots || [];

  let saving = false;
  let error = '';

  // Lazy loaded entity data
  let clothings = [];
  let clothingsLoading = true;

  onMount(async () => {
    clothingsLoading = true;
    try {
      clothings = await loadEntity('clothings');
    } catch (e) {
      console.error('Failed to load clothings:', e);
    } finally {
      clothingsLoading = false;
    }
  });

  // Form data - initialized from data.service (not the reactive variable)
  let serviceType = data.service?.type || 'healing';
  let title = data.service?.title || '';
  let description = data.service?.description || '';
  let planetId = data.service?.planet_id || null;
  let willingToTravel = data.service?.willing_to_travel || false;
  let travelFee = data.service?.travel_fee ? parseFloat(data.service.travel_fee).toFixed(2) : null;

  // Healing details
  let paramedicLevel = data.service?.healing_details?.paramedic_level || null;
  let acceptsTimeBilling = data.service?.healing_details?.accepts_time_billing !== false;
  let ratePerHour = data.service?.healing_details?.rate_per_hour ? parseFloat(data.service.healing_details.rate_per_hour).toFixed(2) : (data.service?.dps_details?.rate_per_hour ? parseFloat(data.service.dps_details.rate_per_hour).toFixed(2) : null);
  let acceptsDecayBilling = data.service?.healing_details?.accepts_decay_billing !== false || data.service?.dps_details?.accepts_decay_billing !== false;

  // DPS details
  let dpsNotes = data.service?.dps_details?.notes || '';

  // Equipment
  let equipment = data.service?.equipment || [];

  // Transportation details
  let transportationType = data.service?.transportation_details?.transportation_type || 'regular';
  let shipName = data.service?.transportation_details?.ship_name || '';
  let serviceMode = data.service?.transportation_details?.service_mode || 'on_demand';

  // Custom type name
  let customTypeName = data.service?.custom_type_name || '';

  // Ship name options for regular transportation
  const regularShipOptions = ['Sleipnir', 'Quad-Wing Interceptor'];

  // Service mode options
  const serviceModeOptions = [
    { value: 'on_demand', label: 'On Demand' },
    { value: 'scheduled', label: 'Scheduled' }
  ];

  // Reactive: reset ship name and service mode when transportation type changes
  $: if (transportationType === 'regular') {
    shipName = shipName && regularShipOptions.includes(shipName) ? shipName : '';
    serviceMode = 'on_demand';
  } else if (transportationType === 'warp_equus') {
    shipName = 'Quad-Wing Equus';
    serviceMode = 'on_demand';
  } else if (transportationType === 'warp_privateer') {
    shipName = shipName === 'Quad-Wing Equus' || regularShipOptions.includes(shipName) ? '' : shipName;
  }

  const serviceTypes = [
    { value: 'healing', label: 'Healing' },
    { value: 'dps', label: 'DPS' },
    { value: 'transportation', label: 'Transportation' },
    { value: 'custom', label: 'Custom' }
  ];

  const transportationTypes = [
    { value: 'regular', label: 'Regular' },
    { value: 'warp_equus', label: 'Warp (Equus)' },
    { value: 'warp_privateer', label: 'Warp (Privateer/Mothership)' }
  ];

  // Dynamic placeholder based on service type
  $: titlePlaceholder = {
    healing: 'e.g., Professional Healing Service',
    dps: 'e.g., High-Level DPS Support',
    transportation: 'e.g., Calypso to Arkadia Warp Service',
    custom: 'e.g., Mining Finder Service'
  }[serviceType] || 'Enter service title';

  async function handleSubmit() {
    error = '';

    if (!title.trim()) {
      error = 'Please enter a service title.';
      return;
    }

    if (serviceType === 'custom' && !customTypeName.trim()) {
      error = 'Please enter a custom type name.';
      return;
    }

    if ((serviceType === 'healing' || serviceType === 'dps') && equipment.length > 50) {
      error = 'Equipment list cannot exceed 50 items.';
      return;
    }

    saving = true;

    const payload = {
      // Note: type cannot be changed after creation
      title: title.trim(),
      description: description.trim() || null,
      planet_id: serviceType === 'transportation' ? null : (planetId || null),
      willing_to_travel: serviceType === 'transportation' ? true : willingToTravel,
      travel_fee: (serviceType === 'transportation' || willingToTravel) && travelFee ? parseFloat(travelFee) : null,
      equipment: (serviceType === 'healing' || serviceType === 'dps') ? equipment : []
    };

    if (serviceType === 'custom') {
      payload.custom_type_name = customTypeName.trim();
    }

    if (serviceType === 'healing') {
      payload.healing_details = {
        paramedic_level: paramedicLevel ? parseInt(paramedicLevel) : null,
        accepts_time_billing: acceptsTimeBilling,
        rate_per_hour: acceptsTimeBilling && ratePerHour ? parseFloat(ratePerHour) : null,
        accepts_decay_billing: acceptsDecayBilling
      };
    }

    if (serviceType === 'dps') {
      payload.dps_details = {
        accepts_time_billing: acceptsTimeBilling,
        rate_per_hour: acceptsTimeBilling && ratePerHour ? parseFloat(ratePerHour) : null,
        accepts_decay_billing: acceptsDecayBilling,
        notes: dpsNotes.trim() || null
      };
    }

    if (serviceType === 'transportation') {
      payload.transportation_details = {
        transportation_type: transportationType,
        ship_name: shipName || null,
        service_mode: serviceMode
      };
    }

    try {
      const result = await apiPut(fetch, `/api/services/${service.id}`, payload);

      if (result.error) {
        error = result.error;
        saving = false;
        return;
      }

      // Success - redirect to the service
      goto(`/market/services/${service.id}`);
    } catch (e) {
      error = 'Failed to update service. Please try again.';
      saving = false;
    }
  }

  async function handleToggleActive() {
    const newState = !service.is_active;
    const action = newState ? 'activate' : 'deactivate';

    if (!confirm(`Are you sure you want to ${action} this service?${!newState ? ' It will no longer be visible to others.' : ''}`)) {
      return;
    }

    saving = true;
    try {
      const result = await apiPut(fetch, `/api/services/${service.id}`, { is_active: newState });
      if (result.error) {
        error = result.error;
        saving = false;
        return;
      }
      goto('/market/services/my');
    } catch (e) {
      error = `Failed to ${action} service.`;
      saving = false;
    }
  }
</script>

<svelte:head>
  <title>Edit Service | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="header-row">
      <a href="/market/services/{service.id}" class="back-link">&larr; Back to Service</a>
    </div>

    <h1>Edit Service</h1>

  {#if !service.is_active}
    <div class="inactive-banner {isNewService ? 'new-service' : ''}">
      {#if isNewService}
        <strong>Service created successfully!</strong>
        <p>Complete your service configuration below, then click "Activate Service" at the bottom to make it visible to customers.</p>
      {:else}
        <strong>This service is currently deactivated.</strong>
        <p>It is not visible to other users. Click "Activate Service" at the bottom to make it visible again.</p>
      {/if}
    </div>
  {/if}

  {#if error}
    <div class="error-message">{error}</div>
  {/if}

  <form on:submit|preventDefault={handleSubmit} class="service-form">
    <div class="form-section">
      <h2>Basic Information</h2>

      <div class="form-group">
        <label for="serviceType">Service Type</label>
        <select id="serviceType" bind:value={serviceType} disabled>
          {#each serviceTypes as type}
            <option value={type.value}>{type.label}</option>
          {/each}
        </select>
        <small>Service type cannot be changed after creation</small>
      </div>

      {#if serviceType === 'custom'}
        <div class="form-group">
          <label for="customTypeName">Custom Type Name *</label>
          <input type="text" id="customTypeName" bind:value={customTypeName} placeholder="e.g., Pet Training" />
        </div>
      {/if}

      <div class="form-group">
        <label for="title">Service Title *</label>
        <input type="text" id="title" bind:value={title} placeholder={titlePlaceholder} />
      </div>

      <div class="form-group">
        <label for="description">Description</label>
        <textarea id="description" bind:value={description} rows="4" placeholder="Describe your service..."></textarea>
      </div>
    </div>

    {#if serviceType !== 'transportation'}
      <div class="form-section">
        <h2>Location</h2>

        <div class="form-group">
          <label for="planet">Based On Planet</label>
          <select id="planet" bind:value={planetId}>
            <option value={null}>-- Select Planet --</option>
            {#each planets.filter(p => p.Id > 0) as planet}
              <option value={planet.Id}>{planet.Name}</option>
            {/each}
          </select>
        </div>

        <div class="form-group checkbox-group">
          <label>
            <input type="checkbox" bind:checked={willingToTravel} />
            Willing to travel to other planets
          </label>
        </div>

        {#if willingToTravel}
          <div class="form-group">
            <label for="travelFee">Travel Fee (PED)</label>
            <input type="number" id="travelFee" bind:value={travelFee} step="0.01" min="0" placeholder="Fee for traveling through lootable space" />
            <small>Only charged when traveling between planet groups through lootable space</small>
          </div>
        {/if}
      </div>
    {/if}

    {#if serviceType === 'healing' || serviceType === 'dps'}
      <div class="form-section">
        <h2>{serviceType === 'healing' ? 'Healing' : 'DPS'} Details</h2>

        {#if serviceType === 'healing'}
          <div class="form-group">
            <label for="paramedicLevel">Paramedic Level</label>
            <input type="number" id="paramedicLevel" bind:value={paramedicLevel} min="0" placeholder="Your paramedic profession level" />
          </div>
        {/if}

        {#if serviceType === 'dps'}
          <div class="form-group">
            <label for="dpsNotes">Notes</label>
            <textarea id="dpsNotes" bind:value={dpsNotes} rows="2" placeholder="e.g., Specializing in hunting Atrox"></textarea>
          </div>
        {/if}

        <div class="form-section-inner">
          <h3>Pricing Options</h3>

          <div class="form-group checkbox-group">
            <label>
              <input type="checkbox" bind:checked={acceptsTimeBilling} />
              Accept time-based pricing
            </label>
          </div>

          {#if acceptsTimeBilling}
            <div class="form-group">
              <label for="ratePerHour">Rate per Hour (PED)</label>
              <input type="number" id="ratePerHour" bind:value={ratePerHour} step="0.01" min="0" placeholder="Your hourly rate" />
            </div>
          {/if}

          <div class="form-group checkbox-group">
            <label>
              <input type="checkbox" bind:checked={acceptsDecayBilling} />
              Accept decay-based pricing
            </label>
          </div>
          <small>Uncheck all options to offer a free service. Decay pricing amount is determined after service completion.</small>
        </div>

        <EquipmentEditor serviceType={serviceType} bind:equipment {clothings} loading={clothingsLoading} />
      </div>
    {/if}

    {#if serviceType === 'transportation'}
      <div class="form-section">
        <h2>Transportation Details</h2>

        <div class="form-group">
          <label for="transportationType">Transportation Type *</label>
          <select id="transportationType" bind:value={transportationType}>
            {#each transportationTypes as type}
              <option value={type.value}>{type.label}</option>
            {/each}
          </select>
        </div>

        <div class="form-group">
          <label for="shipName">Ship Name</label>
          {#if transportationType === 'regular'}
            <select id="shipName" bind:value={shipName}>
              <option value="">-- Select Ship --</option>
              {#each regularShipOptions as ship}
                <option value={ship}>{ship}</option>
              {/each}
            </select>
          {:else if transportationType === 'warp_equus'}
            <input type="text" id="shipName" value="Quad-Wing Equus" disabled />
          {:else}
            <input type="text" id="shipName" bind:value={shipName} placeholder="Enter your ship name" />
          {/if}
        </div>

        <div class="form-group">
          <label for="serviceMode">Service Mode *</label>
          {#if transportationType === 'warp_privateer'}
            <select id="serviceMode" bind:value={serviceMode}>
              {#each serviceModeOptions as mode}
                <option value={mode.value}>{mode.label}</option>
              {/each}
            </select>
            <small>On Demand: Customers request flights as needed. Scheduled: You set regular flight times. Create separate services if you want to offer both.</small>
          {:else}
            <input type="text" id="serviceMode" value="On Demand" disabled />
            <small>Regular and Equus transportation is on-demand only.</small>
          {/if}
        </div>

        {#if transportationType === 'warp_privateer'}
          <PilotManager
            serviceId={service.id}
            {pilots}
            isOwner={true}
          />
        {/if}

        <div class="transportation-links">
          <a href="/market/services/{service.id}/ticket-offers" class="manage-link-btn">
            Manage Ticket Offers
          </a>
          <a href="/market/services/{service.id}/flights" class="manage-link-btn">
            Flight Dashboard
          </a>
        </div>
      </div>
    {/if}

    <div class="form-section availability-link-section">
      <h2>Availability Schedule</h2>
      <p>Set when you're available to provide this service.</p>
      <a href="/market/services/{service.id}/availability" class="availability-btn">Edit Availability Calendar</a>
    </div>

    <div class="form-actions">
      <button type="button" class={service.is_active ? "delete-btn" : "activate-btn"} on:click={handleToggleActive} disabled={saving}>
        {service.is_active ? 'Deactivate Service' : 'Activate Service'}
      </button>
      <div class="right-actions">
        <button type="button" class="cancel-btn" on:click={() => goto(`/market/services/${service.id}`)}>Cancel</button>
        <button type="submit" class="submit-btn" disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  </form>
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
    max-width: 800px;
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
    margin: 0 0 1.5rem 0;
  }

  .error-message {
    background: #fee;
    border: 1px solid #fcc;
    color: #c00;
    padding: 0.75rem 1rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .service-form {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .form-section {
    background: var(--secondary-color);
    border: 1px solid #666;
    border-radius: 8px;
    padding: 1.5rem;
  }

  .form-section h2 {
    margin: 0 0 1rem 0;
    font-size: 1.2rem;
    border-bottom: 1px solid #666;
    padding-bottom: 0.5rem;
  }

  .form-section-inner {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #555;
  }

  .form-section-inner h3 {
    margin: 0 0 0.75rem 0;
    font-size: 1rem;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group:last-child {
    margin-bottom: 0;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.25rem;
    font-weight: 500;
  }

  .form-group input[type="text"],
  .form-group input[type="number"],
  .form-group select,
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

  .form-group select option {
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

  .form-group select:disabled,
  .form-group input:disabled {
    opacity: 0.7;
    cursor: not-allowed;
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

  .info-text {
    color: #888;
    margin: 0;
  }

  .form-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .right-actions {
    display: flex;
    gap: 1rem;
  }

  .cancel-btn, .submit-btn, .delete-btn, .activate-btn {
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

  .cancel-btn:hover {
    background: var(--hover-color);
  }

  .submit-btn {
    background: #4a9eff;
    color: white;
  }

  .submit-btn:hover:not(:disabled) {
    background: #3a8eef;
  }

  .submit-btn:disabled, .delete-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .delete-btn {
    background: #e74c3c;
    color: white;
  }

  .delete-btn:hover:not(:disabled) {
    background: #c0392b;
  }

  .activate-btn {
    background: var(--success-color, #10b981);
    color: white;
  }

  .activate-btn:hover:not(:disabled) {
    background: var(--success-color-hover, #059669);
  }

  .inactive-banner {
    background: var(--warning-bg, #fef3c7);
    border: 1px solid var(--warning-color, #f59e0b);
    color: var(--warning-color, #92400e);
    padding: 1rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
  }

  .inactive-banner strong {
    display: block;
    margin-bottom: 0.5rem;
  }

  .inactive-banner p {
    margin: 0;
    font-size: 0.9rem;
  }

  .inactive-banner.new-service {
    background: var(--success-bg, #d1fae5);
    border-color: var(--success-color, #10b981);
    color: var(--success-text, #065f46);
  }

  .availability-link-section {
    text-align: center;
  }

  .availability-link-section p {
    margin: 0 0 1rem 0;
    color: #888;
  }

  .availability-btn {
    display: inline-block;
    background: var(--primary-color);
    color: var(--text-color);
    border: 1px solid #666;
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    text-decoration: none;
    font-weight: 500;
  }

  .availability-btn:hover {
    background: var(--hover-color);
  }

  .transportation-links {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #555;
    display: flex;
    gap: 1rem;
    justify-content: center;
    flex-wrap: wrap;
  }

  .manage-link-btn {
    display: inline-block;
    background: #4a9eff;
    color: white;
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    text-decoration: none;
    font-weight: 500;
  }

  .manage-link-btn:hover {
    background: #3a8eef;
  }
</style>

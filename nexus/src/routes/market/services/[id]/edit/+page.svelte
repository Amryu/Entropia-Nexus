<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { onMount, untrack } from 'svelte';
  import { apiPut } from '$lib/util';
  import EquipmentEditor from '$lib/components/services/EquipmentEditor.svelte';
  import PilotManager from '$lib/components/services/PilotManager.svelte';
  import { loadEntity } from '$lib/utils/entityLoader';

  let { data } = $props();

  // Check if this is a newly created service
  let isNewService = $derived($page.url.searchParams.get('new') === '1');

  let planets = $derived(data.planets || []);
  let service = $derived(data.service);
  let pilots = $derived(data.pilots || []);

  let saving = $state(false);
  let error = $state('');

  // Lazy loaded entity data
  let clothings = $state([]);
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

  // Form data - re-sync from page data on navigation
  let serviceType = $state('healing');
  let title = $state('');
  let description = $state('');
  let planetId = $state(null);
  let willingToTravel = $state(false);
  let travelFee = $state(null);

  // Healing details
  let paramedicLevel = $state(null);
  let acceptsTimeBilling = $state(true);
  let ratePerHour = $state(null);
  let acceptsDecayBilling = $state(true);

  // DPS details
  let dpsNotes = $state('');

  // Equipment
  let equipment = $state([]);

  // Transportation details
  let transportationType = $state('regular');
  let shipName = $state('');
  let serviceMode = $state('on_demand');

  // Custom type name
  let customTypeName = $state('');

  // Owner fields (transportation only)
  let differentOwner = $state(false);
  let ownerDisplayName = $state('');

  // Pickup (transportation)
  let allowsPickup = $state(false);
  let pickupFee = $state('');

  // Discord code (warp services only)
  let discordCode = $state('');

  // Populate form when service data changes (initial load or navigation)
  $effect(() => {
    const s = service;
    if (!s) return;
    serviceType = s.type || 'healing';
    title = s.title || '';
    description = s.description || '';
    planetId = s.planet_id || null;
    willingToTravel = s.willing_to_travel || false;
    travelFee = s.travel_fee ? parseFloat(s.travel_fee).toFixed(2) : null;
    paramedicLevel = s.healing_details?.paramedic_level || null;
    acceptsTimeBilling = s.healing_details?.accepts_time_billing !== false;
    ratePerHour = s.healing_details?.rate_per_hour ? parseFloat(s.healing_details.rate_per_hour).toFixed(2) : (s.dps_details?.rate_per_hour ? parseFloat(s.dps_details.rate_per_hour).toFixed(2) : null);
    acceptsDecayBilling = s.healing_details?.accepts_decay_billing !== false || s.dps_details?.accepts_decay_billing !== false;
    dpsNotes = s.dps_details?.notes || '';
    equipment = s.equipment || [];
    transportationType = s.transportation_details?.transportation_type || 'regular';
    shipName = s.transportation_details?.ship_name || '';
    serviceMode = s.transportation_details?.service_mode || 'on_demand';
    customTypeName = s.custom_type_name || '';
    differentOwner = !!(s.owner_display_name || s.owner_user_id);
    ownerDisplayName = s.owner_display_name || '';
    allowsPickup = s.transportation_details?.allows_pickup || false;
    pickupFee = s.transportation_details?.pickup_fee || '';
    discordCode = s.transportation_details?.discord_code || '';
  });

  // Ship name options for regular transportation
  const regularShipOptions = ['Sleipnir', 'Quad-Wing Interceptor'];

  // Service mode options
  const serviceModeOptions = [
    { value: 'on_demand', label: 'On Demand' },
    { value: 'scheduled', label: 'Scheduled' }
  ];

  // Reactive: reset ship name and service mode when transportation type changes
  $effect(() => {
    if (transportationType === 'regular') {
      const current = untrack(() => shipName);
      shipName = current && regularShipOptions.includes(current) ? current : '';
      serviceMode = 'on_demand';
    } else if (transportationType === 'warp_equus') {
      shipName = 'Quad-Wing Equus';
      serviceMode = 'on_demand';
    } else if (transportationType === 'warp_privateer') {
      const current = untrack(() => shipName);
      shipName = current === 'Quad-Wing Equus' || regularShipOptions.includes(current) ? '' : current;
    }
  });

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
  let titlePlaceholder = $derived({
    healing: 'e.g., Professional Healing Service',
    dps: 'e.g., High-Level DPS Support',
    transportation: 'e.g., Calypso to Arkadia Warp Service',
    custom: 'e.g., Mining Finder Service'
  }[serviceType] || 'Enter service title');

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
      description: description || null,
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
        service_mode: serviceMode,
        allows_pickup: allowsPickup,
        pickup_fee: allowsPickup && pickupFee ? parseFloat(pickupFee) : null,
        discord_code: (transportationType === 'warp_equus' || transportationType === 'warp_privateer') ? (discordCode.trim() || null) : null
      };
      payload.owner_display_name = differentOwner && ownerDisplayName.trim() ? ownerDisplayName.trim() : null;
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

  <form onsubmit={(e) => { e.preventDefault(); handleSubmit(e); }} class="service-form">
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
        <span class="form-label">Description</span>
        {#await import('$lib/components/wiki/RichTextEditor.svelte') then { default: RichTextEditor }}
          <RichTextEditor
            content={description}
            placeholder="Describe your service..."
            showHeadings={false}
            showCodeBlock={false}
            showVideo={false}
            showImages={false}
            onchange={(data) => description = data}
          />
        {/await}
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

        <EquipmentEditor serviceType={serviceType} bind:equipment {clothings} />
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

        <div class="form-group checkbox-group">
          <label>
            <input type="checkbox" bind:checked={allowsPickup} />
            Allow pickup requests
          </label>
          <small>Let customers request pickup from a custom location (incurs an additional jump).</small>
        </div>

        {#if allowsPickup}
          <div class="form-group">
            <label for="pickupFee">Pickup Fee (PED)</label>
            <input type="number" id="pickupFee" bind:value={pickupFee} min="0" step="0.01" placeholder="0.00" />
            <small>Flat fee charged per pickup request. Leave empty for no additional charge.</small>
          </div>
        {/if}

        <div class="form-group checkbox-group">
          <label>
            <input type="checkbox" bind:checked={differentOwner} />
            The ship owner is a different player
          </label>
        </div>

        {#if differentOwner}
          <div class="form-group">
            <label for="ownerDisplayName">Owner Name (EU Name)</label>
            <input type="text" id="ownerDisplayName" bind:value={ownerDisplayName} placeholder="Enter the owner's Entropia Universe name" maxlength="100" />
            <small>The owner does not need to have a Nexus account. If they do, they will get full management access.</small>
          </div>
        {/if}

        {#if transportationType === 'warp_equus' || transportationType === 'warp_privateer'}
          <div class="form-group">
            <label for="discordCode">Discord Server (optional)</label>
            <input type="text" id="discordCode" bind:value={discordCode} placeholder="Invite link or code" />
            <small>Setting this will disable Nexus Discord thread creation for this service's flights. Only the invite code is stored.</small>
          </div>
        {/if}

        {#if transportationType === 'warp_privateer'}
          <PilotManager
            serviceId={service.id}
            {pilots}
            isOwner={true}
            managerId={service.user_id}
            managerName={service.manager_name}
            ownerUserId={service.owner_user_id}
            ownerDisplayName={service.owner_display_name}
            currentUserId={data.user?.id}
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
      <button type="button" class={service.is_active ? "delete-btn" : "activate-btn"} onclick={handleToggleActive} disabled={saving}>
        {service.is_active ? 'Deactivate Service' : 'Activate Service'}
      </button>
      <div class="right-actions">
        <button type="button" class="cancel-btn" onclick={() => goto(`/market/services/${service.id}`)}>Cancel</button>
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

  .form-group label,
  .form-group .form-label {
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
    background: var(--success-bg);
    border-color: var(--success-color);
    color: var(--success-text);
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

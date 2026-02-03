<!--
  @component Vehicles Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Supports full wiki editing.

  Legacy editConfig preserved in vehicles-legacy/+page.svelte
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, getTypeLink } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import ItemSearchInput from '$lib/components/wiki/ItemSearchInput.svelte';
  import DefenseGridEdit from '$lib/components/wiki/DefenseGridEdit.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/Acquisition.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  // Wiki edit state
  import {
    editMode,
    isCreateMode as isCreateModeStore,
    initEditState,
    resetEditState,
    currentEntity,
    existingPendingChange,
    viewingPendingChange,
    setExistingPendingChange,
    setViewingPendingChange,
    updateField,
    changeMetadata
  } from '$lib/stores/wikiEditState';

  export let data;

  $: vehicle = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};
  $: allItems = data.allItems || [];
  $: pendingChange = data.pendingChange;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: isCreateMode = data.isCreateMode || false;
  $: materialsList = data.materials || [];
  $: vehicleAttachmentTypesList = data.vehicleAttachmentTypes || [];

  // Verified users can edit
  $: canEdit = user?.verified || user?.isAdmin;

  // Type options for vehicles
  const typeOptions = [
    { value: 'Land', label: 'Land' },
    { value: 'Water', label: 'Water' },
    { value: 'Air', label: 'Air' },
    { value: 'Amphibious', label: 'Amphibious' },
    { value: 'Space', label: 'Space' }
  ];

  // Empty vehicle template for create mode
  const emptyVehicle = {
    Id: null,
    Name: '',
    Properties: {
      Description: '',
      Type: 'Land',
      Weight: null,
      SpawnedWeight: null,
      PassengerCount: 1,
      ItemCapacity: null,
      WeightCapacity: null,
      WheelGrip: null,
      EnginePower: null,
      MaxSpeed: null,
      MaxStructuralIntegrity: null,
      Economy: {
        MaxTT: null,
        MinTT: null,
        Durability: null,
        FuelConsumptionActive: null,
        FuelConsumptionPassive: null
      },
      Defense: {}
    },
    Fuel: null,
    AttachmentSlots: []
  };

  // Initialize edit state when user/vehicle changes
  $: if (user) {
    const existingChange = data.existingChange || null;
    const initialEntity = isCreateMode
      ? (existingChange?.data || emptyVehicle)
      : vehicle;
    initEditState(initialEntity, 'Vehicle', isCreateMode, existingChange);
  }

  // Set pending change in store when it changes
  $: if (pendingChange) {
    setExistingPendingChange(pendingChange);
  }

  // Active vehicle: use currentEntity in edit mode, pendingChange data when viewing, otherwise original
  $: activeVehicle = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : vehicle;

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });

  // Build navigation items
  $: navItems = allItems;

  // Type filters for sidebar
  $: navFilters = [];

  // Sidebar table columns
  $: navTableColumns = [
    { key: 'type', header: 'Type', width: '60px', filterPlaceholder: 'Land', getValue: (item) => item.Properties?.Type, format: (v) => v || '-' },
    { key: 'speed', header: 'Speed', width: '60px', filterPlaceholder: '>50', getValue: (item) => item.Properties?.MaxSpeed, format: (v) => v != null ? v.toFixed(0) : '-' },
    { key: 'fuel', header: 'Fuel Usage', width: '80px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Economy?.FuelConsumptionActive ?? item.Properties?.Economy?.FuelConsumptionPassive, format: (v) => v != null ? v.toFixed(2) : '-' }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Vehicles', href: '/items/vehicles' },
    ...(activeVehicle?.Name ? [{ label: activeVehicle.Name }] : isCreateMode ? [{ label: 'New Vehicle' }] : [])
  ];

  // SEO
  $: seoDescription = activeVehicle?.Properties?.Description ||
    `${activeVehicle?.Name || 'Vehicle'} - ${activeVehicle?.Properties?.Type || ''} vehicle in Entropia Universe.`;

  $: canonicalUrl = activeVehicle?.Name
    ? `https://entropianexus.com/items/vehicles/${encodeURIComponentSafe(activeVehicle.Name)}`
    : 'https://entropianexus.com/items/vehicles';

  // Image URL for SEO
  $: entityImageUrl = vehicle?.Id ? `/api/img/vehicle/${vehicle.Id}` : null;

  // ========== CALCULATION FUNCTIONS ==========
  function getTotalDefense(item) {
    if (!item?.Properties?.Defense) return 0;
    const d = item.Properties.Defense;
    return (d.Impact ?? 0) + (d.Cut ?? 0) + (d.Stab ?? 0) + (d.Penetration ?? 0) +
           (d.Shrapnel ?? 0) + (d.Burn ?? 0) + (d.Cold ?? 0) + (d.Acid ?? 0) + (d.Electric ?? 0);
  }

  // ========== COMPUTED VALUES ==========
  $: totalDefense = getTotalDefense(activeVehicle);

  // Defense types for grid display
  const defenseTypes = ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    defense: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-vehicle-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-vehicle-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }

  // ========== EDIT HANDLERS ==========
  function handleDescriptionChange(event) {
    updateField('Properties.Description', event.detail);
  }
</script>

<WikiSEO
  title={activeVehicle?.Name || 'Vehicles'}
  description={seoDescription}
  entityType="Vehicle"
  entity={activeVehicle}
  imageUrl={entityImageUrl}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Vehicles"
  {breadcrumbs}
  entity={activeVehicle}
  entityType="Vehicle"
  basePath="/items/vehicles"
  {navItems}
  {navFilters}
  {navTableColumns}
  {user}
  editable={true}
  {canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
>
  {#if activeVehicle || isCreateMode}
    <!-- Pending Change Banner -->
    {#if $existingPendingChange && !$editMode && !isCreateMode}
      <div class="pending-change-banner">
        <div class="banner-content">
          <span class="banner-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
          </span>
          <span class="banner-text">
            This vehicle has a pending change by <strong>{$existingPendingChange.author_name || 'Unknown'}</strong>
            ({$existingPendingChange.state})
          </span>
        </div>
        <div class="banner-actions">
          {#if $viewingPendingChange}
            <button class="banner-btn" on:click={() => setViewingPendingChange(false)}>
              View Current
            </button>
          {:else}
            <button class="banner-btn primary" on:click={() => setViewingPendingChange(true)}>
              View Pending
            </button>
          {/if}
        </div>
      </div>
    {/if}

    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeVehicle?.Id}
            entityName={activeVehicle?.Name}
            entityType="vehicle"
            {user}
            isEditMode={$editMode}
            {isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              type="text"
              value={activeVehicle?.Name || ''}
              path="Name"
              placeholder="Enter vehicle name"
            />
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge">{activeVehicle?.Properties?.Type || 'Vehicle'}</span>
          </div>
        </div>

        <!-- Tier-1 Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Max Speed</span>
            <span class="stat-value">{activeVehicle?.Properties?.MaxSpeed != null ? `${activeVehicle.Properties.MaxSpeed.toFixed(2)} km/h` : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Passengers</span>
            <span class="stat-value">{activeVehicle?.Properties?.PassengerCount ?? 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Max. SI</span>
            <span class="stat-value">{activeVehicle?.Properties?.MaxStructuralIntegrity ?? 'N/A'}</span>
          </div>
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.Weight ?? ''}
                path="Properties.Weight"
                step={0.001}
                suffix="kg"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Spawned Weight</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.SpawnedWeight ?? ''}
                path="Properties.SpawnedWeight"
                step={0.1}
                suffix="kg"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">
              <InlineEdit
                type="select"
                value={activeVehicle?.Properties?.Type || 'Land'}
                path="Properties.Type"
                options={typeOptions}
              />
            </span>
          </div>
        </div>

        <!-- Vehicle Stats -->
        <div class="stats-section">
          <h4 class="section-title">Vehicle</h4>
          <div class="stat-row">
            <span class="stat-label">Passengers</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.PassengerCount ?? ''}
                path="Properties.PassengerCount"
                step={1}
                min={1}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Item Capacity</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.ItemCapacity ?? ''}
                path="Properties.ItemCapacity"
                step={1}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Weight Capacity</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.WeightCapacity ?? ''}
                path="Properties.WeightCapacity"
                step={0.1}
                suffix="kg"
              />
            </span>
          </div>
          {#if activeVehicle?.Properties?.Type === 'Land' || activeVehicle?.Properties?.Type === 'Amphibious'}
            <div class="stat-row">
              <span class="stat-label">Wheel Grip</span>
              <span class="stat-value">
                <InlineEdit
                  type="number"
                  value={activeVehicle?.Properties?.WheelGrip ?? ''}
                  path="Properties.WheelGrip"
                  step={0.01}
                />
              </span>
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Engine Power</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.EnginePower ?? ''}
                path="Properties.EnginePower"
                step={1}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max. Speed</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.MaxSpeed ?? ''}
                path="Properties.MaxSpeed"
                step={0.01}
                suffix=" km/h"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max. SI</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.MaxStructuralIntegrity ?? ''}
                path="Properties.MaxStructuralIntegrity"
                step={1}
              />
            </span>
          </div>
          {#if activeVehicle?.AttachmentSlots?.length > 0 && !$editMode}
            <div class="stat-row">
              <span class="stat-label">Attachment Slots</span>
              <span class="stat-value">{activeVehicle.AttachmentSlots.map(x => x.Name).join(', ')}</span>
            </div>
          {/if}
        </div>

        <!-- Attachment Slots Editor -->
        {#if $editMode || activeVehicle?.AttachmentSlots?.length > 0}
          <div class="stats-section attachment-slots-section">
            <h4 class="section-title">Attachment Slots</h4>
            {#if $editMode}
              <div class="attachment-slots-editor">
                {#each activeVehicle?.AttachmentSlots || [] as slot, index}
                  <div class="slot-row">
                    <select
                      class="vehicle-select"
                      value={slot.Name || ''}
                      on:change={(e) => {
                        const value = e.target.value;
                        const slots = [...(activeVehicle?.AttachmentSlots || [])];
                        slots[index] = { Name: value };
                        updateField('AttachmentSlots', slots);
                      }}
                    >
                      <option value="">Select slot type...</option>
                      {#each vehicleAttachmentTypesList as t}
                        <option value={t.Name}>{t.Name}</option>
                      {/each}
                    </select>
                    <button
                      type="button"
                      class="remove-slot-btn"
                      on:click={() => {
                        const slots = [...(activeVehicle?.AttachmentSlots || [])];
                        slots.splice(index, 1);
                        updateField('AttachmentSlots', slots);
                      }}
                      title="Remove slot"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                      </svg>
                    </button>
                  </div>
                {/each}
                <button
                  type="button"
                  class="add-slot-btn"
                  on:click={() => {
                    const slots = [...(activeVehicle?.AttachmentSlots || []), { Name: '' }];
                    updateField('AttachmentSlots', slots);
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                  </svg>
                  Add Slot
                </button>
              </div>
            {:else}
              <div class="attachment-slots-list">
                {#each activeVehicle?.AttachmentSlots || [] as slot}
                  <span class="slot-tag">{slot.Name}</span>
                {/each}
              </div>
            {/if}
          </div>
        {/if}

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max. TT</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.Economy?.MaxTT ?? ''}
                path="Properties.Economy.MaxTT"
                step={0.01}
                suffix=" PED"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min. TT</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.Economy?.MinTT ?? ''}
                path="Properties.Economy.MinTT"
                step={0.01}
                suffix=" PED"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Durability</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.Economy?.Durability ?? ''}
                path="Properties.Economy.Durability"
                step={1}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Fuel</span>
            <span class="stat-value">
              {#if $editMode}
                <ItemSearchInput
                  value={activeVehicle?.Fuel?.Name || ''}
                  placeholder="Search fuel..."
                  allowedTypes={['Material']}
                  on:change={(e) => {
                    const value = e.detail?.value || '';
                    if (!value) {
                      updateField('Fuel', null);
                    }
                  }}
                  on:select={(e) => {
                    if (e.detail?.value) {
                      updateField('Fuel', { Name: e.detail.value });
                    }
                  }}
                />
              {:else}
                {activeVehicle?.Fuel?.Name ?? 'N/A'}
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Consumption (Active)</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.Economy?.FuelConsumptionActive ?? ''}
                path="Properties.Economy.FuelConsumptionActive"
                step={0.01}
                suffix=" PED/km"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Consumption (Passive)</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeVehicle?.Properties?.Economy?.FuelConsumptionPassive ?? ''}
                path="Properties.Economy.FuelConsumptionPassive"
                step={0.01}
                suffix=" PED/min"
              />
            </span>
          </div>
        </div>

        <!-- Defense Grid -->
        {#if totalDefense > 0 || $editMode}
          <div class="stats-section defense-section">
            <h4 class="section-title">Defense</h4>
            <DefenseGridEdit
              defense={activeVehicle?.Properties?.Defense}
              fieldPath="Properties.Defense"
              title="Total Defense"
              types={defenseTypes}
            />
          </div>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            type="text"
            value={activeVehicle?.Name || ''}
            path="Name"
            placeholder="Enter vehicle name"
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeVehicle?.Properties?.Description || ''}
              on:change={handleDescriptionChange}
              placeholder="Enter a description for this vehicle..."
            />
          {:else if activeVehicle?.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeVehicle.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeVehicle?.Name || 'This vehicle'} is a {activeVehicle?.Properties?.Type?.toLowerCase() || ''} vehicle in Entropia Universe.
            </div>
          {/if}
        </div>

        <!-- Acquisition Section -->
        {#if additional.acquisition && !isCreateMode}
          <DataSection
            title="Acquisition"
            icon=""
            bind:expanded={panelStates.acquisition}
            on:toggle={savePanelStates}
          >
            <Acquisition acquisition={additional.acquisition} />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Vehicles</h2>
      <p>Select a vehicle from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .pending-change-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background-color: var(--warning-bg, #fef3c7);
    border: 1px solid var(--warning-border, #f59e0b);
    border-radius: 8px;
    margin-bottom: 16px;
  }

  :global(.dark) .pending-change-banner {
    background-color: rgba(245, 158, 11, 0.1);
    border-color: rgba(245, 158, 11, 0.3);
  }

  .banner-content {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .banner-icon {
    color: var(--warning-color, #d97706);
  }

  .banner-text {
    font-size: 14px;
    color: var(--text-color);
  }

  .banner-actions {
    display: flex;
    gap: 8px;
  }

  .banner-btn {
    padding: 6px 12px;
    font-size: 13px;
    border-radius: 4px;
    border: 1px solid var(--border-color, #555);
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s;
  }

  .banner-btn:hover {
    background-color: var(--secondary-color);
  }

  .banner-btn.primary {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .banner-btn.primary:hover {
    opacity: 0.9;
  }

  .layout-a {
    position: relative;
    width: 100%;
  }

  .layout-a::after {
    content: '';
    display: block;
    clear: both;
  }

  /* Floating infobox - Wikipedia style */
  .wiki-infobox-float {
    float: right;
    width: 300px;
    margin: 0 0 0 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 16px;
  }

  .infobox-header {
    text-align: center;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .infobox-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .infobox-subtitle {
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-top: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .type-badge {
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
  }

  /* Stats sections */
  .stats-section {
    padding: 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  .stats-section.tier-1 {
    background: linear-gradient(135deg, #4a7c59 0%, #3a6349 100%);
    padding: 14px;
  }

  .stats-section.tier-1 .stat-row.primary {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    padding: 8px 12px;
    margin-bottom: 6px;
  }

  .stats-section.tier-1 .stat-row.primary:last-child {
    margin-bottom: 0;
  }

  .stats-section.tier-1 .stat-label {
    color: rgba(255, 255, 255, 0.9);
    font-size: 13px;
    text-transform: uppercase;
    font-weight: 500;
  }

  .stats-section.tier-1 .stat-value {
    color: #e8f4e8;
    font-size: 18px;
    font-weight: 700;
  }

  .section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 10px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 4px 0;
    font-size: 13px;
  }

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    font-weight: 500;
    color: var(--text-color);
    text-align: right;
    word-break: break-word;
    max-width: 60%;
  }

  /* Attachment Slots Editor */
  .attachment-slots-editor {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .slot-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .slot-row .vehicle-select {
    flex: 1;
    padding: 4px 6px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    height: 28px;
  }

  .slot-row .vehicle-select:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .slot-row .vehicle-select option {
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
  }

  .remove-slot-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-muted, #999);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .remove-slot-btn:hover {
    background-color: var(--error-bg, #fee2e2);
    border-color: var(--error-color, #ef4444);
    color: var(--error-color, #ef4444);
  }

  .add-slot-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 8px 12px;
    border: 1px dashed var(--border-color, #555);
    border-radius: 4px;
    background-color: transparent;
    color: var(--text-muted, #999);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .add-slot-btn:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--bg-color, var(--primary-color));
  }

  .attachment-slots-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .slot-tag {
    padding: 4px 8px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    font-size: 12px;
    color: var(--text-color);
  }

  /* Mini defense grid for infobox */
  .infobox-defense-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
  }

  .mini-defense-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 6px 4px;
    background-color: var(--secondary-color);
    border-radius: 4px;
    border: 1px solid var(--border-color, #555);
  }

  .mini-defense-label {
    font-size: 9px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .mini-defense-value {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  /* Total defense full-width box */
  .defense-total-box {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
    padding: 10px 12px;
    background-color: var(--accent-color, #4a9eff);
    border-radius: 6px;
  }

  .defense-total-label {
    font-size: 12px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .defense-total-value {
    font-size: 18px;
    font-weight: 700;
    color: white;
  }

  .wiki-article {
    overflow: hidden;
  }

  .article-title {
    font-size: 32px;
    font-weight: 600;
    margin: 0 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--accent-color, #4a9eff);
  }

  .description-panel {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }

  .description-content {
    font-size: 15px;
    line-height: 1.6;
    color: var(--text-color);
  }

  .description-content.placeholder {
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .no-selection {
    text-align: center;
    padding: 60px 20px;
  }

  .no-selection h2 {
    font-size: 28px;
    margin-bottom: 12px;
  }

  .no-selection p {
    color: var(--text-muted, #999);
    margin: 8px 0;
  }

  /* Tablet adjustments */
  @media (max-width: 1023px) {
    .wiki-infobox-float {
      width: 280px;
      margin-left: 16px;
      padding: 14px;
    }
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .layout-a {
      max-width: 100%;
    }

    .wiki-infobox-float {
      float: none;
      width: auto;
      margin: 0 0 16px 0;
    }

    .article-title {
      display: none;
    }

    .infobox-title {
      font-size: 16px;
    }

    .pending-change-banner {
      flex-direction: column;
      gap: 12px;
      align-items: flex-start;
    }
  }
</style>

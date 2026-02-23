<!--
  @component Material Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox Tier 1: Type, Value (read-only)  |  Tier 2: Type (editable), Weight  |  Economy: Value (editable)
  Article: Description, Acquisition, Usage

  Supports full wiki editing with wikiEditState integration.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { encodeURIComponentSafe, clampDecimals, getLatestPendingUpdate, loadEditDeps } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';

  // Edit state management
  import {
    editMode,
    isCreateMode,
    initEditState,
    resetEditState,
    currentEntity,
    existingPendingChange,
    viewingPendingChange,
    setExistingPendingChange,
    setViewingPendingChange,
    updateField,
    changeMetadata
  } from '$lib/stores/wikiEditState.js';

  // Legacy components for data display
  import Acquisition from '$lib/components/wiki/Acquisition.svelte';
  import Usage from '$lib/components/wiki/Usage.svelte';

  // Material-specific editor
  import RefiningRecipesEditor from '$lib/components/wiki/RefiningRecipesEditor.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  export let data;

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = false;
  $: if ($editMode && data.availableItems === null && !editDepsLoading) {
    editDepsLoading = true;
    loadEditDeps([
      { key: 'availableItems', url: '/api/items' }
    ]).then(deps => {
      data = { ...data, ...deps };
      editDepsLoading = false;
    });
  }

  $: material = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: additional = data.additional || {};
  $: pendingChange = data.pendingChange;
  $: existingChange = data.existingChange;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: canCreateNew = data.canCreateNew ?? true;
  $: availableItems = data.availableItems || [];
  $: materialEntityId = material?.Id ?? material?.ItemId;
  $: userPendingUpdate = getLatestPendingUpdate(userPendingUpdates, materialEntityId);
  $: resolvedPendingChange = userPendingUpdate || pendingChange;
  $: canUsePendingChange = !!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve')));

  // Permission check - verified users can edit
  $: canEdit = user?.verified === true;

  // Empty entity template for create mode
  const emptyMaterial = {
    Id: null,
    Name: '',
    Properties: {
      Type: null,
      Description: null,
      Weight: null,
      Economy: { MaxTT: null }
    },
    RefiningRecipes: []
  };

  // Initialize edit state when entity/user changes
  $: if (user) {
    if (data.isCreateMode) {
      const initialData = existingChange?.data || emptyMaterial;
      initEditState(initialData, 'Material', true, existingChange);
    } else if (material) {
      initEditState(material, 'Material', false, canUsePendingChange ? resolvedPendingChange : null);
    }
  }

  // Handle pending changes from API
  $: if (resolvedPendingChange) {
    setExistingPendingChange(resolvedPendingChange);
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }

  // Active entity - use this everywhere in templates
  $: activeMaterial = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : material;

  // Cleanup on unmount
  onDestroy(() => {
    resetEditState();
  });

  // Build material type options for SearchInput (unique types from loaded materials)
  $: materialTypeOptions = [...new Set(allItems.filter(m => m?.Properties?.Type).map(m => m.Properties.Type))].sort()
    .map(t => ({ label: t, value: t }));

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters - none for materials (simple list)
  const navFilters = [];

  // Full column definitions for materials
  const columnDefs = {
    type: { key: 'type', header: 'Type', width: '90px', filterPlaceholder: 'Ore', getValue: (item) => item.Properties?.Type, format: (v) => v || '-' },
    weight: { key: 'weight', header: 'Weight', width: '60px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Weight, format: (v) => v != null ? clampDecimals(v, 1, 6) : '-' },
    value: { key: 'value', header: 'Value', width: '70px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 2, 8) : '-' }
  };

  // Sidebar table columns for materials
  const navTableColumns = [columnDefs.type];
  const navFullWidthColumns = [columnDefs.type, columnDefs.weight, columnDefs.value];
  const allAvailableColumns = Object.values(columnDefs);

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Materials', href: '/items/materials' },
    ...(activeMaterial?.Name ? [{ label: activeMaterial.Name }] : data.isCreateMode ? [{ label: 'New Material' }] : [])
  ];

  // SEO
  $: seoDescription = activeMaterial?.Properties?.Description ||
    `${activeMaterial?.Name || 'Material'} - crafting material in Entropia Universe.`;

  $: canonicalUrl = activeMaterial?.Name
    ? `https://entropianexus.com/items/materials/${encodeURIComponentSafe(activeMaterial.Name)}`
    : 'https://entropianexus.com/items/materials';

  // SEO Image URL (if entity has an image)
  $: entityImageUrl = material?.Id ? `/api/img/material/${material.Id}` : null;

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    acquisition: true,
    usage: true,
    refining: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-material-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-material-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== VALUE FORMATTERS ==========
  function formatWeight(weight) {
    if (weight == null) return 'N/A';
    return `${clampDecimals(weight, 1, 6)}kg`;
  }

  function formatValue(value) {
    if (value == null) return 'N/A';
    return `${clampDecimals(value, 2, 8)} PED`;
  }
</script>

<WikiSEO
  title={activeMaterial?.Name || 'Materials'}
  description={seoDescription}
  entityType="material"
  entity={activeMaterial}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={activeMaterial}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Materials"
  {breadcrumbs}
  entity={data.isCreateMode ? $currentEntity : (activeMaterial || material)}
  basePath="/items/materials"
  {navItems}
  {navFilters}
  {navTableColumns}
  navAllAvailableColumns={allAvailableColumns}
  navFullWidthColumns={navFullWidthColumns}
  navPageTypeId="materials"
  {user}
  editable={true}
  {canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
  {editDepsLoading}
>
  <!-- Pending change banner -->
  {#if $existingPendingChange && !$editMode && !data.isCreateMode}
    <div class="pending-change-banner" class:viewing={$viewingPendingChange}>
      <div class="banner-content">
        <span class="banner-icon">⏳</span>
        <span class="banner-text">
          {#if $existingPendingChange.state === 'Pending'}
            This material has changes pending review.
          {:else}
            This material has a draft with unsaved changes.
          {/if}
        </span>
        <button
          class="banner-toggle"
          on:click={() => setViewingPendingChange(!$viewingPendingChange)}
        >
          {$viewingPendingChange ? 'View Original' : 'View Changes'}
        </button>
      </div>
    </div>
  {/if}

  {#if activeMaterial || data.isCreateMode}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeMaterial?.Id}
            entityName={activeMaterial?.Name}
            entityType="material"
            {user}
            isEditMode={$editMode}
            isCreateMode={data.isCreateMode}
          />
          <div class="infobox-title">
            {#if $editMode}
              <InlineEdit
                value={activeMaterial?.Name || ''}
                path="Name"
                type="text"
                required={true}
                placeholder="Material Name"
              />
            {:else}
              {activeMaterial?.Name || 'New Material'}
            {/if}
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge">Material</span>
          </div>
        </div>

        <!-- Primary Stats (read-only summary) -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Type</span>
            <span class="stat-value">{activeMaterial?.Properties?.Type || 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Value</span>
            <span class="stat-value">{formatValue(activeMaterial?.Properties?.Economy?.MaxTT)}</span>
          </div>
        </div>

        <!-- Secondary Stats -->
        <div class="stats-section tier-2">
          <h4 class="section-title">Properties</h4>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">
              {#if $editMode}
                <SearchInput
                  value={activeMaterial?.Properties?.Type || ''}
                  options={materialTypeOptions}
                  placeholder="e.g. Ore"
                  on:select={(e) => updateField('Properties.Type', e.detail.value)}
                  on:change={(e) => updateField('Properties.Type', e.detail.value)}
                />
              {:else}
                {activeMaterial?.Properties?.Type || 'N/A'}
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">
              {#if $editMode}
                <InlineEdit
                  value={activeMaterial?.Properties?.Weight}
                  path="Properties.Weight"
                  type="number"
                  min={0}
                  step={0.001}
                  suffix="kg"
                  placeholder="0.00"
                />
              {:else}
                {formatWeight(activeMaterial?.Properties?.Weight)}
              {/if}
            </span>
          </div>
        </div>

        <!-- Economy -->
        <div class="stats-section tier-2">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Value</span>
            <span class="stat-value">
              {#if $editMode}
                <InlineEdit
                  value={activeMaterial?.Properties?.Economy?.MaxTT}
                  path="Properties.Economy.MaxTT"
                  type="number"
                  min={0}
                  step={0.0001}
                  suffix="PED"
                  placeholder="0.00"
                />
              {:else}
                {formatValue(activeMaterial?.Properties?.Economy?.MaxTT)}
              {/if}
            </span>
          </div>
        </div>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          {#if $editMode}
            <InlineEdit
              value={activeMaterial?.Name || ''}
              path="Name"
              type="text"
              required={true}
              placeholder="Material Name"
            />
          {:else}
            {activeMaterial?.Name || 'New Material'}
          {/if}
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeMaterial?.Properties?.Description || ''}
              on:change={(e) => updateField('Properties.Description', e.detail)}
              placeholder="Enter a description for this material..."
            />
          {:else if activeMaterial?.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeMaterial.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeMaterial?.Name || 'This material'} is a material used in crafting and other activities.
            </div>
          {/if}
        </div>

        <!-- Refining Recipes Section (edit mode only) -->
        {#if $editMode}
          <DataSection
            title="Refining Recipes"
            icon=""
            bind:expanded={panelStates.refining}
            subtitle="{activeMaterial?.RefiningRecipes?.length || 0} recipe{(activeMaterial?.RefiningRecipes?.length || 0) !== 1 ? 's' : ''}"
            on:toggle={savePanelStates}
          >
            <RefiningRecipesEditor
              recipes={activeMaterial?.RefiningRecipes || []}
              fieldName="RefiningRecipes"
              materialName={activeMaterial?.Name || ''}
            />
          </DataSection>
        {/if}

        <!-- Acquisition Section -->
        {#if additional.acquisition && !data.isCreateMode}
          <DataSection
            title="Acquisition"
            icon=""
            bind:expanded={panelStates.acquisition}
            on:toggle={savePanelStates}
          >
            <Acquisition acquisition={additional.acquisition} />
          </DataSection>
        {/if}

        <!-- Usage Section -->
        {#if additional.usage && !data.isCreateMode}
          <DataSection
            title="Usage"
            icon=""
            bind:expanded={panelStates.usage}
            on:toggle={savePanelStates}
          >
            <Usage item={activeMaterial} usage={additional.usage} />
          </DataSection>
        {/if}

      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Materials</h2>
      <p>Select a material from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .pending-change-banner {
    background: linear-gradient(135deg, #3d4a5c 0%, #2d3748 100%);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 16px;
  }

  .pending-change-banner.viewing {
    background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
    border-color: var(--accent-color, #4a9eff);
  }

  .banner-content {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .banner-icon {
    font-size: 20px;
  }

  .banner-text {
    flex: 1;
    min-width: 200px;
    color: var(--text-color);
  }

  .banner-toggle {
    padding: 6px 12px;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
  }

  .banner-toggle:hover {
    filter: brightness(1.1);
  }

  @media (min-width: 1400px) {
    .wiki-infobox-float {
      width: 280px;
    }
  }
</style>

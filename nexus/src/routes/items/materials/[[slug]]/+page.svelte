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
  import { onMount, onDestroy, untrack } from 'svelte';
  import { encodeURIComponentSafe, clampDecimals, getLatestPendingUpdate, loadEditDeps } from '$lib/util';
  import { hasVisibleText } from '$lib/sanitize.js';


  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import MarketPriceSection from '$lib/components/wiki/MarketPriceSection.svelte';
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
  let { data = $bindable() } = $props();

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = $state(false);
  $effect(() => {
    if ($editMode && data.availableItems === null && !untrack(() => editDepsLoading)) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'availableItems', url: '/api/items' }
      ]).then(deps => {
        data = { ...data, ...deps };
        editDepsLoading = false;
      });
    }
  });

  let material = $derived(data.object);
  let user = $derived(data.session?.user);
  let allItems = $derived(data.allItems || []);
  let additional = $derived(data.additional || {});
  let pendingChange = $derived(data.pendingChange);
  let existingChange = $derived(data.existingChange);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let availableItems = $derived(data.availableItems || []);
  let materialEntityId = $derived(material?.Id ?? material?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, materialEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));

  // Permission check - verified users can edit
  let canEdit = $derived(user?.verified === true);

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
  $effect(() => {
    if (user) {
      if (data.isCreateMode) {
        const initialData = existingChange?.data || emptyMaterial;
        initEditState(initialData, 'Material', true, existingChange);
      } else if (material) {
        initEditState(material, 'Material', false, canUsePendingChange ? resolvedPendingChange : null);
      }
    }
  });

  // Handle pending changes from API
  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });

  // Active entity - use this everywhere in templates
  let activeMaterial = $derived($editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : material);

  // Cleanup on unmount
  onDestroy(() => {
    resetEditState();
  });

  // Build material type options for SearchInput (unique types from loaded materials)
  let materialTypeOptions = $derived([...new Set(allItems.filter(m => m?.Properties?.Type).map(m => m.Properties.Type))].sort()
    .map(t => ({ label: t, value: t })));

  // Build navigation items
  let navItems = $derived(allItems);

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
  let breadcrumbs = $derived([
    { label: 'Items', href: '/items' },
    { label: 'Materials', href: '/items/materials' },
    ...(activeMaterial?.Name ? [{ label: activeMaterial.Name }] : data.isCreateMode ? [{ label: 'New Material' }] : [])
  ]);

  // SEO
  let seoDescription = $derived(activeMaterial?.Properties?.Description ||
    `${activeMaterial?.Name || 'Material'} - crafting material in Entropia Universe.`);

  let canonicalUrl = $derived(activeMaterial?.Name
    ? `https://entropianexus.com/items/materials/${encodeURIComponentSafe(activeMaterial.Name)}`
    : 'https://entropianexus.com/items/materials');

  // SEO Image URL (if entity has an image)
  let entityImageUrl = $derived(material?.Id ? `/api/img/material/${material.Id}` : null);

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    marketPrices: true,
    acquisition: true,
    usage: true,
    refining: true
  });

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
    <PendingChangeBanner
      pendingChange={$existingPendingChange}
      viewing={$viewingPendingChange}
      onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
      entityLabel="material"
    />
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
            {#if activeMaterial?.Properties?.IsRare}<span class="item-flag-badge rare">Rare</span>{/if}
            {#if activeMaterial?.Properties?.IsUntradeable}<span class="item-flag-badge untradeable">Untradeable</span>{/if}
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
                  onselect={(e) => updateField('Properties.Type', e.value)}
                  onchange={(e) => updateField('Properties.Type', e.value)}
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
          <div class="stat-row">
            <span class="stat-label">Rare</span>
            <span class="stat-value" class:highlight-yes={activeMaterial?.Properties?.IsRare}>
              <InlineEdit value={activeMaterial?.Properties?.IsRare} path="Properties.IsRare" type="checkbox" />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Untradeable</span>
            <span class="stat-value" class:highlight-yes={activeMaterial?.Properties?.IsUntradeable}>
              <InlineEdit value={activeMaterial?.Properties?.IsUntradeable} path="Properties.IsUntradeable" type="checkbox" />
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
              onchange={(data) => updateField('Properties.Description', data)}
              placeholder="Enter a description for this material..."
              showWaypoints={true}
            />
          {:else if hasVisibleText(activeMaterial?.Properties?.Description)}
            <div class="description-content">{@html activeMaterial.Properties.Description}</div>
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
            ontoggle={savePanelStates}
          >
            <RefiningRecipesEditor
              recipes={activeMaterial?.RefiningRecipes || []}
              fieldName="RefiningRecipes"
              materialName={activeMaterial?.Name || ''}
            />
          </DataSection>
        {/if}

        <!-- Market Prices Section -->
        {#if !data.isCreateMode && !activeMaterial?.Properties?.IsUntradeable}
          <MarketPriceSection
            itemId={activeMaterial?.ItemId}
            itemName={activeMaterial?.Name}
            bind:expanded={panelStates.marketPrices}
            ontoggle={savePanelStates}
          />
        {/if}

        <!-- Acquisition Section -->
        {#if additional.acquisition && !data.isCreateMode}
          <DataSection
            title="Acquisition"
            icon=""
            bind:expanded={panelStates.acquisition}
            ontoggle={savePanelStates}
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
            ontoggle={savePanelStates}
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
  @media (min-width: 1400px) {
    .wiki-infobox-float {
      width: 280px;
    }
  }
</style>

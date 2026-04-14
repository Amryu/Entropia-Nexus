<!--
  @component Furnishings Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Handles 4 subtypes: furniture, decorations, storagecontainers, signs
  Supports full wiki editing.

  Legacy editConfig preserved in furnishings-legacy/+page.svelte
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy, untrack } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, getLatestPendingUpdate } from '$lib/util';
  import { hasVisibleText } from '$lib/sanitize.js';


  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import MarketPriceSection from '$lib/components/wiki/MarketPriceSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/wiki/Acquisition.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';
  // Wiki edit state
  import {
    editMode,
    isCreateMode as createModeStore,
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

  let { data } = $props();



  // Local filter state - decoupled from URL
  let selectedFilter = $state(null);
  let filterInitialized = $state(false);




  // Type navigation buttons
  const typeButtons = [
    { label: 'Furniture', title: 'Furniture', type: 'furniture' },
    { label: 'Decor', title: 'Decorations', type: 'decorations' },
    { label: 'Storage', title: 'Storage Containers', type: 'storagecontainers' },
    { label: 'Signs', title: 'Signs', type: 'signs' }
  ];

  // Type name mapping
  function getTypeName(type) {
    switch (type) {
      case 'furniture': return 'Furniture';
      case 'decorations': return 'Decoration';
      case 'storagecontainers': return 'Storage Container';
      case 'signs': return 'Sign';
      default: return 'Furnishing';
    }
  }

  // Entity type for editing
  function getEntityType(type) {
    switch (type) {
      case 'furniture': return 'Furniture';
      case 'decorations': return 'Decoration';
      case 'storagecontainers': return 'StorageContainer';
      case 'signs': return 'Sign';
      default: return null;
    }
  }

  // Get empty entity template based on type
  function getEmptyEntity(type) {
    const base = {
      Name: '',
      Properties: {
        Description: '',
        Weight: 0,
        Economy: {
          MaxTT: 0,
          MinTT: 0
        }
      }
    };

    switch (type) {
      case 'furniture':
      case 'decorations':
        base.Properties.Type = '';
        break;
      case 'storagecontainers':
        base.Properties.ItemCapacity = 0;
        base.Properties.WeightCapacity = 0;
        break;
      case 'signs':
        base.Properties.ItemPoints = 0;
        base.Properties.Economy.Cost = 0;
        base.Properties.Display = {
          AspectRatio: '16:9',
          CanShowLocalContent: false,
          CanShowImagesAndText: false,
          CanShowEffects: false,
          CanShowMultimedia: false,
          CanShowParticipantContent: false
        };
        break;
    }
    return base;
  }




  // Helper to apply pending changes to entity for display
  function applyChangesToEntity(entity, changes) {
    if (!entity || !changes) return entity;
    const result = JSON.parse(JSON.stringify(entity));
    for (const [path, value] of Object.entries(changes)) {
      setNestedValue(result, path, value);
    }
    return result;
  }

  function setNestedValue(obj, path, value) {
    const keys = path.split('.');
    let current = obj;
    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) current[keys[i]] = {};
      current = current[keys[i]];
    }
    current[keys[keys.length - 1]] = value;
  }

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });



  // Full column definitions for furnishings
  const columnDefs = {
    cat: { key: 'cat', header: 'Cat', width: '60px', filterPlaceholder: 'Furn', getValue: (item) => getTypeName(item._type || additional.type).slice(0, 6), format: (v) => v || '-' },
    type: { key: 'type', header: 'Type', width: '60px', filterPlaceholder: 'Chair', getValue: (item) => item.Properties?.Type, format: (v) => v ? v.slice(0, 6) : '-' },
    tt: { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' },
    minTT: { key: 'minTT', header: 'Min TT', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Economy?.MinTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' },
    weight: { key: 'weight', header: 'Weight', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Weight, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' },
    cap: { key: 'cap', header: 'Items', width: '55px', filterPlaceholder: '>50', getValue: (item) => item.Properties?.ItemCapacity, format: (v) => v ?? '-' },
    weightCap: { key: 'weightCap', header: 'Wt. Cap.', width: '60px', filterPlaceholder: '>100', getValue: (item) => item.Properties?.WeightCapacity, format: (v) => v != null ? clampDecimals(v, 0, 1) : '-' },
    ratio: { key: 'ratio', header: 'Ratio', width: '55px', filterPlaceholder: '16:9', getValue: (item) => item.Properties?.Display?.AspectRatio, format: (v) => v || '-' },
    itemPoints: { key: 'itemPoints', header: 'Points', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.ItemPoints, format: (v) => v != null ? v : '-' },
    cost: { key: 'cost', header: 'Cost', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Economy?.Cost, format: (v) => v != null ? clampDecimals(v, 2, 2) : '-' }
  };

  // Type-specific sidebar table columns
  function getNavTableColumns(type) {
    switch (type) {
      case 'furniture':
      case 'decorations':
        return [columnDefs.type, columnDefs.tt];
      case 'storagecontainers':
        return [columnDefs.cap, columnDefs.tt];
      case 'signs':
        return [columnDefs.ratio, columnDefs.tt];
      default:
        return [columnDefs.cat, columnDefs.tt];
    }
  }

  function getNavFullWidthColumns(type) {
    switch (type) {
      case 'furniture':
      case 'decorations':
        return [columnDefs.type, columnDefs.tt, columnDefs.minTT, columnDefs.weight];
      case 'storagecontainers':
        return [columnDefs.cap, columnDefs.weightCap, columnDefs.tt, columnDefs.minTT, columnDefs.weight];
      case 'signs':
        return [columnDefs.ratio, columnDefs.itemPoints, columnDefs.tt, columnDefs.minTT, columnDefs.cost, columnDefs.weight];
      default:
        return [columnDefs.cat, columnDefs.tt, columnDefs.weight];
    }
  }

  const allAvailableColumns = Object.values(columnDefs);

  // Custom href generator for items
  function getItemHref(item, basePath) {
    const type = item._type || selectedFilter || additional.type;
    if (type) {
      return `/items/furnishings/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }








  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    marketPrices: true,
    acquisition: true
  });

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-furnishing-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-furnishing-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }
  let furnishing = $derived(data.object);
  let user = $derived(data.session?.user);
  let additional = $derived(data.additional || {});
  let pendingChange = $derived(data.pendingChange);
  let existingChange = $derived(data.existingChange);
  let isCreateMode = $derived(data.isCreateMode || false);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  $effect(() => {
    if (!untrack(() => filterInitialized)) {
      selectedFilter = additional.type || null;
      filterInitialized = true;
    }
  });
  $effect(() => {
    if (filterInitialized && !furnishing && !isCreateMode) {
      if ((additional.type || null) !== untrack(() => selectedFilter)) {
        selectedFilter = additional.type || null;
      }
    }
  });
  let furnishingEntityId = $derived(furnishing?.Id ?? furnishing?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, furnishingEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));
  // Can edit if user is verified or admin
  let canEdit = $derived(user?.verified || user?.grants?.includes('wiki.edit'));
  // For multi-type pages, data.items is an object keyed by type
  let allItems = $derived((() => {
    if (!data.items) return [];
    if (selectedFilter && data.items[selectedFilter]) {
      return data.items[selectedFilter];
    }
    // No filter selected - combine all items from all types
    const combined = [];
    for (const [type, items] of Object.entries(data.items)) {
      for (const item of items) {
        combined.push({ ...item, _type: type });
      }
    }
    return combined;
  })());
  // Initialize edit state when entity or user changes
  $effect(() => {
    if (user && additional.type) {
      const entityType = getEntityType(additional.type);
      const entity = isCreateMode ? (existingChange?.data || getEmptyEntity(additional.type)) : furnishing;
      if (entity && entityType) {
        const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
        initEditState(entity, entityType, isCreateMode, editChange);
      }
    }
  });
  // Set existing pending change when data loads
  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });
  // Active entity: what we display (edit mode → currentEntity, pending view → pending data, default → furnishing)
  let activeEntity = $derived($editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.changes)
      ? applyChangesToEntity(furnishing, $existingPendingChange.changes)
      : furnishing);
  // Build navigation items
  let navItems = $derived(allItems);
  // Navigation filters - uses selectedFilter for active state (local, not URL-based)
  let navFilters = $derived(typeButtons.map(btn => ({
    label: btn.label,
    title: btn.title,
    type: btn.type,
    active: selectedFilter === btn.type,
    href: selectedFilter === btn.type ? '/items/furnishings' : `/items/furnishings/${btn.type}`
  })));
  let navTableColumns = $derived(getNavTableColumns(selectedFilter));
  let navFullWidthColumns = $derived(getNavFullWidthColumns(selectedFilter));
  let navPageTypeId = $derived(`furnishings-${selectedFilter || 'all'}`);
  // Base path for navigation - uses selectedFilter so it persists
  let effectiveBasePath = $derived(selectedFilter
    ? `/items/furnishings/${selectedFilter}`
    : '/items/furnishings');
  // Create categories for the "New" dropdown
  let createCategories = $derived(typeButtons.map(btn => ({
    label: getTypeName(btn.type),
    href: `/items/furnishings/${btn.type}`
  })));
  // Filter pending creates by selected filter type
  let filteredPendingCreates = $derived(selectedFilter
    ? (userPendingCreates || []).filter(change => {
        const entityType = getEntityType(selectedFilter);
        return change.entity === entityType;
      })
    : userPendingCreates || []);
  // Breadcrumbs
  let breadcrumbs = $derived([
    { label: 'Items', href: '/items' },
    { label: 'Furnishings', href: '/items/furnishings' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + (additional.type !== 'furniture' ? 's' : ''), href: `/items/furnishings/${additional.type}` }] : []),
    ...(activeEntity ? [{ label: activeEntity.Name || 'New ' + getTypeName(additional.type) }] : [])
  ]);
  // SEO
  let seoDescription = $derived(activeEntity?.Properties?.Description ||
    `${activeEntity?.Name || 'Furnishing'} - ${getTypeName(additional.type)} in Entropia Universe.`);
  let canonicalUrl = $derived(furnishing
    ? `https://entropianexus.com/items/furnishings/${additional.type}/${encodeURIComponentSafe(furnishing.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/furnishings/${additional.type}`
    : 'https://entropianexus.com/items/furnishings');
  // Image URL for SEO
  let entityImageUrl = $derived(furnishing?.Id && additional.type
    ? `/api/img/${getEntityType(additional.type).toLowerCase()}/${furnishing.Id}`
    : null);
</script>

<WikiSEO
  title={activeEntity?.Name || `${getTypeName(additional.type)}s`}
  description={seoDescription}
  entityType={getEntityType(additional.type)}
  entity={activeEntity}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={activeEntity}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Furnishings"
  {breadcrumbs}
  entity={activeEntity}
  basePath={effectiveBasePath}
  {navItems}
  {navFilters}
  {navTableColumns}
  navAllAvailableColumns={allAvailableColumns}
  navFullWidthColumns={navFullWidthColumns}
  navPageTypeId={navPageTypeId}
  navGetItemHref={getItemHref}
  {user}
  editable={true}
  canEdit={canEdit}
  {createCategories}
  {canCreateNew}
  userPendingCreates={filteredPendingCreates}
  {userPendingUpdates}
>
  {#if activeEntity || isCreateMode}
    <!-- Pending Change Banner -->
    {#if $existingPendingChange && !$editMode}
      <PendingChangeBanner
        pendingChange={$existingPendingChange}
        viewing={$viewingPendingChange}
        onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
        entityLabel="furnishing"
      />
    {/if}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeEntity?.Id}
            entityName={activeEntity?.Name}
            entityType={getEntityType(additional.type).toLowerCase()}
            {user}
            isEditMode={$editMode}
            {isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              value={activeEntity?.Name}
              path="Name"
              type="text"
              placeholder="{getTypeName(additional.type)} Name"
            />
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge">{getTypeName(additional.type)}</span>
            {#if activeEntity?.Properties?.IsRare}<span class="item-flag-badge rare">Rare</span>{/if}
            {#if activeEntity?.Properties?.IsUntradeable}<span class="item-flag-badge untradeable">Untradeable</span>{/if}
          </div>
        </div>

        <!-- Tier-1 Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">TT Value</span>
            <span class="stat-value">
              {activeEntity?.Properties?.Economy?.MaxTT != null ? `${activeEntity.Properties.Economy.MaxTT.toFixed(2)} PED` : 'N/A'}
            </span>
          </div>

          {#if additional.type === 'storagecontainers'}
            <div class="stat-row primary">
              <span class="stat-label">Item Capacity</span>
              <span class="stat-value">{activeEntity?.Properties?.ItemCapacity ?? 'N/A'}</span>
            </div>
          {:else if additional.type === 'signs'}
            <div class="stat-row primary">
              <span class="stat-label">Aspect Ratio</span>
              <span class="stat-value">{activeEntity?.Properties?.Display?.AspectRatio ?? 'N/A'}</span>
            </div>
          {:else if activeEntity?.Properties?.Type || $editMode}
            <div class="stat-row primary">
              <span class="stat-label">Type</span>
              <span class="stat-value">{activeEntity?.Properties?.Type ?? 'N/A'}</span>
            </div>
          {/if}
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Weight}
                path="Properties.Weight"
                type="number"
                min={0}
                step={0.1}
                suffix=" kg"
              />
            </span>
          </div>
          {#if (additional.type === 'furniture' || additional.type === 'decorations') && (activeEntity?.Properties?.Type || $editMode)}
            <div class="stat-row">
              <span class="stat-label">Type</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Type}
                  path="Properties.Type"
                  type="text"
                />
              </span>
            </div>
          {/if}
          {#if additional.type === 'signs'}
            <div class="stat-row">
              <span class="stat-label">Item Points</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.ItemPoints}
                  path="Properties.ItemPoints"
                  type="number"
                  min={0}
                />
              </span>
            </div>
          {/if}
          {#if additional.type === 'storagecontainers'}
            <div class="stat-row">
              <span class="stat-label">Item Capacity</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.ItemCapacity}
                  path="Properties.ItemCapacity"
                  type="number"
                  min={0}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Weight Capacity</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.WeightCapacity}
                  path="Properties.WeightCapacity"
                  type="number"
                  min={0}
                  step={0.1}
                />
              </span>
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Rare</span>
            <span class="stat-value" class:highlight-yes={activeEntity?.Properties?.IsRare}>
              <InlineEdit value={activeEntity?.Properties?.IsRare} path="Properties.IsRare" type="checkbox" />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Untradeable</span>
            <span class="stat-value" class:highlight-yes={activeEntity?.Properties?.IsUntradeable}>
              <InlineEdit value={activeEntity?.Properties?.IsUntradeable} path="Properties.IsUntradeable" type="checkbox" />
            </span>
          </div>
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max. TT</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Economy?.MaxTT}
                path="Properties.Economy.MaxTT"
                type="number"
                min={0}
                step={0.01}
                suffix=" PED"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min. TT</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Economy?.MinTT}
                path="Properties.Economy.MinTT"
                type="number"
                min={0}
                step={0.01}
                suffix=" PED"
              />
            </span>
          </div>
          {#if additional.type === 'signs'}
            <div class="stat-row">
              <span class="stat-label">Cost</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Economy?.Cost}
                  path="Properties.Economy.Cost"
                  type="number"
                  min={0}
                  step={0.01}
                />
              </span>
            </div>
          {/if}
        </div>

        <!-- Display Stats (signs only) -->
        {#if additional.type === 'signs'}
          <div class="stats-section">
            <h4 class="section-title">Display</h4>
            <div class="stat-row">
              <span class="stat-label">Aspect Ratio</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Display?.AspectRatio}
                  path="Properties.Display.AspectRatio"
                  type="text"
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Local Content</span>
              <span class="stat-value feature-flag" class:yes={activeEntity?.Properties?.Display?.CanShowLocalContent}>
                <InlineEdit
                  value={activeEntity?.Properties?.Display?.CanShowLocalContent}
                  path="Properties.Display.CanShowLocalContent"
                  type="checkbox"
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Images & Text</span>
              <span class="stat-value feature-flag" class:yes={activeEntity?.Properties?.Display?.CanShowImagesAndText}>
                <InlineEdit
                  value={activeEntity?.Properties?.Display?.CanShowImagesAndText}
                  path="Properties.Display.CanShowImagesAndText"
                  type="checkbox"
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Effects</span>
              <span class="stat-value feature-flag" class:yes={activeEntity?.Properties?.Display?.CanShowEffects}>
                <InlineEdit
                  value={activeEntity?.Properties?.Display?.CanShowEffects}
                  path="Properties.Display.CanShowEffects"
                  type="checkbox"
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Multimedia</span>
              <span class="stat-value feature-flag" class:yes={activeEntity?.Properties?.Display?.CanShowMultimedia}>
                <InlineEdit
                  value={activeEntity?.Properties?.Display?.CanShowMultimedia}
                  path="Properties.Display.CanShowMultimedia"
                  type="checkbox"
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Participant Content</span>
              <span class="stat-value feature-flag" class:yes={activeEntity?.Properties?.Display?.CanShowParticipantContent}>
                <InlineEdit
                  value={activeEntity?.Properties?.Display?.CanShowParticipantContent}
                  path="Properties.Display.CanShowParticipantContent"
                  type="checkbox"
                />
              </span>
            </div>
          </div>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            value={activeEntity?.Name}
            path="Name"
            type="text"
            placeholder="{getTypeName(additional.type)} Name"
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeEntity?.Properties?.Description || ''}
              onchange={(data) => updateField('Properties.Description', data)}
              placeholder="Enter {getTypeName(additional.type).toLowerCase()} description..."
              showWaypoints={true}
            />
          {:else if hasVisibleText(activeEntity?.Properties?.Description)}
            <div class="description-content">{@html activeEntity.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || 'This ' + getTypeName(additional.type).toLowerCase()} is a {getTypeName(additional.type).toLowerCase()} in Entropia Universe.
            </div>
          {/if}
        </div>
        <!-- Market Prices Section -->
        {#if !activeEntity?.Properties?.IsUntradeable}
        <MarketPriceSection
          itemId={activeEntity?.ItemId}
          itemName={activeEntity?.Name}
          bind:expanded={panelStates.marketPrices}
          ontoggle={savePanelStates}
        />
        {/if}

        <!-- Acquisition Section -->
        {#if additional.acquisition}
          <DataSection
            title="Acquisition"
            icon=""
            bind:expanded={panelStates.acquisition}
            ontoggle={savePanelStates}
          >
            <Acquisition acquisition={additional.acquisition} />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>{additional.type ? getTypeName(additional.type) + (additional.type !== 'furniture' ? 's' : '') : 'Furnishings'}</h2>
      <p>Select a {additional.type ? getTypeName(additional.type).toLowerCase() : 'furnishing'} from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  /* Furnishing-specific: feature flag styling for sign display capabilities */
  .stat-value.feature-flag {
    color: var(--text-muted, #999);
  }

  .stat-value.feature-flag.yes {
    color: #4ade80;
    font-weight: 600;
  }
</style>

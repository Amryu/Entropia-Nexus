<!--
  @component Blueprint Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Supports full wiki editing.
  Infobox: Level, Type, Book, Cost, Boosted, SiB, Profession, PED/h
  Article: Description, Construction (with markup calculator), Acquisition

  Legacy editConfig preserved for reference (see blueprints-legacy for full version):
  {
    constructor: () => ({
      Name: null,
      Properties: {
        Description: null, Type: null, Level: null, IsBoosted: false,
        MinimumCraftAmount: null, MaximumCraftAmount: null,
        Skill: { IsSiB: true, LearningIntervalStart: null, LearningIntervalEnd: null }
      },
      Book: { Name: null },
      Profession: { Name: null },
      Product: { Name: null },
      Materials: [],
      Drops: []
    }),
    dependencies: ['items', 'materials', 'blueprintbooks', 'professions', 'blueprints'],
    controls: [General group, Skill group, Materials list, Drops list]
  }
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { encodeURIComponentSafe, clampDecimals, getTypeLink, getItemLink, getLatestPendingUpdate, hasItemTag } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';

  // Blueprint-specific component
  import BlueprintMaterials from '$lib/components/wiki/BlueprintMaterials.svelte';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/wiki/Acquisition.svelte';

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

  export let data;

  const craftDuration = 5; // seconds per craft cycle

  $: blueprint = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: additional = data.additional || {};
  $: pendingChange = data.pendingChange;
  $: existingChange = data.existingChange;
  $: isCreateMode = data.isCreateMode || false;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];

  $: userPendingUpdates = data.userPendingUpdates || [];
  $: blueprintEntityId = blueprint?.Id ?? blueprint?.ItemId;
  $: userPendingUpdate = getLatestPendingUpdate(userPendingUpdates, blueprintEntityId);
  $: resolvedPendingChange = userPendingUpdate || pendingChange;
  $: canUsePendingChange = !!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve')));
  // Edit mode dropdown data
  $: blueprintbooks = data.blueprintbooks || [];
  $: professions = data.professions || [];
  $: productItems = data.productItems || [];
  $: materials = data.materials || [];

  // Options for SearchInput dropdowns
  $: bookOptions = blueprintbooks.map(b => ({ value: b.Name, label: b.Name })).sort((a, b) => a.label.localeCompare(b.label));
  $: professionOptions = professions.map(p => ({ value: p.Name, label: p.Name })).sort((a, b) => a.label.localeCompare(b.label));
  $: productOptions = productItems.map(i => ({ value: i.Name, label: i.Name })).sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
  // For Drops, use all blueprints (allItems)
  $: blueprintDropOptions = allItems.map(b => ({ value: b.Name, label: b.Name })).sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));

  // Can edit if user is verified or admin
  $: canEdit = user?.verified || user?.grants?.includes('wiki.edit');

  // Build navigation items
  $: navItems = allItems;

  // Empty entity template for create mode
  const emptyEntity = {
    Name: '',
    Properties: {
      Description: '',
      Type: 'Weapon',
      Level: 1,
      IsBoosted: false,
      MinimumCraftAmount: 1,
      MaximumCraftAmount: 1,
      Skill: {
        IsSiB: true,
        LearningIntervalStart: 0,
        LearningIntervalEnd: 100
      }
    },
    Book: null,
    Profession: null,
    Product: null,
    Materials: [],
    Drops: []
  };

  // Initialize edit state when entity or user changes
  $: if (user) {
    const entity = isCreateMode ? (existingChange?.data || emptyEntity) : blueprint;
    if (entity) {
      const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
      initEditState(entity, 'Blueprint', isCreateMode, editChange);
    }
  }

  // Set existing pending change when data loads
  $: if (resolvedPendingChange) {
    setExistingPendingChange(resolvedPendingChange);
    // Auto-enable viewing pending change for author or admin
    if (user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))) {
      setViewingPendingChange(true);
    }
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }

  // Active entity: what we display (edit mode → currentEntity, pending view → pending data, default → blueprint)
  $: activeEntity = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.changes)
      ? applyChangesToEntity(blueprint, $existingPendingChange.changes)
      : blueprint;

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

  // Navigation filters
  const navFilters = [
    {
      key: 'Properties.Type',
      label: 'Type',
      values: [
        { value: 'Weapon', label: 'Weapon' },
        { value: 'Armor', label: 'Armor' },
        { value: 'Tool', label: 'Tool' },
        { value: 'Vehicle', label: 'Vehicle' },
        { value: 'Textile', label: 'Textile' },
        { value: 'Furniture', label: 'Furniture' },
        { value: 'Attachment', label: 'Attachment' },
        { value: 'Enhancer', label: 'Enhancer' },
      ]
    }
  ];

  // Blueprint type options for editing
  const typeOptions = [
    { value: 'Weapon', label: 'Weapon' },
    { value: 'Armor', label: 'Armor' },
    { value: 'Tool', label: 'Tool' },
    { value: 'Vehicle', label: 'Vehicle' },
    { value: 'Textile', label: 'Textile' },
    { value: 'Furniture', label: 'Furniture' },
    { value: 'Attachment', label: 'Attachment' },
    { value: 'Enhancer', label: 'Enhancer' }
  ];

  // Sidebar table columns for blueprints
  const bpColumnDefs = {
    type: {
      key: 'type',
      header: 'Type',
      width: '80px',
      filterPlaceholder: 'Weapon',
      getValue: (item) => item.Properties?.Type,
      format: (v) => v || '-'
    },
    profession: {
      key: 'profession',
      header: 'Profession',
      width: '95px',
      filterPlaceholder: 'Weapons',
      getValue: (item) => item.Profession?.Name,
      format: (v) => v || '-'
    },
    level: {
      key: 'level',
      header: 'Level',
      width: '65px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Level,
      format: (v) => v != null ? v : '-'
    },
    product: {
      key: 'product',
      header: 'Product',
      width: '120px',
      filterPlaceholder: 'Item name',
      getValue: (item) => item.Product?.Name,
      format: (v) => v || '-'
    },
    sib: {
      key: 'sib',
      header: 'SiB',
      width: '45px',
      filterPlaceholder: 'Yes',
      getValue: (item) => item.Properties?.Skill?.IsSiB ? 1 : 0,
      format: (v) => v ? 'Yes' : 'No'
    },
    limited: {
      key: 'limited',
      header: 'Ltd',
      width: '45px',
      filterPlaceholder: 'Yes',
      getValue: (item) => hasItemTag(item.Name, 'L') ? 1 : 0,
      format: (v) => v ? 'Yes' : 'No'
    },
    book: {
      key: 'book',
      header: 'Book',
      width: '100px',
      filterPlaceholder: 'Book name',
      getValue: (item) => item.Book?.Name,
      format: (v) => v || '-'
    },
    boosted: {
      key: 'boosted',
      header: 'Boost',
      width: '50px',
      filterPlaceholder: 'Yes',
      getValue: (item) => item.Properties?.IsBoosted ? 1 : 0,
      format: (v) => v ? 'Yes' : 'No'
    }
  };

  const navTableColumns = [
    bpColumnDefs.type,
    bpColumnDefs.profession,
    bpColumnDefs.level
  ];

  // Full-width table columns (superset of navTableColumns)
  const navFullWidthColumns = [
    ...navTableColumns,
    bpColumnDefs.product,
    bpColumnDefs.sib,
    bpColumnDefs.limited,
    bpColumnDefs.book,
    bpColumnDefs.boosted
  ];

  const allAvailableColumns = Object.values(bpColumnDefs);

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Blueprints', href: '/items/blueprints' },
    ...(activeEntity ? [{ label: activeEntity.Name || 'New Blueprint' }] : [])
  ];

  // SEO
  $: seoDescription = activeEntity?.Properties?.Description ||
    `${activeEntity?.Name || 'Blueprint'} - Level ${activeEntity?.Properties?.Level || '?'} ${activeEntity?.Properties?.Type || ''} blueprint in Entropia Universe.`;

  $: canonicalUrl = blueprint
    ? `https://entropianexus.com/items/blueprints/${encodeURIComponentSafe(blueprint.Name)}`
    : 'https://entropianexus.com/items/blueprints';

  // Image URL for SEO
  $: entityImageUrl = blueprint?.Id ? `/api/img/blueprint/${blueprint.Id}` : null;

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    construction: true,
    acquisition: true,
    drops: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-blueprint-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-blueprint-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== CALCULATOR FUNCTIONS ==========
  function getCost(bp) {
    if (!bp?.Materials?.length) return null;
    return bp.Materials.reduce((acc, mat) => {
      const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
      return acc + (matTT * (mat.Amount || 0));
    }, 0);
  }

  function getCyclePerHour(bp) {
    const cost = getCost(bp);
    if (cost === null || cost === 0) return null;
    return (3600 / craftDuration) * cost;
  }

  // Reactive calculations
  $: cost = getCost(activeEntity);
  $: cyclePerHour = getCyclePerHour(activeEntity);

  // ========== EDIT MODE HANDLERS ==========
  function handleBookChange(e) {
    updateField('Book.Name', e.detail.value);
  }

  function handleBookSelect(e) {
    updateField('Book.Name', e.detail.value || '');
  }

  function handleProductInput(e) {
    updateField('Product.Name', e.detail.value);
  }

  function handleProductSelect(e) {
    const selected = e.detail?.data;
    if (selected) {
      updateField('Product', selected);
    } else {
      updateField('Product.Name', e.detail?.value || '');
    }
  }

  // Drops array handlers
  function addDrop() {
    const currentDrops = activeEntity?.Drops || [];
    const newDrop = { Name: blueprintDropOptions[0]?.value || '' };
    updateField('Drops', [...currentDrops, newDrop]);
  }

  function updateDrop(index, name) {
    const currentDrops = [...(activeEntity?.Drops || [])];
    currentDrops[index] = { Name: name };
    updateField('Drops', currentDrops);
  }

  function removeDrop(index) {
    const currentDrops = [...(activeEntity?.Drops || [])];
    currentDrops.splice(index, 1);
    updateField('Drops', currentDrops);
  }
</script>

<WikiSEO
  title={activeEntity?.Name || 'Blueprints'}
  description={seoDescription}
  entityType="Blueprint"
  entity={activeEntity}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={activeEntity}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Blueprints"
  {breadcrumbs}
  entity={activeEntity}
  basePath="/items/blueprints"
  {navItems}
  {navFilters}
  {navTableColumns}
  {navFullWidthColumns}
  navAllAvailableColumns={allAvailableColumns}
  navPageTypeId="blueprints"
  {user}
  editable={true}
  {canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
>
  {#if activeEntity || isCreateMode}
    <!-- Pending Change Banner -->
    {#if $existingPendingChange && !$editMode}
      <PendingChangeBanner
        pendingChange={$existingPendingChange}
        viewing={$viewingPendingChange}
        onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
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
            entityType="blueprint"
            {user}
            isEditMode={$editMode}
            {isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              value={activeEntity?.Name}
              path="Name"
              type="text"
              placeholder="Blueprint Name"
            />
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge">{activeEntity?.Properties?.Type || 'Blueprint'}</span>
            <span>Level {activeEntity?.Properties?.Level ?? '?'}</span>
          </div>
        </div>

        <!-- Primary Stats -->
        <div class="stats-section tier-1 tier-brown">
          <div class="stat-row primary">
            <span class="stat-label">Cost</span>
            <span class="stat-value">{cost !== null ? `${cost.toFixed(2)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Product</span>
            <span class="stat-value">
              {#if activeEntity?.Product?.Name}
                <a href={getItemLink(activeEntity.Product)} class="tier1-link">{activeEntity.Product.Name}</a>
              {:else}
                N/A
              {/if}
            </span>
          </div>
        </div>

        <!-- General Info -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">0.1kg</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Level</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Level}
                path="Properties.Level"
                type="number"
                min={1}
                max={100}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Type}
                path="Properties.Type"
                type="select"
                options={typeOptions}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Book</span>
            <span class="stat-value">
              {#if $editMode}
                <SearchInput
                  value={activeEntity?.Book?.Name || ''}
                  placeholder="Search book..."
                  options={bookOptions}
                  validValues={blueprintbooks.map(b => b.Name)}
                  on:change={handleBookChange}
                  on:select={handleBookSelect}
                />
              {:else}
                {activeEntity?.Book?.Name ?? 'N/A'}
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Product</span>
            <span class="stat-value">
              {#if $editMode}
                <SearchInput
                  value={activeEntity?.Product?.Name || ''}
                  placeholder="Search product..."
                  options={productOptions}
                  validValues={productItems.map(i => i.Name)}
                  on:change={handleProductInput}
                  on:select={handleProductSelect}
                />
              {:else if activeEntity?.Product?.Name}
                <a href={getItemLink(activeEntity.Product)} class="item-link">{activeEntity.Product.Name}</a>
              {:else}
                N/A
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Amount</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.MinimumCraftAmount}
                path="Properties.MinimumCraftAmount"
                type="number"
                min={1}
              />
              -
              <InlineEdit
                value={activeEntity?.Properties?.MaximumCraftAmount}
                path="Properties.MaximumCraftAmount"
                type="number"
                min={1}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Boosted</span>
            <span class="stat-value" class:highlight-yes={activeEntity?.Properties?.IsBoosted}>
              <InlineEdit
                value={activeEntity?.Properties?.IsBoosted}
                path="Properties.IsBoosted"
                type="checkbox"
              />
            </span>
          </div>
        </div>

        <!-- Skill Info -->
        <div class="stats-section">
          <h4 class="section-title">Skill</h4>
          <div class="stat-row">
            <span class="stat-label">SiB</span>
            <span class="stat-value" class:highlight-yes={activeEntity?.Properties?.Skill?.IsSiB}>
              <InlineEdit
                value={activeEntity?.Properties?.Skill?.IsSiB}
                path="Properties.Skill.IsSiB"
                type="checkbox"
              />
            </span>
          </div>
          {#if activeEntity?.Profession?.Name || $editMode}
            <div class="stat-row">
              <span class="stat-label">Profession</span>
              <span class="stat-value">
                {#if $editMode}
                  <InlineEdit
                    value={activeEntity?.Profession?.Name || ''}
                    path="Profession.Name"
                    type="select"
                    placeholder="Select profession..."
                    options={professionOptions}
                  />
                {:else if activeEntity?.Profession?.Name}
                  <a href={getTypeLink(activeEntity.Profession.Name, 'Profession')} class="profession-link">{activeEntity.Profession.Name}</a>
                {:else}
                  N/A
                {/if}
              </span>
            </div>
            <div class="stat-row indent">
              <span class="stat-label">Level Range</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Skill?.LearningIntervalStart}
                  path="Properties.Skill.LearningIntervalStart"
                  type="number"
                  min={0}
                />
                -
                <InlineEdit
                  value={activeEntity?.Properties?.Skill?.LearningIntervalEnd}
                  path="Properties.Skill.LearningIntervalEnd"
                  type="number"
                  min={0}
                />
              </span>
            </div>
          {/if}
        </div>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            value={activeEntity?.Name}
            path="Name"
            type="text"
            placeholder="Blueprint Name"
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeEntity?.Properties?.Description || ''}
              on:change={(e) => updateField('Properties.Description', e.detail)}
              placeholder="Enter blueprint description..."
            />
          {:else if activeEntity?.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeEntity.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || 'This blueprint'} is a level {activeEntity?.Properties?.Level ?? '?'} {activeEntity?.Properties?.Type?.toLowerCase() || ''} blueprint.
            </div>
          {/if}
        </div>

        <!-- Construction Section -->
        {#if activeEntity?.Materials?.length > 0 || $editMode}
          <DataSection
            title="Construction"
            icon=""
            bind:expanded={panelStates.construction}
            subtitle="{activeEntity?.Materials?.length || 0} materials"
            on:toggle={savePanelStates}
          >
            <BlueprintMaterials blueprint={activeEntity} availableMaterials={materials} />
          </DataSection>
        {/if}

        <!-- Acquisition Section -->
        {#if additional.acquisition}
          <DataSection
            title="Acquisition"
            icon=""
            bind:expanded={panelStates.acquisition}
            on:toggle={savePanelStates}
          >
            <Acquisition acquisition={additional.acquisition} />
          </DataSection>
        {/if}

        <!-- Drops Section (blueprints that can drop from crafting this) -->
        {#if (activeEntity?.Drops?.length > 0) || $editMode}
          <DataSection
            title="Drops"
            icon=""
            bind:expanded={panelStates.drops}
            subtitle="{activeEntity?.Drops?.length || 0} blueprints"
            on:toggle={savePanelStates}
          >
            {#if $editMode}
              <div class="drops-edit-list">
                {#each activeEntity?.Drops || [] as drop, i}
                  <div class="drop-edit-row">
                    <SearchInput
                      value={drop.Name || ''}
                      options={blueprintDropOptions}
                      placeholder="Select blueprint..."
                      on:select={(e) => updateDrop(i, e.detail.value)}
                    />
                    <button class="btn-remove" on:click={() => removeDrop(i)} title="Remove drop">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </div>
                {/each}
                <button class="btn-add" on:click={addDrop}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                  Add Drop
                </button>
              </div>
            {:else}
              <div class="drops-list">
                {#each activeEntity?.Drops || [] as drop}
                  <a href="/items/blueprints/{encodeURIComponentSafe(drop.Name)}" class="drop-link">
                    {drop.Name}
                  </a>
                {/each}
              </div>
            {/if}
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Blueprints</h2>
      <p>Select a blueprint from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .stats-section.tier-1 .tier1-link {
    color: #f4e8e8;
    text-decoration: none;
    font-size: 14px;
    font-weight: 600;
  }

  .stats-section.tier-1 .tier1-link:hover {
    text-decoration: underline;
  }

  .stat-value {
    text-align: right;
  }

  .stat-value :global(.inline-edit .edit-select) {
    min-width: 160px;
  }

  .item-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .item-link:hover {
    text-decoration: underline;
  }

  /* Drops section styles */
  .drops-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .drop-link {
    display: block;
    padding: 10px 14px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
    font-size: 14px;
    transition: background-color 0.15s;
  }

  .drop-link:hover {
    background-color: var(--hover-color);
    text-decoration: underline;
  }

  .drops-edit-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .drop-edit-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  .drop-edit-row :global(.searchable-select) {
    flex: 1;
  }

  .btn-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--error-color, #ff6b6b);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-remove:hover {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-add {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 14px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 6px;
    color: var(--text-muted, #999);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-add:hover {
    background-color: var(--hover-color);
    color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
  }
</style>

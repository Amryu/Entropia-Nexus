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
  import { encodeURIComponentSafe, clampDecimals, getTypeLink, getItemLink } from '$lib/util';
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
  import SearchableSelect from '$lib/components/wiki/SearchableSelect.svelte';
  import ItemSearchInput from '$lib/components/wiki/ItemSearchInput.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/Acquisition.svelte';

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
  // Edit mode dropdown data
  $: blueprintbooks = data.blueprintbooks || [];
  $: professions = data.professions || [];
  $: productItems = data.productItems || [];
  $: materials = data.materials || [];

  // Options for SearchableSelect dropdowns
  $: bookOptions = blueprintbooks.map(b => ({ value: b.Name, label: b.Name })).sort((a, b) => a.label.localeCompare(b.label));
  $: professionOptions = professions.map(p => ({ value: p.Name, label: p.Name })).sort((a, b) => a.label.localeCompare(b.label));
  $: productOptions = productItems.map(i => ({ value: i.Name, label: i.Name })).sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
  // For Drops, use all blueprints (allItems)
  $: blueprintDropOptions = allItems.map(b => ({ value: b.Name, label: b.Name })).sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));

  // Can edit if user is verified or admin
  $: canEdit = user?.verified || user?.isAdmin;

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
      initEditState(entity, 'Blueprint', isCreateMode, existingChange);
    }
  }

  // Set existing pending change when data loads
  $: if (pendingChange) {
    setExistingPendingChange(pendingChange);
    // Auto-enable viewing pending change for author or admin
    if (user && (pendingChange.author_id === user.id || user.isAdmin)) {
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
  const navTableColumns = [
    {
      key: 'type',
      header: 'Type',
      width: '80px',
      filterPlaceholder: 'Weapon',
      getValue: (item) => item.Properties?.Type,
      format: (v) => v || '-'
    },
    {
      key: 'profession',
      header: 'Profession',
      width: '95px',
      filterPlaceholder: 'Weapons',
      getValue: (item) => item.Profession?.Name,
      format: (v) => v || '-'
    },
    {
      key: 'level',
      header: 'Level',
      width: '65px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Level,
      format: (v) => v != null ? v : '-'
    }
  ];

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
  function handleProductInput(e) {
    updateField('Product.Name', e.detail.value);
  }

  function handleProductSelect(e) {
    const selected = e.detail?.item;
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
  entity={blueprint}
  entityType="Blueprint"
  basePath="/items/blueprints"
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
        <div class="stats-section tier-1">
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
                <InlineEdit
                  value={activeEntity?.Book?.Name || ''}
                  path="Book.Name"
                  type="select"
                  placeholder="Select book..."
                  options={bookOptions}
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
                <ItemSearchInput
                  value={activeEntity?.Product?.Name || ''}
                  placeholder="Search product..."
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
                    <SearchableSelect
                      value={drop.Name || ''}
                      options={blueprintDropOptions}
                      placeholder="Select blueprint..."
                      on:change={(e) => updateDrop(i, e.detail.value)}
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
  .pending-change-banner {
    background: linear-gradient(135deg, #f59e0b22 0%, #f59e0b11 100%);
    border: 1px solid #f59e0b44;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 16px;
  }

  .banner-content {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .banner-icon {
    font-size: 18px;
  }

  .banner-text {
    flex: 1;
    color: var(--text-color);
    font-size: 14px;
  }

  .banner-toggle {
    padding: 6px 12px;
    font-size: 12px;
    background: var(--accent-color);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: opacity 0.2s;
  }

  .banner-toggle:hover {
    opacity: 0.9;
  }

  .layout-a {
    position: relative;
    width: 100%;
  }

  /* Clearfix to ensure spacing after floated infobox */
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
    background: linear-gradient(135deg, #7c5a4a 0%, #634939 100%);
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
    color: #f4e8e8;
    font-size: 18px;
    font-weight: 700;
  }

  .stats-section.tier-1 .tier1-link {
    color: #f4e8e8;
    text-decoration: none;
    font-size: 14px;
    font-weight: 600;
  }

  .stats-section.tier-1 .tier1-link:hover {
    text-decoration: underline;
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

  .stat-row.indent {
    padding-left: 12px;
  }

  .stat-row.indent .stat-label {
    font-size: 11px;
  }

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    font-weight: 500;
    color: var(--text-color);
    text-align: right;
  }

  .stat-value :global(.inline-edit .edit-select) {
    min-width: 160px;
  }

  .stat-value.highlight-yes {
    color: var(--success-color, #4ade80);
  }

  .profession-link,
  .item-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .profession-link:hover,
  .item-link:hover {
    text-decoration: underline;
  }

  .wiki-article {
    overflow: hidden; /* Contains floated infobox */
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
      width: 270px;
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

    /* Hide article title on mobile - redundant with infobox */
    .article-title {
      display: none;
    }

    .infobox-title {
      font-size: 16px;
    }
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

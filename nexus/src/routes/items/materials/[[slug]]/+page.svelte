<!--
  @component Material Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: Weight, Value
  Article: Description, Acquisition, Usage

  Supports full wiki editing with wikiEditState integration.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { encodeURIComponentSafe, clampDecimals } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';

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
  import Acquisition from '$lib/components/Acquisition.svelte';
  import Usage from '$lib/components/Usage.svelte';

  // Material-specific editor
  import RefiningRecipesEditor from '$lib/components/wiki/RefiningRecipesEditor.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  export let data;

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

  // Permission check - verified users can edit
  $: canEdit = user?.verified === true;

  // Empty entity template for create mode
  const emptyMaterial = {
    Id: null,
    Name: '',
    Properties: {
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
      initEditState(material, 'Material', false, null);
    }
  }

  // Handle pending changes from API
  $: if (pendingChange) {
    setExistingPendingChange(pendingChange);
    if (user && (pendingChange.author_id === user.id || user.isAdmin)) {
      setViewingPendingChange(true);
    }
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

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters - none for materials (simple list)
  const navFilters = [];

  // Sidebar table columns for materials
  const navTableColumns = [
    {
      key: 'type',
      header: 'Type',
      width: '90px',
      filterPlaceholder: 'Ore',
      getValue: (item) => item.Properties?.Type,
      format: (v) => v || '-'
    }
  ];

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
  entity={data.isCreateMode ? $currentEntity : material}
  entityType="Material"
  basePath="/items/materials"
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

        <!-- Primary Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
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
          <div class="stat-row primary">
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
              {availableItems}
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
    width: 280px;
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
      width: 260px;
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

    .banner-content {
      flex-direction: column;
      align-items: flex-start;
    }

    .banner-toggle {
      width: 100%;
      text-align: center;
    }
  }

  /* Refining Recipes */
  .refining-recipes {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .recipe-card {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 12px;
  }

  .recipe-header {
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .recipe-output {
    font-size: 14px;
    color: var(--text-color);
  }

  .recipe-output strong {
    color: var(--accent-color, #4a9eff);
  }

  .recipe-ingredients {
    margin-top: 8px;
  }

  .ingredients-label {
    font-size: 12px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    margin-bottom: 6px;
  }

  .ingredients-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .ingredient {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    font-size: 13px;
  }

  .ingredient-amount {
    color: var(--accent-color, #4a9eff);
    font-weight: 600;
  }

  .ingredient-name {
    color: var(--text-color);
  }

  .no-ingredients {
    color: var(--text-muted, #999);
    font-style: italic;
    font-size: 13px;
  }
</style>

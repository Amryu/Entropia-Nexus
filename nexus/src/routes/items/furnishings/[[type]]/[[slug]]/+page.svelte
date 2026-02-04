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
  import { onMount, onDestroy } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/Acquisition.svelte';

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

  export let data;

  $: furnishing = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};
  $: pendingChange = data.pendingChange;
  $: existingChange = data.existingChange;
  $: isCreateMode = data.isCreateMode || false;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];

  $: userPendingUpdates = data.userPendingUpdates || [];
  // Can edit if user is verified or admin
  $: canEdit = user?.verified || user?.isAdmin;

  // For multi-type pages, data.items is an object keyed by type
  $: allItems = (() => {
    if (!data.items) return [];
    if (additional.type && data.items[additional.type]) {
      return data.items[additional.type];
    }
    // No type selected - combine all items from all types
    const combined = [];
    for (const [type, items] of Object.entries(data.items)) {
      for (const item of items) {
        combined.push({ ...item, _type: type });
      }
    }
    return combined;
  })();

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

  // Initialize edit state when entity or user changes
  $: if (user && additional.type) {
    const entityType = getEntityType(additional.type);
    const entity = isCreateMode ? (existingChange?.data || getEmptyEntity(additional.type)) : furnishing;
    if (entity && entityType) {
      initEditState(entity, entityType, isCreateMode, existingChange);
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

  // Active entity: what we display (edit mode → currentEntity, pending view → pending data, default → furnishing)
  $: activeEntity = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.changes)
      ? applyChangesToEntity(furnishing, $existingPendingChange.changes)
      : furnishing;

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

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters - type buttons with deselection support
  $: navFilters = typeButtons.map(btn => ({
    label: btn.label,
    title: btn.title,
    type: btn.type,
    active: additional.type === btn.type,
    href: additional.type === btn.type ? '/items/furnishings' : `/items/furnishings/${btn.type}`
  }));

  // Type-specific sidebar table columns
  function getNavTableColumns(type) {
    switch (type) {
      case 'furniture':
      case 'decorations':
        return [
          { key: 'type', header: 'Type', width: '60px', filterPlaceholder: 'Chair', getValue: (item) => item.Properties?.Type, format: (v) => v ? v.slice(0, 6) : '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      case 'storagecontainers':
        return [
          { key: 'cap', header: 'Items', width: '55px', filterPlaceholder: '>50', getValue: (item) => item.Properties?.ItemCapacity, format: (v) => v ?? '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      case 'signs':
        return [
          { key: 'ratio', header: 'Ratio', width: '55px', filterPlaceholder: '16:9', getValue: (item) => item.Properties?.Display?.AspectRatio, format: (v) => v || '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      default:
        return [
          { key: 'cat', header: 'Cat', width: '60px', filterPlaceholder: 'Furn', getValue: (item) => getTypeName(item._type || additional.type).slice(0, 6), format: (v) => v || '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
    }
  }

  $: navTableColumns = getNavTableColumns(additional.type);

  // Custom href generator for items
  function getItemHref(item, basePath) {
    const type = item._type || additional.type;
    if (type) {
      return `/items/furnishings/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Furnishings', href: '/items/furnishings' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + (additional.type !== 'furniture' ? 's' : ''), href: `/items/furnishings/${additional.type}` }] : []),
    ...(activeEntity ? [{ label: activeEntity.Name || 'New ' + getTypeName(additional.type) }] : [])
  ];

  // SEO
  $: seoDescription = activeEntity?.Properties?.Description ||
    `${activeEntity?.Name || 'Furnishing'} - ${getTypeName(additional.type)} in Entropia Universe.`;

  $: canonicalUrl = furnishing
    ? `https://entropianexus.com/items/furnishings/${additional.type}/${encodeURIComponentSafe(furnishing.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/furnishings/${additional.type}`
    : 'https://entropianexus.com/items/furnishings';

  // Image URL for SEO
  $: entityImageUrl = furnishing?.Id && additional.type
    ? `/api/img/${getEntityType(additional.type).toLowerCase()}/${furnishing.Id}`
    : null;

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    acquisition: true
  };

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
  entity={furnishing}
  entityType={getEntityType(additional.type)}
  basePath="/items/furnishings/{additional.type || ''}"
  {navItems}
  {navFilters}
  {navTableColumns}
  navGetItemHref={getItemHref}
  {user}
  editable={true}
  canEdit={canEdit && !!additional.type}
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
              on:change={(e) => updateField('Properties.Description', e.detail)}
              placeholder="Enter {getTypeName(additional.type).toLowerCase()} description..."
            />
          {:else if activeEntity?.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeEntity.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || 'This ' + getTypeName(additional.type).toLowerCase()} is a {getTypeName(additional.type).toLowerCase()} in Entropia Universe.
            </div>
          {/if}
        </div>

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
  }

  .stat-value.feature-flag {
    color: var(--text-muted, #999);
  }

  .stat-value.feature-flag.yes {
    color: #4ade80;
    font-weight: 600;
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
  }
</style>

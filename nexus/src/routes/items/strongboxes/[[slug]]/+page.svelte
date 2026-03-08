<!--
  @component Strongboxes Wiki Page
  Wikipedia-style layout with floating infobox on the right side.

  Supports full wiki editing with wikiEditState integration.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, getItemLink, getLatestPendingUpdate, loadEditDeps } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
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

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  export let data;

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = false;
  $: if ($editMode && data.allItems === null && !editDepsLoading) {
    editDepsLoading = true;
    loadEditDeps([
      { key: 'allItems', url: '/api/items' }
    ]).then(deps => {
      data = { ...data, ...deps };
      editDepsLoading = false;
    });
  }

  $: strongbox = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};
  $: pendingChange = data.pendingChange;
  $: existingChange = data.existingChange;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: canCreateNew = data.canCreateNew ?? true;
  $: allItemsList = data.allItems || [];
  $: strongboxEntityId = strongbox?.Id ?? strongbox?.ItemId;
  $: userPendingUpdate = getLatestPendingUpdate(userPendingUpdates, strongboxEntityId);
  $: resolvedPendingChange = userPendingUpdate || pendingChange;
  $: canUsePendingChange = !!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve')));

  // Permission check - verified users can edit
  $: canEdit = user?.verified === true;

  // Empty entity template for create mode
  const emptyStrongbox = {
    Id: null,
    Name: '',
    Properties: {
      Description: null
    },
    Loots: []
  };

  // Initialize edit state when entity/user changes
  $: if (user) {
    if (data.isCreateMode) {
      const initialData = existingChange?.data || emptyStrongbox;
      initEditState(initialData, 'Strongbox', true, existingChange);
    } else if (strongbox) {
      initEditState(strongbox, 'Strongbox', false, canUsePendingChange ? resolvedPendingChange : null);
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
  $: activeStrongbox = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : strongbox;

  // Cleanup on unmount
  onDestroy(() => {
    resetEditState();
  });

  // All strongboxes for navigation
  $: allItems = data.items || [];

  // Build navigation items
  $: navItems = allItems;

  // No filters for strongboxes
  $: navFilters = [];

  // Full column definitions for strongboxes
  const columnDefs = {
    loots: { key: 'loots', header: 'Loots', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Loots?.length || 0, format: (v) => v != null ? v : '-' }
  };

  // Sidebar table columns
  $: navTableColumns = [columnDefs.loots];
  const navFullWidthColumns = [columnDefs.loots];
  const allAvailableColumns = Object.values(columnDefs);

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Strongboxes', href: '/items/strongboxes' },
    ...(activeStrongbox?.Name ? [{ label: activeStrongbox.Name }] : data.isCreateMode ? [{ label: 'New Strongbox' }] : [])
  ];

  // SEO
  $: seoDescription = activeStrongbox?.Properties?.Description ||
    `${activeStrongbox?.Name || 'Strongbox'} - Strongbox container in Entropia Universe.`;

  $: canonicalUrl = activeStrongbox?.Name
    ? `https://entropianexus.com/items/strongboxes/${encodeURIComponentSafe(activeStrongbox.Name)}`
    : 'https://entropianexus.com/items/strongboxes';

  // SEO Image URL (if entity has an image)
  $: entityImageUrl = strongbox?.Id ? `/api/img/strongbox/${strongbox.Id}` : null;

  // Check for loots
  $: hasLoots = activeStrongbox?.Loots?.length > 0;

  // Rarity order for sorting
  const rarityOrder = {
    'Common': 0,
    'Uncommon': 1,
    'Rare': 2,
    'Epic': 3,
    'Supreme': 4,
    'Legendary': 5,
    'Mythical': 6
  };

  // Rarity options for dropdown
  const rarityOptions = [
    { value: 'Common', label: 'Common' },
    { value: 'Uncommon', label: 'Uncommon' },
    { value: 'Rare', label: 'Rare' },
    { value: 'Epic', label: 'Epic' },
    { value: 'Supreme', label: 'Supreme' },
    { value: 'Legendary', label: 'Legendary' },
    { value: 'Mythical', label: 'Mythical' }
  ];

  // Sort loots by rarity
  function sortByRarity(a, b) {
    const aOrder = rarityOrder[a.Rarity] ?? 99;
    const bOrder = rarityOrder[b.Rarity] ?? 99;
    return aOrder - bOrder;
  }

  // Rarity color mapping
  function getRarityColor(rarity) {
    switch (rarity) {
      case 'Common': return '#9ca3af';
      case 'Uncommon': return '#22c55e';
      case 'Rare': return '#3b82f6';
      case 'Epic': return '#a855f7';
      case 'Supreme': return '#f97316';
      case 'Legendary': return '#f59e0b';
      case 'Mythical': return '#ef4444';
      default: return '#9ca3af';
    }
  }

  // Sorted loots
  $: sortedLoots = hasLoots ? [...activeStrongbox.Loots].sort(sortByRarity) : [];

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    loots: true,
    marketPrices: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-strongbox-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-strongbox-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }
</script>

<WikiSEO
  title={activeStrongbox?.Name || 'Strongboxes'}
  description={seoDescription}
  entityType="Strongbox"
  entity={activeStrongbox}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={activeStrongbox}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Strongboxes"
  {breadcrumbs}
  entity={data.isCreateMode ? $currentEntity : (activeStrongbox || strongbox)}
  basePath="/items/strongboxes"
  {navItems}
  {navFilters}
  {navTableColumns}
  navAllAvailableColumns={allAvailableColumns}
  navFullWidthColumns={navFullWidthColumns}
  navPageTypeId="strongboxes"
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
            This strongbox has changes pending review.
          {:else}
            This strongbox has a draft with unsaved changes.
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

  {#if activeStrongbox || data.isCreateMode}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeStrongbox?.Id}
            entityName={activeStrongbox?.Name}
            entityType="strongbox"
            {user}
            isEditMode={$editMode}
            isCreateMode={data.isCreateMode}
          />
          <div class="infobox-title">
            {#if $editMode}
              <InlineEdit
                value={activeStrongbox?.Name || ''}
                path="Name"
                type="text"
                required={true}
                placeholder="Strongbox Name"
              />
            {:else}
              {activeStrongbox?.Name || 'New Strongbox'}
            {/if}
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge">Strongbox</span>
          </div>
        </div>

        <!-- Tier-1 Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Loots</span>
            <span class="stat-value">{activeStrongbox?.Loots?.length || 0} items</span>
          </div>
        </div>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          {#if $editMode}
            <InlineEdit
              value={activeStrongbox?.Name || ''}
              path="Name"
              type="text"
              required={true}
              placeholder="Strongbox Name"
            />
          {:else}
            {activeStrongbox?.Name || 'New Strongbox'}
          {/if}
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeStrongbox?.Properties?.Description || ''}
              on:change={(e) => updateField('Properties.Description', e.detail)}
              placeholder="Enter a description for this strongbox..."
            />
          {:else if activeStrongbox?.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeStrongbox.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeStrongbox?.Name || 'This strongbox'} is a strongbox that can be obtained and opened in Entropia Universe.
            </div>
          {/if}
        </div>

        <!-- Loots Section -->
        {#if hasLoots || $editMode}
          <DataSection
            title="Possible Loots"
            icon=""
            bind:expanded={panelStates.loots}
            on:toggle={savePanelStates}
          >
            {#if $editMode}
              <!-- Edit mode: Loots editor -->
            <div class="loots-editor">
                {#each activeStrongbox?.Loots || [] as loot, index}
                  <div class="loot-row">
                    <div class="loot-field item-field">
                      <label>Item</label>
                      <SearchInput
                        value={loot.Item?.Name || ''}
                        placeholder="Search for item..."
                        apiEndpoint="/search/items"
                        displayFn={(item) => item?.Name || ''}
                        on:change={(e) => {
                          const loots = [...(activeStrongbox?.Loots || [])];
                          const value = e.detail?.value || '';
                          if (value) {
                            const selectedItem = allItemsList.find(i => i.Name === value);
                            loots[index] = {
                              ...loots[index],
                              Item: selectedItem ? { Name: selectedItem.Name, Properties: selectedItem.Properties } : { Name: value }
                            };
                          } else {
                            loots[index] = { ...loots[index], Item: null };
                          }
                          updateField('Loots', loots);
                        }}
                        on:select={(e) => {
                          const loots = [...(activeStrongbox?.Loots || [])];
                          const value = e.detail?.value || '';
                          if (value) {
                            const selectedItem = allItemsList.find(i => i.Name === value);
                            loots[index] = {
                              ...loots[index],
                              Item: selectedItem ? { Name: selectedItem.Name, Properties: selectedItem.Properties } : { Name: value }
                            };
                          }
                          updateField('Loots', loots);
                        }}
                      />
                    </div>
                    <div class="loot-field rarity-field">
                      <label>Rarity</label>
                      <select
                        value={loot.Rarity || 'Common'}
                        on:change={(e) => {
                          const loots = [...(activeStrongbox?.Loots || [])];
                          loots[index] = { ...loots[index], Rarity: e.target.value };
                          updateField('Loots', loots);
                        }}
                      >
                        {#each rarityOptions as opt}
                          <option value={opt.value}>{opt.label}</option>
                        {/each}
                      </select>
                    </div>
                    <div class="loot-field date-field from-field">
                      <label>Available From (optional)</label>
                      <input
                        type="date"
                        value={loot.AvailableFrom || ''}
                        on:input={(e) => {
                          const loots = [...(activeStrongbox?.Loots || [])];
                          loots[index] = { ...loots[index], AvailableFrom: e.target.value || null };
                          updateField('Loots', loots);
                        }}
                      />
                    </div>
                    <div class="loot-field date-field until-field">
                      <label>Available Until (optional)</label>
                      <input
                        type="date"
                        value={loot.AvailableUntil || ''}
                        on:input={(e) => {
                          const loots = [...(activeStrongbox?.Loots || [])];
                          loots[index] = { ...loots[index], AvailableUntil: e.target.value || null };
                          updateField('Loots', loots);
                        }}
                      />
                    </div>
                    <button
                      type="button"
                      class="remove-loot-btn"
                      on:click={() => {
                        const loots = [...(activeStrongbox?.Loots || [])];
                        loots.splice(index, 1);
                        updateField('Loots', loots);
                      }}
                      title="Remove loot"
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
                  class="add-loot-btn"
                  on:click={() => {
                    const loots = [...(activeStrongbox?.Loots || []), {
                      Item: { Name: '' },
                      Rarity: 'Common',
                      AvailableFrom: null,
                      AvailableUntil: null
                    }];
                    updateField('Loots', loots);
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                  </svg>
                  Add Loot
                </button>
              </div>
            {:else}
              <!-- View mode: Loots table -->
              <div class="loots-table-wrapper">
                <table class="loots-table">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Rarity</th>
                      <th>Available From</th>
                      <th>Available Until</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each sortedLoots as loot}
                      <tr>
                        <td class="item-name">
                          {#if loot.Item?.Name}
                            <a href={getItemLink(loot.Item)} class="item-link">{loot.Item.Name}</a>
                          {:else}
                            <span class="na-text">Unknown Item</span>
                          {/if}
                        </td>
                        <td>
                          <span class="rarity-badge" style="background-color: {getRarityColor(loot.Rarity)}">
                            {loot.Rarity || 'Unknown'}
                          </span>
                        </td>
                        <td class="date-cell">{loot.AvailableFrom || '-'}</td>
                        <td class="date-cell">{loot.AvailableUntil || '-'}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {/if}
          </DataSection>
        {/if}

        <!-- Market Prices Section -->
        {#if !data.isCreateMode}
          <MarketPriceSection
            itemId={activeStrongbox?.Id}
            itemName={activeStrongbox?.Name}
            bind:expanded={panelStates.marketPrices}
            on:toggle={savePanelStates}
          />
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
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Strongboxes</h2>
      <p>Select a strongbox from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  /* Strongbox-specific: pending change banner */
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

  /* Strongbox-specific: loots editor */
  .loots-editor {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .loot-row {
    display: flex;
    gap: 10px;
    align-items: flex-end;
    padding: 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
    border: 1px solid var(--border-color, #555);
    overflow: visible;
  }

  .loot-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow: visible;
  }

  .loot-field label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
  }

  .loot-field.item-field {
    flex: 2;
  }

  .loot-field.rarity-field {
    width: 120px;
  }

  .loot-field.date-field {
    width: 140px;
  }

  .loot-field input,
  .loot-field select {
    padding: 8px 10px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 13px;
    height: 32px;
    box-sizing: border-box;
  }

  .loot-field.item-field :global(.item-search) {
    height: 32px;
  }

  .loot-field.item-field :global(.item-search input) {
    padding: 8px 10px !important;
    height: 32px !important;
    box-sizing: border-box !important;
    font-size: 13px !important;
    background-color: var(--secondary-color) !important;
    border: 1px solid var(--border-color, #555) !important;
    border-radius: 4px !important;
    color: var(--text-color) !important;
  }

  .loot-field input:focus,
  .loot-field select:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .remove-loot-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-muted, #999);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .remove-loot-btn:hover {
    background-color: var(--error-bg, #fee2e2);
    border-color: var(--error-color, #ef4444);
    color: var(--error-color, #ef4444);
  }

  .add-loot-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 16px;
    border: 1px dashed var(--border-color, #555);
    border-radius: 6px;
    background-color: transparent;
    color: var(--text-muted, #999);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .add-loot-btn:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--bg-color, var(--primary-color));
  }

  /* Strongbox-specific: loots table */
  .loots-table-wrapper {
    overflow-x: auto;
  }

  .loots-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .loots-table th,
  .loots-table td {
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .loots-table th {
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.3px;
    background-color: var(--hover-color);
  }

  .loots-table td {
    color: var(--text-color);
  }

  .loots-table tbody tr:hover {
    background-color: var(--hover-color);
  }

  .item-name {
    font-weight: 500;
  }

  .item-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .item-link:hover {
    text-decoration: underline;
  }

  .na-text {
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .rarity-badge {
    display: inline-block;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
  }

  .date-cell {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  /* Strongbox-specific: mobile adjustments for loots */
  @media (max-width: 899px) {
    .loots-table th,
    .loots-table td {
      padding: 8px;
      font-size: 12px;
    }

    .banner-content {
      flex-direction: column;
      align-items: flex-start;
    }

    .banner-toggle {
      width: 100%;
      text-align: center;
    }

    .loots-editor {
      gap: 8px;
    }

    .loot-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      grid-template-areas:
        "item item"
        "from until"
        "rarity remove";
      gap: 8px;
      padding: 10px;
      align-items: end;
    }

    .loot-field,
    .loot-field.item-field,
    .loot-field.rarity-field,
    .loot-field.date-field {
      width: 100%;
      flex: 1 1 auto;
    }

    .loot-field.item-field {
      grid-area: item;
    }

    .loot-field.from-field {
      grid-area: from;
    }

    .loot-field.until-field {
      grid-area: until;
    }

    .loot-field.rarity-field {
      grid-area: rarity;
    }

    .loot-field label {
      font-size: 11px;
    }

    .remove-loot-btn {
      grid-area: remove;
      align-self: end;
      justify-self: end;
    }

    .loot-field :global(.item-search input) {
      width: 100%;
    }
  }
</style>

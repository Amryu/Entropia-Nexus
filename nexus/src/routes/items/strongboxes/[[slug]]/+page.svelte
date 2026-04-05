<!--
  @component Strongboxes Wiki Page
  Wikipedia-style layout with floating infobox on the right side.

  Supports full wiki editing with wikiEditState integration.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy, untrack } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, getItemLink, getLatestPendingUpdate, loadEditDeps } from '$lib/util';


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

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  let { data = $bindable() } = $props();

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = $state(false);
  $effect(() => {
    if ($editMode && data.allItems === null && !untrack(() => editDepsLoading)) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'allItems', url: '/api/items' }
      ]).then(deps => {
        data = { ...data, ...deps };
        editDepsLoading = false;
      });
    }
  });

  let strongbox = $derived(data.object);
  let user = $derived(data.session?.user);
  let additional = $derived(data.additional || {});
  let pendingChange = $derived(data.pendingChange);
  let existingChange = $derived(data.existingChange);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let allItemsList = $derived(data.allItems || []);
  let strongboxEntityId = $derived(strongbox?.Id ?? strongbox?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, strongboxEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));

  // Permission check - verified users can edit
  let canEdit = $derived(user?.verified === true);

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
  $effect(() => {
    if (user) {
      if (data.isCreateMode) {
        const initialData = existingChange?.data || emptyStrongbox;
        initEditState(initialData, 'Strongbox', true, existingChange);
      } else if (strongbox) {
        initEditState(strongbox, 'Strongbox', false, canUsePendingChange ? resolvedPendingChange : null);
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
  let activeStrongbox = $derived($editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : strongbox);

  // Cleanup on unmount
  onDestroy(() => {
    resetEditState();
  });

  // All strongboxes for navigation
  let allItems = $derived(data.items || []);

  // Build navigation items
  let navItems = $derived(allItems);

  // No filters for strongboxes
  let navFilters = $derived([]);

  // Full column definitions for strongboxes
  const columnDefs = {
    loots: { key: 'loots', header: 'Loots', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Loots?.length || 0, format: (v) => v != null ? v : '-' }
  };

  // Sidebar table columns
  let navTableColumns = $derived([columnDefs.loots]);
  const navFullWidthColumns = [columnDefs.loots];
  const allAvailableColumns = Object.values(columnDefs);

  // Breadcrumbs
  let breadcrumbs = $derived([
    { label: 'Items', href: '/items' },
    { label: 'Strongboxes', href: '/items/strongboxes' },
    ...(activeStrongbox?.Name ? [{ label: activeStrongbox.Name }] : data.isCreateMode ? [{ label: 'New Strongbox' }] : [])
  ]);

  // SEO
  let seoDescription = $derived(activeStrongbox?.Properties?.Description ||
    `${activeStrongbox?.Name || 'Strongbox'} - Strongbox container in Entropia Universe.`);

  let canonicalUrl = $derived(activeStrongbox?.Name
    ? `https://entropianexus.com/items/strongboxes/${encodeURIComponentSafe(activeStrongbox.Name)}`
    : 'https://entropianexus.com/items/strongboxes');

  // SEO Image URL (if entity has an image)
  let entityImageUrl = $derived(strongbox?.Id ? `/api/img/strongbox/${strongbox.Id}` : null);

  // Check for loots
  let hasLoots = $derived(activeStrongbox?.Loots?.length > 0);

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
  let sortedLoots = $derived(hasLoots ? [...activeStrongbox.Loots].sort(sortByRarity) : []);

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    loots: true,
    marketPrices: true,
    acquisition: true
  });

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
    <PendingChangeBanner
      pendingChange={$existingPendingChange}
      viewing={$viewingPendingChange}
      onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
      entityLabel="strongbox"
    />
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
            {#if activeStrongbox?.Properties?.IsRare}<span class="item-flag-badge rare">Rare</span>{/if}
            {#if activeStrongbox?.Properties?.IsUntradeable}<span class="item-flag-badge untradeable">Untradeable</span>{/if}
          </div>
        </div>

        <!-- Tier-1 Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Loots</span>
            <span class="stat-value">{activeStrongbox?.Loots?.length || 0} items</span>
          </div>
        </div>

        <!-- Properties -->
        <div class="stats-section">
          <h4 class="section-title">Properties</h4>
          <div class="stat-row">
            <span class="stat-label">Rare</span>
            <span class="stat-value" class:highlight-yes={activeStrongbox?.Properties?.IsRare}>
              <InlineEdit value={activeStrongbox?.Properties?.IsRare} path="Properties.IsRare" type="checkbox" />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Untradeable</span>
            <span class="stat-value" class:highlight-yes={activeStrongbox?.Properties?.IsUntradeable}>
              <InlineEdit value={activeStrongbox?.Properties?.IsUntradeable} path="Properties.IsUntradeable" type="checkbox" />
            </span>
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
              onchange={(data) => updateField('Properties.Description', data)}
              placeholder="Enter a description for this strongbox..."
              showWaypoints={true}
            />
          {:else if activeStrongbox?.Properties?.Description}
            <div class="description-content">{@html activeStrongbox.Properties.Description}</div>
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
            ontoggle={savePanelStates}
          >
            {#if $editMode}
              <!-- Edit mode: Loots editor -->
            <div class="loots-editor">
                {#each activeStrongbox?.Loots || [] as loot, index}
                  <div class="loot-row">
                    <div class="loot-field item-field">
                      <span class="field-label">Item</span>
                      <SearchInput
                        value={loot.Item?.Name || ''}
                        placeholder="Search for item..."
                        apiEndpoint="/search/items"
                        displayFn={(item) => item?.Name || ''}
                        onchange={(e) => {
                          const loots = [...(activeStrongbox?.Loots || [])];
                          const value = e.value || '';
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
                        onselect={(e) => {
                          const loots = [...(activeStrongbox?.Loots || [])];
                          const value = e.value || '';
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
                      <span class="field-label">Rarity</span>
                      <select
                        value={loot.Rarity || 'Common'}
                        onchange={(e) => {
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
                      <span class="field-label">Available From (optional)</span>
                      <input
                        type="date"
                        value={loot.AvailableFrom || ''}
                        oninput={(e) => {
                          const loots = [...(activeStrongbox?.Loots || [])];
                          loots[index] = { ...loots[index], AvailableFrom: e.target.value || null };
                          updateField('Loots', loots);
                        }}
                      />
                    </div>
                    <div class="loot-field date-field until-field">
                      <span class="field-label">Available Until (optional)</span>
                      <input
                        type="date"
                        value={loot.AvailableUntil || ''}
                        oninput={(e) => {
                          const loots = [...(activeStrongbox?.Loots || [])];
                          loots[index] = { ...loots[index], AvailableUntil: e.target.value || null };
                          updateField('Loots', loots);
                        }}
                      />
                    </div>
                    <button
                      type="button"
                      class="remove-loot-btn"
                      onclick={() => {
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
                  onclick={() => {
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
        {#if !data.isCreateMode && !activeStrongbox?.Properties?.IsUntradeable}
          <MarketPriceSection
            itemId={activeStrongbox?.ItemId}
            itemName={activeStrongbox?.Name}
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

  .loot-field .field-label {
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

    .loot-field .field-label {
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

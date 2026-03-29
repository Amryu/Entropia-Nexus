<!--
  @component Clothing Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: All stats including effects
  Article: Description → Acquisition
  Supports full wiki editing.

  Legacy editConfig preserved in clothing-legacy/+page.svelte
  Key structure:
  - constructor: Name, Properties (Description, Weight, Type, Slot, Gender, Economy), Set, EffectsOnEquip[]
  - dependencies: ['effects', 'equipsets']
  - controls: General, Economy, Set (with Name and EffectsOnSetEquip), Equip Effects
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy, untrack } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, groupBy, getLatestPendingUpdate, loadEditDeps } from '$lib/util';


  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import MarketPriceSection from '$lib/components/wiki/MarketPriceSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import EffectsEditor from '$lib/components/wiki/EffectsEditor.svelte';
  import SetEffectsEditor from '$lib/components/wiki/SetEffectsEditor.svelte';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/wiki/Acquisition.svelte';

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

  let { data = $bindable() } = $props();

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = $state(false);
  $effect(() => {
    if ($editMode && data.effects === null && !untrack(() => editDepsLoading)) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'effects', url: '/api/effects' },
        { key: 'equipsets', url: '/api/equipsets' }
      ]).then(deps => {
        data = { ...data, ...deps };
        editDepsLoading = false;
      });
    }
  });

  let clothing = $derived(data.object);
  let user = $derived(data.session?.user);
  let additional = $derived(data.additional || {});
  let allItems = $derived(data.allItems || []);
  let pendingChange = $derived(data.pendingChange);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let isCreateMode = $derived(data.isCreateMode || false);
  let effectsList = $derived(data.effects || []);
  let equipsetsList = $derived(data.equipsets || []);
  let clothingEntityId = $derived(clothing?.Id ?? clothing?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, clothingEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));

  // Verified users can edit
  let canEdit = $derived(user?.verified || user?.grants?.includes('wiki.edit'));

  // Type options
  let typeOptions = $derived(Array.from(new Set(
    (allItems || [])
      .map(item => item?.Properties?.Type)
      .filter(v => v && v.trim().length > 0)
  )).sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })));

  // Slot options
  let slotOptions = $derived(Array.from(new Set(
    (allItems || [])
      .map(item => item?.Properties?.Slot)
      .filter(v => v && v.trim().length > 0)
  )).sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })));

  // Gender options
  const genderOptions = [
    { value: 'Both', label: 'Both' },
    { value: 'Male', label: 'Male' },
    { value: 'Female', label: 'Female' },
    { value: 'Neutral', label: 'Neutral' }
  ];

  // Empty clothing template for create mode
  const emptyClothing = {
    Id: null,
    Name: '',
    Properties: {
      Description: '',
      Weight: null,
      Type: 'Common',
      Slot: 'Body',
      Gender: 'Both',
      Economy: {
        MaxTT: null,
        MinTT: 0
      }
    },
    EffectsOnEquip: [],
    Set: { Name: null, EffectsOnSetEquip: [] }
  };

  // Initialize edit state when user/clothing changes
  $effect(() => {
    if (user) {
      const existingChange = data.existingChange || null;
      const initialEntity = isCreateMode
        ? (existingChange?.data || emptyClothing)
        : clothing;
      const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
      initEditState(initialEntity, 'Clothing', isCreateMode, editChange);
    }
  });

  // Set pending change in store when it changes
  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });

  // Active clothing: use currentEntity in edit mode, pendingChange data when viewing, otherwise original
  let activeClothing = $derived($editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : clothing);

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });

  function handleSetChange({ value = '' } = {}) {
    const trimmed = value.trim();
    if (trimmed) {
      updateField('Set.Name', trimmed);
      updateField('Set.EffectsOnSetEquip', []);
    } else {
      updateField('Set', { Name: null, EffectsOnSetEquip: [] });
    }
  }

  function handleSetSelect({ value = '' } = {}) {
    const trimmed = value.trim();
    if (trimmed) {
      const selected = equipsetsList.find(s => s.Name === trimmed);
      updateField('Set.Name', trimmed);
      updateField('Set.EffectsOnSetEquip', selected ? (selected.EffectsOnSetEquip || []) : []);
    } else {
      updateField('Set', { Name: null, EffectsOnSetEquip: [] });
    }
  }

  // Build navigation items
  let navItems = $derived(allItems);

  // Navigation filters
  const navFilters = [
    {
      key: 'hasEffects',
      label: 'Effects',
      values: [
        { value: 'yes', label: 'Has Effects' },
        { value: 'no', label: 'No Effects' }
      ],
      filterFn: (item, value) => {
        const equipCount = item?.EffectsOnEquip?.length || item?.Effects?.length || item?.Properties?.Effects?.length || item?.Properties?.EffectsOnEquip?.length || 0;
        const setCount = item?.Set?.EffectsOnSetEquip?.length || item?.EffectsOnSetEquip?.length || item?.SetEffects?.length || item?.Properties?.SetEffects?.length || item?.Properties?.Set?.EffectsOnSetEquip?.length || 0;
        const hasEffects = (equipCount + setCount) > 0;
        return value === 'yes' ? hasEffects : !hasEffects;
      }
    }
  ];

  // Full column definitions for clothing
  const columnDefs = {
    slot: { key: 'slot', header: 'Slot', width: '70px', filterPlaceholder: 'Head', getValue: (item) => item.Properties?.Slot, format: (v) => v || '-' },
    type: { key: 'type', header: 'Type', width: '80px', filterPlaceholder: 'Armor', getValue: (item) => item.Properties?.Type, format: (v) => v || '-' },
    effects: {
      key: 'effects', header: 'Effects', width: '70px', filterPlaceholder: 'Yes',
      getValue: (item) => {
        const equipCount = item?.EffectsOnEquip?.length || item?.Effects?.length || item?.Properties?.Effects?.length || item?.Properties?.EffectsOnEquip?.length || 0;
        const setCount = item?.Set?.EffectsOnSetEquip?.length || item?.EffectsOnSetEquip?.length || item?.SetEffects?.length || item?.Properties?.SetEffects?.length || item?.Properties?.Set?.EffectsOnSetEquip?.length || 0;
        return (equipCount + setCount) > 0;
      },
      format: (v) => v ? 'Yes' : 'No'
    },
    gender: { key: 'gender', header: 'Gender', width: '60px', filterPlaceholder: 'Male', getValue: (item) => item.Properties?.Gender, format: (v) => v ?? 'Unknown' },
    weight: { key: 'weight', header: 'Weight', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Weight, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' },
    maxTT: { key: 'maxTT', header: 'Max TT', width: '60px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 2, 4) : '-' },
    minTT: { key: 'minTT', header: 'Min TT', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Economy?.MinTT, format: (v) => v != null ? clampDecimals(v, 2, 4) : '-' },
    set: { key: 'set', header: 'Set', width: '80px', filterPlaceholder: 'Adj', getValue: (item) => item.Set?.Name, format: (v) => v || '-' }
  };

  const navTableColumns = [columnDefs.slot, columnDefs.type, columnDefs.effects];
  const navFullWidthColumns = [columnDefs.slot, columnDefs.type, columnDefs.effects, columnDefs.gender, columnDefs.weight, columnDefs.maxTT, columnDefs.set];
  const allAvailableColumns = Object.values(columnDefs);

  // Breadcrumbs
  let breadcrumbs = $derived([
    { label: 'Items', href: '/items' },
    { label: 'Clothing', href: '/items/clothing' },
    ...(activeClothing?.Name ? [{ label: activeClothing.Name }] : isCreateMode ? [{ label: 'New Clothing' }] : [])
  ]);

  // SEO
  let seoDescription = $derived(activeClothing?.Properties?.Description ||
    `${activeClothing?.Name || 'Clothing'} - ${activeClothing?.Properties?.Type || ''} ${activeClothing?.Properties?.Slot || ''} clothing in Entropia Universe.`);

  let canonicalUrl = $derived(activeClothing?.Name
    ? `https://entropianexus.com/items/clothing/${encodeURIComponentSafe(activeClothing.Name)}`
    : 'https://entropianexus.com/items/clothing');

  // Image URL for SEO
  let entityImageUrl = $derived(clothing?.Id ? `/api/img/clothing/${clothing.Id}` : null);

  // Check if item has effects
  let hasEquipEffects = $derived(activeClothing?.EffectsOnEquip?.length > 0);
  let hasSetEffects = $derived(activeClothing?.Set?.EffectsOnSetEquip?.length > 0);

  // Get set effects grouped by piece count
  function getSetEffects(item) {
    if (!item?.Set?.EffectsOnSetEquip?.length) return null;
    const grouped = groupBy(item.Set.EffectsOnSetEquip, x => x.Values.MinSetPieces);
    return Object.entries(grouped)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([pieces, effects]) => ({
        pieces: Number(pieces),
        effects: effects.map(e => ({
          name: e.Name,
          strength: e.Values.Strength,
          unit: e.Values.Unit || ''
        }))
      }));
  }

  let setEffects = $derived(getSetEffects(activeClothing));

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    marketPrices: true,
    acquisition: true
  });

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-clothing-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-clothing-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== EDIT HANDLERS ==========
  function handleDescriptionChange(data) {
    updateField('Properties.Description', data);
  }
</script>

<WikiSEO
  title={activeClothing?.Name || 'Clothing'}
  description={seoDescription}
  entityType="Clothing"
  entity={activeClothing}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={activeClothing}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Clothing"
  {breadcrumbs}
  entity={activeClothing}
  basePath="/items/clothing"
  {navItems}
  {navFilters}
  {navTableColumns}
  navAllAvailableColumns={allAvailableColumns}
  navFullWidthColumns={navFullWidthColumns}
  navPageTypeId="clothing"
  {user}
  editable={true}
  {canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
  {editDepsLoading}
>
  {#if activeClothing || isCreateMode}
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
            This clothing has a pending change by <strong>{$existingPendingChange.author_name || 'Unknown'}</strong>
            ({$existingPendingChange.state})
          </span>
        </div>
        <div class="banner-actions">
          {#if $viewingPendingChange}
            <button class="banner-btn" onclick={() => setViewingPendingChange(false)}>
              View Current
            </button>
          {:else}
            <button class="banner-btn primary" onclick={() => setViewingPendingChange(true)}>
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
            entityId={activeClothing?.Id}
            entityName={activeClothing?.Name}
            entityType="clothing"
            {user}
            isEditMode={$editMode}
            {isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              type="text"
              value={activeClothing?.Name || ''}
              path="Name"
              placeholder="Enter clothing name"
            />
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge">{activeClothing?.Properties?.Type || 'Clothing'}</span>
            <span class="type-badge">{activeClothing?.Properties?.Slot || 'Body'}</span>
            {#if activeClothing.Properties?.IsRare}<span class="item-flag-badge rare">Rare</span>{/if}
            {#if activeClothing.Properties?.IsUntradeable}<span class="item-flag-badge untradeable">Untradeable</span>{/if}
          </div>
        </div>

        <!-- Primary Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Type</span>
            <span class="stat-value">{activeClothing?.Properties?.Type || 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Slot</span>
            <span class="stat-value">{activeClothing?.Properties?.Slot || 'N/A'}</span>
          </div>
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">
              {#if $editMode}
                <SearchInput
                  value={activeClothing?.Properties?.Type || ''}
                  placeholder="Search type..."
                  options={typeOptions}
                  onchange={(e) => updateField('Properties.Type', e.value || '')}
                  onselect={(e) => updateField('Properties.Type', e.value || '')}
                />
              {:else}
                {activeClothing?.Properties?.Type || 'N/A'}
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Slot</span>
            <span class="stat-value">
              {#if $editMode}
                <SearchInput
                  value={activeClothing?.Properties?.Slot || ''}
                  placeholder="Search slot..."
                  options={slotOptions}
                  onchange={(e) => updateField('Properties.Slot', e.value || '')}
                  onselect={(e) => updateField('Properties.Slot', e.value || '')}
                />
              {:else}
                {activeClothing?.Properties?.Slot || 'N/A'}
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Gender</span>
            <span class="stat-value">
              <InlineEdit
                type="select"
                value={activeClothing?.Properties?.Gender ?? 'Unknown'}
                path="Properties.Gender"
                options={genderOptions}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeClothing?.Properties?.Weight ?? ''}
                path="Properties.Weight"
                step={0.1}
                suffix=" kg"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Rare</span>
            <span class="stat-value" class:highlight-yes={activeClothing.Properties?.IsRare}>
              <InlineEdit value={activeClothing.Properties?.IsRare} path="Properties.IsRare" type="checkbox" />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Untradeable</span>
            <span class="stat-value" class:highlight-yes={activeClothing.Properties?.IsUntradeable}>
              <InlineEdit value={activeClothing.Properties?.IsUntradeable} path="Properties.IsUntradeable" type="checkbox" />
            </span>
          </div>
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max TT</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeClothing?.Properties?.Economy?.MaxTT ?? ''}
                path="Properties.Economy.MaxTT"
                step={0.01}
                suffix=" PED"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min TT</span>
            <span class="stat-value">
              <InlineEdit
                type="number"
                value={activeClothing?.Properties?.Economy?.MinTT ?? 0}
                path="Properties.Economy.MinTT"
                step={0.01}
                suffix=" PED"
              />
            </span>
          </div>
        </div>

        <!-- Equip Effects -->
        {#if hasEquipEffects || $editMode}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects</h4>
            <EffectsEditor
              effects={activeClothing?.EffectsOnEquip || []}
              fieldName="EffectsOnEquip"
              availableEffects={effectsList}
              effectType="equip"
              title="Effects on Equip"
            />
          </div>
        {/if}

        <!-- Set Effects -->
        {#if hasSetEffects || $editMode}
          <div class="stats-section set-effects">
            <h4 class="section-title">Equipment Set</h4>
            {#if $editMode}
              <div class="stat-row">
                <span class="stat-label">Equipment Set</span>
                <span class="stat-value">
                  <SearchInput
                    value={activeClothing?.Set?.Name || ''}
                    placeholder="Search equipment set..."
                    options={equipsetsList.map(s => s.Name)}
                    onchange={handleSetChange}
                    onselect={handleSetSelect}
                  />
                </span>
              </div>
            {/if}
            {#if !$editMode && activeClothing?.Set?.Name}
              <div class="set-name">Set: {activeClothing.Set.Name}</div>
            {/if}
            <SetEffectsEditor
              effects={activeClothing?.Set?.EffectsOnSetEquip || []}
              fieldName="Set.EffectsOnSetEquip"
              availableEffects={effectsList}
              maxPieces={7}
            />
          </div>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            type="text"
            value={activeClothing?.Name || ''}
            path="Name"
            placeholder="Enter clothing name"
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeClothing?.Properties?.Description || ''}
              onchange={handleDescriptionChange}
              placeholder="Enter a description for this clothing item..."
              showWaypoints={true}
            />
          {:else if activeClothing?.Properties?.Description}
            <div class="description-content">{@html activeClothing.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {activeClothing?.Name || 'This item'} is a {activeClothing?.Properties?.Type?.toLowerCase() || ''} clothing item worn on the {activeClothing?.Properties?.Slot?.toLowerCase() || 'body'}.
            </div>
          {/if}
        </div>

        <!-- Market Prices Section -->
        {#if !isCreateMode && !activeClothing?.Properties?.IsUntradeable}
          <MarketPriceSection
            itemId={activeClothing?.ItemId}
            itemName={activeClothing?.Name}
            bind:expanded={panelStates.marketPrices}
            ontoggle={savePanelStates}
          />
        {/if}

        <!-- Acquisition Section -->
        {#if additional.acquisition && !isCreateMode}
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
      <h2>Clothing</h2>
      <p>Select a clothing item from the list to view details.</p>
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

  .set-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color, #555);
  }

</style>

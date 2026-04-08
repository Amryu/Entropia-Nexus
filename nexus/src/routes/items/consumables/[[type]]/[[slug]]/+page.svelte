<!--
  @component Consumables Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Handles 2 subtypes: stimulants, capsules
  Supports full wiki editing.

  Key structure:
  - stimulants: Name, Properties (Description, Weight, Type, Economy), EffectsOnConsume[]
  - capsules: Name, Properties (Economy, MinProfessionLevel), Mob, Profession
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy, untrack } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, getTimeString, getTypeLink, groupBy, getLatestPendingUpdate, loadEditDeps } from '$lib/util';
  import { hasVisibleText } from '$lib/sanitize.js';


  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import MarketPriceSection from '$lib/components/wiki/MarketPriceSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import EffectsEditor from '$lib/components/wiki/EffectsEditor.svelte';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';

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
  } from '$lib/stores/wikiEditState';

  // Legacy components for data display
  import Acquisition from '$lib/components/wiki/Acquisition.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';
  import AdSlot from '$lib/components/AdSlot.svelte';

  let { data = $bindable() } = $props();

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = $state(false);
  $effect(() => {
    if ($editMode && data.effects === null && !untrack(() => editDepsLoading)) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'effects', url: '/api/effects' },
        { key: 'mobs', url: '/api/mobs' },
        { key: 'professions', url: '/api/professions' }
      ]).then(deps => {
        data = { ...data, ...deps };
        editDepsLoading = false;
      });
    }
  });

  let consumable = $derived(data.object);
  let user = $derived(data.session?.user);
  let additional = $derived(data.additional || {});
  let pendingChange = $derived(data.pendingChange);
  let existingChange = $derived(data.existingChange);
  let isCreateMode = $derived(data.isCreateMode || false);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);

  // Local filter state - decoupled from URL
  let selectedFilter = $state(null);
  let filterInitialized = $state(false);

  $effect(() => {
    if (!untrack(() => filterInitialized)) {
      selectedFilter = additional.type || null;
      filterInitialized = true;
    }
  });

  $effect(() => {
    if (untrack(() => filterInitialized) && !consumable && !isCreateMode) {
      if ((additional.type || null) !== untrack(() => selectedFilter)) {
        selectedFilter = additional.type || null;
      }
    }
  });
  let effectsList = $derived(data.effects || []);
  let mobsList = $derived(data.mobs || []);
  let mobOptions = $derived((mobsList || []).map(m => ({ label: m.Name, value: m.Name })));
  let professionsList = $derived(data.professions || []);
  let consumableEntityId = $derived(consumable?.Id ?? consumable?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, consumableEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));

  // Permission check - verified users and admins can edit
  let canEdit = $derived(user?.verified || user?.grants?.includes('wiki.edit'));

  // For multi-type pages, data.items is an object keyed by type
  let allItems = $derived((() => {
    if (!data.items) return [];
    if (selectedFilter && data.items[selectedFilter]) {
      return data.items[selectedFilter];
    }
    // No filter selected - combine all items from all types, adding _type for correct linking
    const combined = [];
    for (const [type, items] of Object.entries(data.items)) {
      for (const item of items) {
        combined.push({ ...item, _type: type });
      }
    }
    return combined;
  })());

  // Type navigation buttons
  const typeButtons = [
    { label: 'Stimulants', title: 'Stimulants', type: 'stimulants' },
    { label: 'Capsules', title: 'Creature Control Capsules', type: 'capsules' }
  ];

  // Type name mapping
  function getTypeName(type) {
    switch (type) {
      case 'stimulants': return 'Stimulant';
      case 'capsules': return 'Creature Control Capsule';
      default: return 'Consumable';
    }
  }

  // Entity type for editing
  function getEntityType(type) {
    switch (type) {
      case 'stimulants': return 'Consumable';
      case 'capsules': return 'Capsule';
      default: return 'Consumable';
    }
  }

  // Empty entity template for create mode (type-specific)
  function getEmptyEntity(type) {
    const base = {
      Name: '',
      Properties: {
        Economy: {
          MaxTT: 0
        }
      }
    };

    switch (type) {
      case 'stimulants':
        base.Properties.Description = '';
        base.Properties.Weight = 0;
        base.Properties.Type = '';
        base.EffectsOnConsume = [];
        break;
      case 'capsules':
        base.Properties.MinProfessionLevel = 0;
        base.Mob = null;
        base.Profession = null;
        break;
    }

    return base;
  }

  // ========== WIKI EDIT STATE ==========
  // Initialize edit state when user/entity changes
  $effect(() => {
    if (user) {
      const entityType = getEntityType(additional.type);
      const emptyEntity = getEmptyEntity(additional.type);
      const entity = isCreateMode ? (existingChange?.data || emptyEntity) : consumable;
      const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
      initEditState(entity || emptyEntity, entityType, isCreateMode, editChange);
    }
  });

  // Set pending change when it exists
  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });

  // Active entity: in edit mode use currentEntity, when viewing pending use its data, otherwise use original
  let activeEntity = $derived($editMode
    ? $currentEntity
    : $viewingPendingChange && $existingPendingChange?.data
      ? $existingPendingChange.data
      : consumable);

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });

  // Build navigation items
  let navItems = $derived(allItems);

  // Navigation filters - uses selectedFilter for active state (local, not URL-based)
  let navFilters = $derived(typeButtons.map(btn => ({
    label: btn.label,
    title: btn.title,
    type: btn.type,
    active: selectedFilter === btn.type,
    href: selectedFilter === btn.type ? '/items/consumables' : `/items/consumables/${btn.type}`
  })));

  // Full column definitions for consumables
  const columnDefs = {
    category: { key: 'category', header: 'Type', width: '90px', filterPlaceholder: 'Stimulant', getValue: (item) => item._type === 'stimulants' ? 'Stimulant' : 'Capsule', format: (v) => v || '-' },
    type: { key: 'type', header: 'Type', width: '70px', filterPlaceholder: 'Pill', getValue: (item) => item.Properties?.Type, format: (v) => v || '-' },
    effects: { key: 'effects', header: 'Effect #', width: '80px', filterPlaceholder: '>0', getValue: (item) => item?.EffectsOnConsume?.length || 0, format: (v) => v != null ? v : '-' },
    mob: { key: 'mob', header: 'Mob', width: '100px', filterPlaceholder: 'Atrox', getValue: (item) => item.Mob?.Name, format: (v) => v || '-' },
    mobType: { key: 'mobType', header: 'Mob Type', width: '90px', filterPlaceholder: 'Animal', getValue: (item) => item.Mob?.Type, format: (v) => v || '-' },
    profession: { key: 'profession', header: 'Profession', width: '90px', filterPlaceholder: 'Tamer', getValue: (item) => item.Profession?.Name, format: (v) => v || '-' },
    minLevel: { key: 'minLevel', header: 'Min Lvl', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.MinProfessionLevel, format: (v) => v != null ? v : '-' },
    maxTT: { key: 'maxTT', header: 'TT Value', width: '65px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 2, 4) : '-' },
    weight: { key: 'weight', header: 'Weight', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Weight, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' },
    effectOrMob: { key: 'effectOrMob', header: 'Effect # / Mob Type', width: '130px', filterPlaceholder: '>0', getValue: (item) => item._type === 'stimulants' ? (item?.EffectsOnConsume?.length || 0) : (item.Mob?.Type || item.Mob?.Name), format: (v) => v != null ? v : '-' }
  };

  // Type-specific sidebar table columns
  function getNavTableColumns(type) {
    switch (type) {
      case 'stimulants':
        return [columnDefs.type, columnDefs.effects];
      case 'capsules':
        return [columnDefs.mob, columnDefs.mobType];
      default:
        return [columnDefs.category, columnDefs.effectOrMob];
    }
  }

  function getNavFullWidthColumns(type) {
    switch (type) {
      case 'stimulants':
        return [columnDefs.type, columnDefs.effects, columnDefs.weight, columnDefs.maxTT];
      case 'capsules':
        return [columnDefs.mob, columnDefs.mobType, columnDefs.profession, columnDefs.minLevel, columnDefs.maxTT];
      default:
        return [columnDefs.category, columnDefs.effectOrMob, columnDefs.maxTT, columnDefs.weight];
    }
  }

  let navTableColumns = $derived(getNavTableColumns(selectedFilter));
  let navFullWidthColumns = $derived(getNavFullWidthColumns(selectedFilter));
  const allAvailableColumns = Object.values(columnDefs);
  let navPageTypeId = $derived(`consumables-${selectedFilter || 'all'}`);

  // Custom href generator for items
  function getItemHref(item, basePath) {
    const type = item._type || selectedFilter || additional.type;
    if (type) {
      return `/items/consumables/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Base path for navigation - uses selectedFilter so it persists
  let effectiveBasePath = $derived(selectedFilter
    ? `/items/consumables/${selectedFilter}`
    : '/items/consumables');

  // Create categories for the "New" dropdown
  let createCategories = $derived(typeButtons.map(btn => ({
    label: getTypeName(btn.type),
    href: `/items/consumables/${btn.type}`
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
    { label: 'Consumables', href: '/items/consumables' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + 's', href: `/items/consumables/${additional.type}` }] : []),
    ...(consumable ? [{ label: consumable.Name }] : [])
  ]);

  // SEO
  let seoDescription = $derived(consumable?.Properties?.Description ||
    `${consumable?.Name || 'Consumable'} - ${getTypeName(additional.type)} in Entropia Universe.`);

  let canonicalUrl = $derived(consumable
    ? `https://entropianexus.com/items/consumables/${additional.type}/${encodeURIComponentSafe(consumable.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/consumables/${additional.type}`
    : 'https://entropianexus.com/items/consumables');

  // Image URL for SEO
  let entityImageUrl = $derived(consumable?.Id && additional.type
    ? `/api/img/${getEntityType(additional.type).toLowerCase()}/${consumable.Id}`
    : null);

  // Format effects grouped by duration (use activeEntity for live updates)
  function getFormattedEffects(item) {
    if (!item?.EffectsOnConsume?.length) return null;
    const grouped = groupBy(item.EffectsOnConsume, x => x.Values.DurationSeconds);
    return Object.entries(grouped)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([duration, effects]) => ({
        duration: Number(duration),
        effects: effects.map(e => ({
          name: e.Name,
          strength: e.Values.Strength,
          unit: e.Values.Unit || ''
        }))
      }));
  }

  let formattedEffects = $derived(getFormattedEffects(activeEntity));

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    marketPrices: true,
    acquisition: true
  });

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-consumable-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-consumable-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }
</script>

<WikiSEO
  title={consumable?.Name || `${getTypeName(additional.type)}s`}
  description={seoDescription}
  entityType={getEntityType(additional.type)}
  entity={activeEntity}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={consumable}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Consumables"
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
  {editDepsLoading}
>
  {#if consumable || isCreateMode}
    <!-- Pending Change Banner -->
    {#if $existingPendingChange && !$editMode}
      <PendingChangeBanner
        pendingChange={$existingPendingChange}
        viewing={$viewingPendingChange}
        onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
        entityLabel="consumable"
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
              placeholder="Enter name..."
            />
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge">{getTypeName(additional.type)}</span>
            {#if activeEntity?.Properties?.IsRare}<span class="item-flag-badge rare">Rare</span>{/if}
            {#if activeEntity?.Properties?.IsUntradeable}<span class="item-flag-badge untradeable">Untradeable</span>{/if}
          </div>
        </div>

        <!-- Tier-1 Stats (type-specific primary stats) -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">TT Value</span>
            <span class="stat-value">{activeEntity?.Properties?.Economy?.MaxTT != null ? `${clampDecimals(activeEntity.Properties.Economy.MaxTT, 2, 4)} PED` : 'N/A'}</span>
          </div>
          {#if additional.type === 'stimulants'}
            <div class="stat-row primary">
              <span class="stat-label">Type</span>
              <span class="stat-value">{activeEntity?.Properties?.Type || 'N/A'}</span>
            </div>
          {:else if additional.type === 'capsules'}
            <div class="stat-row primary">
              <span class="stat-label">Creature</span>
              <span class="stat-value">{activeEntity?.Mob?.Name || 'N/A'}</span>
            </div>
          {/if}
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          {#if additional.type === 'stimulants'}
            <div class="stat-row">
              <span class="stat-label">Weight</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Weight}
                  path="Properties.Weight"
                  type="number"
                  suffix="kg"
                  step={0.01}
                />
              </span>
            </div>
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
          {:else if additional.type === 'capsules'}
            <div class="stat-row">
              <span class="stat-label">Creature</span>
              <span class="stat-value">
                {#if $editMode}
                  <SearchInput
                    value={activeEntity?.Mob?.Name || ''}
                    options={mobOptions}
                    placeholder="Search creature..."
                    onchange={(e) => {
                      if (e.value) {
                        updateField('Mob', { Name: e.value });
                      } else {
                        updateField('Mob', null);
                      }
                    }}
                    onselect={(e) => {
                      if (e.value) {
                        updateField('Mob', { Name: e.value });
                      }
                    }}
                  />
                {:else if activeEntity?.Mob?.Name}
                  <a href={getTypeLink(activeEntity.Mob.Name, 'Mob')} class="entity-link">{activeEntity.Mob.Name}</a>
                {:else}
                  N/A
                {/if}
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Profession</span>
              <span class="stat-value">
                {#if $editMode}
                  <InlineEdit
                    value={activeEntity?.Profession?.Name || ''}
                    path="Profession.Name"
                    type="select"
                    placeholder="Select profession..."
                    options={professionsList.map(p => ({ value: p.Name, label: p.Name }))}
                  />
                {:else if activeEntity?.Profession?.Name}
                  <a href={getTypeLink(activeEntity.Profession.Name, 'Profession')} class="entity-link">{activeEntity.Profession.Name}</a>
                {:else}
                  N/A
                {/if}
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Min. Level</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.MinProfessionLevel}
                  path="Properties.MinProfessionLevel"
                  type="number"
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
            <span class="stat-label">Value</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Economy?.MaxTT}
                path="Properties.Economy.MaxTT"
                type="number"
                suffix=" PED"
                step={0.01}
              />
            </span>
          </div>
        </div>

        <!-- Effects on Consume (stimulants only) - placed after Economy -->
        {#if additional.type === 'stimulants' && (activeEntity?.EffectsOnConsume?.length > 0 || $editMode)}
          <div class="stats-section effects-section">
            <EffectsEditor
              effects={activeEntity?.EffectsOnConsume || []}
              fieldName="EffectsOnConsume"
              availableEffects={effectsList}
              effectType="consume"
              title="Effects on Consume"
            />
          </div>
        {/if}

        <div class="infobox-ad">
          <AdSlot adSlot="3560522008" adFormat="autorelaxed" matchedContentRows={1} matchedContentColumns={1} />
        </div>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            value={activeEntity?.Name}
            path="Name"
            type="text"
            placeholder="Enter name..."
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeEntity?.Properties?.Description || ''}
              onchange={(data) => updateField('Properties.Description', data)}
              placeholder="Enter a description for this {getTypeName(additional.type).toLowerCase()}..."
              showWaypoints={true}
            />
          {:else if hasVisibleText(activeEntity?.Properties?.Description)}
            <div class="description-content">{@html activeEntity.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || 'This consumable'} is a {getTypeName(additional.type).toLowerCase()} used in Entropia Universe.
            </div>
          {/if}
        </div>

        <div class="wiki-content-ad">
          <AdSlot adSlot="3560522008" adFormat="autorelaxed" matchedContentRows={1} matchedContentColumns={4} />
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
      <h2>{additional.type ? getTypeName(additional.type) + 's' : 'Consumables'}</h2>
      <p>Select a {additional.type ? getTypeName(additional.type).toLowerCase() : 'consumable'} from the list to view details.</p>
      <div class="no-selection-ad">
        <AdSlot adSlot="3560522008" adFormat="autorelaxed" matchedContentRows={1} matchedContentColumns={4} />
      </div>
    </div>
  {/if}
</WikiPage>

<style>
  .infobox-ad { margin-top: 12px; }
  .wiki-content-ad { margin: 16px 0; }
  .no-selection-ad { max-width: 728px; margin: 32px auto 0; }

  /* No page-specific styles - all shared rules are in style.css */
</style>

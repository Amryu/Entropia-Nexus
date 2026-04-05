<!--
  @component Medical Tools Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Handles 2 subtypes: tools, chips
  Supports full wiki editing.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy, untrack } from 'svelte';
  import { hasItemTag, clampDecimals, encodeURIComponentSafe, getTimeString, getTypeLink, getLatestPendingUpdate, loadEditDeps } from '$lib/util';


  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import MarketPriceSection from '$lib/components/wiki/MarketPriceSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import EffectsEditor from '$lib/components/wiki/EffectsEditor.svelte';
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

  // Generic wiki components
  import TieringEditor from '$lib/components/wiki/TieringEditor.svelte';
  import Acquisition from '$lib/components/wiki/Acquisition.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  let { data = $bindable() } = $props();

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = $state(false);
  $effect(() => {
    if ($editMode && data.effects === null && !untrack(() => editDepsLoading)) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'effects', url: '/api/effects' }
      ]).then(deps => {
        data = { ...data, ...deps };
        editDepsLoading = false;
      });
    }
  });

  let medtool = $derived(data.object);
  let user = $derived(data.session?.user);
  let additional = $derived(data.additional || {});
  let pendingChange = $derived(data.pendingChange);
  let existingChange = $derived(data.existingChange);
  let isCreateMode = $derived(data.isCreateMode || false);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let effectsList = $derived(data.effects || []);

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
    if (filterInitialized && !medtool && !isCreateMode) {
      if ((additional.type || null) !== untrack(() => selectedFilter)) {
        selectedFilter = additional.type || null;
      }
    }
  });
  let medtoolEntityId = $derived(medtool?.Id ?? medtool?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, medtoolEntityId));
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
    { label: 'Tools', title: 'Medical Tools', type: 'tools' },
    { label: 'Chips', title: 'Medical Chips', type: 'chips' }
  ];

  // Type name mapping
  function getTypeName(type) {
    switch (type) {
      case 'tools': return 'Medical Tool';
      case 'chips': return 'Medical Chip';
      default: return 'Medical Tool';
    }
  }

  // Entity type for editing
  function getEntityType(type) {
    switch (type) {
      case 'tools': return 'MedicalTool';
      case 'chips': return 'MedicalChip';
      default: return 'MedicalTool';
    }
  }

  // Empty entity template for create mode (type-specific)
  function getEmptyEntity(type) {
    const base = {
      Name: '',
      Properties: {
        Description: '',
        Weight: 0,
        MaxHeal: 0,
        MinHeal: 0,
        UsesPerMinute: 0,
        Economy: {
          MaxTT: 0,
          MinTT: 0,
          Decay: 0
        },
        Skill: {
          IsSiB: false,
          LearningIntervalStart: null,
          LearningIntervalEnd: null
        }
      },
      EffectsOnEquip: [],
      EffectsOnUse: []
    };

    if (type === 'tools') {
      base.Tiers = [];
    }

    if (type === 'chips') {
      base.Properties.Range = 0;
      base.Properties.Economy.AmmoBurn = 0;
      base.Properties.Mindforce = {
        Level: 0,
        Concentration: 0,
        Cooldown: 0,
        CooldownGroup: null
      };
    }

    return base;
  }

  // ========== WIKI EDIT STATE ==========
  // Initialize edit state when user/entity changes
  $effect(() => {
    if (user) {
      const entityType = getEntityType(additional.type);
      const emptyEntity = getEmptyEntity(additional.type);
      const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
      initEditState(medtool || emptyEntity, entityType, isCreateMode, editChange);
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
      : medtool);

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
    href: selectedFilter === btn.type ? '/items/medicaltools' : `/items/medicaltools/${btn.type}`
  })));

  // All column definitions for medical tools
  const columnDefs = {
    type: {
      key: 'type',
      header: 'Type',
      width: '60px',
      filterPlaceholder: 'Tool',
      getValue: (item) => item._type === 'tools' ? 'Tool' : 'Chip',
      format: (v) => v || '-'
    },
    interval: {
      key: 'interval',
      header: 'Interval',
      width: '60px',
      filterPlaceholder: '<5',
      getValue: (item) => getReload(item),
      format: (v) => v != null ? `${v.toFixed(2)}s` : '-'
    },
    upm: {
      key: 'upm',
      header: 'Uses',
      width: '50px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.UsesPerMinute,
      format: (v) => v != null ? clampDecimals(v, 0, 1) : '-'
    },
    mfLevel: {
      key: 'mfLevel',
      header: 'MF Lvl',
      width: '55px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Mindforce?.Level ?? item.Properties?.Level,
      format: (v) => v != null ? v : '-'
    },
    concentration: {
      key: 'concentration',
      header: 'Conc.',
      width: '55px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Properties?.Mindforce?.Concentration,
      format: (v) => v != null ? `${v}s` : '-'
    },
    cooldown: {
      key: 'cooldown',
      header: 'CD',
      width: '50px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Properties?.Mindforce?.Cooldown,
      format: (v) => v != null ? `${v}s` : '-'
    },
    cooldownGroup: {
      key: 'cooldownGroup',
      header: 'CD Grp',
      width: '55px',
      filterPlaceholder: '>0',
      getValue: (item) => item.Properties?.Mindforce?.CooldownGroup,
      format: (v) => v != null ? v : '-'
    },
    hps: {
      key: 'hps',
      header: 'HPS',
      width: '50px',
      filterPlaceholder: '>10',
      getValue: (item) => getHps(item),
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    hpp: {
      key: 'hpp',
      header: 'HPP',
      width: '50px',
      filterPlaceholder: '>10',
      getValue: (item) => getHpp(item),
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    maxHeal: {
      key: 'maxHeal',
      header: 'Max Heal',
      width: '65px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.MaxHeal,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    minHeal: {
      key: 'minHeal',
      header: 'Min Heal',
      width: '65px',
      getValue: (item) => item.Properties?.MinHeal,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    cost: {
      key: 'cost',
      header: 'Cost',
      width: '50px',
      filterPlaceholder: '>0.5',
      getValue: (item) => getCost(item),
      format: (v) => v != null ? v.toFixed(4) : '-'
    },
    maxtt: {
      key: 'maxtt',
      header: 'Max TT',
      width: '60px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Economy?.MaxTT,
      format: (v) => v != null ? v.toFixed(2) : '-'
    },
    mintt: {
      key: 'mintt',
      header: 'Min TT',
      width: '55px',
      getValue: (item) => item.Properties?.Economy?.MinTT,
      format: (v) => v != null ? v.toFixed(2) : '-'
    },
    decay: {
      key: 'decay',
      header: 'Decay',
      width: '50px',
      filterPlaceholder: '>0.5',
      getValue: (item) => item.Properties?.Economy?.Decay,
      format: (v) => v != null ? v.toFixed(2) : '-'
    },
    ammo: {
      key: 'ammo',
      header: 'Ammo',
      width: '55px',
      getValue: (item) => item.Properties?.Economy?.AmmoBurn,
      format: (v) => v != null ? v : '-'
    },
    totalUses: {
      key: 'totalUses',
      header: 'Total Uses',
      width: '70px',
      filterPlaceholder: '>100',
      getValue: (item) => getTotalUses(item),
      format: (v) => v != null ? v : '-'
    },
    sib: {
      key: 'sib',
      header: 'SiB',
      width: '40px',
      getValue: (item) => item.Properties?.Skill?.IsSiB,
      format: (v) => v === true ? 'Yes' : v === false ? 'No' : '-'
    },
    minLevel: {
      key: 'minLevel',
      header: 'Min Lvl',
      width: '60px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Properties?.Skill?.LearningIntervalStart ?? null,
      format: (v) => v != null ? String(v) : '-'
    },
    maxLevel: {
      key: 'maxLevel',
      header: 'Max Lvl',
      width: '60px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Skill?.LearningIntervalEnd ?? null,
      format: (v) => v != null ? String(v) : '-'
    },
    range: {
      key: 'range',
      header: 'Range',
      width: '50px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Range,
      format: (v) => v != null ? v : '-'
    },
    weight: {
      key: 'weight',
      header: 'Weight',
      width: '55px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Properties?.Weight,
      format: (v) => v != null ? v : '-'
    }
  };

  function getNavTableColumns(type) {
    switch (type) {
      case 'tools':
      case 'chips':
        return [columnDefs.hps, columnDefs.hpp, columnDefs.interval, columnDefs.upm, columnDefs.mfLevel];
      default:
        return [columnDefs.type, columnDefs.hps, columnDefs.hpp, columnDefs.interval, columnDefs.upm];
    }
  }

  function getNavFullWidthColumns(type) {
    switch (type) {
      case 'tools':
        return [columnDefs.hps, columnDefs.hpp, columnDefs.interval, columnDefs.upm, columnDefs.cost, columnDefs.maxtt, columnDefs.maxHeal, columnDefs.decay, columnDefs.sib, columnDefs.minLevel, columnDefs.maxLevel, columnDefs.cooldown, columnDefs.cooldownGroup, columnDefs.weight];
      case 'chips':
        return [columnDefs.hps, columnDefs.hpp, columnDefs.interval, columnDefs.upm, columnDefs.cost, columnDefs.maxtt, columnDefs.maxHeal, columnDefs.range, columnDefs.decay, columnDefs.ammo, columnDefs.sib, columnDefs.minLevel, columnDefs.maxLevel, columnDefs.cooldown, columnDefs.cooldownGroup];
      default:
        return [columnDefs.type, columnDefs.hps, columnDefs.hpp, columnDefs.interval, columnDefs.upm, columnDefs.cost, columnDefs.maxtt, columnDefs.maxHeal, columnDefs.decay, columnDefs.sib, columnDefs.minLevel, columnDefs.maxLevel, columnDefs.cooldown, columnDefs.cooldownGroup];
    }
  }

  let navTableColumns = $derived(getNavTableColumns(selectedFilter));
  let navFullWidthColumns = $derived(getNavFullWidthColumns(selectedFilter));
  let allAvailableColumns = $derived(Object.values(columnDefs));
  let navPageTypeId = $derived(`medicaltools-${selectedFilter || 'all'}`);

  // Custom href generator for items
  function getItemHref(item, basePath) {
    const type = item._type || selectedFilter || additional.type;
    if (type) {
      return `/items/medicaltools/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Base path for navigation - uses selectedFilter so it persists
  let effectiveBasePath = $derived(selectedFilter
    ? `/items/medicaltools/${selectedFilter}`
    : '/items/medicaltools');

  // Create categories for the "New" dropdown
  let createCategories = $derived(typeButtons.map(btn => ({
    label: getTypeName(btn.type),
    href: `/items/medicaltools/${btn.type}`
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
    { label: 'Medical Tools', href: '/items/medicaltools' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + 's', href: `/items/medicaltools/${additional.type}` }] : []),
    ...(medtool ? [{ label: medtool.Name }] : [])
  ]);

  // SEO
  let seoDescription = $derived(medtool?.Properties?.Description ||
    `${medtool?.Name || 'Medical Tool'} - ${getTypeName(additional.type)} in Entropia Universe.`);

  let canonicalUrl = $derived(medtool
    ? `https://entropianexus.com/items/medicaltools/${additional.type}/${encodeURIComponentSafe(medtool.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/medicaltools/${additional.type}`
    : 'https://entropianexus.com/items/medicaltools');

  // Image URL for SEO
  let entityImageUrl = $derived(medtool?.Id && additional.type
    ? `/api/img/${getEntityType(additional.type).toLowerCase()}/${medtool.Id}`
    : null);

  // ========== CALCULATION FUNCTIONS ==========
  function getCost(item) {
    if (!item?.Properties?.Economy?.Decay) return null;
    return item.Properties.Economy.Decay + (item.Properties.Economy.AmmoBurn ?? 0) / 100;
  }

  function getEffectiveHealing(item) {
    if (item?.Properties?.MaxHeal == null || item?.Properties?.MinHeal == null) return null;
    return (item.Properties.MaxHeal + item.Properties.MinHeal) / 2;
  }

  function getReload(item) {
    if (!item?.Properties?.UsesPerMinute) return null;
    return 60 / item.Properties.UsesPerMinute;
  }

  function getHps(item) {
    const reload = getReload(item);
    const effectiveHealing = getEffectiveHealing(item);
    if (reload == null || effectiveHealing == null) return null;
    return effectiveHealing / reload;
  }

  function getHpp(item) {
    const cost = getCost(item);
    const effectiveHealing = getEffectiveHealing(item);
    if (cost == null || effectiveHealing == null) return null;
    return effectiveHealing / cost;
  }

  function getTotalUses(item) {
    if (!item?.Properties?.Economy?.MaxTT || !item?.Properties?.Economy?.Decay) return null;
    const maxTT = item.Properties.Economy.MaxTT;
    const minTT = item.Properties.Economy.MinTT ?? 0;
    const decay = item.Properties.Economy.Decay;
    return Math.floor((maxTT - minTT) / (decay / 100));
  }

  // ========== COMPUTED VALUES ========== (use activeEntity for live updates)
  let cost = $derived(getCost(activeEntity));
  let reload = $derived(getReload(activeEntity));
  let hps = $derived(getHps(activeEntity));
  let hpp = $derived(getHpp(activeEntity));
  let totalUses = $derived(getTotalUses(activeEntity));
  let cyclePerRepair = $derived(totalUses && cost ? totalUses * (cost / 100) : null);
  let cyclePerHour = $derived(reload && cost ? (3600 / reload) * (cost / 100) : null);
  let timeToBreak = $derived(cyclePerHour > 0 && cyclePerRepair ? cyclePerRepair / cyclePerHour : null);

  // Check for tiering (tools only, non-L items)
  let hasTiering = $derived(additional.type === 'tools' && activeEntity && !hasItemTag(activeEntity.Name, 'L'));

  // ========== RELOAD/USES TOGGLE ==========
  let showReload = $state(true);
  let showReloadEffective = $derived($editMode ? false : showReload);

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-medicaltools-show-reload');
      if (stored !== null) {
        showReload = stored === 'true';
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function toggleReloadUses() {
    showReload = !showReload;
    try {
      localStorage.setItem('wiki-medicaltools-show-reload', String(showReload));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    tiering: true,
    marketPrices: true,
    acquisition: true
  });

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-medicaltools-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-medicaltools-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }
</script>

<WikiSEO
  title={medtool?.Name || `${getTypeName(additional.type)}s`}
  description={seoDescription}
  entityType={getEntityType(additional.type)}
  entity={activeEntity}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={medtool}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Medical Tools"
  {breadcrumbs}
  entity={activeEntity}
  basePath={effectiveBasePath}
  {navItems}
  {navFilters}
  {navTableColumns}
  {navFullWidthColumns}
  navAllAvailableColumns={allAvailableColumns}
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
  {#if medtool || isCreateMode}
    <!-- Pending Change Banner -->
    {#if $existingPendingChange && !$editMode}
      <PendingChangeBanner
        pendingChange={$existingPendingChange}
        viewing={$viewingPendingChange}
        onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
        entityLabel="medical tool"
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
            {#if activeEntity?.Properties?.Skill?.IsSiB}
              <span class="sib-badge">SiB</span>
            {/if}
            {#if activeEntity?.Properties?.IsRare}<span class="item-flag-badge rare">Rare</span>{/if}
            {#if activeEntity?.Properties?.IsUntradeable}<span class="item-flag-badge untradeable">Untradeable</span>{/if}
          </div>
        </div>

        <!-- Tier-1 Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">HPS</span>
            <span class="stat-value">{hps != null ? hps.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">HPP</span>
            <span class="stat-value">{hpp != null ? hpp.toFixed(4) : 'N/A'}</span>
          </div>
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
                suffix="kg"
                step={0.01}
              />
            </span>
          </div>
          {#if $editMode}
            <!-- In edit mode, always show Uses/min as editable -->
            <div class="stat-row">
              <span class="stat-label">Uses/min</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.UsesPerMinute}
                  path="Properties.UsesPerMinute"
                  type="number"
                  min={0}
                  step={0.01}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Reload</span>
              <span class="stat-value">{reload != null ? `${reload.toFixed(2)}s` : 'N/A'}</span>
            </div>
          {:else}
            <!-- In view mode, toggle between Reload and Uses/min -->
            <div class="stat-row toggleable" onclick={toggleReloadUses} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), e.currentTarget.click())} title="Click to toggle between Reload and Uses/min" role="button" tabindex="0">
              {#if showReloadEffective}
                <span class="stat-label">Reload <span class="toggle-hint">⇄</span></span>
                <span class="stat-value">{reload != null ? `${reload.toFixed(2)}s` : 'N/A'}</span>
              {:else}
                <span class="stat-label">Uses/min <span class="toggle-hint">⇄</span></span>
                <span class="stat-value">{activeEntity?.Properties?.UsesPerMinute ?? 'N/A'}</span>
              {/if}
            </div>
          {/if}
          {#if additional.type === 'chips'}
            <div class="stat-row">
              <span class="stat-label">Range</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Range}
                  path="Properties.Range"
                  type="number"
                  suffix="m"
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

        <!-- Healing Stats -->
        <div class="stats-section">
          <h4 class="section-title">Healing</h4>
          <div class="stat-row">
            <span class="stat-label">HPS</span>
            <span class="stat-value highlight">{hps != null ? hps.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max. Heal</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.MaxHeal}
                path="Properties.MaxHeal"
                type="number"
                suffix=" HP"
                step={0.01}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min. Heal</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.MinHeal}
                path="Properties.MinHeal"
                type="number"
                suffix=" HP"
                step={0.01}
              />
            </span>
          </div>
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">HPP</span>
            <span class="stat-value highlight">{hpp != null ? hpp.toFixed(4) : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max. TT</span>
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
          <div class="stat-row">
            <span class="stat-label">Min. TT</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Economy?.MinTT}
                path="Properties.Economy.MinTT"
                type="number"
                suffix=" PED"
                step={0.01}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Decay</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Economy?.Decay}
                path="Properties.Economy.Decay"
                type="number"
                suffix=" PEC"
                step={0.0001}
              />
            </span>
          </div>
          {#if additional.type === 'chips'}
            <div class="stat-row">
              <span class="stat-label">Ammo</span>
              <span class="stat-value">{activeEntity?.Ammo?.Name || 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Ammo Burn</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Economy?.AmmoBurn}
                  path="Properties.Economy.AmmoBurn"
                  type="number"
                />
              </span>
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Cost</span>
            <span class="stat-value">{cost != null ? `${cost.toFixed(4)} PEC` : 'N/A'}</span>
          </div>
          {#if totalUses}
            <div class="stat-row">
              <span class="stat-label">Total Uses</span>
              <span class="stat-value">{totalUses}</span>
            </div>
          {/if}
        </div>

        <!-- Mindforce Stats (chips only) -->
        {#if additional.type === 'chips'}
          <div class="stats-section">
            <h4 class="section-title">Mindforce</h4>
            <div class="stat-row">
              <span class="stat-label">Level</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Mindforce?.Level}
                  path="Properties.Mindforce.Level"
                  type="number"
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Concentration</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Mindforce?.Concentration}
                  path="Properties.Mindforce.Concentration"
                  type="number"
                  suffix="s"
                  step={0.1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cooldown</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Mindforce?.Cooldown}
                  path="Properties.Mindforce.Cooldown"
                  type="number"
                  suffix="s"
                  step={0.1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cooldown Group</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Mindforce?.CooldownGroup}
                  path="Properties.Mindforce.CooldownGroup"
                  type="number"
                  min={1}
                  step={1}
                />
              </span>
            </div>
          </div>
        {/if}

        <!-- Skilling Info -->
        <div class="stats-section">
          <h4 class="section-title">Skilling</h4>
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
          <div class="stat-row">
            <span class="stat-label">Profession</span>
            <span class="stat-value">
              <a href={getTypeLink(additional.type === 'chips' ? 'Biotropic' : 'Paramedic', 'Profession')} class="profession-link">
                {additional.type === 'chips' ? 'Biotropic' : 'Paramedic'}
              </a>
            </span>
          </div>
          {#if activeEntity?.Properties?.Skill?.IsSiB && (activeEntity?.Properties?.Skill?.LearningIntervalStart !== null || activeEntity?.Properties?.Skill?.LearningIntervalEnd !== null || $editMode)}
            <div class="stat-row indent">
              <span class="stat-label">Level Range</span>
              <span class="stat-value">
                {#if $editMode}
                  <span class="interval-edit">
                    <InlineEdit
                      value={activeEntity?.Properties?.Skill?.LearningIntervalStart}
                      path="Properties.Skill.LearningIntervalStart"
                      type="number"
                      min={0}
                      step={0.1}
                      placeholder="Min"
                    />
                    <span class="interval-sep">-</span>
                    <InlineEdit
                      value={activeEntity?.Properties?.Skill?.LearningIntervalEnd}
                      path="Properties.Skill.LearningIntervalEnd"
                      type="number"
                      min={0}
                      step={0.1}
                      placeholder="Max"
                    />
                  </span>
                {:else}
                  {activeEntity?.Properties?.Skill?.LearningIntervalStart ?? '?'} - {activeEntity?.Properties?.Skill?.LearningIntervalEnd ?? '?'}
                {/if}
              </span>
            </div>
          {/if}
        </div>

        <!-- Misc Stats -->
        {#if cyclePerRepair || cyclePerHour || timeToBreak}
          <div class="stats-section">
            <h4 class="section-title">Misc</h4>
            {#if cyclePerRepair}
              <div class="stat-row">
                <span class="stat-label">PED/repair</span>
                <span class="stat-value">{cyclePerRepair.toFixed(2)} PED</span>
              </div>
            {/if}
            {#if cyclePerHour}
              <div class="stat-row">
                <span class="stat-label">PED/h</span>
                <span class="stat-value">{cyclePerHour.toFixed(2)} PED</span>
              </div>
            {/if}
            {#if timeToBreak}
              <div class="stat-row">
                <span class="stat-label">Time to break</span>
                <span class="stat-value">{timeToBreak.toFixed(2)}h</span>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Effects (if any) -->
        {#if (activeEntity?.EffectsOnEquip?.length > 0) || (activeEntity?.EffectsOnUse?.length > 0) || $editMode}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects</h4>
            <div class="effects-combined">
              <EffectsEditor
                effects={activeEntity?.EffectsOnEquip || []}
                fieldName="EffectsOnEquip"
                availableEffects={effectsList}
                effectType="equip"
                showEmpty={$editMode}
              />
              <EffectsEditor
                effects={activeEntity?.EffectsOnUse || []}
                fieldName="EffectsOnUse"
                availableEffects={effectsList}
                effectType="use"
                showEmpty={$editMode}
              />
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
          {:else if activeEntity?.Properties?.Description}
            <div class="description-content">{@html activeEntity.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || 'This medical tool'} is a {getTypeName(additional.type).toLowerCase()} used in Entropia Universe.
            </div>
          {/if}
        </div>

        <!-- Tiering Section (tools only, non-L items) -->
        {#if hasTiering}
          <DataSection
            title="Tiers"
            icon=""
            bind:expanded={panelStates.tiering}
            subtitle="{(additional.tierInfo?.length || activeEntity?.Tiers?.length || 0)} tiers"
            ontoggle={savePanelStates}
          >
            <TieringEditor entity={activeEntity} entityType="MedicalTool" tierInfo={additional.tierInfo || []} />
          </DataSection>
        {/if}

        <!-- Market Prices Section -->
        {#if !activeEntity?.Properties?.IsUntradeable}
        <MarketPriceSection
          itemId={activeEntity?.ItemId}
          itemName={activeEntity?.Name}
          entityType={getEntityType(additional.type)}
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
      <h2>{additional.type ? getTypeName(additional.type) + 's' : 'Medical Tools'}</h2>
      <p>Select a {additional.type ? getTypeName(additional.type).toLowerCase() : 'medical tool'} from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .sib-badge {
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
    background-color: #10b981;
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
  }

  .stat-value.highlight {
    color: #4ade80;
    font-weight: 600;
  }

  /* Combined effects layout (equip + use side by side) */
  .effects-combined {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 16px;
  }

  .effects-combined :global(.effects-editor) {
    flex: 1;
    min-width: 200px;
  }

  .effects-section {
    padding: 12px;
  }

  @media (max-width: 899px) {
    .effects-combined {
      flex-direction: column;
    }
  }
</style>

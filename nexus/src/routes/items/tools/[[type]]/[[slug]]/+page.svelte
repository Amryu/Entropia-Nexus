<!--
  @component Tools Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: All numeric stats organized by section
  Article: Description → Tiering → Acquisition

  Handles 7 tool subtypes: refiners, scanners, finders, excavators, teleportationchips, effectchips, misctools
  Supports full wiki editing.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { hasItemTag, encodeURIComponentSafe, clampDecimals, getTypeLink, getTimeString, getLatestPendingUpdate } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
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
  import TieringEditor from '$lib/components/wiki/TieringEditor.svelte';
  import Acquisition from '$lib/components/wiki/Acquisition.svelte';

  // Wiki edit components
  import EffectsEditor from '$lib/components/wiki/EffectsEditor.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  export let data;

  $: tool = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};
  $: pendingChange = data.pendingChange;
  $: existingChange = data.existingChange;
  $: isCreateMode = data.isCreateMode || false;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];

  // Local filter state - decoupled from URL
  // Filter persists through item navigation; only changes when explicitly clicking filter buttons
  let selectedFilter = null;
  let filterInitialized = false;

  // Initialize filter from URL once on first data load
  $: if (!filterInitialized) {
    selectedFilter = additional.type || null;
    filterInitialized = true;
  }

  // Sync filter only when on list view (no item selected, not create mode)
  $: if (filterInitialized && !tool && !isCreateMode) {
    if ((additional.type || null) !== selectedFilter) {
      selectedFilter = additional.type || null;
    }
  }
  $: effects = data.effects || [];
  $: professions = data.professions || [];
  $: professionOptions = professions.map(p => ({ value: p.Name, label: p.Name })).sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
  $: toolEntityId = tool?.Id ?? tool?.ItemId;
  $: userPendingUpdate = getLatestPendingUpdate(userPendingUpdates, toolEntityId);
  $: resolvedPendingChange = userPendingUpdate || pendingChange;
  $: canUsePendingChange = !!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve')));

  // Permission check - verified users and admins can edit
  $: canEdit = user?.verified || user?.grants?.includes('wiki.edit');

  // For multi-type pages, data.items is an object keyed by type
  // When no filter is selected, show all items from all types (with _type added for linking)
  $: allItems = (() => {
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
  })();

  // Type navigation buttons
  const typeButtons = [
    { label: 'Refiners', title: 'Refiners', type: 'refiners' },
    { label: 'Scanners', title: 'Scanners', type: 'scanners' },
    { label: 'Finders', title: 'Finders', type: 'finders' },
    { label: 'Excavators', title: 'Excavators', type: 'excavators' },
    { label: 'TP Chips', title: 'Teleportation Chips', type: 'teleportationchips' },
    { label: 'Effect Chips', title: 'Effect Chips', type: 'effectchips' },
    { label: 'Misc. Tools', title: 'Misc. Tools', type: 'misctools' }
  ];

  // When misctools profession is cleared, also clear skill fields
  // InlineEdit already updates Profession.Name via its own path prop
  function handleMiscToolProfessionChange(e) {
    if (!e.detail.value) {
      updateField('Properties.Skill.IsSiB', null);
      updateField('Properties.Skill.LearningIntervalStart', null);
      updateField('Properties.Skill.LearningIntervalEnd', null);
    }
  }

  // Type name mapping
  function getTypeName(type) {
    switch (type) {
      case 'refiners': return 'Refiner';
      case 'scanners': return 'Scanner';
      case 'finders': return 'Finder';
      case 'excavators': return 'Excavator';
      case 'teleportationchips': return 'Teleportation Chip';
      case 'effectchips': return 'Effect Chip';
      case 'misctools': return 'Misc. Tool';
      default: return 'Tool';
    }
  }

  // Entity type for editing
  function getEntityType(type) {
    switch (type) {
      case 'refiners': return 'Refiner';
      case 'scanners': return 'Scanner';
      case 'finders': return 'Finder';
      case 'excavators': return 'Excavator';
      case 'teleportationchips': return 'TeleportationChip';
      case 'effectchips': return 'EffectChip';
      case 'misctools': return 'MiscTool';
      default: return 'Tool';
    }
  }

  // Empty entity template for create mode (type-specific)
  function getEmptyEntity(type) {
    const base = {
      Name: '',
      Properties: {
        Description: '',
        Weight: 0,
        Economy: {
          MaxTT: 0,
          MinTT: 0,
          Decay: 0
        }
      }
    };

    switch (type) {
      case 'refiners':
        // Basic tools - just economy
        break;
      case 'misctools':
        base.Properties.Type = '';
        base.Properties.Skill = {
          IsSiB: null,
          LearningIntervalStart: null,
          LearningIntervalEnd: null
        };
        base.Profession = { Name: null };
        break;
      case 'scanners':
        base.Properties.Range = 0;
        base.Properties.UsesPerMinute = 0;
        break;
      case 'finders':
        base.Properties.Depth = 0;
        base.Properties.Range = 0;
        base.Properties.Economy.AmmoBurn = 0;
        base.Properties.Skill = {
          IsSiB: false,
          LearningIntervalStart: null,
          LearningIntervalEnd: null
        };
        break;
      case 'excavators':
        base.Properties.Efficiency = 0;
        base.Properties.UsesPerMinute = 0;
        base.Properties.Skill = {
          IsSiB: false,
          LearningIntervalStart: null,
          LearningIntervalEnd: null
        };
        break;
      case 'teleportationchips':
      case 'effectchips':
        base.Properties.Range = 0;
        base.Properties.UsesPerMinute = 0;
        base.Properties.Economy.AmmoBurn = 0;
        base.Ammo = { Name: 'Mind Essence' };
        base.Properties.Mindforce = {
          Level: 0,
          Concentration: 0,
          Cooldown: 0,
          CooldownGroup: null
        };
        base.Properties.Skill = {
          IsSiB: false,
          LearningIntervalStart: null,
          LearningIntervalEnd: null
        };
        break;
    }

    return base;
  }

  // ========== WIKI EDIT STATE ==========
  // Initialize edit state when user/entity changes
  $: if (user) {
    const entityType = getEntityType(additional.type);
    const emptyEntity = getEmptyEntity(additional.type);
    const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
    initEditState(tool || emptyEntity, entityType, isCreateMode, editChange);
  }

  // Set pending change when it exists
  $: if (resolvedPendingChange) {
    setExistingPendingChange(resolvedPendingChange);
    if (user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))) {
      setViewingPendingChange(true);
    }
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }

  // Active entity: in edit mode use currentEntity, when viewing pending use its data, otherwise use original
  $: activeEntity = $editMode
    ? $currentEntity
    : $viewingPendingChange && $existingPendingChange?.data
      ? $existingPendingChange.data
      : tool;

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters - type buttons
  // Uses selectedFilter for active state (local filter state, not URL-based)
  $: navFilters = typeButtons.map(btn => ({
    label: btn.label,
    title: btn.title,
    type: btn.type,
    active: selectedFilter === btn.type,
    href: selectedFilter === btn.type ? '/items/tools' : `/items/tools/${btn.type}`
  }));

  // Type-specific sidebar table columns
  function getNavTableColumns(type) {
    const usesColumn = {
      key: 'upm',
      header: 'Uses/Minute',
      width: '55px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.UsesPerMinute,
      format: (v) => v != null ? clampDecimals(v, 0, 1) : '-'
    };

    const decayColumn = {
      key: 'decay',
      header: 'Decay',
      width: '55px',
      filterPlaceholder: '<0.5',
      getValue: (item) => item.Properties?.Economy?.Decay,
      format: (v) => v != null ? v.toFixed(2) : '-'
    };

    const typeColumn = {
      key: 'toolType',
      header: 'Tool Type',
      width: '70px',
      filterPlaceholder: 'Finder',
      getValue: (item) => getTypeName(item._type || type),
      format: (v) => v || '-'
    };

    const rangeColumn = {
      key: 'range',
      header: 'Range',
      width: '55px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Range,
      format: (v) => v != null ? v : '-'
    };

    const depthColumn = {
      key: 'depth',
      header: 'Depth',
      width: '55px',
      filterPlaceholder: '>100',
      getValue: (item) => item.Properties?.Depth,
      format: (v) => v != null ? v : '-'
    };

    const avgDepthColumn = {
      ...depthColumn,
      key: 'avgDepth',
      header: 'Average Depth'
    };

    const costColumn = {
      key: 'cost',
      header: 'Cost per Use',
      width: '90px',
      filterPlaceholder: '<1',
      getValue: (item) => getCost(item),
      format: (v) => v != null ? v.toFixed(2) : '-'
    };

    switch (type) {
      case 'scanners':
        return [usesColumn, decayColumn, rangeColumn, depthColumn];
      case 'finders':
      case 'excavators':
        return [usesColumn, decayColumn, avgDepthColumn, rangeColumn];
      case 'teleportationchips':
      case 'effectchips':
        return [usesColumn, decayColumn, costColumn, rangeColumn];
      case 'refiners':
      case 'misctools':
        return [usesColumn, decayColumn];
      default:
        return [typeColumn, usesColumn, decayColumn];
    }
  }

  $: navTableColumns = getNavTableColumns(selectedFilter);

  // Full column definitions for all tool types
  const columnDefs = {
    toolType: { key: 'toolType', header: 'Tool Type', width: '70px', filterPlaceholder: 'Finder', getValue: (item) => getTypeName(item._type || additional.type), format: (v) => v || '-' },
    upm: { key: 'upm', header: 'Uses/Min', width: '55px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.UsesPerMinute, format: (v) => v != null ? clampDecimals(v, 0, 1) : '-' },
    decay: { key: 'decay', header: 'Decay', width: '55px', filterPlaceholder: '<0.5', getValue: (item) => item.Properties?.Economy?.Decay, format: (v) => v != null ? v.toFixed(2) : '-' },
    range: { key: 'range', header: 'Range', width: '55px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Range, format: (v) => v != null ? v : '-' },
    depth: { key: 'depth', header: 'Depth', width: '55px', filterPlaceholder: '>100', getValue: (item) => item.Properties?.Depth, format: (v) => v != null ? v : '-' },
    efficiency: { key: 'efficiency', header: 'Effic.', width: '55px', filterPlaceholder: '>50', getValue: (item) => item.Properties?.Efficiency, format: (v) => v != null ? v : '-' },
    effPerPed: { key: 'effPerPed', header: 'Eff/PED', width: '60px', filterPlaceholder: '>10', getValue: (item) => calcEfficiencyPerPed(item), format: (v) => v != null ? v.toFixed(1) : '-' },
    cost: { key: 'cost', header: 'Cost/Use', width: '60px', filterPlaceholder: '<1', getValue: (item) => getCost(item), format: (v) => v != null ? v.toFixed(2) : '-' },
    maxTT: { key: 'maxTT', header: 'Max TT', width: '60px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 2, 4) : '-' },
    minTT: { key: 'minTT', header: 'Min TT', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Economy?.MinTT, format: (v) => v != null ? clampDecimals(v, 2, 4) : '-' },
    ammoBurn: { key: 'ammoBurn', header: 'Ammo Burn', width: '60px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Economy?.AmmoBurn, format: (v) => v != null ? v : '-' },
    totalUses: { key: 'totalUses', header: 'Uses', width: '55px', filterPlaceholder: '>100', getValue: (item) => getTotalUses(item), format: (v) => v != null ? v.toLocaleString() : '-' },
    weight: { key: 'weight', header: 'Weight', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Weight, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' },
    sib: { key: 'sib', header: 'SiB', width: '40px', filterPlaceholder: 'Yes', getValue: (item) => item.Properties?.Skill?.IsSiB, format: (v) => v ? 'Yes' : 'No' },
    minLevel: { key: 'minLevel', header: 'Min Lvl', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Skill?.LearningIntervalStart, format: (v) => v != null ? v : '-' },
    maxLevel: { key: 'maxLevel', header: 'Max Lvl', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Skill?.LearningIntervalEnd, format: (v) => v != null ? v : '-' },
    mfLevel: { key: 'mfLevel', header: 'MF Lvl', width: '55px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Mindforce?.Level ?? item.Properties?.Level, format: (v) => v != null ? v : '-' },
    concentration: { key: 'concentration', header: 'Conc.', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Mindforce?.Concentration, format: (v) => v != null ? `${v}s` : '-' },
    cooldown: { key: 'cooldown', header: 'CD', width: '50px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Mindforce?.Cooldown, format: (v) => v != null ? `${v}s` : '-' },
    cooldownGroup: { key: 'cooldownGroup', header: 'CD Grp', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Mindforce?.CooldownGroup, format: (v) => v != null ? v : '-' }
  };

  function getNavFullWidthColumns(type) {
    switch (type) {
      case 'scanners':
        return [columnDefs.upm, columnDefs.decay, columnDefs.range, columnDefs.depth, columnDefs.maxTT, columnDefs.minTT, columnDefs.totalUses, columnDefs.weight];
      case 'finders':
        return [columnDefs.upm, columnDefs.decay, columnDefs.depth, columnDefs.range, columnDefs.ammoBurn, columnDefs.cost, columnDefs.maxTT, columnDefs.totalUses, columnDefs.sib, columnDefs.minLevel, columnDefs.maxLevel];
      case 'excavators':
        return [columnDefs.upm, columnDefs.decay, columnDefs.efficiency, columnDefs.effPerPed, columnDefs.maxTT, columnDefs.totalUses, columnDefs.sib, columnDefs.minLevel, columnDefs.maxLevel, columnDefs.weight];
      case 'teleportationchips':
      case 'effectchips':
        return [columnDefs.upm, columnDefs.decay, columnDefs.cost, columnDefs.range, columnDefs.ammoBurn, columnDefs.maxTT, columnDefs.sib, columnDefs.minLevel, columnDefs.maxLevel, columnDefs.cooldown, columnDefs.cooldownGroup];
      case 'refiners':
        return [columnDefs.upm, columnDefs.decay, columnDefs.maxTT, columnDefs.minTT, columnDefs.totalUses, columnDefs.weight];
      case 'misctools':
        return [columnDefs.upm, columnDefs.decay, columnDefs.maxTT, columnDefs.minTT, columnDefs.totalUses, columnDefs.sib, columnDefs.minLevel, columnDefs.maxLevel, columnDefs.weight];
      default:
        return [columnDefs.toolType, columnDefs.upm, columnDefs.decay, columnDefs.maxTT, columnDefs.weight];
    }
  }

  $: navFullWidthColumns = getNavFullWidthColumns(selectedFilter);
  $: allAvailableColumns = Object.values(columnDefs);
  $: navPageTypeId = `tools-${selectedFilter || 'all'}`;

  // Custom href generator for items - handles _type property for "all items" view
  function getItemHref(item, basePath) {
    const type = item._type || selectedFilter || additional.type;
    if (type) {
      return `/items/tools/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Base path for navigation - uses selectedFilter so it persists through navigation
  $: effectiveBasePath = selectedFilter
    ? `/items/tools/${selectedFilter}`
    : '/items/tools';

  // Filter pending creates by selected filter type
  $: filteredPendingCreates = selectedFilter
    ? (userPendingCreates || []).filter(change => {
        const entityType = getEntityType(selectedFilter);
        return change.entity === entityType;
      })
    : userPendingCreates || [];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Tools', href: '/items/tools' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + 's', href: `/items/tools/${additional.type}` }] : []),
    ...(tool ? [{ label: tool.Name }] : [])
  ];

  // SEO
  $: seoDescription = tool?.Properties?.Description ||
    `${tool?.Name || 'Tool'} - ${getTypeName(additional.type)} in Entropia Universe.`;

  $: canonicalUrl = tool
    ? `https://entropianexus.com/items/tools/${additional.type}/${encodeURIComponentSafe(tool.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/tools/${additional.type}`
    : 'https://entropianexus.com/items/tools';

  // Image URL for SEO (use entity type in lowercase format)
  $: entityImageUrl = tool?.Id && additional.type
    ? `/api/img/${getEntityType(additional.type).toLowerCase()}/${tool.Id}`
    : null;

  // Check if item is tierable (not Limited)
  $: isTierable = activeEntity && !hasItemTag(activeEntity.Name, 'L') && ['finders', 'excavators'].includes(additional.type);

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    tiering: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-tool-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-tool-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== RELOAD/USES TOGGLE ==========
  let showReload = true;
  $: showReloadEffective = $editMode ? false : showReload;
  const mindforceAmmoOptions = [
    { value: 'Mind Essence', label: 'Mind Essence' },
    { value: 'Synthetic Mind Essence', label: 'Synthetic Mind Essence' },
    { value: 'Light Mind Essence', label: 'Light Mind Essence' }
  ];

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-tool-show-reload');
      if (stored !== null) {
        showReload = stored === 'true';
      }
    } catch (e) {}
  });

  function toggleReloadUses() {
    showReload = !showReload;
    try {
      localStorage.setItem('wiki-tool-show-reload', String(showReload));
    } catch (e) {}
  }

  // ========== CALCULATOR FUNCTIONS ==========
  function getTotalUses(item) {
    const maxTT = item?.Properties?.Economy?.MaxTT;
    const minTT = item?.Properties?.Economy?.MinTT ?? 0;
    const decay = item?.Properties?.Economy?.Decay;
    if (maxTT == null || decay == null || decay === 0) return null;
    return Math.floor((maxTT - minTT) / (decay / 100));
  }

  function getCost(item) {
    const decay = item?.Properties?.Economy?.Decay;
    const ammoBurn = item?.Properties?.Economy?.AmmoBurn;
    if (decay == null || ammoBurn == null) return null;
    return decay + ammoBurn / 100;
  }

  function getReload(item) {
    const upm = item?.Properties?.UsesPerMinute;
    if (upm == null || upm === 0) return null;
    return 60 / upm;
  }

  function calcEfficiencyPerPed(item) {
    const eff = item?.Properties?.Efficiency;
    const decay = item?.Properties?.Economy?.Decay;
    if (eff == null || decay == null || decay === 0) return null;
    return eff / (decay / 100);
  }

  function calcEfficiencyPerSec(item) {
    const eff = item?.Properties?.Efficiency;
    const reload = getReload(item);
    if (eff == null || reload == null || reload === 0) return null;
    return eff / reload;
  }

  // Reactive calculations (use activeEntity for live editing updates)
  $: totalUses = getTotalUses(activeEntity);
  $: cost = getCost(activeEntity);
  $: reload = getReload(activeEntity);
  $: effPerPed = calcEfficiencyPerPed(activeEntity);
  $: effPerSec = calcEfficiencyPerSec(activeEntity);
</script>

<WikiSEO
  title={tool?.Name || `${getTypeName(additional.type)}s`}
  description={seoDescription}
  entityType={getEntityType(additional.type)}
  entity={activeEntity}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={tool}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Tools"
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
  canEdit={canEdit && !!additional.type}
  {canCreateNew}
  userPendingCreates={filteredPendingCreates}
  {userPendingUpdates}
>
  {#if tool || isCreateMode}
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
              placeholder="Enter name..."
            />
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge">{getTypeName(additional.type)}</span>
          </div>
        </div>

        <!-- Tier-1 Stats (type-specific primary stats) -->
        <div class="stats-section tier-1">
          {#if additional.type === 'refiners'}
            <div class="stat-row primary">
              <span class="stat-label">TT Value</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.MaxTT != null ? `${clampDecimals(activeEntity.Properties.Economy.MaxTT, 2, 4)} PED` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Decay</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.Decay != null ? `${activeEntity.Properties.Economy.Decay.toFixed(4)} PEC` : 'N/A'}</span>
            </div>
          {:else if additional.type === 'scanners'}
            <div class="stat-row primary">
              <span class="stat-label">Range</span>
              <span class="stat-value">{activeEntity?.Properties?.Range != null ? `${activeEntity.Properties.Range}m` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Uses/min</span>
              <span class="stat-value">{activeEntity?.Properties?.UsesPerMinute != null ? clampDecimals(activeEntity.Properties.UsesPerMinute, 0, 2) : 'N/A'}</span>
            </div>
          {:else if additional.type === 'finders'}
            <div class="stat-row primary">
              <span class="stat-label">Depth</span>
              <span class="stat-value">{activeEntity?.Properties?.Depth != null ? `${activeEntity.Properties.Depth}m` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Range</span>
              <span class="stat-value">{activeEntity?.Properties?.Range != null ? `${activeEntity.Properties.Range}m` : 'N/A'}</span>
            </div>
          {:else if additional.type === 'excavators'}
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{activeEntity?.Properties?.Efficiency ?? 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Eff/PED</span>
              <span class="stat-value">{effPerPed != null ? effPerPed.toFixed(1) : 'N/A'}</span>
            </div>
          {:else if additional.type === 'teleportationchips'}
            <div class="stat-row primary">
              <span class="stat-label">Range</span>
              <span class="stat-value">{activeEntity?.Properties?.Range != null ? `${activeEntity.Properties.Range}km` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Cost/Use</span>
              <span class="stat-value">{cost != null ? `${cost.toFixed(2)} PEC` : 'N/A'}</span>
            </div>
          {:else if additional.type === 'effectchips'}
            <div class="stat-row primary">
              <span class="stat-label">Range</span>
              <span class="stat-value">{activeEntity?.Properties?.Range != null ? `${activeEntity.Properties.Range}m` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Cost/Use</span>
              <span class="stat-value">{cost != null ? `${cost.toFixed(2)} PEC` : 'N/A'}</span>
            </div>
          {:else}
            <!-- misctools -->
            <div class="stat-row primary">
              <span class="stat-label">TT Value</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.MaxTT != null ? `${clampDecimals(activeEntity.Properties.Economy.MaxTT, 2, 4)} PED` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Decay</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.Decay != null ? `${activeEntity.Properties.Economy.Decay.toFixed(4)} PEC` : 'N/A'}</span>
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
                suffix="kg"
                step={0.01}
              />
            </span>
          </div>
          {#if additional.type === 'misctools'}
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
          {#if additional.type === 'teleportationchips' || additional.type === 'effectchips'}
            <div class="stat-row">
              <span class="stat-label">Range</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Range}
                  path="Properties.Range"
                  type="number"
                  suffix={additional.type === 'teleportationchips' ? 'km' : 'm'}
                />
              </span>
            </div>
          {/if}
          {#if additional.type !== 'refiners' && additional.type !== 'misctools'}
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div class="stat-row toggleable" on:click={toggleReloadUses} title="Click to toggle between Reload and Uses/min">
              {#if showReloadEffective}
                <span class="stat-label">Reload <span class="toggle-hint">⇄</span></span>
                <span class="stat-value">{reload != null ? `${reload.toFixed(2)}s` : 'N/A'}</span>
              {:else}
                <span class="stat-label">Uses/min <span class="toggle-hint">⇄</span></span>
                <span class="stat-value">
                  <InlineEdit
                    value={activeEntity?.Properties?.UsesPerMinute}
                    path="Properties.UsesPerMinute"
                    type="number"
                    step={0.1}
                  />
                </span>
              {/if}
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Total Uses</span>
            <span class="stat-value">{totalUses != null ? totalUses.toLocaleString() : 'N/A'}</span>
          </div>
        </div>

        <!-- Effects on Use (effect chips) -->
        {#if additional.type === 'effectchips' && (activeEntity?.EffectsOnUse?.length > 0 || $editMode)}
          <div class="stats-section effects-section">
            <EffectsEditor
              effects={activeEntity?.EffectsOnUse || []}
              fieldName="EffectsOnUse"
              availableEffects={effects}
              effectType="use"
              title="Effects on Use"
              showEmpty={$editMode}
            />
          </div>
        {/if}

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max TT</span>
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
            <span class="stat-label">Min TT</span>
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
          {#if additional.type === 'finders'}
            <div class="stat-row">
              <span class="stat-label">Ammo</span>
              <span class="stat-value">Survey Probe</span>
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
          {:else if additional.type === 'teleportationchips' || additional.type === 'effectchips'}
            <div class="stat-row">
              <span class="stat-label">Ammo</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Ammo?.Name || 'Mind Essence'}
                  path="Ammo.Name"
                  type="select"
                  options={mindforceAmmoOptions}
                />
              </span>
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
            <div class="stat-row">
              <span class="stat-label">Cost/Use</span>
              <span class="stat-value">{cost != null ? `${cost.toFixed(2)} PEC` : 'N/A'}</span>
            </div>
            {#if additional.type === 'teleportationchips' && activeEntity?.Properties?.Range}
              <div class="stat-row">
                <span class="stat-label">Cost/km</span>
                <span class="stat-value">{cost != null ? `${(cost / activeEntity.Properties.Range).toFixed(2)} PEC/km` : 'N/A'}</span>
              </div>
            {/if}
          {/if}
        </div>

        <!-- Mining Stats (finders/excavators) -->
        {#if additional.type === 'finders' || additional.type === 'excavators'}
          <div class="stats-section">
            <h4 class="section-title">Mining</h4>
            {#if additional.type === 'finders'}
              <div class="stat-row">
                <span class="stat-label">Depth</span>
                <span class="stat-value">
                  <InlineEdit
                    value={activeEntity?.Properties?.Depth}
                    path="Properties.Depth"
                    type="number"
                    suffix="m"
                  />
                </span>
              </div>
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
            {:else}
              <div class="stat-row">
                <span class="stat-label">Efficiency</span>
                <span class="stat-value">
                  <InlineEdit
                    value={activeEntity?.Properties?.Efficiency}
                    path="Properties.Efficiency"
                    type="number"
                  />
                </span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Efficiency/PED</span>
                <span class="stat-value">{effPerPed != null ? effPerPed.toFixed(1) : 'N/A'}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Efficiency/s</span>
                <span class="stat-value">{effPerSec != null ? effPerSec.toFixed(2) : 'N/A'}</span>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Mindforce Stats (TP/Effect chips) -->
        {#if additional.type === 'teleportationchips' || additional.type === 'effectchips'}
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
                  type="text"
                />
              </span>
            </div>
          </div>
        {/if}

        <!-- Skilling Info -->
        {#if additional.type !== 'scanners' && additional.type !== 'refiners'}
          <div class="stats-section">
            <h4 class="section-title">Skilling</h4>
            {#if additional.type !== 'misctools'}
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
            {/if}
            {#if additional.type === 'finders'}
              <div class="stat-row">
                <span class="stat-label">Professions</span>
                <span class="stat-value">
                  <a href={getTypeLink('Prospector', 'Profession')} class="profession-link">Prospector</a>,
                  <a href={getTypeLink('Surveyor', 'Profession')} class="profession-link">Surveyor</a>,
                  <a href={getTypeLink('Treasure Hunter', 'Profession')} class="profession-link">Treasure Hunter</a>
                </span>
              </div>
            {:else if additional.type === 'excavators'}
              <div class="stat-row">
                <span class="stat-label">Professions</span>
                <span class="stat-value">
                  <a href={getTypeLink('Driller', 'Profession')} class="profession-link">Driller</a>,
                  <a href={getTypeLink('Miner', 'Profession')} class="profession-link">Miner</a>,
                  <a href={getTypeLink('Archaeologist', 'Profession')} class="profession-link">Archaeologist</a>
                </span>
              </div>
            {:else if additional.type === 'teleportationchips'}
              <div class="stat-row">
                <span class="stat-label">Profession</span>
                <span class="stat-value">
                  <a href={getTypeLink('Translocator', 'Profession')} class="profession-link">Translocator</a>
                </span>
              </div>
            {:else if additional.type === 'misctools'}
              <div class="stat-row">
                <span class="stat-label">Profession</span>
                <span class="stat-value">
                  {#if $editMode}
                    <InlineEdit
                      value={activeEntity?.Profession?.Name}
                      path="Profession.Name"
                      type="select"
                      placeholder="None"
                      options={professionOptions}
                      on:change={handleMiscToolProfessionChange}
                    />
                  {:else if activeEntity?.Profession?.Name}
                    <a href={getTypeLink(activeEntity.Profession.Name, 'Profession')} class="profession-link">{activeEntity.Profession.Name}</a>
                  {:else}
                    N/A
                  {/if}
                </span>
              </div>
              {#if activeEntity?.Profession?.Name}
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
                  <span class="stat-label">Level Range</span>
                  <span class="stat-value">
                    <InlineEdit
                      value={activeEntity?.Properties?.Skill?.LearningIntervalStart}
                      path="Properties.Skill.LearningIntervalStart"
                      type="number"
                      step={0.1}
                    />
                    -
                    <InlineEdit
                      value={activeEntity?.Properties?.Skill?.LearningIntervalEnd}
                      path="Properties.Skill.LearningIntervalEnd"
                      type="number"
                      step={0.1}
                    />
                  </span>
                </div>
              {/if}
            {:else if activeEntity?.Profession?.Name}
              <div class="stat-row">
                <span class="stat-label">Profession</span>
                <span class="stat-value">
                  <a href={getTypeLink(activeEntity.Profession.Name, 'Profession')} class="profession-link">{activeEntity.Profession.Name}</a>
                </span>
              </div>
            {/if}
            {#if additional.type !== 'misctools'}
              <div class="stat-row">
                <span class="stat-label">Level Range</span>
                <span class="stat-value">
                  <InlineEdit
                    value={activeEntity?.Properties?.Skill?.LearningIntervalStart}
                    path="Properties.Skill.LearningIntervalStart"
                    type="number"
                    step={0.1}
                  />
                  -
                  <InlineEdit
                    value={activeEntity?.Properties?.Skill?.LearningIntervalEnd}
                    path="Properties.Skill.LearningIntervalEnd"
                    type="number"
                    step={0.1}
                  />
                </span>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Effects on Equip (finders/excavators) -->
        {#if (additional.type === 'finders' || additional.type === 'excavators') && (activeEntity?.EffectsOnEquip?.length > 0 || $editMode)}
          <div class="stats-section effects-section">
            <EffectsEditor
              effects={activeEntity?.EffectsOnEquip || []}
              fieldName="EffectsOnEquip"
              availableEffects={effects}
              effectType="equip"
              title="Effects on Equip"
              showEmpty={$editMode}
            />
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
              on:change={(e) => updateField('Properties.Description', e.detail)}
              placeholder="Enter a description for this {getTypeName(additional.type).toLowerCase()}..."
            />
          {:else if activeEntity?.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeEntity.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || 'This tool'} is a {getTypeName(additional.type).toLowerCase()} used in various activities in Entropia Universe.
            </div>
          {/if}
        </div>

        <!-- Tiering Section (finders/excavators, non-limited only) -->
        {#if isTierable && additional.tierInfo}
          <DataSection
            title="Tiers"
            icon=""
            bind:expanded={panelStates.tiering}
            subtitle="{additional.tierInfo?.length || 0} tiers"
            on:toggle={savePanelStates}
          >
            <TieringEditor entity={activeEntity} entityType={getEntityType(additional.type)} tierInfo={additional.tierInfo} />
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
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>{additional.type ? getTypeName(additional.type) + 's' : 'Tools'}</h2>
      <p>Select a {additional.type ? getTypeName(additional.type).toLowerCase() : 'tool'} from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  /* All shared wiki infobox styles are in global style.css */
</style>

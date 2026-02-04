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
  import { onMount, onDestroy } from 'svelte';
  import { hasItemTag, clampDecimals, encodeURIComponentSafe, getTimeString, getTypeLink } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
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
  import Acquisition from '$lib/components/Acquisition.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  export let data;

  $: medtool = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};
  $: pendingChange = data.pendingChange;
  $: existingChange = data.existingChange;
  $: isCreateMode = data.isCreateMode || false;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: effectsList = data.effects || [];

  // Permission check - verified users and admins can edit
  $: canEdit = user?.verified || user?.isAdmin;

  // For multi-type pages, data.items is an object keyed by type
  $: allItems = (() => {
    if (!data.items) return [];
    if (additional.type && data.items[additional.type]) {
      return data.items[additional.type];
    }
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
  $: if (user) {
    const entityType = getEntityType(additional.type);
    const emptyEntity = getEmptyEntity(additional.type);
    initEditState(medtool || emptyEntity, entityType, isCreateMode, existingChange);
  }

  // Set pending change when it exists
  $: if (pendingChange) {
    setExistingPendingChange(pendingChange);
  }

  // Active entity: in edit mode use currentEntity, when viewing pending use its data, otherwise use original
  $: activeEntity = $editMode
    ? $currentEntity
    : $viewingPendingChange && $existingPendingChange?.data
      ? $existingPendingChange.data
      : medtool;

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
    href: additional.type === btn.type ? '/items/medicaltools' : `/items/medicaltools/${btn.type}`
  }));

  // Type-specific sidebar table columns
  function getNavTableColumns(type) {
    const typeColumn = {
      key: 'type',
      header: 'Type',
      width: '60px',
      filterPlaceholder: 'Tool',
      getValue: (item) => item._type === 'tools' ? 'Tool' : 'Chip',
      format: (v) => v || '-'
    };

    const intervalColumn = {
      key: 'interval',
      header: 'Heal Interval',
      width: '90px',
      filterPlaceholder: '<5',
      getValue: (item) => getReload(item),
      format: (v) => v != null ? `${v.toFixed(2)}s` : '-'
    };

    const usesColumn = {
      key: 'upm',
      header: 'Uses/Minute',
      width: '85px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.UsesPerMinute,
      format: (v) => v != null ? clampDecimals(v, 0, 1) : '-'
    };

    const maxLevelColumn = {
      key: 'maxLvl',
      header: 'Max Level',
      width: '80px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Mindforce?.Level ?? item.Properties?.Level,
      format: (v) => v != null ? v : '-'
    };

    switch (type) {
      case 'tools':
      case 'chips':
        return [intervalColumn, usesColumn, maxLevelColumn];
      default:
        return [typeColumn, intervalColumn, usesColumn, maxLevelColumn];
    }
  }

  $: navTableColumns = getNavTableColumns(additional.type);

  // Custom href generator for items
  function getItemHref(item, basePath) {
    const type = item._type || additional.type;
    if (type) {
      return `/items/medicaltools/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Medical Tools', href: '/items/medicaltools' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + 's', href: `/items/medicaltools/${additional.type}` }] : []),
    ...(medtool ? [{ label: medtool.Name }] : [])
  ];

  // SEO
  $: seoDescription = medtool?.Properties?.Description ||
    `${medtool?.Name || 'Medical Tool'} - ${getTypeName(additional.type)} in Entropia Universe.`;

  $: canonicalUrl = medtool
    ? `https://entropianexus.com/items/medicaltools/${additional.type}/${encodeURIComponentSafe(medtool.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/medicaltools/${additional.type}`
    : 'https://entropianexus.com/items/medicaltools';

  // Image URL for SEO
  $: entityImageUrl = medtool?.Id && additional.type
    ? `/api/img/${getEntityType(additional.type).toLowerCase()}/${medtool.Id}`
    : null;

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
  $: cost = getCost(activeEntity);
  $: reload = getReload(activeEntity);
  $: hps = getHps(activeEntity);
  $: hpp = getHpp(activeEntity);
  $: totalUses = getTotalUses(activeEntity);
  $: cyclePerRepair = totalUses && cost ? totalUses * (cost / 100) : null;
  $: cyclePerHour = reload && cost ? (3600 / reload) * (cost / 100) : null;
  $: timeToBreak = cyclePerHour > 0 && cyclePerRepair ? cyclePerRepair / cyclePerHour : null;

  // Check for tiering (tools only, non-L items)
  $: hasTiering = additional.type === 'tools' && activeEntity && !hasItemTag(activeEntity.Name, 'L');

  // ========== RELOAD/USES TOGGLE ==========
  let showReload = true;
  $: showReloadEffective = $editMode ? false : showReload;

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
  let panelStates = {
    tiering: true,
    acquisition: true
  };

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
  entity={medtool}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={medtool}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Medical Tools"
  {breadcrumbs}
  entity={medtool}
  entityType={getEntityType(additional.type)}
  basePath="/items/medicaltools/{additional.type || ''}"
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
  {#if medtool || isCreateMode}
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
            {#if activeEntity?.Properties?.Skill?.IsSiB}
              <span class="sib-badge">SiB</span>
            {/if}
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
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div class="stat-row toggleable" on:click={toggleReloadUses} title="Click to toggle between Reload and Uses/min">
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
                  type="text"
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
              on:change={(e) => updateField('Properties.Description', e.detail)}
              placeholder="Enter a description for this {getTypeName(additional.type).toLowerCase()}..."
            />
          {:else if activeEntity?.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeEntity.Properties.Description)}</div>
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
            on:toggle={savePanelStates}
          >
            <TieringEditor entity={activeEntity} entityType="MedicalTool" tierInfo={additional.tierInfo || []} />
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
      <h2>{additional.type ? getTypeName(additional.type) + 's' : 'Medical Tools'}</h2>
      <p>Select a {additional.type ? getTypeName(additional.type).toLowerCase() : 'medical tool'} from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  /* Pending change banner */
  .pending-change-banner {
    background: linear-gradient(135deg, #f59e0b20, #f59e0b10);
    border: 1px solid #f59e0b;
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
    font-size: 14px;
    color: var(--text-color);
  }

  .banner-toggle {
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 500;
    background: var(--accent-color);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: opacity 0.15s;
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

  .sib-badge {
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
    background-color: #10b981;
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

  .stat-value.highlight {
    color: #4ade80;
    font-weight: 600;
  }

  .stat-value.highlight-yes {
    color: var(--success-color, #4ade80);
  }

  .stat-value.effect-value {
    color: var(--accent-color, #4a9eff);
  }

  .stat-row.toggleable {
    cursor: pointer;
    padding: 4px 6px;
    margin: 0 -6px;
    border-radius: 4px;
    transition: background-color 0.15s;
  }

  .stat-row.toggleable:hover {
    background-color: var(--hover-color);
  }

  .toggle-hint {
    font-size: 10px;
    color: var(--text-muted, #999);
    margin-left: 4px;
    opacity: 0.7;
  }

  .stat-row.toggleable:hover .toggle-hint {
    opacity: 1;
  }

  .stat-row.indent {
    padding-left: 12px;
  }

  .stat-row.indent .stat-label {
    font-size: 11px;
  }

  .profession-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .profession-link:hover {
    text-decoration: underline;
  }

  .interval-edit {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .interval-sep {
    color: var(--text-muted, #999);
    font-weight: 400;
  }

  .entity-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .entity-link:hover {
    text-decoration: underline;
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

  /* Effects styling */
  .effects-section .stat-row {
    padding: 3px 0;
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
  @media (max-width: 899px) {
    .effects-combined {
      flex-direction: column;
    }
  }

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

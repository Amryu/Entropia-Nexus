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
  import { onMount, onDestroy } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, getTimeString, getTypeLink, groupBy, getLatestPendingUpdate } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
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
  import Acquisition from '$lib/components/Acquisition.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  export let data;

  $: consumable = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};
  $: pendingChange = data.pendingChange;
  $: existingChange = data.existingChange;
  $: isCreateMode = data.isCreateMode || false;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: effectsList = data.effects || [];
  $: mobsList = data.mobs || [];
  $: mobOptions = (mobsList || []).map(m => ({ label: m.Name, value: m.Name }));
  $: professionsList = data.professions || [];
  $: consumableEntityId = consumable?.Id ?? consumable?.ItemId;
  $: userPendingUpdate = getLatestPendingUpdate(userPendingUpdates, consumableEntityId);
  $: resolvedPendingChange = userPendingUpdate || pendingChange;
  $: canUsePendingChange = !!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve')));

  // Permission check - verified users and admins can edit
  $: canEdit = user?.verified || user?.grants?.includes('wiki.edit');

  // For multi-type pages, data.items is an object keyed by type
  // When no type is selected, show all items from all types (with _type added for linking)
  $: allItems = (() => {
    if (!data.items) return [];
    if (additional.type && data.items[additional.type]) {
      return data.items[additional.type];
    }
    // No type selected - combine all items from all types, adding _type for correct linking
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
  $: if (user) {
    const entityType = getEntityType(additional.type);
    const emptyEntity = getEmptyEntity(additional.type);
    const entity = isCreateMode ? (existingChange?.data || emptyEntity) : consumable;
    const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
    initEditState(entity || emptyEntity, entityType, isCreateMode, editChange);
  }

  // Set pending change when it exists
  $: if (resolvedPendingChange) {
    setExistingPendingChange(resolvedPendingChange);
    // Auto-enable viewing pending change for author or admin
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
      : consumable;

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
    href: additional.type === btn.type ? '/items/consumables' : `/items/consumables/${btn.type}`
  }));

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

  $: navTableColumns = getNavTableColumns(additional.type);
  $: navFullWidthColumns = getNavFullWidthColumns(additional.type);
  const allAvailableColumns = Object.values(columnDefs);
  $: navPageTypeId = `consumables-${additional.type || 'all'}`;

  // Custom href generator for items - handles _type property for "all items" view
  function getItemHref(item, basePath) {
    const type = item._type || additional.type;
    if (type) {
      return `/items/consumables/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Consumables', href: '/items/consumables' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + 's', href: `/items/consumables/${additional.type}` }] : []),
    ...(consumable ? [{ label: consumable.Name }] : [])
  ];

  // SEO
  $: seoDescription = consumable?.Properties?.Description ||
    `${consumable?.Name || 'Consumable'} - ${getTypeName(additional.type)} in Entropia Universe.`;

  $: canonicalUrl = consumable
    ? `https://entropianexus.com/items/consumables/${additional.type}/${encodeURIComponentSafe(consumable.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/consumables/${additional.type}`
    : 'https://entropianexus.com/items/consumables';

  // Image URL for SEO
  $: entityImageUrl = consumable?.Id && additional.type
    ? `/api/img/${getEntityType(additional.type).toLowerCase()}/${consumable.Id}`
    : null;

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

  $: formattedEffects = getFormattedEffects(activeEntity);

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    acquisition: true
  };

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
  entityType={getEntityType(additional.type)}
  basePath="/items/consumables/{additional.type || ''}"
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
  {userPendingCreates}
  {userPendingUpdates}
>
  {#if consumable || isCreateMode}
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
                    on:change={(e) => {
                      if (e.detail?.value) {
                        updateField('Mob', { Name: e.detail.value });
                      } else {
                        updateField('Mob', null);
                      }
                    }}
                    on:select={(e) => {
                      if (e.detail?.value) {
                        updateField('Mob', { Name: e.detail.value });
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
              {activeEntity?.Name || 'This consumable'} is a {getTypeName(additional.type).toLowerCase()} used in Entropia Universe.
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
      <h2>{additional.type ? getTypeName(additional.type) + 's' : 'Consumables'}</h2>
      <p>Select a {additional.type ? getTypeName(additional.type).toLowerCase() : 'consumable'} from the list to view details.</p>
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

  .stat-value.effect-value {
    color: var(--accent-color, #4a9eff);
  }

  .entity-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .entity-link:hover {
    text-decoration: underline;
  }

  /* Effects styling */
  .effects-section .effect-group {
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px dashed var(--border-color, #555);
  }

  .effects-section .effect-group:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
  }

  .effect-duration {
    font-size: 11px;
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
    text-transform: uppercase;
    margin-bottom: 6px;
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

    /* Hide article title on mobile - redundant with infobox */
    .article-title {
      display: none;
    }

    .infobox-title {
      font-size: 16px;
    }
  }
</style>

<!--
  @component Armor Set Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Supports full wiki editing.
  Infobox: Defense stats (9 types + total), Economy, Set Effects, Total Absorption
  Article: Description, Set Pieces, Tiering, Acquisition

  Legacy editConfig preserved in armorsets-legacy/+page.svelte
  Key structure:
  - constructor: Name, Properties (Description, Weight, Economy, Defense), Armors[], EffectsOnSetEquip[], Tiers[]
  - dependencies: ['effects']
  - controls: General, Economy, Defense (9 types), Armors (7 slots with gender support), Set Effects, Tiering
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { encodeURIComponentSafe, clampDecimals, hasItemTag, groupBy, getLatestPendingUpdate, loadEditDeps } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import MarketPriceSection from '$lib/components/wiki/MarketPriceSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import DefenseGridEdit from '$lib/components/wiki/DefenseGridEdit.svelte';

  // ArmorSet-specific components
  import ArmorSetPieces from './ArmorSetPieces.svelte';
  import TieringEditor from '$lib/components/wiki/TieringEditor.svelte';
  import SetEffectsEditor from '$lib/components/wiki/SetEffectsEditor.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/wiki/Acquisition.svelte';
  import Usage from '$lib/components/wiki/Usage.svelte';

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

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = false;
  $: if ($editMode && data.effects === null && !editDepsLoading) {
    editDepsLoading = true;
    loadEditDeps([
      { key: 'effects', url: '/api/effects' }
    ]).then(deps => {
      data = { ...data, ...deps };
      editDepsLoading = false;
    });
  }

  $: armorSet = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: additional = data.additional || {};
  $: pendingChange = data.pendingChange;
  $: existingChange = data.existingChange;
  $: isCreateMode = data.isCreateMode || false;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: effects = data.effects || [];
  $: armorSetEntityId = armorSet?.Id ?? armorSet?.ItemId;
  $: userPendingUpdate = getLatestPendingUpdate(userPendingUpdates, armorSetEntityId);
  $: resolvedPendingChange = userPendingUpdate || pendingChange;
  $: canUsePendingChange = !!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve')));

  // Can edit if user is verified or admin
  $: canEdit = user?.verified || user?.grants?.includes('wiki.edit');

  // Build navigation items
  $: navItems = allItems;

  // Empty entity template for create mode
  const emptyEntity = {
    Name: '',
    Properties: {
      Description: '',
      Weight: 0,
      Economy: {
        MaxTT: 0,
        MinTT: 0,
        Durability: 0
      },
      Defense: {
        Impact: 0,
        Cut: 0,
        Stab: 0,
        Penetration: 0,
        Shrapnel: 0,
        Burn: 0,
        Cold: 0,
        Acid: 0,
        Electric: 0
      }
    },
    Armors: [],
    EffectsOnSetEquip: [],
    Tiers: []
  };

  // Initialize edit state when entity or user changes
  $: if (user) {
    const entity = isCreateMode ? (existingChange?.data || emptyEntity) : armorSet;
    if (entity) {
      const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
      initEditState(entity, 'ArmorSet', isCreateMode, editChange);
    }
  }

  // Set existing pending change when data loads
  $: if (resolvedPendingChange) {
    setExistingPendingChange(resolvedPendingChange);
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }

  // Active entity: what we display (edit mode → currentEntity, pending view → pending data, default → armorSet)
  $: activeEntity = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.changes)
      ? applyChangesToEntity(armorSet, $existingPendingChange.changes)
      : armorSet;

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

  // Flatten Armors array-of-arrays into a flat piece list for MarketPriceSection
  function flattenArmorPieces(armors) {
    if (!Array.isArray(armors)) return null;
    const flat = [];
    for (const variants of armors) {
      if (!Array.isArray(variants)) continue;
      for (const armor of variants) {
        if (!armor?.Name) continue;
        flat.push({
          name: armor.Name,
          slot: armor.Properties?.Slot || '',
          gender: armor.Properties?.Gender || 'Both',
        });
      }
    }
    return flat.length > 0 ? flat : null;
  }

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });

  // Defense types for filtering
  const defenseTypes = ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];

  // Get required threshold percentage based on number of selected filters
  // 1 filter: 20%, 2: 35%, 3: 45%, 4+: +10% each
  function getDefenseThreshold(count) {
    if (count <= 0) return 0;
    if (count === 1) return 0.20;
    if (count === 2) return 0.35;
    if (count === 3) return 0.45;
    // 4+: 45% + 10% for each additional
    return 0.45 + (count - 3) * 0.10;
  }

  // Custom filter function for defense types
  // Threshold increases with more filters selected to ensure meaningful results
  function defenseFilterFn(item, selectedTypes) {
    if (!selectedTypes || selectedTypes.length === 0) return true;

    const totalDef = getTotalDefense(item);
    if (!totalDef || totalDef === 0) return false;

    // Sum the defense values for all selected types
    const selectedDefense = selectedTypes.reduce((sum, type) => {
      return sum + (item.Properties?.Defense?.[type] ?? 0);
    }, 0);

    // Get threshold based on number of selected filters
    const threshold = getDefenseThreshold(selectedTypes.length);

    return (selectedDefense / totalDef) >= threshold;
  }

  // Help text for defense filter
  const defenseFilterHelp = [
    '1 type selected: 20% of total defense',
    '2 types selected: 35% of total defense',
    '3 types selected: 45% of total defense',
    '4+ types: +10% for each additional'
  ];

  // Sort function for defense filter - returns total flat defense of selected types (higher = better)
  function defenseSortFn(item, selectedTypes) {
    if (!selectedTypes || selectedTypes.length === 0) return 0;
    return selectedTypes.reduce((sum, type) => {
      return sum + (item.Properties?.Defense?.[type] ?? 0);
    }, 0);
  }

  // Navigation filters - defense type buttons (multi-select)
  const navFilters = [
    {
      key: 'defenseType',
      label: 'Defense Type',
      multiSelect: true,
      filterFn: defenseFilterFn,
      sortFn: defenseSortFn,
      helpText: defenseFilterHelp,
      values: defenseTypes.map(type => ({ value: type, label: type.substring(0, 3) }))
    }
  ];

  // All column definitions for armor sets
  const columnDefs = {
    defense: {
      key: 'defense',
      header: 'Total Def',
      width: '75px',
      filterPlaceholder: '>50',
      getValue: (item) => getTotalDefense(item),
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    durability: {
      key: 'durability',
      header: 'Durability',
      width: '70px',
      filterPlaceholder: '>1000',
      getValue: (item) => item.Properties?.Economy?.Durability,
      format: (v) => v != null ? v : '-'
    },
    impact: {
      key: 'impact',
      header: 'Impact',
      width: '50px',
      filterPlaceholder: '>5',
      getValue: (item) => item.Properties?.Defense?.Impact ?? null,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    cut: {
      key: 'cut',
      header: 'Cut',
      width: '50px',
      filterPlaceholder: '>5',
      getValue: (item) => item.Properties?.Defense?.Cut ?? null,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    stab: {
      key: 'stab',
      header: 'Stab',
      width: '50px',
      filterPlaceholder: '>5',
      getValue: (item) => item.Properties?.Defense?.Stab ?? null,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    penetration: {
      key: 'penetration',
      header: 'Pen',
      width: '50px',
      filterPlaceholder: '>5',
      getValue: (item) => item.Properties?.Defense?.Penetration ?? null,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    shrapnel: {
      key: 'shrapnel',
      header: 'Shrap',
      width: '50px',
      filterPlaceholder: '>5',
      getValue: (item) => item.Properties?.Defense?.Shrapnel ?? null,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    burn: {
      key: 'burn',
      header: 'Burn',
      width: '50px',
      filterPlaceholder: '>5',
      getValue: (item) => item.Properties?.Defense?.Burn ?? null,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    cold: {
      key: 'cold',
      header: 'Cold',
      width: '50px',
      filterPlaceholder: '>5',
      getValue: (item) => item.Properties?.Defense?.Cold ?? null,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    acid: {
      key: 'acid',
      header: 'Acid',
      width: '50px',
      filterPlaceholder: '>5',
      getValue: (item) => item.Properties?.Defense?.Acid ?? null,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    electric: {
      key: 'electric',
      header: 'Elec',
      width: '50px',
      filterPlaceholder: '>5',
      getValue: (item) => item.Properties?.Defense?.Electric ?? null,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    absorption: {
      key: 'absorption',
      header: 'Absorption',
      width: '75px',
      filterPlaceholder: '>100',
      getValue: (item) => getTotalAbsorption(item),
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    maxDecay: {
      key: 'maxDecay',
      header: 'Max Decay',
      width: '70px',
      filterPlaceholder: '>1',
      getValue: (item) => getMaxArmorDecay(item),
      format: (v) => v != null ? v.toFixed(2) : '-'
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
      filterPlaceholder: '>0',
      getValue: (item) => item.Properties?.Economy?.MinTT,
      format: (v) => v != null ? v.toFixed(2) : '-'
    },
    weight: {
      key: 'weight',
      header: 'Weight',
      width: '55px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Properties?.Weight,
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    pieces: {
      key: 'pieces',
      header: 'Pieces',
      width: '50px',
      getValue: (item) => item.Armors?.flat().filter(x => x?.Properties?.Gender === 'Both' || x?.Properties?.Gender === 'Male').length ?? null,
      format: (v) => v != null ? v : '-'
    }
  };

  const navTableColumns = [
    columnDefs.defense,
    columnDefs.durability,
    columnDefs.impact,
    columnDefs.cut,
    columnDefs.stab
  ];

  const navFullWidthColumns = [
    columnDefs.defense,
    columnDefs.durability,
    columnDefs.impact,
    columnDefs.cut,
    columnDefs.stab,
    columnDefs.penetration,
    columnDefs.shrapnel,
    columnDefs.burn,
    columnDefs.cold,
    columnDefs.acid,
    columnDefs.electric,
    columnDefs.absorption,
    columnDefs.maxtt
  ];

  const allAvailableColumns = Object.values(columnDefs);

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Armor Sets', href: '/items/armorsets' },
    ...(activeEntity ? [{ label: activeEntity.Name || 'New Armor Set' }] : [])
  ];

  // SEO
  $: seoDescription = activeEntity?.Properties?.Description ||
    `${activeEntity?.Name || 'Armor Set'} - armor set with ${getTotalDefense(activeEntity)?.toFixed(1) || '?'} total defense in Entropia Universe.`;

  $: canonicalUrl = armorSet
    ? `https://entropianexus.com/items/armorsets/${encodeURIComponentSafe(armorSet.Name)}`
    : 'https://entropianexus.com/items/armorsets';

  // Image URL for SEO (approved images only)
  $: entityImageUrl = armorSet?.Id ? `/api/img/armorset/${armorSet.Id}` : null;

  // Check if armor set is tierable
  $: isTierable = activeEntity && !hasItemTag(activeEntity.Name, 'L');

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    pieces: true,
    tiering: true,
    marketPrices: true,
    acquisition: true,
    usage: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-armorset-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-armorset-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== CALCULATOR FUNCTIONS ==========
  function getTotalDefense(item) {
    if (!item?.Properties?.Defense) return null;
    const d = item.Properties.Defense;
    return (d.Impact ?? 0) + (d.Cut ?? 0) + (d.Stab ?? 0) + (d.Penetration ?? 0) +
           (d.Shrapnel ?? 0) + (d.Burn ?? 0) + (d.Cold ?? 0) + (d.Acid ?? 0) + (d.Electric ?? 0);
  }

  function getMaxArmorDecay(item) {
    const totalDef = getTotalDefense(item);
    if (!item?.Properties?.Economy?.Durability || !totalDef) return null;
    return totalDef * ((100000 - item.Properties.Economy.Durability) / 100000) * 0.05;
  }

  function getTotalAbsorption(item) {
    const maxDecay = getMaxArmorDecay(item);
    const totalDef = getTotalDefense(item);
    if (!item?.Properties?.Economy?.MaxTT || !maxDecay) return null;
    return totalDef * ((item.Properties.Economy.MaxTT - (item.Properties.Economy.MinTT ?? 0)) / (maxDecay / 100));
  }

  // Get set effects grouped by piece count
  function getSetEffects(item) {
    if (!item?.EffectsOnSetEquip?.length) return null;
    const grouped = groupBy(item.EffectsOnSetEquip, x => x.Values.MinSetPieces);
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

  // Reactive calculations
  $: totalDefense = getTotalDefense(activeEntity);
  $: maxDecay = getMaxArmorDecay(activeEntity);
  $: totalAbsorption = getTotalAbsorption(activeEntity);
  $: setEffects = getSetEffects(activeEntity);
  $: pieceCount = activeEntity?.Armors?.flat().filter(x => x?.Properties?.Gender === 'Both' || x?.Properties?.Gender === 'Male').length ?? 0;

  // Damage types for display
  const damageTypes = ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];
</script>

<WikiSEO
  title={activeEntity?.Name || 'Armor Sets'}
  description={seoDescription}
  entityType="ArmorSet"
  entity={activeEntity}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={activeEntity}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Armor Sets"
  {breadcrumbs}
  entity={activeEntity}
  basePath="/items/armorsets"
  {navItems}
  {navFilters}
  {navTableColumns}
  {navFullWidthColumns}
  navAllAvailableColumns={allAvailableColumns}
  navPageTypeId="armorsets"
  {user}
  editable={true}
  {canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
  {editDepsLoading}
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
            entityType="armorset"
            {user}
            isEditMode={$editMode}
            {isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              value={activeEntity?.Name}
              path="Name"
              type="text"
              placeholder="Armor Set Name"
            />
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge">Armor Set</span>
            <span>{pieceCount} pieces</span>
          </div>
        </div>

        <!-- Primary Stats -->
        <div class="stats-section tier-1 tier-purple">
          <div class="stat-row primary">
            <span class="stat-label">Total Defense</span>
            <span class="stat-value">{totalDefense?.toFixed(1) ?? 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Total Absorption</span>
            <span class="stat-value">{totalAbsorption?.toFixed(0) ?? 'N/A'} HP</span>
          </div>
        </div>

        <!-- Defense Breakdown -->
        <div class="stats-section defense-section">
          <h4 class="section-title">Defense</h4>
          <DefenseGridEdit
            defense={activeEntity?.Properties?.Defense}
            fieldPath="Properties.Defense"
            title="Total Defense"
            types={damageTypes}
          />
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max TT</span>
            <span class="stat-value">{activeEntity?.Properties?.Economy?.MaxTT?.toFixed(2) ?? 'N/A'} PED</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min TT</span>
            <span class="stat-value">{activeEntity?.Properties?.Economy?.MinTT?.toFixed(2) ?? 'N/A'} PED</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Durability</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Economy?.Durability}
                path="Properties.Economy.Durability"
                type="number"
                min={0}
                max={100000}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max Decay</span>
            <span class="stat-value">{maxDecay?.toFixed(4) ?? 'N/A'} PEC</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{activeEntity?.Properties?.Weight?.toFixed(1) ?? 'N/A'} kg</span>
          </div>
        </div>

        <!-- Set Effects -->
        {#if setEffects?.length > 0 || $editMode}
          <div class="stats-section set-effects">
            <h4 class="section-title">Set Effects</h4>
            <SetEffectsEditor
              effects={activeEntity?.EffectsOnSetEquip || []}
              fieldName="EffectsOnSetEquip"
              availableEffects={effects}
              maxPieces={pieceCount || 7}
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
            placeholder="Armor Set Name"
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeEntity?.Properties?.Description || ''}
              on:change={(e) => updateField('Properties.Description', e.detail)}
              placeholder="Enter armor set description..."
            />
          {:else if activeEntity?.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeEntity.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || 'This armor set'} is an armor set providing {totalDefense?.toFixed(1) || '?'} total defense.
            </div>
          {/if}
        </div>

        <!-- Set Pieces Section -->
        {#if activeEntity?.Armors?.length > 0 || $editMode}
          <DataSection
            title="Set Pieces"
            icon=""
            bind:expanded={panelStates.pieces}
            subtitle="{pieceCount} pieces"
            on:toggle={savePanelStates}
          >
            {#key armorSet?.Id ?? 'create'}
              <ArmorSetPieces armorSet={activeEntity} />
            {/key}
          </DataSection>
        {/if}

        <!-- Tiering Section -->
        {#if isTierable}
          <DataSection
            title="Tiering"
            icon=""
            bind:expanded={panelStates.tiering}
            subtitle="{additional.tierInfo?.length || 0} tiers"
            on:toggle={savePanelStates}
          >
            <TieringEditor entity={activeEntity} entityType="ArmorSet" tierInfo={additional.tierInfo || []} setPieceCount={pieceCount} />
          </DataSection>
        {/if}

        <!-- Market Prices Section -->
        <MarketPriceSection
          itemId={activeEntity?.Id}
          itemName={activeEntity?.Name}
          entityType="ArmorSet"
          pieces={flattenArmorPieces(activeEntity?.Armors)}
          bind:expanded={panelStates.marketPrices}
          on:toggle={savePanelStates}
        />

        <!-- Acquisition Section -->
        {#if additional.acquisition}
          <DataSection
            title="Acquisition"
            icon=""
            bind:expanded={panelStates.acquisition}
            on:toggle={savePanelStates}
          >
            <Acquisition acquisition={additional.acquisition} isMultiItem={true} />
          </DataSection>
        {/if}

        <!-- Usage Section -->
        {#if additional.usage}
          <DataSection
            title="Usage"
            icon=""
            bind:expanded={panelStates.usage}
            on:toggle={savePanelStates}
          >
            <Usage usage={additional.usage} item={armorSet} isMultiItem={true} />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Armor Sets</h2>
      <p>Select an armor set from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  /* Set Effects Styling */
  .set-effects {
    padding: 12px;
  }
</style>

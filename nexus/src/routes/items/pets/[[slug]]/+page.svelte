<!--
  @component Pets Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Supports full wiki editing.

  Legacy editConfig preserved in pets-legacy/+page.svelte
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy, untrack } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, getTypeLink, getLatestPendingUpdate, loadEditDeps } from '$lib/util';


  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import MarketPriceSection from '$lib/components/wiki/MarketPriceSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import PetEffectsEditor from '$lib/components/wiki/PetEffectsEditor.svelte';
  import Acquisition from '$lib/components/wiki/Acquisition.svelte';
  import Usage from '$lib/components/wiki/Usage.svelte';

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

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';
  import AdSlot from '$lib/components/AdSlot.svelte';

  let { data = $bindable() } = $props();

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = $state(false);





  // Empty entity template for create mode
  const emptyEntity = {
    Name: '',
    Properties: {
      Description: '',
      Rarity: 'Common',
      TrainingDifficulty: 'Easy',
      TamingLevel: 1,
      ExportableLevel: 0,
      NutrioCapacity: 0,
      NutrioConsumptionPerHour: 0
    },
    Planet: null,
    Effects: []
  };




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


  // Full column definitions for pets
  const columnDefs = {
    rarity: { key: 'rarity', header: 'Rarity', width: '70px', filterPlaceholder: 'Rare', getValue: (item) => item.Properties?.Rarity, format: (v) => v || '-' },
    effects: { key: 'effects', header: 'Effect #', width: '75px', filterPlaceholder: '>0', getValue: (item) => item.Effects?.length || 0, format: (v) => v != null ? v : '-' },
    planet: { key: 'planet', header: 'Planet', width: '70px', filterPlaceholder: 'Calypso', getValue: (item) => item.Planet?.Name, format: (v) => v || '-' },
    tamingLevel: { key: 'tamingLevel', header: 'Taming Lvl', width: '70px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.TamingLevel, format: (v) => v != null ? v : '-' },
    training: { key: 'training', header: 'Training', width: '65px', filterPlaceholder: 'Easy', getValue: (item) => item.Properties?.TrainingDifficulty, format: (v) => v || '-' },
    exportable: { key: 'exportable', header: 'Exportable', width: '70px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.ExportableLevel, format: (v) => v != null && v > 0 ? `Lvl ${v}` : 'No' },
    nutrioCapacity: { key: 'nutrioCapacity', header: 'Nutrio Cap.', width: '80px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.NutrioCapacity, format: (v) => v != null ? `${(v / 100).toFixed(2)} PED` : '-' },
    nutrioConsumption: { key: 'nutrioConsumption', header: 'Nutrio/h', width: '70px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.NutrioConsumptionPerHour, format: (v) => v != null ? `${(v / 100).toFixed(2)}` : '-' }
  };

  const navFullWidthColumns = [columnDefs.rarity, columnDefs.effects, columnDefs.planet, columnDefs.tamingLevel, columnDefs.training, columnDefs.exportable, columnDefs.nutrioCapacity];
  const allAvailableColumns = Object.values(columnDefs);






  // Rarity options for editing
  const rarityOptions = [
    { value: 'Common', label: 'Common' },
    { value: 'Uncommon', label: 'Uncommon' },
    { value: 'Rare', label: 'Rare' },
    { value: 'Epic', label: 'Epic' },
    { value: 'Legendary', label: 'Legendary' },
    { value: 'Mythic', label: 'Mythic' },
    { value: 'Unique', label: 'Unique' }
  ];

  // Training difficulty options
  const trainingOptions = [
    { value: 'Easy', label: 'Easy' },
    { value: 'Average', label: 'Average' },
    { value: 'Hard', label: 'Hard' }
  ];

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    skills: true,
    marketPrices: true,
    acquisition: true,
    usage: true
  });

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-pet-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-pet-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }

  // Rarity color mapping
  function getRarityColor(rarity) {
    switch (rarity) {
      case 'Common': return '#9ca3af';
      case 'Uncommon': return '#22c55e';
      case 'Rare': return '#3b82f6';
      case 'Epic': return '#a855f7';
      case 'Legendary': return '#f59e0b';
      case 'Mythic': return '#ef4444';
      case 'Unique': return '#ec4899';
      default: return '#9ca3af';
    }
  }
  $effect(() => {
    if ($editMode && data.effects === null && !untrack(() => editDepsLoading)) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'effects', url: '/api/effects' },
        { key: 'planetsList', url: '/api/planets' }
      ]).then(deps => {
        data = { ...data, ...deps };
        editDepsLoading = false;
      });
    }
  });
  let pet = $derived(data.object);
  let user = $derived(data.session?.user);
  let additional = $derived(data.additional || {});
  let pendingChange = $derived(data.pendingChange);
  let existingChange = $derived(data.existingChange);
  let isCreateMode = $derived(data.isCreateMode || false);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let planetsList = $derived(data.planets || []);
  let effectsList = $derived(data.effects || []);
  let petEntityId = $derived(pet?.Id ?? pet?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, petEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));
  // Can edit if user is verified or admin
  let canEdit = $derived(user?.verified || user?.grants?.includes('wiki.edit'));
  // All pets for navigation
  let allItems = $derived(data.allItems || []);
  // Build navigation items
  let navItems = $derived(allItems);
  // Initialize edit state when entity or user changes
  $effect(() => {
    if (user) {
      const entity = isCreateMode ? (existingChange?.data || emptyEntity) : pet;
      if (entity) {
        const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
        initEditState(entity, 'Pet', isCreateMode, editChange);
      }
    }
  });
  // Set existing pending change when data loads
  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });
  // Active entity: what we display (edit mode → currentEntity, pending view → pending data, default → pet)
  let activeEntity = $derived($editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.changes)
      ? applyChangesToEntity(pet, $existingPendingChange.changes)
      : pet);
  // Rarity filters for sidebar
  let navFilters = $derived([
    { key: 'Properties.Rarity', label: 'Rarity', values: [
      { value: 'Common', label: 'Common' },
      { value: 'Uncommon', label: 'Uncommon' },
      { value: 'Rare', label: 'Rare' },
      { value: 'Epic', label: 'Epic' },
      { value: 'Legendary', label: 'Legendary' }
    ]}
  ]);
  // Sidebar table columns
  let navTableColumns = $derived([columnDefs.rarity, columnDefs.effects]);
  // Breadcrumbs
  let breadcrumbs = $derived([
    { label: 'Items', href: '/items' },
    { label: 'Pets', href: '/items/pets' },
    ...(activeEntity ? [{ label: activeEntity.Name || 'New Pet' }] : [])
  ]);
  // SEO
  let seoDescription = $derived(activeEntity?.Properties?.Description ||
    `${activeEntity?.Name || 'Pet'} - ${activeEntity?.Properties?.Rarity || ''} pet in Entropia Universe.`);
  let canonicalUrl = $derived(pet
    ? `https://entropianexus.com/items/pets/${encodeURIComponentSafe(pet.Name)}`
    : 'https://entropianexus.com/items/pets');
  // Image URL for SEO
  let entityImageUrl = $derived(pet?.Id ? `/api/img/pet/${pet.Id}` : null);
  // Check for effects
  let hasEffects = $derived(activeEntity?.Effects?.length > 0);
</script>

<WikiSEO
  title={activeEntity?.Name || 'Pets'}
  description={seoDescription}
  entityType="Pet"
  entity={activeEntity}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={activeEntity}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Pets"
  {breadcrumbs}
  entity={activeEntity}
  basePath="/items/pets"
  {navItems}
  {navFilters}
  {navTableColumns}
  navAllAvailableColumns={allAvailableColumns}
  navFullWidthColumns={navFullWidthColumns}
  navPageTypeId="pets"
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
        entityLabel="pet"
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
            entityType="pet"
            {user}
            isEditMode={$editMode}
            isCreateMode={isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              value={activeEntity?.Name || ''}
              path="Name"
              type="text"
              placeholder="Pet Name"
            />
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge" style="background-color: {getRarityColor(activeEntity?.Properties?.Rarity)}">{activeEntity?.Properties?.Rarity || 'Pet'}</span>
            {#if activeEntity?.Properties?.IsRare}<span class="item-flag-badge rare">Rare</span>{/if}
            {#if activeEntity?.Properties?.IsUntradeable}<span class="item-flag-badge untradeable">Untradeable</span>{/if}
          </div>
        </div>

        <!-- Tier-1 Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Rarity</span>
            <span class="stat-value">{activeEntity?.Properties?.Rarity ?? 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Training</span>
            <span class="stat-value">{activeEntity?.Properties?.TrainingDifficulty ?? 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Taming Level</span>
            <span class="stat-value">{activeEntity?.Properties?.TamingLevel ?? 'N/A'}</span>
          </div>
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Rarity</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Rarity ?? ''}
                path="Properties.Rarity"
                type="select"
                options={rarityOptions}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Training Difficulty</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.TrainingDifficulty ?? ''}
                path="Properties.TrainingDifficulty"
                type="select"
                options={trainingOptions}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Planet</span>
            <span class="stat-value">
              {#if $editMode}
                <select
                  class="pet-select"
                  value={activeEntity?.Planet?.Name || ''}
                  onchange={(e) => {
                    const value = e.target.value;
                    if (value) {
                      updateField('Planet', { Name: value });
                    } else {
                      updateField('Planet', null);
                    }
                  }}
                >
                  <option value="">Select planet...</option>
                  {#each planetsList as planet}
                    <option value={planet.Name}>{planet.Name}</option>
                  {/each}
                </select>
              {:else}
                {activeEntity?.Planet?.Name ?? 'N/A'}
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Exportable</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.ExportableLevel ?? null}
                path="Properties.ExportableLevel"
                type="number"
                min={0}
                max={100}
                displayFormat={activeEntity?.Properties?.ExportableLevel > 0 ? 'Level {value}' : 'No'}
              />
            </span>
          </div>
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
            <span class="stat-label">Nutrio Capacity</span>
            <span class="stat-value">
              {#if $editMode}
                <InlineEdit
                  value={activeEntity?.Properties?.NutrioCapacity ?? null}
                  path="Properties.NutrioCapacity"
                  type="number"
                  min={0}
                  step={1}
                  suffix="PED"
                />
              {:else}
                {activeEntity?.Properties?.NutrioCapacity != null ? `${(activeEntity.Properties.NutrioCapacity / 100).toFixed(2)} PED` : 'N/A'}
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Nutrio Consumption</span>
            <span class="stat-value">
              {#if $editMode}
                <InlineEdit
                  value={activeEntity?.Properties?.NutrioConsumptionPerHour ?? null}
                  path="Properties.NutrioConsumptionPerHour"
                  type="number"
                  min={0}
                  step={1}
                  suffix="PED/h"
                />
              {:else}
                {activeEntity?.Properties?.NutrioConsumptionPerHour != null ? `${(activeEntity.Properties.NutrioConsumptionPerHour / 100).toFixed(2)} PED/h` : 'N/A'}
              {/if}
            </span>
          </div>
        </div>

        <!-- Skill Stats -->
        <div class="stats-section">
          <h4 class="section-title">Skill</h4>
          <div class="stat-row">
            <span class="stat-label">Profession</span>
            <span class="stat-value links">
              <a href={getTypeLink('Animal Tamer', 'Profession')} class="entity-link">Animal Tamer</a>
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Taming Level</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.TamingLevel ?? null}
                path="Properties.TamingLevel"
                type="number"
                min={1}
                max={100}
              />
            </span>
          </div>
        </div>

        <div class="infobox-ad">
          <AdSlot adSlot="3560522008" adFormat="autorelaxed" matchedContentRows={1} matchedContentColumns={1} />
        </div>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            value={activeEntity?.Name || ''}
            path="Name"
            type="text"
            placeholder="Pet Name"
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeEntity?.Properties?.Description || ''}
              onchange={(data) => updateField('Properties.Description', data)}
              placeholder="Enter pet description..."
              showWaypoints={true}
            />
          {:else if activeEntity?.Properties?.Description}
            <div class="description-content">{@html activeEntity.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || 'This pet'} is a {activeEntity?.Properties?.Rarity?.toLowerCase() || ''} pet that can be tamed in Entropia Universe.
            </div>
          {/if}
        </div>

        <div class="wiki-content-ad">
          <AdSlot adSlot="3560522008" adFormat="autorelaxed" matchedContentRows={1} matchedContentColumns={4} />
        </div>

        <!-- Pet Skills/Effects Section -->
        {#if hasEffects || $editMode}
          <DataSection
            title="Pet Skills"
            icon=""
            bind:expanded={panelStates.skills}
            ontoggle={savePanelStates}
          >
            <PetEffectsEditor
              effects={activeEntity?.Effects || []}
              fieldName="Effects"
              availableEffects={effectsList}
            />
          </DataSection>
        {/if}

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

        <!-- Usage Section -->
        {#if additional.usage}
          <DataSection
            title="Usage"
            icon=""
            bind:expanded={panelStates.usage}
            ontoggle={savePanelStates}
          >
            <Usage usage={additional.usage} item={activeEntity} />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Pets</h2>
      <p>Select a pet from the list to view details.</p>
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

  .pet-select {
    padding: 4px 6px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    width: 100%;
    box-sizing: border-box;
    height: 28px;
  }

  .pet-select:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .pet-select option {
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
  }

  .stat-value.links {
    text-align: right;
    font-size: 12px;
  }

</style>

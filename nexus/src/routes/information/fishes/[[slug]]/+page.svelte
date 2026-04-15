<!--
  @component Fish Wiki Page
  Wikipedia-style layout. Fish is a hybrid info entity: it references a
  Material item (by name) and a MobSpecies row (1:1, CodexType='Fish').
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { onDestroy, setContext } from 'svelte';
  setContext('wikiContributeCategory', 'fish');
  import { encodeURIComponentSafe, getLatestPendingUpdate, loadEditDeps } from '$lib/util';

  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  import {
    editMode,
    initEditState,
    resetEditState,
    currentEntity,
    existingPendingChange,
    viewingPendingChange,
    setExistingPendingChange,
    setViewingPendingChange,
    updateField
  } from '$lib/stores/wikiEditState.js';

  let { data = $bindable() } = $props();

  const BIOMES = ['Sea', 'River', 'Lake', 'Deep Ocean', 'Sky'];
  const DIFFICULTIES = ['Easy', 'Medium', 'Hard', 'Very Hard', 'Elite'];
  const TIMES_OF_DAY = ['Day', 'Night'];
  const ROD_TYPES = ['Casting', 'Angling', 'Fly Fishing', 'Deep Ocean Fishing', 'Baitfishing'];

  const emptyEntity = {
    Name: '',
    Properties: {
      Description: '',
      Biome: null,
      Size: null,
      Strength: null,
      Difficulty: null,
      MinDepth: null,
      TimeOfDay: null,
      RodTypes: []
    },
    Item: { Name: null },
    Species: { Name: '', CodexBaseCost: null },
    PreferredLure: { Name: null },
    Planets: []
  };

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

  onDestroy(() => { resetEditState(); });

  const navFilters = [
    {
      key: 'Properties.Biome',
      label: 'Biome',
      values: BIOMES.map(b => ({ value: b, label: b }))
    },
    {
      key: 'Properties.Difficulty',
      label: 'Difficulty',
      values: DIFFICULTIES.map(d => ({ value: d, label: d }))
    }
  ];

  const fishColumnDefs = {
    biome: {
      key: 'biome',
      header: 'Biome',
      width: '100px',
      filterPlaceholder: 'Sea',
      getValue: (item) => item.Properties?.Biome,
      format: (v) => v || '-'
    },
    difficulty: {
      key: 'difficulty',
      header: 'Difficulty',
      width: '90px',
      filterPlaceholder: 'Easy',
      getValue: (item) => item.Properties?.Difficulty,
      format: (v) => v || '-'
    },
    size: {
      key: 'size',
      header: 'Size',
      width: '60px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Size,
      format: (v) => v != null ? v : '-'
    }
  };

  const navTableColumns = [fishColumnDefs.biome, fishColumnDefs.difficulty];
  const navFullWidthColumns = [fishColumnDefs.biome, fishColumnDefs.difficulty, fishColumnDefs.size];
  const allAvailableColumns = Object.values(fishColumnDefs);

  // Lazy-load edit dependencies on edit activation
  let editDepsLoading = $state(false);
  $effect(() => {
    if ($editMode && data.itemsList === null && !editDepsLoading) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'itemsList', url: '/api/items?limit=5000' },
        { key: 'planetsList', url: '/api/planets' },
        { key: 'speciesList', url: '/api/mobspecies' }
      ], data).finally(() => { editDepsLoading = false; });
    }
  });

  let fish = $derived(data.object);
  let user = $derived(data.session?.user);
  let allItems = $derived(data.allItems || []);
  let pendingChange = $derived(data.pendingChange);
  let existingChange = $derived(data.existingChange);
  let isCreateMode = $derived(data.isCreateMode || false);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let fishEntityId = $derived(fish?.Id);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, fishEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));
  let canEdit = $derived(user?.verified || user?.grants?.includes('wiki.edit'));
  let navItems = $derived(allItems);

  $effect(() => {
    if (user) {
      const entity = isCreateMode ? (existingChange?.data || emptyEntity) : fish;
      if (entity) {
        const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
        initEditState(entity, 'Fish', isCreateMode, editChange);
      }
    }
  });

  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });

  let activeEntity = $derived($editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.changes)
      ? applyChangesToEntity(fish, $existingPendingChange.changes)
      : fish);

  let breadcrumbs = $derived([
    { label: 'Information', href: '/information' },
    { label: 'Fishes', href: '/information/fishes' },
    ...(activeEntity ? [{ label: activeEntity.Name || 'New Fish' }] : [])
  ]);

  let seoDescription = $derived(activeEntity?.Properties?.Description ||
    `${activeEntity?.Name || 'Fish'} - ${activeEntity?.Properties?.Biome || ''} fish in Entropia Universe.`);
  let canonicalUrl = $derived(fish
    ? `https://entropianexus.com/information/fishes/${encodeURIComponentSafe(fish.Name)}`
    : 'https://entropianexus.com/information/fishes');
  let entityImageUrl = $derived(fish?.Id ? `/api/img/fish/${fish.Id}` : null);

  // SearchInput option builders (only computed on edit for perf)
  let materialItemOptions = $derived.by(() => {
    if (!$editMode || !Array.isArray(data.itemsList)) return [];
    return data.itemsList
      .filter(it => it?.Properties?.Type === 'Material' || it?.Properties?.Type === 'Fish')
      .map(it => ({ value: it.Name, label: it.Name, sublabel: it.Properties?.Type }));
  });

  let lureItemOptions = $derived.by(() => {
    if (!$editMode || !Array.isArray(data.itemsList)) return [];
    return data.itemsList
      .filter(it => it?.Properties?.Type === 'FishingLure')
      .map(it => ({ value: it.Name, label: it.Name }));
  });

  // Only Fish-type species are offered in the picker. Typing a name not in
  // the list creates a new Fish species on save.
  let fishSpeciesOptions = $derived.by(() => {
    if (!$editMode || !Array.isArray(data.speciesList)) return [];
    return data.speciesList
      .filter(s => s?.Properties?.CodexType === 'Fish')
      .map(s => ({ value: s.Name, label: s.Name, _raw: s }));
  });

  // Pre-fill BaseCost when an existing species is picked.
  function handleSpeciesSelect(e) {
    const name = e?.value ?? '';
    updateField('Species.Name', name);
    const existing = (data.speciesList || []).find(s => s.Name === name);
    if (existing?.Properties?.CodexBaseCost != null) {
      updateField('Species.CodexBaseCost', Number(existing.Properties.CodexBaseCost));
    }
  }

  let isExistingSpecies = $derived.by(() => {
    const name = activeEntity?.Species?.Name;
    if (!name || !Array.isArray(data.speciesList)) return false;
    return data.speciesList.some(s => s.Name === name && s.Properties?.CodexType === 'Fish');
  });

  function toggleRodType(rt) {
    const current = Array.isArray(activeEntity?.Properties?.RodTypes) ? [...activeEntity.Properties.RodTypes] : [];
    const idx = current.indexOf(rt);
    if (idx >= 0) current.splice(idx, 1);
    else current.push(rt);
    updateField('Properties.RodTypes', current);
  }

  function togglePlanet(planetName) {
    const current = Array.isArray(activeEntity?.Planets) ? [...activeEntity.Planets] : [];
    const idx = current.findIndex(p => p?.Name === planetName);
    if (idx >= 0) current.splice(idx, 1);
    else current.push({ Name: planetName });
    updateField('Planets', current);
  }

  function isRodTypeSelected(rt) {
    return (activeEntity?.Properties?.RodTypes || []).includes(rt);
  }

  function isPlanetSelected(name) {
    return (activeEntity?.Planets || []).some(p => p?.Name === name);
  }
</script>

<WikiSEO
  title={activeEntity?.Name || 'Fishes'}
  description={seoDescription}
  entityType="Fish"
  entity={activeEntity}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={activeEntity}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Fishes"
  {breadcrumbs}
  entity={activeEntity}
  basePath="/information/fishes"
  {navItems}
  {navFilters}
  {navTableColumns}
  {navFullWidthColumns}
  navAllAvailableColumns={allAvailableColumns}
  navPageTypeId="fishes"
  {user}
  editable={true}
  {canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
>
  {#if activeEntity || isCreateMode}
    {#if $existingPendingChange && !$editMode}
      <PendingChangeBanner
        pendingChange={$existingPendingChange}
        viewing={$viewingPendingChange}
        onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
        entityLabel="fish"
      />
    {/if}

    <div class="layout-a">
      <aside class="wiki-infobox-float">
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeEntity?.Id}
            entityName={activeEntity?.Name}
            entityType="fish"
            {user}
            isEditMode={$editMode}
            {isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              value={activeEntity?.Name}
              path="Name"
              type="text"
              placeholder="Fish Name"
            />
          </div>
          <div class="infobox-subtitle">
            {#if activeEntity?.Properties?.Biome}
              <span class="category-badge">{activeEntity.Properties.Biome}</span>
            {/if}
            {#if activeEntity?.Properties?.Difficulty}
              <span class="category-badge">{activeEntity.Properties.Difficulty}</span>
            {/if}
          </div>
        </div>

        <div class="stats-section tier-1 tier-blue">
          <div class="stat-row">
            <span class="stat-label">Biome</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Biome}
                path="Properties.Biome"
                type="select"
                options={[{ value: null, label: '-' }, ...BIOMES.map(b => ({ value: b, label: b }))]}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Difficulty</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Difficulty}
                path="Properties.Difficulty"
                type="select"
                options={[{ value: null, label: '-' }, ...DIFFICULTIES.map(d => ({ value: d, label: d }))]}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Size (cm)</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Size}
                path="Properties.Size"
                type="number"
                placeholder="-"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Strength</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Strength}
                path="Properties.Strength"
                type="number"
                placeholder="-"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min Depth (m)</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.MinDepth}
                path="Properties.MinDepth"
                type="number"
                placeholder="-"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Time of Day</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.TimeOfDay}
                path="Properties.TimeOfDay"
                type="select"
                options={[{ value: null, label: 'Any' }, ...TIMES_OF_DAY.map(t => ({ value: t, label: t }))]}
              />
            </span>
          </div>
        </div>

        <div class="stats-section">
          <h4 class="section-title">Item (Material)</h4>
          <div class="stat-row">
            <span class="stat-value stat-value-block">
              {#if $editMode}
                <SearchInput
                  value={activeEntity?.Item?.Name || ''}
                  placeholder="Search material..."
                  options={materialItemOptions}
                  onchange={(e) => updateField('Item.Name', e.value)}
                  onselect={(e) => updateField('Item.Name', e.value)}
                />
              {:else}
                {activeEntity?.Item?.Name || 'N/A'}
              {/if}
            </span>
          </div>
        </div>

        <div class="stats-section">
          <h4 class="section-title">
            Species (Codex)
            {#if $editMode && activeEntity?.Species?.Name}
              <span class="species-state">{isExistingSpecies ? 'existing' : 'new'}</span>
            {/if}
          </h4>
          <div class="stat-row">
            <span class="stat-label">Name</span>
            <span class="stat-value stat-value-block">
              {#if $editMode}
                <SearchInput
                  value={activeEntity?.Species?.Name || ''}
                  placeholder="Pick or type new..."
                  options={fishSpeciesOptions}
                  onchange={handleSpeciesSelect}
                  onselect={handleSpeciesSelect}
                />
              {:else}
                {activeEntity?.Species?.Name || 'N/A'}
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Codex Base Cost</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Species?.CodexBaseCost}
                path="Species.CodexBaseCost"
                type="number"
                placeholder="-"
              />
            </span>
          </div>
        </div>

        <div class="stats-section">
          <h4 class="section-title">Preferred Lure</h4>
          <div class="stat-row">
            <span class="stat-value stat-value-block">
              {#if $editMode}
                <SearchInput
                  value={activeEntity?.PreferredLure?.Name || ''}
                  placeholder="Search lure..."
                  options={lureItemOptions}
                  onchange={(e) => updateField('PreferredLure.Name', e.value)}
                  onselect={(e) => updateField('PreferredLure.Name', e.value)}
                />
              {:else}
                {activeEntity?.PreferredLure?.Name || 'N/A'}
              {/if}
            </span>
          </div>
        </div>
      </aside>

      <article class="wiki-article">
        <DataSection title="Description" expanded={true}>
          {#if $editMode}
            <RichTextEditor
              value={activeEntity?.Properties?.Description || ''}
              path="Properties.Description"
            />
          {:else if activeEntity?.Properties?.Description}
            <div>{@html activeEntity.Properties.Description}</div>
          {:else}
            <p class="muted">No description yet.</p>
          {/if}
        </DataSection>

        <DataSection title="Rod Types" expanded={true}>
          {#if $editMode}
            <div class="toggle-group">
              {#each ROD_TYPES as rt}
                <button
                  type="button"
                  class="toggle {isRodTypeSelected(rt) ? 'active' : ''}"
                  onclick={() => toggleRodType(rt)}
                >
                  {rt}
                </button>
              {/each}
            </div>
          {:else if (activeEntity?.Properties?.RodTypes || []).length > 0}
            <ul>
              {#each activeEntity.Properties.RodTypes as rt}
                <li>{rt}</li>
              {/each}
            </ul>
          {:else}
            <p class="muted">No rod types set.</p>
          {/if}
        </DataSection>

        <DataSection title="Planets" expanded={true}>
          {#if $editMode}
            <div class="toggle-group">
              {#each (data.planetsList || []) as p}
                <button
                  type="button"
                  class="toggle {isPlanetSelected(p.Name) ? 'active' : ''}"
                  onclick={() => togglePlanet(p.Name)}
                >
                  {p.Name}
                </button>
              {/each}
            </div>
          {:else if (activeEntity?.Planets || []).length > 0}
            <ul>
              {#each activeEntity.Planets as p}
                <li>{p?.Name || '-'}</li>
              {/each}
            </ul>
          {:else}
            <p class="muted">No planets set.</p>
          {/if}
        </DataSection>
      </article>
    </div>
  {/if}
</WikiPage>

<style>
  .layout-a {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 320px;
    gap: var(--space-lg, 24px);
  }
  .wiki-infobox-float {
    grid-column: 2;
    display: flex;
    flex-direction: column;
    gap: var(--space-md, 16px);
  }
  .wiki-article {
    grid-column: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-md, 16px);
  }
  .stats-section {
    background: var(--surface-card, #1e2530);
    border: 1px solid var(--border-subtle, #2a3340);
    border-radius: var(--radius-md, 8px);
    padding: var(--space-md, 16px);
  }
  .infobox-header {
    text-align: center;
    padding: var(--space-md, 16px);
    background: var(--surface-card, #1e2530);
    border-radius: var(--radius-md, 8px);
  }
  .infobox-title {
    font-size: 1.25rem;
    font-weight: 600;
  }
  .infobox-subtitle {
    margin-top: var(--space-xs, 4px);
    display: flex;
    justify-content: center;
    gap: var(--space-xs, 4px);
    flex-wrap: wrap;
  }
  .category-badge {
    font-size: 0.75rem;
    padding: 2px 8px;
    background: var(--surface-accent, #2a3340);
    border-radius: 999px;
  }
  .stat-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
  }
  .stat-label {
    color: var(--text-muted, #8a95a5);
  }
  .stat-value-block {
    width: 100%;
  }
  .section-title {
    margin: 0 0 var(--space-sm, 8px) 0;
    font-size: 0.85rem;
    text-transform: uppercase;
    color: var(--text-muted, #8a95a5);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .species-state {
    font-size: 0.65rem;
    padding: 2px 6px;
    border-radius: 999px;
    background: var(--surface-accent, #2a3340);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .toggle-group {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs, 4px);
  }
  .toggle {
    padding: 6px 12px;
    border: 1px solid var(--border-subtle, #2a3340);
    background: var(--surface-card, #1e2530);
    color: var(--text-primary, #e6ebf0);
    border-radius: var(--radius-sm, 4px);
    cursor: pointer;
  }
  .toggle.active {
    background: var(--accent-primary, #3b82f6);
    border-color: var(--accent-primary, #3b82f6);
    color: white;
  }
  .muted {
    color: var(--text-muted, #8a95a5);
    font-style: italic;
  }

  @media (max-width: 960px) {
    .layout-a {
      grid-template-columns: 1fr;
    }
    .wiki-infobox-float {
      grid-column: 1;
    }
    .wiki-article {
      grid-column: 1;
    }
  }
</style>

<!--
  @component Fish Wiki Page
  Wikipedia-style layout. Fish is a hybrid info entity: it references a
  Material item (by name) and a MobSpecies row (many:1, CodexType='Fish').
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { onDestroy, setContext, untrack } from 'svelte';
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
  import MobCodex from '$lib/components/wiki/mobs/MobCodex.svelte';
  import FishSectorGrid from '$lib/components/wiki/fish/FishSectorGrid.svelte';

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
      Difficulty: null,
      MinDepth: null,
      TimeOfDay: null,
      Weight: null,
      Economy: { MaxTT: null },
      Biomes: [],
      RodTypes: []
    },
    Sizes: [],
    Species: { Name: '', CodexBaseCost: null },
    FishOil: { Name: null },
    PreferredLure: { Name: null },
    Planets: [],
    Locations: []
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
      key: 'Properties.Biomes',
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
      getValue: (item) => (item.Properties?.Biomes || []).join(', '),
      format: (v) => v || '-'
    },
    difficulty: {
      key: 'difficulty',
      header: 'Difficulty',
      width: '90px',
      filterPlaceholder: 'Easy',
      getValue: (item) => item.Properties?.Difficulty,
      format: (v) => v || '-'
    }
  };

  const navTableColumns = [fishColumnDefs.biome, fishColumnDefs.difficulty];
  const navFullWidthColumns = [fishColumnDefs.biome, fishColumnDefs.difficulty];
  const allAvailableColumns = Object.values(fishColumnDefs);

  // Lazy-load edit dependencies on edit activation
  let editDepsLoading = $state(false);
  $effect(() => {
    if ($editMode && data.itemsList === null && !untrack(() => editDepsLoading)) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'itemsList', url: '/api/items?limit=5000' },
        { key: 'planetsList', url: '/api/planets' },
        { key: 'speciesList', url: '/api/mobspecies' }
      ]).then(deps => {
        data = { ...data, ...deps };
        editDepsLoading = false;
      });
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
  let skillsList = $derived(data.skillsList || []);
  let speciesCodexBaseCost = $derived(activeEntity?.Species?.CodexBaseCost ?? activeEntity?.Species?.Properties?.CodexBaseCost);
  let speciesCodexType = $derived(activeEntity?.Species?.Properties?.CodexType ?? 'Fish');
  let hasCodex = $derived(speciesCodexBaseCost != null);

  let sortedSizes = $derived.by(() => {
    const sizes = activeEntity?.Sizes || [];
    return [...sizes].sort((a, b) => (a.ScrapsToRefine ?? Infinity) - (b.ScrapsToRefine ?? Infinity));
  });

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
    `${activeEntity?.Name || 'Fish'} - ${(activeEntity?.Properties?.Biomes || []).join(', ') || ''} fish in Entropia Universe.`);
  let canonicalUrl = $derived(fish
    ? `https://entropianexus.com/information/fishes/${encodeURIComponentSafe(fish.Name)}`
    : 'https://entropianexus.com/information/fishes');
  let entityImageUrl = $derived(fish?.Id ? `/api/img/fish/${fish.Id}` : null);

  let lureItemOptions = $derived.by(() => {
    if (!$editMode || !Array.isArray(data.itemsList)) return [];
    return data.itemsList
      .filter(it => it?.Properties?.Type === 'FishingLure')
      .map(it => ({ value: it.Name, label: it.Name }));
  });

  let oilItemOptions = $derived.by(() => {
    if (!$editMode || !Array.isArray(data.itemsList)) return [];
    return data.itemsList
      .filter(it => it?.Properties?.Type === 'Material' && it.Name.toLowerCase().includes('oil'))
      .map(it => ({ value: it.Name, label: it.Name }));
  });

  function addSize() {
    const current = Array.isArray(activeEntity?.Sizes) ? [...activeEntity.Sizes] : [];
    current.push({ Name: '', Strength: null, ScrapsToRefine: null });
    updateField('Sizes', current);
  }

  function removeSize(index) {
    const current = (activeEntity?.Sizes || []).filter((_, i) => i !== index);
    updateField('Sizes', current);
  }

  function updateSize(index, field, value) {
    const current = (activeEntity?.Sizes || []).map((s, i) =>
      i === index ? { ...s, [field]: value } : s
    );
    updateField('Sizes', current);
  }

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

  // ===== Multi-select add/remove for biomes, rod types, and planets =====

  let biomeAddOptions = $derived.by(() => {
    const selected = new Set(activeEntity?.Properties?.Biomes || []);
    return BIOMES
      .filter(b => !selected.has(b))
      .map(b => ({ value: b, label: b }));
  });

  function addBiome(b) {
    if (!b) return;
    const current = Array.isArray(activeEntity?.Properties?.Biomes) ? [...activeEntity.Properties.Biomes] : [];
    if (current.includes(b)) return;
    current.push(b);
    updateField('Properties.Biomes', current);
  }

  function removeBiome(b) {
    const current = (activeEntity?.Properties?.Biomes || []).filter(x => x !== b);
    updateField('Properties.Biomes', current);
  }

  // Remaining rod-type options (not yet selected).
  let rodTypeAddOptions = $derived.by(() => {
    const selected = new Set(activeEntity?.Properties?.RodTypes || []);
    return ROD_TYPES
      .filter(rt => !selected.has(rt))
      .map(rt => ({ value: rt, label: rt }));
  });

  function addRodType(rt) {
    if (!rt) return;
    const current = Array.isArray(activeEntity?.Properties?.RodTypes) ? [...activeEntity.Properties.RodTypes] : [];
    if (current.includes(rt)) return;
    current.push(rt);
    updateField('Properties.RodTypes', current);
  }

  function removeRodType(rt) {
    const current = (activeEntity?.Properties?.RodTypes || []).filter(x => x !== rt);
    updateField('Properties.RodTypes', current);
  }

  // Remaining planet options (not yet selected).
  let planetAddOptions = $derived.by(() => {
    const selected = new Set((activeEntity?.Planets || []).map(p => p?.Name).filter(Boolean));
    return (data.planetsList || [])
      .filter(p => p?.Name && !selected.has(p.Name))
      .map(p => ({ value: p.Name, label: p.Name }));
  });

  function addPlanet(name) {
    if (!name) return;
    const current = Array.isArray(activeEntity?.Planets) ? [...activeEntity.Planets] : [];
    if (current.some(p => p?.Name === name)) return;
    current.push({ Name: name });
    updateField('Planets', current);
  }

  function removePlanet(name) {
    const current = (activeEntity?.Planets || []).filter(p => p?.Name !== name);
    updateField('Planets', current);
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
        <!-- Header: image, name, species subtitle -->
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
          {#if activeEntity?.Species?.Name}
            <div class="infobox-subtitle">
              <span class="category-badge">{activeEntity.Species.Name}</span>
            </div>
          {/if}
        </div>

        <!-- Tier-1: display-only primary stats (no inputs) -->
        <div class="stats-section tier-1 tier-blue">
          <div class="stat-row primary">
            <span class="stat-label">Biome</span>
            <span class="stat-value">{(activeEntity?.Properties?.Biomes || []).join(', ') || 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Difficulty</span>
            <span class="stat-value">{activeEntity?.Properties?.Difficulty || 'N/A'}</span>
          </div>
        </div>

        <!-- General: editable core attributes (dropdowns + numbers) -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Difficulty</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Difficulty}
                path="Properties.Difficulty"
                type="select"
                placeholder="Select difficulty"
                options={DIFFICULTIES.map(d => ({ value: d, label: d }))}
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
                placeholder="Any"
                options={TIMES_OF_DAY.map(t => ({ value: t, label: t }))}
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
            <span class="stat-label">Weight</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Weight}
                path="Properties.Weight"
                type="number"
                placeholder="-"
              />
            </span>
          </div>
        </div>

        <!-- Economy: TT value from the backing Materials row -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max TT</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.Economy?.MaxTT}
                path="Properties.Economy.MaxTT"
                type="number"
                placeholder="-"
              />
            </span>
          </div>
        </div>

        <!-- Fish Oil -->
        <div class="stats-section">
          <h4 class="section-title">Fish Oil</h4>
          <div class="stat-row stat-row-block">
            <span class="stat-value stat-value-block">
              {#if $editMode}
                <SearchInput
                  value={activeEntity?.FishOil?.Name || ''}
                  placeholder="Search oil material..."
                  options={oilItemOptions}
                  onchange={(e) => updateField('FishOil.Name', e.value)}
                  onselect={(e) => updateField('FishOil.Name', e.value)}
                />
              {:else}
                {activeEntity?.FishOil?.Name || 'N/A'}
              {/if}
            </span>
          </div>
        </div>

        <!-- Species (codex) -->
        <div class="stats-section">
          <h4 class="section-title">
            Species
            {#if $editMode && activeEntity?.Species?.Name}
              <span class="species-state">{isExistingSpecies ? 'existing' : 'new'}</span>
            {/if}
          </h4>
          <div class="stat-row stat-row-block">
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
            <span class="stat-label">Base Cost</span>
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

        <!-- Preferred lure -->
        <div class="stats-section">
          <h4 class="section-title">Preferred Lure</h4>
          <div class="stat-row stat-row-block">
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

        <!-- Biomes: multi-select via dropdown + chip list -->
        <div class="stats-section">
          <h4 class="section-title">Biomes</h4>
          {#if (activeEntity?.Properties?.Biomes || []).length > 0}
            <div class="chip-list">
              {#each activeEntity.Properties.Biomes as b}
                <span class="chip">
                  {b}
                  {#if $editMode}
                    <button type="button" class="chip-remove" aria-label="Remove {b}" onclick={() => removeBiome(b)}>×</button>
                  {/if}
                </span>
              {/each}
            </div>
          {:else if !$editMode}
            <p class="empty-note">None set</p>
          {/if}
          {#if $editMode && biomeAddOptions.length > 0}
            <select
              class="add-select"
              value=""
              onchange={(e) => { addBiome(e.currentTarget.value); e.currentTarget.value = ''; }}
            >
              <option value="" disabled>+ Add biome…</option>
              {#each biomeAddOptions as opt}
                <option value={opt.value}>{opt.label}</option>
              {/each}
            </select>
          {/if}
        </div>

        <!-- Rod types: multi-select via dropdown + chip list -->
        <div class="stats-section">
          <h4 class="section-title">Rod Types</h4>
          {#if (activeEntity?.Properties?.RodTypes || []).length > 0}
            <div class="chip-list">
              {#each activeEntity.Properties.RodTypes as rt}
                <span class="chip">
                  {rt}
                  {#if $editMode}
                    <button type="button" class="chip-remove" aria-label="Remove {rt}" onclick={() => removeRodType(rt)}>×</button>
                  {/if}
                </span>
              {/each}
            </div>
          {:else if !$editMode}
            <p class="empty-note">None set</p>
          {/if}
          {#if $editMode && rodTypeAddOptions.length > 0}
            <select
              class="add-select"
              value=""
              onchange={(e) => { addRodType(e.currentTarget.value); e.currentTarget.value = ''; }}
            >
              <option value="" disabled>+ Add rod type…</option>
              {#each rodTypeAddOptions as opt}
                <option value={opt.value}>{opt.label}</option>
              {/each}
            </select>
          {/if}
        </div>

        <!-- Planets: multi-select via dropdown + chip list -->
        <div class="stats-section">
          <h4 class="section-title">Planets</h4>
          {#if (activeEntity?.Planets || []).length > 0}
            <div class="chip-list">
              {#each activeEntity.Planets as p}
                <span class="chip">
                  {p?.Name || '-'}
                  {#if $editMode}
                    <button type="button" class="chip-remove" aria-label="Remove {p?.Name}" onclick={() => removePlanet(p?.Name)}>×</button>
                  {/if}
                </span>
              {/each}
            </div>
          {:else if !$editMode}
            <p class="empty-note">None set</p>
          {/if}
          {#if $editMode && planetAddOptions.length > 0}
            <select
              class="add-select"
              value=""
              onchange={(e) => { addPlanet(e.currentTarget.value); e.currentTarget.value = ''; }}
            >
              <option value="" disabled>+ Add planet…</option>
              {#each planetAddOptions as opt}
                <option value={opt.value}>{opt.label}</option>
              {/each}
            </select>
          {/if}
        </div>
      </aside>

      <!-- Main article: title + description + sizes + codex -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            value={activeEntity?.Name}
            path="Name"
            type="text"
            placeholder="Fish Name"
          />
        </h1>

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

        <DataSection
          title="Sizes"
          expanded={true}
          subtitle="{(activeEntity?.Sizes || []).length} sizes"
        >
          {#if $editMode}
            {#if (activeEntity?.Sizes || []).length > 0}
              <table class="sizes-table">
                <thead>
                  <tr>
                    <th class="sizes-th-name">Name</th>
                    <th class="sizes-th-num">Strength</th>
                    <th class="sizes-th-num">Scraps to Refine</th>
                    <th class="sizes-th-action"></th>
                  </tr>
                </thead>
                <tbody>
                  {#each activeEntity.Sizes as size, i}
                    <tr>
                      <td>
                        <input type="text" class="size-input" value={size.Name} placeholder="Size name"
                          onchange={(e) => updateSize(i, 'Name', e.currentTarget.value)} />
                      </td>
                      <td>
                        <input type="number" class="size-input size-input-num" value={size.Strength}
                          placeholder="-" onchange={(e) => updateSize(i, 'Strength', e.currentTarget.value ? Number(e.currentTarget.value) : null)} />
                      </td>
                      <td>
                        <input type="number" class="size-input size-input-num" value={size.ScrapsToRefine}
                          placeholder="-" onchange={(e) => updateSize(i, 'ScrapsToRefine', e.currentTarget.value ? Number(e.currentTarget.value) : null)} />
                      </td>
                      <td class="sizes-td-action">
                        <button type="button" class="chip-remove" aria-label="Remove size" onclick={() => removeSize(i)}>×</button>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            {/if}
            <button type="button" class="add-btn" onclick={addSize}>+ Add size</button>
          {:else if sortedSizes.length > 0}
            <table class="sizes-table">
              <thead>
                <tr>
                  <th class="sizes-th-name">Name</th>
                  <th class="sizes-th-num">Strength</th>
                  <th class="sizes-th-num">Scraps to Refine</th>
                </tr>
              </thead>
              <tbody>
                {#each sortedSizes as size}
                  <tr>
                    <td>{size.Name}</td>
                    <td class="num">{size.Strength ?? '-'}</td>
                    <td class="num">{size.ScrapsToRefine ?? '-'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {:else}
            <p class="muted">No sizes recorded yet.</p>
          {/if}
        </DataSection>

        {#if !isCreateMode && hasCodex}
          <DataSection title="Codex Calculator" expanded={true}>
            <MobCodex
              baseCost={speciesCodexBaseCost}
              codexType={speciesCodexType}
              mobType="Fish"
              skills={skillsList}
            />
          </DataSection>
        {/if}

        <DataSection
          title="Locations"
          expanded={true}
          subtitle="{(activeEntity?.Locations || []).reduce((n, l) => n + (l.Sectors?.length || 0), 0)} sectors"
        >
          <FishSectorGrid
            locations={activeEntity?.Locations || []}
            planets={activeEntity?.Planets || []}
            isEditMode={$editMode}
            planetsList={data.planetsList}
            onchange={(newLocations) => updateField('Locations', newLocations)}
          />
        </DataSection>

        <!-- TODO: Global section (fish global stats/tracking) goes here when implemented -->
      </article>
    </div>
  {/if}
</WikiPage>

<style>
  /*
   * Wiki layout classes (.layout-a, .wiki-infobox-float, .wiki-article,
   * .stats-section, .infobox-header/-title/-subtitle, .stat-row/-label/
   * -value, .section-title, .category-badge) are defined globally in
   * $lib/style.css and shared with profession/skill/mob pages. Only
   * page-specific additions live here.
   */

  /* Full-width stat row (no label, embedded picker takes the whole line) */
  .stat-row-block {
    display: block;
    padding: 4px 0;
  }

  /* Block-level stat-value cell for embedded SearchInputs */
  :global(.stat-value.stat-value-block) {
    display: block;
    width: 100%;
  }

  /* "existing" / "new" badge next to the Species section title */
  .species-state {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 999px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-left: 8px;
    font-weight: 400;
  }

  /* Chip list for multi-select (rod types / planets) */
  .chip-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 8px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 500;
  }

  .chip-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    padding: 0;
    background: rgba(0, 0, 0, 0.25);
    color: white;
    border: none;
    border-radius: 50%;
    font-size: 14px;
    line-height: 1;
    cursor: pointer;
  }

  .chip-remove:hover {
    background: rgba(0, 0, 0, 0.5);
  }

  /* Add-new dropdown for multi-select sections */
  .add-select {
    width: 100%;
    padding: 6px 8px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
  }

  .add-select:hover {
    border-color: var(--accent-color, #4a9eff);
  }

  /* View-mode empty note inside infobox sections */
  .empty-note {
    margin: 0;
    color: var(--text-muted, #999);
    font-size: 12px;
    font-style: italic;
  }

  /* Empty-state message in article sections */
  .muted {
    color: var(--text-muted, #999);
    font-style: italic;
    margin: 0;
  }

  /* Sizes table in article area */
  .sizes-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .sizes-table th {
    text-align: left;
    font-weight: 600;
    padding: 6px 10px;
    border-bottom: 2px solid var(--border-color, #555);
    color: var(--text-muted, #999);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .sizes-table td {
    padding: 5px 10px;
    border-bottom: 1px solid var(--border-color-subtle, rgba(128, 128, 128, 0.2));
  }

  .sizes-table tr:hover {
    background-color: var(--hover-bg, rgba(128, 128, 128, 0.08));
  }

  .sizes-th-name {
    width: auto;
  }

  .sizes-th-num {
    width: 120px;
    text-align: right !important;
  }

  .sizes-th-action {
    width: 32px;
  }

  .sizes-td-action {
    text-align: center;
  }

  .sizes-table td.num {
    text-align: right;
  }

  .size-input {
    width: 100%;
    padding: 4px 8px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    font-size: 13px;
    box-sizing: border-box;
  }

  .size-input:focus {
    border-color: var(--accent-color, #4a9eff);
    outline: none;
  }

  .size-input-num {
    text-align: right;
  }

  .add-btn {
    width: 100%;
    padding: 8px;
    margin-top: 8px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-muted, #999);
    border: 1px dashed var(--border-color, #555);
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
    text-align: center;
  }

  .add-btn:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }
</style>

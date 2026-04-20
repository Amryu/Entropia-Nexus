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
  import DayCycleSlider from '$lib/components/wiki/fish/DayCycleSlider.svelte';
  import { FISHING_PLANETS } from '$lib/mapUtil';

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

  const BIOMES = ['Sea', 'River', 'Lake', 'Deep Ocean'];
  const DIFFICULTIES = ['Easy', 'Medium', 'Hard', 'Very Hard'];
  const ROD_TYPES = ['Casting', 'Angling', 'Fly Fishing', 'Deep Ocean Fishing', 'Baitfishing'];

  const emptyEntity = {
    Name: '',
    Properties: {
      Description: '',
      Difficulty: null,
      MinDepth: null,
      Strength: null,
      ScrapsToRefine: null,
      Weight: null,
      Rarity: null,
      TimeOfDay: null,
      Biomes: [],
      RodTypes: []
    },
    Species: { Name: '' },
    FishOil: { Name: null },
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
    },
    species: {
      key: 'species',
      header: 'Family',
      width: '100px',
      getValue: (item) => item.Species?.Name,
      format: (v) => v || '-'
    },
    rarity: {
      key: 'rarity',
      header: 'Rarity',
      width: '110px',
      getValue: (item) => item.Properties?.Rarity,
      format: (v) => v || '-'
    },
    strength: {
      key: 'strength',
      header: 'Strength',
      width: '80px',
      getValue: (item) => item.Properties?.Strength,
      format: (v) => v != null ? v : '-'
    },
    scrapsToRefine: {
      key: 'scrapsToRefine',
      header: 'Scraps',
      width: '80px',
      getValue: (item) => item.Properties?.ScrapsToRefine,
      format: (v) => v != null ? v : '-'
    },
    timeOfDay: {
      key: 'timeOfDay',
      header: 'Time of Day',
      width: '110px',
      getValue: (item) => {
        const t = item.Properties?.TimeOfDay;
        if (!t || t.Start == null || t.End == null) return null;
        const fmt = (v) => {
          const total = v * 24;
          const h = Math.floor(total);
          const m = Math.round((total - h) * 60);
          return `${String(h >= 24 ? 0 : h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
        };
        return `${fmt(t.Start)}–${fmt(t.End)}`;
      },
      format: (v) => v || 'Unknown'
    },
    minDepth: {
      key: 'minDepth',
      header: 'Min Depth',
      width: '80px',
      getValue: (item) => item.Properties?.MinDepth,
      format: (v) => v != null ? `${v} m` : '-'
    },
    rodTypes: {
      key: 'rodTypes',
      header: 'Rod Types',
      width: '120px',
      getValue: (item) => (item.Properties?.RodTypes || []).join(', '),
      format: (v) => v || '-'
    }
  };

  const navTableColumns = [fishColumnDefs.biome, fishColumnDefs.difficulty, fishColumnDefs.rarity];
  const navFullWidthColumns = [
    fishColumnDefs.biome, fishColumnDefs.difficulty, fishColumnDefs.species,
    fishColumnDefs.rarity, fishColumnDefs.timeOfDay
  ];
  const allAvailableColumns = Object.values(fishColumnDefs);

  // Lazy-load edit dependencies on edit activation
  let editDepsLoading = $state(false);
  $effect(() => {
    if ($editMode && data.materialsList === null && !untrack(() => editDepsLoading)) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'materialsList', url: '/api/materials?limit=5000' },
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
  const speciesCodexBaseCost = 6;
  let speciesCodexType = $derived(activeEntity?.Species?.Properties?.CodexType ?? 'Fish');

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

  let seoDescription = $derived.by(() => {
    if (activeEntity?.Properties?.Description) return activeEntity.Properties.Description;
    const name = activeEntity?.Name || 'Fish';
    const biomes = (activeEntity?.Properties?.Biomes || []).join(', ');
    const difficulty = activeEntity?.Properties?.Difficulty;
    const family = activeEntity?.Species?.Name;
    const parts = [name];
    if (family) parts.push(`${family} family`);
    if (biomes) parts.push(biomes);
    if (difficulty) parts.push(`${difficulty} difficulty`);
    parts.push('fish in Entropia Universe');
    return parts.join(' - ');
  });
  let canonicalUrl = $derived(fish
    ? `https://entropianexus.com/information/fishes/${encodeURIComponentSafe(fish.Name)}`
    : 'https://entropianexus.com/information/fishes');
  let entityImageUrl = $derived(fish?.Id ? `/api/img/fish/${fish.Id}` : null);

  let oilItemOptions = $derived.by(() => {
    if (!$editMode || !Array.isArray(data.materialsList)) return [];
    return data.materialsList
      .filter(it => it?.Properties?.Type === 'Fish Oil')
      .map(it => ({ value: it.Name, label: it.Name }));
  });


  // Family dropdown: fed from MobSpecies rows with CodexType='Fish'. Seeded
  // to the 11 game families (Cod/Carp/Eel/Tuna/Pike/Bass/Catfish/Salmon/
  // Sturgeon/Swordfish/Misc) by migration 090 — this is a closed set; new
  // entries via free text are no longer supported.
  let fishSpeciesOptions = $derived.by(() => {
    if (!$editMode || !Array.isArray(data.speciesList)) return [];
    return data.speciesList
      .filter(s => s?.Properties?.CodexType === 'Fish')
      .map(s => ({ value: s.Name, label: s.Name }));
  });

  // Side-effect when the Family dropdown changes: suggest a FishOil name
  // matching the family if the user hasn't set one yet. InlineEdit already
  // wrote Properties `Species.Name` via its `path` prop.
  function handleSpeciesSelect(e) {
    const name = e?.value ?? '';
    if (name && !activeEntity?.FishOil?.Name) {
      updateField('FishOil.Name', `${name} Fish Oil`);
    }
  }

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

  function updateTimeOfDay({ start, end }) {
    if (start == null && end == null) {
      updateField('Properties.TimeOfDay', null);
    } else {
      updateField('Properties.TimeOfDay', { Start: start, End: end });
    }
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
      .filter(p => p?.Name && !selected.has(p.Name) && FISHING_PLANETS.has(p.Name))
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
  sidebarColumns={allAvailableColumns}
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

        <!-- Primary display-only stats (no inputs) -->
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
            <span class="stat-label">Scraps to Refine</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Properties?.ScrapsToRefine}
                path="Properties.ScrapsToRefine"
                type="number"
                placeholder="-"
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Rarity</span>
            <span class="stat-value">{activeEntity?.Properties?.Rarity || 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Family</span>
            <span class="stat-value">
              {#if $editMode}
                <InlineEdit
                  value={activeEntity?.Species?.Name}
                  path="Species.Name"
                  type="select"
                  placeholder="Select family"
                  options={fishSpeciesOptions}
                  onchange={handleSpeciesSelect}
                />
              {:else}
                {activeEntity?.Species?.Name || 'N/A'}
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Fish Oil</span>
            <span class="stat-value">
              {#if $editMode}
                <SearchInput
                  value={activeEntity?.FishOil?.Name || ''}
                  placeholder="Search oil material..."
                  options={oilItemOptions}
                  onchange={(e) => updateField('FishOil.Name', e.value)}
                  onselect={(e) => updateField('FishOil.Name', e.value)}
                />
              {:else if activeEntity?.FishOil?.Name}
                <a href="/items/materials/{encodeURIComponentSafe(activeEntity.FishOil.Name)}">{activeEntity.FishOil.Name}</a>
              {:else}
                N/A
              {/if}
            </span>
          </div>
        </div>

        <!-- Classifications: consolidated multi-select panel -->
        <div class="stats-section">
          <h4 class="section-title">Classifications</h4>

          <div class="multi-group">
            <span class="multi-label">Biomes</span>
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
              <span class="empty-inline">-</span>
            {/if}
            {#if $editMode && biomeAddOptions.length > 0}
              <select class="add-select" value="" onchange={(e) => { addBiome(e.currentTarget.value); e.currentTarget.value = ''; }}>
                <option value="" disabled>+ Add…</option>
                {#each biomeAddOptions as opt}
                  <option value={opt.value}>{opt.label}</option>
                {/each}
              </select>
            {/if}
          </div>

          <div class="multi-group">
            <span class="multi-label">Time of Day</span>
            <DayCycleSlider
              start={activeEntity?.Properties?.TimeOfDay?.Start ?? null}
              end={activeEntity?.Properties?.TimeOfDay?.End ?? null}
              editable={$editMode}
              onchange={updateTimeOfDay}
            />
          </div>

          <div class="multi-group">
            <span class="multi-label">Rod Types</span>
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
              <span class="empty-inline">-</span>
            {/if}
            {#if $editMode && rodTypeAddOptions.length > 0}
              <select class="add-select" value="" onchange={(e) => { addRodType(e.currentTarget.value); e.currentTarget.value = ''; }}>
                <option value="" disabled>+ Add…</option>
                {#each rodTypeAddOptions as opt}
                  <option value={opt.value}>{opt.label}</option>
                {/each}
              </select>
            {/if}
          </div>

          <div class="multi-group">
            <span class="multi-label">Planets</span>
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
              <span class="empty-inline">-</span>
            {/if}
            {#if $editMode && planetAddOptions.length > 0}
              <select class="add-select" value="" onchange={(e) => { addPlanet(e.currentTarget.value); e.currentTarget.value = ''; }}>
                <option value="" disabled>+ Add…</option>
                {#each planetAddOptions as opt}
                  <option value={opt.value}>{opt.label}</option>
                {/each}
              </select>
            {/if}
          </div>
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

        {#if !isCreateMode}
          <DataSection title="Codex Calculator" expanded={true}>
            <MobCodex
              baseCost={speciesCodexBaseCost}
              codexType={speciesCodexType}
              mobType="Fish"
              skills={skillsList}
            />
          </DataSection>
        {/if}

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

  /* Grouped multi-select rows inside a single Classifications section */
  .multi-group {
    padding: 6px 0;
    border-bottom: 1px solid var(--border-color-subtle, rgba(255, 255, 255, 0.06));
  }

  .multi-group:last-child {
    border-bottom: none;
  }

  .multi-label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
  }

  .empty-inline {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  /* Chip list for multi-select */
  .chip-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 6px;
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

</style>

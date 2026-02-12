<!--
  @component Mob Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: General stats, damage spread, skill info
  Article: Description → Maturities → Locations → Loots → Codex
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { encodeURIComponentSafe, clampDecimals, getTypeLink, getLatestPendingUpdate } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';

  // Mob-specific components
  import MobMaturities from '$lib/components/wiki/mobs/MobMaturities.svelte';
  import MobLoots from '$lib/components/wiki/mobs/MobLoots.svelte';
  import MobLocations from '$lib/components/wiki/mobs/MobLocations.svelte';
  import MobCodex from '$lib/components/wiki/mobs/MobCodex.svelte';
  import MobDamageGrid from '$lib/components/wiki/mobs/MobDamageGrid.svelte';

  // Mob edit components
  import MobMaturitiesEdit from '$lib/components/wiki/mobs/MobMaturitiesEdit.svelte';
  import MobSpawnsEdit from '$lib/components/wiki/mobs/MobSpawnsEdit.svelte';
  import MobLootsEdit from '$lib/components/wiki/mobs/MobLootsEdit.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  // Wiki edit state
  import {
    editMode,
    isCreateMode as isCreateModeStore,
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

  export let data;

  $: mob = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: speciesList = data.speciesList || [];
  $: itemsList = data.itemsList || [];  // Items for loot autocomplete
  $: planetsList = data.planetsList || [];  // All planets from API
  $: skillsList = data.skillsList || [];  // Skills for codex calculator
  $: pendingChange = data.pendingChange;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: isCreateMode = data.isCreateMode || false;
  $: mobEntityId = mob?.Id ?? mob?.ItemId;
  $: userPendingUpdate = getLatestPendingUpdate(userPendingUpdates, mobEntityId);
  $: resolvedPendingChange = userPendingUpdate || pendingChange;
  $: canUsePendingChange = !!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve')));

  // Build species options for autocomplete
  $: speciesOptions = speciesList.map(s => ({ value: s.Name, label: s.Name }));

  // Verified users can edit
  $: canEdit = user?.verified || user?.grants?.includes('wiki.edit');

  // Planet options from API (filter out Id=0 which is "Unknown")
  $: planetOptions = planetsList
    .filter(p => p.Id > 0)
    .map(p => ({ value: p.Name, label: p.Name }));

  // Mob type options
  const typeOptions = [
    { value: 'Animal', label: 'Animal' },
    { value: 'Mutant', label: 'Mutant' },
    { value: 'Robot', label: 'Robot' },
    { value: 'Asteroid', label: 'Asteroid' }
  ];

  // Defense profession options (Evader, Dodger, Jammer per legacy)
  const defenseProfessionOptions = [
    { value: 'Evader', label: 'Evader' },
    { value: 'Dodger', label: 'Dodger' },
    { value: 'Jammer', label: 'Jammer' }
  ];

  // Empty mob template for create mode
  const emptyMob = {
    Id: null,
    Name: '',
    Type: 'Animal',
    Planet: { Name: 'Calypso' },
    Properties: {
      Description: '',
      AttacksPerMinute: null,
      AttackRange: null,
      AggressionRange: null,
      AggressionTimer: null,
      IsSweatable: false
    },
    Maturities: [],
    Spawns: [],
    Loots: []
  };

  // Initialize edit state when user/mob changes
  $: if (user) {
    const existingChange = data.existingChange || null;
    const initialEntity = isCreateMode
      ? (existingChange?.data || emptyMob)
      : mob;
    const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
    initEditState(initialEntity, 'Mob', isCreateMode, editChange);
  }

  // Set pending change in store when it changes
  $: if (resolvedPendingChange) {
    setExistingPendingChange(resolvedPendingChange);
    if (user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))) {
      setViewingPendingChange(true);
    }
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }

  // Active mob: use currentEntity in edit mode, pendingChange data when viewing, otherwise original
  $: activeMob = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : mob;

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });

  // Build navigation items from mobs
  $: navItems = allItems;

  // Navigation filters - filter by planet and type
  const navFilters = [
    {
      key: 'Planet.Name',
      label: 'Planet',
      values: [
        { value: 'Calypso', label: 'Calypso' },
        { value: 'Arkadia', label: 'Arkadia' },
        { value: 'Cyrene', label: 'Cyrene' },
        { value: 'Monria', label: 'Monria' },
        { value: 'ROCKtropia', label: 'Rocktropia' },
        { value: 'Toulan', label: 'Toulan' },
        { value: 'Next Island', label: 'Next Island' },
        { value: 'Space', label: 'Space' },
      ]
    },
    {
      key: 'Type',
      label: 'Type',
      values: [
        { value: 'Animal', label: 'Animal' },
        { value: 'Mutant', label: 'Mutant' },
        { value: 'Robot', label: 'Robot' },
        { value: 'Asteroid', label: 'Asteroid' },
      ]
    }
  ];

  function isCat4Mob(item) {
    return item?.Species?.Properties?.CodexType === 'MobLooter';
  }

  // Get smallest HP/Lvl for sidebar display (non-boss maturities only unless all are bosses)
  function getSmallestHpPerLevel(mobData) {
    if (!mobData?.Maturities || mobData.Maturities.length === 0) return null;

    // Try non-boss maturities first
    let maturities = mobData.Maturities.filter(m => !m.Properties?.Boss);
    // Fall back to all maturities if only bosses exist
    if (maturities.length === 0) maturities = mobData.Maturities;

    let smallest = null;
    for (const m of maturities) {
      const hp = m.Properties?.Health;
      const lvl = m.Properties?.Level;
      if (hp != null && lvl != null && lvl > 0) {
        const ratio = hp / lvl;
        if (smallest === null || ratio < smallest) {
          smallest = ratio;
        }
      }
    }
    return smallest;
  }

  const mobColumnDefs = {
    hpPerLevel: {
      key: 'hpPerLevel',
      header: 'HP/Lvl',
      width: '70px',
      filterPlaceholder: '>50',
      getValue: (item) => getSmallestHpPerLevel(item),
      format: (v) => v != null ? Math.round(v) : '-'
    },
    level: {
      key: 'level',
      header: 'Level Range',
      width: '90px',
      filterPlaceholder: '>10',
      getValue: (item) => getLevelRange(item)?.max ?? null,
      format: (_v, item) => {
        const range = getLevelRange(item);
        return range ? `${range.min}-${range.max}` : '-';
      }
    },
    hp: {
      key: 'hp',
      header: 'HP Range',
      width: '80px',
      filterPlaceholder: '>100',
      getValue: (item) => getHealthRange(item)?.max ?? null,
      format: (_v, item) => {
        const range = getHealthRange(item);
        return range ? `${range.min}-${range.max}` : '-';
      }
    },
    cat4: {
      key: 'cat4',
      header: 'Cat 4',
      width: '55px',
      filterPlaceholder: 'Yes',
      getValue: (item) => isCat4Mob(item) ? 1 : 0,
      format: (v) => v ? 'Yes' : 'No'
    },
    type: {
      key: 'type',
      header: 'Type',
      width: '65px',
      filterPlaceholder: 'Animal',
      getValue: (item) => item.Type,
      format: (v) => v || '-'
    },
    planet: {
      key: 'planet',
      header: 'Planet',
      width: '80px',
      filterPlaceholder: 'Calypso',
      getValue: (item) => item.Planet?.Name,
      format: (v) => v || '-'
    },
    sweatable: {
      key: 'sweatable',
      header: 'Sweat',
      width: '55px',
      filterPlaceholder: 'Yes',
      getValue: (item) => item.Properties?.IsSweatable ? 1 : 0,
      format: (v) => v ? 'Yes' : 'No'
    },
    apm: {
      key: 'apm',
      header: 'APM',
      width: '50px',
      filterPlaceholder: '>20',
      getValue: (item) => item.Properties?.AttacksPerMinute,
      format: (v) => v != null ? v : '-'
    },
    atkRange: {
      key: 'atkRange',
      header: 'Range',
      width: '55px',
      filterPlaceholder: '>5',
      getValue: (item) => item.Properties?.AttackRange,
      format: (v) => v != null ? v : '-'
    },
    aggrRange: {
      key: 'aggrRange',
      header: 'Aggr Range',
      width: '70px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.AggressionRange,
      format: (v) => v != null ? v : '-'
    },
    aggrTimer: {
      key: 'aggrTimer',
      header: 'Aggr Timer',
      width: '80px',
      getValue: (item) => item.Properties?.AggressionTimer,
      format: (v) => v || '-'
    }
  };

  const navTableColumns = [
    mobColumnDefs.hpPerLevel,
    mobColumnDefs.level,
    mobColumnDefs.hp,
    mobColumnDefs.cat4
  ];

  // Full-width table columns (superset of navTableColumns with additional stats)
  const navFullWidthColumns = [
    ...navTableColumns,
    mobColumnDefs.type,
    mobColumnDefs.planet,
    mobColumnDefs.sweatable,
    mobColumnDefs.apm,
    mobColumnDefs.atkRange
  ];

  const allAvailableColumns = Object.values(mobColumnDefs);

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Information', href: '/information' },
    { label: 'Mobs', href: '/information/mobs' },
    ...(activeMob?.Name ? [{ label: activeMob.Name }] : isCreateMode ? [{ label: 'New Mob' }] : [])
  ];

  // SEO
  $: seoDescription = activeMob?.Properties?.Description ||
    `${activeMob?.Name || 'Mob'} - ${activeMob?.Type || ''} mob on ${activeMob?.Planet?.Name || 'Calypso'} in Entropia Universe.`;

  $: canonicalUrl = activeMob?.Name
    ? `https://entropianexus.com/information/mobs/${encodeURIComponentSafe(activeMob.Name)}`
    : 'https://entropianexus.com/information/mobs';

  // Image URL for SEO (approved images only)
  $: entityImageUrl = mob?.Id ? `/api/img/mob/${mob.Id}` : null;

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    maturities: true,
    locations: true,
    loots: true,
    codex: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-mob-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-mob-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== MOB CALCULATIONS ==========
  function getDamageSpread(mobData, attackName) {
    if (!mobData?.Maturities) return null;

    let attackSpreads = mobData.Maturities.map(x => {
      let attack = x.Attacks?.find(y => y.Name === attackName);
      if (attack == null) return null;
      return {
        Impact: attack.Damage?.Impact || 0,
        Cut: attack.Damage?.Cut || 0,
        Stab: attack.Damage?.Stab || 0,
        Penetration: attack.Damage?.Penetration || 0,
        Shrapnel: attack.Damage?.Shrapnel || 0,
        Burn: attack.Damage?.Burn || 0,
        Cold: attack.Damage?.Cold || 0,
        Acid: attack.Damage?.Acid || 0,
        Electric: attack.Damage?.Electric || 0,
      }
    }).filter(x => x != null);

    if (attackSpreads.length === 0) {
      // Check if the attack exists at all
      const hasAttack = mobData.Maturities.some(x => x.Attacks?.some(y => y.Name === attackName));
      if (hasAttack) {
        return { Impact: 0, Cut: 0, Stab: 0, Penetration: 0, Shrapnel: 0, Burn: 0, Cold: 0, Acid: 0, Electric: 0 };
      }
      return null;
    }

    // Average the damage spreads
    const avgSpread = {};
    ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'].forEach(key => {
      avgSpread[key] = attackSpreads.map(x => x[key]).reduce((a, b) => a + b, 0) / attackSpreads.length;
    });
    return avgSpread;
  }

  function getLowestHpPerLevel(mobData) {
    if (!mobData?.Maturities || mobData.Maturities.length === 0) return null;

    // Exclude boss maturities from tier 1 calculations
    const nonBossMaturities = mobData.Maturities.filter(m => !m.Properties?.Boss);
    if (nonBossMaturities.length === 0) return null;

    let lowest = nonBossMaturities.reduce((a, b) => {
      const aValid = a.Properties?.Health != null && a.Properties?.Level != null;
      const bValid = b.Properties?.Health != null && b.Properties?.Level != null;

      if (aValid && bValid) {
        return a.Properties.Health / a.Properties.Level < b.Properties.Health / b.Properties.Level ? a : b;
      }
      if (aValid) return a;
      if (bValid) return b;
      return a;
    });

    if (!lowest.Properties?.Level || !lowest.Properties?.Health) return null;
    return lowest.Properties.Health / lowest.Properties.Level;
  }

  function getHealthRange(mobData) {
    if (!mobData?.Maturities || mobData.Maturities.length === 0) return null;
    // Exclude boss maturities from tier 1 calculations
    const healths = mobData.Maturities
      .filter(m => !m.Properties?.Boss)
      .map(m => m.Properties?.Health)
      .filter(h => h != null);
    if (healths.length === 0) return null;
    return {
      min: Math.min(...healths),
      max: Math.max(...healths)
    };
  }

  function getLevelRange(mobData) {
    if (!mobData?.Maturities || mobData.Maturities.length === 0) return null;
    // Exclude boss maturities from tier 1 calculations
    const levels = mobData.Maturities
      .filter(m => !m.Properties?.Boss)
      .map(m => m.Properties?.Level)
      .filter(l => l != null);
    if (levels.length === 0) return null;
    return {
      min: Math.min(...levels),
      max: Math.max(...levels)
    };
  }

  function getMobTypeLabel(mobData) {
    if (!mobData) return 'Unknown';
    if (mobData.Type) return mobData.Type;

    // Infer from scanning profession
    const scanProf = mobData.ScanningProfession?.Name;
    if (scanProf === 'Animal Investigator') return 'Animal';
    if (scanProf === 'Mutant Investigator') return 'Mutant';
    if (scanProf === 'Robot Investigator') return 'Robot';
    return 'Unknown';
  }

  function getScanningProfession(mobData) {
    const type = getMobTypeLabel(mobData);
    if (type === 'Animal') return 'Animal Investigator';
    if (type === 'Mutant') return 'Mutant Investigator';
    if (type === 'Robot') return 'Robot Investigator';
    return null;
  }

  function getLootingProfession(mobData) {
    const type = getMobTypeLabel(mobData);
    if (type === 'Animal') return 'Animal Looter';
    if (type === 'Mutant') return 'Mutant Looter';
    if (type === 'Robot') return 'Robot Looter';
    return null;
  }

  // Reactive calculations
  $: primaryDamageSpread = getDamageSpread(activeMob, 'Primary');
  $: secondaryDamageSpread = getDamageSpread(activeMob, 'Secondary');
  $: tertiaryDamageSpread = getDamageSpread(activeMob, 'Tertiary');
  $: lowestHpPerLevel = getLowestHpPerLevel(activeMob);
  $: healthRange = getHealthRange(activeMob);
  $: levelRange = getLevelRange(activeMob);
  $: mobType = getMobTypeLabel(activeMob);
  $: isAsteroid = activeMob?.Type === 'Asteroid';
  $: scanningProfession = getScanningProfession(activeMob);
  $: lootingProfession = getLootingProfession(activeMob);
  $: hasCodex = activeMob?.Species?.Properties?.CodexBaseCost != null;

  // ========== EDIT HANDLERS ==========
  function handleDescriptionChange(event) {
    updateField('Properties.Description', event.detail);
  }
</script>

<WikiSEO
  title={activeMob?.Name || 'Mobs'}
  description={seoDescription}
  entityType="mob"
  entity={activeMob}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={activeMob}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

  <WikiPage
    title="Mobs"
    {breadcrumbs}
    entity={activeMob}
    basePath="/information/mobs"
    {navItems}
    {navFilters}
    {navTableColumns}
    {navFullWidthColumns}
    navAllAvailableColumns={allAvailableColumns}
    navPageTypeId="mobs"
    {user}
    editable={true}
  {canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
>
  {#if activeMob || isCreateMode}
    <!-- Pending Change Banner -->
    {#if $existingPendingChange && !$editMode && !isCreateMode}
      <div class="pending-change-banner">
        <div class="banner-content">
          <span class="banner-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
          </span>
          <span class="banner-text">
            This mob has a pending change by <strong>{$existingPendingChange.author_name || 'Unknown'}</strong>
            ({$existingPendingChange.state})
          </span>
        </div>
        <div class="banner-actions">
          {#if $viewingPendingChange}
            <button class="banner-btn" on:click={() => setViewingPendingChange(false)}>
              View Current
            </button>
          {:else}
            <button class="banner-btn primary" on:click={() => setViewingPendingChange(true)}>
              View Pending
            </button>
          {/if}
        </div>
      </div>
    {/if}

    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeMob?.Id}
            entityName={activeMob?.Name}
            entityType="mob"
            {user}
            isEditMode={$editMode}
            {isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              value={activeMob?.Name || ''}
              path="Name"
              type="text"
              placeholder="Enter mob name"
            />
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge type-{mobType.toLowerCase()}">{mobType}</span>
            <span>{activeMob?.Planet?.Name || 'Calypso'}</span>
          </div>
        </div>

        <!-- Key Stats -->
        <div class="stats-section tier-1 tier-blue">
          <div class="stat-row primary">
            <span class="stat-label">HP/Level</span>
            <span class="stat-value">{lowestHpPerLevel ? lowestHpPerLevel.toFixed(2) : 'N/A'}</span>
          </div>
          {#if levelRange}
            <div class="stat-row primary">
              <span class="stat-label">Level Range</span>
              <span class="stat-value">{levelRange.min} - {levelRange.max}</span>
            </div>
          {/if}
          {#if healthRange}
            <div class="stat-row primary">
              <span class="stat-label">HP Range</span>
              <span class="stat-value">{healthRange.min} - {healthRange.max}</span>
            </div>
          {/if}
        </div>

        <!-- General Info -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
            <div class="stat-row">
              <span class="stat-label">Species</span>
              <span class="stat-value">
                {#if $editMode}
                  <SearchInput
                    value={activeMob?.Species?.Name || ''}
                    placeholder="Search species..."
                    options={speciesOptions}
                    on:change={(e) => updateField('Species.Name', e.detail.value || '')}
                    on:select={(e) => updateField('Species.Name', e.detail.value || '')}
                  />
                {:else}
                  {activeMob?.Species?.Name || 'N/A'}
                {/if}
              </span>
            </div>
          <div class="stat-row">
            <span class="stat-label">Planet</span>
            <span class="stat-value">
              <InlineEdit
                value={activeMob?.Planet?.Name || 'Calypso'}
                path="Planet.Name"
                type="select"
                options={planetOptions}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">
              <InlineEdit
                value={activeMob?.Type || 'Animal'}
                path="Type"
                type="select"
                options={typeOptions}
              />
            </span>
          </div>
          {#if !isAsteroid}
            <div class="stat-row">
              <span class="stat-label">Attacks/Min</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeMob?.Properties?.AttacksPerMinute}
                  path="Properties.AttacksPerMinute"
                  type="number"
                  step={0.1}
                  min={0}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Attack Range</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeMob?.Properties?.AttackRange}
                  path="Properties.AttackRange"
                  type="number"
                  suffix="m"
                  step={0.1}
                  min={0}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Aggro Range</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeMob?.Properties?.AggressionRange}
                  path="Properties.AggressionRange"
                  type="number"
                  suffix="m"
                  step={0.1}
                  min={0}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Aggro Timer</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeMob?.Properties?.AggressionTimer}
                  path="Properties.AggressionTimer"
                  type="select"
                  placeholder="N/A"
                  options={[
                    { value: 'Very Long', label: 'Very Long' },
                    { value: 'Long', label: 'Long' },
                    { value: 'Medium', label: 'Medium' },
                    { value: 'Short', label: 'Short' },
                    { value: 'Very Short', label: 'Very Short' },
                    { value: 'Instant', label: 'Instant' },
                  ]}
                />
              </span>
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Sweatable</span>
            <span class="stat-value" class:highlight-yes={activeMob?.Properties?.IsSweatable}>
              <InlineEdit
                value={activeMob?.Properties?.IsSweatable}
                path="Properties.IsSweatable"
                type="checkbox"
              />
            </span>
          </div>
        </div>

        <!-- Skills -->
        {#if !isAsteroid}
          <div class="stats-section">
            <h4 class="section-title">Skills</h4>
            <div class="stat-row">
              <span class="stat-label">Defense</span>
              <span class="stat-value">
                {#if $editMode}
                  <InlineEdit
                    value={activeMob?.DefensiveProfession?.Name || ''}
                    path="DefensiveProfession.Name"
                    type="select"
                    options={defenseProfessionOptions}
                    placeholder="Select..."
                  />
                {:else if activeMob?.DefensiveProfession?.Name}
                  <a href={getTypeLink(activeMob.DefensiveProfession.Name, 'Profession')} class="profession-link">
                    {activeMob.DefensiveProfession.Name}
                  </a>
                {:else}
                  N/A
                {/if}
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Scanning</span>
              <span class="stat-value">
                {#if scanningProfession}
                  <a href={getTypeLink(scanningProfession, 'Profession')} class="profession-link">
                    {scanningProfession}
                  </a>
                {:else}
                  N/A
                {/if}
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Looting</span>
              <span class="stat-value">
                {#if lootingProfession}
                  <a href={getTypeLink(lootingProfession, 'Profession')} class="profession-link">
                    {lootingProfession}
                  </a>
                {:else}
                  N/A
                {/if}
              </span>
            </div>
          </div>
        {/if}

        <!-- Damage Breakdown -->
        {#if !isAsteroid}
          <div class="stats-section damage-section">
            <h4 class="section-title">Damage Breakdown</h4>
            {#if primaryDamageSpread}
              <MobDamageGrid damageSpread={primaryDamageSpread} label="Primary" />
            {/if}
            {#if secondaryDamageSpread}
              <MobDamageGrid damageSpread={secondaryDamageSpread} label="Secondary" />
            {/if}
            {#if tertiaryDamageSpread}
              <MobDamageGrid damageSpread={tertiaryDamageSpread} label="Tertiary" />
            {/if}
            {#if !primaryDamageSpread && !secondaryDamageSpread && !tertiaryDamageSpread}
              <div class="no-data">No damage data available</div>
            {/if}
          </div>
        {/if}

        <!-- Codex Info -->
        {#if hasCodex}
          <div class="stats-section">
            <h4 class="section-title">Codex</h4>
            <div class="stat-row">
              <span class="stat-label">Base Cost</span>
              <span class="stat-value">{activeMob?.Species?.Properties?.CodexBaseCost} PED</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Type</span>
              <span class="stat-value">{activeMob?.Species?.Properties?.CodexType || 'Mob'}</span>
            </div>
          </div>
        {/if}

        <!-- Quick Link to Map -->
        {#if activeMob?.Spawns && activeMob.Spawns.length > 0}
          <a href="/maps/{activeMob?.Planet?.Name?.toLowerCase() || 'calypso'}" class="map-link-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon>
              <line x1="8" y1="2" x2="8" y2="18"></line>
              <line x1="16" y1="6" x2="16" y2="22"></line>
            </svg>
            <span>View on Map</span>
          </a>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            value={activeMob?.Name || ''}
            path="Name"
            type="text"
            placeholder="Enter mob name"
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeMob?.Properties?.Description || ''}
              on:change={handleDescriptionChange}
              placeholder="Enter a description for this mob..."
            />
          {:else if activeMob?.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeMob.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeMob?.Name || 'This mob'} is a {mobType.toLowerCase()} found on {activeMob?.Planet?.Name || 'Calypso'}.
            </div>
          {/if}
        </div>

        <!-- Maturities Section -->
        <DataSection
          title="Maturities"
          icon=""
          bind:expanded={panelStates.maturities}
          subtitle="{activeMob?.Maturities?.length || 0} maturities"
          on:toggle={savePanelStates}
        >
          {#if $editMode}
            <MobMaturitiesEdit
              maturities={activeMob?.Maturities || []}
              type={activeMob?.Type}
              fieldPath="Maturities"
            />
          {:else}
            <MobMaturities maturities={activeMob?.Maturities} type={activeMob?.Type} />
          {/if}
        </DataSection>

        <!-- Locations Section -->
        {#if $editMode || (activeMob?.Spawns && activeMob.Spawns.length > 0)}
          <DataSection
            title="Locations"
            icon=""
            bind:expanded={panelStates.locations}
            subtitle="{activeMob?.Spawns?.length || 0} spawn{(activeMob?.Spawns?.length || 0) !== 1 ? 's' : ''}"
            on:toggle={savePanelStates}
          >
            {#if $editMode}
              <MobSpawnsEdit
                spawns={activeMob?.Spawns || []}
                fieldPath="Spawns"
                mobName={activeMob?.Name || ''}
                maturities={activeMob?.Maturities || []}
                allMobs={allItems}
              />
            {:else}
              <MobLocations mobName={activeMob?.Name} mobSpawns={activeMob.Spawns} />
            {/if}
          </DataSection>
        {/if}

        <!-- Loots Section -->
        {#if $editMode || (activeMob?.Loots && activeMob.Loots.length > 0)}
          <DataSection
            title="Loots"
            icon=""
            bind:expanded={panelStates.loots}
            subtitle="{activeMob?.Loots?.length || 0} item{(activeMob?.Loots?.length || 0) !== 1 ? 's' : ''}"
            on:toggle={savePanelStates}
          >
            {#if $editMode}
              <MobLootsEdit
                loots={activeMob?.Loots || []}
                fieldPath="Loots"
                maturities={activeMob?.Maturities || []}
                allItems={itemsList}
              />
            {:else}
              <MobLoots loots={activeMob.Loots} />
            {/if}
          </DataSection>
        {/if}

        <!-- Codex Section -->
        {#if !isCreateMode && hasCodex}
          <DataSection
            title="Codex Calculator"
            icon=""
            bind:expanded={panelStates.codex}
            on:toggle={savePanelStates}
          >
            <MobCodex
              baseCost={activeMob?.Species?.Properties?.CodexBaseCost}
              codexType={activeMob?.Species?.Properties?.CodexType}
              mobType={mobType}
              skills={skillsList}
            />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Mobs</h2>
      <p>Select a mob from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .pending-change-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background-color: var(--warning-bg, #fef3c7);
    border: 1px solid var(--warning-border, #f59e0b);
    border-radius: 8px;
    margin-bottom: 16px;
  }

  :global(.dark) .pending-change-banner {
    background-color: rgba(245, 158, 11, 0.1);
    border-color: rgba(245, 158, 11, 0.3);
  }

  .banner-content {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .banner-icon {
    color: var(--warning-color, #d97706);
  }

  .banner-text {
    font-size: 14px;
    color: var(--text-color);
  }

  .banner-actions {
    display: flex;
    gap: 8px;
  }

  .banner-btn {
    padding: 6px 12px;
    font-size: 13px;
    border-radius: 4px;
    border: 1px solid var(--border-color, #555);
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s;
  }

  .banner-btn:hover {
    background-color: var(--secondary-color);
  }

  .banner-btn.primary {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .banner-btn.primary:hover {
    opacity: 0.9;
  }

  @media (min-width: 1400px) {
    .wiki-infobox-float {
      width: 320px;
    }
  }

  .type-badge.type-animal {
    background-color: #4ade80;
  }

  .type-badge.type-mutant {
    background-color: #a78bfa;
  }

  .type-badge.type-robot {
    background-color: #60a5fa;
  }

  .type-badge.type-asteroid {
    background-color: #fbbf24;
    color: #000;
  }

  .damage-section {
    padding: 12px;
  }

  .no-data {
    color: var(--text-muted, #999);
    font-style: italic;
    font-size: 13px;
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .pending-change-banner {
      flex-direction: column;
      gap: 12px;
      align-items: flex-start;
    }
  }

  /* Extra small mobile - portrait phones */
  @media (max-width: 400px) {
    .wiki-infobox-float {
      padding: 10px;
    }

    .infobox-header {
      padding-bottom: 10px;
    }

    .infobox-title {
      font-size: 15px;
    }

    .stats-section {
      padding: 8px;
    }

    .stats-section.tier-1 {
      padding: 10px;
    }

    .stats-section.tier-1 .stat-row.primary {
      padding: 6px 10px;
    }

    .stats-section.tier-1 .stat-value {
      font-size: 16px;
    }

    .section-title {
      font-size: 11px;
    }

    .stat-row {
      font-size: 11px;
      padding: 3px 0;
    }

    .map-link-btn {
      padding: 8px 12px;
      font-size: 12px;
    }
  }
</style>

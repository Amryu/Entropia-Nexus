<!--
  @component Mob Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: General stats, damage spread, skill info
  Article: Description → Maturities → Locations → Loots → Codex
-->
<script>
  import { run } from 'svelte/legacy';

  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { onMount, onDestroy, tick } from 'svelte';
  import { encodeURIComponentSafe, getTypeLink, getLatestPendingUpdate, loadEditDeps } from '$lib/util';
  import { getPlanetNavFilter } from '$lib/mapUtil';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiNavigation from '$lib/components/wiki/WikiNavigation.svelte';
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
  import MobGlobals from '$lib/components/wiki/mobs/MobGlobals.svelte';

  // Mob edit components
  import MobMaturitiesEdit from '$lib/components/wiki/mobs/MobMaturitiesEdit.svelte';
  import MobSpawnsEdit from '$lib/components/wiki/mobs/MobSpawnsEdit.svelte';
  import MobLootsEdit from '$lib/components/wiki/mobs/MobLootsEdit.svelte';
  import CreateSpeciesDialog from '$lib/components/wiki/mobs/CreateSpeciesDialog.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  // Wiki edit state
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
  } from '$lib/stores/wikiEditState';

  let { data = $bindable() } = $props();

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = $state(false);
  run(() => {
    if ($editMode && data.speciesList === null && !editDepsLoading) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'speciesList', url: '/api/mobspecies' },
        { key: 'itemsList', url: '/api/items?limit=5000' },
        { key: 'planetsList', url: '/api/planets' }
      ]).then(deps => {
        data = { ...data, ...deps };
        editDepsLoading = false;
      });
    }
  });

  let mob = $derived(data.object);
  let user = $derived(data.session?.user);
  let allItems = $derived(data.allItems || []);
  let speciesList = $derived(data.speciesList || []);
  let itemsList = $derived(data.itemsList || []);  // Items for loot autocomplete
  let planetsList = $derived(data.planetsList || []);  // All planets from API
  let skillsList = $derived(data.skillsList || []);  // Skills for codex calculator
  let pendingChange = $derived(data.pendingChange);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let isCreateMode = $derived(data.isCreateMode || false);
  let currentChangeId = $derived($page.url.searchParams.get('changeId'));
  let activeView = $derived(data.view || 'mobs');
  let isMaturityView = $derived(activeView === 'maturities' && !isCreateMode);
  let selectedMaturityId = $derived(data.selectedMaturityId ?? null);
  let mobEntityId = $derived(mob?.Id ?? mob?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, mobEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));

  // Build species options for autocomplete
  let showCreateSpeciesDialog = $state(false);
  let showEditSpeciesDialog = $state(false);
  let localSpeciesList = $state([]);
  let localSpeciesSeed = $state('');
  run(() => {
    const seed = JSON.stringify((speciesList || []).map(s => [
      s?.Name || '',
      s?.Properties?.CodexBaseCost ?? null,
      s?.Properties?.CodexType ?? null
    ]));
    if (seed !== localSpeciesSeed) {
      localSpeciesSeed = seed;
      localSpeciesList = [...(speciesList || [])];
    }
  });
  let speciesOptions = $derived(localSpeciesList.map(s => ({ value: s.Name, label: s.Name })));

  // Verified users can edit
  let canEdit = $derived(user?.verified || user?.grants?.includes('wiki.edit'));

  // Planet options from API (filter out Id=0 which is "Unknown")
  let planetOptions = $derived(planetsList
    .filter(p => p.Id > 0)
    .map(p => ({ value: p.Name, label: p.Name })));

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

  // Track initialization to avoid resetting edits on query-only navigation.
  let lastInitKey = $state(null);
  run(() => {
    const initKey = `Mob-${mob?.Id ?? 'new'}-${isCreateMode}-${data.existingChange?.id ?? 'none'}`;
    if (user && initKey !== lastInitKey) {
      lastInitKey = initKey;
      const existingChange = data.existingChange || null;
      const initialEntity = isCreateMode
        ? (existingChange?.data || emptyMob)
        : mob;
      const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
      initEditState(initialEntity, 'Mob', isCreateMode, editChange);
    }
  });

  // Set pending change in store when it changes
  run(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });

  // Active mob: use currentEntity in edit mode, pendingChange data when viewing, otherwise original
  let activeMob = $derived($editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : mob);

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });

  // Sidebar expanded/full-width state
  let sidebarExpanded = $state(false);
  let sidebarFullWidth = $state(false);

  // Damage type abbreviations for sidebar columns
  const damageAbbreviations = {
    Impact: 'Imp', Cut: 'Cut', Stab: 'Stab', Penetration: 'Pen',
    Shrapnel: 'Shr', Burn: 'Brn', Cold: 'Cld', Acid: 'Acd', Electric: 'Elc'
  };

  function formatDamageHtml(damageObj) {
    if (!damageObj) return '-';
    const parts = Object.entries(damageObj)
      .filter(([_, v]) => v != null && v > 0)
      .map(([key, value]) =>
        `<span style="color: var(--damage-${key.toLowerCase()})">${Math.round(value)} ${damageAbbreviations[key] || key}</span>`
      );
    return parts.length > 0 ? parts.join('<span style="opacity:0.5">/</span>') : '-';
  }

  // Build navigation items from mobs
  let navItems = $derived(allItems);

  function getPrimaryDamage(maturity) {
    const primaryAttack = maturity?.Attacks?.find(a => a.Name === 'Primary') || maturity?.Attacks?.[0];
    return primaryAttack?.TotalDamage ?? null;
  }

  function getMaturityDefense(maturity) {
    const def = maturity?.Properties?.Defense;
    if (!def) return null;
    const total = (def.Impact || 0) + (def.Cut || 0) + (def.Stab || 0) +
      (def.Penetration || 0) + (def.Shrapnel || 0) + (def.Burn || 0) +
      (def.Cold || 0) + (def.Acid || 0) + (def.Electric || 0);
    return total > 0 ? total : null;
  }

  /**
   * When mob-level AttacksPerMinute is changed, cascade to all maturities.
   */
  function handleMobApmChange(event) {
    const newApm = event.detail.value;
    const maturities = $currentEntity?.Maturities;
    if (!maturities || maturities.length === 0) return;

    const updatedMaturities = maturities.map(m => ({
      ...m,
      Properties: {
        ...m.Properties,
        AttacksPerMinute: newApm
      }
    }));
    updateField('Maturities', updatedMaturities);
  }

  // Flatten mobs to maturity rows for sidebar maturity mode.
  let maturityNavItems = $derived((allItems || []).flatMap((mobItem) => {
    const mobName = mobItem?.Name;
    if (!mobName || !Array.isArray(mobItem?.Maturities)) return [];

    return mobItem.Maturities
      .map((maturity) => {
        const level = maturity?.Properties?.Level ?? null;
        const hp = maturity?.Properties?.Health ?? null;
        const hpPerLevel = hp != null && level != null && level > 0 ? hp / level : null;
        const maturityName = maturity?.Name?.trim()?.length ? maturity.Name : 'Single Maturity';
        const maturityId = maturity?.Id;
        if (maturityId == null) return null;

        const primaryAttack = maturity?.Attacks?.find(a => a.Name === 'Primary') || maturity?.Attacks?.[0];
        const secondaryAttack = maturity?.Attacks?.find(a => a.Name === 'Secondary') || maturity?.Attacks?.[1];
        const tertiaryAttack = maturity?.Attacks?.find(a => a.Name === 'Tertiary') || maturity?.Attacks?.[2];
        return {
          Id: maturityId,
          Name: `${mobName} - ${maturityName}`,
          MaturityName: maturityName,
          MobName: mobName,
          MobId: mobItem?.Id ?? null,
          Planet: mobItem?.Planet?.Name || null,
          Type: mobItem?.Type || null,
          Level: level,
          HP: hp,
          HpPerLevel: hpPerLevel,
          Boss: maturity?.Properties?.Boss === true,
          PrimaryDamage: primaryAttack?.TotalDamage ?? null,
          PrimaryDamageComposition: primaryAttack?.Damage || null,
          SecondaryDamage: secondaryAttack?.TotalDamage ?? null,
          SecondaryDamageComposition: secondaryAttack?.Damage || null,
          TertiaryDamage: tertiaryAttack?.TotalDamage ?? null,
          TertiaryDamageComposition: tertiaryAttack?.Damage || null,
          Defense: getMaturityDefense(maturity),
          Sweatable: mobItem?.Properties?.IsSweatable || false,
          APM: mobItem?.Properties?.AttacksPerMinute ?? null,
          AttackRange: mobItem?.Properties?.AttackRange ?? null,
          AggressionRange: mobItem?.Properties?.AggressionRange ?? null,
          AggressionTimer: mobItem?.Properties?.AggressionTimer || null,
          Cat4: mobItem?.Species?.Properties?.CodexType === 'MobLooter'
        };
      })
      .filter(Boolean);
  }));

  // Navigation filters - filter by planet and type
  const navFilters = [
    getPlanetNavFilter('Planet.Name'),
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

  const maturityNavFilters = [
    getPlanetNavFilter('Planet'),
    {
      key: 'Type',
      label: 'Type',
      values: [
        { value: 'Animal', label: 'Animal' },
        { value: 'Mutant', label: 'Mutant' },
        { value: 'Robot', label: 'Robot' },
        { value: 'Asteroid', label: 'Asteroid' },
      ]
    },
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
    },
    damage: {
      key: 'damage',
      header: 'Damage (%)',
      width: '120px',
      html: true,
      getValue: (item) => {
        const mats = item.Maturities?.filter(m => !m.Properties?.Boss);
        const mat = mats?.length ? mats[0] : item.Maturities?.[0];
        const primary = mat?.Attacks?.find(a => a.Name === 'Primary') || mat?.Attacks?.[0];
        return primary?.TotalDamage ?? null;
      },
      format: (_v, item) => {
        const mats = item.Maturities?.filter(m => !m.Properties?.Boss);
        const mat = mats?.length ? mats[0] : item.Maturities?.[0];
        const primary = mat?.Attacks?.find(a => a.Name === 'Primary') || mat?.Attacks?.[0];
        return formatDamageHtml(primary?.Damage);
      }
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
    mobColumnDefs.damage,
    mobColumnDefs.type,
    mobColumnDefs.planet,
    mobColumnDefs.sweatable,
    mobColumnDefs.apm,
    mobColumnDefs.atkRange
  ];

  const allAvailableColumns = Object.values(mobColumnDefs);

  const maturityColumnDefs = {
    mob: {
      key: 'mob',
      header: 'Mob',
      width: '120px',
      filterPlaceholder: 'Atrox',
      getValue: (item) => item.MobName,
      format: (v) => v || '-'
    },
    maturity: {
      key: 'maturity',
      header: 'Maturity',
      width: '105px',
      filterPlaceholder: 'Young',
      getValue: (item) => item.MaturityName,
      format: (v) => v || '-'
    },
    level: {
      key: 'level',
      header: 'Level',
      width: '65px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Level,
      format: (v) => v != null ? v : '-'
    },
    hp: {
      key: 'hp',
      header: 'HP',
      width: '70px',
      filterPlaceholder: '>100',
      getValue: (item) => item.HP,
      format: (v) => v != null ? v : '-'
    },
    hpPerLevel: {
      key: 'hpPerLevel',
      header: 'HP/Lvl',
      width: '70px',
      filterPlaceholder: '>50',
      getValue: (item) => item.HpPerLevel,
      format: (v) => v != null ? Math.round(v) : '-'
    },
    primaryDamage: {
      key: 'primaryDamage',
      header: 'Damage',
      width: '70px',
      filterPlaceholder: '>20',
      getValue: (item) => item.PrimaryDamage,
      format: (v) => v != null ? v : '-'
    },
    damage: {
      key: 'damage',
      header: 'Damage (%)',
      width: '120px',
      html: true,
      getValue: (item) => item.PrimaryDamage ?? null,
      format: (_v, item) => formatDamageHtml(item.PrimaryDamageComposition)
    },
    secondaryDamage: {
      key: 'secondaryDamage',
      header: 'Secondary',
      width: '70px',
      filterPlaceholder: '>20',
      getValue: (item) => item.SecondaryDamage,
      format: (v) => v != null ? v : '-'
    },
    secondaryDamageComp: {
      key: 'secondaryDamageComp',
      header: 'Secondary (%)',
      width: '120px',
      html: true,
      getValue: (item) => item.SecondaryDamage ?? null,
      format: (_v, item) => formatDamageHtml(item.SecondaryDamageComposition)
    },
    tertiaryDamage: {
      key: 'tertiaryDamage',
      header: 'Tertiary',
      width: '70px',
      filterPlaceholder: '>20',
      getValue: (item) => item.TertiaryDamage,
      format: (v) => v != null ? v : '-'
    },
    tertiaryDamageComp: {
      key: 'tertiaryDamageComp',
      header: 'Tertiary (%)',
      width: '120px',
      html: true,
      getValue: (item) => item.TertiaryDamage ?? null,
      format: (_v, item) => formatDamageHtml(item.TertiaryDamageComposition)
    },
    defense: {
      key: 'defense',
      header: 'Defense',
      width: '70px',
      filterPlaceholder: '>20',
      getValue: (item) => item.Defense,
      format: (v) => v != null ? v : '-'
    },
    boss: {
      key: 'boss',
      header: 'Boss',
      width: '60px',
      filterPlaceholder: 'Yes',
      getValue: (item) => item.Boss ? 1 : 0,
      format: (v) => v ? 'Yes' : 'No'
    },
    planet: {
      key: 'planet',
      header: 'Planet',
      width: '80px',
      filterPlaceholder: 'Calypso',
      getValue: (item) => item.Planet,
      format: (v) => v || '-'
    },
    type: {
      key: 'type',
      header: 'Type',
      width: '70px',
      filterPlaceholder: 'Animal',
      getValue: (item) => item.Type,
      format: (v) => v || '-'
    },
    sweatable: {
      key: 'sweatable',
      header: 'Sweat',
      width: '55px',
      filterPlaceholder: 'Yes',
      getValue: (item) => item.Sweatable ? 1 : 0,
      format: (v) => v ? 'Yes' : 'No'
    },
    apm: {
      key: 'apm',
      header: 'APM',
      width: '50px',
      filterPlaceholder: '>20',
      getValue: (item) => item.APM,
      format: (v) => v != null ? v : '-'
    },
    atkRange: {
      key: 'atkRange',
      header: 'Range',
      width: '55px',
      filterPlaceholder: '>5',
      getValue: (item) => item.AttackRange,
      format: (v) => v != null ? v : '-'
    },
    aggrRange: {
      key: 'aggrRange',
      header: 'Aggr Range',
      width: '70px',
      filterPlaceholder: '>10',
      getValue: (item) => item.AggressionRange,
      format: (v) => v != null ? v : '-'
    },
    aggrTimer: {
      key: 'aggrTimer',
      header: 'Aggr Timer',
      width: '80px',
      getValue: (item) => item.AggressionTimer,
      format: (v) => v || '-'
    },
    cat4: {
      key: 'cat4',
      header: 'Cat 4',
      width: '55px',
      filterPlaceholder: 'Yes',
      getValue: (item) => item.Cat4 ? 1 : 0,
      format: (v) => v ? 'Yes' : 'No'
    }
  };

  const maturityNavTableColumns = [
    maturityColumnDefs.mob,
    maturityColumnDefs.maturity,
    maturityColumnDefs.level,
    maturityColumnDefs.hp
  ];

  const maturityNavFullWidthColumns = [
    ...maturityNavTableColumns,
    maturityColumnDefs.hpPerLevel,
    maturityColumnDefs.damage,
    maturityColumnDefs.primaryDamage,
    maturityColumnDefs.defense,
    maturityColumnDefs.type,
    maturityColumnDefs.planet
  ];

  const maturityAllAvailableColumns = Object.values(maturityColumnDefs);

  let activeSidebarItems = $derived(isMaturityView ? maturityNavItems : navItems);
  let activeSidebarFilters = $derived(isMaturityView ? maturityNavFilters : navFilters);
  let activeSidebarTableColumns = $derived(isMaturityView ? maturityNavTableColumns : navTableColumns);
  let activeSidebarFullWidthColumns = $derived(isMaturityView ? maturityNavFullWidthColumns : navFullWidthColumns);
  let activeSidebarColumns = $derived(isMaturityView ? maturityAllAvailableColumns : allAvailableColumns);
  let activeSidebarPageTypeId = $derived(isMaturityView ? 'mobs-maturities' : 'mobs');
  let sidebarPendingCreates = $derived(isMaturityView ? [] : userPendingCreates);
  let sidebarPendingUpdates = $derived(isMaturityView ? [] : userPendingUpdates);

  function switchSidebar(mode) {
    if (mode === 'maturities' && isMaturityView) return;
    if (mode === 'mobs' && !isMaturityView) return;

    const nextUrl = new URL($page.url);
    if (mode === 'maturities') {
      nextUrl.searchParams.set('view', 'maturities');
    } else {
      nextUrl.searchParams.delete('view');
      nextUrl.searchParams.delete('maturity');
    }

    goto(`${nextUrl.pathname}${nextUrl.search}`);
  }

  function getMaturitySidebarHref(item) {
    const mobSlug = encodeURIComponentSafe(item.MobName);
    return `/information/mobs/${mobSlug}?view=maturities&maturity=${item.Id}`;
  }

  // Breadcrumbs
  let breadcrumbs = $derived([
    { label: 'Information', href: '/information' },
    { label: 'Mobs', href: '/information/mobs' },
    ...(activeMob?.Name ? [{ label: activeMob.Name }] : isCreateMode ? [{ label: 'New Mob' }] : [])
  ]);

  // SEO
  let seoDescription = $derived(activeMob?.Properties?.Description ||
    `${activeMob?.Name || 'Mob'} - ${activeMob?.Type || ''} mob on ${activeMob?.Planet?.Name || 'Calypso'} in Entropia Universe.`);

  let canonicalUrl = $derived(activeMob?.Name
    ? `https://entropianexus.com/information/mobs/${encodeURIComponentSafe(activeMob.Name)}`
    : 'https://entropianexus.com/information/mobs');

  // Image URL for SEO (approved images only)
  let entityImageUrl = $derived(mob?.Id ? `/api/img/mob/${mob.Id}` : null);

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    maturities: true,
    locations: true,
    loots: true,
    codex: true,
    globals: false
  });
  let maturitiesSectionAnchor = $state();
  let lastMaturityScrollKey = $state(null);

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
  const DAMAGE_KEYS = ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];

  function getDamageGroups(mobData, attackName) {
    if (!mobData?.Maturities) return null;

    // Sort maturities same as MobMaturities.svelte: non-bosses first, by HP*Level
    const sorted = [...mobData.Maturities].sort((a, b) => {
      const aIsBoss = a.Properties?.Boss === true;
      const bIsBoss = b.Properties?.Boss === true;
      if (aIsBoss !== bIsBoss) return aIsBoss ? 1 : -1;
      const aHp = a.Properties?.Health;
      const aLvl = a.Properties?.Level;
      const bHp = b.Properties?.Health;
      const bLvl = b.Properties?.Level;
      const aHas = aHp != null && aLvl != null;
      const bHas = bHp != null && bLvl != null;
      if (aHas !== bHas) return aHas ? -1 : 1;
      if (!aHas && !bHas) return 0;
      return (aHp * aLvl) - (bHp * bLvl);
    });

    let hasAnyAttack = false;
    const entries = [];
    for (const mat of sorted) {
      const attack = mat.Attacks?.find(a => a.Name === attackName);
      if (!attack) continue;
      hasAnyAttack = true;
      const spread = {};
      for (const k of DAMAGE_KEYS) spread[k] = attack.Damage?.[k] || 0;
      const key = DAMAGE_KEYS.map(k => Math.round(spread[k])).join(',');
      entries.push({ name: mat.Name || 'Unknown', spread, key });
    }

    if (!hasAnyAttack) return null;
    if (entries.length === 0) return null;

    // Group consecutive maturities with matching damage composition
    const groups = [];
    for (const entry of entries) {
      const last = groups[groups.length - 1];
      if (last && last.key === entry.key) {
        last.maturities.push(entry.name);
      } else {
        groups.push({ damageSpread: entry.spread, maturities: [entry.name], key: entry.key });
      }
    }
    return groups.map(({ damageSpread, maturities }) => ({ damageSpread, maturities }));
  }

  function formatMaturityLabel(maturities, totalCount) {
    if (maturities.length === totalCount) return null;
    if (maturities.length <= 2) return maturities.join(', ');
    return `${maturities[0]} \u2013 ${maturities[maturities.length - 1]}`;
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
  let primaryDamageGroups = $derived(getDamageGroups(activeMob, 'Primary'));
  let secondaryDamageGroups = $derived(getDamageGroups(activeMob, 'Secondary'));
  let tertiaryDamageGroups = $derived(getDamageGroups(activeMob, 'Tertiary'));
  let totalMaturityCount = $derived(activeMob?.Maturities?.length || 0);
  let lowestHpPerLevel = $derived(getLowestHpPerLevel(activeMob));
  let healthRange = $derived(getHealthRange(activeMob));
  let levelRange = $derived(getLevelRange(activeMob));
  let mobType = $derived(getMobTypeLabel(activeMob));
  let isAsteroid = $derived(activeMob?.Type === 'Asteroid');
  let scanningProfession = $derived(getScanningProfession(activeMob));
  let lootingProfession = $derived(getLootingProfession(activeMob));
  let speciesCodexBaseCost = $derived(activeMob?.Species?._newSpecies?.CodexBaseCost ?? activeMob?.Species?.Properties?.CodexBaseCost);
  let speciesCodexType = $derived(activeMob?.Species?._newSpecies?.CodexType ?? activeMob?.Species?.Properties?.CodexType);
  let hasCodex = $derived(speciesCodexBaseCost != null);
  let selectedMaturityBelongsToActiveMob = $derived(selectedMaturityId != null
    && !!activeMob?.Maturities?.some(m => String(m.Id) === String(selectedMaturityId)));
  let selectedMaturityIdForActiveMob = $derived(selectedMaturityBelongsToActiveMob ? selectedMaturityId : null);

  // Ensure selected maturity is visible in the article and section stays open.
  let maturityScrollKey = $derived(selectedMaturityIdForActiveMob != null && activeMob?.Id != null && !$editMode
    ? `${activeMob.Id}-${selectedMaturityIdForActiveMob}`
    : null);
  run(() => {
    if (maturityScrollKey && maturityScrollKey !== lastMaturityScrollKey) {
      lastMaturityScrollKey = maturityScrollKey;
      panelStates = { ...panelStates, maturities: true };
      savePanelStates();
      tick().then(() => {
        maturitiesSectionAnchor?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  });

  // ========== EDIT HANDLERS ==========
  function handleDescriptionChange(event) {
    updateField('Properties.Description', event.detail);
  }

  function buildSpeciesProps(raw) {
    return {
      CodexBaseCost: raw?.CodexBaseCost ?? null,
      CodexType: raw?.CodexType ?? 'Mob'
    };
  }

  function upsertLocalSpecies(name, speciesProps) {
    const normalized = buildSpeciesProps(speciesProps);
    const species = { Name: name, Properties: normalized };
    const existingIndex = localSpeciesList.findIndex(s => s.Name === name);

    if (existingIndex >= 0) {
      localSpeciesList = localSpeciesList.map((s, index) => index === existingIndex ? species : s);
    } else {
      localSpeciesList = [...localSpeciesList, species];
    }
  }

  function buildSpeciesPayload(name, speciesProps, baseSpecies = null) {
    const normalized = buildSpeciesProps(speciesProps);
    return {
      ...(baseSpecies ? JSON.parse(JSON.stringify(baseSpecies)) : {}),
      Name: name,
      Properties: {
        ...(baseSpecies?.Properties || {}),
        ...normalized
      },
      _newSpecies: normalized
    };
  }

  function handleSpeciesNameInput(nextName) {
    const name = (nextName || '').trim();
    if (!name) {
      updateField('Species', null);
      return;
    }

    const selectedSpecies = localSpeciesList.find(s => s.Name === name);
    if (selectedSpecies) {
      const currentSpecies = activeMob?.Species;
      const payload = JSON.parse(JSON.stringify(selectedSpecies));
      if (currentSpecies?.Name === name && currentSpecies?._newSpecies) {
        payload._newSpecies = buildSpeciesProps(currentSpecies._newSpecies);
        payload.Properties = {
          ...(payload.Properties || {}),
          ...payload._newSpecies
        };
      }
      updateField('Species', payload);
      return;
    }

    updateField('Species', { Name: name });
  }

  function handleCreateSpecies(event) {
    const { Name, _newSpecies } = event.detail;
    upsertLocalSpecies(Name, _newSpecies);
    updateField('Species', buildSpeciesPayload(Name, _newSpecies));
    showCreateSpeciesDialog = false;
  }

  function handleEditSpecies(event) {
    const { Name, _newSpecies } = event.detail;
    upsertLocalSpecies(Name, _newSpecies);
    updateField('Species', buildSpeciesPayload(Name, _newSpecies, activeMob?.Species));
    showEditSpeciesDialog = false;
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
  {user}
  editable={true}
  {canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
  {editDepsLoading}
  bind:sidebarExpanded
  bind:sidebarFullWidth
>
  {#snippet sidebar()}
    <div  class="mobs-sidebar">
      <WikiNavigation
        items={activeSidebarItems}
        filters={activeSidebarFilters}
        basePath="/information/mobs"
        title="Mobs"
        currentSlug={isMaturityView ? null : activeMob?.Name}
        currentItemId={isMaturityView ? selectedMaturityId : null}
        {currentChangeId}
        customGetItemHref={isMaturityView ? getMaturitySidebarHref : null}
        userPendingCreates={sidebarPendingCreates}
        userPendingUpdates={sidebarPendingUpdates}
        tableColumns={activeSidebarTableColumns}
        fullWidthColumns={activeSidebarFullWidthColumns}
        allAvailableColumns={activeSidebarColumns}
        pageTypeId={activeSidebarPageTypeId}
        expanded={sidebarExpanded}
        fullWidth={sidebarFullWidth}
        on:toggleExpand={() => sidebarExpanded = !sidebarExpanded}
        on:toggleFullWidth={() => sidebarFullWidth = !sidebarFullWidth}
      >
        <!-- @migration-task: migrate this slot by hand, `after-header` is an invalid identifier -->
  <div slot="after-header" class="sidebar-toggle">
          <button class:active={!isMaturityView} onclick={() => switchSidebar('mobs')}>Mobs</button>
          <button class:active={isMaturityView} onclick={() => switchSidebar('maturities')}>Maturities</button>
        </div>
      </WikiNavigation>
    </div>
  {/snippet}

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
            <button class="banner-btn" onclick={() => setViewingPendingChange(false)}>
              View Current
            </button>
          {:else}
            <button class="banner-btn primary" onclick={() => setViewingPendingChange(true)}>
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
            <span class="stat-label">Avg HP/Lvl</span>
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
                  <div class="species-edit-row">
                    <SearchInput
                      value={activeMob?.Species?.Name || ''}
                      placeholder="Search species..."
                      options={speciesOptions}
                      on:change={(e) => handleSpeciesNameInput(e.detail.value)}
                      on:select={(e) => handleSpeciesNameInput(e.detail.value)}
                    />
                    {#if activeMob?.Species?.Name}
                      <button class="btn-create-inline" onclick={() => showEditSpeciesDialog = true} title="Edit species details">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                        </svg>
                        Edit
                      </button>
                    {/if}
                    <button class="btn-create-inline" onclick={() => showCreateSpeciesDialog = true} title="Create new species">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="12" y1="5" x2="12" y2="19" />
                        <line x1="5" y1="12" x2="19" y2="12" />
                      </svg>
                      New
                    </button>
                  </div>
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
                  on:change={handleMobApmChange}
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
            {#each [{ name: 'Primary', groups: primaryDamageGroups }, { name: 'Secondary', groups: secondaryDamageGroups }, { name: 'Tertiary', groups: tertiaryDamageGroups }] as attack}
              {#if attack.groups}
                {#each attack.groups as group}
                  {@const matLabel = formatMaturityLabel(group.maturities, totalMaturityCount)}
                  <MobDamageGrid
                    damageSpread={group.damageSpread}
                    label={attack.groups.length === 1 && !matLabel ? attack.name : `${attack.name}${matLabel ? ` (${matLabel})` : ''}`}
                  />
                {/each}
              {/if}
            {/each}
            {#if !primaryDamageGroups && !secondaryDamageGroups && !tertiaryDamageGroups}
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
              <span class="stat-value">{speciesCodexBaseCost} PED</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Type</span>
              <span class="stat-value">{speciesCodexType || 'Mob'}</span>
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
              showWaypoints={true}
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
        <div class="maturities-anchor" bind:this={maturitiesSectionAnchor}>
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
                mobName={activeMob?.Name || ''}
                fieldPath="Maturities"
              />
            {:else}
              <MobMaturities
                maturities={activeMob?.Maturities}
                type={activeMob?.Type}
                selectedMaturityId={selectedMaturityIdForActiveMob}
              />
            {/if}
          </DataSection>
        </div>

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
              baseCost={speciesCodexBaseCost}
              codexType={speciesCodexType}
              mobType={mobType}
              skills={skillsList}
            />
          </DataSection>
        {/if}

        <!-- Globals Section -->
        {#if !isCreateMode && activeMob?.Id}
          <DataSection
            title="Globals"
            icon=""
            bind:expanded={panelStates.globals}
            subtitle="Global loot events"
            on:toggle={savePanelStates}
          >
            <MobGlobals mobName={activeMob.Name} />
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

{#if showCreateSpeciesDialog}
  <CreateSpeciesDialog
    on:create={handleCreateSpecies}
    on:cancel={() => showCreateSpeciesDialog = false}
  />
{/if}

{#if showEditSpeciesDialog}
  <CreateSpeciesDialog
    species={activeMob?.Species}
    on:create={handleEditSpecies}
    on:cancel={() => showEditSpeciesDialog = false}
  />
{/if}

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

  .maturities-anchor {
    margin-bottom: 16px;
  }

  @media (max-width: 899px) {
    .maturities-anchor {
      margin-bottom: 12px;
    }
  }

  .mobs-sidebar {
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }

  .mobs-sidebar :global(.wiki-nav) {
    flex: 1;
    min-height: 0;
  }

  .sidebar-toggle {
    display: flex;
    gap: 8px;
    padding: 8px;
  }

  .sidebar-toggle button {
    flex: 1;
    border: 1px solid var(--border-color, #555);
    background: var(--secondary-color);
    color: var(--text-color);
    padding: 6px 8px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
  }

  .sidebar-toggle button.active {
    background: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .species-edit-row {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
  }

  .btn-create-inline {
    display: flex;
    align-items: center;
    gap: 3px;
    padding: 5px 8px;
    font-size: 11px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .btn-create-inline:hover {
    background-color: var(--hover-color);
    color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
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

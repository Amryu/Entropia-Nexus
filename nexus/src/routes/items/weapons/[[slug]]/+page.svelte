<!--
  @component Weapon Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: All numeric stats + damage breakdown
  Article: Description → Tiers → Acquisition
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy, untrack } from 'svelte';
  import { encodeURIComponentSafe, hasItemTag, clampDecimals, getTypeLink, getLatestPendingUpdate, loadEditDeps } from '$lib/util';


  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import MarketPriceSection from '$lib/components/wiki/MarketPriceSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  // Edit state management
  import {
    editMode,
    isCreateMode,
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

  // Weapon-specific components
  import DamageBreakdownGrid from '$lib/components/wiki/DamageBreakdownGrid.svelte';

  // Generic wiki components
  import TieringEditor from '$lib/components/wiki/TieringEditor.svelte';
  import EffectsEditor from '$lib/components/wiki/EffectsEditor.svelte';

  // Legacy components for comparison
  import Acquisition from '$lib/components/wiki/Acquisition.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  let { data = $bindable() } = $props();

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = $state(false);
  $effect(() => {
    if ($editMode && data.effects === null && !untrack(() => editDepsLoading)) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'effects', url: '/api/effects' },
        { key: 'vehicleAttachmentTypes', url: '/api/vehicleattachmenttypes' }
      ]).then(deps => {
        data = { ...data, ...deps };
        editDepsLoading = false;
      });
    }
  });

  let weapon = $derived(data.object);
  let user = $derived(data.session?.user);
  let allItems = $derived(data.allItems || []);
  let additional = $derived(data.additional || {});
  let pendingChange = $derived(data.pendingChange);
  let effects = $derived(data.effects || []);
  let vehicleAttachmentTypes = $derived(data.vehicleAttachmentTypes || []);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let canCreateNew = $derived(data.canCreateNew !== false);
  let pendingCreatesCount = $derived(data.pendingCreatesCount || 0);
  let existingChange = $derived(data.existingChange);

  // Empty weapon template for create mode
  const emptyWeapon = {
    Id: null,
    ItemId: null,
    Name: '',
    Properties: {
      Description: '',
      Weight: null,
      Type: null,
      Category: null,
      Class: 'Ranged',
      UsesPerMinute: null,
      Range: null,
      ImpactRadius: null,
      Mindforce: null,
      Economy: {
        Efficiency: null,
        MaxTT: null,
        MinTT: null,
        Decay: null,
        AmmoBurn: null,
      },
      Damage: {
        Stab: null,
        Cut: null,
        Impact: null,
        Penetration: null,
        Shrapnel: null,
        Burn: null,
        Cold: null,
        Acid: null,
        Electric: null,
      },
      Skill: {
        Hit: { LearningIntervalStart: null, LearningIntervalEnd: null },
        Dmg: { LearningIntervalStart: null, LearningIntervalEnd: null },
        IsSiB: false,
      },
    },
    Ammo: { Name: null },
    ProfessionHit: { Name: null },
    ProfessionDmg: { Name: null },
    AttachmentType: { Name: null },
    EffectsOnEquip: [],
    EffectsOnUse: [],
    Tiers: [],
  };

  let currentChangeId = $derived($page.url.searchParams.get('changeId'));
  let weaponEntityId = $derived(weapon?.Id ?? weapon?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, weaponEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));
  let createSeed = $derived(existingChange?.data || resolvedPendingChange?.data || emptyWeapon);

  // ========== EDIT STATE MANAGEMENT ==========
  // Initialize edit state when weapon changes or in create mode
  let lastInitKey = null;
  $effect(() => {
    if (user) {
      const createSeedSource = existingChange?.data ? 'existing' : (resolvedPendingChange?.data ? 'pending' : 'empty');
      const initKey = data.isCreateMode
        ? `create:${currentChangeId || 'new'}:${createSeedSource}`
        : (weapon?.Id ?? weapon?.ItemId)
          ? `view:${weapon?.Id ?? weapon?.ItemId}:${resolvedPendingChange?.id || 'none'}`
          : null;

      if (initKey && initKey !== untrack(() => lastInitKey)) {
        if (data.isCreateMode) {
          // If editing an existing pending create, use that data; otherwise use empty template
          initEditState(createSeed, 'Weapon', true, existingChange || resolvedPendingChange || null);
        } else if (weapon) {
          initEditState(weapon, 'Weapon', false, canUsePendingChange ? resolvedPendingChange : null);
        }
        lastInitKey = initKey;
      }
    }
  });

  // Initialize pending change state
  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });

  // Determine which entity to display:
  // 1. In edit mode: show currentEntity (original + pending edits)
  // 2. Viewing pending change: show pending change data
  // 3. Otherwise: show original weapon
  let activeWeapon = $derived($editMode
    ? ($currentEntity || createSeed)
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : (weapon || (data.isCreateMode ? createSeed : null)));

  // Track previous entity for navigation detection
  let previousEntityId = null;

  // Exit edit mode when navigating to a different entity (unless it's a draft/pending change)
  $effect(() => {
    const currentId = weapon?.Id;
    const prevId = untrack(() => previousEntityId);
    if (currentId !== prevId && prevId !== null) {
      // Only exit edit mode if not viewing a draft/pending change
      const hasUnsavedDraft = $editMode && !$existingPendingChange;
      if ($editMode && !hasUnsavedDraft) {
        resetEditState();
      }
      previousEntityId = currentId;
    } else if (prevId === null && currentId) {
      previousEntityId = currentId;
    }
  });

  // Cleanup on component destroy
  onDestroy(() => {
    resetEditState();
  });

  // Build navigation items from grouped weapons
  let navItems = $derived(allItems);

  // Navigation filters
  const navFilters = [
    {
      key: 'Properties.Class',
      label: 'Class',
      values: [
        { value: 'Ranged', label: 'Ranged' },
        { value: 'Melee', label: 'Melee' },
        { value: 'Mindforce', label: 'Mindforce' },
        { value: 'Attached', label: 'Attached' },
      ]
    }
  ];

  // All column definitions keyed for lookup
  const columnDefs = {
    class: {
      key: 'class',
      header: 'Class',
      width: '70px',
      filterPlaceholder: 'Ranged',
      getValue: (item) => item.Properties?.Class,
      format: (v) => v || '-'
    },
    type: {
      key: 'type',
      header: 'Type',
      width: '70px',
      filterPlaceholder: 'Laser',
      getValue: (item) => item.Properties?.Type,
      format: (v) => v || '-'
    },
    dps: {
      key: 'dps',
      header: 'DPS',
      width: '55px',
      filterPlaceholder: '>10',
      getValue: (item) => getDps(item),
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    dpp: {
      key: 'dpp',
      header: 'DPP',
      width: '55px',
      filterPlaceholder: '>2',
      getValue: (item) => getDpp(item),
      format: (v) => v != null ? v.toFixed(2) : '-'
    },
    effectiveDmg: {
      key: 'effectiveDmg',
      header: 'Eff Dmg',
      width: '60px',
      filterPlaceholder: '>10',
      getValue: (item) => getEffectiveDamage(item),
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    eff: {
      key: 'eff',
      header: 'Effic.',
      width: '55px',
      filterPlaceholder: '>50',
      getValue: (item) => getEfficiency(item),
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    damage: {
      key: 'damage',
      header: 'Damage',
      width: '60px',
      filterPlaceholder: '>20',
      getValue: (item) => getTotalDamage(item),
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    range: {
      key: 'range',
      header: 'Range',
      width: '55px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Range,
      format: (v) => v != null ? v : '-'
    },
    upm: {
      key: 'upm',
      header: 'Uses',
      width: '50px',
      filterPlaceholder: '>30',
      getValue: (item) => item.Properties?.UsesPerMinute,
      format: (v) => v != null ? v : '-'
    },
    maxtt: {
      key: 'maxtt',
      header: 'Max TT',
      width: '60px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Economy?.MaxTT,
      format: (v) => v != null ? v.toFixed(2) : '-'
    },
    decay: {
      key: 'decay',
      header: 'Decay',
      width: '55px',
      filterPlaceholder: '>0.5',
      getValue: (item) => item.Properties?.Economy?.Decay,
      format: (v) => v != null ? v.toFixed(2) : '-'
    },
    ammo: {
      key: 'ammo',
      header: 'Ammo',
      width: '55px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Properties?.Economy?.AmmoBurn,
      format: (v) => v != null ? v : '-'
    },
    uses: {
      key: 'uses',
      header: 'Uses',
      width: '55px',
      filterPlaceholder: '>100',
      getValue: (item) => getTotalUses(item),
      format: (v) => v != null ? v : '-'
    },
    sib: {
      key: 'sib',
      header: 'SiB',
      width: '40px',
      getValue: (item) => item.Properties?.Skill?.IsSiB,
      format: (v) => v === true ? 'Yes' : v === false ? 'No' : '-'
    },
    minLevel: {
      key: 'minLevel',
      header: 'Min Lvl',
      width: '60px',
      filterPlaceholder: '>1',
      getValue: (item) => {
        const skill = item?.Properties?.Skill;
        const hitMin = skill?.Hit?.LearningIntervalStart ?? null;
        const dmgMin = skill?.Dmg?.LearningIntervalStart ?? null;
        if (hitMin != null && dmgMin != null) return Math.max(hitMin, dmgMin);
        return hitMin ?? dmgMin ?? null;
      },
      format: (v, item) => {
        const skill = item?.Properties?.Skill;
        const hitMin = skill?.Hit?.LearningIntervalStart ?? null;
        const dmgMin = skill?.Dmg?.LearningIntervalStart ?? null;
        if (hitMin != null && dmgMin != null) {
          return hitMin === dmgMin ? String(hitMin) : `${hitMin}/${dmgMin}`;
        }
        if (hitMin != null) return String(hitMin);
        if (dmgMin != null) return String(dmgMin);
        return '-';
      }
    },
    maxLevel: {
      key: 'maxLevel',
      header: 'Max Lvl',
      width: '60px',
      filterPlaceholder: '>10',
      getValue: (item) => {
        const skill = item?.Properties?.Skill;
        const hitMax = skill?.Hit?.LearningIntervalEnd ?? null;
        const dmgMax = skill?.Dmg?.LearningIntervalEnd ?? null;
        if (hitMax != null && dmgMax != null) return Math.max(hitMax, dmgMax);
        return hitMax ?? dmgMax ?? null;
      },
      format: (v, item) => {
        const skill = item?.Properties?.Skill;
        const hitMax = skill?.Hit?.LearningIntervalEnd ?? null;
        const dmgMax = skill?.Dmg?.LearningIntervalEnd ?? null;
        if (hitMax != null && dmgMax != null) {
          return hitMax === dmgMax ? String(hitMax) : `${hitMax}/${dmgMax}`;
        }
        if (hitMax != null) return String(hitMax);
        if (dmgMax != null) return String(dmgMax);
        return '-';
      }
    },
    costPerUse: {
      key: 'costPerUse',
      header: 'Cost/Use',
      width: '65px',
      filterPlaceholder: '>0.5',
      getValue: (item) => getCostPerUse(item),
      format: (v) => v != null ? v.toFixed(4) : '-'
    },
    reload: {
      key: 'reload',
      header: 'Reload',
      width: '55px',
      filterPlaceholder: '>1',
      getValue: (item) => getReload(item),
      format: (v) => v != null ? v.toFixed(2) : '-'
    },
    weight: {
      key: 'weight',
      header: 'Weight',
      width: '55px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Properties?.Weight,
      format: (v) => v != null ? v : '-'
    },
    mintt: {
      key: 'mintt',
      header: 'Min TT',
      width: '55px',
      filterPlaceholder: '>0',
      getValue: (item) => item.Properties?.Economy?.MinTT,
      format: (v) => v != null ? v.toFixed(2) : '-'
    },
    category: {
      key: 'category',
      header: 'Category',
      width: '75px',
      filterPlaceholder: 'Rifle',
      getValue: (item) => item.Properties?.Category,
      format: (v) => v || '-'
    },
    impactRadius: {
      key: 'impactRadius',
      header: 'Radius',
      width: '55px',
      filterPlaceholder: '>0',
      getValue: (item) => item.Properties?.ImpactRadius,
      format: (v) => v != null ? v : '-'
    },
    mfLevel: {
      key: 'mfLevel',
      header: 'MF Lvl',
      width: '55px',
      filterPlaceholder: '>10',
      getValue: (item) => item.Properties?.Mindforce?.Level ?? item.Properties?.Level,
      format: (v) => v != null ? v : '-'
    },
    concentration: {
      key: 'concentration',
      header: 'Conc.',
      width: '55px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Properties?.Mindforce?.Concentration,
      format: (v) => v != null ? `${v}s` : '-'
    },
    cooldown: {
      key: 'cooldown',
      header: 'CD',
      width: '50px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Properties?.Mindforce?.Cooldown,
      format: (v) => v != null ? `${v}s` : '-'
    },
    cooldownGroup: {
      key: 'cooldownGroup',
      header: 'CD Grp',
      width: '55px',
      filterPlaceholder: '>0',
      getValue: (item) => item.Properties?.Mindforce?.CooldownGroup,
      format: (v) => v != null ? v : '-'
    }
  };

  const navTableColumns = [
    columnDefs.class,
    columnDefs.type,
    columnDefs.dps,
    columnDefs.dpp,
    columnDefs.eff
  ];

  // Full-width table columns (superset of navTableColumns with additional stats)
  const navFullWidthColumns = [
    columnDefs.class,
    columnDefs.type,
    columnDefs.dps,
    columnDefs.dpp,
    columnDefs.eff,
    columnDefs.costPerUse,
    columnDefs.maxtt,
    columnDefs.effectiveDmg,
    columnDefs.range,
    columnDefs.upm,
    columnDefs.sib,
    columnDefs.minLevel,
    columnDefs.maxLevel,
    columnDefs.cooldown,
    columnDefs.cooldownGroup
  ];

  // All available columns for user configuration
  const allAvailableColumns = Object.values(columnDefs);

  // Breadcrumbs
  let breadcrumbs = $derived([
    { label: 'Items', href: '/items' },
    { label: 'Weapons', href: '/items/weapons' },
    ...(data.isCreateMode ? [{ label: 'New Weapon' }] : (weapon ? [{ label: weapon.Name }] : []))
  ]);

  // SEO
  let seoDescription = $derived(weapon?.Properties?.Description ||
    `${weapon?.Name || 'Weapon'} - ${weapon?.Properties?.Class || ''} ${weapon?.Properties?.Type || ''} weapon in Entropia Universe.`);

  let canonicalUrl = $derived(weapon
    ? `https://entropianexus.com/items/weapons/${encodeURIComponentSafe(weapon.Name)}`
    : 'https://entropianexus.com/items/weapons');

  // ========== EDITING PERMISSIONS ==========
  // Verified users and users with wiki.edit grant can edit
  let canEdit = $derived(user?.verified || user?.grants?.includes('wiki.edit'));

  // Check if weapon is tierable
  let isTierable = $derived(activeWeapon && !hasItemTag(activeWeapon.Name, 'L'));
  let hasEffects = $derived((activeWeapon?.EffectsOnEquip?.length > 0) || (activeWeapon?.EffectsOnUse?.length > 0));

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    tiers: true,
    marketPrices: true,
    acquisition: true
  });

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-weapon-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-weapon-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // Image URL for SEO (approved images only)
  let entityImageUrl = $derived(weapon?.Id ? `/api/img/weapon/${weapon.Id}` : null);

  // ========== RELOAD/USES TOGGLE ==========
  let showReload = $state(true);
  let showReloadEffective = $derived($editMode ? false : showReload);

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-weapon-show-reload');
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
      localStorage.setItem('wiki-weapon-show-reload', String(showReload));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== CALCULATOR FUNCTIONS ==========
  function getTotalDamage(item) {
    if (!item?.Properties?.Damage) return null;
    const d = item.Properties.Damage;
    return (d.Impact || 0) + (d.Cut || 0) + (d.Stab || 0) + (d.Penetration || 0) +
           (d.Shrapnel || 0) + (d.Burn || 0) + (d.Cold || 0) + (d.Acid || 0) + (d.Electric || 0);
  }

  function getEffectiveDamage(item) {
    const totalDamage = getTotalDamage(item);
    if (totalDamage === null || totalDamage === 0) return null;
    const multiplier = 0.88 * 0.75 + 0.02 * 1.75;
    return totalDamage * multiplier;
  }

  function getReload(item) {
    if (!item?.Properties?.UsesPerMinute) return null;
    return 60 / item.Properties.UsesPerMinute;
  }

  function getCostPerUse(item) {
    const decay = item?.Properties?.Economy?.Decay;
    const ammoBurn = item?.Properties?.Economy?.AmmoBurn ?? 0;
    if (decay === null || decay === undefined) return null;
    return decay + (ammoBurn / 100);
  }

  function getDps(item) {
    const reload = getReload(item);
    const effectiveDamage = getEffectiveDamage(item);
    if (effectiveDamage === null || reload === null) return null;
    return effectiveDamage / reload;
  }

  function getDpp(item) {
    const cost = getCostPerUse(item);
    const effectiveDamage = getEffectiveDamage(item);
    if (cost === null || cost === 0 || effectiveDamage === null) return null;
    return effectiveDamage / cost;
  }

  function getEfficiency(item) {
    return item?.Properties?.Economy?.Efficiency || null;
  }

  function getTotalUses(item) {
    const maxTT = item?.Properties?.Economy?.MaxTT;
    const minTT = item?.Properties?.Economy?.MinTT ?? 0;
    const decay = item?.Properties?.Economy?.Decay;
    if (maxTT === null || maxTT === undefined || decay === null || decay === undefined || decay === 0) return null;
    return Math.floor((maxTT - minTT) / (decay / 100));
  }

  // Skill-related getters
  function getSkillInfo(item) {
    return item?.Properties?.Skill || null;
  }

  function getProfessionNames(item) {
    // Profession names are at top level, not in Properties.Skill
    return {
      hit: item?.ProfessionHit?.Name || null,
      dmg: item?.ProfessionDmg?.Name || null
    };
  }

  function getSkillIntervals(item) {
    const skill = getSkillInfo(item);
    if (!skill) return null;
    return {
      hit: {
        min: skill.Hit?.LearningIntervalStart ?? null,
        max: skill.Hit?.LearningIntervalEnd ?? null
      },
      dmg: {
        min: skill.Dmg?.LearningIntervalStart ?? null,
        max: skill.Dmg?.LearningIntervalEnd ?? null
      }
    };
  }

  // Reactive calculations - use activeWeapon to update in real-time during editing
  let dps = $derived(getDps(activeWeapon));
  let dpp = $derived(getDpp(activeWeapon));
  let efficiency = $derived(getEfficiency(activeWeapon));
  let costPerUse = $derived(getCostPerUse(activeWeapon));
  let reload = $derived(getReload(activeWeapon));
  let totalUses = $derived(getTotalUses(activeWeapon));
  let totalDamage = $derived(getTotalDamage(activeWeapon));
  let effectiveDamage = $derived(getEffectiveDamage(activeWeapon));
  let skillInfo = $derived(getSkillInfo(activeWeapon));
  let professionNames = $derived(getProfessionNames(activeWeapon));
  let skillIntervals = $derived(getSkillIntervals(activeWeapon));

  // ========== CONDITIONAL FIELD OPTIONS ==========
  // Category options based on Class
  let categoryOptions = $derived((() => {
    const cls = activeWeapon?.Properties?.Class;
    if (cls === 'Ranged') return ['Rifle', 'Carbine', 'Pistol', 'Cannon', 'Flamethrower', 'Support', 'Mounted'];
    if (cls === 'Melee') return ['Axe', 'Sword', 'Knife', 'Whip', 'Club', 'Power Fist'];
    if (cls === 'Mindforce') return ['Chip'];
    if (cls === 'Attached') return ['Hanging', 'Turret'];
    if (cls === 'Stationary') return ['Turret'];
    return [];
  })());

  // Type options based on Class
  let typeOptions = $derived((() => {
    const cls = activeWeapon?.Properties?.Class;
    if (cls === 'Ranged' || cls === 'Attached' || cls === 'Stationary') {
      return ['Laser', 'BLP', 'Explosive', 'Gauss', 'Plasma', 'Mining Laser (Low)', 'Mining Laser (Medium)', 'Mining Laser (High)'];
    }
    if (cls === 'Melee') return ['Blades', 'Clubs', 'Fists', 'Whips'];
    if (cls === 'Mindforce') return ['Pyrokinetic', 'Cryogenic', 'Electrokinesis'];
    return [];
  })());

  // Ammo Type options based on Class
  let ammoOptions = $derived((() => {
    const cls = activeWeapon?.Properties?.Class;
    if (cls === 'Ranged' || cls === 'Attached' || cls === 'Stationary') {
      return ['Weapon Cells', 'BLP Pack', 'Explosive Projectiles'];
    }
    if (cls === 'Melee') return [null, 'Weapon Cells'];
    if (cls === 'Mindforce') return ['Synthetic Mind Essence', 'Mind Essence', 'Light Mind Essence'];
    return [];
  })());

  // Hit Profession options based on Type
  let hitProfessionOptions = $derived((() => {
    const type = activeWeapon?.Properties?.Type;
    if (type === 'Laser') return ['Laser Pistoleer (Hit)', 'Laser Sniper (Hit)', 'Mounted Laser (Hit)'];
    if (type === 'BLP') return ['BLP Pistoleer (Hit)', 'BLP Sniper (Hit)', 'Mounted BLP (Hit)'];
    if (type === 'Plasma') return ['Plasma Pistoleer (Hit)', 'Plasma Sniper (Hit)'];
    if (type === 'Gauss') return ['Gauss Sniper (Hit)'];
    if (type === 'Explosive') return ['Grenadier (Hit)', 'Mounted Grenadier (Hit)'];
    if (type?.startsWith('Mining Laser')) return ['Mining Laser (Hit)'];
    if (type === 'Pyrokinetic') return ['Pyro Kinetic (Hit)'];
    if (type === 'Cryogenic') return ['Cryogenic (Hit)'];
    if (type === 'Electrokinesis') return ['Electro Kinetic (Hit)'];
    if (type === 'Blades') return ['Swordsman (Hit)', 'Knifefighter (Hit)', 'Whipper (Hit)'];
    if (type === 'Clubs') return ['One Handed Clubber (Hit)', 'Two Handed Clubber (Hit)'];
    if (type === 'Fists') return ['Brawler (Hit)'];
    if (type === 'Whips') return ['Whipper (Hit)'];
    return [];
  })());

  // Dmg Profession options based on Type
  let dmgProfessionOptions = $derived((() => {
    const type = activeWeapon?.Properties?.Type;
    if (type === 'Laser') return ['Ranged Laser (Dmg)'];
    if (type === 'BLP') return ['Ranged BLP (Dmg)'];
    if (type === 'Plasma') return ['Ranged Plasma (Dmg)'];
    if (type === 'Gauss') return ['Ranged Gauss (Dmg)'];
    if (type === 'Explosive') return ['Grenadier (Dmg)'];
    if (type?.startsWith('Mining Laser')) return ['Mining Laser (Dmg)'];
    if (type === 'Pyrokinetic') return ['Pyro Kinetic (Dmg)'];
    if (type === 'Cryogenic') return ['Cryogenic (Dmg)'];
    if (type === 'Electrokinesis') return ['Electro Kinetic (Dmg)'];
    if (type === 'Blades') return ['Swordsman (Dmg)', 'Knifefighter (Dmg)', 'Whipper (Dmg)'];
    if (type === 'Clubs') return ['One Handed Clubber (Dmg)', 'Two Handed Clubber (Dmg)'];
    if (type === 'Fists') return ['Brawler (Dmg)'];
    if (type === 'Whips') return ['Whipper (Dmg)'];
    return [];
  })());

  // ========== SMART INFERENCE ==========
  // Auto-select values when there's only one valid option.
  // This speeds up editing by inferring obvious choices.

  // Track previous values to detect changes
  let prevClass = null;
  let prevType = null;

  // When Class changes, auto-select Category if only one option exists
  $effect(() => {
    if ($editMode && activeWeapon?.Properties?.Class && activeWeapon.Properties.Class !== untrack(() => prevClass)) {
      prevClass = activeWeapon.Properties.Class;
      // If only one category option for this class, auto-select it
      if (categoryOptions.length === 1 && activeWeapon.Properties.Category !== categoryOptions[0]) {
        updateField('Properties.Category', categoryOptions[0]);
      }
      // If current category is not valid for new class, clear it
      if (categoryOptions.length > 0 && activeWeapon.Properties.Category && !categoryOptions.includes(activeWeapon.Properties.Category)) {
        updateField('Properties.Category', categoryOptions.length === 1 ? categoryOptions[0] : null);
      }
      // If only one type option for this class, auto-select it
      if (typeOptions.length === 1 && activeWeapon.Properties.Type !== typeOptions[0]) {
        updateField('Properties.Type', typeOptions[0]);
      }
      // If current type is not valid for new class, clear it
      if (typeOptions.length > 0 && activeWeapon.Properties.Type && !typeOptions.includes(activeWeapon.Properties.Type)) {
        updateField('Properties.Type', typeOptions.length === 1 ? typeOptions[0] : null);
      }
    }
  });

  // When Type changes, auto-select professions if only one option exists
  $effect(() => {
    if ($editMode && activeWeapon?.Properties?.Type && activeWeapon.Properties.Type !== untrack(() => prevType)) {
      prevType = activeWeapon.Properties.Type;
      // Auto-select Hit Profession if only one option
      if (hitProfessionOptions.length === 1 && professionNames.hit !== hitProfessionOptions[0]) {
        updateField('ProfessionHit.Name', hitProfessionOptions[0]);
      }
      // If current hit profession is not valid for new type, clear or auto-select
      if (hitProfessionOptions.length > 0 && professionNames.hit && !hitProfessionOptions.includes(professionNames.hit)) {
        updateField('ProfessionHit.Name', hitProfessionOptions.length === 1 ? hitProfessionOptions[0] : null);
      }
      // Auto-select Dmg Profession if only one option
      if (dmgProfessionOptions.length === 1 && professionNames.dmg !== dmgProfessionOptions[0]) {
        updateField('ProfessionDmg.Name', dmgProfessionOptions[0]);
      }
      // If current dmg profession is not valid for new type, clear or auto-select
      if (dmgProfessionOptions.length > 0 && professionNames.dmg && !dmgProfessionOptions.includes(professionNames.dmg)) {
        updateField('ProfessionDmg.Name', dmgProfessionOptions.length === 1 ? dmgProfessionOptions[0] : null);
      }
    }
  });
</script>

<WikiSEO
  title={weapon?.Name || 'Weapons'}
  description={seoDescription}
  entityType="weapon"
  entity={activeWeapon}
  sidebarColumns={navTableColumns}
  sidebarEntity={weapon}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

  <WikiPage
    title="Weapons"
    {breadcrumbs}
    entity={data.isCreateMode ? ($currentEntity || createSeed) : (activeWeapon || weapon)}
    basePath="/items/weapons"
    {navItems}
    {navFilters}
    {navTableColumns}
    {navFullWidthColumns}
    navAllAvailableColumns={allAvailableColumns}
    navPageTypeId="weapons"
    {user}
    editable={true}
    canEdit={canEdit}
    {canCreateNew}
    {userPendingCreates}
    {userPendingUpdates}
    {editDepsLoading}
>
  {#if activeWeapon}
    <!-- Pending Change Banner -->
    {#if $existingPendingChange && !$editMode}
      <PendingChangeBanner
        pendingChange={$existingPendingChange}
        viewing={$viewingPendingChange}
        onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
        entityLabel="weapon"
      />
    {/if}

    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeWeapon?.Id}
            entityName={activeWeapon?.Name}
            entityType="weapon"
            {user}
            isEditMode={$editMode}
            isCreateMode={$isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              value={activeWeapon.Name}
              path="Name"
              type="text"
              required
            />
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge">{activeWeapon.Properties?.Class || 'Unknown'}</span>
            {#if activeWeapon?.Properties?.IsRare}<span class="item-flag-badge rare">Rare</span>{/if}
            {#if activeWeapon?.Properties?.IsUntradeable}<span class="item-flag-badge untradeable">Untradeable</span>{/if}
          </div>
        </div>

        <!-- Tier 1 Stats (toned down) -->
        <div class="stats-section tier-1 tier-blue">
          <div class="stat-row primary">
            <span class="stat-label">Efficiency</span>
            <span class="stat-value">{efficiency ? `${efficiency.toFixed(1)}%` : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">DPS</span>
            <span class="stat-value">{dps ? dps.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">DPP</span>
            <span class="stat-value">{dpp ? dpp.toFixed(2) : 'N/A'}</span>
          </div>
        </div>

        <!-- Tier 2 Stats -->
        <div class="stats-section tier-2">
          <h4 class="section-title">Performance</h4>
          <div class="stat-row">
            <span class="stat-label">Damage</span>
            <span class="stat-value">{totalDamage ? `${(totalDamage / 2).toFixed(1)} - ${totalDamage.toFixed(1)}` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Effective Dmg</span>
            <span class="stat-value">{effectiveDamage ? effectiveDamage.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Range</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Range}
                path="Properties.Range"
                type="number"
                suffix="m"
                min={0}
                step={0.1}
              />
            </span>
          </div>
          {#if $editMode}
            <!-- In edit mode, always show Uses/min as editable -->
            <div class="stat-row">
              <span class="stat-label">Uses/min</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.UsesPerMinute}
                  path="Properties.UsesPerMinute"
                  type="number"
                  min={0}
                  step={0.01}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Reload</span>
              <span class="stat-value">{reload ? `${reload.toFixed(2)}s` : 'N/A'}</span>
            </div>
          {:else}
            <!-- In view mode, toggle between Reload and Uses/min -->
            <div class="stat-row toggleable" onclick={toggleReloadUses} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), e.currentTarget.click())} title="Click to toggle between Reload and Uses/min" role="button" tabindex="0">
              {#if showReloadEffective}
                <span class="stat-label">Reload <span class="toggle-hint">⇄</span></span>
                <span class="stat-value">{reload ? `${reload.toFixed(2)}s` : 'N/A'}</span>
              {:else}
                <span class="stat-label">Uses/min <span class="toggle-hint">⇄</span></span>
                <span class="stat-value">{activeWeapon.Properties?.UsesPerMinute ?? 'N/A'}</span>
              {/if}
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Cost/Use</span>
            <span class="stat-value">{costPerUse ? `${costPerUse.toFixed(4)} PEC` : 'N/A'}</span>
          </div>
        </div>

        <!-- Economy Stats -->
        <div class="stats-section tier-3">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Efficiency</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Economy?.Efficiency}
                path="Properties.Economy.Efficiency"
                type="number"
                suffix="%"
                min={0}
                max={100}
                step={0.1}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max TT</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Economy?.MaxTT}
                path="Properties.Economy.MaxTT"
                type="number"
                suffix=" PED"
                min={0}
                step={0.00001}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min TT</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Economy?.MinTT}
                path="Properties.Economy.MinTT"
                type="number"
                suffix=" PED"
                min={0}
                step={0.00001}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Decay</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Economy?.Decay}
                path="Properties.Economy.Decay"
                type="number"
                suffix=" PEC"
                min={0}
                step={0.00001}
              />
            </span>
          </div>
          {#if activeWeapon.Ammo?.Name || $editMode}
            <div class="stat-row">
              <span class="stat-label">Ammo Type</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Ammo?.Name}
                  path="Ammo.Name"
                  type="select"
                  placeholder="None"
                  options={ammoOptions.filter(v => v !== null).map(v => ({ value: v, label: v }))}
                />
              </span>
            </div>
            {#if activeWeapon.Ammo?.Name}
              <div class="stat-row">
                <span class="stat-label">Ammo Burn</span>
                <span class="stat-value">
                  <InlineEdit
                    value={activeWeapon.Properties?.Economy?.AmmoBurn}
                    path="Properties.Economy.AmmoBurn"
                    type="number"
                    min={0}
                    step={1}
                  />
                </span>
              </div>
            {/if}
          {/if}
          <div class="stat-row">
            <span class="stat-label">Total Uses</span>
            <span class="stat-value">{totalUses ?? 'N/A'}</span>
          </div>
        </div>

        <!-- Properties -->
        <div class="stats-section">
          <h4 class="section-title">Properties</h4>
          <div class="stat-row">
            <span class="stat-label">Class</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Class}
                path="Properties.Class"
                type="select"
                options={[
                  { value: 'Ranged', label: 'Ranged' },
                  { value: 'Melee', label: 'Melee' },
                  { value: 'Mindforce', label: 'Mindforce' },
                  { value: 'Attached', label: 'Attached' },
                  { value: 'Stationary', label: 'Stationary' }
                ]}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Category</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Category}
                path="Properties.Category"
                type="select"
                options={categoryOptions.map(v => ({ value: v, label: v }))}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Type}
                path="Properties.Type"
                type="select"
                options={typeOptions.map(v => ({ value: v, label: v }))}
              />
            </span>
          </div>
          {#if activeWeapon.Properties?.Class === 'Attached'}
            <div class="stat-row">
              <span class="stat-label">Attachment Type</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.AttachmentType?.Name}
                  path="AttachmentType.Name"
                  type="select"
                  placeholder="None"
                  options={vehicleAttachmentTypes.map(v => ({ value: v.Name, label: v.Name }))}
                />
              </span>
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Weight}
                path="Properties.Weight"
                type="number"
                suffix="kg"
                min={0}
                step={0.1}
              />
            </span>
          </div>
          {#if activeWeapon.Properties?.Type === 'Explosive'}
            <div class="stat-row">
              <span class="stat-label">Impact Radius</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.ImpactRadius}
                  path="Properties.ImpactRadius"
                  type="number"
                  suffix="m"
                  min={0}
                  step={0.1}
                />
              </span>
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Rare</span>
            <span class="stat-value" class:highlight-yes={activeWeapon?.Properties?.IsRare}>
              <InlineEdit value={activeWeapon?.Properties?.IsRare} path="Properties.IsRare" type="checkbox" />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Untradeable</span>
            <span class="stat-value" class:highlight-yes={activeWeapon?.Properties?.IsUntradeable}>
              <InlineEdit value={activeWeapon?.Properties?.IsUntradeable} path="Properties.IsUntradeable" type="checkbox" />
            </span>
          </div>
        </div>

        <!-- Skilling Info -->
        <div class="stats-section">
          <h4 class="section-title">Skilling</h4>
          <div class="stat-row">
            <span class="stat-label">SiB</span>
            <span class="stat-value" class:highlight-yes={skillInfo?.IsSiB}>
              <InlineEdit
                value={skillInfo?.IsSiB}
                path="Properties.Skill.IsSiB"
                type="checkbox"
              />
            </span>
          </div>
          {#if professionNames.hit || $editMode}
            <div class="stat-row">
              <span class="stat-label">Hit Profession</span>
              <span class="stat-value wide-select">
                {#if $editMode}
                  <InlineEdit
                    value={professionNames.hit}
                    path="ProfessionHit.Name"
                    type="select"
                    placeholder="None"
                    options={hitProfessionOptions.map(v => ({ value: v, label: v }))}
                  />
                {:else}
                  <a href={getTypeLink(professionNames.hit, 'Profession')} class="profession-link">{professionNames.hit}</a>
                {/if}
              </span>
            </div>
            {#if skillInfo?.IsSiB && (skillIntervals?.hit?.min !== null || skillIntervals?.hit?.max !== null || $editMode)}
              <div class="stat-row indent">
                <span class="stat-label">Level Range</span>
                <span class="stat-value">
                  {#if $editMode}
                    <span class="interval-edit">
                      <InlineEdit
                        value={skillIntervals?.hit?.min}
                        path="Properties.Skill.Hit.LearningIntervalStart"
                        type="number"
                        min={0}
                        step={0.1}
                        placeholder="Min"
                      />
                      <span class="interval-sep">-</span>
                      <InlineEdit
                        value={skillIntervals?.hit?.max}
                        path="Properties.Skill.Hit.LearningIntervalEnd"
                        type="number"
                        min={0}
                        step={0.1}
                        placeholder="Max"
                      />
                    </span>
                  {:else}
                    {skillIntervals?.hit?.min ?? '?'} - {skillIntervals?.hit?.max ?? '?'}
                  {/if}
                </span>
              </div>
            {/if}
          {/if}
          {#if professionNames.dmg || $editMode}
            <div class="stat-row">
              <span class="stat-label">Dmg Profession</span>
              <span class="stat-value wide-select">
                {#if $editMode}
                  <InlineEdit
                    value={professionNames.dmg}
                    path="ProfessionDmg.Name"
                    type="select"
                    placeholder="None"
                    options={dmgProfessionOptions.map(v => ({ value: v, label: v }))}
                  />
                {:else}
                  <a href={getTypeLink(professionNames.dmg, 'Profession')} class="profession-link">{professionNames.dmg}</a>
                {/if}
              </span>
            </div>
            {#if skillInfo?.IsSiB && (skillIntervals?.dmg?.min !== null || skillIntervals?.dmg?.max !== null || $editMode)}
              <div class="stat-row indent">
                <span class="stat-label">Level Range</span>
                <span class="stat-value">
                  {#if $editMode}
                    <span class="interval-edit">
                      <InlineEdit
                        value={skillIntervals?.dmg?.min}
                        path="Properties.Skill.Dmg.LearningIntervalStart"
                        type="number"
                        min={0}
                        step={0.1}
                        placeholder="Min"
                      />
                      <span class="interval-sep">-</span>
                      <InlineEdit
                        value={skillIntervals?.dmg?.max}
                        path="Properties.Skill.Dmg.LearningIntervalEnd"
                        type="number"
                        min={0}
                        step={0.1}
                        placeholder="Max"
                      />
                    </span>
                  {:else}
                    {skillIntervals?.dmg?.min ?? '?'} - {skillIntervals?.dmg?.max ?? '?'}
                  {/if}
                </span>
              </div>
            {/if}
          {/if}
        </div>

        <!-- Mindforce Properties (only for Mindforce weapons) -->
        {#if activeWeapon.Properties?.Class === 'Mindforce'}
          <div class="stats-section">
            <h4 class="section-title">Mindforce</h4>
            <div class="stat-row">
              <span class="stat-label">Level</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.Mindforce?.Level}
                  path="Properties.Mindforce.Level"
                  type="number"
                  min={1}
                  step={1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Concentration</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.Mindforce?.Concentration}
                  path="Properties.Mindforce.Concentration"
                  type="number"
                  suffix="s"
                  min={0}
                  step={0.1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cooldown</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.Mindforce?.Cooldown}
                  path="Properties.Mindforce.Cooldown"
                  type="number"
                  suffix="s"
                  min={0}
                  step={0.1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cooldown Group</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.Mindforce?.CooldownGroup}
                  path="Properties.Mindforce.CooldownGroup"
                  type="number"
                  min={1}
                  step={1}
                />
              </span>
            </div>
          </div>
        {/if}

        <!-- Damage Breakdown (bars) -->
        <div class="stats-section damage-section">
          <h4 class="section-title">Damage Breakdown</h4>
          <DamageBreakdownGrid weapon={activeWeapon} isMining={activeWeapon?.Properties?.Type?.startsWith('Mining Laser')} />
        </div>

        <!-- Effects (if any) -->
        {#if hasEffects || $editMode}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects</h4>
            <div class="effects-combined">
              <EffectsEditor
                effects={activeWeapon?.EffectsOnEquip || []}
                fieldName="EffectsOnEquip"
                availableEffects={effects}
                effectType="equip"
                showEmpty={$editMode}
              />
              <EffectsEditor
                effects={activeWeapon?.EffectsOnUse || []}
                fieldName="EffectsOnUse"
                availableEffects={effects}
                effectType="use"
                showEmpty={$editMode}
              />
            </div>
          </div>
        {/if}

        <!-- Loadout Calculator Link -->
        <a href="/tools/loadouts?weapon={encodeURIComponentSafe(activeWeapon.Name)}" class="loadout-link-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="4" y="4" width="16" height="16" rx="2" />
            <path d="M9 9h6M9 12h6M9 15h4" />
          </svg>
          <span>Open in Loadout Calculator</span>
        </a>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            value={activeWeapon.Name}
            path="Name"
            type="text"
            required
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeWeapon.Properties?.Description || ''}
              placeholder="Enter weapon description..."
              onchange={(data) => updateField('Properties.Description', data)}
              showWaypoints={true}
            />
          {:else if activeWeapon.Properties?.Description}
            <div class="description-content">{@html activeWeapon.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {activeWeapon.Name} is a {activeWeapon.Properties?.Class?.toLowerCase() || ''} {activeWeapon.Properties?.Type?.toLowerCase() || ''} weapon.
            </div>
          {/if}
        </div>

        <!-- Tiering Section -->
        {#if isTierable}
          <DataSection
            title="Tiers"
            icon=""
            bind:expanded={panelStates.tiers}
            subtitle="{(additional.tierInfo?.length || activeWeapon?.Tiers?.length || 0)} tiers"
            ontoggle={savePanelStates}
          >
            <TieringEditor entity={activeWeapon} entityType="Weapon" tierInfo={additional.tierInfo || []} />
          </DataSection>
        {/if}

        <!-- Market Prices Section -->
        {#if !activeWeapon?.Properties?.IsUntradeable}
        <MarketPriceSection
          itemId={activeWeapon?.ItemId}
          itemName={activeWeapon?.Name}
          entityType="Weapon"
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
      </article>
    </div>
  {:else}
    <div class="no-selection">
      {#if data.isCreateMode && !user}
        <h2>Login Required</h2>
        <p>You need to log in and verify your account to create new weapons.</p>
        <a href="/discord/login?redirect={encodeURIComponent($page.url.pathname + $page.url.search)}" class="login-link-btn">
          Login with Discord
        </a>
      {:else if data.isCreateMode}
        <h2>Loading...</h2>
        <p>Preparing new weapon form...</p>
      {:else}
        <h2>Weapons</h2>
        <p>Select a weapon from the list to view details.</p>
      {/if}
    </div>
  {/if}
</WikiPage>

<style>
  /* Width override (global default is 300px) - scoped to desktop to not
     override the global stacked/mobile width: auto due to Svelte specificity */
  @media (min-width: 1400px) {
    .wiki-infobox-float {
      width: 320px;
    }
  }

  /* Wider select dropdowns for Class, Category, Type, Professions */
  .stat-value :global(.inline-edit .edit-select) {
    min-width: 160px;
  }

  .stat-value.wide-select :global(.inline-edit .edit-select) {
    min-width: 180px;
  }

  .damage-section,
  .effects-section {
    padding: 12px;
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

  @media (max-width: 899px) {
    .effects-combined {
      flex-direction: column;
    }
  }

  .loadout-link-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 16px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    color: var(--text-color);
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.15s;
  }

  .loadout-link-btn:hover {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .loadout-link-btn svg {
    flex-shrink: 0;
  }

  .no-selection .login-link-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 16px;
    padding: 10px 20px;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    text-decoration: none;
    border-radius: 6px;
    font-weight: 500;
    transition: all 0.15s;
  }

  .no-selection .login-link-btn:hover {
    filter: brightness(1.1);
  }
</style>

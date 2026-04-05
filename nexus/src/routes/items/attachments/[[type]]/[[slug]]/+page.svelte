<!--
  @component Attachments Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Handles 7 subtypes: weaponamplifiers, weaponvisionattachments, absorbers,
  finderamplifiers, armorplatings, enhancers, mindforceimplants
  Supports full wiki editing (except enhancers, which are database-generated).
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
  import DamageBreakdownGrid from '$lib/components/wiki/DamageBreakdownGrid.svelte';
  import DefenseGridEdit from '$lib/components/wiki/DefenseGridEdit.svelte';
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

  // Legacy components for data display
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
        { key: 'effects', url: '/api/effects' }
      ]).then(deps => {
        data = { ...data, ...deps };
        editDepsLoading = false;
      });
    }
  });

  let attachment = $derived(data.object);
  let user = $derived(data.session?.user);
  let additional = $derived(data.additional || {});
  let pendingChange = $derived(data.pendingChange);
  let existingChange = $derived(data.existingChange);
  let isCreateMode = $derived(data.isCreateMode || false);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let effectsList = $derived(data.effects || []);

  // Local filter state - decoupled from URL
  let selectedFilter = $state(null);
  let filterInitialized = $state(false);

  $effect(() => {
    if (!untrack(() => filterInitialized)) {
      selectedFilter = additional.type || null;
      filterInitialized = true;
    }
  });

  $effect(() => {
    if (filterInitialized && !attachment && !isCreateMode) {
      if ((additional.type || null) !== untrack(() => selectedFilter)) {
        selectedFilter = additional.type || null;
      }
    }
  });
  let attachmentEntityId = $derived(attachment?.Id ?? attachment?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, attachmentEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));

  // Permission check - verified users and admins can edit
  // Enhancers are generated in the database and should not be editable
  let canEdit = $derived((user?.verified || user?.grants?.includes('wiki.edit')) && additional.type !== 'enhancers');

  // For multi-type pages, data.items is an object keyed by type
  let allItems = $derived((() => {
    if (!data.items) return [];
    if (selectedFilter && data.items[selectedFilter]) {
      return data.items[selectedFilter];
    }
    // No filter selected - combine all items from all types
    const combined = [];
    for (const [type, items] of Object.entries(data.items)) {
      for (const item of items) {
        combined.push({ ...item, _type: type });
      }
    }
    return combined;
  })());

  // Type navigation buttons
  const typeButtons = [
    { label: 'Amplifiers', title: 'Weapon Amplifiers', type: 'weaponamplifiers' },
    { label: 'Scopes', title: 'Sights/Scopes', type: 'weaponvisionattachments' },
    { label: 'Absorbers', title: 'Deterioration Absorbers', type: 'absorbers' },
    { label: 'Finder Amp', title: 'Finder Amplifiers', type: 'finderamplifiers' },
    { label: 'Platings', title: 'Armor Platings', type: 'armorplatings' },
    { label: 'Enhancers', title: 'Enhancers', type: 'enhancers' },
    { label: 'Implants', title: 'Mindforce Implants', type: 'mindforceimplants' }
  ];

  // Type name mapping
  function getTypeName(type) {
    switch (type) {
      case 'weaponamplifiers': return 'Weapon Amplifier';
      case 'weaponvisionattachments': return 'Sight/Scope';
      case 'absorbers': return 'Deterioration Absorber';
      case 'finderamplifiers': return 'Finder Amplifier';
      case 'armorplatings': return 'Armor Plating';
      case 'enhancers': return 'Enhancer';
      case 'mindforceimplants': return 'Mindforce Implant';
      default: return 'Attachment';
    }
  }

  // Entity type for editing
  function getEntityType(type) {
    switch (type) {
      case 'weaponamplifiers': return 'WeaponAmplifier';
      case 'weaponvisionattachments': return 'WeaponVisionAttachment';
      case 'absorbers': return 'Absorber';
      case 'finderamplifiers': return 'FinderAmplifier';
      case 'armorplatings': return 'ArmorPlating';
      case 'enhancers': return 'Enhancer';
      case 'mindforceimplants': return 'MindforceImplant';
      default: return null;
    }
  }

  // Empty entity template for create mode (type-specific)
  function getEmptyEntity(type) {
    const base = {
      Name: '',
      Properties: {
        Description: '',
        Weight: 0,
        Economy: {
          MaxTT: 0,
          MinTT: 0
        }
      },
      EffectsOnEquip: []
    };

    switch (type) {
      case 'weaponamplifiers':
        base.Properties.Type = '';
        base.Properties.Economy.Decay = 0;
        base.Properties.Economy.AmmoBurn = 0;
        base.Properties.Economy.Efficiency = 0;
        base.Properties.Economy.Absorption = 0;
        base.Properties.Damage = {
          Impact: 0, Cut: 0, Stab: 0, Penetration: 0,
          Shrapnel: 0, Burn: 0, Cold: 0, Acid: 0, Electric: 0
        };
        break;
      case 'weaponvisionattachments':
        base.Properties.Type = null;
        base.Properties.Zoom = 0;
        base.Properties.Economy.Decay = 0;
        base.Properties.Economy.Efficiency = 0;
        base.Properties.SkillModification = 0;
        base.Properties.SkillBonus = 0;
        break;
      case 'absorbers':
        base.Properties.Economy.Efficiency = 0;
        base.Properties.Economy.Absorption = 0;
        base.Properties.Economy.Decay = 0;
        break;
      case 'finderamplifiers':
        base.Properties.Efficiency = 0;
        base.Properties.Economy.Decay = 0;
        base.Properties.MinProfessionLevel = 0;
        break;
      case 'armorplatings':
        base.Properties.Economy.Durability = 0;
        base.Properties.Defense = {
          Block: 0, Impact: 0, Cut: 0, Stab: 0, Penetration: 0,
          Shrapnel: 0, Burn: 0, Cold: 0, Acid: 0, Electric: 0
        };
        break;
      case 'enhancers':
        base.Properties.Tool = '';
        base.Properties.Type = '';
        base.Properties.Socket = 0;
        break;
      case 'mindforceimplants':
        base.Properties.Economy.Absorption = 0;
        base.Properties.MaxProfessionLevel = 0;
        break;
    }

    return base;
  }

  // ========== WIKI EDIT STATE ==========
  // Initialize edit state when user/entity changes
  $effect(() => {
    if (user) {
      const entityType = getEntityType(additional.type);
      const emptyEntity = getEmptyEntity(additional.type);
      const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
      initEditState(attachment || emptyEntity, entityType, isCreateMode, editChange);
    }
  });

  // Set pending change when it exists
  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });

  // Active entity: in edit mode use currentEntity, when viewing pending use its data, otherwise use original
  let activeEntity = $derived($editMode
    ? $currentEntity
    : $viewingPendingChange && $existingPendingChange?.data
      ? $existingPendingChange.data
      : attachment);

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });

  // Build navigation items
  let navItems = $derived(allItems);

  // Navigation filters - uses selectedFilter for active state (local, not URL-based)
  let typeNavFilters = $derived(typeButtons.map(btn => ({
    label: btn.label,
    title: btn.title,
    type: btn.type,
    active: selectedFilter === btn.type,
    href: selectedFilter === btn.type ? '/items/attachments' : `/items/attachments/${btn.type}`
  })));

  // Defense-type multi-select filter for armor platings.
  // Threshold scales with number of selected types (same rule as armor sets):
  // 1 type: 20%, 2: 35%, 3: 45%, 4+: +10% per additional.
  function getDefenseThreshold(count) {
    if (count <= 0) return 0;
    if (count === 1) return 0.20;
    if (count === 2) return 0.35;
    if (count === 3) return 0.45;
    return 0.45 + (count - 3) * 0.10;
  }

  function defenseFilterFn(item, selectedTypes) {
    if (!selectedTypes || selectedTypes.length === 0) return true;
    const totalDef = getTotalDefense(item);
    if (!totalDef) return false;
    const selectedDefense = selectedTypes.reduce(
      (sum, type) => sum + (item.Properties?.Defense?.[type] ?? 0), 0);
    return (selectedDefense / totalDef) >= getDefenseThreshold(selectedTypes.length);
  }

  function defenseSortFn(item, selectedTypes) {
    if (!selectedTypes || selectedTypes.length === 0) return 0;
    return selectedTypes.reduce(
      (sum, type) => sum + (item.Properties?.Defense?.[type] ?? 0), 0);
  }

  const defenseFilterHelp = [
    '1 type selected: 20% of total defense',
    '2 types selected: 35% of total defense',
    '3 types selected: 45% of total defense',
    '4+ types: +10% for each additional'
  ];

  // Combine type-navigation filters with the damage-type filter for armor platings
  let navFilters = $derived(selectedFilter === 'armorplatings'
    ? [
        ...typeNavFilters,
        {
          key: 'defenseType',
          label: 'Defense Type',
          multiSelect: true,
          filterFn: defenseFilterFn,
          sortFn: defenseSortFn,
          helpText: defenseFilterHelp,
          values: ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric']
            .map(type => ({ value: type, label: type.substring(0, 3) }))
        }
      ]
    : typeNavFilters);

  // Full column definitions for attachments
  const columnDefs = {
    cat: { key: 'cat', header: 'Type', width: '70px', filterPlaceholder: 'Amp', getValue: (item) => getTypeName(item._type || additional.type), format: (v) => v || '-' },
    damage: { key: 'damage', header: 'Damage', width: '70px', filterPlaceholder: '>5', getValue: (item) => getTotalDamage(item), format: (v) => v != null ? v.toFixed(1) : '-' },
    dpp: { key: 'dpp', header: 'DPP', width: '55px', filterPlaceholder: '>2', getValue: (item) => getDPP(item), format: (v) => v != null ? v.toFixed(2) : '-' },
    eff: { key: 'eff', header: 'Efficiency', width: '80px', filterPlaceholder: '>50', getValue: (item) => item.Properties?.Economy?.Efficiency, format: (v) => v != null ? v.toFixed(1) : '-' },
    finderEff: { key: 'finderEff', header: 'Efficiency', width: '80px', filterPlaceholder: '>50', getValue: (item) => item.Properties?.Efficiency, format: (v) => v != null ? v.toFixed(1) : '-' },
    type: { key: 'type', header: 'Type', width: '70px', filterPlaceholder: 'Scope', getValue: (item) => item.Properties?.Type, format: (v) => v || '-' },
    abs: { key: 'abs', header: 'Absorption', width: '85px', filterPlaceholder: '>5', getValue: (item) => item.Properties?.Economy?.Absorption, format: (v) => v != null ? `${(v * 100).toFixed(0)}%` : '-' },
    decay: { key: 'decay', header: 'Decay', width: '70px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.Decay, format: (v) => v != null ? v.toFixed(2) : '-' },
    ammoBurn: { key: 'ammoBurn', header: 'Ammo Burn', width: '70px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Economy?.AmmoBurn, format: (v) => v != null ? v : '-' },
    cost: { key: 'cost', header: 'Cost', width: '60px', filterPlaceholder: '>0', getValue: (item) => getCost(item), format: (v) => v != null ? v.toFixed(4) : '-' },
    def: { key: 'def', header: 'Total Def', width: '70px', filterPlaceholder: '>10', getValue: (item) => getTotalDefense(item), format: (v) => v != null ? v.toFixed(1) : '-' },
    dur: { key: 'dur', header: 'Durability', width: '70px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Economy?.Durability, format: (v) => v != null ? v : '-' },
    zoom: { key: 'zoom', header: 'Zoom', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Zoom, format: (v) => v != null ? `${v.toFixed(1)}x` : '-' },
    skillMod: { key: 'skillMod', header: 'Skill Mod', width: '65px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.SkillModification, format: (v) => v != null ? `${v}%` : '-' },
    skillBonus: { key: 'skillBonus', header: 'Skill Bonus', width: '75px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.SkillBonus, format: (v) => v != null ? `${v}` : '-' },
    maxTT: { key: 'maxTT', header: 'Max TT', width: '60px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 2, 4) : '-' },
    minTT: { key: 'minTT', header: 'Min TT', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Economy?.MinTT, format: (v) => v != null ? clampDecimals(v, 2, 4) : '-' },
    totalUses: { key: 'totalUses', header: 'Uses', width: '55px', filterPlaceholder: '>100', getValue: (item) => getTotalUses(item), format: (v) => v != null ? v : '-' },
    weight: { key: 'weight', header: 'Weight', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Weight, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' },
    tool: { key: 'tool', header: 'Tool', width: '70px', filterPlaceholder: 'Weapon', getValue: (item) => item.Properties?.Tool, format: (v) => v || '-' },
    tier: { key: 'tier', header: 'Tier', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Tier ?? item.Tier, format: (v) => v != null ? v : '-' },
    socket: { key: 'socket', header: 'Socket', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.Socket, format: (v) => v != null ? v : '-' },
    minLevel: { key: 'minLevel', header: 'Min Lvl', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.MinProfessionLevel, format: (v) => v != null ? v : '-' },
    maxLevel: { key: 'maxLevel', header: 'Max Lvl', width: '55px', filterPlaceholder: '>0', getValue: (item) => item.Properties?.MaxProfessionLevel, format: (v) => v != null ? v : '-' },
    lvl: { key: 'lvl', header: 'Level', width: '70px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Mindforce?.Level ?? item.Properties?.Level, format: (v) => v != null ? v : '-' }
  };

  // Type-specific sidebar table columns
  function getNavTableColumns(type) {
    switch (type) {
      case 'weaponamplifiers':
        return [columnDefs.damage, columnDefs.dpp, columnDefs.eff];
      case 'weaponvisionattachments':
        return [columnDefs.type, columnDefs.eff];
      case 'absorbers':
        return [columnDefs.abs, columnDefs.eff];
      case 'finderamplifiers':
        return [columnDefs.decay, columnDefs.finderEff];
      case 'armorplatings':
        return [columnDefs.def, columnDefs.dur];
      case 'enhancers':
        return [columnDefs.type, columnDefs.tier];
      case 'mindforceimplants':
        return [columnDefs.abs, columnDefs.lvl];
      default:
        return [columnDefs.cat, columnDefs.eff];
    }
  }

  function getNavFullWidthColumns(type) {
    switch (type) {
      case 'weaponamplifiers':
        return [columnDefs.damage, columnDefs.dpp, columnDefs.eff, columnDefs.type, columnDefs.decay, columnDefs.ammoBurn, columnDefs.cost, columnDefs.maxTT, columnDefs.totalUses, columnDefs.weight];
      case 'weaponvisionattachments':
        return [columnDefs.type, columnDefs.eff, columnDefs.zoom, columnDefs.decay, columnDefs.skillMod, columnDefs.skillBonus, columnDefs.maxTT, columnDefs.weight];
      case 'absorbers':
        return [columnDefs.abs, columnDefs.eff, columnDefs.decay, columnDefs.maxTT, columnDefs.minTT, columnDefs.weight];
      case 'finderamplifiers':
        return [columnDefs.decay, columnDefs.finderEff, columnDefs.minLevel, columnDefs.maxTT, columnDefs.minTT, columnDefs.totalUses, columnDefs.weight];
      case 'armorplatings':
        return [columnDefs.def, columnDefs.dur, columnDefs.maxTT, columnDefs.minTT, columnDefs.weight];
      case 'enhancers':
        return [columnDefs.type, columnDefs.tier, columnDefs.tool, columnDefs.socket, columnDefs.maxTT, columnDefs.weight];
      case 'mindforceimplants':
        return [columnDefs.abs, columnDefs.maxLevel, columnDefs.lvl, columnDefs.maxTT, columnDefs.minTT, columnDefs.weight];
      default:
        return [columnDefs.cat, columnDefs.eff, columnDefs.maxTT, columnDefs.weight];
    }
  }

  let navTableColumns = $derived(getNavTableColumns(selectedFilter));
  let navFullWidthColumns = $derived(getNavFullWidthColumns(selectedFilter));
  const allAvailableColumns = Object.values(columnDefs);
  let navPageTypeId = $derived(`attachments-${selectedFilter || 'all'}`);

  // Custom href generator for items
  function getItemHref(item, basePath) {
    const type = item._type || selectedFilter || additional.type;
    if (type) {
      return `/items/attachments/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Base path for navigation - uses selectedFilter so it persists
  let effectiveBasePath = $derived(selectedFilter
    ? `/items/attachments/${selectedFilter}`
    : '/items/attachments');

  // Create categories for the "New" dropdown (exclude enhancers which are database-generated)
  let createCategories = $derived(typeButtons
    .filter(btn => btn.type !== 'enhancers')
    .map(btn => ({
      label: getTypeName(btn.type),
      href: `/items/attachments/${btn.type}`
    })));

  // Filter pending creates by selected filter type
  let filteredPendingCreates = $derived(selectedFilter
    ? (userPendingCreates || []).filter(change => {
        const entityType = getEntityType(selectedFilter);
        return change.entity === entityType;
      })
    : userPendingCreates || []);

  // Breadcrumbs
  let breadcrumbs = $derived([
    { label: 'Items', href: '/items' },
    { label: 'Attachments', href: '/items/attachments' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + 's', href: `/items/attachments/${additional.type}` }] : []),
    ...(attachment ? [{ label: attachment.Name }] : [])
  ]);

  // SEO
  let seoDescription = $derived(attachment?.Properties?.Description ||
    `${attachment?.Name || 'Attachment'} - ${getTypeName(additional.type)} in Entropia Universe.`);

  let canonicalUrl = $derived(attachment
    ? `https://entropianexus.com/items/attachments/${additional.type}/${encodeURIComponentSafe(attachment.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/attachments/${additional.type}`
    : 'https://entropianexus.com/items/attachments');

  // Image URL for SEO
  let entityImageUrl = $derived(attachment?.Id && additional.type
    ? `/api/img/${getEntityType(additional.type).toLowerCase()}/${attachment.Id}`
    : null);

  // ========== CALCULATION FUNCTIONS ==========
  function getCost(item) {
    if (!item?.Properties?.Economy) return null;
    const decay = item.Properties.Economy.Decay ?? 0;
    const ammoBurn = item.Properties.Economy.AmmoBurn ?? 0;
    if (additional.type === 'weaponamplifiers') {
      return decay != null && ammoBurn != null ? decay + ammoBurn / 100 : null;
    }
    return decay;
  }

  function getTotalUses(item) {
    if (!item?.Properties?.Economy?.MaxTT || !item?.Properties?.Economy?.Decay) return null;
    const maxTT = item.Properties.Economy.MaxTT;
    const minTT = item.Properties.Economy.MinTT ?? 0;
    const decay = item.Properties.Economy.Decay;
    return Math.floor((maxTT - minTT) / (decay / 100));
  }

  function getTotalDamage(item) {
    if (!item?.Properties?.Damage) return 0;
    const d = item.Properties.Damage;
    return (d.Impact ?? 0) + (d.Cut ?? 0) + (d.Stab ?? 0) + (d.Penetration ?? 0) +
           (d.Shrapnel ?? 0) + (d.Burn ?? 0) + (d.Cold ?? 0) + (d.Acid ?? 0) + (d.Electric ?? 0);
  }

  function getEffectiveDamage(item) {
    const totalDamage = getTotalDamage(item);
    return totalDamage != null ? totalDamage * (0.88 * 0.75 + 0.02 * 1.75) : null;
  }

  function getDPP(item) {
    const cost = getCost(item);
    const effectiveDamage = getEffectiveDamage(item);
    if (cost && effectiveDamage) return effectiveDamage / cost;
    return null;
  }

  function getTotalDefense(item) {
    if (!item?.Properties?.Defense) return 0;
    const d = item.Properties.Defense;
    return (d.Impact ?? 0) + (d.Cut ?? 0) + (d.Stab ?? 0) + (d.Penetration ?? 0) +
           (d.Shrapnel ?? 0) + (d.Burn ?? 0) + (d.Cold ?? 0) + (d.Acid ?? 0) + (d.Electric ?? 0);
  }

  function getMaxArmorDecay(item) {
    if (!item?.Properties?.Economy?.Durability || !getTotalDefense(item)) return null;
    return getTotalDefense(item) * ((100000 - item.Properties.Economy.Durability) / 100000) * 0.05;
  }

  function getTotalAbsorption(item) {
    if (!item?.Properties?.Economy?.MaxTT) return null;
    const maxArmorDecay = getMaxArmorDecay(item);
    if (!maxArmorDecay) return null;
    const minTT = item.Properties.Economy.MinTT ?? 0;
    return getTotalDefense(item) * ((item.Properties.Economy.MaxTT - minTT) / (maxArmorDecay / 100));
  }

  function getEnhancerEffect(item) {
    const key = `${item?.Properties?.Tool} ${item?.Properties?.Type}`;
    const effects = {
      'Weapon Damage': 'Increases damage, decay and ammo burn by 10%',
      'Weapon Range': 'Increases range by 5%',
      'Weapon Skill Modification': 'Increases your profession levels for the weapon by 0.5',
      'Weapon Economy': 'Reduces the decay and ammo burn by approximately 1-1.1%',
      'Weapon Accuracy': 'Increases the chance for a critical hit by 0.2% (at max skill)',
      'Armor Defense': 'Increases all protection by 5%',
      'Armor Durability': 'Increases durability by 10%',
      'Medical Tool Economy': 'Reduces the decay by 10%',
      'Medical Tool Heal': 'Increases the decay and the amount healed by 5%',
      'Medical Tool Skill Modification': 'Increases your profession levels for the tool by 0.5',
      'Mining Excavator Speed': 'Increases the efficiency by 10%',
      'Mining Finder Depth': 'Increases the average depth by approximately 7.5%',
      'Mining Finder Range': 'Increases the range by 1%',
      'Mining Finder Skill Modification': 'Increases your profession levels for the finder by 0.5'
    };
    return effects[key] || null;
  }

  // ========== COMPUTED VALUES ========== (use activeEntity for live updates)
  let cost = $derived(getCost(activeEntity));
  let totalUses = $derived(getTotalUses(activeEntity));
  let totalDamage = $derived(getTotalDamage(activeEntity));
  let dpp = $derived(getDPP(activeEntity));
  let totalDefense = $derived(getTotalDefense(activeEntity));
  let maxArmorDecay = $derived(getMaxArmorDecay(activeEntity));
  let totalAbsorptionVal = $derived(getTotalAbsorption(activeEntity));
  let enhancerEffect = $derived(getEnhancerEffect(activeEntity));

  // Check for effects
  let hasEquipEffects = $derived(activeEntity?.EffectsOnEquip?.length > 0);

  // Damage types with values for display
  const damageTypes = ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];
  const defenseTypes = ['Block', 'Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];
  const platingDefenseTypes = ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];
  const amplifierTypeOptions = [
    { value: 'Energy', label: 'Energy' },
    { value: 'BLP', label: 'BLP' },
    { value: 'Explosive', label: 'Explosive' },
    { value: 'Mining', label: 'Mining' },
    { value: 'Melee', label: 'Melee' },
    { value: 'Matrix', label: 'Matrix' },
    { value: 'Mindforce', label: 'Mindforce' }
  ];

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    damage: true,
    defense: true,
    marketPrices: true,
    acquisition: true
  });

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-attachment-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-attachment-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }
</script>

<WikiSEO
  title={attachment?.Name || `${getTypeName(additional.type)}s`}
  description={seoDescription}
  entityType={getEntityType(additional.type)}
  entity={activeEntity}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={attachment}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Attachments"
  {breadcrumbs}
  entity={activeEntity}
  basePath={effectiveBasePath}
  {navItems}
  {navFilters}
  {navTableColumns}
  navAllAvailableColumns={allAvailableColumns}
  navFullWidthColumns={navFullWidthColumns}
  navPageTypeId={navPageTypeId}
  navGetItemHref={getItemHref}
  {user}
  editable={true}
  canEdit={canEdit}
  {createCategories}
  {canCreateNew}
  userPendingCreates={filteredPendingCreates}
  {userPendingUpdates}
  {editDepsLoading}
>
  {#if attachment || isCreateMode}
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
            entityType={getEntityType(additional.type)?.toLowerCase()}
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
            {#if activeEntity?.Properties?.IsRare}<span class="item-flag-badge rare">Rare</span>{/if}
            {#if activeEntity?.Properties?.IsUntradeable}<span class="item-flag-badge untradeable">Untradeable</span>{/if}
          </div>
        </div>

        <!-- Tier-1 Stats (type-specific primary stats) -->
        <div class="stats-section tier-1">
          <!-- Amplifiers: Efficiency, Total Damage, DPP -->
          {#if additional.type === 'weaponamplifiers'}
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.Efficiency != null ? `${activeEntity.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Total Damage</span>
              <span class="stat-value">{totalDamage?.toFixed(1) || 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">DPP</span>
              <span class="stat-value">{dpp != null ? dpp.toFixed(4) : 'N/A'}</span>
            </div>

          <!-- Scopes/Sights: Efficiency, Skill Mod -->
          {:else if additional.type === 'weaponvisionattachments'}
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.Efficiency != null ? `${activeEntity.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Skill Mod.</span>
              <span class="stat-value">{activeEntity?.Properties?.SkillModification != null ? activeEntity.Properties.SkillModification.toFixed(1) : 'N/A'}</span>
            </div>

          <!-- Absorbers: Efficiency, Absorption -->
          {:else if additional.type === 'absorbers'}
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.Efficiency != null ? `${activeEntity.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Absorption</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.Absorption != null ? `${clampDecimals(activeEntity.Properties.Economy.Absorption * 100, 0, 2)}%` : 'N/A'}</span>
            </div>

          <!-- Mindforce implants: TT, Absorption -->
          {:else if additional.type === 'mindforceimplants'}
            <div class="stat-row primary">
              <span class="stat-label">TT Value</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.MaxTT != null ? `${clampDecimals(activeEntity.Properties.Economy.MaxTT, 2, 4)} PED` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Absorption</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.Absorption != null ? `${clampDecimals(activeEntity.Properties.Economy.Absorption * 100, 0, 2)}%` : 'N/A'}</span>
            </div>

          <!-- Finder amplifiers: Efficiency, Decay -->
          {:else if additional.type === 'finderamplifiers'}
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{activeEntity?.Properties?.Efficiency != null ? activeEntity.Properties.Efficiency.toFixed(1) : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Decay</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.Decay != null ? `${activeEntity.Properties.Economy.Decay.toFixed(4)} PEC` : 'N/A'}</span>
            </div>

          <!-- Armor platings: Total Defense, Durability -->
          {:else if additional.type === 'armorplatings'}
            <div class="stat-row primary">
              <span class="stat-label">Total Defense</span>
              <span class="stat-value">{totalDefense?.toFixed(1) || 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Durability</span>
              <span class="stat-value">{activeEntity?.Properties?.Economy?.Durability ?? 'N/A'}</span>
            </div>

          <!-- Enhancers: Tool, Type -->
          {:else if additional.type === 'enhancers'}
            <div class="stat-row primary">
              <span class="stat-label">Tool</span>
              <span class="stat-value">{activeEntity?.Properties?.Tool || 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Type</span>
              <span class="stat-value">{activeEntity?.Properties?.Type || 'N/A'}</span>
            </div>
          {/if}
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

          {#if additional.type === 'weaponamplifiers'}
            <div class="stat-row">
              <span class="stat-label">Amplifier Type</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Type}
                  path="Properties.Type"
                  type="select"
                  options={amplifierTypeOptions}
                />
              </span>
            </div>
          {:else if additional.type === 'absorbers'}
            <div class="stat-row">
              <span class="stat-label">Absorption</span>
              <span class="stat-value">
                {#if $editMode}
                  <span class="inline-edit editable">
                    <span class="edit-wrapper">
                      <input
                        type="number"
                        class="edit-input"
                        min="0"
                        max="100"
                        step="0.1"
                        value={activeEntity?.Properties?.Economy?.Absorption != null
                          ? (activeEntity.Properties.Economy.Absorption * 100).toFixed(1)
                          : ''}
                        oninput={(e) => {
                          const value = e.target.value === '' ? null : parseFloat(e.target.value) / 100;
                          updateField('Properties.Economy.Absorption', value);
                        }}
                      />
                      <span class="suffix">%</span>
                    </span>
                  </span>
                {:else}
                  {activeEntity?.Properties?.Economy?.Absorption != null
                    ? `${clampDecimals(activeEntity.Properties.Economy.Absorption * 100, 0, 2)}%`
                    : 'N/A'}
                {/if}
              </span>
            </div>
          {:else if additional.type === 'weaponvisionattachments'}
            <div class="stat-row">
              <span class="stat-label">Type</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Type}
                  path="Properties.Type"
                  type="select"
                  options={[
                    { value: 'Scope', label: 'Scope' },
                    { value: 'Sight', label: 'Sight' }
                  ]}
                />
              </span>
            </div>
            {#if activeEntity?.Properties?.Type === 'Scope'}
              <div class="stat-row">
                <span class="stat-label">Zoom</span>
                <span class="stat-value">
                  <InlineEdit
                    value={activeEntity?.Properties?.Zoom}
                    path="Properties.Zoom"
                    type="number"
                    suffix="x"
                    min={0}
                    step={0.1}
                  />
                </span>
              </div>
            {/if}
          {:else if additional.type === 'enhancers'}
            <div class="stat-row">
              <span class="stat-label">Socket</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Socket}
                  path="Properties.Socket"
                  type="number"
                />
              </span>
            </div>
          {:else if additional.type === 'mindforceimplants'}
            <div class="stat-row">
              <span class="stat-label">Max. Profession Level</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.MaxProfessionLevel}
                  path="Properties.MaxProfessionLevel"
                  type="number"
                />
              </span>
            </div>
          {/if}
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

        <!-- Damage Grid in Infobox (weapon amplifiers only) -->
        {#if additional.type === 'weaponamplifiers' && (totalDamage > 0 || $editMode)}
          <div class="stats-section damage-section">
            <h4 class="section-title">Damage Breakdown</h4>
            <DamageBreakdownGrid weapon={activeEntity} isMining={activeEntity?.Properties?.Type === 'Mining'} />
          </div>
        {/if}

        <!-- Defense Grid in Infobox (armor platings only) -->
        {#if additional.type === 'armorplatings' && (totalDefense > 0 || $editMode)}
          <div class="stats-section defense-section">
            <h4 class="section-title">Defense</h4>
            <DefenseGridEdit
              defense={activeEntity?.Properties?.Defense || {}}
              fieldPath="Properties.Defense"
              title="Total Defense"
              types={platingDefenseTypes}
            />
          </div>
        {/if}

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>

          {#if additional.type === 'weaponamplifiers' || additional.type === 'absorbers' || additional.type === 'weaponvisionattachments'}
            <div class="stat-row">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Economy?.Efficiency}
                  path="Properties.Economy.Efficiency"
                  type="number"
                  suffix="%"
                  min={0}
                  step={0.1}
                />
              </span>
            </div>
          {/if}

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

          {#if additional.type !== 'enhancers'}
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
          {/if}

          {#if additional.type === 'mindforceimplants' || (additional.type === 'weaponamplifiers' && activeEntity?.Properties?.Type === 'Mining')}
            <div class="stat-row">
              <span class="stat-label">Absorption</span>
              <span class="stat-value">
                {#if $editMode}
                  <span class="inline-edit editable">
                    <span class="edit-wrapper">
                      <input
                        type="number"
                        class="edit-input"
                        min="0"
                        max="100"
                        step="0.1"
                        value={activeEntity?.Properties?.Economy?.Absorption != null
                          ? (activeEntity.Properties.Economy.Absorption * 100).toFixed(1)
                          : ''}
                        oninput={(e) => {
                          const value = e.target.value === '' ? null : parseFloat(e.target.value) / 100;
                          updateField('Properties.Economy.Absorption', value);
                        }}
                      />
                      <span class="suffix">%</span>
                    </span>
                  </span>
                {:else}
                  {activeEntity?.Properties?.Economy?.Absorption != null
                    ? `${clampDecimals(activeEntity.Properties.Economy.Absorption * 100, 0, 2)}%`
                    : 'N/A'}
                {/if}
              </span>
            </div>
          {/if}

          {#if additional.type === 'weaponamplifiers' || additional.type === 'weaponvisionattachments' || additional.type === 'absorbers'}
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
          {/if}

          {#if additional.type === 'weaponamplifiers'}
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
            <div class="stat-row">
              <span class="stat-label">Cost</span>
              <span class="stat-value">{cost != null ? `${cost.toFixed(4)} PEC` : 'N/A'}</span>
            </div>
          {/if}

          {#if additional.type === 'armorplatings'}
            <div class="stat-row">
              <span class="stat-label">Durability</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.Economy?.Durability}
                  path="Properties.Economy.Durability"
                  type="number"
                  min={0}
                  step={1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Max. Decay</span>
              <span class="stat-value">{maxArmorDecay != null ? `${maxArmorDecay.toFixed(4)} PEC` : 'N/A'}</span>
            </div>
          {/if}

          {#if (additional.type === 'weaponamplifiers' || additional.type === 'weaponvisionattachments' || additional.type === 'finderamplifiers' || additional.type === 'absorbers') && totalUses}
            <div class="stat-row">
              <span class="stat-label">Total Uses</span>
              <span class="stat-value">{totalUses}</span>
            </div>
          {/if}

          {#if additional.type === 'armorplatings' && totalAbsorptionVal}
            <div class="stat-row">
              <span class="stat-label">Total Absorption</span>
              <span class="stat-value">{totalAbsorptionVal.toFixed(1)} HP</span>
            </div>
          {/if}
        </div>

        <!-- Skill Stats (for scopes and finder amps) -->
        {#if additional.type === 'weaponvisionattachments'}
          <div class="stats-section">
            <h4 class="section-title">Skill</h4>
            <div class="stat-row">
              <span class="stat-label">Skill Modification</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.SkillModification}
                  path="Properties.SkillModification"
                  type="number"
                  suffix="%"
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Skill Bonus</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.SkillBonus}
                  path="Properties.SkillBonus"
                  type="number"
                  step={0.1}
                />
              </span>
            </div>
          </div>
        {:else if additional.type === 'finderamplifiers'}
          <div class="stats-section">
            <h4 class="section-title">Skill</h4>
            <div class="stat-row">
              <span class="stat-label">Professions</span>
              <span class="stat-value links">
                <a href={getTypeLink('Prospector', 'Profession')} class="entity-link">Prospector</a>,
                <a href={getTypeLink('Surveyor', 'Profession')} class="entity-link">Surveyor</a>,
                <a href={getTypeLink('Treasure Hunter', 'Profession')} class="entity-link">Treasure Hunter</a>
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Min. Profession Level</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeEntity?.Properties?.MinProfessionLevel}
                  path="Properties.MinProfessionLevel"
                  type="number"
                />
              </span>
            </div>
          </div>
        {/if}

        <!-- Enhancer Effect -->
        {#if additional.type === 'enhancers' && enhancerEffect}
          <div class="stats-section effect-description">
            <h4 class="section-title">Effect</h4>
            <div class="effect-text">{enhancerEffect}</div>
          </div>
        {/if}

        <!-- Effects on Equip -->
        {#if hasEquipEffects || $editMode}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects on Equip</h4>
            {#if $editMode}
              <EffectsEditor
                effects={activeEntity?.EffectsOnEquip || []}
                fieldName="EffectsOnEquip"
                availableEffects={effectsList}
              />
            {:else}
              {#each activeEntity.EffectsOnEquip.sort((a,b) => a.Name.localeCompare(b.Name)) as effect}
                <div class="stat-row">
                  <span class="stat-label">{effect.Name}</span>
                  <span class="stat-value effect-value">{effect.Values.Strength}{effect.Values.Unit}</span>
                </div>
              {/each}
            {/if}
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
              onchange={(data) => updateField('Properties.Description', data)}
              placeholder="Enter a description for this {getTypeName(additional.type).toLowerCase()}..."
              showWaypoints={true}
            />
          {:else if activeEntity?.Properties?.Description}
            <div class="description-content">{@html activeEntity.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || 'This attachment'} is a {getTypeName(additional.type).toLowerCase()} used in Entropia Universe.
            </div>
          {/if}
        </div>

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
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>{additional.type ? getTypeName(additional.type) + 's' : 'Attachments'}</h2>
      <p>Select an {additional.type ? getTypeName(additional.type).toLowerCase() : 'attachment'} from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .stat-value.effect-value {
    color: var(--accent-color, #4a9eff);
  }

  .stat-value.links {
    text-align: right;
    font-size: 12px;
  }

  /* Effect description for enhancers */
  .effect-description .effect-text {
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-color);
  }

  /* Effects styling */
  .effects-section .stat-row {
    padding: 3px 0;
  }

  .inline-edit {
    display: inline-flex;
    flex-direction: column;
    gap: 2px;
  }

  .edit-wrapper {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .edit-input {
    padding: 4px 8px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    font-size: inherit;
    font-family: inherit;
    width: 80px;
  }

  .inline-edit.editable .edit-input {
    background-color: var(--bg-secondary, var(--secondary-color));
  }

  .suffix {
    color: var(--text-muted, #999);
    font-size: 0.9em;
  }
</style>

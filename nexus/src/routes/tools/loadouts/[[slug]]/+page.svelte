<script>
  // @ts-nocheck
  import '$lib/style.css';
  import '../loadouts.css';

  import { onMount, onDestroy, tick } from 'svelte';
  import { slide } from 'svelte/transition';
  import { browser } from '$app/environment';
  import { beforeNavigate, goto } from '$app/navigation';

  import FancyTable from '$lib/components/FancyTable.svelte';
  import { loading, darkMode } from '../../../../stores.js';
  import { clampDecimals, hasItemTag, encodeURIComponentSafe, getTypeLink } from '$lib/util.js';
  import * as LoadoutCalc from '$lib/utils/loadoutCalculations.js';
  import { buildEffectCaps, getEffectUnit as getEffectUnitFromCatalog } from '$lib/utils/loadoutEffects.js';
  import { evaluateLoadout } from '$lib/utils/loadoutEvaluator.js';
  import { loadLoadoutEntities } from '$lib/utils/entityLoader';
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import EffectsEditor from '$lib/components/wiki/EffectsEditor.svelte';

  export let data;
  $: user = data?.session?.user;
  $: isLoggedIn = !!user;

  // Shared loadout mode (read-only view)
  $: sharedLoadout = data?.additional?.sharedLoadout || data?.object || null;
  $: shareError = data?.additional?.shareError || null;
  $: shareCode = data?.additional?.shareCode || null;
  $: isSharedMode = !!sharedLoadout;
  $: sharedLoadoutData = sharedLoadout?.data ?? null;
  $: sharedDisplayName = sharedLoadoutData?.Name || sharedLoadout?.name || 'Shared Loadout';

  // Track if loadouts have been initialized (for mode transitions)
  let loadoutsInitialized = false;
  let loadoutsDataLoaded = false;

  // Initialize loadouts when entering normal mode (either on mount or after leaving shared mode)
  $: if (browser && !isSharedMode && !loadoutsInitialized) {
    initializeLoadoutsOnModeChange();
  }

  async function initializeLoadoutsOnModeChange() {
    loadoutsInitialized = true;
    loadoutsDataLoaded = false;
    loadCompareColumnPrefs();
    localLoadouts = readLocalLoadouts();
    loadouts = localLoadouts;

    if (isLoggedIn) {
      await fetchOnlineLoadouts();
      // Skip URL update during init so URL selection reactive can use the original URL
      await setActiveSource('online', { skipUrlUpdate: true });
      // Prompt to import local loadouts if user has local but no online loadouts
      if (!hasPromptedImport && onlineLoadouts.length === 0 && localLoadouts.length > 0) {
        showImportDialog = true;
        hasPromptedImport = true;
      }
    } else {
      await setActiveSource('local', { skipUrlUpdate: true });
    }

    loadoutsDataLoaded = true;
  }

  // Copy shared loadout state
  let isCopying = false;
  let copyStatus = null;
  let copyError = null;

  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];
  const LOCAL_STORAGE_KEY = 'loadouts';
  const AUTOSAVE_DELAY_MS = 10000;

  const isLimitedName = (name) => !!name && hasItemTag(name, 'L');

  function getArmorPieceLink(name) {
    if (!name) return null;
    return `/items/armors/${encodeURIComponentSafe(name)}`;
  }

  function getEquipmentLink(kind, name) {
    if (!name) return null;
    switch (kind) {
      case 'weapon':
        return getTypeLink(name, 'Weapon');
      case 'amplifier':
      case 'matrix':
        return getTypeLink(name, 'WeaponAmplifier');
      case 'scope':
      case 'sight':
      case 'scope-sight':
        return getTypeLink(name, 'WeaponVisionAttachment');
      case 'absorber':
        return getTypeLink(name, 'Absorber');
      case 'implant':
        return getTypeLink(name, 'MindforceImplant');
      case 'armorset':
        return getTypeLink(name, 'Armor');
      case 'armor':
        return getArmorPieceLink(name);
      case 'armorplating':
        return getTypeLink(name, 'ArmorPlating');
      case 'clothing':
        return getTypeLink(name, 'Clothing');
      case 'pet':
        return getTypeLink(name, 'Pet');
      case 'consumable':
        return getTypeLink(name, 'Consumable');
      default:
        return null;
    }
  }

  function getApiBase() {
    return browser
      ? (import.meta.env.VITE_API_URL || 'https://api.entropianexus.com')
      : (process.env.INTERNAL_API_URL || 'http://api:3000');
  }

  let settings = {
    onlyShowReasonableAmplifiers: true,
    overampCap: 10,
  }

  let weapons = [];
  let amplifiers = [];
  let scopes = [];
  let sights = [];
  let absorbers = [];
  let matrices = [];
  let implants = [];
  let armorsets = [];
  let armors = [];
  let armorplatings = [];
  let enhancers = [];
  let clothing = [];
  let pets = [];
  let stimulants = [];
  let effectsCatalog = [];
  let effectCaps = {};

  let entitiesLoading = true;
  let entitiesVersion = 0;

  let localLoadouts = [];
  let onlineLoadouts = [];
  let loadouts = [];
  let loadout = null;
  let activeSource = 'local';
  let activeOnlineId = null;
  let loadoutSearch = '';
  let onlineLoading = false;
  let onlineError = null;
  let isDirty = false;
  let autosaveDueAt = null;
  let autosaveTimeout = null;
  let autosaveTicker = null;
  let autosaveNow = Date.now();
  let isSaving = false;
  let saveError = null;
  let showShareDialog = false;
  let sharePublic = false;
  let shareLink = '';
  let shareCopyStatus = '';
  let shareCopyTimeout = null;
  let showImportDialog = false;
  let showImportSourceDialog = false;
  let importInProgress = false;
  let importError = null;
  let importSuccess = false;
  let hasPromptedImport = false;
  let showFileImport = false;
  let fileInput;

  // Delete confirmation dialog
  let showDeleteDialog = false;

  // URL selection tracking
  let urlSelectionAttempted = false;

  let activePicker = null;
  let showPickerDialog = false;
  let showPickerPreview = false;
  let pickerPreviewRow = null;
  let pickerPreviewItem = null;
  let suppressDirty = false;
  let isNavigationSave = false;
  let clothingReplaceNotice = '';
  let loadoutVersion = 0;
  let evaluation = null;
  let allEffects = [];
  let offensiveEffects = [];
  let defensiveEffects = [];
  let utilityEffects = [];
  let offensiveTotals = { damage: 0, reload: 0, critChance: 0, critDamage: 0 };
  let expandedEffectKeys = new Set();

  let compareMode = false;
  let compareType = 'weapons'; // 'weapons' | 'armor'
  let compareDisplay = 'values'; // 'values' | 'delta'
  let compareNameQuery = '';
  let compareHiddenLoadoutIds = new Set();
  let compareHiddenOpen = false;
  let compareColumnsOpen = false;
  let compareColumnKeysWeapons = ['name', 'efficiency', 'dps', 'dpp', 'reload', 'cost'];
  let compareColumnKeysArmor = ['name', 'armorName', 'totalDefense', 'topDefenseTypesShort', 'totalAbsorption', 'blockChance'];
  let compareAnchorId = null;
  let compareAnchorEval = null;
  let compareEffectiveDisplay = 'values';
  let compareVisibleKeys = [];
  let compareRows = [];
  let hiddenCompareRows = [];
  let compareColumns = [];

  const COMPARE_COLUMNS_STORAGE_KEYS = {
    weapons: 'nexus.loadouts.compare.columns.weapons',
    armor: 'nexus.loadouts.compare.columns.armor'
  };
  const COMPARE_HIDDEN_ROWS_STORAGE_KEY = 'nexus.loadouts.compare.hidden.loadoutIds';

  const COMPARE_COLUMN_ORDER = {
    weapons: [
      'name',
      'efficiency',
      'dps',
      'dpp',
      'reload',
      'totalDamage',
      'effectiveDamage',
      'range',
      'cost',
      'decay',
      'ammo',
      'skillModification',
      'skillBonus',
      'lowestTotalUses'
    ],
    armor: [
      'name',
      'armorName',
      'totalDefense',
      'topDefenseTypesShort',
      'totalAbsorption',
      'blockChance',
      'armorMarkupCost',
      'plateMarkupCost'
    ]
  };

  const COMPARE_COLUMN_LABELS = {
    name: 'Name',
    efficiency: 'Efficiency',
    dps: 'DPS',
    dpp: 'DPP',
    reload: 'Reload',
    totalDamage: 'Total Damage',
    effectiveDamage: 'Effective Damage',
    range: 'Range',
    cost: 'Cost',
    decay: 'Decay',
    ammo: 'Ammo',
    skillModification: 'Skill Modification',
    skillBonus: 'Skill Bonus',
    lowestTotalUses: 'Lowest Uses',
    armorName: 'Armor',
    totalDefense: 'Total Defense',
    topDefenseTypesShort: 'Defense Types',
    totalAbsorption: 'Total Absorption',
    blockChance: 'Block Chance',
    armorMarkupCost: 'Armor Markup',
    plateMarkupCost: 'Plate Markup'
  };

  function getCompareColumnLabel(key) {
    return COMPARE_COLUMN_LABELS[key] || key;
  }

  const COMPARE_MOBILE_KEYS = {
    weapons: ['name', 'efficiency', 'dps', 'dpp'],
    armor: ['name', 'topDefenseTypesShort']
  };

  function sortCompareKeys(type, keys) {
    const order = COMPARE_COLUMN_ORDER[type] || [];
    const set = new Set(keys);
    // Always keep name first.
    const out = ['name'];
    for (const k of order) {
      if (k === 'name') continue;
      if (set.has(k)) out.push(k);
    }
    return out;
  }

  function safeParseJsonArray(raw) {
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : null;
    } catch {
      return null;
    }
  }

  function loadCompareColumnPrefs() {
    if (typeof localStorage === 'undefined') return;

    const weapons = safeParseJsonArray(localStorage.getItem(COMPARE_COLUMNS_STORAGE_KEYS.weapons) || '');
    if (weapons) compareColumnKeysWeapons = sortCompareKeys('weapons', weapons);

    const armor = safeParseJsonArray(localStorage.getItem(COMPARE_COLUMNS_STORAGE_KEYS.armor) || '');
    if (armor) compareColumnKeysArmor = sortCompareKeys('armor', armor);

    const hidden = safeParseJsonArray(localStorage.getItem(COMPARE_HIDDEN_ROWS_STORAGE_KEY) || '');
    if (hidden) compareHiddenLoadoutIds = new Set(hidden.filter(Boolean));
  }

  function persistCompareColumnPrefs(type) {
    if (typeof localStorage === 'undefined') return;
    const value = type === 'weapons' ? compareColumnKeysWeapons : compareColumnKeysArmor;
    localStorage.setItem(COMPARE_COLUMNS_STORAGE_KEYS[type], JSON.stringify(value));
  }

  function toggleCompareColumn(type, key) {
    if (key === 'name') return;

    const current = type === 'weapons' ? compareColumnKeysWeapons : compareColumnKeysArmor;
    const next = new Set(current);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    next.add('name');

    const sorted = sortCompareKeys(type, Array.from(next));
    if (type === 'weapons') compareColumnKeysWeapons = sorted;
    else compareColumnKeysArmor = sorted;

    persistCompareColumnPrefs(type);
  }

  function resetCompareColumns(type) {
    if (type === 'weapons') compareColumnKeysWeapons = ['name', 'efficiency', 'dps', 'dpp', 'reload', 'cost'];
    else compareColumnKeysArmor = ['name', 'totalDefense', 'topDefenseTypesShort', 'totalAbsorption', 'blockChance'];
    persistCompareColumnPrefs(type);
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function setCompareHidden(id, hidden) {
    const next = new Set(compareHiddenLoadoutIds);
    if (hidden) next.add(id);
    else next.delete(id);
    compareHiddenLoadoutIds = next;

    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(COMPARE_HIDDEN_ROWS_STORAGE_KEY, JSON.stringify(Array.from(compareHiddenLoadoutIds)));
    }
  }

  function handleCompareWrapperClick(event) {
    const target = event?.target;
    const btn = target?.closest?.('button[data-compare-action]');
    if (!btn) return;

    event.preventDefault();
    event.stopPropagation();

    const action = btn.getAttribute('data-compare-action');
    const id = btn.getAttribute('data-compare-id');
    if (!id) return;

    if (action === 'hide') setCompareHidden(id, true);
    if (action === 'show') setCompareHidden(id, false);
  }

  function handleCompareGlobalClick() {
    if (compareHiddenOpen) compareHiddenOpen = false;
    if (compareColumnsOpen) compareColumnsOpen = false;
  }

  let windowWidth = browser ? window.innerWidth : 0;
  let hasMeasuredLayout = false;
  let drawerOpen = false;
  let touchStartX = 0;
  let touchStartY = 0;
  let swipeOffset = 0;
  let swipeActive = false;
  let mobilePanelsEl;

  const mobilePanelItems = [
    { key: 'info', label: 'Stats', icon: 'icon-stats' },
    { key: 'settings', label: 'Settings', icon: 'icon-settings' },
    { key: 'weapons', label: 'Weapons', icon: 'icon-weapon' },
    { key: 'armor', label: 'Armor', icon: 'icon-armor' },
    { key: 'accessories', label: 'Accessories & Buffs', icon: 'icon-accessories' },
  ];
  const mobilePanels = mobilePanelItems.map((panel) => panel.key);
  let activeMobilePanel = 'weapons';

  function toggleEffectExpanded(key) {
    if (!key) return;
    if (expandedEffectKeys.has(key)) expandedEffectKeys.delete(key);
    else expandedEffectKeys.add(key);
    // Reassign so Svelte updates.
    expandedEffectKeys = new Set(expandedEffectKeys);
  }

  $: isMobileLayout = hasMeasuredLayout ? windowWidth < 900 : false;
  $: activeMobilePanelIndex = Math.max(0, mobilePanels.indexOf(activeMobilePanel));
  $: mobilePanelTranslate = isMobileLayout
    ? `translateX(calc(-${activeMobilePanelIndex * 100}% + ${swipeOffset}px))`
    : 'translateX(0)';

  $: breadcrumbs = isSharedMode
    ? [
        { label: 'Tools', href: '/tools' },
        { label: 'Loadouts', href: '/tools/loadouts' },
        { label: 'Shared' }
      ]
    : [
        { label: 'Tools', href: '/tools' },
        { label: 'Loadouts', href: '/tools/loadouts' },
        ...(loadout?.Name ? [{ label: loadout.Name }] : [])
      ];

  function alphabeticalSort(a, b) {
    if (a?.Name === null) return 1;
    if (b?.Name === null) return -1;

    return a.Name.localeCompare(b.Name, undefined, { numeric: true });
  }

  function processEntityData(entities) {
    const rawWeapons = entities.weapons || [];
    const rawAmplifiers = entities.weaponAmplifiers || [];
    const rawVisionAttachments = entities.weaponVisionAttachments || [];

    weapons = rawWeapons.filter(x => x.Properties?.Class !== 'Attached' && x.Properties?.Class !== 'Stationary').sort(alphabeticalSort);
    amplifiers = rawAmplifiers.filter(x => x.Properties?.Type !== 'Matrix').sort(alphabeticalSort);
    scopes = rawVisionAttachments.filter(x => x.Properties?.Type === 'Scope').sort(alphabeticalSort);
    sights = rawVisionAttachments.filter(x => x.Properties?.Type === 'Sight').sort(alphabeticalSort);
    absorbers = (entities.absorbers || []).sort(alphabeticalSort);
    matrices = rawAmplifiers.filter(x => x.Properties?.Type === 'Matrix').sort(alphabeticalSort);
    implants = (entities.mindforceImplants || []).sort(alphabeticalSort);
    armorsets = (entities.armorSets || []).sort(alphabeticalSort);
    armors = (entities.armors || []).sort(alphabeticalSort);
    armorplatings = (entities.armorPlatings || []).sort(alphabeticalSort);
    enhancers = (entities.enhancers || []).sort(alphabeticalSort);
    clothing = (entities.clothings || []).sort(alphabeticalSort);
    pets = (entities.pets || []).sort(alphabeticalSort);
    stimulants = (entities.consumables || []).sort(alphabeticalSort);
    entitiesVersion += 1;
    if (loadout) {
      loadout = loadout;
    }
  }

  const isRingSlot = (slot) => /ring|finger/i.test(slot || '');
  const getRingSide = (slot) => {
    const normalized = (slot || '').toLowerCase();
    if (normalized.includes('left')) return 'Left';
    if (normalized.includes('right')) return 'Right';
    return null;
  };

  $: ringItems = (clothing || []).filter(item => isRingSlot(item?.Properties?.Slot));

  // Use effective loadout for reactive statements (shared mode uses sharedLoadoutData)
  $: effectiveLoadoutData = isSharedMode ? sharedLoadoutData : loadout;
  $: selectedClothing = (effectiveLoadoutData?.Gear?.Clothing || []).filter(item => !isRingSlot(item?.Slot));
  $: selectedConsumables = effectiveLoadoutData?.Gear?.Consumables || [];
  $: leftRing = effectiveLoadoutData?.Gear?.Clothing ? getClothingSlotFromData(effectiveLoadoutData, 'Ring', 'Left') : null;
  $: rightRing = effectiveLoadoutData?.Gear?.Clothing ? getClothingSlotFromData(effectiveLoadoutData, 'Ring', 'Right') : null;
  $: activePet = effectiveLoadoutData?.Gear?.Pet?.Name
    ? pets.find(pet => pet.Name === effectiveLoadoutData.Gear.Pet.Name)
    : null;
  $: activePetEffects = activePet?.Effects || [];
  $: {
    // Ensure this recomputes when caps/catalog/entities/loadout change.
    // Use sharedLoadoutData in shared mode, otherwise use loadout
    loadoutVersion;
    effectCaps;
    effectsCatalog;
    entitiesVersion;
    const effectiveLoadout = isSharedMode ? sharedLoadoutData : loadout;
    evaluation = effectiveLoadout
      ? evaluateLoadout(
          effectiveLoadout,
          {
            armorSlots,
            weapons,
            amplifiers,
            scopes,
            sights,
            absorbers,
            matrices,
            implants,
            armors,
            armorPlatings: armorplatings,
            armorSets: armorsets,
            clothing,
            pets,
            stimulants
          },
          { effectsCatalog, effectCaps, isLimitedName }
        )
      : null;
    allEffects = evaluation?.effects?.all ?? [];
    offensiveEffects = evaluation?.effects?.offensive ?? [];
    defensiveEffects = evaluation?.effects?.defensive ?? [];
    utilityEffects = evaluation?.effects?.utility ?? [];
    offensiveTotals = evaluation?.offensiveTotals ?? { damage: 0, reload: 0, critChance: 0, critDamage: 0 };
  }

  $: stats = evaluation?.stats || {};

  // Auto-select loadout from URL when data becomes available (skip in shared mode)
  $: if (browser && !isSharedMode && data?.additional?.loadoutId && !urlSelectionAttempted && !loadout && loadoutsDataLoaded) {
    urlSelectionAttempted = true;
    const urlId = data.additional.loadoutId;
    // Try online loadouts first (database ID)
    if (activeSource === 'online' && onlineLoadouts.length > 0) {
      const record = onlineLoadouts.find(r => r.id === urlId);
      if (record) {
        setActiveLoadout(record.data, { recordId: record.id });
      } else {
        updateUrlSlug(null);
      }
    }
    // Try local loadouts (internal loadout ID)
    else if (activeSource === 'local' && localLoadouts.length > 0) {
      const local = localLoadouts.find(l => l.Id === urlId);
      if (local) {
        setActiveLoadout(local);
      } else {
        updateUrlSlug(null);
      }
    }
  }

  function getEvalContext() {
    return {
      armorSlots,
      weapons,
      amplifiers,
      scopes,
      sights,
      absorbers,
      matrices,
      implants,
      armors,
      armorPlatings: armorplatings,
      armorSets: armorsets,
      clothing,
      pets,
      stimulants
    };
  }

  function evaluateAnyLoadout(loadoutArg) {
    return loadoutArg
      ? evaluateLoadout(loadoutArg, getEvalContext(), { effectsCatalog, effectCaps, isLimitedName })
      : null;
  }

  let compareEvalCache = new Map();

  $: if (compareMode) {
    // Build a snapshot cache when entering compare (avoids per-render recomputation).
    // We intentionally don't depend on loadoutVersion to avoid recomputing on every edit.
    entitiesVersion;
    effectsCatalog;
    effectCaps;

    const ctx = getEvalContext();
    const next = new Map();
    for (const lo of loadouts) {
      if (!lo?.Id) continue;
      next.set(lo.Id, evaluateLoadout(lo, ctx, { effectsCatalog, effectCaps, isLimitedName }));
    }
    compareEvalCache = next;
  } else {
    compareEvalCache = new Map();
  }

  $: compareAnchorId = loadout?.Id ?? null;
  $: compareAnchorEval = compareAnchorId ? compareEvalCache.get(compareAnchorId) : null;
  $: compareEffectiveDisplay = compareDisplay === 'delta' && compareAnchorEval ? 'delta' : 'values';
  $: compareVisibleKeys = isMobileLayout
    ? COMPARE_MOBILE_KEYS[compareType]
    : (compareType === 'weapons' ? compareColumnKeysWeapons : compareColumnKeysArmor);

  function compareValue(value, anchorValue) {
    if (value == null) return null;
    if (compareEffectiveDisplay !== 'delta') return value;
    return (anchorValue == null) ? null : (value - anchorValue);
  }

  function formatNumber(value, digits = 2) {
    if (value == null || Number.isNaN(value)) return '-';
    return Number(value).toFixed(digits);
  }

  function formatDeltaNumber(value, digits = 2) {
    if (value == null || Number.isNaN(value)) return '-';
    const sign = value > 0 ? '+' : '';
    return `${sign}${Number(value).toFixed(digits)}`;
  }

  function formatDefenseTypesWithValues(defenseByType, max = 3) {
    const abbr = {
      Impact: 'Imp',
      Cut: 'Cut',
      Stab: 'Stb',
      Penetration: 'Pen',
      Shrapnel: 'Shr',
      Burn: 'Brn',
      Cold: 'Cld',
      Acid: 'Acd',
      Electric: 'Ele'
    };

    const entries = Object.entries(defenseByType || {})
      .filter(([, value]) => (value ?? 0) > 0)
      .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))
      .slice(0, Math.max(0, max));

    if (entries.length === 0) return '-';
    return entries
      .map(([key, value]) => `${formatNumber(value, 1)} ${abbr[key] || key.slice(0, 3)}`)
      .join(' / ');
  }

  function getDeltaClass(value, higherIsBetter) {
    if (value == null || Number.isNaN(value) || value === 0) return '';
    const good = value > 0 ? higherIsBetter : !higherIsBetter;
    return good ? 'cmp-pos' : 'cmp-neg';
  }

  function buildCompareRow(loadoutArg) {
    const id = loadoutArg?.Id;
    const evalResult = id ? compareEvalCache.get(id) : null;
    const s = evalResult?.stats || {};
    const a = compareAnchorEval?.stats || {};

    /** @type {any} */
    const row = {
      _id: id,
      _isAnchor: id != null && id === compareAnchorId,
      name: loadoutArg?.Name ?? ''
    };

    if (compareType === 'weapons') {
      row.efficiency = compareValue(s.efficiency ?? null, a.efficiency ?? null);
      row.dps = compareValue(s.dps ?? null, a.dps ?? null);
      row.dpp = compareValue(s.dpp ?? null, a.dpp ?? null);
      row.reload = compareValue(s.reload ?? null, a.reload ?? null);
      row.totalDamage = compareValue(s.totalDamage ?? null, a.totalDamage ?? null);
      row.effectiveDamage = compareValue(s.effectiveDamage ?? null, a.effectiveDamage ?? null);
      row.range = compareValue(s.range ?? null, a.range ?? null);
      row.cost = compareValue(s.cost ?? null, a.cost ?? null);
      row.decay = compareValue(s.decay ?? null, a.decay ?? null);
      row.ammo = compareValue(s.ammo ?? null, a.ammo ?? null);
      row.skillModification = compareValue(s.skillModification ?? null, a.skillModification ?? null);
      row.skillBonus = compareValue(s.skillBonus ?? null, a.skillBonus ?? null);
      row.lowestTotalUses = compareValue(s.lowestTotalUses ?? null, a.lowestTotalUses ?? null);
    } else {
      row.armorName = getArmorSetLabel(loadoutArg);
      row.totalDefense = compareValue(s.totalDefense ?? null, a.totalDefense ?? null);
      row.topDefenseTypesShort = formatDefenseTypesWithValues(s.totalDefenseByType, 3);
      row.totalAbsorption = compareValue(s.totalAbsorption ?? null, a.totalAbsorption ?? null);
      row.blockChance = compareValue(s.blockChance ?? null, a.blockChance ?? null);
      row.armorMarkupCost = compareValue(s.armorMarkupCost ?? null, a.armorMarkupCost ?? null);
      row.plateMarkupCost = compareValue(s.plateMarkupCost ?? null, a.plateMarkupCost ?? null);
    }

    return row;
  }

  $: {
    compareType;
    compareEffectiveDisplay;
    compareAnchorId;
    compareAnchorEval;
    const allowHidden = isMobileLayout;
    compareRows = compareMode
      ? loadouts
          .filter(lo => lo?.Id && (allowHidden || !compareHiddenLoadoutIds.has(lo.Id)))
          .filter(lo => !compareNameQuery?.trim() || (lo?.Name || '').toLowerCase().includes(compareNameQuery.trim().toLowerCase()))
          .map(buildCompareRow)
      : [];
  }

  $: hiddenCompareRows = loadouts
    .filter(lo => lo?.Id && compareHiddenLoadoutIds.has(lo.Id))
    .map(lo => ({ id: lo.Id, name: lo.Name }));

  $: if (compareHiddenLoadoutIds.size > 0) {
    const existing = new Set(loadouts.filter(lo => lo?.Id).map(lo => lo.Id));
    const pruned = new Set(Array.from(compareHiddenLoadoutIds).filter(id => existing.has(id)));
    if (pruned.size !== compareHiddenLoadoutIds.size) {
      compareHiddenLoadoutIds = pruned;
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(COMPARE_HIDDEN_ROWS_STORAGE_KEY, JSON.stringify(Array.from(compareHiddenLoadoutIds)));
      }
    }
  }

  function buildCompareColumns() {
    const type = compareType;
    const visible = new Set(compareVisibleKeys);

    const isDelta = compareEffectiveDisplay === 'delta';

    /** @type {Record<string, any>} */
    const defs = {
      name: {
        key: 'name',
        header: 'Name',
        width: '190px',
        main: true,
        sortable: true,
        searchable: true,
        rawValue: false,
        mobileWidth: '140px',
        formatter: (value, row) => {
          const label = escapeHtml(value || '');
          const cls = row?._isAnchor ? 'cmp-name anchor' : 'cmp-name';
          return `<span class=\"${cls}\" title=\"${label}\">${label}</span>`;
        }
      }
    };

    if (type === 'weapons') {
      defs.efficiency = {
        key: 'efficiency',
        header: 'Eff',
        width: '90px',
        sortable: true,
        hideOnMobile: false,
        mobileWidth: '82px',
        formatter: (value) => {
          const num = value == null ? null : Number(value);
          return isDelta ? `${formatDeltaNumber(num, 1)}%` : `${formatNumber(num, 1)}%`;
        },
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
      defs.dps = {
        key: 'dps',
        header: 'DPS',
        width: '100px',
        sortable: true,
        hideOnMobile: false,
        mobileWidth: '92px',
        formatter: (value) => isDelta ? formatDeltaNumber(value, 4) : formatNumber(value, 4),
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
      defs.dpp = {
        key: 'dpp',
        header: 'DPP',
        width: '100px',
        sortable: true,
        hideOnMobile: false,
        mobileWidth: '92px',
        formatter: (value) => isDelta ? formatDeltaNumber(value, 4) : formatNumber(value, 4),
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
      defs.reload = {
        key: 'reload',
        header: 'Reload',
        width: '110px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? `${formatDeltaNumber(value, 2)}s` : `${formatNumber(value, 2)}s`,
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, false)}` : 'cmp-num'
      };
      defs.totalDamage = {
        key: 'totalDamage',
        header: 'Tot Dmg',
        width: '110px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? formatDeltaNumber(value, 2) : formatNumber(value, 2),
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
      defs.effectiveDamage = {
        key: 'effectiveDamage',
        header: 'Eff Dmg',
        width: '110px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? formatDeltaNumber(value, 2) : formatNumber(value, 2),
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
      defs.range = {
        key: 'range',
        header: 'Range',
        width: '100px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? `${formatDeltaNumber(value, 2)}m` : `${formatNumber(value, 2)}m`,
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
      defs.cost = {
        key: 'cost',
        header: 'Cost',
        width: '110px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? `${formatDeltaNumber(value, 2)} PEC` : `${formatNumber(value, 2)} PEC`,
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, false)}` : 'cmp-num'
      };
      defs.decay = {
        key: 'decay',
        header: 'Decay',
        width: '110px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? `${formatDeltaNumber(value, 2)} PEC` : `${formatNumber(value, 2)} PEC`,
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, false)}` : 'cmp-num'
      };
      defs.ammo = {
        key: 'ammo',
        header: 'Ammo',
        width: '100px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? formatDeltaNumber(value, 2) : formatNumber(value, 2),
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, false)}` : 'cmp-num'
      };
      defs.skillModification = {
        key: 'skillModification',
        header: 'Skill Mod',
        width: '110px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? `${formatDeltaNumber(value, 1)}%` : `${formatNumber(value, 1)}%`,
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
      defs.skillBonus = {
        key: 'skillBonus',
        header: 'Skill Bonus',
        width: '120px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? `${formatDeltaNumber(value, 1)}%` : `${formatNumber(value, 1)}%`,
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
      defs.lowestTotalUses = {
        key: 'lowestTotalUses',
        header: 'Uses',
        width: '100px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? formatDeltaNumber(value, 0) : formatNumber(value, 0),
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
    } else {
      defs.armorName = {
        key: 'armorName',
        header: 'Armor',
        width: '180px',
        sortable: true,
        searchable: true,
        formatter: (value) => escapeHtml(value || '-')
      };
      defs.totalDefense = {
        key: 'totalDefense',
        header: 'Tot Def',
        width: '110px',
        sortable: true,
        hideOnMobile: false,
        mobileWidth: '102px',
        formatter: (value) => isDelta ? formatDeltaNumber(value, 0) : formatNumber(value, 0),
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
      defs.topDefenseTypesShort = {
        key: 'topDefenseTypesShort',
        header: 'Types',
        width: '120px',
        sortable: false,
        hideOnMobile: false,
        mobileWidth: '120px',
        formatter: (value) => `<span class=\"cmp-types\" title=\"${escapeHtml(value || '-')}\">${escapeHtml(value || '-')}</span>`
      };
      defs.totalAbsorption = {
        key: 'totalAbsorption',
        header: 'Absorb',
        width: '110px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? formatDeltaNumber(value, 0) : formatNumber(value, 0),
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
      defs.blockChance = {
        key: 'blockChance',
        header: 'Block',
        width: '100px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? `${formatDeltaNumber(value, 1)}%` : `${formatNumber(value, 1)}%`,
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, true)}` : 'cmp-num'
      };
      defs.armorMarkupCost = {
        key: 'armorMarkupCost',
        header: 'Armor MU',
        width: '120px',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? `${formatDeltaNumber(value, 2)} PED` : `${formatNumber(value, 2)} PED`,
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, false)}` : 'cmp-num'
      };
      defs.plateMarkupCost = {
        key: 'plateMarkupCost',
        header: 'Plate MU',
        sortable: true,
        hideOnMobile: true,
        formatter: (value) => isDelta ? `${formatDeltaNumber(value, 2)} PED` : `${formatNumber(value, 2)} PED`,
        cellClass: (value) => isDelta ? `cmp-num ${getDeltaClass(value, false)}` : 'cmp-num'
      };
    }

    for (const key of Object.keys(defs)) {
      delete defs[key].width;
      delete defs[key].mobileWidth;
      defs[key].widthBasis = 'both';
    }

    if (isMobileLayout) {
      for (const key of Object.keys(defs)) {
        defs[key].mobileWidth = null;
        defs[key].widthBasis = 'both';
      }
    }

    const cols = [];
    if (!isMobileLayout) {
      cols.push({
        key: '_vis',
        header: '',
        sortable: false,
        searchable: false,
        cellClass: () => 'cmp-action-cell',
        widthBasis: 'both',
        formatter: (_, row) => {
          const id = escapeHtml(row?._id);
          const disabled = row?._isAnchor;
          const title = disabled ? 'Current loadout' : 'Hide';
          const disabledAttr = disabled ? ' disabled' : '';
          return `<button type=\"button\" class=\"compare-row-action\" data-compare-action=\"hide\" data-compare-id=\"${id}\" title=\"${title}\" aria-label=\"${title}\"${disabledAttr}><svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\"><use href=\"#icon-hide\"></use></svg></button>`;
        }
      });
    }

    for (const key of COMPARE_COLUMN_ORDER[type]) {
      if (!visible.has(key)) continue;
      if (key === 'name') cols.push(defs.name);
      else if (defs[key]) cols.push(defs[key]);
    }

    return cols;
  }

  $: {
    compareType;
    compareVisibleKeys;
    compareEffectiveDisplay;
    compareColumns = compareMode ? buildCompareColumns() : [];
  }

  function createEmptyLoadout() {
    const newArmorObject = () => ({
      Name: null,
      Plate: null
    });

    return {
      Id: crypto?.randomUUID ? crypto.randomUUID() : Math.random().toString(16).slice(2),
      Name: 'New Loadout',
      Properties: {
        BonusDamage: 0,
        BonusCritChance: 0,
        BonusCritDamage: 0,
        BonusReload: 0
      },
      Gear: {
        Weapon: {
          Name: null,
          Amplifier: null,
          Scope: null,
          Sight: null,
          Absorber: null,
          Implant: null,
          Matrix: null,
          Enhancers: {
            Damage: 0,
            Accuracy: 0,
            Range: 0,
            Economy: 0,
            SkillMod: 0,
          }
        },
        Armor: {
          SetName: null,
          PlateName: null,
          Head: newArmorObject(),
          Torso: newArmorObject(),
          Arms: newArmorObject(),
          Hands: newArmorObject(),
          Legs: newArmorObject(),
          Shins: newArmorObject(),
          Feet: newArmorObject(),
          Enhancers: {
            Defense: 0,
            Durability: 0,
          },
          ManageIndividual: false,
        },
        Clothing: [],
        Consumables: [],
        Pet: {
          Name: null,
          Effect: null,
        }
      },
      Skill: {
        Hit: 200,
        Dmg: 200,
      },
      Markup: {
        Weapon: 100,
        Ammo: 100,
        Amplifier: 100,
        Absorber: 100,
        Scope: 100,
        Sight: 100,
        ScopeSight: 100,
        Matrix: 100,
        Implant: 100,
        ArmorSet: 100,
        PlateSet: 100,
        Armors: {
          Head: 100,
          Torso: 100,
          Arms: 100,
          Hands: 100,
          Legs: 100,
          Shins: 100,
          Feet: 100,
        },
        Plates: {
          Head: 100,
          Torso: 100,
          Arms: 100,
          Hands: 100,
          Legs: 100,
          Shins: 100,
          Feet: 100,
        },
      }
    };
  }

  function ensureLoadoutIds(items) {
    return (items || []).map(item => {
      if (!item || typeof item !== 'object') return createEmptyLoadout();
      if (!item.Id) {
        item.Id = crypto?.randomUUID ? crypto.randomUUID() : Math.random().toString(16).slice(2);
      }
      const normalizedConsumables = (item.Gear?.Consumables || []).map(entry => (
        typeof entry === 'string' ? { Name: entry } : entry
      ));
      item.Gear = {
        ...item.Gear,
        Clothing: item.Gear?.Clothing ?? [],
        Pet: item.Gear?.Pet ?? { Name: null, Effect: null },
        Consumables: normalizedConsumables
      };
      return item;
    });
  }

  function readLocalLoadouts() {
    if (typeof localStorage === 'undefined') return [];
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return ensureLoadoutIds(Array.isArray(parsed) ? parsed : []);
    } catch (err) {
      console.error('Failed to read local loadouts:', err);
      return [];
    }
  }

  function writeLocalLoadouts(next) {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(next || []));
  }

  // Create a copy of a shared loadout
  function createCopyLoadout(source) {
    const clone = JSON.parse(JSON.stringify(source));
    clone.Id = crypto?.randomUUID ? crypto.randomUUID() : Math.random().toString(16).slice(2);
    clone.Name = source?.Name ? `Copy of ${source.Name}` : 'Loadout Copy';
    return clone;
  }

  async function handleMakeCopy() {
    if (!sharedLoadoutData || isCopying) return;
    isCopying = true;
    copyStatus = null;
    copyError = null;
    const copy = createCopyLoadout(sharedLoadoutData);

    try {
      if (user) {
        const response = await fetch('/api/tools/loadout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: copy.Name, data: copy })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result?.error || 'Failed to create loadout.');
        }
        copyStatus = 'Loadout saved to your account.';
      } else {
        const local = readLocalLoadouts();
        local.unshift(copy);
        writeLocalLoadouts(local);
        copyStatus = 'Loadout saved locally.';
      }
      await goto('/tools/loadouts');
    } catch (error) {
      console.error('Copy failed:', error);
      copyError = error.message || 'Failed to copy loadout.';
    } finally {
      isCopying = false;
    }
  }

  // URL slug helpers
  function updateUrlSlug(loadoutId) {
    if (!browser) return;
    if (isSharedMode) return; // Don't change URL in shared mode
    const newPath = loadoutId ? `/tools/loadouts/${loadoutId}` : '/tools/loadouts';
    if (window.location.pathname !== newPath) {
      goto(newPath, { replaceState: true, keepFocus: true, noScroll: true });
    }
  }

  async function setActiveLoadout(nextLoadout, { skipSave = false, recordId = null, skipUrlUpdate = false } = {}) {
    // Auto-save current loadout before switching (if dirty and online)
    if (!skipSave && activeSource === 'online' && isDirty && activeOnlineId && loadout && !isSaving) {
      await handleSave();
    }

    suppressDirty = true;
    loadout = nextLoadout || null;
    isDirty = false;
    autosaveDueAt = null;
    clearAutosaveTicker();
    saveError = null;
    if (activeSource === 'online') {
      // Use provided recordId if available, otherwise look up by data reference
      const record = recordId
        ? onlineLoadouts.find(r => r.id === recordId)
        : onlineLoadouts.find(r => r.data === loadout);
      activeOnlineId = record?.id || null;
      sharePublic = record?.public || false;
      shareLink = record?.share_code && typeof window !== 'undefined'
        ? `${window.location.origin}/tools/loadouts/${record.share_code}`
        : '';
      // Update URL with loadout ID (unless during initialization when URL should be preserved)
      if (!skipUrlUpdate) {
        updateUrlSlug(activeOnlineId);
      }
    } else {
      // For local loadouts, use the loadout's internal ID
      if (!skipUrlUpdate) {
        updateUrlSlug(nextLoadout?.Id || null);
      }
    }
    clothingReplaceNotice = '';
    // Wait for all Svelte reactive updates to complete, then reset dirty state
    // Using tick() ensures we wait for the reactive cascade (like resetMarkup) to finish
    await tick();
    suppressDirty = false;
    isDirty = false; // Ensure we're clean after all reactive updates
  }

  async function setActiveSource(nextSource, { skipUrlUpdate = false } = {}) {
    activeSource = nextSource;
    loadouts = activeSource === 'online'
      ? onlineLoadouts.map(r => r.data)
      : localLoadouts;
    // Don't auto-select - just clear current selection when switching sources
    // During initialization, skipUrlUpdate preserves the URL so URL selection reactive can use it
    await setActiveLoadout(null, { skipSave: true, skipUrlUpdate });
  }

  async function fetchOnlineLoadouts() {
    if (!isLoggedIn) return;
    onlineLoading = true;
    onlineError = null;
    try {
      const response = await fetch('/api/tools/loadout');
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.error || 'Failed to load online loadouts');
      }
      onlineLoadouts = (data || []).map(row => ({
        id: row.id,
        name: row.name,
        public: !!row.public,
        share_code: row.share_code || null,
        last_update: row.last_update,
        data: row.data || createEmptyLoadout()
      }));
      if (activeSource === 'online') {
        loadouts = onlineLoadouts.map(r => r.data);
        // Don't auto-select first loadout
      }
    } catch (err) {
      console.error('Failed to load online loadouts:', err);
      onlineError = err.message;
    } finally {
      onlineLoading = false;
    }
  }

  function markDirty() {
    if (suppressDirty) return;
    loadoutVersion += 1;
    if (activeSource !== 'online') return;
    if (!loadout) return;
    isDirty = true;
    scheduleAutosave();
  }

  function touchLoadouts() {
    if (activeSource === 'online') {
      onlineLoadouts = onlineLoadouts;
    } else {
      localLoadouts = localLoadouts;
      loadouts = localLoadouts;
      writeLocalLoadouts(localLoadouts);
    }
    loadoutVersion += 1;
  }

  function scheduleAutosave() {
    if (autosaveTimeout) clearTimeout(autosaveTimeout);
    autosaveDueAt = Date.now() + AUTOSAVE_DELAY_MS;
    autosaveTimeout = setTimeout(() => {
      autosaveTimeout = null;
      handleSave();
    }, AUTOSAVE_DELAY_MS);
    if (!autosaveTicker) {
      autosaveTicker = setInterval(() => {
        autosaveNow = Date.now();
      }, 1000);
    }
  }

  function clearAutosaveTicker() {
    if (autosaveTicker) {
      clearInterval(autosaveTicker);
      autosaveTicker = null;
    }
  }

  async function handleSave() {
    if (activeSource !== 'online' || !loadout) return;
    if (!activeOnlineId) return;
    isSaving = true;
    saveError = null;
    try {
      const payload = {
        name: loadout.Name || 'New Loadout',
        data: loadout,
        public: sharePublic || false
      };
      const response = await fetch(`/api/tools/loadout/${activeOnlineId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result?.error || 'Failed to save loadout');
      }
      const recordIndex = onlineLoadouts.findIndex(r => r.id === activeOnlineId);
      if (recordIndex >= 0) {
        onlineLoadouts[recordIndex] = {
          ...onlineLoadouts[recordIndex],
          name: result?.name || payload.name,
          public: result?.public ?? sharePublic,
          share_code: result?.share_code ?? onlineLoadouts[recordIndex].share_code,
          last_update: result?.last_update || onlineLoadouts[recordIndex].last_update,
          data: loadout
        };
        onlineLoadouts = onlineLoadouts;
      }
      if (result?.share_code && typeof window !== 'undefined') {
        shareLink = `${window.location.origin}/tools/loadouts/${result.share_code}`;
      }
      isDirty = false;
      autosaveDueAt = null;
      clearAutosaveTicker();
    } catch (err) {
      console.error('Save failed:', err);
      saveError = err.message;
    } finally {
      isSaving = false;
    }
  }

  async function createOnlineLoadout() {
    const newLoadout = createEmptyLoadout();
    try {
      const response = await fetch('/api/tools/loadout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newLoadout.Name, data: newLoadout })
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result?.error || 'Failed to create loadout');
      }
      const record = {
        id: result.id,
        name: result.name,
        public: !!result.public,
        share_code: result.share_code || null,
        last_update: result.last_update,
        data: result.data || newLoadout
      };
      onlineLoadouts = [record, ...onlineLoadouts];
      loadouts = onlineLoadouts.map(r => r.data);
      await setActiveLoadout(record.data);
      isDirty = false;
      autosaveDueAt = null;
      clearAutosaveTicker();
    } catch (err) {
      console.error('Create failed:', err);
      onlineError = err.message;
    }
  }

  async function createLocalLoadout() {
    const newLoadout = createEmptyLoadout();
    localLoadouts = [newLoadout, ...localLoadouts];
    loadouts = localLoadouts;
    await setActiveLoadout(newLoadout);
    writeLocalLoadouts(localLoadouts);
  }

  function confirmDeleteLoadout() {
    if (!loadout) return;
    showDeleteDialog = true;
  }

  function cancelDelete() {
    showDeleteDialog = false;
  }

  async function deleteActiveLoadout() {
    showDeleteDialog = false;
    if (!loadout) return;
    if (activeSource === 'online') {
      if (!activeOnlineId) return;
      try {
        const response = await fetch(`/api/tools/loadout/${activeOnlineId}`, { method: 'DELETE' });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result?.error || 'Failed to delete loadout');
        }
        onlineLoadouts = onlineLoadouts.filter(r => r.id !== activeOnlineId);
        loadouts = onlineLoadouts.map(r => r.data);
        await setActiveLoadout(null, { skipSave: true });
      } catch (err) {
        console.error('Delete failed:', err);
        saveError = err.message;
      }
    } else {
      const index = localLoadouts.findIndex(x => x.Id === loadout.Id);
      if (index < 0) return;
      localLoadouts.splice(index, 1);
      localLoadouts = localLoadouts;
      loadouts = localLoadouts;
      await setActiveLoadout(null, { skipSave: true });
      writeLocalLoadouts(localLoadouts);
    }
  }

  function exportActiveLoadout() {
    if (!loadout) return;
    const data = JSON.stringify(loadout);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (loadout.Name ?? 'loadout') + '.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleFileChange() {
    const file = fileInput?.files?.[0];
    if (!file) return;
    const reader = new FileReader();

    reader.onload = (e) => {
      try {
        const contents = e.target.result;
        const data = JSON.parse(contents);
        if (!data || typeof data !== 'object') return;
        const parsed = ensureLoadoutIds([data])[0];
        localLoadouts = [parsed, ...localLoadouts];
        loadouts = localLoadouts;
        setActiveLoadout(parsed);
        writeLocalLoadouts(localLoadouts);
      } catch (err) {
        console.error('Failed to import loadout:', err);
      }
    };

    reader.readAsText(file);
  }

  function importLoadoutFile() {
    if (!fileInput) return;
    fileInput.click();
  }

  function openPicker(kind) {
    if (activePicker === kind && showPickerDialog) {
      closePicker();
      return;
    }
    activePicker = kind;
    showPickerDialog = true;
    showPickerPreview = false;
    pickerPreviewRow = null;
    pickerPreviewItem = null;
  }

  function closePicker() {
    showPickerDialog = false;
    activePicker = null;
    showPickerPreview = false;
    pickerPreviewRow = null;
    pickerPreviewItem = null;
  }

  function setMobilePanelIndex(index) {
    if (compareMode) {
      activeMobilePanel = 'weapons';
      return;
    }
    const count = mobilePanels.length;
    const nextIndex = ((index % count) + count) % count;
    activeMobilePanel = mobilePanels[nextIndex];
  }

  function handlePanelSwipe(direction) {
    if (!isMobileLayout) return;
    if (compareMode) {
      activeMobilePanel = 'weapons';
      return;
    }
    if (direction === 'next') {
      setMobilePanelIndex(activeMobilePanelIndex + 1);
    } else if (direction === 'prev') {
      setMobilePanelIndex(activeMobilePanelIndex - 1);
    }
  }

  function handleTouchStart(event) {
    if (!isMobileLayout) return;
    if (compareMode) return;
    const touch = event.touches?.[0];
    if (!touch) return;
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
    swipeActive = true;
    swipeOffset = 0;
  }

  function handleTouchMove(event) {
    if (!isMobileLayout || !swipeActive) return;
    if (compareMode) return;
    const touch = event.touches?.[0];
    if (!touch) return;
    const deltaX = touch.clientX - touchStartX;
    const deltaY = touch.clientY - touchStartY;
    if (Math.abs(deltaX) < Math.abs(deltaY)) return;
    const width = mobilePanelsEl?.clientWidth || windowWidth || 0;
    const clamped = Math.max(-width, Math.min(width, deltaX));
    swipeOffset = clamped;
  }

  function handleTouchEnd(event) {
    if (!isMobileLayout) return;
    if (compareMode) return;
    const touch = event.changedTouches?.[0];
    if (!touch) return;
    const deltaX = touch.clientX - touchStartX;
    const deltaY = touch.clientY - touchStartY;
    swipeActive = false;
    if (Math.abs(deltaX) < 40 || Math.abs(deltaX) < Math.abs(deltaY)) {
      swipeOffset = 0;
      return;
    }
    if (deltaX < 0) {
      handlePanelSwipe('next');
    } else {
      handlePanelSwipe('prev');
    }
    swipeOffset = 0;
  }

  function applyPickerSelection(item) {
    if (!loadout || !activePicker || !item) return;

    if (activePicker === 'weapon') {
      loadout.Gear.Weapon.Name = item.Name;
      loadout.Gear.Weapon.Amplifier = null;
      loadout.Gear.Weapon.Scope = null;
      loadout.Gear.Weapon.Sight = null;
      loadout.Gear.Weapon.Absorber = null;
      loadout.Gear.Weapon.Matrix = null;
      loadout.Gear.Weapon.Implant = null;
    } else if (activePicker === 'amplifier') {
      loadout.Gear.Weapon.Amplifier = { Name: item.Name };
    } else if (activePicker === 'absorber') {
      loadout.Gear.Weapon.Absorber = { Name: item.Name };
    } else if (activePicker === 'scope') {
      loadout.Gear.Weapon.Scope = { Name: item.Name };
    } else if (activePicker === 'scope-sight') {
      if (!loadout.Gear.Weapon.Scope) {
        loadout.Gear.Weapon.Scope = { Name: null, Sight: null };
      }
      loadout.Gear.Weapon.Scope.Sight = { Name: item.Name };
    } else if (activePicker === 'sight') {
      loadout.Gear.Weapon.Sight = { Name: item.Name };
    } else if (activePicker === 'matrix') {
      loadout.Gear.Weapon.Matrix = { Name: item.Name };
    } else if (activePicker === 'implant') {
      loadout.Gear.Weapon.Implant = { Name: item.Name };
    } else if (activePicker === 'armorset') {
      const armorSet = getArmorSet(item.Name);
      if (armorSet) {
        loadout.Gear.Armor.SetName = armorSet.Name;
        armorSlots.forEach(slot => {
          loadout.Gear.Armor[slot] = {
            Name: armorSet.Armors.flat().find(x => slot === x.Properties.Slot)?.Name,
            Plate: loadout.Gear.Armor[slot].Plate
          };
        });
      }
    } else if (activePicker.startsWith('armor-')) {
      const slot = activePicker.split('-')[1];
      loadout.Gear.Armor[slot] = { Name: item.Name, Plate: loadout.Gear.Armor[slot].Plate };
    } else if (activePicker.startsWith('armorplating')) {
      if (loadout.Gear.Armor.ManageIndividual) {
        const slot = activePicker.split('-')[1];
        if (!slot || loadout.Gear.Armor[slot].Name == null) {
          return;
        }
        loadout.Gear.Armor[slot].Plate = { Name: item.Name };
      } else {
        loadout.Gear.Armor.PlateName = item.Name;
        armorSlots.forEach(slot => {
          if (loadout.Gear.Armor[slot].Name == null) return;
          loadout.Gear.Armor[slot].Plate = { Name: item.Name };
        });
      }
    } else if (activePicker === 'pet') {
      loadout.Gear.Pet = { Name: item.Name, Effect: null };
    } else if (activePicker === 'ring-left') {
      setClothingSlot('Ring', 'Left', item.Name);
    } else if (activePicker === 'ring-right') {
      setClothingSlot('Ring', 'Right', item.Name);
    } else if (activePicker === 'consumable') {
      addConsumableItem(item);
      return;
    } else if (activePicker === 'clothing') {
      addClothingItem(item);
    } else if (activePicker.startsWith('clothing-')) {
      const slotName = activePicker.replace('clothing-', '');
      setClothingSlot(slotName, null, item.Name);
    }

  }

  function handlePickerRowClick(event) {
    if (!loadout || !activePicker) return;
    const row = event?.detail?.row;
    const item = row?._item;
    if (!item) return;
    pickerPreviewRow = row;
    pickerPreviewItem = item;
    showPickerPreview = true;
  }

  function confirmPickerSelection() {
    if (!pickerPreviewItem) return;
    applyPickerSelection(pickerPreviewItem);
    touchLoadouts();
    markDirty();
    closePicker();
  }

  function returnToPickerList() {
    showPickerPreview = false;
    pickerPreviewRow = null;
    pickerPreviewItem = null;
  }

  function openImportSourceDialog() {
    showImportSourceDialog = true;
  }

  function handleImportFromFile() {
    showImportSourceDialog = false;
    importLoadoutFile();
  }

  function handleImportLocal() {
    showImportSourceDialog = false;
    showImportDialog = true;
  }

  function openShareDialog() {
    if (activeSource !== 'online' || !loadout) return;
    const record = onlineLoadouts.find(r => r.data === loadout);
    sharePublic = record?.public || false;
    shareLink = record?.share_code && typeof window !== 'undefined'
      ? `${window.location.origin}/tools/loadouts/${record.share_code}`
      : '';
    shareCopyStatus = '';
    if (shareCopyTimeout) {
      clearTimeout(shareCopyTimeout);
      shareCopyTimeout = null;
    }
    showShareDialog = true;
  }

  async function handleShareToggle(event) {
    sharePublic = !!event?.target?.checked;
    if (activeSource !== 'online' || !loadout || !activeOnlineId) return;
    await handleSave();
  }

  function applyShareSettings() {
    showShareDialog = false;
    shareCopyStatus = '';
    if (shareCopyTimeout) {
      clearTimeout(shareCopyTimeout);
      shareCopyTimeout = null;
    }
  }

  async function handleCopyShareLink() {
    if (!shareLink) return;
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(shareLink);
      } else {
        const input = document.createElement('textarea');
        input.value = shareLink;
        input.setAttribute('readonly', 'true');
        input.style.position = 'absolute';
        input.style.left = '-9999px';
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
      }
      shareCopyStatus = 'Copied';
    } catch (err) {
      console.error('Failed to copy share link', err);
      shareCopyStatus = 'Copy failed';
    }

    if (shareCopyTimeout) clearTimeout(shareCopyTimeout);
    shareCopyTimeout = setTimeout(() => {
      shareCopyStatus = '';
      shareCopyTimeout = null;
    }, 1500);
  }

  async function importLocalLoadouts() {
    if (!isLoggedIn || importInProgress) return;
    importInProgress = true;
    importError = null;
    importSuccess = false;
    try {
      const candidates = [...localLoadouts];
      if (candidates.length === 0) {
        importInProgress = false;
        return;
      }
      const batches = [];
      let currentBatch = [];
      const encoder = new TextEncoder();
      const maxPayloadSize = 20000;
      const basePayloadSize = encoder.encode(JSON.stringify({ loadouts: [] })).length;
      let currentSize = basePayloadSize;
      for (const item of candidates) {
        const payload = JSON.stringify(item);
        const itemSize = encoder.encode(payload).length;
        if (itemSize + basePayloadSize > maxPayloadSize) {
          continue;
        }
        const nextSize = currentSize + itemSize + (currentBatch.length > 0 ? 1 : 0);
        if (nextSize > maxPayloadSize && currentBatch.length > 0) {
          batches.push(currentBatch);
          currentBatch = [item];
          currentSize = basePayloadSize + itemSize;
          continue;
        }
        currentBatch.push(item);
        currentSize = nextSize;
      }
      if (currentBatch.length > 0) batches.push(currentBatch);

      for (const batch of batches) {
        const response = await fetch('/api/tools/loadout/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ loadouts: batch })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result?.error || 'Failed to import loadouts');
        }
      }

      localLoadouts = [];
      writeLocalLoadouts(localLoadouts);
      importSuccess = true;
      await fetchOnlineLoadouts();
      if (activeSource === 'online' && onlineLoadouts.length > 0) {
        await setActiveLoadout(onlineLoadouts[0].data);
      }
    } catch (err) {
      console.error('Import failed:', err);
      importError = err.message;
    } finally {
      importInProgress = false;
    }
  }

  function handleBeforeUnload(event) {
    if (activeSource === 'online' && isDirty && activeOnlineId && loadout) {
      // Try to save via sendBeacon (fire-and-forget for browser close/refresh)
      const payload = JSON.stringify({
        name: loadout.Name || 'New Loadout',
        data: loadout,
        public: sharePublic || false
      });
      navigator.sendBeacon(`/api/tools/loadout/${activeOnlineId}`, new Blob([payload], { type: 'application/json' }));
    }
  }

  // Auto-save when navigating away within the app
  beforeNavigate(async ({ to, cancel }) => {
    if (activeSource === 'online' && isDirty && activeOnlineId && loadout && !isSaving && !isNavigationSave) {
      // Save immediately before navigation
      cancel();
      isNavigationSave = true;
      try {
        await handleSave();
      } finally {
        // Continue navigation after save completes (whether it succeeded or failed)
        if (to?.url) {
          const { goto } = await import('$app/navigation');
          goto(to.url.pathname + to.url.search + to.url.hash);
        }
      }
    }
  });

  onMount(async () => {
    if (browser) {
      windowWidth = window.innerWidth;
      hasMeasuredLayout = true;
    }

    // Loadout initialization is now handled by the reactive statement
    // that watches isSharedMode and loadoutsInitialized

    // Lazy load entity data (needed for both modes)
    entitiesLoading = true;
    try {
      const entities = await loadLoadoutEntities();
      processEntityData(entities);
    } catch (error) {
      console.error('Failed to load entity data:', error);
    } finally {
      entitiesLoading = false;
    }

    try {
      const response = await fetch(`${getApiBase()}/effects`);
      if (response.ok) {
        effectsCatalog = await response.json();
        effectCaps = buildEffectCaps(effectsCatalog);
      }
    } catch (error) {
      console.error('Failed to load effects catalog:', error);
    }

    if (!isSharedMode && typeof window !== 'undefined') {
      window.addEventListener('beforeunload', handleBeforeUnload);
      window.addEventListener('click', handleCompareGlobalClick);
    }
  });

  onDestroy(() => {
    if (autosaveTimeout) clearTimeout(autosaveTimeout);
    clearAutosaveTicker();
    if (typeof window !== 'undefined') {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      window.removeEventListener('click', handleCompareGlobalClick);
    }
  });

  $: if (activeSource === 'local') {
    writeLocalLoadouts(localLoadouts);
  }

  $: autosaveSeconds = autosaveDueAt ? Math.max(0, Math.ceil((autosaveDueAt - autosaveNow) / 1000)) : null;

  $: activeLoadoutKey = activeSource === 'online' ? activeOnlineId : loadout?.Id;
  $: activeRecord = activeSource === 'online'
    ? onlineLoadouts.find(r => r.id === activeOnlineId)
    : null;
  $: isPublicLoadout = !!activeRecord?.public;
  $: pickerConfig = activePicker ? (isMobileLayout, getPickerConfig(activePicker)) : null;
  $: pickerRowHeight = isMobileLayout ? 30 : 34;

  function getLoadoutListLabel(item) {
    if (!item) return 'Untitled';
    if (item.Name && item.Name !== 'New Loadout') return item.Name;
    const weaponName = item.Gear?.Weapon?.Name;
    const armorName = item.Gear?.Armor?.SetName;
    if (weaponName && armorName) return `${weaponName} (${armorName})`;
    if (weaponName) return weaponName;
    return item.Name || 'New Loadout';
  }

  function handleNewLoadout() {
    if (activeSource === 'online') {
      createOnlineLoadout();
    } else {
      createLocalLoadout();
    }
  }

  function handleManualSave() {
    if (activeSource !== 'online') return;
    if (!isDirty) return;
    handleSave();
  }

  async function switchSource(source) {
    if (source === activeSource) return;
    if (source === 'online') {
      if (!isLoggedIn) return;
      if (!onlineLoadouts.length) {
        await fetchOnlineLoadouts();
      }
    }
    setActiveSource(source);
  }

  $: sidebarLoadouts = activeSource === 'online'
    ? onlineLoadouts.map(record => ({ id: record.id, data: record.data }))
    : localLoadouts.map(item => ({ id: item.Id, data: item }));

  $: if (activeSource === 'online') {
    loadouts = onlineLoadouts.map(r => r.data);
  } else {
    loadouts = localLoadouts;
  }

  $: filteredLoadouts = sidebarLoadouts.filter(item => {
    const name = getLoadoutListLabel(item.data).toLowerCase();
    const query = loadoutSearch.trim().toLowerCase();
    return !query || name.includes(query);
  });

  $: if(loadout?.Gear.Weapon.Enhancers) {
    loadout.Gear.Weapon.Enhancers.Damage = clamp(loadout.Gear.Weapon.Enhancers.Damage, 0, 10);
    loadout.Gear.Weapon.Enhancers.Accuracy = clamp(loadout.Gear.Weapon.Enhancers.Accuracy, 0, 10);
    loadout.Gear.Weapon.Enhancers.Range = clamp(loadout.Gear.Weapon.Enhancers.Range, 0, 10);
    loadout.Gear.Weapon.Enhancers.Economy = clamp(loadout.Gear.Weapon.Enhancers.Economy, 0, 10);
    loadout.Gear.Weapon.Enhancers.SkillMod = clamp(loadout.Gear.Weapon.Enhancers.SkillMod, 0, 10);
  }

  $: if(loadout?.Gear.Armor.Enhancers) {
    loadout.Gear.Armor.Enhancers.Defense = clamp(loadout.Gear.Armor.Enhancers.Defense, 0, 10);
    loadout.Gear.Armor.Enhancers.Durability = clamp(loadout.Gear.Armor.Enhancers.Durability, 0, 10);
  }

  $: if (loadout && loadout.Markup == null) {
    resetMarkup();
  }
  $: if (loadout?.Markup) {
    if (loadout.Markup.ArmorSet == null) loadout.Markup.ArmorSet = 100;
    if (loadout.Markup.PlateSet == null) loadout.Markup.PlateSet = 100;
    if (!loadout.Markup.Armors) loadout.Markup.Armors = {};
    if (!loadout.Markup.Plates) loadout.Markup.Plates = {};
    armorSlots.forEach(slot => {
      if (loadout.Markup.Armors[slot] == null) loadout.Markup.Armors[slot] = 100;
      if (loadout.Markup.Plates[slot] == null) loadout.Markup.Plates[slot] = 100;
    });
  }

  function resetMarkup() {
    loadout.Markup = {
      Weapon: 100,
      Ammo: 100,
      Amplifier: 100,
      Absorber: 100,
      Scope: 100,
      Sight: 100,
      ScopeSight: 100,
      Matrix: 100,
      Implant: 100,
      ArmorSet: 100,
      PlateSet: 100,
      Armors: {
        Head: 100,
        Torso: 100,
        Arms: 100,
        Hands: 100,
        Legs: 100,
        Shins: 100,
        Feet: 100,
      },
      Plates: {
        Head: 100,
        Torso: 100,
        Arms: 100,
        Hands: 100,
        Legs: 100,
        Shins: 100,
        Feet: 100,
      },
    };
    touchLoadouts();
    markDirty();
  }

  $: if (loadout?.Gear?.Armor?.ManageIndividual === false && loadout?.Gear?.Armor?.SetName === null) {
    resetArmor();
  } else if (loadout?.Gear?.Armor?.ManageIndividual === true) {
    loadout.Gear.Armor.SetName = null;
    loadout.Gear.Armor.PlateName = null;
  }


  function getWeapon(name) {
    return weapons.find(x => x.Name === name);
  }

  function getAmplifier(name) {
    return amplifiers.find(x => x.Name === name);
  }

  function getAbsorber(name) {
    return absorbers.find(x => x.Name === name);
  }

  function getScope(name) {
    return scopes.find(x => x.Name === name);
  }

  function getSight(name) {
    return sights.find(x => x.Name === name);
  }

  function getMatrix(name) {
    return matrices.find(x => x.Name === name);
  }

  function getImplant(name) {
    return implants.find(x => x.Name === name);
  }

  function getArmorSet(name) {
    return armorsets.find(x => x.Name === name);
  }

  function getArmor(name) {
    return armors.find(x => x.Name === name);
  }

  function getArmorSetLabel(loadoutArg) {
    if (!loadoutArg?.Gear?.Armor) return '-';
    const armorGear = loadoutArg.Gear.Armor;
    const setName = armorGear.SetName || null;
    const equippedArmors = armorSlots
      .map(slot => getArmor(armorGear?.[slot]?.Name))
      .filter(Boolean);
    const uniqueSetNames = [...new Set(equippedArmors.map(item => item?.Set?.Name).filter(Boolean))];

    if (uniqueSetNames.length > 1) return 'Mixed';
    if (uniqueSetNames.length === 1) return uniqueSetNames[0];
    if (setName) return setName;
    return '-';
  }

  function getArmorPlating(name) {
    return armorplatings.find(x => x.Name === name);
  }

  function getAttachmentCount() {
    let weapon = getWeapon();

    return 3 + (weapon?.Properties?.Class === 'Ranged'
      ? 2
      : weapon?.Properties?.Class === 'Melee'
      ? 1
      : weapon?.Properties?.Class === 'Mindforce'
      ? 1
      : 0);
  }

  function getClothingSlot(slotName, side = null) {
    const list = loadout?.Gear?.Clothing || [];
    if (isRingSlot(slotName)) {
      return list.find(item =>
        isRingSlot(item?.Slot)
        && (side ? item?.Side === side : !item?.Side)
      );
    }
    return list.find(item => item?.Slot === slotName && (side ? item?.Side === side : !item?.Side));
  }

  // Version that takes loadout data as parameter for shared mode
  function getClothingSlotFromData(loadoutData, slotName, side = null) {
    const list = loadoutData?.Gear?.Clothing || [];
    if (isRingSlot(slotName)) {
      return list.find(item =>
        isRingSlot(item?.Slot)
        && (side ? item?.Side === side : !item?.Side)
      );
    }
    return list.find(item => item?.Slot === slotName && (side ? item?.Side === side : !item?.Side));
  }

  function getClothingItem(name) {
    return clothing.find(item => item.Name === name);
  }

  function getClothingWikiLink(name) {
    return `/items/clothing/${encodeURIComponentSafe(name)}`;
  }

  function formatEffectCount(count) {
    if (!count) return '-';
    return count === 1 ? '1 effect' : `${count} effects`;
  }

  function getClothingItemSlot(item) {
    return item?.Properties?.Slot || item?.Slot || 'Unknown';
  }

  function hasClothingEffects(item) {
    const effectsCount = item?.EffectsOnEquip?.length
      || item?.Effects?.length
      || item?.Properties?.Effects?.length
      || item?.Properties?.EffectsOnEquip?.length
      || 0;
    const setEffectsCount = item?.Set?.EffectsOnSetEquip?.length
      || item?.EffectsOnSetEquip?.length
      || item?.SetEffects?.length
      || item?.Properties?.SetEffects?.length
      || item?.Properties?.Set?.EffectsOnSetEquip?.length
      || 0;
    return effectsCount > 0 || setEffectsCount > 0;
  }

  function getClothingEffectCount(item) {
    const equipCount = item?.EffectsOnEquip?.length
      || item?.Effects?.length
      || item?.Properties?.Effects?.length
      || item?.Properties?.EffectsOnEquip?.length
      || 0;
    const setCount = item?.Set?.EffectsOnSetEquip?.length
      || item?.EffectsOnSetEquip?.length
      || item?.SetEffects?.length
      || item?.Properties?.SetEffects?.length
      || item?.Properties?.Set?.EffectsOnSetEquip?.length
      || 0;
    return (equipCount || 0) + (setCount || 0);
  }

  function getClothingEffectLabel(item) {
    const count = getClothingEffectCount(item);
    return count > 0 ? `${count} effects` : '-';
  }

  function addClothingItem(item) {
    if (!loadout?.Gear || !item) return;
    const slotName = getClothingItemSlot(item);
    if (isRingSlot(slotName)) return;
    const list = [...(loadout.Gear.Clothing || [])];
    // For items with a defined slot (not Unknown), replace existing items in that slot
    // For Unknown slot items, allow duplicates (unlimited)
    if (slotName && slotName !== 'Unknown') {
      const existingIndex = list.findIndex(entry => !isRingSlot(entry?.Slot) && entry?.Slot === slotName);
      if (existingIndex >= 0) {
        const replaced = list[existingIndex];
        list.splice(existingIndex, 1);
        clothingReplaceNotice = `Replaced ${replaced?.Name || 'item'} in ${slotName}.`;
      } else {
        clothingReplaceNotice = '';
      }
    } else {
      clothingReplaceNotice = '';
    }
    list.push({ Slot: slotName, Name: item.Name });
    loadout.Gear.Clothing = list;
    touchLoadouts();
    markDirty();
  }

  function removeClothingItem(name, slotName) {
    if (!loadout?.Gear) return;
    const list = [...(loadout.Gear.Clothing || [])];
    loadout.Gear.Clothing = list.filter(entry => !(entry?.Name === name && entry?.Slot === slotName));
    touchLoadouts();
    markDirty();
  }

  function getConsumableItem(name) {
    return stimulants.find(item => item.Name === name);
  }

  function hasConsumableEffects(item) {
    return (item?.EffectsOnConsume?.length || 0) > 0;
  }

  function getConsumableEffectCount(item) {
    return item?.EffectsOnConsume?.length || 0;
  }

  function addConsumableItem(item) {
    if (!loadout?.Gear || !item) return;
    const list = [...(loadout.Gear.Consumables || [])];
    if (!list.find(entry => entry?.Name === item.Name)) {
      list.push({ Name: item.Name });
      loadout.Gear.Consumables = list;
      touchLoadouts();
      markDirty();
    }
  }

  function removeConsumableItem(name) {
    if (!loadout?.Gear) return;
    const list = [...(loadout.Gear.Consumables || [])];
    loadout.Gear.Consumables = list.filter(entry => entry?.Name !== name);
    touchLoadouts();
    markDirty();
  }

  function getPetEffectStrength(effect) {
    return effect?.Properties?.Strength ?? effect?.Values?.Strength ?? effect?.Values?.Value ?? 0;
  }

  function formatSigned(value, unit = '%') {
    if (value == null || Number.isNaN(value)) return 'N/A';
    const sign = value > 0 ? '+' : value < 0 ? '' : '';
    return `${sign}${value.toFixed(2)}${unit}`;
  }

  function formatSignedNoPlus(value, unit = '%') {
    if (value == null || Number.isNaN(value)) return 'N/A';
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 'N/A';
    const sign = numeric < 0 ? '-' : '';
    return `${sign}${Math.abs(numeric).toFixed(2)}${unit}`;
  }

  function formatMagnitude(value, unit = '%') {
    if (value == null || Number.isNaN(value)) return 'N/A';
    return `${Math.abs(value).toFixed(2)}${unit}`;
  }

  function formatCapLimit(limit, unit, polarity) {
    if (limit == null || Number.isNaN(limit)) return 'N/A';
    const numeric = Number(limit);
    if (!Number.isFinite(numeric)) return 'N/A';
    const sign = polarity === 'negative' ? '-' : '';
    return `${sign}${Math.abs(numeric).toFixed(2)}${unit}`;
  }

  function togglePetEffect(effectKey) {
    if (!loadout?.Gear?.Pet) return;
    loadout.Gear.Pet.Effect = loadout.Gear.Pet.Effect === effectKey ? null : effectKey;
    touchLoadouts();
    markDirty();
  }

  function setClothingSlot(slotName, side, name) {
    if (!loadout?.Gear) return;
    const list = [...(loadout.Gear.Clothing || [])];
    const isRing = isRingSlot(slotName);
    const matchesSlot = (item) => {
      const slotMatches = isRing ? isRingSlot(item?.Slot) : item?.Slot === slotName;
      const sideMatches = side ? item?.Side === side : !item?.Side;
      return slotMatches && sideMatches;
    };
    const nextList = list.filter(item => !matchesSlot(item));
    if (!name) {
      loadout = {
        ...loadout,
        Gear: {
          ...loadout.Gear,
          Clothing: nextList
        }
      };
      touchLoadouts();
      markDirty();
      return;
    }
    const entry = { Slot: isRing ? 'Ring' : slotName, Name: name };
    if (side) entry.Side = side;
    nextList.push(entry);
    loadout = {
      ...loadout,
      Gear: {
        ...loadout.Gear,
        Clothing: nextList
      }
    };
    touchLoadouts();
    markDirty();
  }

  function clamp(value, min, max) {
    return LoadoutCalc.clamp(value, min, max);
  }

  function enforceEnhancerCap(group, key, value) {
    if (!loadout?.Gear) return;
    const target = group === 'weapon'
      ? loadout.Gear.Weapon?.Enhancers
      : loadout.Gear.Armor?.Enhancers;
    if (!target) return;
    const parsed = Number(value);
    const nextValue = Number.isFinite(parsed) ? Math.max(0, Math.min(10, parsed)) : 0;
    target[key] = nextValue;
    const total = Object.values(target).reduce((sum, val) => sum + (Number(val) || 0), 0);
    if (total > 10) {
      const excess = total - 10;
      target[key] = Math.max(0, (Number(target[key]) || 0) - excess);
    }
  }

  function resetArmor() {
    const newArmorObject = () => ({
      Name: null,
      Plate: null
    });

    loadout.Gear.Armor.SetName = null;
    loadout.Gear.Armor.PlateName = null;

    armorSlots.forEach(slot => {
      loadout.Gear.Armor[slot] = newArmorObject();
    });

    touchLoadouts();
    markDirty();
  }

  function clearSlot(e, slot) {
    e.preventDefault();

    if (slot === 'weapon') {
      loadout.Gear.Weapon.Name = null;
      loadout.Gear.Weapon.Amplifier = null;
      loadout.Gear.Weapon.Scope = null;
      loadout.Gear.Weapon.Sight = null;
      loadout.Gear.Weapon.Absorber = null;
      loadout.Gear.Weapon.Matrix = null;
      loadout.Gear.Weapon.Implant = null;
    } else if (slot === 'amplifier') {
      loadout.Gear.Weapon.Amplifier = null;
    } else if (slot === 'scope') {
      loadout.Gear.Weapon.Scope = null;
    } else if (slot === 'sight') {
      loadout.Gear.Weapon.Sight = null;
    } else if (slot === 'absorber') {
      loadout.Gear.Weapon.Absorber = null;
    } else if (slot === 'matrix') {
      loadout.Gear.Weapon.Matrix = null;
    } else if (slot === 'implant') {
      loadout.Gear.Weapon.Implant = null;
    } else if (slot === 'scope-sight') {
      loadout.Gear.Weapon.Scope.Sight = null;
    } else if (slot.startsWith('armor-')) {
      loadout.Gear.Armor[slot.split('-')[1]].Name = null;
      loadout.Gear.Armor[slot.split('-')[1]].Plate = null;
    } else if (slot.startsWith('armorplating-')) {
      loadout.Gear.Armor[slot.split('-')[1]].Plate = null;
    } else if (slot === 'armorplating') {
      loadout.Gear.Armor.PlateName = null;

      armorSlots.forEach(slot => {
        loadout.Gear.Armor[slot].Plate = null;
      });
    } else if (slot === 'armorset') {
      resetArmor();
      return;
    } else if (slot === 'pet') {
      loadout.Gear.Pet = { Name: null, Effect: null };
    } else if (slot === 'ring-left') {
      setClothingSlot('Ring', 'Left', null);
    } else if (slot === 'ring-right') {
      setClothingSlot('Ring', 'Right', null);
    } else if (slot.startsWith('clothing-')) {
      const slotName = slot.replace('clothing-', '');
      setClothingSlot(slotName, null, null);
    }

    touchLoadouts();
    markDirty();
  }

  function comparePickerValue(loadout, getter, setter, newObject, selectValue) {
    const loadoutCopy = JSON.parse(JSON.stringify(loadout));

    const currentEval = evaluateAnyLoadout(loadoutCopy);
    const currentValue = selectValue?.(currentEval);
    if (currentValue == null) return null;

    const currentObject = getter(loadoutCopy);
    setter(loadoutCopy, newObject);

    const newEval = evaluateAnyLoadout(loadoutCopy);
    const newValue = selectValue?.(newEval);
    if (newValue == null) return null;

    // Restore the original object in case callers reuse the clone later.
    setter(loadoutCopy, currentObject);

    const difference = newValue - currentValue;

    return difference > 0
      ? `<span style='color: ${$darkMode ? 'lightgreen' : 'darkgreen'};'>+${difference.toFixed(2)}</span>`
      : difference < 0
      ? `<span style='color: ${$darkMode ? '#FF5555' : 'darkred'};'>${difference.toFixed(2)}</span>`
      : difference.toFixed(2);
  }

  function compareEfficiency(loadout, getter, setter, object) {
    return comparePickerValue(loadout, getter, setter, object, (e) => e?.stats?.efficiency);
  }

  function compareDpp(loadout, getter, setter, object) {
    return comparePickerValue(loadout, getter, setter, object, (e) => e?.stats?.dpp);
  }

  function compareDps(loadout, getter, setter, object) {
    return comparePickerValue(loadout, getter, setter, object, (e) => e?.stats?.dps);
  }

  function buildPickerRows(items, mapper) {
    return (items || []).map(item => ({
      ...mapper(item),
      _item: item
    }));
  }

  function getFilteredAmplifiers() {
    const weapon = getWeapon(loadout?.Gear?.Weapon?.Name);
    if (!weapon) return [];
    return amplifiers.filter(x => {
      const ampDamage = LoadoutCalc.calculateItemTotalDamage(x);
      const weaponDamage = LoadoutCalc.calculateItemTotalDamage(weapon);

      if (!ampDamage) {
        return false;
      }

      if (2 * ampDamage > (1 + ((settings.overampCap ?? 0) / 100)) * weaponDamage && settings.onlyShowReasonableAmplifiers) {
        return false;
      }

      if (weapon.Properties.Class === 'Ranged') {
        return weapon.Properties.Type === 'BLP'
          ? x.Properties.Type === 'BLP'
          : x.Properties.Type === 'Energy';
      }

      if (weapon.Properties.Class === 'Melee') {
        return x.Properties.Type === 'Melee';
      }

      if (weapon.Properties.Class === 'Mindforce') {
        return x.Properties.Type === 'Mindforce';
      }

      return false;
    });
  }

  function getFilteredImplants() {
    const weapon = getWeapon(loadout?.Gear?.Weapon?.Name);
    return implants.filter(x => {
      return x.Properties.MaxProfessionLevel == null || (
        weapon?.Properties?.Skill?.Hit?.LearningIntervalStart <= x.Properties.MaxProfessionLevel
        && weapon?.Properties?.Skill?.Dmg?.LearningIntervalStart <= x.Properties.MaxProfessionLevel
      );
    });
  }

  function getPickerItemLink(kind, item) {
    if (!item?.Name) return null;
    const slug = encodeURIComponentSafe(item.Name);

    if (kind === 'weapon') return `/items/weapons/${slug}`;
    if (kind === 'pet') return `/items/pets/${slug}`;
    if (kind === 'consumable') return `/items/consumables/${slug}`;
    if (kind === 'armorset') return `/items/armorsets/${slug}`;
    if (kind?.startsWith('armor-')) return `/items/armors/${slug}`;
    if (kind?.startsWith('armorplating')) return `/items/attachments/armorplatings/${slug}`;
    if (kind === 'amplifier' || kind === 'matrix') return `/items/attachments/weaponamplifiers/${slug}`;
    if (kind === 'absorber') return `/items/attachments/absorbers/${slug}`;
    if (kind === 'scope' || kind === 'sight' || kind === 'scope-sight') return `/items/attachments/weaponvisionattachments/${slug}`;
    if (kind === 'implant') return `/items/attachments/mindforceimplants/${slug}`;
    if (kind === 'clothing' || kind?.startsWith('clothing-') || kind === 'ring-left' || kind === 'ring-right') {
      return `/items/clothing/${slug}`;
    }

    return null;
  }

  function getPickerMobileKeys() {
    return ['name'];
  }

  function finalizePickerColumns(kind, columns) {
    const mobileKeys = getPickerMobileKeys(kind);
    let finalized = columns;

    if (isMobileLayout) {
      finalized = columns.filter(column => mobileKeys.includes(column.key));
    } else {
      finalized = columns.map(column => ({
        ...column,
        hideOnMobile: column.hideOnMobile || !mobileKeys.includes(column.key)
      }));
    }

    if (!isMobileLayout) {
      finalized = [
        ...finalized,
        {
          key: 'link',
          header: '',
          width: '42px',
          sortable: false,
          searchable: false,
          formatter: (_value, row) => {
            const href = getPickerItemLink(kind, row?._item);
            if (!href) return '';
            return `<a class="picker-link-btn" href="${href}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()" aria-label="Open item in new tab"><svg class="picker-link-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-external"></use></svg></a>`;
          }
        }
      ];
    }

    return finalized;
  }

  function getPickerConfig(kind) {
    if (!kind) return null;

    if (kind === 'weapon') {
      return {
        title: 'Select Weapon',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'class', header: 'Class', width: '90px' },
          { key: 'type', header: 'Type', width: '90px' },
          { key: 'dps', header: 'DPS', width: '70px' },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(weapons, item => ({
          name: item.Name,
          class: item.Properties.Class,
          type: item.Properties.Type,
          dps: LoadoutCalc.calculateItemDpsPreview(item) != null ? LoadoutCalc.calculateItemDpsPreview(item).toFixed(2) : 'N/A',
          dpp: LoadoutCalc.calculateItemDppPreview(item) != null ? LoadoutCalc.calculateItemDppPreview(item).toFixed(2) : 'N/A',
          efficiency: item.Properties?.Economy?.Efficiency != null ? `${item.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A'
        }))
      };
    }

    if (kind === 'amplifier') {
      return {
        title: 'Select Amplifier',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'damage', header: 'Damage', width: '80px' },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(getFilteredAmplifiers(), item => ({
          name: item.Name,
          damage: compareDps(loadout, x => x.Gear.Weapon.Amplifier, (x, v) => x.Gear.Weapon.Amplifier = v, item) ?? 'N/A',
          dpp: compareDpp(loadout, x => x.Gear.Weapon.Amplifier, (x, v) => x.Gear.Weapon.Amplifier = v, item) ?? 'N/A',
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Amplifier, (x, v) => x.Gear.Weapon.Amplifier = v, item) ?? 'N/A'
        }))
      };
    }

    if (kind === 'absorber') {
      const weapon = getWeapon(loadout?.Gear?.Weapon?.Name);
      return {
        title: 'Select Absorber',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'efficiency', header: 'Efficiency', width: '90px' },
          { key: 'decay', header: 'Decay', width: '90px' },
          { key: 'uses', header: 'Uses', width: '80px' }
        ]),
        rows: buildPickerRows(absorbers, item => ({
          name: item.Name,
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Absorber, (x, v) => x.Gear.Weapon.Absorber = v, item) ?? 'N/A',
          decay: item.Properties?.Economy?.Absorption != null && weapon?.Properties?.Economy?.Decay != null
            ? `${(weapon.Properties.Economy.Decay * item.Properties.Economy.Absorption).toFixed(4)} PEC`
            : 'N/A',
          uses: weapon ? (LoadoutCalc.calculateAbsorberTotalUses(item, weapon) ?? 'N/A') : 'N/A'
        }))
      };
    }

    if (kind === 'scope') {
      return {
        title: 'Select Scope',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(scopes, item => ({
          name: item.Name,
          dpp: compareDpp(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, item) ?? 'N/A',
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, item) ?? 'N/A'
        }))
      };
    }

    if (kind === 'scope-sight') {
      return {
        title: 'Select Scope Sight',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(sights, item => ({
          name: item.Name,
          dpp: compareDpp(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, item) ?? 'N/A',
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, item) ?? 'N/A'
        }))
      };
    }

    if (kind === 'sight') {
      return {
        title: 'Select Sight',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(sights, item => ({
          name: item.Name,
          dpp: compareDpp(loadout, x => x.Gear.Weapon.Sight, (x, v) => x.Gear.Weapon.Sight = v, item) ?? 'N/A',
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Sight, (x, v) => x.Gear.Weapon.Sight = v, item) ?? 'N/A'
        }))
      };
    }

    if (kind === 'matrix') {
      return {
        title: 'Select Matrix',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'dps', header: 'DPS', width: '70px' },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(matrices, item => ({
          name: item.Name,
          dps: compareDps(loadout, x => x.Gear.Weapon.Matrix, (x, v) => x.Gear.Weapon.Matrix = v, item) ?? 'N/A',
          dpp: compareDpp(loadout, x => x.Gear.Weapon.Matrix, (x, v) => x.Gear.Weapon.Matrix = v, item) ?? 'N/A',
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Matrix, (x, v) => x.Gear.Weapon.Matrix = v, item) ?? 'N/A'
        }))
      };
    }

    if (kind === 'implant') {
      const weapon = getWeapon(loadout?.Gear?.Weapon?.Name);
      return {
        title: 'Select Implant',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'efficiency', header: 'Efficiency', width: '90px' },
          { key: 'decay', header: 'Decay', width: '90px' },
          { key: 'uses', header: 'Uses', width: '80px' }
        ]),
        rows: buildPickerRows(getFilteredImplants(), item => ({
          name: item.Name,
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Implant, (x, v) => x.Gear.Weapon.Implant = v, item) ?? 'N/A',
          decay: item.Properties?.Economy?.Absorption != null && weapon?.Properties?.Economy?.Decay != null
            ? `${(weapon.Properties.Economy.Decay * item.Properties.Economy.Absorption).toFixed(4)} PEC`
            : 'N/A',
          uses: weapon ? (LoadoutCalc.calculateAbsorberTotalUses(item, weapon) ?? 'N/A') : 'N/A'
        }))
      };
    }

    if (kind === 'armorset') {
      return {
        title: 'Select Armor Set',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'total', header: 'Total Def', width: '90px' },
          { key: 'durability', header: 'Durability', width: '100px' }
        ]),
        rows: buildPickerRows(armorsets, item => ({
          name: item.Name,
          total: LoadoutCalc.calculateItemTotalDefense(item) ?? 'N/A',
          durability: item.Properties.Economy.Durability ?? 'N/A'
        }))
      };
    }

    if (kind.startsWith('armor-')) {
      const slot = kind.split('-')[1];
      return {
        title: `Select ${slot} Armor`,
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'total', header: 'Total Def', width: '90px' },
          { key: 'durability', header: 'Durability', width: '100px' }
        ]),
        rows: buildPickerRows(armors.filter(x => x.Properties.Slot === slot), item => ({
          name: item.Name,
          total: LoadoutCalc.calculateItemTotalDefense(item) ?? 'N/A',
          durability: item.Properties.Economy.Durability ?? 'N/A'
        }))
      };
    }

    if (kind.startsWith('armorplating')) {
      return {
        title: 'Select Armor Plating',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'total', header: 'Total Def', width: '90px' },
          { key: 'durability', header: 'Durability', width: '100px' }
        ]),
        rows: buildPickerRows(armorplatings, item => ({
          name: item.Name,
          total: LoadoutCalc.calculateItemTotalDefense(item) ?? 'N/A',
          durability: item.Properties.Economy.Durability ?? 'N/A'
        }))
      };
    }

    if (kind === 'pet') {
      return {
        title: 'Select Pet',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'type', header: 'Type', width: '120px' },
          { key: 'level', header: 'Level', width: '70px' }
        ]),
        rows: buildPickerRows(pets, item => ({
          name: item.Name,
          type: item.Properties?.Type ?? 'N/A',
          level: item.Properties?.Level ?? 'N/A'
        }))
      };
    }

    if (kind === 'clothing') {
      const availableClothing = clothing.filter(item => {
        const slotName = getClothingItemSlot(item);
        // Show non-ring clothing items that have effects
        return !isRingSlot(slotName) && hasClothingEffects(item);
      });
      return {
        title: 'Select Clothing',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'slot', header: 'Slot', width: '120px' }
        ]),
        rows: buildPickerRows(availableClothing, item => {
          const slotName = getClothingItemSlot(item);
          return {
            name: item.Name,
            slot: slotName
          };
        })
      };
    }

    if (kind === 'consumable') {
      const availableConsumables = stimulants.filter(item => hasConsumableEffects(item));
      return {
        title: 'Select Consumable',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'type', header: 'Type', width: '140px' },
          { key: 'effects', header: 'Effects', width: '110px' }
        ]),
        rows: buildPickerRows(availableConsumables, item => ({
          name: item.Name,
          type: item.Properties?.Type ?? 'N/A',
          effects: formatEffectCount(getConsumableEffectCount(item))
        }))
      };
    }

    if (kind === 'ring-left' || kind === 'ring-right') {
      const side = kind === 'ring-left' ? 'Left' : 'Right';
      const filteredRings = ringItems.filter(item => getRingSide(getClothingItemSlot(item)) === side);
      return {
        title: 'Select Ring',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'slot', header: 'Slot', width: '120px' },
          { key: 'type', header: 'Type', width: '120px' }
        ]),
        rows: buildPickerRows(filteredRings, item => ({
          name: item.Name,
          slot: item.Properties?.Slot ?? 'N/A',
          type: item.Properties?.Type ?? 'N/A'
        }))
      };
    }

    if (kind.startsWith('clothing-')) {
      const slotName = kind.replace('clothing-', '');
      return {
        title: `Select ${slotName}`,
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'slot', header: 'Slot', width: '120px' },
          { key: 'type', header: 'Type', width: '120px' }
        ]),
        rows: buildPickerRows(clothing.filter(x => x.Properties?.Slot === slotName), item => ({
          name: item.Name,
          slot: item.Properties?.Slot ?? 'N/A',
          type: item.Properties?.Type ?? 'N/A'
        }))
      };
    }

    return null;
  }

  function stripHtml(value) {
    return String(value ?? '')
      .replace(/<[^>]*>/g, '')
      .replace(/&nbsp;/g, ' ')
      .trim();
  }

  function getPickerPreviewTitle(row) {
    if (!row) return '';
    const name = row.name ?? row.Name ?? row._item?.Name;
    return stripHtml(name) || 'Selected Item';
  }

  function formatStatValue(value, suffix = '') {
    if (value == null || value === 'N/A' || Number.isNaN(value)) return 'N/A';
    const numeric = typeof value === 'number';
    let base = value;
    if (numeric) {
      const rounded = Math.abs(value - Math.round(value)) < 0.01;
      base = rounded ? Math.round(value).toString() : value.toFixed(2);
    }
    return `${base}${suffix}`;
  }

  function getEffectUnit(effectName, currentEffect = null) {
    return getEffectUnitFromCatalog(effectsCatalog, effectName, currentEffect);
  }

  function getItemEffectGroups(item) {
    if (!item) return [];
    const groups = [];
    const equip = item.EffectsOnEquip || item.Properties?.EffectsOnEquip || [];
    const use = item.EffectsOnUse || item.Properties?.EffectsOnUse || [];
    const consume = item.EffectsOnConsume || item.Properties?.EffectsOnConsume || [];
    const setEffects = item.EffectsOnSetEquip || item.Set?.EffectsOnSetEquip || item.Properties?.Set?.EffectsOnSetEquip || [];
    const generic = item.Effects || item.Properties?.Effects || [];

    if (equip.length) groups.push({ title: 'Effects on Equip', effects: equip, effectType: 'equip' });
    if (use.length) groups.push({ title: 'Effects on Use', effects: use, effectType: 'use' });
    if (consume.length) groups.push({ title: 'Effects on Consume', effects: consume, effectType: 'consume' });

    // Group set effects by MinSetPieces (like armor sets display)
    if (setEffects.length) {
      const byPieceCount = {};
      for (const effect of setEffects) {
        const pieces = effect.Values?.MinSetPieces || 1;
        if (!byPieceCount[pieces]) byPieceCount[pieces] = [];
        byPieceCount[pieces].push(effect);
      }
      // Sort by piece count and add each group
      const sortedPieceCounts = Object.keys(byPieceCount).map(Number).sort((a, b) => a - b);
      for (const pieces of sortedPieceCounts) {
        groups.push({
          title: `Set Effects (${pieces} Pieces)`,
          effects: byPieceCount[pieces],
          effectType: 'equip'
        });
      }
    }

    if (generic.length) groups.push({ title: 'Effects', effects: generic, effectType: 'equip' });

    return groups;
  }

  function addPreviewRow(rows, label, value, suffix = '') {
    const formatted = formatStatValue(value, suffix);
    if (formatted === 'N/A') return;
    rows.push({ label, value: formatted });
  }

  function addPreviewTextRow(rows, label, value) {
    if (value == null || value === 'N/A' || value === '') return;
    rows.push({ label, value });
  }

  function formatNutrioValue(value, suffix) {
    if (value == null || Number.isNaN(value)) return null;
    return `${(value / 100).toFixed(2)} ${suffix}`;
  }

  function getDefenseBreakdownRows(item) {
    const defense = item?.Properties?.Defense || {};
    const mapping = [
      ['Impact', defense.Impact],
      ['Cut', defense.Cut],
      ['Stab', defense.Stab],
      ['Pen', defense.Penetration],
      ['Shr', defense.Shrapnel],
      ['Burn', defense.Burn],
      ['Cold', defense.Cold],
      ['Acid', defense.Acid],
      ['Elec', defense.Electric]
    ];
    return mapping
      .filter(([, value]) => value != null && value !== 0)
      .map(([label, value]) => ({ label, value: formatStatValue(value) }));
  }

  function getPickerPreviewSections(kind, item, row) {
    const sections = [];
    if (!item) return sections;

    if (kind === 'weapon') {
      const rows = [];
      addPreviewRow(rows, 'Class', item.Properties?.Class);
      addPreviewRow(rows, 'Type', item.Properties?.Type);
      addPreviewRow(rows, 'Total Damage', LoadoutCalc.calculateItemTotalDamage(item));
      addPreviewRow(rows, 'DPS', LoadoutCalc.calculateItemDpsPreview(item));
      addPreviewRow(rows, 'DPP', LoadoutCalc.calculateItemDppPreview(item));
      addPreviewRow(rows, 'Efficiency', item.Properties?.Economy?.Efficiency, '%');
      addPreviewRow(rows, 'Range', item.Properties?.Range, 'm');
      addPreviewRow(rows, 'Uses', LoadoutCalc.calculateItemTotalUses(item));
      sections.push({ title: 'Weapon Stats', rows });
    } else if (kind === 'amplifier' || kind === 'matrix' || kind === 'scope' || kind === 'sight' || kind === 'scope-sight' || kind === 'absorber' || kind === 'implant') {
      const rows = [];
      addPreviewRow(rows, 'Type', item.Properties?.Type);
      if (row?.dpp) addPreviewTextRow(rows, 'DPP (Δ)', stripHtml(row.dpp));
      if (row?.efficiency) addPreviewTextRow(rows, 'Efficiency (Δ)', stripHtml(row.efficiency));
      if (row?.decay) addPreviewTextRow(rows, 'Decay (Δ)', stripHtml(row.decay));
      if (row?.uses) addPreviewTextRow(rows, 'Uses (Δ)', stripHtml(row.uses));
      sections.push({ title: 'Attachment Stats', rows });
    } else if (kind === 'armorset' || kind.startsWith('armor-') || kind.startsWith('armorplating')) {
      const rows = [];
      const defenseRows = getDefenseBreakdownRows(item);
      if (defenseRows.length > 0) {
        sections.push({ title: 'Defense Types', rows: defenseRows });
      }
      addPreviewRow(rows, 'Total Defense', LoadoutCalc.calculateItemTotalDefense(item));
      addPreviewRow(rows, 'Block', item.Properties?.Defense?.Block, '%');
      addPreviewRow(rows, 'Durability', item.Properties?.Economy?.Durability);
      sections.push({ title: 'Armor Stats', rows });
    } else if (kind === 'pet') {
      const rows = [];
      addPreviewRow(rows, 'Type', item.Properties?.Type);
      addPreviewRow(rows, 'Rarity', item.Properties?.Rarity);
      addPreviewRow(rows, 'Training', item.Properties?.TrainingDifficulty);
      addPreviewRow(rows, 'Taming Level', item.Properties?.TamingLevel);
      addPreviewRow(rows, 'Exportable', item.Properties?.ExportableLevel != null ? `Lv ${item.Properties.ExportableLevel}` : null);
      addPreviewTextRow(rows, 'Nutrio Capacity', formatNutrioValue(item.Properties?.NutrioCapacity, 'PED'));
      addPreviewTextRow(rows, 'Nutrio Consumption', formatNutrioValue(item.Properties?.NutrioConsumptionPerHour, 'PED/h'));
      sections.push({ title: 'Pet Stats', rows, compact: true });

      const skills = Array.isArray(item.Effects) ? item.Effects : [];
      const petEffects = skills
        .filter(skill => skill?.Name)
        .map(skill => ({
          Name: skill.Name,
          Values: {
            Strength: skill?.Properties?.Strength ?? skill?.Values?.Strength ?? skill?.Values?.Value ?? 0,
            Unit: getEffectUnit(skill.Name, skill)
          }
        }));

      if (petEffects.length > 0) {
        sections.push({
          title: 'Pet Skills',
          rows: [],
          effectsGroups: [{ title: '', effects: petEffects, effectType: 'equip' }],
          compact: true,
          hideEffectTitle: true
        });
      }
    } else if (kind === 'consumable') {
      const rows = [];
      addPreviewRow(rows, 'Type', item.Properties?.Type);
      addPreviewRow(rows, 'Effects', getConsumableEffectCount(item));
      sections.push({ title: 'Consumable Stats', rows });
    } else if (kind === 'clothing' || kind === 'ring-left' || kind === 'ring-right' || kind?.startsWith('clothing-')) {
      const rows = [];
      addPreviewRow(rows, 'Slot', getClothingItemSlot(item));
      addPreviewRow(rows, 'Type', item.Properties?.Type);
      // Show set name if item belongs to a set
      const setName = item.Set?.Name;
      if (setName) {
        addPreviewRow(rows, 'Set', setName);
      }
      sections.push({ title: 'Clothing Stats', rows });
    }

    if (kind !== 'pet') {
      const effectGroups = getItemEffectGroups(item);
      if (effectGroups.length > 0) {
        sections.push({ title: 'Effects', rows: [], effectsGroups: effectGroups });
      }
    }

    if (sections.length === 0 && row && pickerConfig) {
      const rows = pickerConfig.columns
        .filter(column => column.key !== 'name' && column.key !== 'link' && column.header)
        .map(column => {
          const rawValue = row[column.key];
          const value = stripHtml(rawValue);
          return {
            label: column.header,
            value: value || 'N/A'
          };
        });
      sections.push({ title: 'Details', rows });
    }

    return sections;
  }

</script>



<svelte:head>
  {#if isSharedMode}
    <title>{sharedDisplayName} - Shared Loadout</title>
    <meta name="description" content="Shared loadout configuration on Entropia Nexus." />
  {:else}
    <title>Entropia Nexus - Loadout Manager</title>
    <meta name="description" content="Tool for managing and comparing different combinations of weapons, armor, clothing, pets and pills and comparing them to each other.">
    <meta name="keywords" content="Weapon Compare, Weapon, Compare, Calculator, Loadouts, Manager, Loadout Manager, Entropia Universe, Entropia, Entropia Nexus, EU, PE, Items, Mobs, Maps, Tools, MindArk, Wiki">
    <link rel="canonical" href="https://entropianexus.com/tools/loadouts" />
  {/if}
</svelte:head>

<svelte:window bind:innerWidth={windowWidth} />

<WikiPage
  title={isSharedMode ? 'Loadout Manager' : 'Loadouts'}
  {breadcrumbs}
  entity={isSharedMode ? (sharedLoadoutData || { Name: sharedDisplayName }) : (loadout || { Name: 'Loadouts' })}
  basePath="/tools/loadouts"
  pageClass="tool-loadouts"
  navItems={[]}
  bind:drawerOpen
  {user}
  editable={false}
  canEdit={false}
>
  <div slot="header-actions" class="loadout-header-actions">
    {#if isSharedMode}
      <button class="action-btn" on:click={handleMakeCopy} disabled={!sharedLoadoutData || isCopying}>
        <span class="action-label">{isCopying ? 'Copying...' : 'Make a copy'}</span>
      </button>
    {:else if activeSource === 'online'}
      <button
        class="action-btn save"
        class:dirty={isDirty}
        on:click={handleManualSave}
        disabled={!loadout || isSaving || !isDirty}
        aria-label={isSaving ? 'Saving...' : (isDirty ? 'Save loadout' : 'Saved')}
        title={isSaving ? 'Saving...' : (isDirty ? 'Save' : 'Saved')}
      >
        <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <use href="#icon-save"></use>
        </svg>
        <span class="action-label">Save</span>
        {#if autosaveSeconds != null && isDirty}
          <span class="save-countdown">{autosaveSeconds}s</span>
        {/if}
      </button>
    {:else}
      <button class="action-btn local" disabled title="Saved locally" aria-label="Saved locally">
        <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <use href="#icon-local"></use>
        </svg>
        <span class="action-label">Local</span>
      </button>
    {/if}
    {#if loadout}
      {#if compareMode}
        <button
          class="action-btn cancel"
          on:click={() => {
            compareMode = false;
          }}
          aria-label="Stop comparing"
          title="Stop comparing"
        >
          <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <use href="#icon-cancel"></use>
          </svg>
          <span class="action-label">Stop</span>
        </button>
      {:else}
        <button
          class="action-btn"
          on:click={() => {
            compareMode = true;
          }}
          aria-label="Compare loadouts"
          title="Compare"
        >
          <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <use href="#icon-compare"></use>
          </svg>
          <span class="action-label">Compare</span>
        </button>
      {/if}
    {/if}
    {#if activeSource === 'online'}
      <button
        class="action-btn share"
        class:public={isPublicLoadout && !!loadout}
        on:click={openShareDialog}
        disabled={!loadout}
        aria-label="Share loadout"
        title={isPublicLoadout ? 'Public link enabled' : 'Share'}
      >
        <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <use href="#icon-share"></use>
        </svg>
        <span class="action-label">Share</span>
      </button>
    {/if}
  </div>

  <div slot="sidebar" let:isMobile>
    {#if isSharedMode}
      <div class="loadout-sidebar" class:mobile={isMobile}>
        <div class="sidebar-header">
          <div class="sidebar-title">{sharedDisplayName}</div>
          <div class="sidebar-meta">
            <span class="sidebar-badge">Shared</span>
            <span class="sidebar-badge readonly">Read-only</span>
          </div>
          <div class="sidebar-status code">Code: {shareCode || sharedLoadout?.share_code || 'N/A'}</div>
        </div>
        <div class="sidebar-actions share-actions">
          <button class="sidebar-btn accent" on:click={handleMakeCopy} disabled={!sharedLoadoutData || isCopying}>
            {isCopying ? 'Copying...' : 'Make a copy'}
          </button>
          <a class="sidebar-btn neutral" href="/tools/loadouts">Back to Loadout Manager</a>
        </div>
        <div class="sidebar-status strong">This loadout is read-only. Make a copy to edit.</div>
      </div>
    {:else}
      <div class="loadout-sidebar" class:mobile={isMobile}>
        <div class="nav-header">
          <h2 class="nav-title">Loadouts</h2>
        </div>
        <div class="sidebar-body">
          <div class="sidebar-toggle">
            <button
              class:active={activeSource === 'online'}
              disabled={!isLoggedIn}
              title={!isLoggedIn ? 'Log in to use online loadouts' : 'Online loadouts'}
              on:click={() => switchSource('online')}
            >Online</button>
            <button
              class:active={activeSource === 'local'}
              on:click={() => switchSource('local')}
            >Local</button>
          </div>
          <div class="sidebar-search">
            <input type="text" placeholder="Search loadouts..." bind:value={loadoutSearch} />
          </div>
          <div class="sidebar-actions">
            <button class="sidebar-btn create" on:click={handleNewLoadout} disabled={entitiesLoading}>New</button>
            <button class="sidebar-btn danger" on:click={confirmDeleteLoadout} disabled={!loadout}>Delete</button>
            <button class="sidebar-btn neutral" on:click={exportActiveLoadout} disabled={!loadout}>Export</button>
            <button class="sidebar-btn neutral" on:click={openImportSourceDialog}>Import</button>
          </div>
          <input type="file" bind:this={fileInput} on:change={handleFileChange} class="file-input-hidden" />
          {#if activeSource === 'online' && onlineLoading}
            <div class="sidebar-status">Loading online loadouts...</div>
          {:else if activeSource === 'online' && onlineError}
            <div class="sidebar-status error">{onlineError}</div>
          {/if}
          <div class="sidebar-list">
          {#if filteredLoadouts.length === 0}
            <div class="sidebar-empty">No loadouts found.</div>
          {:else}
            {#each filteredLoadouts as item}
              <button
                class="sidebar-item"
                class:active={item.id === activeLoadoutKey}
                on:click={() => setActiveLoadout(item.data)}
              >
                <span class="item-name">{getLoadoutListLabel(item.data)}</span>
                {#if activeSource === 'online'}
                  {@const record = onlineLoadouts.find(r => r.id === item.id)}
                  <span
                    class="item-visibility"
                    title={record?.public ? 'Public loadout' : 'Private loadout'}
                  >
                    {#if record?.public}
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 5c4.5 0 7.5 3.5 9 7-1.5 3.5-4.5 7-9 7s-7.5-3.5-9-7c1.5-3.5 4.5-7 9-7z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    {:else}
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="4" y="11" width="16" height="9" rx="2" ry="2" />
                        <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                      </svg>
                    {/if}
                  </span>
                {/if}
              </button>
            {/each}
          {/if}
          </div>
        </div>
      </div>
    {/if}
  </div>

  <svg class="icon-sprite" aria-hidden="true">
    <symbol id="icon-plus" viewBox="0 0 24 24">
      <path d="M12 5v14M5 12h14" />
    </symbol>
    <symbol id="icon-compare" viewBox="0 0 24 24">
      <path d="M4 7h11l-3-3M20 17H9l3 3" />
      <path d="M14 4l-3 3 3 3M10 20l3-3-3-3" />
    </symbol>
    <symbol id="icon-cancel" viewBox="0 0 24 24">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </symbol>
    <symbol id="icon-hide" viewBox="0 0 24 24">
      <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-5 0-9.27-3.11-11-7.5a11.5 11.5 0 0 1 5.18-5.9" />
      <path d="M10.58 10.58a2 2 0 0 0 2.83 2.83" />
      <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c5 0 9.27 3.11 11 7.5a11.5 11.5 0 0 1-4.4 5.3" />
      <path d="M1 1l22 22" />
    </symbol>
    <symbol id="icon-save" viewBox="0 0 24 24">
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
      <path d="M17 21V13H7v8" />
      <path d="M7 3v5h8" />
    </symbol>
    <symbol id="icon-share" viewBox="0 0 24 24">
      <path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7" />
      <path d="M12 3v12" />
      <path d="M8 7l4-4 4 4" />
    </symbol>
    <symbol id="icon-external" viewBox="0 0 24 24">
      <path d="M14 3h7v7" />
      <path d="M10 14L21 3" />
      <path d="M21 14v7h-7" />
      <path d="M3 10V3h7" />
    </symbol>
    <symbol id="icon-local" viewBox="0 0 24 24">
      <path d="M4 20h16" />
      <path d="M7 20V8l5-4 5 4v12" />
    </symbol>
    <symbol id="icon-info" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 10v6M12 7h.01" />
    </symbol>
    <symbol id="icon-stats" viewBox="0 0 24 24">
      <path d="M4 20V10" />
      <path d="M10 20V4" />
      <path d="M16 20v-6" />
      <path d="M2 20h20" />
    </symbol>
    <symbol id="icon-settings" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3 1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
    </symbol>
    <symbol id="icon-weapon" viewBox="0 0 24 24">
      <path d="M3 21l7-7M7 21l7-7" />
      <path d="M14 3l7 7M10 7l7 7" />
    </symbol>
    <symbol id="icon-armor" viewBox="0 0 24 24">
      <path d="M12 3l7 3v6c0 5-3.5 8-7 9-3.5-1-7-4-7-9V6l7-3z" />
    </symbol>
    <symbol id="icon-accessories" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="7" />
      <circle cx="12" cy="12" r="3" />
    </symbol>
  </svg>

  {#if compareMode}
    <div class="compare-layout">
      <DataSection title="Compare" collapsible={false}>
        <button
          slot="actions"
          type="button"
          class="compare-exit-btn"
          on:click={() => { compareMode = false; }}
          aria-label="Stop comparing"
          title="Stop comparing"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <use href="#icon-cancel"></use>
          </svg>
        </button>
        <div class="compare-toolbar">
          <div class="compare-toolbar-left">
            <div class="compare-segment" on:click|stopPropagation>
              <button type="button" class:active={compareType === 'weapons'} on:click={() => (compareType = 'weapons')}>Weapons</button>
              <button type="button" class:active={compareType === 'armor'} on:click={() => (compareType = 'armor')}>Armor</button>
            </div>
            <div class="compare-segment" on:click|stopPropagation>
              <button type="button" class:active={compareDisplay === 'values'} on:click={() => (compareDisplay = 'values')}>Values</button>
              <button type="button" class:active={compareDisplay === 'delta'} disabled={!compareAnchorEval} on:click={() => (compareDisplay = 'delta')}>Delta</button>
            </div>
          </div>

          <div class="compare-toolbar-right">
            <div class="compare-search" on:click|stopPropagation>
              <input type="text" placeholder="Search loadouts..." bind:value={compareNameQuery} />
            </div>

            {#if !isMobileLayout}
              <div class="compare-menu">
                <button
                  type="button"
                  class="compare-menu-btn"
                  on:click|stopPropagation={() => {
                    compareHiddenOpen = !compareHiddenOpen;
                    compareColumnsOpen = false;
                  }}
                >
                  Hidden{hiddenCompareRows.length ? ` (${hiddenCompareRows.length})` : ''}
                </button>
                {#if compareHiddenOpen}
                  <div class="compare-popover" on:click|stopPropagation>
                    {#if hiddenCompareRows.length === 0}
                      <div class="compare-popover-empty">No hidden loadouts.</div>
                    {:else}
                      <div class="compare-popover-list">
                        {#each hiddenCompareRows as item (item.id)}
                          <button type="button" class="compare-popover-item" on:click={() => setCompareHidden(item.id, false)}>
                            <span class="compare-popover-name">{item.name}</span>
                            <span class="compare-popover-action">Show</span>
                          </button>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/if}
              </div>
            {/if}

            {#if !isMobileLayout}
              <div class="compare-menu">
                <button
                  type="button"
                  class="compare-menu-btn"
                  on:click|stopPropagation={() => {
                    compareColumnsOpen = !compareColumnsOpen;
                    compareHiddenOpen = false;
                  }}
                >
                  Columns
                </button>
                {#if compareColumnsOpen}
                  <div class="compare-popover" on:click|stopPropagation>
                    <div class="compare-popover-header">
                      <div class="compare-popover-title">Shown columns</div>
                      <button type="button" class="compare-popover-reset" on:click={() => resetCompareColumns(compareType)}>Reset</button>
                    </div>
                    <div class="compare-columns-grid">
                      {#each COMPARE_COLUMN_ORDER[compareType] as key (key)}
                        {#if key !== 'name'}
                          <label class="compare-col-toggle">
                            <input
                              type="checkbox"
                              checked={compareVisibleKeys.includes(key)}
                              on:change={() => toggleCompareColumn(compareType, key)}
                            />
                            <span>{getCompareColumnLabel(key)}</span>
                          </label>
                        {/if}
                      {/each}
                    </div>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        </div>

        <div
          class="compare-table-wrap"
          style={`--compare-row-height: ${isMobileLayout ? 34 : 38}px;`}
          on:click|capture={handleCompareWrapperClick}
        >
          <FancyTable
            columns={compareColumns}
            data={compareRows}
            searchable={true}
            sortable={true}
            rowHeight={isMobileLayout ? 34 : 38}
            emptyMessage="No loadouts match your filters."
            on:rowClick={(e) => {
              const id = e.detail?.row?._id;
              const next = loadouts.find(x => x?.Id === id);
              if (next) setActiveLoadout(next);
            }}
          />
        </div>
      </DataSection>
    </div>
  {:else if isSharedMode}
  <!-- Shared loadout read-only view -->
  <div class="layout-a loadout-layout loadout-readonly">
    {#if shareError}
      <div class="share-status error">{shareError}</div>
    {:else if entitiesLoading}
      <div class="share-status">Loading loadout data...</div>
    {:else if !sharedLoadoutData}
      <div class="share-status">Shared loadout not available.</div>
    {:else}
      {#if copyStatus}
        <div class="share-status success">{copyStatus}</div>
      {/if}
      {#if copyError}
        <div class="share-status error">{copyError}</div>
      {/if}
      <aside class="loadout-sidebar-float">
        <div class="loadout-infobox-card">
          <div class="infobox-header">
            <div class="infobox-title">{sharedDisplayName}</div>
          </div>
          <div class="stats-section tier-1">
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{stats.efficiency != null ? `${stats.efficiency.toFixed(1)}%` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">DPS</span>
              <span class="stat-value">{stats.dps != null ? `${stats.dps.toFixed(4)}` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">DPP</span>
              <span class="stat-value">{stats.dpp != null ? `${stats.dpp.toFixed(4)}` : 'N/A'}</span>
            </div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Offense</h4>
            <div class="stat-row"><span class="stat-label">Total Damage</span><span class="stat-value">{stats.totalDamage != null ? `${stats.totalDamage.toFixed(2)}` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Range</span><span class="stat-value">{stats.range != null ? `${stats.range.toFixed(1)}m` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Critical Chance</span><span class="stat-value">{stats.critChance != null ? `${(stats.critChance * 100).toFixed(1)}%` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Critical Damage</span><span class="stat-value">{stats.critDamage != null ? `${(stats.critDamage * 100).toFixed(0)}%` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Effective Damage</span><span class="stat-value">{stats.effectiveDamage != null ? `${stats.effectiveDamage.toFixed(2)}` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Reload</span><span class="stat-value">{stats.reload != null ? `${stats.reload.toFixed(2)}s` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Uses/min</span><span class="stat-value">{stats.reload != null ? `${clampDecimals(60 / stats.reload, 0, 2)}` : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Economy</h4>
            <div class="stat-row"><span class="stat-label">Decay</span><span class="stat-value">{stats.decay != null ? `${stats.decay.toFixed(4)} PEC` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Ammo</span><span class="stat-value">{stats.ammo != null ? Math.round(stats.ammo) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Cost</span><span class="stat-value">{stats.cost != null ? `${stats.cost.toFixed(4)} PEC` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Total Uses</span><span class="stat-value">{stats.lowestTotalUses != null ? stats.lowestTotalUses : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Defense</h4>
            <div class="stat-row"><span class="stat-label">Armor Defense</span><span class="stat-value">{stats.armorDefense != null ? stats.armorDefense.toFixed(2) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Plate Defense</span><span class="stat-value">{stats.plateDefense != null ? stats.plateDefense.toFixed(2) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Total Defense</span><span class="stat-value">{stats.totalDefense != null ? stats.totalDefense.toFixed(2) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Block</span><span class="stat-value">{stats.blockChance != null ? `${stats.blockChance.toFixed(1)}%` : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Armor Economy</h4>
            <div class="stat-row"><span class="stat-label">Armor Durability</span><span class="stat-value">{stats.armorDurability != null ? stats.armorDurability : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Plate Durability</span><span class="stat-value">{stats.plateDurability != null ? stats.plateDurability : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Total Absorption</span><span class="stat-value">{stats.totalAbsorption != null ? `${stats.totalAbsorption.toFixed(0)} HP` : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Skill</h4>
            <div class="stat-row"><span class="stat-label">Hit Ability</span><span class="stat-value">{stats.hitAbility != null ? `${stats.hitAbility.toFixed(1)}/10.0` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Crit Ability</span><span class="stat-value">{stats.critAbility != null ? `${stats.critAbility.toFixed(1)}/10.0` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Skill Modification</span><span class="stat-value">{stats.skillModification != null ? `${stats.skillModification.toFixed(1)}%` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Skill Bonus</span><span class="stat-value">{stats.skillBonus != null ? `${stats.skillBonus.toFixed(1)}%` : 'N/A'}</span></div>
          </div>
        </div>
        {#if sharedLoadoutData}
          <div class="loadout-settings-panel">
            <DataSection title="Settings" collapsible={false}>
              <div class="settings-grid">
                <div class="settings-group-title">Profession Levels</div>
                <div class="settings-divider" aria-hidden="true"></div>
                <div class="setting-row">
                  <label>Hit Profession</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Skill?.Hit ?? ''} />
                </div>
                <div class="setting-row">
                  <label>Dmg Profession</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Skill?.Dmg ?? ''} />
                </div>
                <div class="settings-group-title">Bonus Stats</div>
                <div class="settings-divider" aria-hidden="true"></div>
                <div class="setting-row">
                  <label>% Damage</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Properties?.BonusDamage ?? 0} />
                </div>
                <div class="setting-row">
                  <label>% Crit Chance</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Properties?.BonusCritChance ?? 0} />
                </div>
                <div class="setting-row">
                  <label>% Crit Damage</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Properties?.BonusCritDamage ?? 0} />
                </div>
                <div class="setting-row">
                  <label>% Reload</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Properties?.BonusReload ?? 0} />
                </div>
              </div>
            </DataSection>
          </div>
        {/if}
      </aside>
      <article class="wiki-article loadout-article">
        <DataSection title="Weapons">
          <div class="panel-grid two-col">
            <div class="panel-block">
              <h3 class="panel-title">Weapon & Attachments</h3>
              <div class="form-grid">
                <div class="form-label">Weapon</div>
                <div class="control-row">
                  {#if sharedLoadoutData?.Gear?.Weapon?.Name}
                    <a class="slot select-button read-only link-slot" href={getEquipmentLink('weapon', sharedLoadoutData.Gear.Weapon.Name)}>
                      {sharedLoadoutData.Gear.Weapon.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No weapon selected.</span></div>
                  {/if}
                  {#if isLimitedName(sharedLoadoutData?.Gear?.Weapon?.Name)}
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.Weapon ?? 100} />
                    </div>
                  {/if}
                </div>
                <div class="form-label">Amplifier</div>
                <div class="control-row">
                  {#if sharedLoadoutData?.Gear?.Weapon?.Name == null}
                    <div class="slot select-button read-only read-only-slot"><span class="placeholder-muted">Weapon required.</span></div>
                  {:else if sharedLoadoutData?.Gear?.Weapon?.Amplifier?.Name}
                    <a class="slot select-button read-only link-slot" href={getEquipmentLink('amplifier', sharedLoadoutData.Gear.Weapon.Amplifier.Name)}>
                      {sharedLoadoutData.Gear.Weapon.Amplifier.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No amplifier selected.</span></div>
                  {/if}
                  {#if isLimitedName(sharedLoadoutData?.Gear?.Weapon?.Amplifier?.Name)}
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.Amplifier ?? 100} />
                    </div>
                  {/if}
                </div>
                <div class="form-label">Absorber</div>
                <div class="control-row">
                  {#if sharedLoadoutData?.Gear?.Weapon?.Name == null}
                    <div class="slot select-button read-only read-only-slot"><span class="placeholder-muted">Weapon required.</span></div>
                  {:else if sharedLoadoutData?.Gear?.Weapon?.Absorber?.Name}
                    <a class="slot select-button read-only link-slot" href={getEquipmentLink('absorber', sharedLoadoutData.Gear.Weapon.Absorber.Name)}>
                      {sharedLoadoutData.Gear.Weapon.Absorber.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No absorber selected.</span></div>
                  {/if}
                  {#if isLimitedName(sharedLoadoutData?.Gear?.Weapon?.Absorber?.Name)}
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.Absorber ?? 100} />
                    </div>
                  {/if}
                </div>
                {#if getWeapon(sharedLoadoutData?.Gear?.Weapon?.Name)?.Properties?.Class === 'Ranged'}
                  <div class="form-label">Scope</div>
                  <div class="control-row">
                    {#if sharedLoadoutData?.Gear?.Weapon?.Scope?.Name}
                      <a class="slot select-button read-only link-slot" href={getEquipmentLink('scope', sharedLoadoutData.Gear.Weapon.Scope.Name)}>
                        {sharedLoadoutData.Gear.Weapon.Scope.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No scope selected.</span></div>
                    {/if}
                    {#if isLimitedName(sharedLoadoutData?.Gear?.Weapon?.Scope?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.Scope ?? 100} />
                      </div>
                    {/if}
                  </div>
                  <div class="form-label sub-label">
                    <span class="branch-icon" aria-hidden="true">
                      <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M2 2v4a2 2 0 0 0 2 2h6" />
                        <path d="M8 6l2 2-2 2" />
                      </svg>
                    </span>
                    <span>Scope Sight</span>
                  </div>
                  <div class="control-row scope-sight-row">
                    {#if sharedLoadoutData?.Gear?.Weapon?.Scope == null}
                      <div class="slot select-button read-only read-only-slot"><span class="placeholder-muted">Add a scope first</span></div>
                    {:else if sharedLoadoutData?.Gear?.Weapon?.Scope?.Sight?.Name}
                      <a class="slot select-button read-only link-slot" href={getEquipmentLink('scope-sight', sharedLoadoutData.Gear.Weapon.Scope.Sight.Name)}>
                        {sharedLoadoutData.Gear.Weapon.Scope.Sight.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No sight selected.</span></div>
                    {/if}
                    {#if isLimitedName(sharedLoadoutData?.Gear?.Weapon?.Scope?.Sight?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.ScopeSight ?? 100} />
                      </div>
                    {/if}
                  </div>
                  <div class="form-label">Sight</div>
                  <div class="control-row">
                    {#if sharedLoadoutData?.Gear?.Weapon?.Sight?.Name}
                      <a class="slot select-button read-only link-slot" href={getEquipmentLink('sight', sharedLoadoutData.Gear.Weapon.Sight.Name)}>
                        {sharedLoadoutData.Gear.Weapon.Sight.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No sight selected.</span></div>
                    {/if}
                    {#if isLimitedName(sharedLoadoutData?.Gear?.Weapon?.Sight?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.Sight ?? 100} />
                      </div>
                    {/if}
                  </div>
                {:else if getWeapon(sharedLoadoutData?.Gear?.Weapon?.Name)?.Properties?.Class === 'Melee'}
                  <div class="form-label">Matrix</div>
                  <div class="control-row">
                    {#if sharedLoadoutData?.Gear?.Weapon?.Matrix?.Name}
                      <a class="slot select-button read-only link-slot" href={getEquipmentLink('matrix', sharedLoadoutData.Gear.Weapon.Matrix.Name)}>
                        {sharedLoadoutData.Gear.Weapon.Matrix.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No matrix selected.</span></div>
                    {/if}
                    {#if isLimitedName(sharedLoadoutData?.Gear?.Weapon?.Matrix?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.Matrix ?? 100} />
                      </div>
                    {/if}
                  </div>
                {:else if getWeapon(sharedLoadoutData?.Gear?.Weapon?.Name)?.Properties?.Class === 'Mindforce'}
                  <div class="form-label">Implant</div>
                  <div class="control-row">
                    {#if sharedLoadoutData?.Gear?.Weapon?.Implant?.Name}
                      <a class="slot select-button read-only link-slot" href={getEquipmentLink('implant', sharedLoadoutData.Gear.Weapon.Implant.Name)}>
                        {sharedLoadoutData.Gear.Weapon.Implant.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No implant selected.</span></div>
                    {/if}
                    {#if isLimitedName(sharedLoadoutData?.Gear?.Weapon?.Implant?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.Implant ?? 100} />
                      </div>
                    {/if}
                  </div>
                {/if}
                <div class="form-label">Ammo</div>
                <div class="control-row">
                  {#if sharedLoadoutData?.Gear?.Weapon?.Name == null}
                    <span class="placeholder-muted">Weapon required.</span>
                  {:else}
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.Ammo ?? 100} />
                    </div>
                  {/if}
                </div>
              </div>
            </div>
            <div class="panel-block">
              <h3 class="panel-title">Enhancers & Options</h3>
              <div class="enhancer-grid">
                <div class="enhancer-field">
                  <label>Damage</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Gear?.Weapon?.Enhancers?.Damage ?? 0} />
                </div>
                <div class="enhancer-field">
                  <label>Accuracy</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Gear?.Weapon?.Enhancers?.Accuracy ?? 0} />
                </div>
                <div class="enhancer-field">
                  <label>Range</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Gear?.Weapon?.Enhancers?.Range ?? 0} />
                </div>
                <div class="enhancer-field">
                  <label>Economy</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Gear?.Weapon?.Enhancers?.Economy ?? 0} />
                </div>
                <div class="enhancer-field">
                  <label>Skill Mod</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Gear?.Weapon?.Enhancers?.SkillMod ?? 0} />
                </div>
              </div>
            </div>
          </div>
        </DataSection>

        <DataSection title="Armor">
          <div class="panel-grid two-col">
            <div class="panel-block">
              <h3 class="panel-title">Armor Selection</h3>
              {#if sharedLoadoutData?.Gear?.Armor?.ManageIndividual}
                <div class="armor-grid">
                  <div class="armor-grid-header">Slot</div>
                  <div class="armor-grid-header">Armor</div>
                  <div class="armor-grid-header">Armor MU</div>
                  <div class="armor-grid-header">Plate</div>
                  <div class="armor-grid-header">Plate MU</div>
                  {#each armorSlots as slot}
                    <div class="armor-label">{slot}</div>
                    {#if sharedLoadoutData?.Gear?.Armor?.[slot]?.Name}
                      <a class="slot select-button read-only link-slot" href={getEquipmentLink('armor', sharedLoadoutData.Gear.Armor[slot].Name)}>
                        {sharedLoadoutData.Gear.Armor[slot].Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No armor selected.</span></div>
                    {/if}
                    {#if isLimitedName(sharedLoadoutData?.Gear?.Armor?.[slot]?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.Armors?.[slot] ?? 100} />
                      </div>
                    {:else}
                      <span class="placeholder-muted"></span>
                    {/if}
                    {#if sharedLoadoutData?.Gear?.Armor?.[slot]?.Name == null}
                      <div class="slot select-button read-only read-only-slot"><span class="placeholder-muted">Armor required.</span></div>
                    {:else if sharedLoadoutData?.Gear?.Armor?.[slot]?.Plate?.Name}
                      <a class="slot select-button read-only link-slot" href={getEquipmentLink('armorplating', sharedLoadoutData.Gear.Armor[slot].Plate.Name)}>
                        {sharedLoadoutData.Gear.Armor[slot].Plate.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No plating selected.</span></div>
                    {/if}
                    {#if isLimitedName(sharedLoadoutData?.Gear?.Armor?.[slot]?.Plate?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.Plates?.[slot] ?? 100} />
                      </div>
                    {:else}
                      <span class="placeholder-muted"></span>
                    {/if}
                  {/each}
                </div>
              {:else}
                <div class="form-grid">
                  <div class="form-label">Armor Set</div>
                  {#if sharedLoadoutData?.Gear?.Armor?.SetName}
                    <a class="slot select-button read-only link-slot" href={getEquipmentLink('armorset', sharedLoadoutData.Gear.Armor.SetName)}>
                      {sharedLoadoutData.Gear.Armor.SetName}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No armor set selected.</span></div>
                  {/if}
                  {#if isLimitedName(sharedLoadoutData?.Gear?.Armor?.SetName)}
                    <div class="form-label">Armor Markup</div>
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.ArmorSet ?? 100} />
                    </div>
                  {/if}
                  <div class="form-label">Plate Set</div>
                  {#if sharedLoadoutData?.Gear?.Armor?.SetName == null}
                    <div class="slot select-button read-only read-only-slot"><span class="placeholder-muted">Armor set required.</span></div>
                  {:else if sharedLoadoutData?.Gear?.Armor?.PlateName}
                    <a class="slot select-button read-only link-slot" href={getEquipmentLink('armorplating', sharedLoadoutData.Gear.Armor.PlateName)}>
                      {sharedLoadoutData.Gear.Armor.PlateName}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No plating selected.</span></div>
                  {/if}
                  {#if isLimitedName(sharedLoadoutData?.Gear?.Armor?.PlateName)}
                    <div class="form-label">Plate Markup</div>
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={sharedLoadoutData?.Markup?.PlateSet ?? 100} />
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
            <div class="panel-block">
              <h3 class="panel-title">Enhancers & Options</h3>
              <div class="enhancer-grid">
                <div class="enhancer-field">
                  <label>Defense</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Gear?.Armor?.Enhancers?.Defense ?? 0} />
                </div>
                <div class="enhancer-field">
                  <label>Durability</label>
                  <input class="read-only-field" type="number" readonly value={sharedLoadoutData?.Gear?.Armor?.Enhancers?.Durability ?? 0} />
                </div>
              </div>
              <label class="checkbox-row">
                <input type="checkbox" checked={!!sharedLoadoutData?.Gear?.Armor?.ManageIndividual} disabled />
                <span>Manage armor pieces individually</span>
              </label>
            </div>
          </div>
        </DataSection>

        <DataSection title="Accessories & Buffs">
          <div class="accessory-panel">
            <div class="accessory-section">
              <h3 class="panel-title">Rings & Pet</h3>
              <div class="accessory-grid rings-pet-grid">
                <div class="accessory-item">
                  <div class="form-label">Left Ring</div>
                  {#if leftRing?.Name}
                    <a class="slot select-button read-only link-slot" href={getEquipmentLink('clothing', leftRing.Name)}>
                      {leftRing.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No ring selected.</span></div>
                  {/if}
                </div>
                <div class="accessory-item">
                  <div class="form-label">Right Ring</div>
                  {#if rightRing?.Name}
                    <a class="slot select-button read-only link-slot" href={getEquipmentLink('clothing', rightRing.Name)}>
                      {rightRing.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No ring selected.</span></div>
                  {/if}
                </div>
                <div class="accessory-item pet-select">
                  <div class="form-label">Pet</div>
                  {#if sharedLoadoutData?.Gear?.Pet?.Name}
                    <a class="slot select-button read-only link-slot pet-active" href={getEquipmentLink('pet', sharedLoadoutData.Gear.Pet.Name)}>
                      {sharedLoadoutData.Gear.Pet.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot"><span class="placeholder-text">No pet selected.</span></div>
                  {/if}
                </div>
              </div>
              <div class="pet-abilities">
                {#if !sharedLoadoutData?.Gear?.Pet?.Name}
                  <div class="pet-abilities-empty">No pet selected.</div>
                {:else if activePetEffects.length === 0}
                  <div class="pet-abilities-empty">No abilities available for this pet.</div>
                {:else}
                  <div class="pet-effect-grid">
                    {#each activePetEffects as effect, index}
                      {@const effectName = effect?.Name || `Effect ${index + 1}`}
                      {@const strength = getPetEffectStrength(effect)}
                      {@const unit = effect?.Properties?.Unit || ''}
                      {@const upkeep = effect?.Properties?.NutrioConsumptionPerHour}
                      {@const level = effect?.Properties?.Unlock?.Level}
                      {@const effectKey = `${effectName}::${strength ?? 0}`}
                      <button
                        class="pet-effect-card read-only"
                        class:active={sharedLoadoutData?.Gear?.Pet?.Effect === effectKey || sharedLoadoutData?.Gear?.Pet?.Effect === effectName}
                        type="button"
                      >
                        <div class="pet-effect-name">{effectName}</div>
                        <div class="pet-effect-meta">
                          <div class="pet-effect-stat">
                            <span class="pet-effect-label">Strength</span>
                            <span class="pet-effect-value">{strength != null ? `${strength}${unit}` : '-'}</span>
                          </div>
                          <div class="pet-effect-stat">
                            <span class="pet-effect-label">Upkeep</span>
                            <span class="pet-effect-value">{upkeep != null ? `${upkeep}/h` : 'N/A'}</span>
                          </div>
                          <div class="pet-effect-stat">
                            <span class="pet-effect-label">Unlock</span>
                            <span class="pet-effect-value">{level != null ? `Lv ${level}` : '-'}</span>
                          </div>
                        </div>
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>
            <div class="accessory-section">
              <div class="accessory-section-header">
                <h3 class="panel-title">Clothing</h3>
              </div>
              <div class="clothing-hint">Slots are unique. Picking a piece for an occupied slot replaces it.</div>
              {#if selectedClothing.length === 0}
                <div class="clothing-empty">No clothing selected.</div>
              {:else}
                <div class="clothing-list">
                  {#each selectedClothing as entry}
                    {@const item = getClothingItem(entry.Name)}
                    <div class="clothing-item">
                      <div class="clothing-main">
                        <a class="clothing-name item-link" href={getEquipmentLink('clothing', entry.Name)}>{entry.Name}</a>
                        <div class="clothing-meta">
                          <span class="clothing-slot">{entry.Slot}</span>
                          <span class="clothing-effects">{getClothingEffectLabel(item)}</span>
                        </div>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
            <div class="accessory-section">
              <div class="accessory-section-header">
                <h3 class="panel-title">Consumables</h3>
              </div>
              <div class="clothing-hint">Only the strongest consumable effect per type is applied.</div>
              {#if selectedConsumables.length === 0}
                <div class="clothing-empty">No consumables selected.</div>
              {:else}
                <div class="clothing-list">
                  {#each selectedConsumables as entry}
                    {@const entryName = entry?.Name || entry}
                    {@const item = getConsumableItem(entryName)}
                    <div class="clothing-item">
                      <div class="clothing-main">
                        <a class="clothing-name item-link" href={getEquipmentLink('consumable', entryName)}>{entryName}</a>
                        <div class="clothing-meta">
                          <span class="clothing-slot">{item?.Properties?.Type ?? 'Consumable'}</span>
                          <span class="clothing-effects">{formatEffectCount(getConsumableEffectCount(item))}</span>
                        </div>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          </div>
        </DataSection>
      </article>
    {/if}
  </div>
  {:else}
  <!-- Empty state when no loadout selected -->
  {#if !loadout}
    <div class="mobile-empty-state">
      <p>Create a new loadout or select an existing one.</p>
      <div class="mobile-empty-actions">
        <button class="mobile-empty-btn create" on:click={handleNewLoadout} disabled={entitiesLoading}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Loadout
        </button>
        {#if isMobileLayout && loadouts.length > 0}
        <button class="mobile-empty-btn browse" on:click={() => drawerOpen = true}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          Browse Loadouts
        </button>
        {/if}
      </div>
    </div>
  {:else}
  <div class="layout-a">
    {#if isMobileLayout}
      <div class="mobile-panel-overview">
        <div class="mobile-panel-track">
          {#each mobilePanelItems as panel, index}
            <button
              class="mobile-panel-button"
              class:active={activeMobilePanel === panel.key}
              on:click={() => setMobilePanelIndex(index)}
              aria-label={panel.label}
              title={panel.label}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <use href={`#${panel.icon}`}></use>
              </svg>
              <span>{panel.label}</span>
            </button>
          {/each}
        </div>
      </div>
    {/if}

    <div
      class="mobile-panels"
      bind:this={mobilePanelsEl}
      on:touchstart={handleTouchStart}
      on:touchmove={handleTouchMove}
      on:touchend={handleTouchEnd}
    >
      <div
        class="mobile-panels-track"
        class:swiping={swipeActive}
        style={`transform: ${mobilePanelTranslate};`}
      >
    <aside class="loadout-sidebar-float">
      <div class="mobile-panel" class:active={activeMobilePanel === 'info'}>
        <div class="loadout-infobox-card" on:input|capture={markDirty} on:change|capture={markDirty}>
        <div class="infobox-header">
          {#if loadout}
            <input class="infobox-name-input" type="text" bind:value={loadout.Name} placeholder="Loadout name" />
          {:else}
            <div class="infobox-title">Select a loadout</div>
          {/if}
        </div>
        {#if loadout}
          <div class="stats-section tier-1">
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{stats.efficiency != null ? `${stats.efficiency.toFixed(1)}%` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">DPS</span>
              <span class="stat-value">{stats.dps != null ? `${stats.dps.toFixed(4)}` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">DPP</span>
              <span class="stat-value">{stats.dpp != null ? `${stats.dpp.toFixed(4)}` : 'N/A'}</span>
            </div>
          </div>
          <div class="stats-section buff-summary">
            <h4 class="section-title">Active Effects</h4>
            {#if offensiveEffects.length === 0 && defensiveEffects.length === 0 && utilityEffects.length === 0}
              <div class="buff-empty">No effects are active</div>
            {:else}
              {#if offensiveEffects.length > 0}
                <div class="buff-panel">
                  <div class="buff-panel-title">Offensive Effects</div>
                  <ul class="effects-list">
                    {#each offensiveEffects as effect}
                      {@const hasCaps = !!(effect?.caps?.item || effect?.caps?.action || effect?.caps?.total)}
                      {@const effectKey = `${effect.name}::${effect.unit}`}
                      {@const expanded = expandedEffectKeys.has(effectKey)}
                      {@const totalBase = (effect?.cappedItem ?? 0) + (effect?.cappedAction ?? 0) + (effect?.rawBonus ?? 0)}
                      {#if hasCaps}
                        <li>
                          <button type="button" class="effect-item equip effect-toggle" class:open={expanded} on:click={() => toggleEffectExpanded(effectKey)}>
                              <span class="effect-name">{effect.name}</span>
                              <span class="effect-details">
                                <span
                                  class="effect-value"
                                  class:positive={effect.polarity === 'positive'}
                                  class:negative={effect.polarity === 'negative'}
                                >
                                  {#if effect.cappedAny}[{/if}{formatMagnitude(effect.signedTotal, effect.unit)}{#if effect.cappedAny}]{/if}
                                </span>
                              </span>
                          </button>
                          {#if expanded}
                            <div class="cap-breakdown" in:slide={{ duration: 180 }} out:slide={{ duration: 160 }}>
                              <div class="cap-breakdown-inner">
                                {#if effect?.caps?.item}
                                  <div class="cap-row">
                                    <span class="cap-label">Item</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawItem ?? 0) > effect.caps.item}>{formatSignedNoPlus(effect.rawItem ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.item, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.action}
                                  <div class="cap-row">
                                    <span class="cap-label">Action</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawAction ?? 0) > effect.caps.action}>{formatSignedNoPlus(effect.rawAction ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.action, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.total}
                                  <div class="cap-row">
                                    <span class="cap-label">Total</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(totalBase) > effect.caps.total}>{formatSignedNoPlus(totalBase, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.total, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                              </div>
                            </div>
                          {/if}
                        </li>
                      {:else}
                        <li class="effect-item equip">
                          <span class="effect-name">{effect.name}</span>
                          <span class="effect-details">
                            <span
                              class="effect-value"
                              class:positive={effect.polarity === 'positive'}
                              class:negative={effect.polarity === 'negative'}
                            >
                              {formatMagnitude(effect.signedTotal, effect.unit)}
                            </span>
                          </span>
                        </li>
                      {/if}
                    {/each}
                  </ul>
                </div>
              {/if}
              {#if defensiveEffects.length > 0}
                <div class="buff-panel">
                  <div class="buff-panel-title">Defensive Effects</div>
                  <ul class="effects-list">
                    {#each defensiveEffects as effect}
                      {@const hasCaps = !!(effect?.caps?.item || effect?.caps?.action || effect?.caps?.total)}
                      {@const effectKey = `${effect.name}::${effect.unit}`}
                      {@const expanded = expandedEffectKeys.has(effectKey)}
                      {@const totalBase = (effect?.cappedItem ?? 0) + (effect?.cappedAction ?? 0) + (effect?.rawBonus ?? 0)}
                      {#if hasCaps}
                        <li>
                          <button type="button" class="effect-item equip effect-toggle" class:open={expanded} on:click={() => toggleEffectExpanded(effectKey)}>
                              <span class="effect-name">{effect.name}</span>
                              <span class="effect-details">
                                <span
                                  class="effect-value"
                                  class:positive={effect.polarity === 'positive'}
                                  class:negative={effect.polarity === 'negative'}
                                >
                                  {#if effect.cappedAny}[{/if}{formatMagnitude(effect.signedTotal, effect.unit)}{#if effect.cappedAny}]{/if}
                                </span>
                              </span>
                          </button>
                          {#if expanded}
                            <div class="cap-breakdown" in:slide={{ duration: 180 }} out:slide={{ duration: 160 }}>
                              <div class="cap-breakdown-inner">
                                {#if effect?.caps?.item}
                                  <div class="cap-row">
                                    <span class="cap-label">Item</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawItem ?? 0) > effect.caps.item}>{formatSignedNoPlus(effect.rawItem ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.item, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.action}
                                  <div class="cap-row">
                                    <span class="cap-label">Action</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawAction ?? 0) > effect.caps.action}>{formatSignedNoPlus(effect.rawAction ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.action, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.total}
                                  <div class="cap-row">
                                    <span class="cap-label">Total</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(totalBase) > effect.caps.total}>{formatSignedNoPlus(totalBase, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.total, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                              </div>
                            </div>
                          {/if}
                        </li>
                      {:else}
                        <li class="effect-item equip">
                          <span class="effect-name">{effect.name}</span>
                          <span class="effect-details">
                            <span
                              class="effect-value"
                              class:positive={effect.polarity === 'positive'}
                              class:negative={effect.polarity === 'negative'}
                            >
                              {formatMagnitude(effect.signedTotal, effect.unit)}
                            </span>
                          </span>
                        </li>
                      {/if}
                    {/each}
                  </ul>
                </div>
              {/if}
              {#if utilityEffects.length > 0}
                <div class="buff-panel">
                  <div class="buff-panel-title">Utility Effects</div>
                  <ul class="effects-list">
                    {#each utilityEffects as effect}
                      {@const hasCaps = !!(effect?.caps?.item || effect?.caps?.action || effect?.caps?.total)}
                      {@const effectKey = `${effect.name}::${effect.unit}`}
                      {@const expanded = expandedEffectKeys.has(effectKey)}
                      {@const totalBase = (effect?.cappedItem ?? 0) + (effect?.cappedAction ?? 0) + (effect?.rawBonus ?? 0)}
                      {#if hasCaps}
                        <li>
                          <button type="button" class="effect-item equip effect-toggle" class:open={expanded} on:click={() => toggleEffectExpanded(effectKey)}>
                              <span class="effect-name">{effect.name}</span>
                              <span class="effect-details">
                                <span
                                  class="effect-value"
                                  class:positive={effect.polarity === 'positive'}
                                  class:negative={effect.polarity === 'negative'}
                                >
                                  {#if effect.cappedAny}[{/if}{formatMagnitude(effect.signedTotal, effect.unit)}{#if effect.cappedAny}]{/if}
                                </span>
                              </span>
                          </button>
                          {#if expanded}
                            <div class="cap-breakdown" in:slide={{ duration: 180 }} out:slide={{ duration: 160 }}>
                              <div class="cap-breakdown-inner">
                                {#if effect?.caps?.item}
                                  <div class="cap-row">
                                    <span class="cap-label">Item</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawItem ?? 0) > effect.caps.item}>{formatSignedNoPlus(effect.rawItem ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.item, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.action}
                                  <div class="cap-row">
                                    <span class="cap-label">Action</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawAction ?? 0) > effect.caps.action}>{formatSignedNoPlus(effect.rawAction ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.action, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.total}
                                  <div class="cap-row">
                                    <span class="cap-label">Total</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(totalBase) > effect.caps.total}>{formatSignedNoPlus(totalBase, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.total, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                              </div>
                            </div>
                          {/if}
                        </li>
                      {:else}
                        <li class="effect-item equip">
                          <span class="effect-name">{effect.name}</span>
                          <span class="effect-details">
                            <span
                              class="effect-value"
                              class:positive={effect.polarity === 'positive'}
                              class:negative={effect.polarity === 'negative'}
                            >
                              {formatMagnitude(effect.signedTotal, effect.unit)}
                            </span>
                          </span>
                        </li>
                      {/if}
                    {/each}
                  </ul>
                </div>
              {/if}
            {/if}
          </div>
          <div class="stats-section">
            <h4 class="section-title">Offense</h4>
            <div class="stat-row"><span class="stat-label">Total Damage</span><span class="stat-value">{stats.totalDamage != null ? `${stats.totalDamage.toFixed(2)}` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Range</span><span class="stat-value">{stats.range != null ? `${stats.range.toFixed(1)}m` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Critical Chance</span><span class="stat-value">{stats.critChance != null ? `${(stats.critChance * 100).toFixed(1)}%` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Critical Damage</span><span class="stat-value">{stats.critDamage != null ? `${(stats.critDamage * 100).toFixed(0)}%` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Effective Damage</span><span class="stat-value">{stats.effectiveDamage != null ? `${stats.effectiveDamage.toFixed(2)}` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Reload</span><span class="stat-value">{stats.reload != null ? `${stats.reload.toFixed(2)}s` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Uses/min</span><span class="stat-value">{stats.reload != null ? `${clampDecimals(60 / stats.reload, 0, 2)}` : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Economy</h4>
            <div class="stat-row"><span class="stat-label">Decay</span><span class="stat-value">{stats.decay != null ? `${stats.decay.toFixed(4)} PEC` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Ammo</span><span class="stat-value">{stats.ammo != null ? Math.round(stats.ammo) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Cost</span><span class="stat-value">{stats.cost != null ? `${stats.cost.toFixed(4)} PEC` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Total Uses</span><span class="stat-value">{stats.lowestTotalUses != null ? stats.lowestTotalUses : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Defense</h4>
            <div class="stat-row"><span class="stat-label">Armor Defense</span><span class="stat-value">{stats.armorDefense != null ? stats.armorDefense.toFixed(2) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Plate Defense</span><span class="stat-value">{stats.plateDefense != null ? stats.plateDefense.toFixed(2) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Total Defense</span><span class="stat-value">{stats.totalDefense != null ? stats.totalDefense.toFixed(2) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Block</span><span class="stat-value">{stats.blockChance != null ? `${stats.blockChance.toFixed(1)}%` : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Armor Economy</h4>
            <div class="stat-row"><span class="stat-label">Armor Durability</span><span class="stat-value">{stats.armorDurability != null ? stats.armorDurability : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Plate Durability</span><span class="stat-value">{stats.plateDurability != null ? stats.plateDurability : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Total Absorption</span><span class="stat-value">{stats.totalAbsorption != null ? `${stats.totalAbsorption.toFixed(0)} HP` : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Skill</h4>
            <div class="stat-row"><span class="stat-label">Hit Ability</span><span class="stat-value">{stats.hitAbility != null ? `${stats.hitAbility.toFixed(1)}/10.0` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Crit Ability</span><span class="stat-value">{stats.critAbility != null ? `${stats.critAbility.toFixed(1)}/10.0` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Skill Modification</span><span class="stat-value">{stats.skillModification != null ? `${stats.skillModification.toFixed(1)}%` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Skill Bonus</span><span class="stat-value">{stats.skillBonus != null ? `${stats.skillBonus.toFixed(1)}%` : 'N/A'}</span></div>
          </div>
        {:else}
          <div class="stats-empty">Select a loadout to view stats.</div>
        {/if}
        </div>
      </div>
      {#if loadout}
        <div class="mobile-panel" class:active={activeMobilePanel === 'settings'}>
          <div class="loadout-settings-panel" on:input|capture={markDirty} on:change|capture={markDirty}>
            <DataSection title="Settings" collapsible={false}>
              <div class="settings-grid">
                <div class="settings-group-title">Profession Levels</div>
                <div class="settings-divider" aria-hidden="true"></div>
                <div class="setting-row">
                  <label>Hit Profession</label>
                  <input type="number" bind:value={loadout.Skill.Hit} />
                </div>
                <div class="setting-row">
                  <label>Dmg Profession</label>
                  <input type="number" bind:value={loadout.Skill.Dmg} />
                </div>
                <div class="settings-group-title">Bonus Stats</div>
                <div class="settings-divider" aria-hidden="true"></div>
                <div class="setting-row">
                  <label>% Damage</label>
                  <input type="number" bind:value={loadout.Properties.BonusDamage} />
                </div>
                <div class="setting-row">
                  <label>% Crit Chance</label>
                  <input type="number" bind:value={loadout.Properties.BonusCritChance} />
                </div>
                <div class="setting-row">
                  <label>% Crit Damage</label>
                  <input type="number" bind:value={loadout.Properties.BonusCritDamage} />
                </div>
                <div class="setting-row">
                  <label>% Reload</label>
                  <input type="number" bind:value={loadout.Properties.BonusReload} />
                </div>
              </div>
            </DataSection>
          </div>
        </div>
      {/if}
    </aside>

    <article class="wiki-article loadout-article" on:input|capture={markDirty} on:change|capture={markDirty}>
      {#if $loading || entitiesLoading}
        <div class="loading-text">Loading game data...</div>
      {:else if loadout != null}
        {#if saveError}
          <div class="save-status error">{saveError}</div>
        {/if}

        <div class="mobile-panel" class:active={activeMobilePanel === 'weapons'}>
          <DataSection title="Weapons">
            <div class="panel-grid two-col">
              <div class="panel-block">
                <h3 class="panel-title">Weapon & Attachments</h3>
                <div class="form-grid">
                  <div class="form-label">Weapon</div>
                  <div class="control-row">
                    <button class="slot select-button" on:contextmenu={e => clearSlot(e, "weapon")} on:click={() => openPicker('weapon')}>
                      {#if loadout?.Gear.Weapon.Name != null}
                        {loadout.Gear.Weapon.Name}
                      {:else}
                        <span class="placeholder-text">Select a weapon...</span>
                      {/if}
                    </button>
                    {#if isLimitedName(loadout?.Gear.Weapon.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Weapon} />
                      </div>
                    {/if}
                  </div>
                  <div class="form-label">Amplifier</div>
                  <div class="control-row">
                    <button class="slot select-button" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "amplifier")} on:click={() => openPicker('amplifier')}>
                      {#if loadout?.Gear.Weapon.Name != null}
                        {#if loadout?.Gear.Weapon.Amplifier?.Name != null}
                          {loadout.Gear.Weapon.Amplifier.Name}
                        {:else}
                          <span class="placeholder-text">Select an amplifier...</span>
                        {/if}
                      {:else}
                        <span class="placeholder-muted">Choose a weapon first</span>
                      {/if}
                    </button>
                    {#if isLimitedName(loadout?.Gear.Weapon.Amplifier?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Amplifier} />
                      </div>
                    {/if}
                  </div>
                  <div class="form-label">Absorber</div>
                  <div class="control-row">
                    <button class="slot select-button" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "absorber")} on:click={() => openPicker('absorber')}>
                      {#if loadout?.Gear.Weapon.Name != null}
                        {#if loadout?.Gear.Weapon.Absorber?.Name != null}
                          {loadout.Gear.Weapon.Absorber.Name}
                        {:else}
                          <span class="placeholder-text">Select an absorber...</span>
                        {/if}
                      {:else}
                        <span class="placeholder-muted">Choose a weapon first</span>
                      {/if}
                    </button>
                    {#if isLimitedName(loadout?.Gear.Weapon.Absorber?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Absorber} />
                      </div>
                    {/if}
                  </div>
                  {#if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Ranged'}
                    <div class="form-label">Scope</div>
                    <div class="control-row">
                      <button class="slot select-button" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "scope")} on:click={() => openPicker('scope')}>
                        {#if loadout?.Gear.Weapon.Scope?.Name != null}
                          {loadout.Gear.Weapon.Scope.Name}
                        {:else}
                          <span class="placeholder-text">Select a scope...</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Weapon.Scope?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Scope} />
                        </div>
                      {/if}
                    </div>
                    <div class="form-label sub-label">
                      <span class="branch-icon" aria-hidden="true">
                        <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                          <path d="M2 2v4a2 2 0 0 0 2 2h6" />
                          <path d="M8 6l2 2-2 2" />
                        </svg>
                      </span>
                      <span>Scope Sight</span>
                    </div>
                    <div class="control-row scope-sight-row">
                      <button class="slot select-button" disabled={loadout?.Gear.Weapon.Scope == null} on:contextmenu={e => clearSlot(e, "scope-sight")} on:click={() => openPicker('scope-sight')}>
                        {#if loadout.Gear.Weapon.Scope != null}
                          {#if loadout?.Gear.Weapon.Scope?.Sight?.Name != null}
                            {loadout.Gear.Weapon.Scope.Sight.Name}
                          {:else}
                            <span class="placeholder-text">Select a sight...</span>
                          {/if}
                        {:else}
                          <span class="placeholder-muted">Add a scope first</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Weapon.Scope?.Sight?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.ScopeSight} />
                        </div>
                      {/if}
                    </div>
                    <div class="form-label">Sight</div>
                    <div class="control-row">
                      <button class="slot select-button" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "sight")} on:click={() => openPicker('sight')}>
                        {#if loadout?.Gear.Weapon.Sight?.Name != null}
                          {loadout.Gear.Weapon.Sight.Name}
                        {:else}
                          <span class="placeholder-text">Select a sight...</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Weapon.Sight?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Sight} />
                        </div>
                      {/if}
                    </div>
                  {:else if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Melee'}
                    <div class="form-label">Matrix</div>
                    <div class="control-row">
                      <button class="slot select-button" disabled={getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class !== 'Melee'} on:contextmenu={e => clearSlot(e, "matrix")} on:click={() => openPicker('matrix')}>
                        {#if loadout?.Gear.Weapon.Matrix?.Name != null}
                          {loadout.Gear.Weapon.Matrix.Name}
                        {:else}
                          <span class="placeholder-text">Select a matrix...</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Weapon.Matrix?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Matrix} />
                        </div>
                      {/if}
                    </div>
                  {:else if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Mindforce'}
                    <div class="form-label">Implant</div>
                    <div class="control-row">
                      <button class="slot select-button" disabled={getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class !== 'Mindforce'} on:contextmenu={e => clearSlot(e, "weapon")} on:click={() => openPicker('implant')}>
                        {#if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Mindforce'}
                          {#if loadout?.Gear.Weapon.Implant?.Name != null}
                            {loadout.Gear.Weapon.Implant.Name}
                          {:else}
                            <span class="placeholder-text">Select an implant...</span>
                          {/if}
                        {:else}
                          <span class="placeholder-muted">Choose a Mindforce weapon</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Weapon.Implant?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Implant} />
                        </div>
                      {/if}
                    </div>
                  {/if}
                  <div class="form-label">Ammo</div>
                  <div class="control-row">
                    {#if loadout?.Gear.Weapon.Name == null}
                      <span class="placeholder-muted">Choose a weapon first</span>
                    {:else}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Ammo} />
                      </div>
                    {/if}
                  </div>
                </div>
                <button class="reset-btn compact" on:click={resetMarkup}>Reset all markup</button>
              </div>
              <div class="panel-block">
                <h3 class="panel-title">Enhancers & Options</h3>
                <div class="enhancer-grid">
                  <div class="enhancer-field">
                    <label>Damage</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      bind:value={loadout.Gear.Weapon.Enhancers.Damage}
                      on:input={(e) => enforceEnhancerCap('weapon', 'Damage', e.target.value)}
                    />
                  </div>
                  <div class="enhancer-field">
                    <label>Accuracy</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      bind:value={loadout.Gear.Weapon.Enhancers.Accuracy}
                      on:input={(e) => enforceEnhancerCap('weapon', 'Accuracy', e.target.value)}
                    />
                  </div>
                  <div class="enhancer-field">
                    <label>Range</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      bind:value={loadout.Gear.Weapon.Enhancers.Range}
                      on:input={(e) => enforceEnhancerCap('weapon', 'Range', e.target.value)}
                    />
                  </div>
                  <div class="enhancer-field">
                    <label>Economy</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      bind:value={loadout.Gear.Weapon.Enhancers.Economy}
                      on:input={(e) => enforceEnhancerCap('weapon', 'Economy', e.target.value)}
                    />
                  </div>
                  <div class="enhancer-field">
                    <label>Skill Mod</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      bind:value={loadout.Gear.Weapon.Enhancers.SkillMod}
                      on:input={(e) => enforceEnhancerCap('weapon', 'SkillMod', e.target.value)}
                    />
                  </div>
                </div>
                <div class="panel-divider compact"></div>
                <div class="option-row">
                  <label class="checkbox-row">
                    <input type="checkbox" bind:checked={settings.onlyShowReasonableAmplifiers} />
                    <span>Include overcapped amplifiers up to</span>
                  </label>
                  <div class="option-input">
                    <input class="compact-input" type="number" min="0" max="100" bind:value={settings.overampCap} />
                    <span class="suffix">%</span>
                  </div>
                </div>
              </div>
            </div>
          </DataSection>
        </div>
        {#if !compareMode}
          <div class="mobile-panel" class:active={activeMobilePanel === 'armor'}>
            <DataSection title="Armor">
              <div class="panel-grid two-col">
              <div class="panel-block">
                <h3 class="panel-title">Armor Selection</h3>
                {#if loadout.Gear.Armor.ManageIndividual}
                  <div class="armor-grid">
                    <div class="armor-grid-header">Slot</div>
                    <div class="armor-grid-header">Armor</div>
                    <div class="armor-grid-header">Armor MU</div>
                    <div class="armor-grid-header">Plate</div>
                    <div class="armor-grid-header">Plate MU</div>
                    {#each armorSlots as slot}
                      <div class="armor-label">{slot}</div>
                      <button class="slot select-button" on:contextmenu={e => clearSlot(e, `armor-${slot}`)} on:click={() => openPicker(`armor-${slot}`)}>
                        {#if loadout?.Gear.Armor[slot].Name != null}
                          {loadout.Gear.Armor[slot].Name}
                        {:else}
                          <span class="placeholder-text">Select armor...</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Armor[slot].Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Armors[slot]} />
                        </div>
                      {:else}
                        <span class="placeholder-muted"></span>
                      {/if}
                      <button class="slot select-button" disabled={loadout?.Gear.Armor[slot].Name == null} on:contextmenu={e => clearSlot(e, `armorplating-${slot}`)} on:click={() => openPicker(`armorplating-${slot}`)}>
                        {#if loadout?.Gear.Armor[slot].Name != null}
                          {#if loadout?.Gear.Armor[slot].Plate?.Name != null}
                            {loadout.Gear.Armor[slot].Plate.Name}
                          {:else}
                            <span class="placeholder-text">Select plating...</span>
                          {/if}
                        {:else}
                          <span class="placeholder-muted">Choose armor first</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Armor[slot].Plate?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Plates[slot]} />
                        </div>
                      {:else}
                        <span class="placeholder-muted"></span>
                      {/if}
                    {/each}
                  </div>
                {:else}
                  <div class="form-grid">
                    <div class="form-label">Armor Set</div>
                    <button class="slot select-button" on:contextmenu={e => clearSlot(e, "armorset")} on:click={() => openPicker('armorset')}>
                      {#if loadout?.Gear.Armor.SetName != null}
                        {loadout.Gear.Armor.SetName}
                      {:else}
                        <span class="placeholder-text">Select an armor set...</span>
                      {/if}
                    </button>
                    {#if isLimitedName(loadout?.Gear.Armor.SetName)}
                      <div class="form-label">Armor Markup</div>
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.ArmorSet} />
                      </div>
                    {/if}
                    <div class="form-label">Plate Set</div>
                    <button class="slot select-button" disabled={loadout?.Gear.Armor.SetName == null} on:contextmenu={e => clearSlot(e, "armorplating")} on:click={() => openPicker('armorplating')}>
                      {#if loadout?.Gear.Armor.SetName != null}
                        {#if loadout?.Gear.Armor.PlateName != null}
                          {loadout.Gear.Armor.PlateName}
                        {:else}
                          <span class="placeholder-text">Select plating...</span>
                        {/if}
                      {:else}
                        <span class="placeholder-muted">Choose armor set first</span>
                      {/if}
                    </button>
                    {#if isLimitedName(loadout?.Gear.Armor.PlateName)}
                      <div class="form-label">Plate Markup</div>
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.PlateSet} />
                      </div>
                    {/if}
                  </div>
                {/if}
              </div>
              <div class="panel-block">
                <h3 class="panel-title">Enhancers & Options</h3>
                <div class="enhancer-grid">
                <div class="enhancer-field">
                  <label>Defense</label>
                  <input
                    type="number"
                    min="0"
                    max="10"
                    bind:value={loadout.Gear.Armor.Enhancers.Defense}
                    on:input={(e) => enforceEnhancerCap('armor', 'Defense', e.target.value)}
                  />
                </div>
                <div class="enhancer-field">
                  <label>Durability</label>
                  <input
                    type="number"
                    min="0"
                    max="10"
                    bind:value={loadout.Gear.Armor.Enhancers.Durability}
                    on:input={(e) => enforceEnhancerCap('armor', 'Durability', e.target.value)}
                  />
                </div>
                </div>
                <label class="checkbox-row">
                  <input type="checkbox" bind:checked={loadout.Gear.Armor.ManageIndividual} />
                  <span>Manage armor pieces individually</span>
                </label>
              </div>
              </div>
            </DataSection>
          </div>
          <div class="mobile-panel" class:active={activeMobilePanel === 'accessories'}>
            <DataSection title="Accessories & Buffs">
              <div class="accessory-panel">
                <div class="accessory-section">
                  <h3 class="panel-title">Rings & Pet</h3>
                  <div class="accessory-grid rings-pet-grid">
                    <div class="accessory-item">
                      <div class="form-label">Left Ring</div>
                      <button class="slot select-button" on:contextmenu={e => clearSlot(e, 'ring-left')} on:click={() => openPicker('ring-left')}>
                        {#if leftRing?.Name}
                          {leftRing.Name}
                        {:else}
                          <span class="placeholder-text">Select ring...</span>
                        {/if}
                      </button>
                    </div>
                    <div class="accessory-item">
                      <div class="form-label">Right Ring</div>
                      <button class="slot select-button" on:contextmenu={e => clearSlot(e, 'ring-right')} on:click={() => openPicker('ring-right')}>
                        {#if rightRing?.Name}
                          {rightRing.Name}
                        {:else}
                          <span class="placeholder-text">Select ring...</span>
                        {/if}
                      </button>
                    </div>
                    <div class="accessory-item pet-select">
                      <div class="form-label">Pet</div>
                      <button
                        class="slot select-button"
                        class:pet-active={!!loadout?.Gear?.Pet?.Name}
                        on:contextmenu={e => clearSlot(e, 'pet')}
                        on:click={() => openPicker('pet')}
                      >
                        {#if loadout?.Gear?.Pet?.Name}
                          {loadout.Gear.Pet.Name}
                        {:else}
                          <span class="placeholder-text">Select pet...</span>
                        {/if}
                      </button>
                    </div>
                  </div>
                  <div class="pet-abilities">
                    {#if !loadout?.Gear?.Pet?.Name}
                      <div class="pet-abilities-empty">Select a pet to view abilities.</div>
                    {:else if activePetEffects.length === 0}
                      <div class="pet-abilities-empty">No abilities available for this pet.</div>
                    {:else}
                      <div class="pet-effect-grid">
                        {#each activePetEffects as effect, index}
                          {@const effectName = effect?.Name || `Effect ${index + 1}`}
                          {@const strength = getPetEffectStrength(effect)}
                          {@const unit = effect?.Properties?.Unit || ''}
                          {@const upkeep = effect?.Properties?.NutrioConsumptionPerHour}
                          {@const level = effect?.Properties?.Unlock?.Level}
                          {@const effectKey = `${effectName}::${strength ?? 0}`}
                          <button
                            class="pet-effect-card"
                            class:active={loadout?.Gear?.Pet?.Effect === effectKey || loadout?.Gear?.Pet?.Effect === effectName}
                            disabled={!loadout?.Gear?.Pet?.Name}
                            on:click={() => togglePetEffect(effectKey)}
                          >
                            <div class="pet-effect-name">{effectName}</div>
                            <div class="pet-effect-meta">
                              <div class="pet-effect-stat">
                                <span class="pet-effect-label">Strength</span>
                                <span class="pet-effect-value">{strength != null ? `${strength}${unit}` : '—'}</span>
                              </div>
                              <div class="pet-effect-stat">
                                <span class="pet-effect-label">Upkeep</span>
                                <span class="pet-effect-value">{upkeep != null ? `${upkeep}/h` : 'N/A'}</span>
                              </div>
                              <div class="pet-effect-stat">
                                <span class="pet-effect-label">Unlock</span>
                                <span class="pet-effect-value">{level != null ? `Lv ${level}` : '—'}</span>
                              </div>
                            </div>
                          </button>
                        {/each}
                      </div>
                    {/if}
                  </div>
                </div>
                <div class="accessory-section">
                  <div class="accessory-section-header">
                    <h3 class="panel-title">Clothing</h3>
                    <button class="add-accessory" on:click={() => openPicker('clothing')}>Add Clothing</button>
                  </div>
                  <div class="clothing-hint">Slots are unique. Picking a piece for an occupied slot replaces it.</div>
                  {#if clothingReplaceNotice}
                    <div class="clothing-warning">{clothingReplaceNotice}</div>
                  {/if}
                  {#if selectedClothing.length === 0}
                    <div class="clothing-empty">No clothing selected yet.</div>
                  {:else}
                    <div class="clothing-list">
                      {#each selectedClothing as entry}
                        {@const item = getClothingItem(entry.Name)}
                        <div class="clothing-item">
                          <div class="clothing-main">
                            <div class="clothing-name">{entry.Name}</div>
                            <div class="clothing-meta">
                              <span class="clothing-slot">{entry.Slot}</span>
                              <span class="clothing-effects">{getClothingEffectLabel(item)}</span>
                            </div>
                          </div>
                          <button class="clothing-remove" on:click={() => removeClothingItem(entry.Name, entry.Slot)}>Remove</button>
                        </div>
                      {/each}
                    </div>
                  {/if}
                </div>
                <div class="accessory-section">
                  <div class="accessory-section-header">
                    <h3 class="panel-title">Consumables</h3>
                    <button class="add-accessory" on:click={() => openPicker('consumable')}>Add Consumable</button>
                  </div>
                  <div class="clothing-hint">Only the strongest consumable effect per type is applied.</div>
                  {#if selectedConsumables.length === 0}
                    <div class="clothing-empty">No consumables selected yet.</div>
                  {:else}
                    <div class="clothing-list">
                      {#each selectedConsumables as entry}
                        {@const entryName = entry?.Name || entry}
                        {@const item = getConsumableItem(entryName)}
                        <div class="clothing-item">
                          <div class="clothing-main">
                            <div class="clothing-name">{entryName}</div>
                            <div class="clothing-meta">
                              <span class="clothing-slot">{item?.Properties?.Type ?? 'Consumable'}</span>
                              <span class="clothing-effects">{formatEffectCount(getConsumableEffectCount(item))}</span>
                            </div>
                          </div>
                          <button class="clothing-remove" on:click={() => removeConsumableItem(entryName)}>Remove</button>
                        </div>
                      {/each}
                    </div>
                  {/if}
                </div>
              </div>
            </DataSection>
          </div>
        {/if}

      {:else}
        <div class="info">
          <h2>Loadout Manager</h2>
          <p>Create or select an existing loadout on the left.</p>
          <p class="instructions">
            Instructions:<br />
            <br />
            - Click "New" to get started.<br />
            - Left-click to select gear.<br />
            - Right-click to clear a slot.<br />
            - Use the Settings panel to adjust skills and bonuses.<br />
            - Compare loadouts with the Compare button in the header.<br />
            <br />
            Local loadouts remain until you clear browser storage. Export them if you want a backup.
          </p>
        </div>
      {/if}
    </article>
      </div>
    </div>
  </div>
  {/if}
  {/if}
</WikiPage>

{#if showPickerDialog && pickerConfig}
  <div class="dialog-backdrop picker-backdrop" on:click={closePicker} on:keydown={(e) => e.key === 'Escape' && closePicker()}>
    <div class="dialog picker-dialog" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="picker-dialog-title">
      <div class="dialog-header">
        <h3 id="picker-dialog-title">{pickerConfig.title}</h3>
        <button class="close-btn" on:click={closePicker} aria-label="Close dialog">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="dialog-body picker-content">
        {#if showPickerPreview && pickerPreviewRow}
          {@const previewLink = getPickerItemLink(activePicker, pickerPreviewItem)}
          {@const previewSections = getPickerPreviewSections(activePicker, pickerPreviewItem, pickerPreviewRow)}
          <div class="picker-preview">
            <div class="picker-preview-header">
              <div class="picker-preview-title">{getPickerPreviewTitle(pickerPreviewRow)}</div>
              {#if previewLink && !isMobileLayout}
                <a class="picker-preview-link" href={previewLink} target="_blank" rel="noopener noreferrer">Open item</a>
              {/if}
            </div>
            <div class="picker-preview-sections" class:single={previewSections.length === 1}>
              {#each previewSections as section}
                <div class="picker-preview-section" class:compact={section.compact}>
                  <div class="picker-preview-section-title">{section.title}</div>
                  {#if section.rows?.length}
                    <div class="picker-preview-grid">
                      {#each section.rows as info}
                      <div class="picker-preview-label stat-label">{info.label}</div>
                      <div class="picker-preview-value stat-value">{info.value}</div>
                      {/each}
                    </div>
                  {/if}
                  {#if section.effectsGroups?.length}
                    <div class:effects-compact={section.compact} class:effects-hide-title={section.hideEffectTitle}>
                      {#each section.effectsGroups as group}
                        <EffectsEditor
                          effects={group.effects}
                          availableEffects={effectsCatalog}
                          effectType={group.effectType}
                          title={group.title}
                          showEmpty={false}
                        />
                      {/each}
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {:else}
          <div class="picker-table">
            <FancyTable
              columns={pickerConfig.columns}
              data={pickerConfig.rows}
              rowHeight={pickerRowHeight}
              pageSize={60}
              searchable={true}
              sortable={true}
              stickyHeader={true}
              emptyMessage="No items found"
              on:rowClick={handlePickerRowClick}
            />
          </div>
        {/if}
      </div>
      {#if showPickerPreview && pickerPreviewRow}
        <div class="dialog-footer">
          <button class="dialog-btn secondary" on:click={returnToPickerList}>Back</button>
          <button class="dialog-btn" on:click={confirmPickerSelection}>Select</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .picker-dialog {
    width: min(1100px, 96vw);
    max-height: 90vh;
    display: flex;
    flex-direction: column;
  }

  .picker-dialog .dialog-body {
    flex: 1 1 auto;
    min-height: 0;
    overflow: auto;
  }

  .picker-table {
    min-height: 0;
  }

  .picker-preview {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .picker-preview-sections {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }

  .picker-preview-sections.single {
    grid-template-columns: 1fr;
  }

  .picker-preview-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 6px 12px;
    grid-auto-flow: row;
  }

  .picker-preview-title {
    word-break: break-word;
  }

  @media (max-width: 900px) {
    .picker-dialog {
      width: 96vw;
      max-height: 92vh;
    }

    .picker-preview-sections {
      grid-template-columns: 1fr;
    }

    .picker-preview-grid {
      grid-template-columns: minmax(120px, 1fr) max-content;
    }
  }
</style>

{#if showImportSourceDialog}
  <div class="dialog-backdrop" on:click={() => showImportSourceDialog = false} on:keydown={(e) => e.key === 'Escape' && (showImportSourceDialog = false)}>
    <div class="dialog dialog-compact" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="import-source-title">
      <div class="dialog-header">
        <h3 id="import-source-title">Import Loadout</h3>
        <button class="close-btn" on:click={() => showImportSourceDialog = false} aria-label="Close dialog">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="dialog-body">
        <p class="share-hint">File imports are saved locally.</p>
        {#if !isLoggedIn}
          <p class="share-hint">Log in to import local loadouts to your account.</p>
        {/if}
      </div>
      <div class="dialog-footer">
        <button class="dialog-btn secondary" on:click={() => showImportSourceDialog = false}>Close</button>
        {#if isLoggedIn}
          <button class="dialog-btn secondary" on:click={handleImportLocal} disabled={localLoadouts.length === 0}>
            Import local ({localLoadouts.length})
          </button>
        {/if}
        <button class="dialog-btn" on:click={handleImportFromFile}>Import from file</button>
      </div>
    </div>
  </div>
{/if}



{#if showShareDialog}
  <div class="dialog-backdrop" on:click={() => showShareDialog = false} on:keydown={(e) => e.key === 'Escape' && (showShareDialog = false)}>
    <div class="dialog dialog-compact" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="share-dialog-title">
      <div class="dialog-header">
        <h3 id="share-dialog-title">Share Loadout</h3>
        <button class="close-btn" on:click={() => showShareDialog = false} aria-label="Close dialog">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="dialog-body">
        <label class="toggle-row">
          <input type="checkbox" bind:checked={sharePublic} on:change={handleShareToggle} />
          <span>Public link</span>
        </label>
        {#if sharePublic}
          <div class="share-link-row">
            <input type="text" readonly value={shareLink} />
            <button
              type="button"
              class="btn-copy"
              class:copied={shareCopyStatus === 'Copied'}
              class:error={shareCopyStatus === 'Copy failed'}
              on:click={handleCopyShareLink}
              disabled={!shareLink}
            >{shareCopyStatus || 'Copy'}</button>
          </div>
        {:else}
          <p class="share-hint">Enable public link to generate a shareable URL.</p>
        {/if}
      </div>
      <div class="dialog-footer">
        <button class="dialog-btn secondary" on:click={() => showShareDialog = false}>Cancel</button>
        <button class="dialog-btn" on:click={applyShareSettings} disabled={!loadout}>Ok</button>
      </div>
    </div>
  </div>
{/if}

{#if showImportDialog}
  <div class="dialog-backdrop" on:click={() => showImportDialog = false} on:keydown={(e) => e.key === 'Escape' && (showImportDialog = false)}>
    <div class="dialog dialog-compact" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="import-dialog-title">
      <div class="dialog-header">
        <h3 id="import-dialog-title">Import Local Loadouts</h3>
        <button class="close-btn" on:click={() => showImportDialog = false} aria-label="Close dialog">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="dialog-body">
        {#if importSuccess}
          <p>Import completed. Your local loadouts have been moved online.</p>
        {:else}
          <p>Import {localLoadouts.length} local loadout(s) into your account?</p>
          <p class="share-hint">This will clear your local list after a successful import.</p>
          {#if importError}
            <p class="dialog-error">{importError}</p>
          {/if}
        {/if}
      </div>
      <div class="dialog-footer">
        <button class="dialog-btn secondary" on:click={() => showImportDialog = false} disabled={importInProgress}>Close</button>
        {#if !importSuccess}
          <button class="dialog-btn" on:click={importLocalLoadouts} disabled={importInProgress || localLoadouts.length === 0}>
            {importInProgress ? 'Importing...' : 'Import'}
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

{#if showDeleteDialog}
<div class="dialog-backdrop" on:click={cancelDelete} on:keydown={(e) => e.key === 'Escape' && cancelDelete()}>
  <div class="dialog" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="delete-dialog-title">
    <div class="dialog-header">
      <h3 id="delete-dialog-title">Delete Loadout</h3>
    </div>
    <div class="dialog-body">
      <p>Are you sure you want to delete this loadout? This action cannot be undone.</p>
    </div>
    <div class="dialog-footer">
      <button class="dialog-btn secondary" on:click={cancelDelete}>Cancel</button>
      <button class="dialog-btn danger" on:click={deleteActiveLoadout}>Delete</button>
    </div>
  </div>
</div>
{/if}


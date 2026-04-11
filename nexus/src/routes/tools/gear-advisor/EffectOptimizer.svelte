<!--
  @component EffectOptimizer
  Main orchestrator for the Effect Optimizer gear advisor tool.
  Lets users target specific equipment effects and find optimal item combinations.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { SvelteSet } from 'svelte/reactivity';
  import { createPreference } from '$lib/preferences.js';
  import { fetchExchangeWapByName, fetchInGamePrices, fetchInventoryMarkups } from '$lib/markupSources.js';
  import { buildEffectCaps } from '$lib/utils/loadoutEffects.js';
  import { hasCondition } from '$lib/shopUtils.js';
  import EffectTargetPanel from './EffectTargetPanel.svelte';
  import EffectSlotCard from './EffectSlotCard.svelte';
  import EffectTotalsBar from './EffectTotalsBar.svelte';
  import EffectSuggestionPanel from './EffectSuggestionPanel.svelte';
  import EffectSetCompare from './EffectSetCompare.svelte';
  import SlotSuggestionDialog from './SlotSuggestionDialog.svelte';
  import OptimizerDialog from './OptimizerDialog.svelte';
  import {
    filterRings,
    filterArmorSetsWithEffects,
    collectAllEffects,
    aggregateEffects,
    findBestCombinations,
    suggestForSlot,
    suggestFromList,
    buildDefaultSetName,
    extractArmorSetEffects,
    extractPetEffect
  } from './effectOptimizer.js';

  let {
    clothings = [],
    pets = [],
    effectsCatalog = [],
    armorSets = [],
    weapons = [],
    weaponAmplifiers = [],
    weaponVisionAttachments = [],
    absorbers = [],
    mindforceImplants = []
  } = $props();

  const alphabetical = (a, b) => (a?.Name || '').localeCompare(b?.Name || '', undefined, { numeric: true });

  // ===== Derived entity lists =====
  let leftRings = $derived(filterRings(clothings, 'left').sort(alphabetical));
  let rightRings = $derived(filterRings(clothings, 'right').sort(alphabetical));
  let armorSetsFiltered = $derived(filterArmorSetsWithEffects(armorSets).sort(alphabetical));
  let petsSorted = $derived([...(pets || [])].sort(alphabetical));
  const hasEffects = (item) => item?.EffectsOnEquip?.length > 0;
  let weaponsSorted = $derived(
    (weapons || []).filter(x => x.Properties?.Class !== 'Attached' && x.Properties?.Class !== 'Stationary' && hasEffects(x)).sort(alphabetical)
  );
  let amplifiersSorted = $derived(
    (weaponAmplifiers || []).filter(x => x.Properties?.Type !== 'Matrix' && hasEffects(x)).sort(alphabetical)
  );
  let visionAttachmentsSorted = $derived((weaponVisionAttachments || []).filter(hasEffects).sort(alphabetical));
  let scopesSorted = $derived(visionAttachmentsSorted.filter(x => x.Properties?.Type === 'Scope'));
  let sightsSorted = $derived(visionAttachmentsSorted.filter(x => x.Properties?.Type === 'Sight'));
  let scopeSightsSorted = $derived(sightsSorted);
  let absorbersSorted = $derived((absorbers || []).filter(hasEffects).sort(alphabetical));
  let implantsSorted = $derived((mindforceImplants || []).filter(hasEffects).sort(alphabetical));

  // Non-ring clothing with effects, grouped by slot
  let clothingSlots = $derived.by(() => {
    const slots = new Map();
    for (const item of (clothings || [])) {
      const slot = item?.Properties?.Slot || '';
      if (/ring|finger/i.test(slot)) continue;
      if (!item.EffectsOnEquip?.length) continue;
      if (!slots.has(slot)) slots.set(slot, []);
      slots.get(slot).push(item);
    }
    for (const [, items] of slots) items.sort(alphabetical);
    return slots;
  });

  let effectCaps = $derived(buildEffectCaps(effectsCatalog));

  // Entity lookup for collectAllEffects
  let entityLookup = $derived({
    leftRings,
    rightRings,
    armorSets: armorSetsFiltered,
    pets: petsSorted,
    weapon: weaponsSorted,
    amplifier: amplifiersSorted,
    scope: scopesSorted,
    scopeSight: scopeSightsSorted,
    sight: sightsSorted,
    absorber: absorbersSorted,
    implant: implantsSorted,
    clothings
  });

  // ===== State =====
  let targets = $state({});
  let priorities = $state([]);
  let leftRing = $state(null);
  let rightRing = $state(null);
  let armorSet = $state(null);
  let armorSetPieces = $state(7);
  let pet = $state(null);
  let petActiveEffect = $state(null);

  // Secondary slots
  let showSecondary = $state(false);
  let secondaryWeapon = $state(null);
  let secondaryAmplifier = $state(null);
  let secondaryScope = $state(null);
  let secondaryScopeSight = $state(null);
  let secondarySight = $state(null);
  let secondaryAbsorber = $state(null);
  let secondaryImplant = $state(null);
  let secondaryClothing = $state({});
  let clothingMuSources = $state({});
  let clothingMuValues = $state({});

  // MU configs per slot
  let muSources = $state({
    leftRing: 'custom', rightRing: 'custom', armorSet: 'custom', pet: 'custom',
    weapon: 'custom', amplifier: 'custom',
    scope: 'custom', scopeSight: 'custom', sight: 'custom',
    absorber: 'custom', implant: 'custom'
  });
  let muValues = $state({
    leftRing: 100, rightRing: 100, armorSet: 100, pet: 0,
    weapon: 100, amplifier: 100,
    scope: 100, scopeSight: 100, sight: 100,
    absorber: 100, implant: 100
  });

  // Settings
  let overcapMode = $state('punish');

  // Optimizer
  let showSuggestions = $state(false);
  let suggestionResults = $state([]);
  let suggestionLoading = $state(false);
  // Slots that participate in optimization. Everything NOT in this set is
  // treated as locked (its current item contributes effects to the baseline).
  const DEFAULT_UNLOCKED = ['leftRing', 'rightRing', 'armorSet', 'pet'];
  let unlockedSlotIds = $state(new SvelteSet(DEFAULT_UNLOCKED));
  let optimizerDialogOpen = $state(false);

  // Per-slot suggestion dialog state
  let suggestDialogOpen = $state(false);
  let suggestDialogSlotKey = $state(null);
  let suggestDialogLabel = $state('');
  let suggestDialogResults = $state([]);
  let suggestDialogLoading = $state(false);
  let suggestDialogMode = $state('contextual');

  // Saved sets
  let savedSets = $state([]);
  let activeSetId = $state(null);

  // Markup data
  let markupData = $state({ wapByName: new Map(), nameToId: new Map(), ingameMap: new Map(), inventoryMap: new Map() });

  // Preference persistence
  let prefLoaded = $state(false);
  const pref = createPreference('gear-advisor.effect-optimizer', null, { debounceMs: 600 });

  onMount(async () => {
    const userId = $page.data?.user?.id ?? null;
    await pref.load(userId);

    let stored;
    pref.subscribe(v => stored = v)();
    if (stored) {
      targets = stored.targets || {};
      priorities = stored.priorities || [];
      leftRing = stored.leftRing ?? null;
      rightRing = stored.rightRing ?? null;
      armorSet = stored.armorSet ?? null;
      armorSetPieces = stored.armorSetPieces ?? 7;
      pet = stored.pet ?? null;
      petActiveEffect = stored.petActiveEffect ?? null;
      showSecondary = stored.showSecondary ?? false;
      secondaryWeapon = stored.secondaryWeapon ?? null;
      secondaryAmplifier = stored.secondaryAmplifier ?? null;
      secondaryScope = stored.secondaryScope ?? null;
      secondaryScopeSight = stored.secondaryScopeSight ?? null;
      secondarySight = stored.secondarySight ?? null;
      // Migrate legacy single vision-attachment slot by Type
      if (stored.secondaryVisionAttachment && !secondaryScope && !secondarySight) {
        const legacy = (weaponVisionAttachments || []).find(v => v.Name === stored.secondaryVisionAttachment);
        if (legacy?.Properties?.Type === 'Scope') secondaryScope = legacy.Name;
        else if (legacy?.Properties?.Type === 'Sight') secondarySight = legacy.Name;
      }
      secondaryAbsorber = stored.secondaryAbsorber ?? null;
      secondaryImplant = stored.secondaryImplant ?? null;
      secondaryClothing = stored.secondaryClothing || {};
      clothingMuSources = stored.clothingMuSources || {};
      clothingMuValues = stored.clothingMuValues || {};
      muSources = { ...muSources, ...(stored.muSources || {}) };
      muValues = { ...muValues, ...(stored.muValues || {}) };
      overcapMode = stored.overcapMode ?? 'punish';
      savedSets = stored.savedSets || [];
      activeSetId = stored.activeSetId ?? null;
      showSuggestions = stored.showSuggestions ?? false;
      if (Array.isArray(stored.unlockedSlotIds)) {
        unlockedSlotIds = new SvelteSet(stored.unlockedSlotIds);
      }
    }
    prefLoaded = true;

    // Load markup sources (non-blocking)
    Promise.all([
      fetchExchangeWapByName(),
      fetchInGamePrices(),
      userId ? fetchInventoryMarkups() : Promise.resolve(new Map())
    ]).then(([exchange, ingame, inventory]) => {
      markupData = {
        wapByName: exchange.wapByName,
        nameToId: exchange.nameToId,
        ingameMap: ingame,
        inventoryMap: inventory
      };
    });
  });

  // Persist state
  $effect(() => {
    // Read all state to track dependencies
    const _t = targets; const _pr = priorities;
    const _lr = leftRing; const _rr = rightRing;
    const _as = armorSet; const _asp = armorSetPieces;
    const _p = pet; const _pae = petActiveEffect;
    const _ss = showSecondary;
    const _sw = secondaryWeapon; const _sa = secondaryAmplifier;
    const _sco = secondaryScope; const _ssg = secondaryScopeSight; const _ssi = secondarySight;
    const _sab = secondaryAbsorber;
    const _si = secondaryImplant; const _sc = secondaryClothing;
    const _cms = clothingMuSources; const _cmv = clothingMuValues;
    const _mu = muSources; const _mv = muValues;
    const _oc = overcapMode; const _sets = savedSets;
    const _asi = activeSetId;
    const _show = showSuggestions;
    const _unlocked = [...unlockedSlotIds];
    if (!prefLoaded) return;
    pref.set({
      targets: _t, priorities: _pr,
      leftRing: _lr, rightRing: _rr,
      armorSet: _as, armorSetPieces: _asp,
      pet: _p, petActiveEffect: _pae,
      showSecondary: _ss,
      secondaryWeapon: _sw, secondaryAmplifier: _sa,
      secondaryScope: _sco, secondaryScopeSight: _ssg, secondarySight: _ssi,
      secondaryAbsorber: _sab,
      secondaryImplant: _si, secondaryClothing: _sc,
      clothingMuSources: _cms, clothingMuValues: _cmv,
      muSources: _mu, muValues: _mv,
      overcapMode: _oc, savedSets: _sets,
      activeSetId: _asi, showSuggestions: _show,
      unlockedSlotIds: _unlocked
    });
  });

  // ===== Current slots object =====
  let currentSlots = $derived({
    leftRing,
    rightRing,
    armorSet,
    armorSetPieces,
    pet,
    petActiveEffect,
    secondary: {
      weapon: secondaryWeapon,
      amplifier: secondaryAmplifier,
      scope: secondaryScope,
      scopeSight: secondaryScopeSight,
      sight: secondarySight,
      absorber: secondaryAbsorber,
      implant: secondaryImplant,
      clothing: secondaryClothing
    }
  });

  // ===== Aggregated effects =====
  let allItemEffects = $derived(collectAllEffects(currentSlots, entityLookup));
  let effectSummary = $derived(aggregateEffects(allItemEffects, effectsCatalog, effectCaps));

  // ===== Total cost =====
  function isAbsoluteMarkup(item, forceAbsolute = false) {
    if (forceAbsolute) return true;
    if (hasCondition(item)) return true;
    const tt = item.Properties?.Economy?.MaxTT ?? item.Properties?.MaxTT ?? null;
    return tt != null && tt > 0;
  }

  function getItemCost(entityList, name, muSource, muCustom, forceAbsolute = false) {
    if (!name) return null;
    const item = (entityList || []).find(e => e.Name === name);
    if (!item) return null;
    const tt = item.Properties?.Economy?.MaxTT ?? item.Properties?.MaxTT ?? null;
    if (forceAbsolute) {
      const mu = muCustom ?? 0;
      return { tt: tt ?? 0, mu, cost: (tt ?? 0) + mu, isAbsolute: true };
    }
    if (tt == null || tt <= 0) return null;
    const isAbsolute = isAbsoluteMarkup(item);
    let mu = muCustom ?? (isAbsolute ? 0 : 100);
    if (muSource === 'inventory' && markupData.inventoryMap) {
      const id = markupData.nameToId?.get(name);
      if (id != null && markupData.inventoryMap.has(id)) mu = markupData.inventoryMap.get(id);
    } else if (muSource === 'ingame' && markupData.ingameMap?.has(name)) {
      mu = markupData.ingameMap.get(name);
    } else if (muSource === 'exchange' && markupData.wapByName?.has(name)) {
      mu = markupData.wapByName.get(name);
    }
    // Absolute: cost = TT + MU (PED). Relative: cost = TT * MU% / 100
    const cost = isAbsolute ? tt + mu : tt * mu / 100;
    return { tt, mu, cost, isAbsolute };
  }

  let totalCost = $derived.by(() => {
    const costs = [];
    const add = (list, name, src, custom, forceAbsolute = false) => {
      const c = getItemCost(list, name, src, custom, forceAbsolute);
      if (c) costs.push({ name, ...c });
    };
    add(leftRings, leftRing, muSources.leftRing, muValues.leftRing);
    add(rightRings, rightRing, muSources.rightRing, muValues.rightRing);
    add(petsSorted, pet, muSources.pet, muValues.pet, true);
    add(weaponsSorted, secondaryWeapon, muSources.weapon, muValues.weapon);
    add(amplifiersSorted, secondaryAmplifier, muSources.amplifier, muValues.amplifier);
    add(scopesSorted, secondaryScope, muSources.scope, muValues.scope);
    add(scopeSightsSorted, secondaryScopeSight, muSources.scopeSight, muValues.scopeSight);
    add(sightsSorted, secondarySight, muSources.sight, muValues.sight);
    add(absorbersSorted, secondaryAbsorber, muSources.absorber, muValues.absorber);
    add(implantsSorted, secondaryImplant, muSources.implant, muValues.implant);
    const total = costs.reduce((sum, c) => sum + c.cost, 0);
    return { items: costs, total };
  });

  // ===== Optimizer handlers =====

  // Build effects for a currently-equipped item in a given slot (for baseline when locked)
  function currentEffectsForSlot(key) {
    if (key === 'leftRing' && leftRing) {
      const item = leftRings.find(r => r.Name === leftRing);
      return item?.EffectsOnEquip || [];
    }
    if (key === 'rightRing' && rightRing) {
      const item = rightRings.find(r => r.Name === rightRing);
      return item?.EffectsOnEquip || [];
    }
    if (key === 'armorSet' && armorSet) {
      const set = armorSetsFiltered.find(s => s.Name === armorSet);
      return set ? extractArmorSetEffects(set, armorSetPieces) : [];
    }
    if (key === 'pet' && pet && petActiveEffect) {
      const petEntity = petsSorted.find(p => p.Name === pet);
      if (!petEntity) return [];
      const eff = extractPetEffect(petEntity, petActiveEffect);
      return eff ? [eff] : [];
    }
    if (key === 'weapon' && secondaryWeapon) {
      const w = weaponsSorted.find(x => x.Name === secondaryWeapon);
      return w?.EffectsOnEquip || [];
    }
    if (key === 'amplifier' && secondaryAmplifier) {
      const a = amplifiersSorted.find(x => x.Name === secondaryAmplifier);
      return a?.EffectsOnEquip || [];
    }
    if (key === 'scope' && secondaryScope) {
      const v = scopesSorted.find(x => x.Name === secondaryScope);
      return v?.EffectsOnEquip || [];
    }
    if (key === 'scopeSight' && secondaryScopeSight) {
      const v = scopeSightsSorted.find(x => x.Name === secondaryScopeSight);
      return v?.EffectsOnEquip || [];
    }
    if (key === 'sight' && secondarySight) {
      const v = sightsSorted.find(x => x.Name === secondarySight);
      return v?.EffectsOnEquip || [];
    }
    if (key === 'absorber' && secondaryAbsorber) {
      const ab = absorbersSorted.find(x => x.Name === secondaryAbsorber);
      return ab?.EffectsOnEquip || [];
    }
    if (key === 'implant' && secondaryImplant) {
      const im = implantsSorted.find(x => x.Name === secondaryImplant);
      return im?.EffectsOnEquip || [];
    }
    if (key.startsWith('clothing:')) {
      const slotName = key.slice('clothing:'.length);
      const name = secondaryClothing[slotName];
      if (!name) return [];
      const item = (clothingSlots.get(slotName) || []).find(c => c.Name === name);
      return item?.EffectsOnEquip || [];
    }
    return [];
  }

  // Enumerate all slot keys currently available to optimize over
  let allSlotKeys = $derived.by(() => {
    const keys = ['leftRing', 'rightRing', 'armorSet', 'pet'];
    if (weaponsSorted.length) keys.push('weapon');
    if (amplifiersSorted.length) keys.push('amplifier');
    if (scopesSorted.length) keys.push('scope');
    if (scopeSightsSorted.length) keys.push('scopeSight');
    if (sightsSorted.length) keys.push('sight');
    if (absorbersSorted.length) keys.push('absorber');
    if (implantsSorted.length) keys.push('implant');
    for (const slotName of clothingSlots.keys()) keys.push('clothing:' + slotName);
    return keys;
  });

  function buildSlotConfigs() {
    const configs = {};
    const slotItems = {
      leftRing: { type: 'ring', items: leftRings, pairExclude: 'rightRing' },
      rightRing: { type: 'ring', items: rightRings, pairExclude: 'leftRing' },
      armorSet: { type: 'armorSet', items: armorSetsFiltered, pieceCount: armorSetPieces },
      pet: { type: 'pet', items: petsSorted },
      weapon: { type: 'equipment', items: weaponsSorted },
      amplifier: { type: 'equipment', items: amplifiersSorted },
      scope: { type: 'equipment', items: scopesSorted },
      scopeSight: { type: 'equipment', items: scopeSightsSorted },
      sight: { type: 'equipment', items: sightsSorted },
      absorber: { type: 'equipment', items: absorbersSorted },
      implant: { type: 'equipment', items: implantsSorted },
    };

    for (const key of allSlotKeys) {
      const locked = !unlockedSlotIds.has(key);
      let base = slotItems[key];
      if (!base && key.startsWith('clothing:')) {
        const slotName = key.slice('clothing:'.length);
        base = { type: 'equipment', items: clothingSlots.get(slotName) || [] };
      }
      if (!base) continue;
      configs[key] = {
        type: base.type,
        items: locked ? [] : base.items,
        locked,
        currentEffects: locked ? currentEffectsForSlot(key) : [],
        pieceCount: base.pieceCount,
        pairExclude: base.pairExclude,
      };
    }
    return configs;
  }

  function handleFillAll() {
    if (Object.keys(targets).length === 0) return;
    suggestionLoading = true;
    setTimeout(() => {
      const slotConfigs = buildSlotConfigs();
      suggestionResults = findBestCombinations(
        targets,
        slotConfigs,
        effectsCatalog,
        effectCaps,
        { overcapMode, priorities, armorSetPieces, maxResults: 50, beamWidth: 250 }
      );
      suggestionLoading = false;
      showSuggestions = true;
    }, 10);
  }

  function applySlotValue(key, value) {
    const name = (value && typeof value === 'object') ? value.name : value;
    if (key === 'leftRing') leftRing = name;
    else if (key === 'rightRing') rightRing = name;
    else if (key === 'armorSet') armorSet = name;
    else if (key === 'pet') {
      pet = name;
      if (value && typeof value === 'object' && value.effectKey) petActiveEffect = value.effectKey;
    }
    else if (key === 'weapon') secondaryWeapon = name;
    else if (key === 'amplifier') secondaryAmplifier = name;
    else if (key === 'scope') secondaryScope = name;
    else if (key === 'scopeSight') secondaryScopeSight = name;
    else if (key === 'sight') secondarySight = name;
    else if (key === 'absorber') secondaryAbsorber = name;
    else if (key === 'implant') secondaryImplant = name;
    else if (key.startsWith('clothing:')) {
      const slotName = key.slice('clothing:'.length);
      secondaryClothing = { ...secondaryClothing, [slotName]: name };
    }
  }

  function handleApplySuggestion(result) {
    for (const [key, value] of Object.entries(result.items || {})) {
      applySlotValue(key, value);
    }
  }

  function handleSwapAlternative(resultIndex, slotKey, value) {
    const result = suggestionResults[resultIndex];
    if (!result) return;
    result.items = { ...result.items, [slotKey]: value };
    suggestionResults = [...suggestionResults];
  }

  function toggleSlotLock(slotKey) {
    if (unlockedSlotIds.has(slotKey)) unlockedSlotIds.delete(slotKey);
    else unlockedSlotIds.add(slotKey);
  }

  function setAllSlotsLocked(locked) {
    if (locked) {
      unlockedSlotIds.clear();
    } else {
      for (const k of allSlotKeys) unlockedSlotIds.add(k);
    }
  }

  function resetLocksToDefault() {
    unlockedSlotIds.clear();
    for (const k of DEFAULT_UNLOCKED) unlockedSlotIds.add(k);
  }

  const PRIMARY_SLOTS = new Set(['leftRing', 'rightRing', 'armorSet', 'pet']);

  // Map slot keys to entity lists for secondary slots
  const SECONDARY_ENTITY_MAP = {
    weapon: () => weaponsSorted,
    amplifier: () => amplifiersSorted,
    scope: () => scopesSorted,
    scopeSight: () => scopeSightsSorted,
    sight: () => sightsSorted,
    absorber: () => absorbersSorted,
    implant: () => implantsSorted,
  };

  let suggestDialogSlotType = $state('primary');
  let suggestDialogEntities = $state([]);
  let suggestDialogCurrentSlotEffects = $state([]);
  let suggestDialogCurrentSlotItemName = $state(null);
  let suggestDialogBaselineSummary = $state([]);

  function currentItemNameForSlot(key) {
    if (key === 'leftRing') return leftRing;
    if (key === 'rightRing') return rightRing;
    if (key === 'armorSet') return armorSet;
    if (key === 'pet') return pet;
    if (key === 'weapon') return secondaryWeapon;
    if (key === 'amplifier') return secondaryAmplifier;
    if (key === 'scope') return secondaryScope;
    if (key === 'scopeSight') return secondaryScopeSight;
    if (key === 'sight') return secondarySight;
    if (key === 'absorber') return secondaryAbsorber;
    if (key === 'implant') return secondaryImplant;
    if (key.startsWith('clothing:')) return secondaryClothing[key.slice('clothing:'.length)] || null;
    return null;
  }

  function handleSlotSuggest(slotKey, label, entityList) {
    if (Object.keys(targets).length === 0) return;
    suggestDialogSlotKey = slotKey;
    suggestDialogLabel = label || slotKey;
    suggestDialogOpen = true;
    suggestDialogSlotType = PRIMARY_SLOTS.has(slotKey) ? 'primary' : 'secondary';
    suggestDialogEntities = entityList || [];
    const currentEffs = currentEffectsForSlot(slotKey);
    suggestDialogCurrentSlotEffects = currentEffs;
    suggestDialogCurrentSlotItemName = currentItemNameForSlot(slotKey);
    // Baseline = aggregated effects from everything EXCEPT this slot
    const baselineEffs = allItemEffects.filter(e => !currentEffs.includes(e));
    suggestDialogBaselineSummary = aggregateEffects(baselineEffs, effectsCatalog, effectCaps);
    runSlotSuggestion(slotKey, suggestDialogMode);
  }

  function runSlotSuggestion(slotKey, mode) {
    suggestDialogLoading = true;
    setTimeout(() => {
      if (PRIMARY_SLOTS.has(slotKey)) {
        suggestDialogResults = suggestForSlot(
          slotKey, targets, currentSlots, entityLookup,
          effectsCatalog, effectCaps,
          { overcapMode, priorities, armorSetPieces, mode, maxResults: 30 }
        );
      } else {
        // Secondary/clothing: use suggestFromList with all current effects as context
        suggestDialogResults = suggestFromList(
          suggestDialogEntities, targets, allItemEffects,
          effectsCatalog, effectCaps,
          { overcapMode, priorities, mode, maxResults: 30 }
        );
      }
      suggestDialogLoading = false;
    }, 10);
  }

  // Re-run when mode changes
  $effect(() => {
    const _mode = suggestDialogMode;
    if (suggestDialogOpen && suggestDialogSlotKey) {
      runSlotSuggestion(suggestDialogSlotKey, _mode);
    }
  });

  function handleSuggestPick(result) {
    const slotKey = suggestDialogSlotKey;
    if (slotKey === 'leftRing') leftRing = result.name;
    else if (slotKey === 'rightRing') rightRing = result.name;
    else if (slotKey === 'armorSet') armorSet = result.name;
    else if (slotKey === 'pet') {
      pet = result.name;
      if (result.effectKey) petActiveEffect = result.effectKey;
    }
    else if (slotKey === 'weapon') secondaryWeapon = result.name;
    else if (slotKey === 'amplifier') secondaryAmplifier = result.name;
    else if (slotKey === 'scope') secondaryScope = result.name;
    else if (slotKey === 'scopeSight') secondaryScopeSight = result.name;
    else if (slotKey === 'sight') secondarySight = result.name;
    else if (slotKey === 'absorber') secondaryAbsorber = result.name;
    else if (slotKey === 'implant') secondaryImplant = result.name;
    else if (slotKey.startsWith('clothing:')) {
      const clothSlot = slotKey.slice('clothing:'.length);
      secondaryClothing = { ...secondaryClothing, [clothSlot]: result.name };
    }
  }

  function handleLoadSet(set) {
    if (!set.slots) return;
    leftRing = set.slots.leftRing ?? null;
    rightRing = set.slots.rightRing ?? null;
    armorSet = set.slots.armorSet ?? null;
    armorSetPieces = set.slots.armorSetPieces ?? 7;
    pet = set.slots.pet ?? null;
    petActiveEffect = set.slots.petActiveEffect ?? null;
    if (set.slots.secondary) {
      secondaryWeapon = set.slots.secondary.weapon ?? null;
      secondaryAmplifier = set.slots.secondary.amplifier ?? null;
      secondaryScope = set.slots.secondary.scope ?? null;
      secondaryScopeSight = set.slots.secondary.scopeSight ?? null;
      secondarySight = set.slots.secondary.sight ?? null;
      secondaryAbsorber = set.slots.secondary.absorber ?? null;
      secondaryImplant = set.slots.secondary.implant ?? null;
      secondaryClothing = set.slots.secondary.clothing || {};
    }
    if (set.targets) targets = { ...set.targets };
  }

  // (showSecondary kept for preference backwards compat but no longer controls visibility)
</script>

<div class="effect-optimizer">
  <!-- Left column: Saved sets + Suggestions -->
  <aside class="eo-left">
    <EffectSetCompare
      bind:savedSets
      bind:activeSetId
      currentSlots={currentSlots}
      currentTargets={targets}
      currentSummary={effectSummary}
      onload={handleLoadSet}
    />

    <div class="eo-left-box">
      <EffectSuggestionPanel
        results={suggestionResults}
        {targets}
        loading={suggestionLoading}
        onFillAll={handleFillAll}
        onApply={handleApplySuggestion}
        onSwapAlternative={handleSwapAlternative}
        onOpenDialog={() => (optimizerDialogOpen = true)}
      />
    </div>
  </aside>

  <!-- Right column: Configuration -->
  <div class="eo-main">
    <!-- Target Effects -->
    <section class="eo-section">
      <EffectTargetPanel
        bind:targets
        bind:priorities
        {effectsCatalog}
        {effectCaps}
      />
    </section>

    <!-- Overcap mode toggle -->
    <div class="eo-settings-row">
      <span class="setting-label">Overcap:</span>
      <div class="toggle-group">
        <button type="button" class="toggle-btn" class:active={overcapMode === 'reject'} onclick={() => overcapMode = 'reject'}>
          Reject
        </button>
        <button type="button" class="toggle-btn" class:active={overcapMode === 'punish'} onclick={() => overcapMode = 'punish'}>
          Penalize
        </button>
        <button type="button" class="toggle-btn" class:active={overcapMode === 'ignore'} onclick={() => overcapMode = 'ignore'}>
          Ignore
        </button>
      </div>
    </div>

    <!-- Primary Equipment Slots -->
    <section class="eo-section">
      <h3 class="eo-section-title">Equipment</h3>
      <div class="slots-grid">
        <EffectSlotCard
          label="Left Ring"
          slotType="ring"
          entities={leftRings}
          bind:selected={leftRing}
          {markupData}
          bind:markupSource={muSources.leftRing}
          bind:markupPercent={muValues.leftRing}
          {effectsCatalog}
          excludeName={rightRing}
          onsuggest={() => handleSlotSuggest('leftRing', 'Left Ring')}
          suggesting={false}
          open={unlockedSlotIds.has('leftRing')}
          onToggleOpen={() => toggleSlotLock('leftRing')}
        />
        <EffectSlotCard
          label="Right Ring"
          slotType="ring"
          entities={rightRings}
          bind:selected={rightRing}
          {markupData}
          bind:markupSource={muSources.rightRing}
          bind:markupPercent={muValues.rightRing}
          {effectsCatalog}
          excludeName={leftRing}
          onsuggest={() => handleSlotSuggest('rightRing', 'Right Ring')}
          suggesting={false}
          open={unlockedSlotIds.has('rightRing')}
          onToggleOpen={() => toggleSlotLock('rightRing')}
        />
        <EffectSlotCard
          label="Armor Set"
          slotType="armorSet"
          entities={armorSetsFiltered}
          bind:selected={armorSet}
          {markupData}
          bind:markupSource={muSources.armorSet}
          bind:markupPercent={muValues.armorSet}
          {effectsCatalog}
          bind:armorSetPieces
          onsuggest={() => handleSlotSuggest('armorSet', 'Armor Set')}
          suggesting={false}
          open={unlockedSlotIds.has('armorSet')}
          onToggleOpen={() => toggleSlotLock('armorSet')}
        />
        <EffectSlotCard
          label="Pet"
          slotType="pet"
          entities={petsSorted}
          bind:selected={pet}
          {markupData}
          bind:markupSource={muSources.pet}
          bind:markupPercent={muValues.pet}
          {effectsCatalog}
          bind:petActiveEffect
          onsuggest={() => handleSlotSuggest('pet', 'Pet')}
          suggesting={false}
          open={unlockedSlotIds.has('pet')}
          onToggleOpen={() => toggleSlotLock('pet')}
        />
      </div>
    </section>

    <!-- Additional Equipment -->
    <section class="eo-section">
      <h3 class="eo-section-title">Additional Equipment</h3>
      <div class="slots-grid">
        {#if weaponsSorted.length > 0}
          <EffectSlotCard
            label="Weapon"
            entities={weaponsSorted}
            bind:selected={secondaryWeapon}
            {markupData}
            bind:markupSource={muSources.weapon}
            bind:markupPercent={muValues.weapon}
            {effectsCatalog}
            compact
            onsuggest={() => handleSlotSuggest('weapon', 'Weapon', weaponsSorted)}
            open={unlockedSlotIds.has('weapon')}
            onToggleOpen={() => toggleSlotLock('weapon')}
          />
        {/if}
        {#if amplifiersSorted.length > 0}
          <EffectSlotCard
            label="Amplifier"
            entities={amplifiersSorted}
            bind:selected={secondaryAmplifier}
            {markupData}
            bind:markupSource={muSources.amplifier}
            bind:markupPercent={muValues.amplifier}
            {effectsCatalog}
            compact
            onsuggest={() => handleSlotSuggest('amplifier', 'Amplifier', amplifiersSorted)}
            open={unlockedSlotIds.has('amplifier')}
            onToggleOpen={() => toggleSlotLock('amplifier')}
          />
        {/if}
        {#if scopesSorted.length > 0}
          <EffectSlotCard
            label="Scope"
            entities={scopesSorted}
            bind:selected={secondaryScope}
            {markupData}
            bind:markupSource={muSources.scope}
            bind:markupPercent={muValues.scope}
            {effectsCatalog}
            compact
            onsuggest={() => handleSlotSuggest('scope', 'Scope', scopesSorted)}
            open={unlockedSlotIds.has('scope')}
            onToggleOpen={() => toggleSlotLock('scope')}
          />
        {/if}
        {#if scopeSightsSorted.length > 0}
          <EffectSlotCard
            label="Scope Sight"
            entities={scopeSightsSorted}
            bind:selected={secondaryScopeSight}
            {markupData}
            bind:markupSource={muSources.scopeSight}
            bind:markupPercent={muValues.scopeSight}
            {effectsCatalog}
            compact
            onsuggest={() => handleSlotSuggest('scopeSight', 'Scope Sight', scopeSightsSorted)}
            open={unlockedSlotIds.has('scopeSight')}
            onToggleOpen={() => toggleSlotLock('scopeSight')}
          />
        {/if}
        {#if sightsSorted.length > 0}
          <EffectSlotCard
            label="Sight"
            entities={sightsSorted}
            bind:selected={secondarySight}
            {markupData}
            bind:markupSource={muSources.sight}
            bind:markupPercent={muValues.sight}
            {effectsCatalog}
            compact
            onsuggest={() => handleSlotSuggest('sight', 'Sight', sightsSorted)}
            open={unlockedSlotIds.has('sight')}
            onToggleOpen={() => toggleSlotLock('sight')}
          />
        {/if}
        {#if absorbersSorted.length > 0}
          <EffectSlotCard
            label="Absorber"
            entities={absorbersSorted}
            bind:selected={secondaryAbsorber}
            {markupData}
            bind:markupSource={muSources.absorber}
            bind:markupPercent={muValues.absorber}
            {effectsCatalog}
            compact
            onsuggest={() => handleSlotSuggest('absorber', 'Absorber', absorbersSorted)}
            open={unlockedSlotIds.has('absorber')}
            onToggleOpen={() => toggleSlotLock('absorber')}
          />
        {/if}
        {#if implantsSorted.length > 0}
          <EffectSlotCard
            label="Implant"
            entities={implantsSorted}
            bind:selected={secondaryImplant}
            {markupData}
            bind:markupSource={muSources.implant}
            bind:markupPercent={muValues.implant}
            {effectsCatalog}
            compact
            onsuggest={() => handleSlotSuggest('implant', 'Implant', implantsSorted)}
            open={unlockedSlotIds.has('implant')}
            onToggleOpen={() => toggleSlotLock('implant')}
          />
        {/if}
      </div>
    </section>

    <!-- Clothing -->
    {#if clothingSlots.size > 0}
      <section class="eo-section">
        <h3 class="eo-section-title">Clothing</h3>
        <div class="slots-grid">
          {#each [...clothingSlots.entries()] as [slotName, items] (slotName)}
            <EffectSlotCard
              label={slotName}
              entities={items}
              selected={secondaryClothing[slotName] || null}
              onselect={(item) => { secondaryClothing = { ...secondaryClothing, [slotName]: item?.Name ?? null }; }}
              onclear={() => { secondaryClothing = { ...secondaryClothing, [slotName]: null }; }}
              {markupData}
              markupSource={clothingMuSources[slotName] || 'custom'}
              markupPercent={clothingMuValues[slotName] ?? 0}
              onmuSourceChange={(src) => { clothingMuSources = { ...clothingMuSources, [slotName]: src }; }}
              onmuValueChange={(val) => { clothingMuValues = { ...clothingMuValues, [slotName]: val }; }}
              {effectsCatalog}
              compact
              onsuggest={items.length ? () => handleSlotSuggest('clothing:' + slotName, slotName, items) : null}
              open={unlockedSlotIds.has('clothing:' + slotName)}
              onToggleOpen={() => toggleSlotLock('clothing:' + slotName)}
            />
          {/each}
        </div>
      </section>
    {/if}

    <!-- Totals -->
    <section class="eo-section">
      <EffectTotalsBar
        summary={effectSummary}
        {targets}
        {effectCaps}
        {effectsCatalog}
        {totalCost}
      />
    </section>
  </div>
</div>

<SlotSuggestionDialog
  bind:open={suggestDialogOpen}
  slotLabel={suggestDialogLabel}
  results={suggestDialogResults}
  {targets}
  currentSummary={effectSummary}
  currentSlotEffects={suggestDialogCurrentSlotEffects}
  currentSlotItemName={suggestDialogCurrentSlotItemName}
  baselineSummary={suggestDialogBaselineSummary}
  {effectsCatalog}
  bind:mode={suggestDialogMode}
  onpick={handleSuggestPick}
  loading={suggestDialogLoading}
/>

<OptimizerDialog
  bind:open={optimizerDialogOpen}
  {allSlotKeys}
  {unlockedSlotIds}
  slotLabels={{
    leftRing: 'Left Ring',
    rightRing: 'Right Ring',
    armorSet: 'Armor Set',
    pet: 'Pet',
    weapon: 'Weapon',
    amplifier: 'Amplifier',
    scope: 'Scope',
    scopeSight: 'Scope Sight',
    sight: 'Sight',
    absorber: 'Absorber',
    implant: 'Implant'
  }}
  currentItems={{
    leftRing, rightRing, armorSet, pet,
    weapon: secondaryWeapon,
    amplifier: secondaryAmplifier,
    scope: secondaryScope,
    scopeSight: secondaryScopeSight,
    sight: secondarySight,
    absorber: secondaryAbsorber,
    implant: secondaryImplant,
    clothing: secondaryClothing
  }}
  results={suggestionResults}
  {targets}
  loading={suggestionLoading}
  onToggleLock={toggleSlotLock}
  onLockAll={() => setAllSlotsLocked(true)}
  onUnlockAll={() => setAllSlotsLocked(false)}
  onResetLocks={resetLocksToDefault}
  onRun={handleFillAll}
  onApply={handleApplySuggestion}
  onSwapAlternative={handleSwapAlternative}
/>

<style>
  .effect-optimizer {
    display: flex;
    gap: 16px;
  }

  .eo-left {
    width: 320px;
    min-width: 320px;
    max-width: 320px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    position: sticky;
    top: 0px;
    align-self: flex-start;
    height: calc(100vh - 138px);
    height: calc(100dvh - 138px);
  }

  .eo-left-box {
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background-color: var(--secondary-color);
    padding: 10px;
    overflow-y: auto;
    flex: 1 1 0;
    min-height: 0;
  }

  .eo-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .eo-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .eo-section-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .eo-settings-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .setting-label {
    font-size: 12px;
    color: var(--text-muted);
  }

  .toggle-group {
    display: flex;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
  }

  .toggle-btn {
    padding: 4px 10px;
    font-size: 12px;
    border: none;
    border-right: 1px solid var(--border-color);
    background-color: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.1s ease;
  }

  .toggle-btn:last-child {
    border-right: none;
  }

  .toggle-btn:hover {
    background-color: var(--hover-color);
  }

  .toggle-btn.active {
    background-color: var(--accent-color);
    color: white;
  }

  .slots-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
  }


  @media (max-width: 1100px) {
    .slots-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 900px) {
    .eo-left {
      width: 240px;
      min-width: 240px;
      max-width: 240px;
    }
  }

  @media (max-width: 768px) {
    .effect-optimizer {
      flex-direction: column;
    }

    .eo-left {
      position: static;
      width: 100%;
      min-width: 0;
      max-width: none;
      height: auto;
    }
  }

  @media (max-width: 600px) {
    .slots-grid {
      grid-template-columns: 1fr;
    }
  }
</style>

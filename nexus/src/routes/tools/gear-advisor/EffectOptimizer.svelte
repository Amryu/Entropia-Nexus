<!--
  @component EffectOptimizer
  Main orchestrator for the Effect Optimizer gear advisor tool.
  Lets users target specific equipment effects and find optimal item combinations.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
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
  import {
    filterRings,
    filterArmorSetsWithEffects,
    collectAllEffects,
    aggregateEffects,
    findBestCombinations,
    suggestForSlot,
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
    visionAttachment: visionAttachmentsSorted,
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
  let secondaryVisionAttachment = $state(null);
  let secondaryAbsorber = $state(null);
  let secondaryImplant = $state(null);
  let secondaryClothing = $state({});

  // MU configs per slot
  let muSources = $state({
    leftRing: 'custom', rightRing: 'custom', armorSet: 'custom', pet: 'custom',
    weapon: 'custom', amplifier: 'custom', visionAttachment: 'custom',
    absorber: 'custom', implant: 'custom'
  });
  let muValues = $state({
    leftRing: 100, rightRing: 100, armorSet: 100, pet: 100,
    weapon: 100, amplifier: 100, visionAttachment: 100,
    absorber: 100, implant: 100
  });

  // Settings
  let overcapMode = $state('punish');

  // Suggestions
  let showSuggestions = $state(false);
  let suggestionResults = $state([]);
  let suggestionLoading = $state(false);
  let emptyOnly = $state(false);

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
      secondaryVisionAttachment = stored.secondaryVisionAttachment ?? null;
      secondaryAbsorber = stored.secondaryAbsorber ?? null;
      secondaryImplant = stored.secondaryImplant ?? null;
      secondaryClothing = stored.secondaryClothing || {};
      muSources = { ...muSources, ...(stored.muSources || {}) };
      muValues = { ...muValues, ...(stored.muValues || {}) };
      overcapMode = stored.overcapMode ?? 'punish';
      savedSets = stored.savedSets || [];
      activeSetId = stored.activeSetId ?? null;
      showSuggestions = stored.showSuggestions ?? false;
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
    const _sv = secondaryVisionAttachment; const _sab = secondaryAbsorber;
    const _si = secondaryImplant; const _sc = secondaryClothing;
    const _mu = muSources; const _mv = muValues;
    const _oc = overcapMode; const _sets = savedSets;
    const _asi = activeSetId;
    const _show = showSuggestions;
    if (!prefLoaded) return;
    pref.set({
      targets: _t, priorities: _pr,
      leftRing: _lr, rightRing: _rr,
      armorSet: _as, armorSetPieces: _asp,
      pet: _p, petActiveEffect: _pae,
      showSecondary: _ss,
      secondaryWeapon: _sw, secondaryAmplifier: _sa,
      secondaryVisionAttachment: _sv, secondaryAbsorber: _sab,
      secondaryImplant: _si, secondaryClothing: _sc,
      muSources: _mu, muValues: _mv,
      overcapMode: _oc, savedSets: _sets,
      activeSetId: _asi, showSuggestions: _show
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
      visionAttachment: secondaryVisionAttachment,
      absorber: secondaryAbsorber,
      implant: secondaryImplant,
      clothing: secondaryClothing
    }
  });

  // ===== Aggregated effects =====
  let allItemEffects = $derived(collectAllEffects(currentSlots, entityLookup));
  let effectSummary = $derived(aggregateEffects(allItemEffects, effectsCatalog, effectCaps));

  // ===== Total cost =====
  function getItemCost(entityList, name, muSource, muCustom) {
    if (!name) return null;
    const item = (entityList || []).find(e => e.Name === name);
    if (!item) return null;
    const tt = item.Properties?.Economy?.MaxTT ?? item.Properties?.MaxTT ?? null;
    if (tt == null || tt <= 0) return null;
    const isAbsolute = hasCondition(item);
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
    const add = (list, name, src, custom) => {
      const c = getItemCost(list, name, src, custom);
      if (c) costs.push({ name, ...c });
    };
    add(leftRings, leftRing, muSources.leftRing, muValues.leftRing);
    add(rightRings, rightRing, muSources.rightRing, muValues.rightRing);
    add(petsSorted, pet, muSources.pet, muValues.pet);
    add(weaponsSorted, secondaryWeapon, muSources.weapon, muValues.weapon);
    add(amplifiersSorted, secondaryAmplifier, muSources.amplifier, muValues.amplifier);
    add(visionAttachmentsSorted, secondaryVisionAttachment, muSources.visionAttachment, muValues.visionAttachment);
    add(absorbersSorted, secondaryAbsorber, muSources.absorber, muValues.absorber);
    add(implantsSorted, secondaryImplant, muSources.implant, muValues.implant);
    const total = costs.reduce((sum, c) => sum + c.cost, 0);
    return { items: costs, total };
  });

  // ===== Suggestion handlers =====
  function handleFillAll() {
    if (Object.keys(targets).length === 0) return;
    suggestionLoading = true;
    // Use setTimeout to avoid blocking the UI
    setTimeout(() => {
      const candidatesBySlot = {
        leftRings: emptyOnly && leftRing ? [] : leftRings,
        rightRings: emptyOnly && rightRing ? [] : rightRings,
        armorSets: emptyOnly && armorSet ? [] : armorSetsFiltered,
        pets: emptyOnly && pet ? [] : petsSorted
      };

      // Build locked slots if emptyOnly
      const lockedSlots = {};
      if (emptyOnly) {
        const lockedEffects = [];
        if (leftRing) {
          lockedSlots.leftRing = true;
          const item = leftRings.find(r => r.Name === leftRing);
          if (item) lockedEffects.push(...(item.EffectsOnEquip || []));
        }
        if (rightRing) {
          lockedSlots.rightRing = true;
          const item = rightRings.find(r => r.Name === rightRing);
          if (item) lockedEffects.push(...(item.EffectsOnEquip || []));
        }
        if (armorSet) {
          lockedSlots.armorSet = true;
          const set = armorSetsFiltered.find(s => s.Name === armorSet);
          if (set) lockedEffects.push(...extractArmorSetEffects(set, armorSetPieces));
        }
        if (pet && petActiveEffect) {
          lockedSlots.pet = true;
          const petEntity = petsSorted.find(p => p.Name === pet);
          if (petEntity) {
            const eff = extractPetEffect(petEntity, petActiveEffect);
            if (eff) lockedEffects.push(eff);
          }
        }
        lockedSlots.effects = lockedEffects;
      }

      // Include secondary slot effects in locked
      const secondaryEffects = [];
      if (secondaryWeapon) {
        const w = weaponsSorted.find(x => x.Name === secondaryWeapon);
        if (w) secondaryEffects.push(...(w.EffectsOnEquip || []));
      }
      if (secondaryAmplifier) {
        const a = amplifiersSorted.find(x => x.Name === secondaryAmplifier);
        if (a) secondaryEffects.push(...(a.EffectsOnEquip || []));
      }
      if (secondaryVisionAttachment) {
        const v = visionAttachmentsSorted.find(x => x.Name === secondaryVisionAttachment);
        if (v) secondaryEffects.push(...(v.EffectsOnEquip || []));
      }
      if (secondaryAbsorber) {
        const ab = absorbersSorted.find(x => x.Name === secondaryAbsorber);
        if (ab) secondaryEffects.push(...(ab.EffectsOnEquip || []));
      }
      if (secondaryImplant) {
        const im = implantsSorted.find(x => x.Name === secondaryImplant);
        if (im) secondaryEffects.push(...(im.EffectsOnEquip || []));
      }

      if (!lockedSlots.effects) lockedSlots.effects = [];
      lockedSlots.effects.push(...secondaryEffects);

      suggestionResults = findBestCombinations(
        targets,
        candidatesBySlot,
        effectsCatalog,
        effectCaps,
        { overcapMode, priorities, armorSetPieces, lockedSlots: emptyOnly ? lockedSlots : { effects: secondaryEffects } }
      );
      suggestionLoading = false;
      showSuggestions = true;
    }, 10);
  }

  function handleApplySuggestion(result, applyEmptyOnly) {
    if (result.items?.leftRing && (!applyEmptyOnly || !leftRing)) {
      leftRing = result.items.leftRing;
    }
    if (result.items?.rightRing && (!applyEmptyOnly || !rightRing)) {
      rightRing = result.items.rightRing;
    }
    if (result.items?.armorSet && (!applyEmptyOnly || !armorSet)) {
      armorSet = result.items.armorSet;
    }
    if (result.items?.pet && (!applyEmptyOnly || !pet)) {
      const petData = result.items.pet;
      if (typeof petData === 'object') {
        pet = petData.name;
        petActiveEffect = petData.effectKey;
      } else {
        pet = petData;
      }
    }
  }

  const SLOT_LABELS = { leftRing: 'Left Ring', rightRing: 'Right Ring', armorSet: 'Armor Set', pet: 'Pet' };

  function handleSlotSuggest(slotKey) {
    if (Object.keys(targets).length === 0) return;
    suggestDialogSlotKey = slotKey;
    suggestDialogLabel = SLOT_LABELS[slotKey] || slotKey;
    suggestDialogOpen = true;
    runSlotSuggestion(slotKey, suggestDialogMode);
  }

  function runSlotSuggestion(slotKey, mode) {
    suggestDialogLoading = true;
    setTimeout(() => {
      suggestDialogResults = suggestForSlot(
        slotKey, targets, currentSlots, entityLookup,
        effectsCatalog, effectCaps,
        { overcapMode, priorities, armorSetPieces, mode, maxResults: 30 }
      );
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
      secondaryVisionAttachment = set.slots.secondary.visionAttachment ?? null;
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
        bind:emptyOnly
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
          onsuggest={() => handleSlotSuggest('leftRing')}
          suggesting={false}
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
          onsuggest={() => handleSlotSuggest('rightRing')}
          suggesting={false}
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
          onsuggest={() => handleSlotSuggest('armorSet')}
          suggesting={false}
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
          onsuggest={() => handleSlotSuggest('pet')}
          suggesting={false}
        />
      </div>
    </section>

    <!-- Additional Equipment -->
    <section class="eo-section">
      <h3 class="eo-section-title">Additional Equipment</h3>
      <div class="slots-grid secondary">
        <EffectSlotCard
          label="Weapon"
          entities={weaponsSorted}
          bind:selected={secondaryWeapon}
          {markupData}
          bind:markupSource={muSources.weapon}
          bind:markupPercent={muValues.weapon}
          {effectsCatalog}
          compact
        />
        <EffectSlotCard
          label="Amplifier"
          entities={amplifiersSorted}
          bind:selected={secondaryAmplifier}
          {markupData}
          bind:markupSource={muSources.amplifier}
          bind:markupPercent={muValues.amplifier}
          {effectsCatalog}
          compact
        />
        <EffectSlotCard
          label="Vision Attachment"
          entities={visionAttachmentsSorted}
          bind:selected={secondaryVisionAttachment}
          {markupData}
          bind:markupSource={muSources.visionAttachment}
          bind:markupPercent={muValues.visionAttachment}
          {effectsCatalog}
          compact
        />
        <EffectSlotCard
          label="Absorber"
          entities={absorbersSorted}
          bind:selected={secondaryAbsorber}
          {markupData}
          bind:markupSource={muSources.absorber}
          bind:markupPercent={muValues.absorber}
          {effectsCatalog}
          compact
        />
        <EffectSlotCard
          label="Implant"
          entities={implantsSorted}
          bind:selected={secondaryImplant}
          {markupData}
          bind:markupSource={muSources.implant}
          bind:markupPercent={muValues.implant}
          {effectsCatalog}
          compact
        />
      </div>
    </section>

    <!-- Clothing -->
    {#if clothingSlots.size > 0}
      <section class="eo-section">
        <h3 class="eo-section-title">Clothing</h3>
        <div class="slots-grid secondary">
          {#each [...clothingSlots.entries()] as [slotName, items] (slotName)}
            <EffectSlotCard
              label={slotName}
              entities={items}
              selected={secondaryClothing[slotName] || null}
              onselect={(item) => { secondaryClothing = { ...secondaryClothing, [slotName]: item?.Name ?? null }; }}
              onclear={() => { secondaryClothing = { ...secondaryClothing, [slotName]: null }; }}
              {markupData}
              markupSource="custom"
              markupPercent={100}
              {effectsCatalog}
              compact
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
  bind:mode={suggestDialogMode}
  onpick={handleSuggestPick}
  loading={suggestDialogLoading}
/>

<style>
  .effect-optimizer {
    display: flex;
    gap: 16px;
    max-width: 1400px;
    margin: 0 auto;
    width: 100%;
    padding: 16px;
    box-sizing: border-box;
  }

  .eo-left {
    flex: 0 0 320px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    align-self: flex-start;
    position: sticky;
    top: 16px;
    max-height: calc(100vh - 32px);
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

  .slots-grid.secondary {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  }

  @media (max-width: 1100px) {
    .slots-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 900px) {
    .eo-left {
      flex: 0 0 220px;
    }
  }

  @media (max-width: 768px) {
    .effect-optimizer {
      flex-direction: column;
    }

    .eo-left {
      flex: none;
      position: static;
      width: 100%;
    }
  }

  @media (max-width: 600px) {
    .slots-grid,
    .slots-grid.secondary {
      grid-template-columns: 1fr;
    }
  }
</style>

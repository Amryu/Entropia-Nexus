<script>
  // @ts-nocheck
  import '$lib/style.css';
  import '../loadouts.css';
  import './share.css';
  import { onMount } from 'svelte';
  import { slide } from 'svelte/transition';
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import { clampDecimals, hasItemTag, getTypeLink, encodeURIComponentSafe } from '$lib/util.js';
  import { buildEffectCaps } from '$lib/utils/loadoutEffects.js';
  import { evaluateLoadout } from '$lib/utils/loadoutEvaluator.js';
  import { loadLoadoutEntities } from '$lib/utils/entityLoader';

  export let data;

  $: user = data?.session?.user;
  $: shared = data?.object;
  $: shareError = data?.additional?.error ?? data?.error;
  $: shareCode = data?.additional?.shareCode;
  $: loadout = shared?.data ?? null;
  $: displayName = loadout?.Name || shared?.name || 'Shared Loadout';

  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];
  const LOCAL_STORAGE_KEY = 'loadouts';
  const isLimitedName = (name) => !!name && hasItemTag(name, 'L');
  const isRingSlot = (slot) => /ring|finger/i.test(slot || '');

  function getApiBase() {
    return browser
      ? (import.meta.env.VITE_API_URL || 'https://api.entropianexus.com')
      : (process.env.INTERNAL_API_URL || 'http://api:3000');
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
  let clothing = [];
  let pets = [];
  let stimulants = [];
  let selectedClothing = [];
  let selectedConsumables = [];
  let leftRing = null;
  let rightRing = null;
  let activePet = null;
  let activePetEffects = [];

  let effectsCatalog = [];
  let effectCaps = {};

  let evaluation = null;
  let allEffects = [];
  let offensiveEffects = [];
  let defensiveEffects = [];
  let utilityEffects = [];
  let expandedEffectKeys = new Set();

  $: evaluation = loadout
    ? evaluateLoadout(
        loadout,
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
  $: stats = evaluation?.stats || {};
  $: allEffects = evaluation?.effects?.all ?? [];
  $: offensiveEffects = evaluation?.effects?.offensive ?? [];
  $: defensiveEffects = evaluation?.effects?.defensive ?? [];
  $: utilityEffects = evaluation?.effects?.utility ?? [];
  $: selectedClothing = (loadout?.Gear?.Clothing || []).filter(item => !isRingSlot(item?.Slot));
  $: selectedConsumables = loadout?.Gear?.Consumables || [];
  $: leftRing = loadout?.Gear?.Clothing ? getClothingSlot('Ring', 'Left') : null;
  $: rightRing = loadout?.Gear?.Clothing ? getClothingSlot('Ring', 'Right') : null;
  $: activePet = loadout?.Gear?.Pet?.Name
    ? pets.find(pet => pet.Name === loadout.Gear.Pet.Name)
    : null;
  $: activePetEffects = activePet?.Effects || [];

  let entitiesLoading = true;
  let entitiesError = null;

  let isCopying = false;
  let copyStatus = null;
  let copyError = null;

  const breadcrumbs = [
    { label: 'Tools', href: '/tools' },
    { label: 'Loadouts', href: '/tools/loadouts' },
    { label: 'Shared' }
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
    clothing = (entities.clothings || []).sort(alphabeticalSort);
    pets = (entities.pets || []).sort(alphabeticalSort);
    stimulants = (entities.consumables || []).sort(alphabeticalSort);
  }

  function getWeapon(name) {
    return weapons.find(x => x.Name === name);
  }

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

  function getClothingItemSlot(item) {
    return item?.Properties?.Slot || item?.Slot || 'Unknown';
  }

  function getClothingItem(name) {
    return clothing.find(item => item.Name === name);
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

  function formatEffectCount(count) {
    if (!count) return '-';
    return count === 1 ? '1 effect' : `${count} effects`;
  }

  function getConsumableItem(name) {
    return stimulants.find(item => item.Name === name);
  }

  function getConsumableEffectCount(item) {
    return item?.EffectsOnConsume?.length || 0;
  }

  function getPetEffectStrength(effect) {
    return effect?.Properties?.Strength ?? effect?.Values?.Strength ?? effect?.Values?.Value ?? 0;
  }

  function formatMagnitude(value, unit = '%') {
    if (value == null || Number.isNaN(value)) return 'N/A';
    return `${Math.abs(value).toFixed(2)}${unit}`;
  }

  function formatSignedNoPlus(value, unit = '%') {
    if (value == null || Number.isNaN(value)) return 'N/A';
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 'N/A';
    const sign = numeric < 0 ? '-' : '';
    return `${sign}${Math.abs(numeric).toFixed(2)}${unit}`;
  }

  function formatCapLimit(limit, unit, polarity) {
    if (limit == null || Number.isNaN(limit)) return 'N/A';
    const numeric = Number(limit);
    if (!Number.isFinite(numeric)) return 'N/A';
    const sign = polarity === 'negative' ? '-' : '';
    return `${sign}${Math.abs(numeric).toFixed(2)}${unit}`;
  }

  function toggleEffectExpanded(effectKey) {
    if (expandedEffectKeys.has(effectKey)) {
      expandedEffectKeys.delete(effectKey);
    } else {
      expandedEffectKeys.add(effectKey);
    }
    expandedEffectKeys = new Set(expandedEffectKeys);
  }

  onMount(async () => {
    if (!loadout) {
      entitiesLoading = false;
      return;
    }
    entitiesLoading = true;
    entitiesError = null;
    try {
      const entities = await loadLoadoutEntities();
      processEntityData(entities);
    } catch (error) {
      console.error('Failed to load entity data:', error);
      entitiesError = 'Failed to load reference data.';
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
  });

  function readLocalLoadouts() {
    if (typeof localStorage === 'undefined') return [];
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      console.error('Failed to read local loadouts:', err);
      return [];
    }
  }

  function writeLocalLoadouts(next) {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(next || []));
  }

  function createCopyLoadout(source) {
    const clone = JSON.parse(JSON.stringify(source));
    clone.Id = crypto?.randomUUID ? crypto.randomUUID() : Math.random().toString(16).slice(2);
    clone.Name = source?.Name ? `Copy of ${source.Name}` : 'Loadout Copy';
    return clone;
  }

  async function handleMakeCopy() {
    if (!loadout || isCopying) return;
    isCopying = true;
    copyStatus = null;
    copyError = null;
    const copy = createCopyLoadout(loadout);

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

</script>
<svelte:head>
  <title>{displayName} - Shared Loadout</title>
  <meta name="description" content="Shared loadout configuration on Entropia Nexus." />
</svelte:head>

<WikiPage
  title="Loadout Manager"
  {breadcrumbs}
  entity={loadout}
  editable={false}
  canEdit={false}
  user={user}
>
  <div slot="header-actions" class="loadout-header-actions">
    <button class="action-btn" on:click={handleMakeCopy} disabled={!loadout || isCopying}>
      <span class="action-label">{isCopying ? 'Copying...' : 'Make a copy'}</span>
    </button>
  </div>

  <div slot="sidebar" let:isMobile>
    <div class="loadout-sidebar" class:mobile={isMobile}>
      <div class="sidebar-header">
        <div class="sidebar-title">{displayName}</div>
        <div class="sidebar-meta">
          <span class="sidebar-badge">Shared</span>
          <span class="sidebar-badge readonly">Read-only</span>
        </div>
        <div class="sidebar-status code">Code: {shareCode || shared?.share_code || 'N/A'}</div>
      </div>
      <div class="sidebar-actions share-actions">
        <button class="sidebar-btn accent" on:click={handleMakeCopy} disabled={!loadout || isCopying}>
          {isCopying ? 'Copying...' : 'Make a copy'}
        </button>
        <a class="sidebar-btn neutral" href="/tools/loadouts">Back to Loadout Manager</a>
      </div>
      <div class="sidebar-status strong">This loadout is read-only. Make a copy to edit.</div>
    </div>
  </div>

  <div class="layout-a loadout-layout loadout-readonly">
    <aside class="loadout-sidebar-float">
      <div class="loadout-infobox-card">
        <div class="infobox-header">
          <div class="infobox-title">{displayName}</div>
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
          <div class="stats-empty">No loadout data available.</div>
        {/if}
      </div>
      {#if loadout}
        <div class="loadout-settings-panel">
          <DataSection title="Settings" collapsible={false}>
            <div class="settings-grid">
              <div class="settings-group-title">Profession Levels</div>
              <div class="settings-divider" aria-hidden="true"></div>
              <div class="setting-row">
                <label>Hit Profession</label>
                <input class="read-only-field" type="number" readonly value={loadout?.Skill?.Hit ?? ''} />
              </div>
              <div class="setting-row">
                <label>Dmg Profession</label>
                <input class="read-only-field" type="number" readonly value={loadout?.Skill?.Dmg ?? ''} />
              </div>
              <div class="settings-group-title">Bonus Stats</div>
              <div class="settings-divider" aria-hidden="true"></div>
              <div class="setting-row">
                <label>% Damage</label>
                <input class="read-only-field" type="number" readonly value={loadout?.Properties?.BonusDamage ?? 0} />
              </div>
              <div class="setting-row">
                <label>% Crit Chance</label>
                <input class="read-only-field" type="number" readonly value={loadout?.Properties?.BonusCritChance ?? 0} />
              </div>
              <div class="setting-row">
                <label>% Crit Damage</label>
                <input class="read-only-field" type="number" readonly value={loadout?.Properties?.BonusCritDamage ?? 0} />
              </div>
              <div class="setting-row">
                <label>% Reload</label>
                <input class="read-only-field" type="number" readonly value={loadout?.Properties?.BonusReload ?? 0} />
              </div>
            </div>
          </DataSection>
        </div>
      {/if}
    </aside>

    <article class="wiki-article loadout-article">

      {#if shareError}
        <div class="share-status error">{shareError}</div>
      {:else if entitiesLoading}
        <div class="share-status">Loading loadout data...</div>
      {:else if entitiesError}
        <div class="share-status error">{entitiesError}</div>
      {:else if loadout}
        {#if copyStatus}
          <div class="share-status success">{copyStatus}</div>
        {/if}
        {#if copyError}
          <div class="share-status error">{copyError}</div>
        {/if}

        <DataSection title="Weapons">
          <div class="panel-grid two-col">
            <div class="panel-block">
              <h3 class="panel-title">Weapon & Attachments</h3>
              <div class="form-grid">
                <div class="form-label">Weapon</div>
                <div class="control-row">
                  {#if loadout?.Gear?.Weapon?.Name}
                    <a
                      class="slot select-button read-only link-slot"
                      href={getEquipmentLink('weapon', loadout.Gear.Weapon.Name)}
                    >
                      {loadout.Gear.Weapon.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot">
                      <span class="placeholder-text">No weapon selected.</span>
                    </div>
                  {/if}
                  {#if isLimitedName(loadout?.Gear?.Weapon?.Name)}
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.Weapon ?? 100} />
                    </div>
                  {/if}
                </div>
                <div class="form-label">Amplifier</div>
                <div class="control-row">
                  {#if loadout?.Gear?.Weapon?.Name == null}
                    <div class="slot select-button read-only read-only-slot">
                      <span class="placeholder-muted">Weapon required.</span>
                    </div>
                  {:else if loadout?.Gear?.Weapon?.Amplifier?.Name}
                    <a
                      class="slot select-button read-only link-slot"
                      href={getEquipmentLink('amplifier', loadout.Gear.Weapon.Amplifier.Name)}
                    >
                      {loadout.Gear.Weapon.Amplifier.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot">
                      <span class="placeholder-text">No amplifier selected.</span>
                    </div>
                  {/if}
                  {#if isLimitedName(loadout?.Gear?.Weapon?.Amplifier?.Name)}
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.Amplifier ?? 100} />
                    </div>
                  {/if}
                </div>
                <div class="form-label">Absorber</div>
                <div class="control-row">
                  {#if loadout?.Gear?.Weapon?.Name == null}
                    <div class="slot select-button read-only read-only-slot">
                      <span class="placeholder-muted">Weapon required.</span>
                    </div>
                  {:else if loadout?.Gear?.Weapon?.Absorber?.Name}
                    <a
                      class="slot select-button read-only link-slot"
                      href={getEquipmentLink('absorber', loadout.Gear.Weapon.Absorber.Name)}
                    >
                      {loadout.Gear.Weapon.Absorber.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot">
                      <span class="placeholder-text">No absorber selected.</span>
                    </div>
                  {/if}
                  {#if isLimitedName(loadout?.Gear?.Weapon?.Absorber?.Name)}
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.Absorber ?? 100} />
                    </div>
                  {/if}
                </div>
                {#if getWeapon(loadout?.Gear?.Weapon?.Name)?.Properties?.Class === 'Ranged'}
                  <div class="form-label">Scope</div>
                  <div class="control-row">
                    {#if loadout?.Gear?.Weapon?.Scope?.Name}
                      <a
                        class="slot select-button read-only link-slot"
                        href={getEquipmentLink('scope', loadout.Gear.Weapon.Scope.Name)}
                      >
                        {loadout.Gear.Weapon.Scope.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot">
                        <span class="placeholder-text">No scope selected.</span>
                      </div>
                    {/if}
                    {#if isLimitedName(loadout?.Gear?.Weapon?.Scope?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.Scope ?? 100} />
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
                    {#if loadout?.Gear?.Weapon?.Scope == null}
                      <div class="slot select-button read-only read-only-slot">
                        <span class="placeholder-muted">Add a scope first</span>
                      </div>
                    {:else if loadout?.Gear?.Weapon?.Scope?.Sight?.Name}
                      <a
                        class="slot select-button read-only link-slot"
                        href={getEquipmentLink('scope-sight', loadout.Gear.Weapon.Scope.Sight.Name)}
                      >
                        {loadout.Gear.Weapon.Scope.Sight.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot">
                        <span class="placeholder-text">No sight selected.</span>
                      </div>
                    {/if}
                    {#if isLimitedName(loadout?.Gear?.Weapon?.Scope?.Sight?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.ScopeSight ?? 100} />
                      </div>
                    {/if}
                  </div>
                  <div class="form-label">Sight</div>
                  <div class="control-row">
                    {#if loadout?.Gear?.Weapon?.Sight?.Name}
                      <a
                        class="slot select-button read-only link-slot"
                        href={getEquipmentLink('sight', loadout.Gear.Weapon.Sight.Name)}
                      >
                        {loadout.Gear.Weapon.Sight.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot">
                        <span class="placeholder-text">No sight selected.</span>
                      </div>
                    {/if}
                    {#if isLimitedName(loadout?.Gear?.Weapon?.Sight?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.Sight ?? 100} />
                      </div>
                    {/if}
                  </div>
                {:else if getWeapon(loadout?.Gear?.Weapon?.Name)?.Properties?.Class === 'Melee'}
                  <div class="form-label">Matrix</div>
                  <div class="control-row">
                    {#if loadout?.Gear?.Weapon?.Matrix?.Name}
                      <a
                        class="slot select-button read-only link-slot"
                        href={getEquipmentLink('matrix', loadout.Gear.Weapon.Matrix.Name)}
                      >
                        {loadout.Gear.Weapon.Matrix.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot">
                        <span class="placeholder-text">No matrix selected.</span>
                      </div>
                    {/if}
                    {#if isLimitedName(loadout?.Gear?.Weapon?.Matrix?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.Matrix ?? 100} />
                      </div>
                    {/if}
                  </div>
                {:else if getWeapon(loadout?.Gear?.Weapon?.Name)?.Properties?.Class === 'Mindforce'}
                  <div class="form-label">Implant</div>
                  <div class="control-row">
                    {#if getWeapon(loadout?.Gear?.Weapon?.Name)?.Properties?.Class !== 'Mindforce'}
                      <div class="slot select-button read-only read-only-slot">
                        <span class="placeholder-muted">Mindforce weapon required.</span>
                      </div>
                    {:else if loadout?.Gear?.Weapon?.Implant?.Name}
                      <a
                        class="slot select-button read-only link-slot"
                        href={getEquipmentLink('implant', loadout.Gear.Weapon.Implant.Name)}
                      >
                        {loadout.Gear.Weapon.Implant.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot">
                        <span class="placeholder-text">No implant selected.</span>
                      </div>
                    {/if}
                    {#if isLimitedName(loadout?.Gear?.Weapon?.Implant?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.Implant ?? 100} />
                      </div>
                    {/if}
                  </div>
                {/if}
                <div class="form-label">Ammo</div>
                <div class="control-row">
                  {#if loadout?.Gear?.Weapon?.Name == null}
                    <span class="placeholder-muted">Weapon required.</span>
                  {:else}
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.Ammo ?? 100} />
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
                  <input class="read-only-field" type="number" readonly value={loadout?.Gear?.Weapon?.Enhancers?.Damage ?? 0} />
                </div>
                <div class="enhancer-field">
                  <label>Accuracy</label>
                  <input class="read-only-field" type="number" readonly value={loadout?.Gear?.Weapon?.Enhancers?.Accuracy ?? 0} />
                </div>
                <div class="enhancer-field">
                  <label>Range</label>
                  <input class="read-only-field" type="number" readonly value={loadout?.Gear?.Weapon?.Enhancers?.Range ?? 0} />
                </div>
                <div class="enhancer-field">
                  <label>Economy</label>
                  <input class="read-only-field" type="number" readonly value={loadout?.Gear?.Weapon?.Enhancers?.Economy ?? 0} />
                </div>
                <div class="enhancer-field">
                  <label>Skill Mod</label>
                  <input class="read-only-field" type="number" readonly value={loadout?.Gear?.Weapon?.Enhancers?.SkillMod ?? 0} />
                </div>
              </div>
            </div>
          </div>
        </DataSection>

        <DataSection title="Armor">
          <div class="panel-grid two-col">
            <div class="panel-block">
              <h3 class="panel-title">Armor Selection</h3>
              {#if loadout?.Gear?.Armor?.ManageIndividual}
                <div class="armor-grid">
                  <div class="armor-grid-header">Slot</div>
                  <div class="armor-grid-header">Armor</div>
                  <div class="armor-grid-header">Armor MU</div>
                  <div class="armor-grid-header">Plate</div>
                  <div class="armor-grid-header">Plate MU</div>
                  {#each armorSlots as slot}
                    <div class="armor-label">{slot}</div>
                    {#if loadout?.Gear?.Armor?.[slot]?.Name}
                      <a
                        class="slot select-button read-only link-slot"
                        href={getEquipmentLink('armor', loadout.Gear.Armor[slot].Name)}
                      >
                        {loadout.Gear.Armor[slot].Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot">
                        <span class="placeholder-text">No armor selected.</span>
                      </div>
                    {/if}
                    {#if isLimitedName(loadout?.Gear?.Armor?.[slot]?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.Armors?.[slot] ?? 100} />
                      </div>
                    {:else}
                      <span class="placeholder-muted"></span>
                    {/if}
                    {#if loadout?.Gear?.Armor?.[slot]?.Name == null}
                      <div class="slot select-button read-only read-only-slot">
                        <span class="placeholder-muted">Armor required.</span>
                      </div>
                    {:else if loadout?.Gear?.Armor?.[slot]?.Plate?.Name}
                      <a
                        class="slot select-button read-only link-slot"
                        href={getEquipmentLink('armorplating', loadout.Gear.Armor[slot].Plate.Name)}
                      >
                        {loadout.Gear.Armor[slot].Plate.Name}
                      </a>
                    {:else}
                      <div class="slot select-button read-only read-only-slot">
                        <span class="placeholder-text">No plating selected.</span>
                      </div>
                    {/if}
                    {#if isLimitedName(loadout?.Gear?.Armor?.[slot]?.Plate?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.Plates?.[slot] ?? 100} />
                      </div>
                    {:else}
                      <span class="placeholder-muted"></span>
                    {/if}
                  {/each}
                </div>
              {:else}
                <div class="form-grid">
                  <div class="form-label">Armor Set</div>
                  {#if loadout?.Gear?.Armor?.SetName}
                    <a
                      class="slot select-button read-only link-slot"
                      href={getEquipmentLink('armorset', loadout.Gear.Armor.SetName)}
                    >
                      {loadout.Gear.Armor.SetName}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot">
                      <span class="placeholder-text">No armor set selected.</span>
                    </div>
                  {/if}
                  {#if isLimitedName(loadout?.Gear?.Armor?.SetName)}
                    <div class="form-label">Armor Markup</div>
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.ArmorSet ?? 100} />
                    </div>
                  {/if}
                  <div class="form-label">Plate Set</div>
                  {#if loadout?.Gear?.Armor?.SetName == null}
                    <div class="slot select-button read-only read-only-slot">
                      <span class="placeholder-muted">Armor set required.</span>
                    </div>
                  {:else if loadout?.Gear?.Armor?.PlateName}
                    <a
                      class="slot select-button read-only link-slot"
                      href={getEquipmentLink('armorplating', loadout.Gear.Armor.PlateName)}
                    >
                      {loadout.Gear.Armor.PlateName}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot">
                      <span class="placeholder-text">No plating selected.</span>
                    </div>
                  {/if}
                  {#if isLimitedName(loadout?.Gear?.Armor?.PlateName)}
                    <div class="form-label">Plate Markup</div>
                    <div class="markup-field">
                      <span class="markup-label">MU%</span>
                      <input class="markup-input read-only-field" type="number" readonly value={loadout?.Markup?.PlateSet ?? 100} />
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
                  <input class="read-only-field" type="number" readonly value={loadout?.Gear?.Armor?.Enhancers?.Defense ?? 0} />
                </div>
                <div class="enhancer-field">
                  <label>Durability</label>
                  <input class="read-only-field" type="number" readonly value={loadout?.Gear?.Armor?.Enhancers?.Durability ?? 0} />
                </div>
              </div>
              <label class="checkbox-row">
                <input type="checkbox" checked={!!loadout?.Gear?.Armor?.ManageIndividual} disabled />
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
                    <a
                      class="slot select-button read-only link-slot"
                      href={getEquipmentLink('clothing', leftRing.Name)}
                    >
                      {leftRing.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot">
                      <span class="placeholder-text">No ring selected.</span>
                    </div>
                  {/if}
                </div>
                <div class="accessory-item">
                  <div class="form-label">Right Ring</div>
                  {#if rightRing?.Name}
                    <a
                      class="slot select-button read-only link-slot"
                      href={getEquipmentLink('clothing', rightRing.Name)}
                    >
                      {rightRing.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot">
                      <span class="placeholder-text">No ring selected.</span>
                    </div>
                  {/if}
                </div>
                <div class="accessory-item pet-select">
                  <div class="form-label">Pet</div>
                  {#if loadout?.Gear?.Pet?.Name}
                    <a
                      class="slot select-button read-only link-slot pet-active"
                      href={getEquipmentLink('pet', loadout.Gear.Pet.Name)}
                    >
                      {loadout.Gear.Pet.Name}
                    </a>
                  {:else}
                    <div class="slot select-button read-only read-only-slot">
                      <span class="placeholder-text">No pet selected.</span>
                    </div>
                  {/if}
                </div>
              </div>
              <div class="pet-abilities">
                {#if !loadout?.Gear?.Pet?.Name}
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
                        class:active={loadout?.Gear?.Pet?.Effect === effectKey || loadout?.Gear?.Pet?.Effect === effectName}
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

      {:else}
        <div class="share-status">Shared loadout not available.</div>
      {/if}
    </article>
  </div>
</WikiPage>





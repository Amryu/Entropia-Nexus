<!--
  @component WeaponProfitability
  (L) Weapon Profitability Analyzer - evaluates whether an (L) weapon's efficiency
  advantage generates enough extra TT returns over its lifetime to justify the
  markup premium paid, compared to one or more base weapons.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { hasItemTag } from '$lib/util.js';
  import { createPreference } from '$lib/preferences.js';
  import { fetchExchangeWapByName, fetchInGamePrices, fetchInventoryMarkups } from '$lib/markupSources.js';
  import EntityPicker from './EntityPicker.svelte';
  import WeaponConfigPanel from './WeaponConfigPanel.svelte';
  import ProfitabilityDetailView from './ProfitabilityDetailView.svelte';
  import ProfitabilityComparisonTable from './ProfitabilityComparisonTable.svelte';
  import {
    createDefaultWeaponConfig,
    extractConfigFromLoadout,
    computeWeaponStats,
    analyzeWeaponProfitability,
    shouldApplyAbsorber,
    formatPED,
    formatPct,
    formatNumber,
    weaponUsesExplosiveAmmo
  } from './weaponProfitability.js';

  let {
    weapons = [],
    weaponAmplifiers = [],
    weaponVisionAttachments = [],
    absorbers = [],
    mindforceImplants = []
  } = $props();

  const isLimited = (name) => !!name && hasItemTag(name, 'L');
  const alphabetical = (a, b) => (a?.Name || '').localeCompare(b?.Name || '', undefined, { numeric: true });

  // Build categorized entity lists (same filtering as loadoutContext.js)
  let entities = $derived.by(() => ({
    weapons: weapons.filter(x => x.Properties?.Class !== 'Attached' && x.Properties?.Class !== 'Stationary').sort(alphabetical),
    amplifiers: weaponAmplifiers.filter(x => x.Properties?.Type !== 'Matrix').sort(alphabetical),
    matrices: weaponAmplifiers.filter(x => x.Properties?.Type === 'Matrix').sort(alphabetical),
    scopes: weaponVisionAttachments.filter(x => x.Properties?.Type === 'Scope').sort(alphabetical),
    sights: weaponVisionAttachments.filter(x => x.Properties?.Type === 'Sight').sort(alphabetical),
    absorbers: absorbers.sort(alphabetical),
    implants: mindforceImplants.sort(alphabetical)
  }));

  // ===== State =====
  let baseWeapons = $state([createDefaultWeaponConfig()]);
  let comparisonWeapons = $state([]);
  let globalAbsorberName = $state(null);
  let globalAbsorberMarkup = $state(100);
  let globalAbsorberMarkupSource = $state('custom');
  let viewMode = $state('config');
  let selectedBaseIndex = $state(0);
  let selectedCompIndex = $state(0);
  let mobHP = $state(null);
  let explosiveAmmoMarkup = $state(100);
  let prefLoaded = $state(false);

  // Markup source data
  let markupData = $state({ wapByName: new Map(), nameToId: new Map(), ingameMap: new Map(), inventoryMap: new Map() });

  // Loadout import
  let showImportDialog = $state(false);
  let importLoading = $state(false);
  let importLoadouts = $state([]);

  // ===== Preference Persistence =====
  const pref = createPreference('gear-advisor.weapon-profitability', null, { debounceMs: 600 });

  onMount(async () => {
    const userId = $page.data?.user?.id ?? null;
    await pref.load(userId);

    let stored;
    pref.subscribe(v => stored = v)();
    if (stored) {
      if (Array.isArray(stored.baseWeapons) && stored.baseWeapons.length > 0) {
        baseWeapons = stored.baseWeapons.map(c => ({ ...createDefaultWeaponConfig(), ...c }));
      }
      if (Array.isArray(stored.comparisonWeapons)) {
        comparisonWeapons = stored.comparisonWeapons.map(c => ({ ...createDefaultWeaponConfig(), ...c }));
      }
      globalAbsorberName = stored.globalAbsorberName ?? null;
      globalAbsorberMarkup = stored.globalAbsorberMarkup ?? 100;
      globalAbsorberMarkupSource = stored.globalAbsorberMarkupSource ?? 'custom';
      viewMode = stored.viewMode ?? 'config';
      selectedBaseIndex = stored.selectedBaseIndex ?? 0;
      selectedCompIndex = stored.selectedCompIndex ?? 0;
      mobHP = stored.mobHP ?? null;
      explosiveAmmoMarkup = stored.explosiveAmmoMarkup ?? 100;
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
    const _b = baseWeapons;
    const _c = comparisonWeapons;
    const _ga = globalAbsorberName;
    const _gm = globalAbsorberMarkup;
    const _gs = globalAbsorberMarkupSource;
    const _v = viewMode;
    const _sb = selectedBaseIndex;
    const _sc = selectedCompIndex;
    const _hp = mobHP;
    const _ea = explosiveAmmoMarkup;
    if (!prefLoaded) return;
    pref.set({
      baseWeapons: _b,
      comparisonWeapons: _c,
      globalAbsorberName: _ga,
      globalAbsorberMarkup: _gm,
      globalAbsorberMarkupSource: _gs,
      viewMode: _v,
      selectedBaseIndex: _sb,
      selectedCompIndex: _sc,
      mobHP: _hp,
      explosiveAmmoMarkup: _ea
    });
  });

  // ===== Explosive ammo sync =====
  // Check if any configured weapon uses explosive ammo
  let hasExplosiveWeapon = $derived.by(() => {
    const allConfigs = [...baseWeapons, ...comparisonWeapons];
    return allConfigs.some(cfg => {
      const w = cfg.weaponName ? entities.weapons?.find(x => x.Name === cfg.weaponName) : null;
      return weaponUsesExplosiveAmmo(w);
    });
  });

  // Sync shared explosive ammo markup to all configs
  $effect(() => {
    const mu = explosiveAmmoMarkup;
    for (const cfg of [...baseWeapons, ...comparisonWeapons]) {
      const w = cfg.weaponName ? entities.weapons?.find(x => x.Name === cfg.weaponName) : null;
      if (weaponUsesExplosiveAmmo(w) && cfg.ammoMarkup !== mu) {
        cfg.ammoMarkup = mu;
      }
    }
  });

  // ===== Computed Stats =====
  let baseStats = $derived.by(() =>
    baseWeapons.map(cfg => computeWeaponStats(cfg, entities))
  );

  let compStats = $derived.by(() =>
    comparisonWeapons.map(cfg => computeWeaponStats(cfg, entities))
  );

  // Analyses: for each comp x selected base
  let analyses = $derived.by(() => {
    const bi = Math.min(selectedBaseIndex, baseWeapons.length - 1);
    const base = baseStats[bi >= 0 ? bi : 0];
    return compStats.map(cs => analyzeWeaponProfitability(base, cs, mobHP));
  });

  // All analyses for all base x comp pairs (for table view)
  let allAnalyses = $derived.by(() => {
    return baseStats.map(base =>
      compStats.map(cs => analyzeWeaponProfitability(base, cs, mobHP))
    );
  });

  // Resolved global absorber entity
  let globalAbsorber = $derived(globalAbsorberName
    ? entities.absorbers?.find(a => a.Name === globalAbsorberName) : null);

  // ===== Actions =====
  function addBase() {
    baseWeapons = [...baseWeapons, createDefaultWeaponConfig()];
  }

  function removeBase(index) {
    if (baseWeapons.length <= 1) return;
    baseWeapons = baseWeapons.filter((_, i) => i !== index);
    if (selectedBaseIndex >= baseWeapons.length) selectedBaseIndex = baseWeapons.length - 1;
  }

  function addComparison() {
    comparisonWeapons = [...comparisonWeapons, createDefaultWeaponConfig()];
  }

  function removeComparison(index) {
    comparisonWeapons = comparisonWeapons.filter((_, i) => i !== index);
    if (selectedCompIndex >= comparisonWeapons.length) selectedCompIndex = Math.max(0, comparisonWeapons.length - 1);
  }

  function applyGlobalAbsorber() {
    if (!globalAbsorberName) return;
    comparisonWeapons = comparisonWeapons.map(cfg => {
      // Sync MU if same absorber is already set
      if (cfg.absorberName === globalAbsorberName) {
        return { ...cfg, absorberMarkup: globalAbsorberMarkup, absorberMarkupSource: globalAbsorberMarkupSource };
      }
      // Apply if no absorber and weapon MU > absorber MU
      if (!cfg.absorberName && shouldApplyAbsorber(cfg.markupPercent, globalAbsorberMarkup)) {
        return { ...cfg, absorberName: globalAbsorberName, absorberMarkup: globalAbsorberMarkup, absorberMarkupSource: globalAbsorberMarkupSource };
      }
      return cfg;
    });
    // Also sync to base weapons that have the same absorber
    baseWeapons = baseWeapons.map(cfg => {
      if (cfg.absorberName === globalAbsorberName) {
        return { ...cfg, absorberMarkup: globalAbsorberMarkup, absorberMarkupSource: globalAbsorberMarkupSource };
      }
      return cfg;
    });
  }

  function resetAll() {
    baseWeapons = [createDefaultWeaponConfig()];
    comparisonWeapons = [];
    globalAbsorberName = null;
    globalAbsorberMarkup = 100;
    selectedBaseIndex = 0;
    selectedCompIndex = 0;
    mobHP = null;
  }

  // ===== Loadout Import =====
  async function openImportDialog() {
    showImportDialog = true;
    importLoading = true;
    try {
      const res = await fetch('/api/tools/loadout');
      if (!res.ok) { importLoadouts = []; return; }
      const data = await res.json();
      importLoadouts = (data || []).map(row => ({
        id: row.id,
        name: row.name,
        data: row.data,
        weaponName: row.data?.Gear?.Weapon?.Name || null,
        setCount: row.data?.Sets?.Weapon?.length || 0
      }));
    } catch {
      importLoadouts = [];
    } finally {
      importLoading = false;
    }
  }

  function importLoadout(loadout) {
    const data = loadout.data;
    if (!data) return;

    const sets = data.Sets?.Weapon;
    if (Array.isArray(sets) && sets.length > 0) {
      // Import each weapon set as a base weapon
      const configs = sets.map(set => extractConfigFromLoadout(set.gear, set.markup));
      baseWeapons = [...baseWeapons.filter(b => b.weaponName != null), ...configs];
    } else {
      // Import main weapon config
      const gear = data.Gear?.Weapon;
      const markup = data.Markup;
      if (gear?.Name) {
        const cfg = extractConfigFromLoadout(gear, markup);
        baseWeapons = [...baseWeapons.filter(b => b.weaponName != null), cfg];
      }
    }
    showImportDialog = false;
  }

  function getWeaponDisplayName(cfg) {
    return cfg?.weaponName || 'No weapon';
  }

  // ===== Ranked (L) Weapon Browser =====
  let showWeaponBrowser = $state(false);
  let browserSortBy = $state('efficiency'); // 'efficiency' | 'dpp' | 'dps' | 'totalDamage' | 'totalUses' | 'name'
  let browserSearch = $state('');

  // Pre-compute base stats for all (L) weapons (simple: no enhancers/attachments, 100% MU)
  let limitedWeapons = $derived(entities.weapons?.filter(w => isLimited(w.Name)) || []);

  let rankedWeapons = $derived.by(() => {
    let list = limitedWeapons.map(w => {
      const eff = w.Properties?.Economy?.Efficiency;
      const decay = w.Properties?.Economy?.Decay;
      const ammo = w.Properties?.Economy?.AmmoBurn;
      const maxTT = w.Properties?.Economy?.MaxTT;
      const minTT = w.Properties?.Economy?.MinTT ?? 0;
      const totalDmg = (w.Properties?.Damage?.Impact ?? 0)
        + (w.Properties?.Damage?.Cut ?? 0) + (w.Properties?.Damage?.Stab ?? 0)
        + (w.Properties?.Damage?.Penetration ?? 0) + (w.Properties?.Damage?.Shrapnel ?? 0)
        + (w.Properties?.Damage?.Burn ?? 0) + (w.Properties?.Damage?.Cold ?? 0)
        + (w.Properties?.Damage?.Acid ?? 0) + (w.Properties?.Damage?.Electric ?? 0);
      const costPEC = decay != null ? decay + ((ammo ?? 0) / 100) : null;
      const dpp = totalDmg && costPEC ? totalDmg / costPEC : null;
      const reload = w.Properties?.UsesPerMinute ? 60 / w.Properties.UsesPerMinute : null;
      const dps = totalDmg && reload ? totalDmg / reload : null;
      const totalUses = maxTT != null && decay ? Math.floor((maxTT - minTT) / (decay / 100)) : null;
      return { weapon: w, name: w.Name, efficiency: eff, dpp, dps, totalDamage: totalDmg || null, totalUses, type: w.Properties?.Type, class: w.Properties?.Class };
    });

    // Filter by search
    if (browserSearch.trim()) {
      const q = browserSearch.trim().toLowerCase();
      list = list.filter(r => r.name.toLowerCase().includes(q));
    }

    // Sort
    list.sort((a, b) => {
      if (browserSortBy === 'name') return a.name.localeCompare(b.name, undefined, { numeric: true });
      const va = a[browserSortBy];
      const vb = b[browserSortBy];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      return vb - va; // descending
    });

    return list;
  });

  // Already-added names for highlighting
  let addedNames = $derived(new Set(comparisonWeapons.map(c => c.weaponName).filter(Boolean)));

  function addFromBrowser(weaponName) {
    if (addedNames.has(weaponName)) return;
    const cfg = createDefaultWeaponConfig();
    cfg.weaponName = weaponName;
    comparisonWeapons = [...comparisonWeapons, cfg];
  }
</script>

<div class="weapon-profitability">
  <!-- Top bar: view tabs + controls -->
  <div class="top-bar">
    <div class="view-tabs">
      {#each [['config', 'Config'], ['list', 'List'], ['table', 'Table']] as [mode, lbl]}
        <button type="button" class="view-tab" class:active={viewMode === mode}
          onclick={() => { viewMode = mode; }}>
          {lbl}
        </button>
      {/each}
    </div>
    <div class="top-actions">
      {#if hasExplosiveWeapon}
        <label class="mob-hp-label" title="Ammo markup for explosive weapons">
          <span>Explosive ammo MU%:</span>
          <input type="number" min="0" step="0.01" class="mob-hp-input"
            bind:value={explosiveAmmoMarkup} />
        </label>
      {/if}
      <label class="mob-hp-label">
        <span>Mob HP:</span>
        <input type="number" min="0" class="mob-hp-input" placeholder="Optional"
          value={mobHP ?? ''}
          oninput={(e) => { mobHP = e.target.value ? Number(e.target.value) : null; }} />
      </label>
      <button type="button" class="reset-btn" onclick={resetAll}>Reset</button>
    </div>
  </div>

  <!-- ===== CONFIG VIEW ===== -->
  {#if viewMode === 'config'}
    <!-- Top row: base weapons (left) + compare weapons (right) -->
    <div class="config-columns">
      <!-- Base weapons column -->
      <div class="config-col">
        <div class="group-header">
          <h3>Base Weapons</h3>
          <div class="group-actions">
            <button type="button" class="add-btn" onclick={addBase}>+ Add</button>
            {#if $page.data?.user}
              <button type="button" class="add-btn" onclick={openImportDialog}>Import</button>
            {/if}
          </div>
        </div>
        <div class="config-cards">
          {#each baseWeapons as cfg, i (i)}
            <WeaponConfigPanel
              bind:config={baseWeapons[i]}
              {entities}
              {markupData}
              removable={baseWeapons.length > 1}
              onremove={() => removeBase(i)}
            />
          {/each}
        </div>
      </div>

      <!-- Compare weapons column -->
      <div class="config-col">
        <div class="group-header">
          <h3>Compare (L) Weapons</h3>
          <div class="group-actions">
            <button type="button" class="add-btn" onclick={addComparison}>+ Add</button>
          </div>
        </div>
        {#if comparisonWeapons.length === 0}
          <p class="empty-hint">Add (L) weapons to compare. Use the List tab to browse.</p>
        {:else}
          <div class="config-cards">
            {#each comparisonWeapons as cfg, i (i)}
              <div class="comp-card-wrap">
                <WeaponConfigPanel
                  bind:config={comparisonWeapons[i]}
                  {entities}
                  {markupData}
                  limitedOnly={true}
                  compact={true}
                  dropUp={true}
                  removable={true}
                  onremove={() => removeComparison(i)}
                />
                {#if analyses[i]}
                  {@const a = analyses[i]}
                  <div class="comp-result" onclick={() => { selectedCompIndex = i; }}>
                    <span class="be-mu" title="Break-even markup">
                      Breakeven: {a.breakEvenMU != null ? a.breakEvenMU.toFixed(1) + '%' : 'N/A'}
                    </span>
                    <span class="net-val {a.netProfitabilityPED > 0.005 ? 'positive' : a.netProfitabilityPED < -0.005 ? 'negative' : ''}">
                      {formatPED(a.netProfitabilityPED).text}
                    </span>
                    <span class="delta-stat">Eff: {formatPct(a.efficiencyDelta)}</span>
                    <span class="delta-stat">DPP: {formatPct(a.dppDiffPct)}</span>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Right: sticky detail panel -->
      <div class="config-detail-col">
        <!-- Global absorber -->
        <div class="detail-panel-section">
        <h4 class="dp-title">Global Absorber</h4>
        <EntityPicker
          entities={entities.absorbers || []}
          selected={globalAbsorber}
          placeholder="Select absorber..."
          onselect={(item) => { globalAbsorberName = item?.Name ?? null; }}
          onclear={() => { globalAbsorberName = null; globalAbsorberMarkup = 100; }}
        />
        {#if globalAbsorberName}
          <div class="absorber-controls">
            <label class="wcp-field">
              <span>MU%</span>
              <input type="number" min="0" step="0.01" class="wcp-num"
                bind:value={globalAbsorberMarkup} />
            </label>
            <div class="wcp-src-btns">
              {#each ['custom', 'inventory', 'ingame', 'exchange'] as src}
                <button type="button" class="src-btn" class:active={globalAbsorberMarkupSource === src}
                  onclick={() => { globalAbsorberMarkupSource = src; }}>
                  {src === 'custom' ? 'Cust' : src === 'inventory' ? 'Inv' : src === 'ingame' ? 'IG' : 'Exch'}
                </button>
              {/each}
            </div>
            <button type="button" class="apply-btn" onclick={applyGlobalAbsorber}
              title="Apply to comparison weapons without an absorber whose MU > absorber MU">
              Apply to all
            </button>
          </div>
        {/if}
      </div>

        <!-- Detail analysis -->
        <div class="detail-panel-section">
          {#if comparisonWeapons.length > 0 && analyses[selectedCompIndex]}
          <div class="dp-selectors">
            {#if baseWeapons.length > 1}
              <label class="dp-sel">
                <span>Base:</span>
                <select class="dp-select" bind:value={selectedBaseIndex}>
                  {#each baseWeapons as bw, i}
                    <option value={i}>{bw.weaponName || `Base ${i + 1}`}</option>
                  {/each}
                </select>
              </label>
            {/if}
            {#if comparisonWeapons.length > 1}
              <label class="dp-sel">
                <span>vs:</span>
                <select class="dp-select" bind:value={selectedCompIndex}>
                  {#each comparisonWeapons as cw, i}
                    <option value={i}>{cw.weaponName || `Weapon ${i + 1}`}</option>
                  {/each}
                </select>
              </label>
            {/if}
          </div>

          {#if analyses[selectedCompIndex]}
          {@const a = analyses[selectedCompIndex]}
            <div class="be-mu-banner">
              <span class="be-mu-label">Break-even Markup</span>
              <span class="be-mu-value">{a.breakEvenMU != null ? a.breakEvenMU.toFixed(1) + '%' : 'N/A'}</span>
            </div>

            <div class="dp-net {a.netProfitabilityPED > 0.005 ? 'positive' : a.netProfitabilityPED < -0.005 ? 'negative' : ''}">
              <span class="dp-net-label">Net Profitability</span>
              <span class="dp-net-value">{formatPED(a.netProfitabilityPED).text}</span>
            </div>

            <!-- Economy stats -->
            <div class="dp-grid">
              <div class="dp-row">
                <span>Efficiency savings</span>
                <span>{a.efficiencySavingsPED != null ? formatPED(a.efficiencySavingsPED).text : 'N/A'}</span>
              </div>
              <div class="dp-row">
                <span>MU cost diff</span>
                <span>{a.premiumDiffPED != null ? a.premiumDiffPED.toFixed(2) + ' PED' : 'N/A'}</span>
              </div>
              <div class="dp-row">
                <span>Efficiency (base / comp)</span>
                <span>{a.baseEfficiency?.toFixed(1) ?? 'N/A'} / {a.compEfficiency?.toFixed(1) ?? 'N/A'} ({formatPct(a.efficiencyDelta)})</span>
              </div>
              <div class="dp-row">
                <span>DPP (base / comp)</span>
                <span>{a.baseDPP?.toFixed(2) ?? 'N/A'} / {a.compDPP?.toFixed(2) ?? 'N/A'} ({formatPct(a.dppDiffPct)})</span>
              </div>
              <div class="dp-row">
                <span>Total uses</span>
                <span>{formatNumber(a.compTotalUses)}</span>
              </div>
              <div class="dp-row">
                <span>Total cycle</span>
                <span>{a.compTotalCyclePED != null ? a.compTotalCyclePED.toFixed(2) + ' PED' : 'N/A'}</span>
              </div>
              <div class="dp-row">
                <span>TT cost / use</span>
                <span>{a.compTTCostPerUsePEC != null ? a.compTTCostPerUsePEC.toFixed(2) + ' PEC' : 'N/A'}</span>
              </div>
              <div class="dp-row">
                <span>MU cost / use</span>
                <span>{a.compPremiumPerUsePEC != null ? a.compPremiumPerUsePEC.toFixed(2) + ' PEC' : 'N/A'}</span>
              </div>
            </div>

            <!-- Combat stats -->
            <h4 class="dp-title">Combat</h4>
            <div class="dp-grid">
              <div class="dp-row">
                <span>DPS (base / comp)</span>
                <span>{a.baseDPS?.toFixed(1) ?? 'N/A'} / {a.compDPS?.toFixed(1) ?? 'N/A'} ({formatPct(a.dpsDiffPct)})</span>
              </div>
              <div class="dp-row">
                <span>Total damage (lifetime)</span>
                <span>{a.compTotalUses != null && compStats[selectedCompIndex]?.totalDamage != null
                  ? formatNumber(Math.round(a.compTotalUses * compStats[selectedCompIndex].totalDamage))
                  : 'N/A'}</span>
              </div>
              {#if mobHP && mobHP > 0}
                <div class="dp-row">
                  <span>Kills / hour (base / comp)</span>
                  <span>{a.baseKillsPerHour?.toFixed(1) ?? 'N/A'} / {a.compKillsPerHour?.toFixed(1) ?? 'N/A'}
                    {#if a.baseKillsPerHour && a.compKillsPerHour}
                      ({formatPct(((a.compKillsPerHour - a.baseKillsPerHour) / a.baseKillsPerHour) * 100)})
                    {/if}
                  </span>
                </div>
                {#if a.extraKillsOverLifetime != null}
                  {@const baseTotalKills = a.compTotalUses && baseStats[selectedBaseIndex]?.totalDamage && mobHP
                    ? (a.compTotalUses * (baseStats[selectedBaseIndex].costPerUse / 100) * baseStats[selectedBaseIndex].dpp) / mobHP
                    : null}
                  <div class="dp-row">
                    <span>Extra kills (lifetime)</span>
                    <span>
                      {a.extraKillsOverLifetime >= 0 ? '+' : ''}{Math.round(a.extraKillsOverLifetime)}
                      {#if baseTotalKills && baseTotalKills > 0}
                        ({formatPct((a.extraKillsOverLifetime / baseTotalKills) * 100)})
                      {/if}
                    </span>
                  </div>
                {/if}
              {/if}
            </div>
          {/if}
        {:else}
          <p class="empty-hint">Add comparison weapons to see the analysis.</p>
        {/if}
        </div>
      </div>
    </div>

  <!-- ===== LIST VIEW (Ranked browser) ===== -->
  {:else if viewMode === 'list'}
    <div class="weapon-browser">
      <div class="browser-controls">
        <input type="text" class="browser-search" placeholder="Filter by name..."
          bind:value={browserSearch} />
        <fieldset class="sort-group">
          <legend>Sort by</legend>
          {#each [['efficiency', 'Efficiency'], ['dpp', 'DPP'], ['dps', 'DPS'], ['totalDamage', 'Damage'], ['totalUses', 'Uses'], ['name', 'Name']] as [key, lbl]}
            <label class="sort-option">
              <input type="radio" name="browserSort" value={key} bind:group={browserSortBy} />
              <span>{lbl}</span>
            </label>
          {/each}
        </fieldset>
      </div>
      <div class="browser-list" role="list">
        {#each rankedWeapons.slice(0, 150) as r, i (r.name)}
          {@const isAdded = addedNames.has(r.name)}
          <button type="button" class="browser-row" class:added={isAdded}
            onclick={() => addFromBrowser(r.name)}
            disabled={isAdded}
            title={isAdded ? 'Already added' : 'Click to add for comparison'}>
            <span class="browser-rank">#{i + 1}</span>
            <span class="browser-name">
              <span class="name-main">{r.name}</span>
              {#if r.type}<span class="name-sub">{r.class} - {r.type}</span>{/if}
            </span>
            <span class="browser-metrics">
              {#if r.efficiency != null}<span class="metric" title="Efficiency">Eff: {r.efficiency.toFixed(1)}</span>{/if}
              {#if r.dpp != null}<span class="metric" title="Damage per PED">DPP: {r.dpp.toFixed(2)}</span>{/if}
              {#if r.dps != null}<span class="metric" title="Damage per second">DPS: {r.dps.toFixed(1)}</span>{/if}
              {#if r.totalDamage != null}<span class="metric" title="Total damage per use">Dmg: {r.totalDamage.toFixed(1)}</span>{/if}
              {#if r.totalUses != null}<span class="metric" title="Total uses before breakage">Uses: {formatNumber(r.totalUses)}</span>{/if}
            </span>
          </button>
        {/each}
        {#if rankedWeapons.length === 0}
          <p class="browser-empty">No (L) weapons found{browserSearch ? ' matching search' : ''}.</p>
        {/if}
      </div>
      {#if rankedWeapons.length > 150}
        <p class="browser-truncated">Showing top 150 of {rankedWeapons.length} weapons.</p>
      {/if}
    </div>

  <!-- ===== TABLE VIEW ===== -->
  {:else if viewMode === 'table'}
    {#if comparisonWeapons.length > 0}
      <ProfitabilityComparisonTable
        {baseWeapons}
        {comparisonWeapons}
        {compStats}
        {allAnalyses}
        bind:selectedBaseIndex
      />
    {:else}
      <p class="empty-hint">Add comparison weapons first (use the List tab to browse, or Config tab to add manually).</p>
    {/if}
  {/if}

  <!-- Import dialog -->
  {#if showImportDialog}
    <div class="modal-overlay" onclick={() => { showImportDialog = false; }}
      onkeydown={(e) => { if (e.key === 'Escape') showImportDialog = false; }}
      role="dialog" tabindex="-1">
      <div class="modal" onclick={(e) => e.stopPropagation()}>
        <div class="modal-header">
          <h3>Import from Loadout</h3>
          <button type="button" class="modal-close" onclick={() => { showImportDialog = false; }}>×</button>
        </div>
        <div class="modal-body">
          {#if importLoading}
            <p>Loading loadouts...</p>
          {:else if importLoadouts.length === 0}
            <p>No saved loadouts found.</p>
          {:else}
            <ul class="import-list">
              {#each importLoadouts as lo (lo.id)}
                <li>
                  <button type="button" class="import-item" onclick={() => importLoadout(lo)}>
                    <span class="import-name">{lo.name}</span>
                    {#if lo.weaponName}
                      <span class="import-weapon">{lo.weaponName}</span>
                    {/if}
                    {#if lo.setCount > 0}
                      <span class="import-sets">{lo.setCount} weapon sets</span>
                    {/if}
                  </button>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .weapon-profitability { display: flex; flex-direction: column; gap: 16px; }

  /* Top bar */
  .top-bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
  .view-tabs { display: flex; gap: 2px; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: 6px; padding: 2px; }
  .view-tab { padding: 6px 14px; font-size: 13px; border: none; background: transparent; color: var(--text-muted); cursor: pointer; border-radius: 4px; }
  .view-tab.active { background: var(--accent-color); color: white; }
  .view-tab:hover:not(.active) { background: var(--hover-color); color: var(--text-color); }
  .top-actions { display: flex; align-items: center; gap: 10px; }
  .mob-hp-label { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-muted); }
  .mob-hp-input { width: 80px; padding: 4px 6px; font-size: 12px; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: 4px; color: var(--text-color); text-align: right; }
  .mob-hp-input:focus { border-color: var(--accent-color); outline: none; }
  .reset-btn { padding: 5px 12px; font-size: 12px; border: 1px solid var(--border-color); background: var(--bg-color); color: var(--text-muted); cursor: pointer; border-radius: 4px; }
  .reset-btn:hover { background: var(--hover-color); color: var(--text-color); }

  /* Config columns: base (left) + compare (center) + detail (right sticky) */
  .config-columns { display: flex; gap: 12px; align-items: flex-start; }
  .config-col { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .config-detail-col {
    flex: 0 0 320px; position: sticky; top: 60px;
    display: flex; flex-direction: column; gap: 10px;
    max-height: calc(100vh - 80px); overflow-y: auto;
  }

  /* Config groups */
  .config-group { display: flex; flex-direction: column; gap: 0; }
  .group-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 6px; }
  .group-header h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--text-color); }
  .group-actions { display: flex; gap: 6px; }
  .add-btn { padding: 4px 10px; font-size: 12px; border: 1px solid var(--accent-color); background: transparent; color: var(--accent-color); cursor: pointer; border-radius: 4px; }
  .add-btn:hover, .add-btn.active { background: var(--accent-color); color: white; }
  .config-cards { display: flex; flex-direction: column; gap: 6px; }

  .empty-hint { font-size: 13px; color: var(--text-muted); margin: 0; padding: 16px; text-align: center; background: var(--bg-color); border: 1px dashed var(--border-color); border-radius: 8px; }

  /* Comparison card quick results */
  .comp-card-wrap { display: flex; flex-direction: column; }
  .comp-result {
    display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
    padding: 5px 10px; cursor: pointer;
    background: var(--bg-color); border: 1px solid var(--border-color); border-top: none;
    border-radius: 0 0 8px 8px; font-size: 11px;
  }
  .comp-result:hover { background: var(--hover-color); }
  .comp-result .be-mu { font-weight: 600; color: var(--accent-color); }
  .comp-result .net-val { font-weight: 600; }
  .comp-result .net-val.positive { color: var(--success-color, #27ae60); }
  .comp-result .net-val.negative { color: var(--danger-color, #e74c3c); }
  .comp-result .delta-stat { color: var(--text-muted); }

  /* Detail panel (right column) */
  .detail-panel-section {
    background: var(--secondary-color); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 8px;
  }
  .dp-title { margin: 0; font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .dp-selectors { display: flex; gap: 8px; flex-wrap: wrap; }
  .dp-sel { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-muted); }
  .dp-select { padding: 3px 6px; font-size: 12px; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: 4px; color: var(--text-color); max-width: 180px; }

  /* Break-even banner */
  .be-mu-banner {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 12px; background: var(--bg-color); border-radius: 6px;
    border: 2px solid var(--accent-color);
  }
  .be-mu-label { font-size: 13px; font-weight: 600; color: var(--text-color); }
  .be-mu-value { font-size: 18px; font-weight: 700; color: var(--accent-color); }

  /* Net result */
  .dp-net {
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 10px; background: var(--bg-color); border-radius: 5px;
  }
  .dp-net-label { font-size: 12px; font-weight: 600; color: var(--text-color); }
  .dp-net-value { font-size: 15px; font-weight: 700; }
  .dp-net.positive .dp-net-value { color: var(--success-color, #27ae60); }
  .dp-net.negative .dp-net-value { color: var(--danger-color, #e74c3c); }

  /* Stats grid */
  .dp-grid { display: flex; flex-direction: column; gap: 3px; }
  .dp-row { display: flex; justify-content: space-between; align-items: center; font-size: 12px; padding: 2px 0; }
  .dp-row span:first-child { color: var(--text-muted); }
  .dp-row span:last-child { color: var(--text-color); font-variant-numeric: tabular-nums; text-align: right; }

  /* Absorber controls in detail panel */
  .absorber-controls { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  .wcp-field { display: flex; align-items: center; gap: 3px; font-size: 11px; color: var(--text-muted); }
  .wcp-num { width: 64px; padding: 4px 5px; font-size: 12px; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: 4px; color: var(--text-color); text-align: right; }
  .wcp-num:focus { border-color: var(--accent-color); outline: none; }
  .wcp-src-btns { display: flex; gap: 1px; }
  .src-btn { padding: 3px 5px; font-size: 10px; border: 1px solid var(--border-color); background: var(--bg-color); color: var(--text-muted); cursor: pointer; border-radius: 3px; }
  .src-btn.active { background: var(--accent-color); border-color: var(--accent-color); color: white; }
  .src-btn:hover:not(.active) { background: var(--hover-color); }
  .apply-btn { padding: 4px 10px; font-size: 11px; border: 1px solid var(--accent-color); background: transparent; color: var(--accent-color); cursor: pointer; border-radius: 4px; white-space: nowrap; }
  .apply-btn:hover { background: var(--accent-color); color: white; }

  /* Import dialog */
  .modal-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); display: flex; justify-content: center; align-items: center; z-index: 200; }
  .modal { background: var(--secondary-color); border: 1px solid var(--border-color); border-radius: 8px; width: 460px; max-width: calc(100% - 32px); max-height: 70vh; display: flex; flex-direction: column; }
  .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border-color); }
  .modal-header h3 { margin: 0; font-size: 15px; }
  .modal-close { background: transparent; border: none; font-size: 20px; color: var(--text-muted); cursor: pointer; padding: 0 4px; }
  .modal-close:hover { color: var(--text-color); }
  .modal-body { padding: 12px 16px; overflow-y: auto; }
  .import-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
  .import-item { display: flex; flex-direction: column; width: 100%; padding: 8px 12px; text-align: left; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: 6px; cursor: pointer; color: var(--text-color); gap: 2px; }
  .import-item:hover { background: var(--hover-color); border-color: var(--accent-color); }
  .import-name { font-size: 13px; font-weight: 500; }
  .import-weapon { font-size: 11px; color: var(--text-muted); }
  .import-sets { font-size: 11px; color: var(--accent-color); }

  /* Weapon browser (List view) */
  .weapon-browser { background: var(--secondary-color); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px; }
  .browser-controls { display: flex; gap: 12px; align-items: flex-start; flex-wrap: wrap; margin-bottom: 8px; }
  .browser-search { flex: 1; min-width: 160px; padding: 6px 10px; font-size: 13px; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: 6px; color: var(--text-color); }
  .browser-search:focus { outline: none; border-color: var(--accent-color); }
  .sort-group { border: 1px solid var(--border-color); border-radius: 6px; padding: 4px 8px; display: flex; flex-wrap: wrap; gap: 2px 10px; align-items: center; }
  .sort-group legend { font-size: 11px; color: var(--text-muted); padding: 0 4px; }
  .sort-option { display: flex; align-items: center; gap: 3px; font-size: 12px; color: var(--text-muted); cursor: pointer; white-space: nowrap; }
  .sort-option input[type="radio"] { margin: 0; width: 13px; height: 13px; }
  .sort-option:has(input:checked) { color: var(--accent-color); font-weight: 500; }

  .browser-list { max-height: 500px; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
  .browser-row { display: flex; align-items: center; gap: 8px; padding: 6px 8px; background: var(--bg-color); border: 1px solid transparent; border-radius: 5px; cursor: pointer; text-align: left; color: var(--text-color); font-size: 12px; }
  .browser-row:hover:not(:disabled) { background: var(--hover-color); border-color: var(--accent-color); }
  .browser-row:disabled { cursor: default; }
  .browser-row.added { opacity: 0.5; border-color: var(--border-color); background: var(--bg-color); }
  .browser-rank { color: var(--text-muted); font-size: 11px; min-width: 28px; text-align: right; flex-shrink: 0; }
  .browser-name { display: flex; flex-direction: column; min-width: 0; flex: 1; }
  .browser-name .name-main { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }
  .browser-name .name-sub { font-size: 10px; color: var(--text-muted); }
  .browser-metrics { display: flex; gap: 8px; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }
  .browser-metrics .metric { font-size: 11px; color: var(--text-muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
  .browser-empty { text-align: center; color: var(--text-muted); font-size: 12px; padding: 16px; margin: 0; }
  .browser-truncated { text-align: center; font-size: 11px; color: var(--text-muted); margin: 6px 0 0; }

  @media (max-width: 1100px) {
    .config-columns { flex-wrap: wrap; }
    .config-detail-col { flex: 1 1 100%; position: static; max-height: none; }
  }

  @media (max-width: 768px) {
    .config-columns { flex-direction: column; }
  }

  @media (max-width: 768px) {
    .top-bar { flex-direction: column; align-items: flex-start; }
    .browser-metrics { display: none; }
  }
</style>

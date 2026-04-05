<!--
  @component ArmorVsMob
  First Gear Advisor sub-tool: compare a full armor set (+ optional plating, Ice Shield, defense enhancers)
  against a mob's damage composition and rank candidates on either side.

  Layout is fixed: armor on the LEFT, mob on the RIGHT, stacks vertically on mobile.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import EntityPicker from './EntityPicker.svelte';
  import PoolSelectionDialog from './PoolSelectionDialog.svelte';
  import MobDamageGrid from '$lib/components/wiki/mobs/MobDamageGrid.svelte';
  import { encodeURIComponentSafe } from '$lib/util';
  import { createPreference } from '$lib/preferences.js';
  import {
    DEFENSE_TYPES,
    MAX_ENHANCERS,
    computeEffectiveDefense,
    computeAttackBreakdown,
    computeDecayRate,
    rankMobs,
    rankMobsChunked,
    rankMaturitiesChunked,
    rankArmorsChunked,
    buildDetails,
    hasDamageData
  } from './armorVsMob.js';

  let { armorSets = [], armorPlatings = [], mobs = [] } = $props();

  // Selections
  let armorSet = $state(null);
  let plating = $state(null);
  let iceShield = $state(false);
  let enhancers = $state(0);
  let dmgReduction = $state(0); // -100..100, % reduction to pre-mitigation damage
  let mob = $state(null);
  let scope = $state('average'); // 'lowest' | 'average' | 'highest'
  let rankBy = $state('mitigation'); // 'typeMatch' | 'mitigation' | 'damageTaken'
  let includePlates = $state(true); // include top-3 plate pairings in armor ranking
  let ulPlatesOnly = $state(false); // restrict plates to unlimited (non-"(L)")

  // Candidate-pool filters (empty = use all) — persisted to user preferences
  // (DB when logged in, localStorage otherwise).
  let poolArmorNames = $state([]);
  let poolPlateNames = $state([]);
  let poolArmorEnhancers = $state({}); // per-armor enhancer overrides
  let showPoolDialog = $state(false);
  let poolLoaded = $state(false);

  // Mob ranking planet filter ('All' = no filter)
  let mobPlanetFilter = $state('All');
  // View mode for mob ranking: per-mob or per-maturity
  let viewMaturities = $state(false);
  // Expected damage-taken range filter (null/empty = no bound)
  let damageMin = $state('');
  let damageMax = $state('');
  let mobPlanets = $derived.by(() => {
    const set = new Set();
    for (const m of mobs || []) {
      const p = m?.Planet?.Name;
      if (p) set.add(p);
    }
    return ['All', ...Array.from(set).sort()];
  });

  const poolPref = createPreference('gear-advisor.pool', {
    armorNames: [],
    plateNames: [],
    armorEnhancers: {}
  }, { debounceMs: 400 });

  onMount(async () => {
    const userId = $page.data?.user?.id ?? null;
    await poolPref.load(userId);
    let stored;
    poolPref.subscribe(v => stored = v)();
    if (stored) {
      poolArmorNames = Array.isArray(stored.armorNames) ? stored.armorNames : [];
      poolPlateNames = Array.isArray(stored.plateNames) ? stored.plateNames : [];
      poolArmorEnhancers = stored.armorEnhancers && typeof stored.armorEnhancers === 'object'
        ? stored.armorEnhancers
        : {};
    }
    poolLoaded = true;
  });

  // Persist pool filters whenever they change (after initial load)
  $effect(() => {
    const _names = poolArmorNames;
    const _plates = poolPlateNames;
    const _enh = poolArmorEnhancers;
    if (!poolLoaded) return;
    poolPref.set({
      armorNames: _names,
      plateNames: _plates,
      armorEnhancers: _enh
    });
  });

  // Derived: effective defense for current armor config (null if no armor)
  let defense = $derived(armorSet
    ? computeEffectiveDefense(armorSet, plating, iceShield, enhancers)
    : null);

  // Pre-mitigation damage multiplier (clamped to ≥ 0)
  let dmgMultiplier = $derived(Math.max(0, 1 - (Number(dmgReduction) || 0) / 100));

  // Decay rate (PEC per unit of damage absorbed) for current armor + plating
  let decayRate = $derived(armorSet ? computeDecayRate(armorSet, plating) : 0);

  // Derived: details breakdown for mob x defense (null if either missing)
  let details = $derived(mob && defense ? buildDetails(mob, defense, dmgMultiplier) : null);

  // Unique attack compositions across all maturities — one bar per distinct spread.
  // Shown above the details table, similar to the info box on the mob wiki page.
  let attackCompositions = $derived.by(() => {
    if (!mob) return [];
    const seen = new Map();
    for (const mat of mob.Maturities || []) {
      for (const atk of mat.Attacks || []) {
        // Skip all-zero composition
        const anyDmg = DEFENSE_TYPES.some(t => (atk?.Damage?.[t] ?? 0) > 0);
        if (!anyDmg) continue;
        const sig = (atk.Name || '') + '|' + DEFENSE_TYPES
          .map(t => `${t}:${atk.Damage?.[t] ?? 0}`).join(',');
        if (!seen.has(sig)) {
          seen.set(sig, { name: atk.Name || 'Attack', damageSpread: atk.Damage });
        }
      }
    }
    return Array.from(seen.values());
  });

  // Flat rows for the details table: one row per (maturity × attack).
  let flatRows = $derived.by(() => {
    if (!mob || !defense) return [];
    const rows = [];
    // Sort maturities by level (nulls last, stable)
    const mats = Array.isArray(mob.Maturities)
      ? mob.Maturities.map((m, i) => ({ m, i })).sort((a, b) => {
          const la = a.m?.Properties?.Level;
          const lb = b.m?.Properties?.Level;
          if (la == null && lb == null) return a.i - b.i;
          if (la == null) return 1;
          if (lb == null) return -1;
          return la - lb;
        }).map(x => x.m)
      : [];
    for (const mat of mats) {
      for (const atk of (mat.Attacks || [])) {
        const br = computeAttackBreakdown(atk, defense, dmgMultiplier);
        rows.push({
          maturityName: mat.Name || '',
          maturityLevel: mat?.Properties?.Level ?? null,
          attackName: br.name,
          totalDamage: atk?.TotalDamage ?? null,
          takenMin: br.takenMin,
          takenAvg: br.expectedTaken,
          takenMax: br.takenMax,
          mitigation: br.mitigation,
          critTaken: br.critTaken,
          decayThisAttack: br.expectedBlocked * decayRate,
          hasData: br.totalAvg > 0
        });
      }
    }
    return rows;
  });

  // Mob ranking — computed asynchronously in chunks so the UI stays responsive
  // when ranking ~500+ mobs against a selected armor.
  let mobRanking = $state([]);
  let mobRankingLoading = $state(false);

  $effect(() => {
    // declare reactive deps
    const _mob = mob;
    const _armorSet = armorSet;
    const _defense = defense;
    const _scope = scope;
    const _rankBy = rankBy;
    const _dmgMultiplier = dmgMultiplier;
    const _decayRate = decayRate;
    const _planet = mobPlanetFilter;
    const _viewMaturities = viewMaturities;

    if (!_armorSet || _mob) {
      mobRanking = [];
      mobRankingLoading = false;
      return;
    }

    mobRankingLoading = true;
    const controller = { aborted: false };

    const filteredMobs = _planet === 'All'
      ? mobs
      : (mobs || []).filter(m => m?.Planet?.Name === _planet);

    const promise = _viewMaturities
      ? rankMaturitiesChunked(
          filteredMobs, _defense, _dmgMultiplier, _rankBy, _decayRate,
          { chunkSize: 100, signal: controller }
        )
      : rankMobsChunked(
          filteredMobs, _defense, _scope, _dmgMultiplier, _rankBy, _decayRate,
          { chunkSize: 100, signal: controller }
        );

    promise.then(result => {
      if (controller.aborted) return;
      mobRanking = result ?? [];
      mobRankingLoading = false;
    }).catch(() => {
      if (!controller.aborted) mobRankingLoading = false;
    });

    return () => { controller.aborted = true; };
  });

  // Apply damage-range filter as a display filter on the ranking
  let displayedMobRanking = $derived.by(() => {
    const lo = damageMin === '' || damageMin == null ? null : Number(damageMin);
    const hi = damageMax === '' || damageMax == null ? null : Number(damageMax);
    if (lo == null && hi == null) return mobRanking;
    return mobRanking.filter(r => {
      if (r.damageTaken == null) return false;
      if (lo != null && r.damageTaken < lo) return false;
      if (hi != null && r.damageTaken > hi) return false;
      return true;
    });
  });
  // Armor ranking is computed asynchronously in chunks so the UI stays
  // responsive — loading spinner shows while hundreds of armor/plate combos
  // are evaluated.
  let armorRanking = $state([]);
  let armorRankingLoading = $state(false);

  $effect(() => {
    // declare reactive deps
    const _mob = mob;
    const _armorSet = armorSet;
    const _scope = scope;
    const _rankBy = rankBy;
    const _iceShield = iceShield;
    const _enhancers = enhancers;
    const _dmgMultiplier = dmgMultiplier;
    const _includePlates = includePlates;
    const _ulPlatesOnly = ulPlatesOnly;
    const _poolArmorNames = poolArmorNames;
    const _poolPlateNames = poolPlateNames;
    const _poolArmorEnhancers = poolArmorEnhancers;

    if (_armorSet || !_mob) {
      armorRanking = [];
      armorRankingLoading = false;
      return;
    }

    armorRankingLoading = true;
    const controller = { aborted: false };

    // If user narrowed the armor pool explicitly, deepen plate search to 10/armor
    const hasArmorPool = _poolArmorNames.length > 0;
    const hasPlatePool = _poolPlateNames.length > 0;
    const platesPerArmor = hasArmorPool ? 10 : 3;

    rankArmorsChunked(
      armorSets, armorPlatings, _mob,
      { iceShield: _iceShield, enhancers: _enhancers, dmgMultiplier: _dmgMultiplier },
      _scope, _rankBy,
      {
        includePlates: _includePlates,
        platesPerArmor,
        ulPlatesOnly: _ulPlatesOnly,
        armorFilter: hasArmorPool ? new Set(_poolArmorNames) : null,
        plateFilter: hasPlatePool ? new Set(_poolPlateNames) : null,
        armorEnhancers: hasArmorPool ? _poolArmorEnhancers : null
      },
      { chunkSize: 40, signal: controller }
    ).then(result => {
      if (controller.aborted) return;
      armorRanking = result ?? [];
      armorRankingLoading = false;
    }).catch(() => {
      if (!controller.aborted) armorRankingLoading = false;
    });

    return () => { controller.aborted = true; };
  });

  // Derived panel modes: 'input' | 'ranking' | 'details'
  // - both empty → both inputs
  // - only armor → armor input (with selection visible), mob panel ranks mobs
  // - only mob → mob input (with selection visible), armor panel ranks armors
  // - both filled → both panels show their summaries
  let armorPanelMode = $derived(
    armorSet && mob ? 'details'
    : !armorSet && mob ? 'ranking'
    : 'input'
  );
  let mobPanelMode = $derived(
    armorSet && mob ? 'details'
    : armorSet && !mob ? 'ranking'
    : 'input'
  );

  function handleReset() {
    armorSet = null;
    plating = null;
    iceShield = false;
    enhancers = 0;
    dmgReduction = 0;
    mob = null;
    scope = 'average';
    rankBy = 'mitigation';
    ulPlatesOnly = false;
    mobPlanetFilter = 'All';
    viewMaturities = false;
    damageMin = '';
    damageMax = '';
    // Intentionally does NOT clear pool filters — those are persisted.
    // Use "Clear all" inside the Restrict Pool dialog to clear them.
  }

  function formatNum(n, digits = 1) {
    if (n == null || Number.isNaN(n)) return '—';
    return Number(n).toFixed(digits);
  }

  function formatPct(n, digits = 1) {
    if (n == null || Number.isNaN(n)) return '—';
    return `${Number(n).toFixed(digits)}%`;
  }

  function clampEnhancers(v) {
    const n = Number.parseInt(v, 10);
    if (!Number.isFinite(n) || n < 0) return 0;
    if (n > MAX_ENHANCERS) return MAX_ENHANCERS;
    return n;
  }
</script>

<div class="avm-root">
  <div class="avm-grid">
    <!-- ARMOR PANEL (left) -->
    <section class="avm-panel" aria-label="Armor side">
      <header class="panel-header">
        <h3>Armor</h3>
        {#if armorSet && mob}
          <button
            type="button"
            class="back-btn"
            onclick={() => { armorSet = null; plating = null; }}
            title="Clear armor to return to the armor ranking for this mob"
          >← Back to armor results</button>
        {/if}
      </header>

      {#if armorPanelMode === 'input' || armorPanelMode === 'details'}
        <div class="panel-body inputs">
          <label class="field">
            <span class="field-label">Armor set</span>
            <EntityPicker
              entities={armorSets}
              selected={armorSet}
              placeholder="Search armor set..."
              onselect={(a) => { armorSet = a; }}
              onclear={() => { armorSet = null; }}
            />
          </label>

          <label class="field">
            <span class="field-label">Plating <span class="hint">(optional)</span></span>
            <EntityPicker
              entities={armorPlatings}
              selected={plating}
              placeholder="Search plating..."
              onselect={(p) => { plating = p; }}
              onclear={() => { plating = null; }}
            />
          </label>

          <label class="field inline" title="+75 Impact/Stab/Cut/Shrapnel/Penetration/Burn defense">
            <input type="checkbox" bind:checked={iceShield} />
            <span>Ice Shield</span>
          </label>

          <label class="field inline">
            <span class="field-label">Def. enhancers</span>
            <input
              type="number"
              class="num-input"
              min="0"
              max={MAX_ENHANCERS}
              value={enhancers}
              oninput={(e) => enhancers = clampEnhancers(e.target.value)}
            />
          </label>

          <label class="field inline" title="Reduces pre-mitigation damage. Negative values amplify incoming damage.">
            <span class="field-label">% Dmg reduction</span>
            <input
              type="number"
              class="num-input"
              step="1"
              value={dmgReduction}
              oninput={(e) => dmgReduction = Number.parseFloat(e.target.value) || 0}
            />
          </label>
        </div>
      {/if}

      {#if armorPanelMode === 'ranking'}
        <div class="panel-body">
          <div class="ranking-header">
            <p class="panel-caption">Armor sets ranked vs <strong>{mob?.Name}</strong> ({scope}):</p>
            <label class="inline-check">
              <input type="checkbox" bind:checked={includePlates} />
              <span>Include top-3 plate pairings</span>
            </label>
            <label class="inline-check" class:disabled={!includePlates}>
              <input type="checkbox" bind:checked={ulPlatesOnly} disabled={!includePlates} />
              <span>UL plates only</span>
            </label>
            <button
              type="button"
              class="pool-btn"
              onclick={() => { showPoolDialog = true; }}
              disabled={!includePlates}
              title="Restrict the candidate pool to specific armors / plates"
            >
              Restrict Pool…
              {#if poolArmorNames.length > 0 || poolPlateNames.length > 0}
                <span class="pool-badge">{poolArmorNames.length || '·'}/{poolPlateNames.length || '·'}</span>
              {/if}
            </button>
            {#if armorRankingLoading && armorRanking.length > 0}
              <span class="refresh-indicator"><span class="spinner small"></span> updating…</span>
            {/if}
          </div>
          {#if armorRankingLoading && armorRanking.length === 0}
            <div class="loading-state">
              <span class="spinner"></span>
              <span>Ranking armors…</span>
            </div>
          {:else if armorRanking.length === 0}
            <p class="empty-msg">No candidates — this mob has no attack data.</p>
          {:else}
            <div class="ranking-list" role="list">
              {#each armorRanking.slice(0, 150) as r, i (r.name + '|' + (r.plating?.Name || '') + '|' + i)}
                <button
                  type="button"
                  class="ranking-row"
                  class:no-damage={!r.hasTotalDamage && r.hasComposition}
                  class:no-data={!r.hasComposition}
                  class:with-plate={!!r.plating}
                  onclick={() => { armorSet = r.armorSet; plating = r.plating; }}
                >
                  <span class="rank-idx">#{i + 1}</span>
                  <span class="rank-name">
                    <span class="name-main">
                      {r.name}{#if r.plating}&nbsp;<span class="plate-tag">+ {r.plating.Name}</span>{/if}
                    </span>
                    {#if r.maturityLabel}<span class="rank-sub">{r.maturityLabel}{#if r.maturityLevel != null}&nbsp;· L{r.maturityLevel}{/if}</span>{/if}
                  </span>
                  <span class="rank-metric">
                    {#if r.hasTotalDamage}
                      <span class="mit" title="Expected damage mitigated vs incoming (integrated over the damage roll range)">{formatPct(r.mitigationPct, 1)} mitigated</span>
                      <span class="type-score" title="How well armor's defenses align with the mob's damage composition (fraction of total armor defense deployed vs this mob)">{formatPct(r.typeScore * 100, 1)} type-match</span>
                      <span class="taken" title="Avg damage taken per hit">–{formatNum(r.damageTaken)}/hit</span>
                      {#if r.decayPerAttack != null}
                        {#if r.decayPerAttackMin != null && r.decayPerAttackMax != null && Math.abs(r.decayPerAttackMax - r.decayPerAttackMin) > 0.0005}
                          <span class="decay" title="Armor/plate decay per attack across maturities (PEC)">{formatNum(r.decayPerAttackMin, 3)}–{formatNum(r.decayPerAttackMax, 3)} PEC decay</span>
                        {:else}
                          <span class="decay" title="Armor/plate decay per attack (PEC)">{formatNum(r.decayPerAttack, 3)} PEC decay</span>
                        {/if}
                      {/if}
                    {:else if r.hasComposition}
                      <span class="type-score primary" title="How well armor's defenses align with the mob's damage composition (total damage unknown for this mob)">{formatPct(r.typeScore * 100, 1)} type-match</span>
                      <span class="warn" title="This mob has no TotalDamage recorded — mitigation % can't be computed">⚠ no total dmg</span>
                    {:else}
                      <span class="err" title="This mob has no damage composition or total damage recorded — it cannot be scored">✕ no damage data</span>
                    {/if}
                  </span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      {/if}

      {#if armorSet && armorPanelMode !== 'ranking'}
        <div class="panel-body details-summary">
          <h4 class="sub-title">{armorSet.Name}</h4>
          {#if plating}<div class="chip">+ {plating.Name}</div>{/if}
          {#if iceShield}<div class="chip">+ Ice Shield</div>{/if}
          {#if enhancers > 0}<div class="chip">+ {enhancers} enhancer{enhancers !== 1 ? 's' : ''}</div>{/if}
          {#if dmgReduction !== 0}<div class="chip">{dmgReduction > 0 ? '-' : '+'}{Math.abs(dmgReduction)}% dmg</div>{/if}

          {#if defense}
            <h5 class="defense-title">Effective defense</h5>
            <div class="defense-grid">
              {#each DEFENSE_TYPES as type}
                <div class="def-cell">
                  <span class="def-label" style="color: var(--damage-{type.toLowerCase()})">
                    <span class="def-label-full">{type}</span>
                    <span class="def-label-short">{type.slice(0, 3)}</span>
                  </span>
                  <span class="def-value">{formatNum(defense[type])}</span>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </section>

    <!-- MOB PANEL (right) -->
    <section class="avm-panel" aria-label="Mob side">
      <header class="panel-header">
        <h3>Mob</h3>
        {#if armorSet && mob}
          <button
            type="button"
            class="back-btn"
            onclick={() => { mob = null; }}
            title="Clear mob to return to the mob ranking for this armor"
          >← Back to mob results</button>
        {/if}
      </header>

      {#if mobPanelMode === 'input' || mobPanelMode === 'details'}
        <div class="panel-body inputs">
          <label class="field">
            <span class="field-label">Mob</span>
            <EntityPicker
              entities={mobs}
              selected={mob}
              placeholder="Search mob..."
              onselect={(m) => { mob = m; }}
              onclear={() => { mob = null; }}
            />
          </label>
        </div>
      {/if}

      {#if mobPanelMode === 'ranking'}
        <div class="panel-body">
          <div class="ranking-header">
            <p class="panel-caption">
              {viewMaturities ? 'Maturities' : 'Mobs'} ranked vs <strong>{armorSet?.Name}</strong>{viewMaturities ? '' : ` (${scope})`}
              {#if mobRankingLoading && mobRanking.length > 0}
                <span class="refresh-indicator"><span class="spinner small"></span> updating…</span>
              {/if}
            </p>
          </div>
          <div class="mob-filters">
            <label class="inline-check">
              <input type="checkbox" bind:checked={viewMaturities} />
              <span>Per maturity</span>
            </label>
            <label class="planet-filter">
              <span class="planet-label">Planet:</span>
              <select bind:value={mobPlanetFilter} class="planet-select">
                {#each mobPlanets as planet}
                  <option value={planet}>{planet}</option>
                {/each}
              </select>
            </label>
            <label class="dmg-range">
              <span class="planet-label">Dmg/hit:</span>
              <input
                type="number"
                class="dmg-input"
                placeholder="min"
                min="0"
                bind:value={damageMin}
              />
              <span class="range-sep">–</span>
              <input
                type="number"
                class="dmg-input"
                placeholder="max"
                min="0"
                bind:value={damageMax}
              />
            </label>
          </div>
          {#if mobRankingLoading && mobRanking.length === 0}
            <div class="loading-state">
              <span class="spinner"></span>
              <span>Ranking mobs…</span>
            </div>
          {:else if mobRanking.length === 0}
            <p class="empty-msg">No ranked mobs — none have attack data.</p>
          {:else if displayedMobRanking.length === 0}
            <p class="empty-msg">No results match the damage-range filter.</p>
          {:else}
            <div class="ranking-list" role="list">
              {#each displayedMobRanking.slice(0, 200) as r, i (r.name + '|' + (r.maturityLabel || '') + '|' + i)}
                <button
                  type="button"
                  class="ranking-row"
                  class:no-damage={!r.hasTotalDamage && r.hasComposition}
                  class:no-data={!r.hasComposition}
                  onclick={() => { mob = r.mob; }}
                >
                  <span class="rank-idx">#{i + 1}</span>
                  <span class="rank-name">
                    <span class="name-main">{r.name}</span>
                    {#if r.maturityLabel}<span class="rank-sub">{r.maturityLabel}{#if r.maturityLevel != null}&nbsp;· L{r.maturityLevel}{/if}</span>{/if}
                  </span>
                  <span class="rank-metric">
                    {#if r.hasTotalDamage}
                      <span class="mit" title="Expected damage mitigated vs incoming (integrated over the damage roll range)">{formatPct(r.mitigationPct, 1)} mitigated</span>
                      <span class="type-score" title="How well armor's defenses align with the mob's damage composition (fraction of total armor defense deployed vs this mob)">{formatPct(r.typeScore * 100, 1)} type-match</span>
                      <span class="taken" title="Avg damage taken per hit">–{formatNum(r.damageTaken)}/hit</span>
                      {#if r.decayPerAttack != null}
                        {#if r.decayPerAttackMin != null && r.decayPerAttackMax != null && Math.abs(r.decayPerAttackMax - r.decayPerAttackMin) > 0.0005}
                          <span class="decay" title="Armor/plate decay per attack across maturities (PEC)">{formatNum(r.decayPerAttackMin, 3)}–{formatNum(r.decayPerAttackMax, 3)} PEC decay</span>
                        {:else}
                          <span class="decay" title="Armor/plate decay per attack (PEC)">{formatNum(r.decayPerAttack, 3)} PEC decay</span>
                        {/if}
                      {/if}
                    {:else if r.hasComposition}
                      <span class="type-score primary" title="How well armor's defenses align with the mob's damage composition (total damage unknown for this mob)">{formatPct(r.typeScore * 100, 1)} type-match</span>
                      <span class="warn" title="This mob has no TotalDamage recorded — mitigation % can't be computed">⚠ no total dmg</span>
                    {:else}
                      <span class="err" title="This mob has no damage composition or total damage recorded — it cannot be scored">✕ no damage data</span>
                    {/if}
                  </span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      {/if}

      {#if mobPanelMode === 'details' && mob}
        <div class="panel-body details">
          <h4 class="sub-title">{mob.Name}</h4>

          {#if attackCompositions.length > 0}
            <div class="composition-summary">
              {#each attackCompositions as comp}
                <MobDamageGrid damageSpread={comp.damageSpread} label={comp.name} />
              {/each}
            </div>
          {/if}

          {#if flatRows.length > 0}
            <table class="fancy-table">
              <thead>
                <tr>
                  <th>Maturity</th>
                  <th>Attack</th>
                  <th class="num">Dmg</th>
                  <th class="num" title="Damage taken at lowest roll / expected avg / max roll (armor caps per-type)">Taken (min/exp/max)</th>
                  <th class="num" title="Max crit damage taken (2× max damage, 20% armor pierce)">Max Crit Dmg</th>
                  <th class="num" title="Armor/plate decay per attack (PEC)">Decay</th>
                  <th class="num">Mit</th>
                </tr>
              </thead>
              <tbody>
                {#each flatRows as row, i (i)}
                  <tr class:no-data-row={!row.hasData}>
                    <td>
                      <span class="cell-main">{row.maturityName}</span>
                      {#if row.maturityLevel != null}<span class="cell-sub">L{row.maturityLevel}</span>{/if}
                    </td>
                    <td>{row.attackName}</td>
                    <td class="num" class:muted={row.totalDamage == null}>
                      {row.totalDamage != null ? formatNum(row.totalDamage, 0) : '—'}
                    </td>
                    {#if row.hasData}
                      <td class="num">{formatNum(row.takenMin)} / {formatNum(row.takenAvg)} / {formatNum(row.takenMax)}</td>
                      <td class="num crit-cell">{formatNum(row.critTaken)}</td>
                      <td class="num decay-cell">{formatNum(row.decayThisAttack, 3)}</td>
                      <td class="num mit-cell">{formatPct(row.mitigation * 100, 0)}</td>
                    {:else}
                      <td class="num muted">—</td>
                      <td class="num muted">—</td>
                      <td class="num muted">—</td>
                      <td class="num muted">—</td>
                    {/if}
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}

          {#if !hasDamageData(mob)}
            <div class="missing-data-cta">
              <p class="missing-data-title">No total damage data for this mob.</p>
              <p class="missing-data-hint">Help the community by adding it on the mob's wiki page.</p>
              <a
                class="missing-data-link"
                href={`/information/mobs/${encodeURIComponentSafe(mob.Name)}?mode=edit`}
                target="_blank"
                rel="noopener"
              >Add damage info →</a>
            </div>
          {/if}
        </div>
      {/if}
    </section>
  </div>

  <!-- Shared action row -->
  <div class="avm-actions">
    <div class="scope-stack">
      <fieldset class="scope-group">
        <legend>Maturity scope</legend>
        <label><input type="radio" name="scope" value="lowest" bind:group={scope} /> Lowest</label>
        <label><input type="radio" name="scope" value="average" bind:group={scope} /> Average</label>
        <label><input type="radio" name="scope" value="highest" bind:group={scope} /> Highest</label>
      </fieldset>

      <fieldset class="scope-group">
        <legend>Rank by</legend>
        <label><input type="radio" name="rankBy" value="mitigation" bind:group={rankBy} /> % Mitigation</label>
        <label><input type="radio" name="rankBy" value="damageTaken" bind:group={rankBy} /> Damage taken</label>
        <label><input type="radio" name="rankBy" value="typeMatch" bind:group={rankBy} /> Type-match</label>
      </fieldset>
    </div>

    <div class="btn-row">
      <button class="btn" onclick={handleReset}>Reset</button>
    </div>
  </div>
</div>

{#if showPoolDialog}
  <PoolSelectionDialog
    {armorSets}
    {armorPlatings}
    initialArmorNames={poolArmorNames}
    initialPlateNames={poolPlateNames}
    initialArmorEnhancers={poolArmorEnhancers}
    defaultEnhancers={enhancers}
    onclose={() => { showPoolDialog = false; }}
    onapply={(e) => {
      poolArmorNames = e.armorNames;
      poolPlateNames = e.plateNames;
      poolArmorEnhancers = e.armorEnhancers;
    }}
  />
{/if}

<style>
  .avm-root {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 16px;
    max-width: 1400px;
    margin: 0 auto;
    width: 100%;
    box-sizing: border-box;
  }

  .avm-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .avm-panel {
    display: flex;
    flex-direction: column;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    min-width: 0;
    /* overflow must stay visible so the EntityPicker dropdown can overflow */
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-color);
    background-color: var(--primary-color);
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
  }

  .panel-header h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-color);
  }

  .panel-body {
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .panel-body.inputs .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .panel-body.inputs .field.inline {
    flex-direction: row;
    align-items: center;
    gap: 8px;
    flex-wrap: nowrap;
    justify-content: flex-start;
  }

  .panel-body.inputs .field.inline .field-label {
    flex-shrink: 0;
  }

  .field-label {
    font-size: 12px;
    color: var(--text-muted);
    font-weight: 500;
  }

  .hint {
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 400;
  }

  .num-input {
    width: 70px;
    padding: 6px 8px;
    font-size: 13px;
    background-color: var(--bg-color, var(--secondary-color));
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
  }

  /* Ranking list */
  .panel-caption {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
  }

  .ranking-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-height: 420px;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 4px;
    background-color: var(--primary-color);
  }

  .ranking-row {
    display: grid;
    grid-template-columns: 40px 1fr auto;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    background: transparent;
    border: none;
    border-radius: 4px;
    color: var(--text-color);
    text-align: left;
    cursor: pointer;
    font-size: 12px;
  }

  .ranking-row:hover {
    background-color: var(--hover-color);
  }

  .rank-idx {
    font-size: 11px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  .rank-name {
    display: flex;
    flex-direction: column;
    gap: 1px;
    overflow: hidden;
    min-width: 0;
  }

  .name-main {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .rank-sub {
    font-size: 10px;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .rank-metric {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 1px;
  }

  .rank-metric .mit {
    font-weight: 600;
    color: var(--accent-color);
    font-variant-numeric: tabular-nums;
  }

  .rank-metric .type-score {
    font-size: 10px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  .rank-metric .type-score.primary {
    font-size: 12px;
    font-weight: 600;
    color: var(--accent-color);
  }

  .rank-metric .taken {
    font-size: 10px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  .rank-metric .decay {
    font-size: 10px;
    color: var(--warning-color, #fbbf24);
    font-variant-numeric: tabular-nums;
  }

  .rank-metric .warn {
    font-size: 10px;
    color: var(--warning-color, #fbbf24);
    font-weight: 500;
  }

  .rank-metric .err {
    font-size: 10px;
    color: var(--error-color, #ff6b6b);
    font-weight: 600;
  }

  .ranking-row.no-damage {
    background-color: color-mix(in srgb, var(--warning-color, #fbbf24) 8%, transparent);
  }

  .ranking-row.no-damage:hover {
    background-color: color-mix(in srgb, var(--warning-color, #fbbf24) 16%, var(--hover-color));
  }

  .ranking-row.no-data {
    background-color: color-mix(in srgb, var(--error-color, #ff6b6b) 10%, transparent);
    opacity: 0.85;
  }

  .ranking-row.no-data:hover {
    background-color: color-mix(in srgb, var(--error-color, #ff6b6b) 20%, var(--hover-color));
    opacity: 1;
  }

  .ranking-row.no-data .rank-name {
    font-style: italic;
  }

  .plate-tag {
    font-size: 10px;
    color: var(--accent-color);
    font-weight: 400;
  }

  .ranking-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 4px;
  }

  .inline-check {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-muted);
    cursor: pointer;
    white-space: nowrap;
  }

  .inline-check input[type="checkbox"] {
    margin: 0;
  }

  .planet-filter {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-muted);
  }

  .planet-select {
    padding: 2px 6px;
    font-size: 11px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
  }
  .planet-select:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .mob-filters {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px 14px;
    margin-bottom: 6px;
    padding: 6px 0;
    border-top: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
  }

  .dmg-range {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-muted);
  }

  .dmg-input {
    width: 52px;
    padding: 2px 4px;
    font-size: 11px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    -moz-appearance: textfield;
    appearance: textfield;
  }
  .dmg-input::-webkit-inner-spin-button,
  .dmg-input::-webkit-outer-spin-button {
    -webkit-appearance: none;
    appearance: none;
    margin: 0;
  }
  .dmg-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .range-sep {
    color: var(--text-muted);
    font-size: 11px;
  }

  .inline-check.disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .pool-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    font-size: 11px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    cursor: pointer;
  }
  .pool-btn:hover:not(:disabled) {
    background-color: var(--hover-color);
  }
  .pool-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .pool-badge {
    display: inline-block;
    padding: 0 5px;
    font-size: 10px;
    font-weight: 600;
    background-color: var(--accent-color);
    color: white;
    border-radius: 8px;
    font-variant-numeric: tabular-nums;
  }

  .loading-state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 24px 12px;
    font-size: 12px;
    color: var(--text-muted);
  }

  .refresh-indicator {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
    color: var(--text-muted);
  }

  .spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  .spinner.small {
    width: 10px;
    height: 10px;
    border-width: 1.5px;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .back-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--accent-color);
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .back-btn:hover {
    background-color: var(--hover-color);
  }

  /* Details */
  .sub-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .chip {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    font-size: 11px;
    color: var(--text-muted);
    margin-right: 4px;
  }

  .defense-title {
    margin: 8px 0 4px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
  }

  .defense-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
  }

  .def-cell {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    background-color: var(--primary-color);
    border-radius: 4px;
    font-size: 11px;
  }

  .def-label {
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }

  .def-label-short {
    display: none;
  }

  .def-value {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: var(--text-color);
    flex-shrink: 0;
  }

  /* Below 900px, use 3-letter abbreviations to keep cells compact */
  @media (max-width: 899px) {
    .def-label-full {
      display: none;
    }
    .def-label-short {
      display: inline;
    }
  }

  .composition-summary {
    padding: 10px 12px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    margin-bottom: 4px;
  }

  .fancy-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
  }

  .fancy-table th {
    text-align: left;
    padding: 6px 10px;
    background-color: var(--primary-color);
    color: var(--text-muted);
    font-weight: 500;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
  }

  .fancy-table td {
    padding: 6px 10px;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .fancy-table tbody tr:last-child td {
    border-bottom: none;
  }

  .fancy-table tbody tr:nth-child(even) {
    background-color: color-mix(in srgb, var(--primary-color) 30%, transparent);
  }

  .fancy-table tbody tr:hover {
    background-color: var(--hover-color);
  }

  .fancy-table .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .fancy-table .mit-cell {
    font-weight: 600;
    color: var(--accent-color);
  }

  .fancy-table .crit-cell {
    font-weight: 600;
    color: var(--damage-cut, #e06060);
  }

  .fancy-table .decay-cell {
    color: var(--warning-color, #fbbf24);
  }

  .fancy-table .muted {
    color: var(--text-muted);
  }

  .fancy-table .cell-main {
    display: inline;
  }

  .fancy-table .cell-sub {
    margin-left: 6px;
    font-size: 10px;
    color: var(--text-muted);
  }

  .fancy-table tr.no-data-row {
    opacity: 0.65;
  }

  /* Action row */
  .avm-actions {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 16px;
    padding: 12px 14px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    flex-wrap: wrap;
  }

  .scope-stack {
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }

  .scope-group {
    border: none;
    padding: 0;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .scope-group legend {
    float: none;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    padding-right: 8px;
  }

  .scope-group label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    cursor: pointer;
  }

  .btn-row {
    display: flex;
    gap: 8px;
  }

  .btn {
    padding: 7px 14px;
    font-size: 13px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
    cursor: pointer;
  }

  .btn:hover:not(:disabled) {
    background-color: var(--hover-color);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .empty-msg {
    margin: 0;
    padding: 12px 0;
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
  }

  .missing-data-cta {
    padding: 16px;
    text-align: center;
    background-color: var(--primary-color);
    border: 1px dashed var(--border-color);
    border-radius: 6px;
  }

  .missing-data-title {
    margin: 0 0 4px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .missing-data-hint {
    margin: 0 0 10px;
    font-size: 11px;
    color: var(--text-muted);
  }

  .missing-data-link {
    display: inline-block;
    padding: 6px 12px;
    background-color: var(--accent-color);
    border-radius: 6px;
    color: white;
    text-decoration: none;
    font-size: 12px;
    font-weight: 500;
  }

  .missing-data-link:hover {
    filter: brightness(1.1);
  }

  /* Mobile: stack panels */
  @media (max-width: 899px) {
    .avm-grid {
      grid-template-columns: 1fr;
    }

    .avm-actions {
      flex-direction: column;
      align-items: stretch;
    }

    .btn-row {
      justify-content: stretch;
    }

    .btn-row .btn {
      flex: 1;
    }

    .defense-grid {
      grid-template-columns: repeat(3, 1fr);
    }

    .ranking-list {
      max-height: 360px;
    }

    .fancy-table {
      font-size: 11px;
    }

    .fancy-table th,
    .fancy-table td {
      padding: 4px 6px;
    }

    .fancy-table th {
      font-size: 10px;
    }

    .composition-summary {
      padding: 8px 10px;
    }
  }
</style>

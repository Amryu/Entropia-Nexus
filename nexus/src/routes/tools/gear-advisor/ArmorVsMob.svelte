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
  import { beforeNavigate } from '$app/navigation';
  import { browser } from '$app/environment';
  import EntityPicker from './EntityPicker.svelte';
  import PoolSelectionDialog from './PoolSelectionDialog.svelte';
  import ComparisonDialog from './ComparisonDialog.svelte';
  import { exportCSV, exportJSON, exportTableAsImage } from './export-utils.js';
  import MobDamageGrid from '$lib/components/wiki/mobs/MobDamageGrid.svelte';
  import { encodeURIComponentSafe } from '$lib/util';
  import { createPreference } from '$lib/preferences.js';
  import {
    DEFENSE_TYPES,
    DEFAULT_ATTACK_NAME,
    MAX_ENHANCERS,
    computeDefenseLayers,
    computeLayerDecayRates,
    computeAttackBreakdown,
    getMobAttackNames,
    rankMobs,
    rankMobsChunked,
    rankMaturitiesChunked,
    rankArmorsChunked,
    buildDetails,
    hasDamageData,
    hasDamageDataOrPotential,
    damagePotentialMidpoint,
    findWeakestDefenseType
  } from '$lib/gear-advisor/armorVsMob.js';
  import { VALID_ADVISOR_SCOPES, VALID_ADVISOR_RANK_BY, buildAdvisorUrl } from '$lib/gear-advisor/buildAdvisorUrl.js';

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
  // Hide rows whose damage values were approximated from a maturity's
  // Damage Potential bucket (no real TotalDamage on any attack).
  let hideApproximated = $state(false);
  let hideApproximatedLoaded = $state(false);

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
  // Which attack to display in details + comparison tables. Resets to the
  // mob's preferred attack (DEFAULT_ATTACK_NAME if present, else first) when
  // the mob changes.
  let selectedAttackName = $state(null);
  let availableAttackNames = $derived(mob ? getMobAttackNames(mob) : []);
  $effect(() => {
    const names = availableAttackNames;
    if (names.length === 0) { selectedAttackName = null; return; }
    if (!selectedAttackName || !names.includes(selectedAttackName)) {
      selectedAttackName = names[0]; // getMobAttackNames puts DEFAULT first
    }
  });

  let mobPlanets = $derived.by(() => {
    const set = new Set();
    for (const m of mobs || []) {
      const p = m?.Planet?.Name;
      if (p) set.add(p);
    }
    return ['All', ...Array.from(set).sort()];
  });

  // Comparison dialog visibility + persisted column visibility state.
  let showComparisonDialog = $state(false);
  const DEFAULT_COMPARE_COLUMNS = {
    maturity: true, dmg: true,
    takenMin: false, takenExp: true, takenMax: false,
    crit: true, decay: true, mit: true
  };
  let visibleCompareColumns = $state({ ...DEFAULT_COMPARE_COLUMNS });
  let compareColumnsLoaded = $state(false);

  // Details-table export menu
  let showDetailsExportMenu = $state(false);

  const poolPref = createPreference('gear-advisor.pool', {
    armorNames: [],
    plateNames: [],
    armorEnhancers: {}
  }, { debounceMs: 400 });

  const compareColumnsPref = createPreference(
    'gear-advisor.compare-columns',
    DEFAULT_COMPARE_COLUMNS,
    { debounceMs: 400 }
  );

  // Persist the Hide-approximated toggle so both the standalone page and the
  // inline panel share the same choice (they use the same storage key).
  const hideApproximatedPref = createPreference(
    'gear-advisor.hide-approximated',
    { value: false },
    { debounceMs: 200 }
  );

  onMount(async () => {
    const userId = $page.data?.user?.id ?? null;
    await Promise.all([
      poolPref.load(userId),
      compareColumnsPref.load(userId),
      hideApproximatedPref.load(userId)
    ]);
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

    let storedCols;
    compareColumnsPref.subscribe(v => storedCols = v)();
    if (storedCols && typeof storedCols === 'object') {
      visibleCompareColumns = { ...DEFAULT_COMPARE_COLUMNS, ...storedCols };
    }
    compareColumnsLoaded = true;

    let storedHide;
    hideApproximatedPref.subscribe(v => storedHide = v)();
    if (storedHide && typeof storedHide === 'object') {
      hideApproximated = storedHide.value === true;
    }
    hideApproximatedLoaded = true;

    applyUrlParams();
    // Allow the URL-sync effect to start writing changes after the initial
    // param-apply has run; otherwise a user with a ?mob=X link would see the
    // param stripped before it gets to populate state.
    urlSyncReady = true;
  });

  // Persist hide-approximated toggle after it loads
  $effect(() => {
    const _hide = hideApproximated;
    if (!hideApproximatedLoaded) return;
    hideApproximatedPref.set({ value: _hide });
  });

  // --- URL state sync ---
  // Reflects the current calculator selection in the page URL as query
  // params, so the page can be linked, bookmarked and round-tripped through
  // the browser back/forward stack. Writes happen via history.replaceState
  // (no history entry per keystroke, no SvelteKit navigation).
  // Params are scrubbed from history before the user navigates away to a
  // different page so the gear advisor doesn't pollute unrelated routes.
  let urlSyncReady = $state(false);

  $effect(() => {
    const _armorSet = armorSet;
    const _plating = plating;
    const _mob = mob;
    const _scope = scope;
    const _rankBy = rankBy;
    if (!urlSyncReady || !browser) return;
    const target = buildAdvisorUrl({
      armor: _armorSet?.Name,
      plating: _plating?.Name,
      mob: _mob?.Name,
      scope: _scope !== 'average' ? _scope : undefined,
      rankBy: _rankBy !== 'mitigation' ? _rankBy : undefined
    });
    const current = window.location.pathname + window.location.search;
    if (current !== target) {
      window.history.replaceState(window.history.state, '', target);
    }
  });

  beforeNavigate((nav) => {
    if (!browser) return;
    const toPath = nav?.to?.url?.pathname;
    const fromPath = nav?.from?.url?.pathname;
    // Only scrub when actually leaving this route (ignore in-page query-only
    // transitions). Replacing the current entry with a bare path prevents
    // the back button from resurrecting stale ?armor=... params.
    if (toPath && fromPath && toPath !== fromPath) {
      try {
        window.history.replaceState(window.history.state, '', fromPath);
      } catch {}
    }
  });

  // Deep-link pre-fill: read armor/plating/mob/scope/rankBy from URL once on
  // mount after pool prefs load so the selection isn't clobbered. Unknown
  // names no-op gracefully.
  function applyUrlParams() {
    const sp = $page.url?.searchParams;
    if (!sp) return;
    const findByName = (list, name) => {
      if (!name) return null;
      const decoded = (() => { try { return decodeURIComponent(name); } catch { return name; } })();
      return (list || []).find(e => e?.Name === decoded) || null;
    };
    const armorName = sp.get('armor');
    if (armorName) {
      const match = findByName(armorSets, armorName);
      if (match) armorSet = match;
    }
    const platingName = sp.get('plating');
    if (platingName) {
      const match = findByName(armorPlatings, platingName);
      if (match) plating = match;
    }
    const mobName = sp.get('mob');
    if (mobName) {
      const match = findByName(mobs, mobName);
      if (match) mob = match;
    }
    const scopeParam = sp.get('scope');
    if (scopeParam && VALID_ADVISOR_SCOPES.has(scopeParam)) scope = scopeParam;
    const rankByParam = sp.get('rankBy');
    if (rankByParam && VALID_ADVISOR_RANK_BY.has(rankByParam)) rankBy = rankByParam;
  }

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

  // Persist comparison column visibility
  $effect(() => {
    const _cols = visibleCompareColumns;
    if (!compareColumnsLoaded) return;
    compareColumnsPref.set({ ..._cols });
  });

  // Derived: defense layers for current armor config (null if no armor)
  let defense = $derived(armorSet
    ? computeDefenseLayers(armorSet, plating, iceShield, enhancers)
    : null);

  // Derived: flat per-type defense map summed across all layers — used by
  // the "Effective defense" grid. computeDefenseLayers returns a layer array,
  // not a type-indexed object, so template access via `defense[type]` would
  // be undefined without this flattening step.
  let effectiveDefense = $derived.by(() => {
    if (!defense) return null;
    const out = {};
    for (const type of DEFENSE_TYPES) {
      let sum = 0;
      for (const layer of defense) sum += layer?.[type] ?? 0;
      out[type] = sum;
    }
    return out;
  });

  // Pre-mitigation damage multiplier (clamped to ≥ 0)
  let dmgMultiplier = $derived(Math.max(0, 1 - (Number(dmgReduction) || 0) / 100));

  // Per-layer decay rates matching defense layers order
  let decayRates = $derived(armorSet ? computeLayerDecayRates(armorSet, plating, iceShield) : null);

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

  // Flat rows for the details table: one row per maturity, showing the
  // currently-selected attack (see selectedAttackName / availableAttackNames).
  // If a maturity doesn't have the selected attack, its row shows "—".
  let flatRows = $derived.by(() => {
    if (!mob || !defense) return [];
    const attackName = selectedAttackName;
    if (!attackName) return [];
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
      const atk = (mat.Attacks || []).find(
        a => (a?.Name || DEFAULT_ATTACK_NAME) === attackName
      );
      if (!atk) {
        rows.push({
          maturityName: mat.Name || '',
          maturityLevel: mat?.Properties?.Level ?? null,
          totalDamage: null,
          takenMin: null,
          takenAvg: null,
          takenMax: null,
          mitigation: null,
          critTaken: null,
          decayThisAttack: null,
          approximated: false,
          hasData: false
        });
        continue;
      }
      // When the attack has no TotalDamage but the maturity carries a
      // Damage Potential classification, substitute the bucket midpoint so
      // the row still shows mitigation/damage-taken numbers (flagged).
      const realTotal = atk?.TotalDamage;
      const dpMid = damagePotentialMidpoint(mat?.Properties?.DamagePotential);
      const approximated = (realTotal == null || realTotal <= 0) && dpMid != null;
      const effectiveAtk = approximated ? { ...atk, TotalDamage: dpMid } : atk;
      const br = computeAttackBreakdown(effectiveAtk, defense, dmgMultiplier, decayRates);
      // Weakest defense type for this single attack at max roll — the type
      // where the biggest uncovered damage lies and thus the best candidate
      // for an armor / plating upgrade.
      let weakestType = null;
      if (effectiveDefense && (effectiveAtk?.TotalDamage ?? 0) > 0) {
        const total = effectiveAtk.TotalDamage * dmgMultiplier;
        let maxLeak = 0;
        for (const t of DEFENSE_TYPES) {
          const pct = (effectiveAtk?.Damage?.[t] ?? 0) / 100;
          if (pct <= 0) continue;
          const incoming = total * pct;
          const leak = Math.max(0, incoming - (effectiveDefense[t] ?? 0));
          if (leak > maxLeak) { maxLeak = leak; weakestType = { type: t, leak }; }
        }
      }
      rows.push({
        maturityName: mat.Name || '',
        maturityLevel: mat?.Properties?.Level ?? null,
        totalDamage: approximated ? dpMid : (realTotal ?? null),
        takenMin: br.takenMin,
        takenAvg: br.expectedTaken,
        takenMax: br.takenMax,
        // Display "deflected" at max roll (worst-case absorbed) so full
        // absorption shows as the full mob damage, not 75% of it.
        deflected: br.blockedMax,
        weakestType,
        mitigation: br.mitigation,
        critTaken: br.critTaken,
        decayThisAttack: br.expectedDecay,
        approximated,
        hasData: br.totalAvg > 0
      });
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
    const _decayRates = decayRates;
    const _planet = mobPlanetFilter;
    const _viewMaturities = viewMaturities;
    const _hideApprox = hideApproximated;

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
          filteredMobs, _defense, _dmgMultiplier, _rankBy, _decayRates,
          { chunkSize: 100, signal: controller, hideApproximated: _hideApprox }
        )
      : rankMobsChunked(
          filteredMobs, _defense, _scope, _dmgMultiplier, _rankBy, _decayRates,
          { chunkSize: 100, signal: controller, hideApproximated: _hideApprox }
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
    const _hideApprox = hideApproximated;

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
        armorEnhancers: hasArmorPool ? _poolArmorEnhancers : null,
        hideApproximated: _hideApprox
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

  function exportDetails(format) {
    showDetailsExportMenu = false;
    if (!mob || flatRows.length === 0) return;
    const mobName = (mob?.Name || 'mob').replace(/[^A-Za-z0-9_-]+/g, '_');
    const setName = armorSet?.Name?.replace(/[^A-Za-z0-9_-]+/g, '_') || 'armor';
    const plateName = plating?.Name?.replace(/[^A-Za-z0-9_-]+/g, '_') || '';
    const atk = (selectedAttackName || 'attack').replace(/[^A-Za-z0-9_-]+/g, '_');
    const base = `gear-advisor_${mobName}_${setName}${plateName ? '+' + plateName : ''}_${atk}`;

    const headers = ['Maturity', 'Dmg', 'Taken (min)', 'Taken (exp)', 'Taken (max)', 'Deflected', 'Weakest type', 'Max Crit Dmg', 'Decay', 'Mit'];
    const dataRows = flatRows.map(row => {
      const lvl = row.maturityLevel != null ? ` (L${row.maturityLevel})` : '';
      return [
        `${row.maturityName}${lvl}`,
        row.totalDamage != null ? formatNum(row.totalDamage, 0) : null,
        row.hasData ? formatNum(row.takenMin) : null,
        row.hasData ? formatNum(row.takenAvg) : null,
        row.hasData ? formatNum(row.takenMax) : null,
        row.hasData ? formatNum(row.deflected) : null,
        row.hasData && row.weakestType ? `${row.weakestType.type} (+${formatNum(row.weakestType.leak, 0)})` : null,
        row.hasData ? formatNum(row.critTaken) : null,
        row.hasData ? formatNum(row.decayThisAttack, 3) : null,
        row.hasData ? formatPct(row.mitigation * 100, 0) : null
      ];
    });

    if (format === 'csv') {
      exportCSV(base, headers, dataRows);
    } else if (format === 'json') {
      exportJSON(base, {
        mob: mob?.Name ?? null,
        armor: armorSet?.Name ?? null,
        plating: plating?.Name ?? null,
        iceShield,
        enhancers,
        dmgReduction,
        attack: selectedAttackName,
        rows: flatRows.map(row => ({
          maturity: row.maturityName,
          level: row.maturityLevel,
          totalDamage: row.totalDamage,
          ...(row.hasData ? {
            takenMin: row.takenMin,
            takenAvg: row.takenAvg,
            takenMax: row.takenMax,
            deflected: row.deflected,
            weakestType: row.weakestType,
            critTaken: row.critTaken,
            decayPerAttack: row.decayThisAttack,
            mitigation: row.mitigation
          } : { hasData: false })
        }))
      });
    } else if (format === 'png') {
      const title = `${mob?.Name ?? ''} vs ${armorSet?.Name ?? ''}${plating ? ' + ' + plating.Name : ''}${selectedAttackName ? ` — ${selectedAttackName}` : ''}`;
      exportTableAsImage(
        base,
        [headers],
        dataRows,
        { title, numericCols: [1, 2, 3, 4, 5, 7, 8, 9] }
      );
    }
  }

  function clampEnhancers(v) {
    const n = Number.parseInt(v, 10);
    if (!Number.isFinite(n) || n < 0) return 0;
    if (n > MAX_ENHANCERS) return MAX_ENHANCERS;
    return n;
  }
</script>

<svelte:window onclick={() => { showDetailsExportMenu = false; }} />

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
            <label class="inline-check" title="Hide rows whose damage values were approximated from this mob's Damage Potential bucket">
              <input type="checkbox" bind:checked={hideApproximated} />
              <span>Hide approximated</span>
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
                {@const approxTip = r.approximated ? 'Damage values approximated from this maturity\'s Damage Potential bucket.' : ''}
                <button
                  type="button"
                  class="ranking-row"
                  class:no-damage={!r.hasTotalDamage && r.hasComposition}
                  class:no-data={!r.hasComposition}
                  class:with-plate={!!r.plating}
                  class:approximated={r.approximated}
                  onclick={() => { armorSet = r.armorSet; plating = r.plating; }}
                >
                  <span class="rank-idx">#{i + 1}</span>
                  <span class="rank-name">
                    <span class="name-main">
                      {r.name}{#if r.plating}&nbsp;<span class="plate-tag">+ {r.plating.Name}</span>{/if}
                    </span>
                    {#if r.maturityLabel}<span class="rank-sub">{r.maturityLabel}{#if r.maturityLevel != null}&nbsp;· L{r.maturityLevel}{/if}</span>{/if}
                    {#if r.approximated}<span class="approx-tag" title={approxTip}>~approx</span>{/if}
                  </span>
                  <span class="rank-metric">
                    {#if r.hasTotalDamage}
                      <span class="mit" title={r.approximated ? approxTip : `Mitigation at the mob's strongest roll (damage deflected ÷ total damage)`}>{r.approximated ? '~' : ''}{formatPct(r.mitigationPct, 1)} mitigated</span>
                      {#if r.damageDeflected != null}
                        <span class="deflected" title={r.approximated ? approxTip : `Damage deflected at the mob's strongest roll (absorbed by armor layers)`}>{r.approximated ? '~' : ''}+{formatNum(r.damageDeflected)}/hit deflected</span>
                      {/if}
                      <span class="type-score" title="How well armor's defenses align with the mob's damage composition (fraction of total armor defense deployed vs this mob)">{formatPct(r.typeScore * 100, 1)} type-match</span>
                      <span class="taken" title={r.approximated ? approxTip : `Damage taken at the mob's strongest roll`}>{r.approximated ? '~' : ''}–{formatNum(r.damageTaken)}/hit</span>
                      {#if r.decayPerAttack != null}
                        {#if r.decayPerAttackMin != null && r.decayPerAttackMax != null && Math.abs(r.decayPerAttackMax - r.decayPerAttackMin) > 0.0005}
                          <span class="decay" title={r.approximated ? approxTip : 'Armor/plate decay per attack across maturities (PEC)'}>{r.approximated ? '~' : ''}{formatNum(r.decayPerAttackMin, 3)}–{formatNum(r.decayPerAttackMax, 3)} PEC decay</span>
                        {:else}
                          <span class="decay" title={r.approximated ? approxTip : 'Armor/plate decay per attack (PEC)'}>{r.approximated ? '~' : ''}{formatNum(r.decayPerAttack, 3)} PEC decay</span>
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
            <div class="ranking-footer">
              <button
                type="button"
                class="pool-btn"
                onclick={() => { showComparisonDialog = true; }}
                disabled={armorRanking.length === 0}
                title="Side-by-side comparison of selected ranked sets across the mob's maturities"
              >Compare…</button>
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

          {#if effectiveDefense}
            <h5 class="defense-title">Effective defense</h5>
            <div class="defense-grid">
              {#each DEFENSE_TYPES as type}
                <div class="def-cell">
                  <span class="def-label" style="color: var(--damage-{type.toLowerCase()})">
                    <span class="def-label-full">{type}</span>
                    <span class="def-label-short">{type.slice(0, 3)}</span>
                  </span>
                  <span class="def-value">{formatNum(effectiveDefense[type])}</span>
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
            <label class="inline-check" title="Hide rows whose damage values were approximated from a maturity's Damage Potential bucket">
              <input type="checkbox" bind:checked={hideApproximated} />
              <span>Hide approximated</span>
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
                {@const approxTip = r.approximated ? 'Damage values approximated from this maturity\'s Damage Potential bucket.' : ''}
                <button
                  type="button"
                  class="ranking-row"
                  class:no-damage={!r.hasTotalDamage && r.hasComposition}
                  class:no-data={!r.hasComposition}
                  class:approximated={r.approximated}
                  onclick={() => { mob = r.mob; }}
                >
                  <span class="rank-idx">#{i + 1}</span>
                  <span class="rank-name">
                    <span class="name-main">{r.name}</span>
                    {#if r.maturityLabel}<span class="rank-sub">{r.maturityLabel}{#if r.maturityLevel != null}&nbsp;· L{r.maturityLevel}{/if}</span>{/if}
                    {#if r.approximated}<span class="approx-tag" title={approxTip}>~approx</span>{/if}
                  </span>
                  <span class="rank-metric">
                    {#if r.hasTotalDamage}
                      <span class="mit" title={r.approximated ? approxTip : `Mitigation at the mob's strongest roll (damage deflected ÷ total damage)`}>{r.approximated ? '~' : ''}{formatPct(r.mitigationPct, 1)} mitigated</span>
                      {#if r.damageDeflected != null}
                        <span class="deflected" title={r.approximated ? approxTip : `Damage deflected at the mob's strongest roll (absorbed by armor layers)`}>{r.approximated ? '~' : ''}+{formatNum(r.damageDeflected)}/hit deflected</span>
                      {/if}
                      <span class="type-score" title="How well armor's defenses align with the mob's damage composition (fraction of total armor defense deployed vs this mob)">{formatPct(r.typeScore * 100, 1)} type-match</span>
                      <span class="taken" title={r.approximated ? approxTip : `Damage taken at the mob's strongest roll`}>{r.approximated ? '~' : ''}–{formatNum(r.damageTaken)}/hit</span>
                      {#if r.decayPerAttack != null}
                        {#if r.decayPerAttackMin != null && r.decayPerAttackMax != null && Math.abs(r.decayPerAttackMax - r.decayPerAttackMin) > 0.0005}
                          <span class="decay" title={r.approximated ? approxTip : 'Armor/plate decay per attack across maturities (PEC)'}>{r.approximated ? '~' : ''}{formatNum(r.decayPerAttackMin, 3)}–{formatNum(r.decayPerAttackMax, 3)} PEC decay</span>
                        {:else}
                          <span class="decay" title={r.approximated ? approxTip : 'Armor/plate decay per attack (PEC)'}>{r.approximated ? '~' : ''}{formatNum(r.decayPerAttack, 3)} PEC decay</span>
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

          <div class="details-toolbar">
            {#if availableAttackNames.length > 1}
              <fieldset class="attack-picker">
                <legend>Attack</legend>
                {#each availableAttackNames as name}
                  <label class="attack-chip" class:active={selectedAttackName === name}>
                    <input type="radio" bind:group={selectedAttackName} value={name} />
                    <span>{name}</span>
                  </label>
                {/each}
              </fieldset>
            {/if}
            {#if flatRows.length > 0}
              <div class="export-wrap" onclick={(e) => e.stopPropagation()} role="presentation">
                <button
                  type="button"
                  class="export-btn"
                  onclick={(e) => { e.stopPropagation(); showDetailsExportMenu = !showDetailsExportMenu; }}
                  aria-haspopup="menu"
                  aria-expanded={showDetailsExportMenu}
                >Export ▾</button>
                {#if showDetailsExportMenu}
                  <div class="export-menu" role="menu">
                    <button role="menuitem" onclick={() => exportDetails('csv')}>CSV</button>
                    <button role="menuitem" onclick={() => exportDetails('json')}>JSON</button>
                    <button role="menuitem" onclick={() => exportDetails('png')}>PNG image</button>
                  </div>
                {/if}
              </div>
            {/if}
          </div>

          {#if flatRows.length > 0}
            <table class="fancy-table">
              <thead>
                <tr>
                  <th>Maturity</th>
                  <th class="num">Dmg</th>
                  <th class="num" title="Damage taken at lowest roll / expected avg / max roll (armor caps per-type)">Taken (min/exp/max)</th>
                  <th class="num" title="Damage absorbed by armor layers at the mob's strongest roll (≤ total attack damage)">Deflected</th>
                  <th title="Defense type with the biggest uncovered damage at max roll — the best upgrade target for this attack">Weakest type</th>
                  <th class="num" title="Max crit damage taken (2× max damage, 20% armor pierce)">Max Crit Dmg</th>
                  <th class="num" title="Armor/plate decay per attack (PEC)">Decay</th>
                  <th class="num">Mit</th>
                </tr>
              </thead>
              <tbody>
                {#each flatRows as row, i (i)}
                  {@const approxTip = row.approximated ? 'Damage values approximated from this maturity\'s Damage Potential bucket.' : ''}
                  <tr class:no-data-row={!row.hasData} class:approximated-row={row.approximated}>
                    <td>
                      <span class="cell-main">{row.maturityName}</span>
                      {#if row.maturityLevel != null}<span class="cell-sub">L{row.maturityLevel}</span>{/if}
                      {#if row.approximated}<span class="approx-tag" title={approxTip}>~approx</span>{/if}
                    </td>
                    <td class="num" class:muted={row.totalDamage == null} class:approx-num={row.approximated} title={row.approximated ? approxTip : ''}>
                      {row.approximated ? '~' : ''}{row.totalDamage != null ? formatNum(row.totalDamage, 0) : '—'}
                    </td>
                    {#if row.hasData}
                      <td class="num" class:approx-num={row.approximated} title={row.approximated ? approxTip : ''}>{row.approximated ? '~' : ''}{formatNum(row.takenMin)} / {formatNum(row.takenAvg)} / {formatNum(row.takenMax)}</td>
                      <td class="num deflected-cell" class:approx-num={row.approximated} title={row.approximated ? approxTip : 'Damage deflected at the mob\'s strongest roll'}>{row.approximated ? '~' : ''}+{formatNum(row.deflected)}</td>
                      <td class:approx-num={row.approximated} title={row.weakestType ? `${row.weakestType.type}: ${formatNum(row.weakestType.leak)} uncovered damage at max roll` : 'Armor fully covers this attack'}>
                        {#if row.weakestType}
                          <span class="weakest-type" style="color: var(--damage-{row.weakestType.type.toLowerCase()})">{row.weakestType.type}</span>
                          <span class="weakest-leak">+{formatNum(row.weakestType.leak, 0)}</span>
                        {:else}
                          <span class="muted">—</span>
                        {/if}
                      </td>
                      <td class="num crit-cell" class:approx-num={row.approximated}>{row.approximated ? '~' : ''}{formatNum(row.critTaken)}</td>
                      <td class="num decay-cell" class:approx-num={row.approximated}>{row.approximated ? '~' : ''}{formatNum(row.decayThisAttack, 3)}</td>
                      <td class="num mit-cell" class:approx-num={row.approximated}>{row.approximated ? '~' : ''}{formatPct(row.mitigation * 100, 0)}</td>
                    {:else}
                      <td class="num muted">—</td>
                      <td class="num muted">—</td>
                      <td class="muted">—</td>
                      <td class="num muted">—</td>
                      <td class="num muted">—</td>
                      <td class="num muted">—</td>
                    {/if}
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}

          {#if !hasDamageDataOrPotential(mob)}
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
          {:else if !hasDamageData(mob)}
            <div class="missing-data-cta approx-cta">
              <p class="missing-data-title">Damage values are approximated from this mob's Damage Potential classification.</p>
              <p class="missing-data-hint">Help by adding exact attack damage on the wiki page.</p>
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
        <label><input type="radio" name="rankBy" value="deflected" bind:group={rankBy} /> Damage deflected</label>
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

{#if showComparisonDialog && mob}
  <ComparisonDialog
    {mob}
    armorRanking={armorRanking}
    {iceShield}
    {enhancers}
    {dmgMultiplier}
    {poolArmorEnhancers}
    poolArmorNamesActive={poolArmorNames.length > 0}
    attackNames={availableAttackNames}
    bind:selectedAttackName
    initialVisibleColumns={visibleCompareColumns}
    onclose={() => { showComparisonDialog = false; }}
    oncolumnschange={(cols) => { visibleCompareColumns = cols; }}
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

  .ranking-footer {
    display: flex;
    justify-content: flex-end;
    margin-top: 8px;
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

  /* Rows whose damage values were approximated from Damage Potential */
  .ranking-row.approximated {
    border-left: 3px solid var(--warning-color, #fbbf24);
  }

  .ranking-row.approximated .mit,
  .ranking-row.approximated .taken,
  .ranking-row.approximated .decay {
    font-style: italic;
    color: var(--text-muted, #999);
  }

  .approx-tag {
    display: inline-block;
    margin-left: 6px;
    padding: 1px 5px;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: var(--warning-color, #fbbf24);
    background: color-mix(in srgb, var(--warning-color, #fbbf24) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--warning-color, #fbbf24) 40%, transparent);
    border-radius: 3px;
    vertical-align: middle;
  }

  .approximated-row {
    background-color: color-mix(in srgb, var(--warning-color, #fbbf24) 6%, transparent);
  }

  .approx-num {
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .missing-data-cta.approx-cta {
    border-color: color-mix(in srgb, var(--warning-color, #fbbf24) 50%, transparent);
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

  .details-toolbar {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin: 0 0 10px 0;
  }

  .details-toolbar .attack-picker {
    margin: 0;
  }

  .export-wrap {
    position: relative;
    margin-left: auto;
  }

  .export-btn {
    padding: 5px 12px;
    font-size: 12px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
    cursor: pointer;
  }
  .export-btn:hover:not(:disabled) { background-color: var(--hover-color); }
  .export-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  .export-menu {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    min-width: 140px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    padding: 4px;
    z-index: 10;
    display: flex;
    flex-direction: column;
  }
  .export-menu button {
    text-align: left;
    padding: 6px 10px;
    font-size: 12px;
    background: transparent;
    border: none;
    color: var(--text-color);
    cursor: pointer;
    border-radius: 4px;
  }
  .export-menu button:hover { background-color: var(--hover-color); }

  .attack-picker {
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 6px 10px 6px 8px;
    margin: 0 0 10px 0;
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    background-color: var(--primary-color);
  }

  .attack-picker legend {
    float: none;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
    padding: 0 6px 0 4px;
    width: auto;
  }

  .attack-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    font-size: 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    cursor: pointer;
    white-space: nowrap;
  }
  .attack-chip:hover { background-color: var(--hover-color); }
  .attack-chip.active {
    background-color: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }
  .attack-chip input { display: none; }

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

  .fancy-table th[title] {
    text-decoration: underline dotted var(--text-muted);
    text-underline-offset: 3px;
    cursor: help;
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

  .fancy-table .weakest-type {
    font-weight: 600;
  }

  .fancy-table .weakest-leak {
    margin-left: 6px;
    font-size: 11px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
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

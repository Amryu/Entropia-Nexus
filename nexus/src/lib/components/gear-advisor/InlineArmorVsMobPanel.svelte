<!--
  @component InlineArmorVsMobPanel
  Compact inline version of the armor-vs-mob gear advisor.
  Two modes:
    - recommend-armors: shown on a mob detail page. Given a mob, ranks armor
      sets (no plate pairings for compactness). Has an All/Pool toggle.
    - recommend-mobs: shown on an armor set detail page. Given an armor set,
      ranks mobs. Has planet dropdown + HP min/max range filter.

  Data lists (armor sets / mobs) are lazy-loaded on mount via the module-level
  promise cache in $lib/gear-advisor/listCache.js — this component is designed
  to mount only when its parent DataSection is expanded.
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import {
    DEFENSE_TYPES,
    computeDefenseLayers,
    computeLayerDecayRates,
    rankArmorsChunked,
    scoreMob,
    hasDamageData,
    hasDamageDataOrPotential,
    findWeakestDefenseType,
    sumLayers
  } from '$lib/gear-advisor/armorVsMob.js';
  import { getArmorSets, getArmorPlatings, getMobs } from '$lib/gear-advisor/listCache.js';
  import { buildAdvisorUrl } from '$lib/gear-advisor/buildAdvisorUrl.js';
  import { createPreference } from '$lib/preferences.js';
  import { encodeURIComponentSafe } from '$lib/util';
  import FancyTable from '$lib/components/FancyTable.svelte';

  let {
    mode,           // 'recommend-armors' | 'recommend-mobs'
    mob = null,
    armorSet = null,
    topN = 50
  } = $props();

  // Loaded lists (lazy)
  let armorSets = $state([]);
  let armorPlatings = $state([]);
  let mobs = $state([]);
  let listsLoaded = $state(false);
  let listsError = $state(false);

  // Pool preference (mob mode only)
  let poolArmorNames = $state([]);
  let poolLoaded = $state(false);
  let useMyPool = $state(false);
  const poolPref = createPreference('gear-advisor.pool', {
    armorNames: [],
    plateNames: [],
    armorEnhancers: {}
  }, { debounceMs: 400 });

  // Mob-mode maturity selector ('__average__' excludes bosses)
  const AVERAGE_NO_BOSS = '__average__';
  let selectedMaturity = $state(AVERAGE_NO_BOSS);

  // Overkill filter: drop armors whose relevant defense (summed across the
  // damage types the mob actually deals) exceeds 1.5x the mob's strongest
  // attack. Only meaningful when TotalDamage is known — with composition-only
  // data, the feature is disabled and ranking falls back to type-match.
  const OVERKILL_DEFENSE_MULTIPLIER = 1.5;
  let rightSized = $state(true);

  // Hide rows approximated from a maturity's Damage Potential bucket.
  // Persisted under the same key as the standalone gear advisor page.
  let hideApproximated = $state(false);
  let hideApproximatedLoaded = $state(false);
  const hideApproximatedPref = createPreference(
    'gear-advisor.hide-approximated',
    { value: false },
    { debounceMs: 200 }
  );

  // Armor mode filters
  let planetFilter = $state('All');
  let hpMin = $state('');
  let hpMax = $state('');
  // Armor-mode optional upper-bound on expected damage taken per hit.
  let maxDamageTakenEnabled = $state(false);
  let maxDamageTakenValue = $state('');

  // Ranking results
  let ranking = $state([]);
  let rankingLoading = $state(false);
  let rankingError = $state(null);

  let currentController = null;

  onMount(async () => {
    try {
      const userId = $page.data?.user?.id ?? null;
      await hideApproximatedPref.load(userId);
      let storedHide;
      hideApproximatedPref.subscribe(v => storedHide = v)();
      if (storedHide && typeof storedHide === 'object') {
        hideApproximated = storedHide.value === true;
      }
      hideApproximatedLoaded = true;

      if (mode === 'recommend-armors') {
        const [a, p] = await Promise.all([
          getArmorSets(fetch),
          getArmorPlatings(fetch)
        ]);
        armorSets = a;
        armorPlatings = p;
        await poolPref.load(userId);
        let stored;
        poolPref.subscribe(v => stored = v)();
        poolArmorNames = Array.isArray(stored?.armorNames) ? stored.armorNames : [];
        poolLoaded = true;
      } else {
        mobs = await getMobs(fetch);
      }
      listsLoaded = true;
    } catch (e) {
      listsError = true;
    }
  });

  // Persist hide-approximated toggle
  $effect(() => {
    const _hide = hideApproximated;
    if (!hideApproximatedLoaded) return;
    hideApproximatedPref.set({ value: _hide });
  });

  onDestroy(() => {
    if (currentController) currentController.aborted = true;
  });

  // Planet options for armor-mode filter
  let planetOptions = $derived.by(() => {
    if (mode !== 'recommend-mobs') return [];
    const set = new Set();
    for (const m of mobs || []) {
      const p = m?.Planet?.Name;
      if (p) set.add(p);
    }
    return ['All', ...Array.from(set).sort()];
  });


  // Cosmetic-armor guard (total defense == 0)
  let armorHasDefense = $derived.by(() => {
    if (mode !== 'recommend-mobs' || !armorSet) return true;
    let sum = 0;
    for (const t of DEFENSE_TYPES) sum += armorSet?.Properties?.Defense?.[t] ?? 0;
    return sum > 0;
  });

  // Mob-mode guard: selected mob has no usable damage data. A non-null
  // DamagePotential bucket on any maturity counts as data here, since the
  // ranking fallback can approximate mitigation from its midpoint.
  let mobLacksDamageData = $derived.by(() => {
    if (mode !== 'recommend-armors' || !mob) return false;
    return !hasDamageDataOrPotential(mob);
  });

  // Mob-mode maturity options for the selector — bosses last, then by level
  // ascending (nulls last). Matches MobMaturities.svelte sort convention.
  let maturityOptions = $derived.by(() => {
    if (mode !== 'recommend-armors' || !mob) return [];
    const mats = Array.isArray(mob?.Maturities) ? mob.Maturities : [];
    const opts = mats.map(m => ({
      name: m?.Name || '',
      level: m?.Properties?.Level ?? null,
      boss: m?.Properties?.Boss === true
    })).filter(o => o.name);
    opts.sort((a, b) => {
      if (a.boss !== b.boss) return a.boss ? 1 : -1;
      if (a.level == null && b.level == null) return 0;
      if (a.level == null) return 1;
      if (b.level == null) return -1;
      return a.level - b.level;
    });
    return opts;
  });

  // Effective mob fed to the ranker — filters maturities based on selection.
  // '__average__' excludes boss maturities; otherwise only the selected maturity is kept.
  let effectiveMob = $derived.by(() => {
    if (mode !== 'recommend-armors' || !mob) return null;
    const mats = Array.isArray(mob?.Maturities) ? mob.Maturities : [];
    if (selectedMaturity === AVERAGE_NO_BOSS) {
      const filtered = mats.filter(m => m?.Properties?.Boss !== true);
      return { ...mob, Maturities: filtered.length > 0 ? filtered : mats };
    }
    const only = mats.filter(m => (m?.Name || '') === selectedMaturity);
    return { ...mob, Maturities: only.length > 0 ? only : mats };
  });

  // True when the selected maturity scope actually has TotalDamage > 0 somewhere.
  // Accepts Damage Potential as a data source — DP midpoint is injected by
  // the ranker as a synthetic TotalDamage so mitigation ranking is viable.
  let effectiveMobHasDamage = $derived(
    mode === 'recommend-armors' && effectiveMob ? hasDamageDataOrPotential(effectiveMob) : false
  );

  // Max TotalDamage across all attacks in the effective mob — used as the
  // anchor for the overkill filter.
  let maxIncomingDamage = $derived.by(() => {
    if (!effectiveMobHasDamage) return 0;
    let max = 0;
    for (const mat of effectiveMob.Maturities || []) {
      for (const atk of mat.Attacks || []) {
        const d = atk?.TotalDamage ?? 0;
        if (d > max) max = d;
      }
    }
    return max;
  });

  // Damage types the effective mob actually deals (pct > 0 in any attack).
  // Used to sum only the *relevant* portion of an armor's defense so that
  // off-type padding (e.g. Electric defense vs a melee mob) doesn't inflate
  // the overkill score.
  let relevantDamageTypes = $derived.by(() => {
    if (mode !== 'recommend-armors' || !effectiveMob) return null;
    const types = new Set();
    for (const mat of effectiveMob.Maturities || []) {
      for (const atk of mat.Attacks || []) {
        for (const t of DEFENSE_TYPES) {
          if ((atk?.Damage?.[t] ?? 0) > 0) types.add(t);
        }
      }
    }
    return types.size > 0 ? types : null;
  });

  // Filtered mob list for armor mode
  let filteredMobs = $derived.by(() => {
    if (mode !== 'recommend-mobs') return [];
    const lo = hpMin === '' || hpMin == null ? null : Number(hpMin);
    const hi = hpMax === '' || hpMax == null ? null : Number(hpMax);
    const planet = planetFilter;
    return (mobs || []).filter(m => {
      if (planet !== 'All' && m?.Planet?.Name !== planet) return false;
      if (lo != null || hi != null) {
        const mats = m?.Maturities || [];
        if (mats.length === 0) return false;
        const anyInRange = mats.some(mat => {
          const hp = mat?.Properties?.Health ?? null;
          if (hp == null) return false;
          if (lo != null && hp < lo) return false;
          if (hi != null && hp > hi) return false;
          return true;
        });
        if (!anyInRange) return false;
      }
      return true;
    });
  });

  // Trigger ranking recomputation on relevant state changes
  $effect(() => {
    const _listsLoaded = listsLoaded;
    const _mode = mode;
    const _mob = mob;
    const _effectiveMob = effectiveMob;
    const _armorSet = armorSet;
    const _useMyPool = useMyPool;
    const _poolArmorNames = poolArmorNames;
    const _filteredMobs = filteredMobs;
    const _armorHasDefense = armorHasDefense;
    const _mobLacksDamageData = mobLacksDamageData;
    const _topN = topN;
    const _hideApproximated = hideApproximated;
    // explicitly reference to track as dep (used inside the branches below)
    void _hideApproximated;

    if (currentController) { currentController.aborted = true; currentController = null; }
    if (!_listsLoaded) return;

    if (_mode === 'recommend-armors') {
      if (!_mob || _mobLacksDamageData || !_effectiveMob) { ranking = []; rankingLoading = false; return; }
      if (_useMyPool && (!_poolArmorNames || _poolArmorNames.length === 0)) {
        ranking = [];
        rankingLoading = false;
        return;
      }
      const _effectiveMobHasDamage = effectiveMobHasDamage;
      const _maxIncomingDamage = maxIncomingDamage;
      const _rightSized = rightSized;
      const _relevantTypes = relevantDamageTypes;
      const controller = { aborted: false };
      currentController = controller;
      rankingLoading = true;
      const armorFilter = _useMyPool ? new Set(_poolArmorNames) : null;
      // No TotalDamage -> rank by composition match (typeScore). Otherwise
      // by absolute damage deflected per hit — favours armor whose defense
      // matches this mob's damage profile in real terms, not just % of a
      // small-damage mob.
      const effectiveRankBy = _effectiveMobHasDamage ? 'deflected' : 'typeMatch';
      const _hideApproxArmor = hideApproximated;
      rankArmorsChunked(
        armorSets, armorPlatings, _effectiveMob,
        { iceShield: false, enhancers: 0, dmgMultiplier: 1 },
        'average', effectiveRankBy,
        { includePlates: false, armorFilter, hideApproximated: _hideApproxArmor },
        { chunkSize: 40, signal: controller }
      ).then(result => {
        if (controller.aborted) return;
        let filtered = result ?? [];
        if (_rightSized && _effectiveMobHasDamage && _maxIncomingDamage > 0 && _relevantTypes) {
          const cap = OVERKILL_DEFENSE_MULTIPLIER * _maxIncomingDamage;
          const rightSizedFiltered = filtered.filter(r => {
            const def = r?.armorSet?.Properties?.Defense || {};
            let relevantDef = 0;
            for (const t of _relevantTypes) relevantDef += def[t] ?? 0;
            return relevantDef <= cap;
          });
          if (rightSizedFiltered.length > 0) filtered = rightSizedFiltered;
        }
        const topRows = filtered.slice(0, _topN);
        // Per-armor: find the maturity of the effective mob where this armor
        // achieves the highest mitigation %. Helps the user see which fight
        // the armor is best matched to when the ranking scope is 'Average'.
        // Also: identify the defense type that leaks the most damage, so
        // the user knows where to upgrade next.
        const poolMats = (_effectiveMob?.Maturities || []).filter(m =>
          Array.isArray(m?.Attacks) && m.Attacks.length > 0
        );
        for (const row of topRows) {
          if (!row?.armorSet) continue;
          // Bare-armor defense map for weakest-type analysis — rank pass
          // uses includePlates:false so this matches the ranking conditions.
          const armorDefFlat = row.armorSet?.Properties?.Defense || {};
          row.weakestType = findWeakestDefenseType(_effectiveMob, armorDefFlat);

          if (poolMats.length === 0) continue;
          const armorDef = computeDefenseLayers(row.armorSet, null, false, 0);
          // Score every maturity, then pick the one with the highest
          // mitigation. Ties (e.g. multiple maturities at 100%) break to
          // the highest level so the displayed maturity is the hardest
          // fight the armor can still fully cover.
          const scored = [];
          for (const mat of poolMats) {
            const synth = { ..._effectiveMob, Maturities: [mat] };
            const score = scoreMob(synth, armorDef, 'average', 1, null);
            if (score?.mitigation == null) continue;
            scored.push({
              name: mat?.Name ?? '',
              level: mat?.Properties?.Level ?? null,
              mitigation: score.mitigation
            });
          }
          if (scored.length === 0) { row.bestMaturity = null; continue; }
          let maxMit = -Infinity;
          for (const s of scored) if (s.mitigation > maxMit) maxMit = s.mitigation;
          const tied = scored.filter(s => s.mitigation === maxMit);
          tied.sort((a, b) => {
            const la = a.level, lb = b.level;
            if (la == null && lb == null) return 0;
            if (la == null) return 1;
            if (lb == null) return -1;
            return lb - la; // highest level first
          });
          row.bestMaturity = tied[0];
        }
        ranking = topRows;
        rankingLoading = false;
      }).catch(() => {
        if (!controller.aborted) { rankingLoading = false; rankingError = 'Failed to rank armors'; }
      });
      return () => { controller.aborted = true; };
    }

    if (_mode === 'recommend-mobs') {
      if (!_armorSet || !_armorHasDefense) { ranking = []; rankingLoading = false; return; }
      const _maxDamageTakenEnabled = maxDamageTakenEnabled;
      const _maxDamageTakenValue = maxDamageTakenValue;
      const defenseLayers = computeDefenseLayers(_armorSet, null, false, 0);
      const decayRates = computeLayerDecayRates(_armorSet, null, false);
      const controller = { aborted: false };
      currentController = controller;
      rankingLoading = true;
      const _hideApproxMob = hideApproximated;
      rankMobsTiered(_filteredMobs, defenseLayers, decayRates, {
        signal: controller,
        hideApproximated: _hideApproxMob
      }).then(result => {
        if (controller.aborted) return;
        let filtered = result ?? [];
        if (_maxDamageTakenEnabled && _maxDamageTakenValue !== '' && _maxDamageTakenValue != null) {
          const threshold = Number(_maxDamageTakenValue);
          if (!Number.isNaN(threshold)) {
            filtered = filtered.filter(r => r?.damageTaken == null || r.damageTaken <= threshold);
          }
        }
        ranking = filtered.slice(0, _topN);
        rankingLoading = false;
      }).catch(() => {
        if (!controller.aborted) { rankingLoading = false; rankingError = 'Failed to rank mobs'; }
      });
      return () => { controller.aborted = true; };
    }
  });

  // ---- Tiered mob ranker (armor mode) ----
  // For each mob, emits one row per "tier":
  //   - lowest non-boss maturity (by level)
  //   - median non-boss maturity (by level)
  //   - highest non-boss maturity (by level)
  //   - each boss maturity, separately
  // When the preferred non-boss tier lacks usable data (no TotalDamage and no
  // DamagePotential bucket), the nearest non-boss maturity by list distance
  // that DOES have data is used instead. Tier picks are deduped per mob so
  // very short maturity lists don't emit duplicates.
  // Rows are sorted by damageDeflected desc, falling back to typeScore for
  // composition-only rows.

  function maturityHasUsableData(mat) {
    if (!mat) return false;
    if (mat?.Properties?.DamagePotential) return true;
    for (const atk of mat?.Attacks || []) {
      if ((atk?.TotalDamage ?? 0) > 0) return true;
    }
    return false;
  }

  function pickNearestWithData(arr, preferredIdx) {
    if (!arr?.length) return -1;
    const clamped = Math.max(0, Math.min(arr.length - 1, preferredIdx));
    if (maturityHasUsableData(arr[clamped])) return clamped;
    for (let d = 1; d < arr.length; d++) {
      const up = clamped + d;
      const down = clamped - d;
      if (up < arr.length && maturityHasUsableData(arr[up])) return up;
      if (down >= 0 && maturityHasUsableData(arr[down])) return down;
    }
    return -1;
  }

  async function rankMobsTiered(mobs, defenseLayers, decayRates, { signal, hideApproximated: hideApprox } = {}) {
    const results = [];
    const list = mobs || [];
    const CHUNK = 80;
    // Per-type effective defense (armor only, no plate/ice in armor mode)
    // — used for the weakest-defense-type analysis per row.
    const effectiveDefByType = sumLayers(defenseLayers);
    for (let i = 0; i < list.length; i++) {
      if (signal?.aborted) return null;
      const mob = list[i];
      const mats = Array.isArray(mob?.Maturities) ? mob.Maturities : [];
      if (mats.length === 0) continue;

      // Sort by level ascending, nulls last (stable within equal levels)
      const sorted = mats.map((m, idx) => ({ m, idx })).sort((a, b) => {
        const la = a.m?.Properties?.Level;
        const lb = b.m?.Properties?.Level;
        if (la == null && lb == null) return a.idx - b.idx;
        if (la == null) return 1;
        if (lb == null) return -1;
        return la - lb;
      }).map(x => x.m);

      const nonBoss = sorted.filter(m => m?.Properties?.Boss !== true);
      const bosses = sorted.filter(m => m?.Properties?.Boss === true);

      // Non-boss tier picks with fallback
      const tierPicks = [];
      if (nonBoss.length > 0) {
        const seen = new Set();
        const candidates = [
          { tier: 'Low',    idx: 0 },
          { tier: 'Median', idx: Math.floor(nonBoss.length / 2) },
          { tier: 'High',   idx: nonBoss.length - 1 }
        ];
        for (const c of candidates) {
          const found = pickNearestWithData(nonBoss, c.idx);
          if (found < 0 || seen.has(found)) continue;
          seen.add(found);
          tierPicks.push({ tier: c.tier, maturity: nonBoss[found] });
        }
      }

      // Each boss is its own row (no fallback between bosses)
      const bossPicks = bosses
        .filter(maturityHasUsableData)
        .map(m => ({ tier: 'Boss', maturity: m }));

      const allPicks = [...tierPicks, ...bossPicks];
      if (allPicks.length === 0) continue;

      for (const pick of allPicks) {
        const synthMob = { ...mob, Maturities: [pick.maturity] };
        const score = scoreMob(synthMob, defenseLayers, 'average', 1, decayRates);
        if (score == null) continue;
        if (hideApprox && score.approximated) continue;
        results.push({
          mob,
          maturity: pick.maturity,
          tier: pick.tier,
          name: mob.Name,
          typeScore: score.typeScore,
          mitigationPct: score.mitigation != null ? score.mitigation * 100 : null,
          damageTaken: score.damageTaken,
          damageDeflected: score.damageDeflected,
          weakestType: findWeakestDefenseType(synthMob, effectiveDefByType),
          decayPerAttack: score.decayPerAttack,
          decayPerAttackMin: score.decayPerAttackMin,
          decayPerAttackMax: score.decayPerAttackMax,
          hasTotalDamage: score.hasTotalDamage,
          hasComposition: score.hasComposition,
          approximated: score.approximated === true,
          maturityLabel: pick.maturity?.Name ?? null,
          maturityLevel: pick.maturity?.Properties?.Level ?? null
        });
      }

      if ((i + 1) % CHUNK === 0) {
        await new Promise(resolve => setTimeout(resolve, 0));
        if (signal?.aborted) return null;
      }
    }

    // Sort: damage-available rows first, ranked by deflected desc; then
    // composition-only rows by type score desc.
    results.sort((a, b) => {
      const ga = !a.hasComposition ? 3 : !a.hasTotalDamage ? 2 : 1;
      const gb = !b.hasComposition ? 3 : !b.hasTotalDamage ? 2 : 1;
      if (ga !== gb) return ga - gb;
      if (ga === 3) return (a.name || '').localeCompare(b.name || '');
      if (ga === 2) return (b.typeScore ?? 0) - (a.typeScore ?? 0);
      const cmp = (b.damageDeflected ?? -Infinity) - (a.damageDeflected ?? -Infinity);
      if (cmp !== 0) return cmp;
      return (a.approximated ? 1 : 0) - (b.approximated ? 1 : 0);
    });
    return results;
  }

  function formatPct(v) {
    if (v == null || Number.isNaN(v)) return '—';
    return `${Number(v).toFixed(1)}%`;
  }
  function formatNum(v, digits = 1) {
    if (v == null || Number.isNaN(v)) return '—';
    return Number(v).toFixed(digits);
  }

  let fullToolHref = $derived.by(() => {
    if (mode === 'recommend-armors') {
      return buildAdvisorUrl({ mob: mob?.Name });
    }
    return buildAdvisorUrl({ armor: armorSet?.Name });
  });

  function armorDetailHref(name) {
    return `/items/armorsets/${encodeURIComponentSafe(name)}`;
  }
  function mobDetailHref(name) {
    return `/information/mobs/${encodeURIComponentSafe(name)}`;
  }

  let poolEmpty = $derived(
    mode === 'recommend-armors' && useMyPool && poolLoaded && poolArmorNames.length === 0
  );

  // Map raw ranking rows into the shape FancyTable consumes. Adds a link
  // field referenced by the name column's formatter so the primary cell
  // is clickable without needing a custom cell snippet.
  let tableRows = $derived.by(() => ranking.map((r, i) => {
    const approximated = r?.approximated === true;
    const prefix = approximated ? '~' : '';
    const name = r?.name ?? '';
    const planet = mode === 'recommend-mobs' ? (r?.mob?.Planet?.Name ?? '—') : '';
    // Mob panel: best-mitigation maturity for this armor set against the
    // effective mob (computed in the ranking effect).
    const best = r?.bestMaturity ?? null;
    const bestLabel = best
      ? `${best.name}${best.level != null ? ` (L${best.level})` : ''}`
      : '—';
    const bestPctVal = best?.mitigation != null ? best.mitigation * 100 : null;
    const bestDisplay = best && bestPctVal != null
      ? `${best.name}${best.level != null ? ` L${best.level}` : ''} · ${bestPctVal.toFixed(1)}%`
      : '—';
    // Weakest defense type (the one leaking the most damage at max roll).
    // Null means the armor fully covers every attack of the target, so
    // there is no specific upgrade target.
    const weakest = r?.weakestType ?? null;
    const weakestDisplay = weakest ? `${weakest.type} (+${Number(weakest.leak).toFixed(0)})` : '—';
    const weakestLeakVal = weakest?.leak ?? 0;
    const maturityHp = r?.maturity?.Properties?.Health ?? null;
    return {
      rank: i + 1,
      name,
      nameLink: mode === 'recommend-armors' ? armorDetailHref(name) : mobDetailHref(name),
      planet,
      approximated,
      tier: r?.tier ?? '',
      maturityLabel: r?.maturityLabel ?? '',
      maturityLevel: r?.maturityLevel ?? null,
      maturityDisplay: (r?.maturityLabel ?? '—') + (r?.maturityLevel != null ? ` (L${r.maturityLevel})` : ''),
      maturityHp,
      maturityHpDisplay: maturityHp != null ? Number(maturityHp).toLocaleString() : '—',
      bestMaturityLabel: bestLabel,
      bestMaturityPct: bestPctVal,
      bestMaturityDisplay: bestDisplay,
      weakestDisplay,
      weakestLeak: weakestLeakVal,
      weakestType: weakest?.type ?? null,
      mitigationPct: r?.mitigationPct ?? null,
      mitigationDisplay: r?.mitigationPct == null ? '—' : `${prefix}${Number(r.mitigationPct).toFixed(1)}%`,
      damageTaken: r?.damageTaken ?? null,
      damageTakenDisplay: r?.damageTaken == null ? '—' : `${prefix}${Number(r.damageTaken).toFixed(1)}`,
      damageDeflected: r?.damageDeflected ?? null,
      deflectedDisplay: r?.damageDeflected == null ? '—' : `${prefix}${Number(r.damageDeflected).toFixed(1)}`,
      decayPerAttack: r?.decayPerAttack ?? null,
      decayDisplay: r?.decayPerAttack == null ? '—' : `${prefix}${Number(r.decayPerAttack).toFixed(2)}`
    };
  }));

  const APPROX_TIP = 'Damage values approximated from this maturity&#039;s Damage Potential bucket.';
  function nameCell(v, row) {
    const tag = row.approximated ? `<span class="approx-tag" title="${APPROX_TIP}">~approx</span>` : '';
    return row.nameLink ? `<a href="${row.nameLink}">${v}</a>${tag}` : `${v}${tag}`;
  }

  let tableColumns = $derived.by(() => {
    const numClass = (_v, row) => row.approximated ? 'num approx-num' : 'num';
    if (mode === 'recommend-armors') {
      const cols = [
        {
          key: 'name',
          header: 'Armor Set',
          main: true,
          width: '140px',
          searchable: true,
          formatter: nameCell
        }
      ];
      // Hide Best Maturity when the user has already pinned one — every
      // row would trivially show that same maturity, adding no info.
      if (selectedMaturity === AVERAGE_NO_BOSS) {
        cols.push({ key: 'bestMaturityDisplay', header: 'Best maturity', sortValue: (row) => row.bestMaturityPct ?? -1, searchable: true, hideOnMobile: true });
      }
      cols.push(
        { key: 'weakestDisplay', header: 'Weakest type', sortValue: (row) => row.weakestLeak ?? 0, searchable: true, hideOnMobile: true },
        { key: 'deflectedDisplay', header: 'Deflected', sortValue: (row) => row.damageDeflected ?? -1, cellClass: numClass, searchable: false },
        { key: 'mitigationDisplay', header: 'Mitigation', sortValue: (row) => row.mitigationPct ?? -1, cellClass: numClass, searchable: false, hideOnMobile: true },
        { key: 'damageTakenDisplay', header: 'Dmg taken', sortValue: (row) => row.damageTaken ?? Infinity, cellClass: numClass, searchable: false },
        { key: 'decayDisplay', header: 'Decay/hit', sortValue: (row) => row.decayPerAttack ?? -1, cellClass: numClass, searchable: false, hideOnMobile: true }
      );
      return cols;
    }
    return [
      {
        key: 'name',
        header: 'Mob',
        main: true,
        width: '140px',
        searchable: true,
        formatter: nameCell
      },
      { key: 'planet', header: 'Planet', searchable: true, hideOnMobile: true },
      { key: 'maturityDisplay', header: 'Maturity', sortValue: (row) => row.maturityLevel ?? -1, searchable: true },
      { key: 'maturityHpDisplay', header: 'HP', sortValue: (row) => row.maturityHp ?? -1, cellClass: numClass, searchable: false },
      { key: 'weakestDisplay', header: 'Weakest type', sortValue: (row) => row.weakestLeak ?? 0, searchable: true, hideOnMobile: true },
      { key: 'deflectedDisplay', header: 'Deflected', sortValue: (row) => row.damageDeflected ?? -1, cellClass: numClass, searchable: false },
      { key: 'mitigationDisplay', header: 'Mitigation', sortValue: (row) => row.mitigationPct ?? -1, cellClass: numClass, searchable: false, hideOnMobile: true },
      { key: 'damageTakenDisplay', header: 'Dmg taken', sortValue: (row) => row.damageTaken ?? Infinity, cellClass: numClass, searchable: false },
      { key: 'decayDisplay', header: 'Decay/hit', sortValue: (row) => row.decayPerAttack ?? -1, cellClass: numClass, searchable: false, hideOnMobile: true }
    ];
  });
</script>

<div class="inline-avm-panel">
  {#if mode === 'recommend-armors' && !mobLacksDamageData}
    <div class="controls">
      <div class="ctl-group ctl-selection">
        <div class="scope-group" role="radiogroup" aria-label="Armors">
          <span class="scope-label">Armors</span>
          <label>
            <input type="radio" name="inline-avm-pool" value="all" checked={!useMyPool} onchange={() => (useMyPool = false)} />
            All
          </label>
          <label>
            <input type="radio" name="inline-avm-pool" value="pool" checked={useMyPool} onchange={() => (useMyPool = true)} />
            My pool
          </label>
        </div>
        {#if maturityOptions.length > 0}
          <label class="filter">
            <span>Maturity</span>
            <select bind:value={selectedMaturity}>
              <option value={AVERAGE_NO_BOSS}>Average (excl. bosses)</option>
              {#each maturityOptions as opt}
                <option value={opt.name}>
                  {opt.name}{opt.level != null ? ` (L${opt.level})` : ''}{opt.boss ? ' - Boss' : ''}
                </option>
              {/each}
            </select>
          </label>
        {/if}
      </div>
      <div class="ctl-group ctl-filters">
        <label
          class="cb"
          title={effectiveMobHasDamage
            ? 'Hides armor sets whose defense against this mob\u2019s damage types is more than 1.5× the mob\u2019s hardest hit. Only the defense values for types the mob actually deals are counted, so off-type padding is ignored. This filters out overkill armor and leaves gear that is a real match for the fight. Requires the mob to have total damage data; disabled when only composition is known.'
            : 'Requires total damage data on the mob. Ranking is falling back to damage-composition match only.'}
        >
          <input
            type="checkbox"
            bind:checked={rightSized}
            disabled={!effectiveMobHasDamage}
          />
          Matching armors only
        </label>
        <label class="cb" title="Hide rows whose damage values were approximated from this mob's Damage Potential bucket.">
          <input type="checkbox" bind:checked={hideApproximated} />
          Hide approximated
        </label>
      </div>
      <a class="btn ctl-action" href={fullToolHref}>Open in Gear Advisor →</a>
    </div>
    {#if !effectiveMobHasDamage && !mobLacksDamageData}
      <p class="info-note">No total damage data — ranking by composition match only.</p>
    {/if}
  {:else if mode === 'recommend-mobs' && armorHasDefense}
    <div class="controls">
      <div class="ctl-group ctl-selection">
        <label class="filter">
          <span>Planet</span>
          <select bind:value={planetFilter}>
            {#each planetOptions as p}
              <option value={p}>{p}</option>
            {/each}
          </select>
        </label>
        <label class="filter filter-range">
          <span>HP</span>
          <input type="number" min="0" step="100" bind:value={hpMin} placeholder="min" aria-label="HP min" />
          <span class="range-sep">–</span>
          <input type="number" min="0" step="100" bind:value={hpMax} placeholder="max" aria-label="HP max" />
        </label>
      </div>
      <div class="ctl-group ctl-filters">
        <label class="cb inline-input" title="Filter out mobs whose expected damage per hit exceeds the threshold">
          <input type="checkbox" bind:checked={maxDamageTakenEnabled} />
          Max dmg
          <input
            type="number"
            min="0"
            step="5"
            bind:value={maxDamageTakenValue}
            disabled={!maxDamageTakenEnabled}
            placeholder="20"
            aria-label="Max damage taken threshold"
          />
        </label>
        <label class="cb" title="Hide rows whose damage values were approximated from a mob's Damage Potential bucket.">
          <input type="checkbox" bind:checked={hideApproximated} />
          Hide approximated
        </label>
      </div>
      <a class="btn ctl-action" href={fullToolHref}>Open in Gear Advisor →</a>
    </div>
  {/if}

  <div class="body">
    {#if !listsLoaded && !listsError}
      <p class="empty-msg">Loading…</p>
    {:else if listsError}
      <p class="empty-msg error">Failed to load data.</p>
    {:else if mode === 'recommend-armors' && mobLacksDamageData}
      <p class="empty-msg">This mob has no damage data recorded yet.</p>
    {:else if mode === 'recommend-mobs' && !armorHasDefense}
      <p class="empty-msg">This armor set has no defense values.</p>
    {:else if poolEmpty}
      <p class="empty-msg">
        Your armor pool is empty.
        <a href={fullToolHref}>Configure it in the Gear Advisor →</a>
      </p>
    {:else if rankingLoading}
      <p class="empty-msg">Ranking…</p>
    {:else if rankingError}
      <p class="empty-msg error">{rankingError}</p>
    {:else if ranking.length === 0}
      <p class="empty-msg">No matches found.</p>
    {:else}
      <div class="table-wrap">
        <FancyTable
          columns={tableColumns}
          data={tableRows}
          rowHeight={32}
          pageSize={50}
          searchable={true}
          sortable={true}
          compact
          preserveDataOrder
          rowClass={(row) => row.approximated ? 'approximated-row' : null}
          emptyMessage="No matches"
        />
      </div>
    {/if}
  </div>

</div>

<style>
  .inline-avm-panel {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 2px 0;
  }

  .controls {
    display: flex;
    gap: 8px 14px;
    flex-wrap: wrap;
    align-items: center;
  }

  /* Groups of related controls. Each group wraps internally, but the outer
     container wraps between groups, so related controls stay together. */
  .ctl-group {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 12px;
  }

  .ctl-group.ctl-selection {
    gap: 6px 14px;
  }

  .ctl-group.ctl-filters {
    gap: 6px 12px;
  }

  .ctl-action {
    margin-left: auto;
  }

  /* Compact HP min/max as a single unit so they never split across rows */
  .filter-range {
    gap: 4px;
  }
  .filter-range input[type="number"] {
    width: 4rem;
  }
  .filter-range .range-sep {
    color: var(--text-muted);
    font-weight: 500;
  }

  /* Radio group laid out horizontally with label to the left */
  .scope-group {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .scope-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    padding-right: 4px;
  }

  .scope-group label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    cursor: pointer;
    color: var(--text-color);
  }

  /* Horizontal label+control on desktop, stacks on mobile */
  .filter {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    margin: 0;
  }

  .filter select,
  .filter input {
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 4px 6px;
    font-size: 12px;
    min-width: 5rem;
    box-sizing: border-box;
  }

  .filter input[type="number"] {
    width: 5rem;
    min-width: 0;
  }

  .filter select:focus,
  .filter input:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .cb {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    color: var(--text-color);
    cursor: pointer;
  }

  .cb.inline-input input[type="number"] {
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 3px 5px;
    font-size: 12px;
    width: 4.5rem;
    box-sizing: border-box;
    margin-left: 2px;
  }

  .cb input[type="checkbox"] {
    margin: 0;
    cursor: pointer;
    accent-color: var(--accent-color);
  }

  .cb input[type="checkbox"]:disabled {
    cursor: not-allowed;
  }

  .cb input[type="number"]:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .cb:has(input[type="checkbox"]:disabled) {
    color: var(--text-muted);
    cursor: not-allowed;
  }

  .info-note {
    margin: 0;
    font-size: 11px;
    color: var(--text-muted);
    font-style: italic;
  }

  .empty-msg {
    margin: 0;
    padding: 10px 8px;
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
  }

  .empty-msg.error {
    color: var(--error-color);
  }

  .empty-msg a {
    color: var(--accent-color);
    text-decoration: none;
    margin-left: 4px;
  }

  .empty-msg a:hover {
    text-decoration: underline;
  }

  /* Scrollable wrapper: ~10 visible rows in compact mode (32px each)
     plus the header; the rest scrolls inside FancyTable. min-width:0 and
     width:100% let the wrapper shrink with the parent on mobile so the
     FancyTable's internal horizontal scroll fires rather than the whole
     page overflowing. */
  .table-wrap {
    width: 100%;
    max-height: 380px;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
  }

  /* Right-align numeric cells in FancyTable via the cellClass hook. */
  :global(.table-wrap .table-cell.num) {
    text-align: right;
    font-variant-numeric: tabular-nums;
    justify-content: flex-end;
  }

  /* Damage-potential approximated rows: warning-tinted left border and
     italic muted numeric cells so the fallback is visually obvious. */
  :global(.table-wrap .table-row.approximated-row) {
    border-left: 3px solid var(--warning-color, #fbbf24);
    background-color: color-mix(in srgb, var(--warning-color, #fbbf24) 5%, transparent);
  }

  :global(.table-wrap .table-cell.approx-num) {
    color: var(--text-muted, #999);
    font-style: italic;
  }

  :global(.table-wrap .approx-tag) {
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

  /* Button style — positioning comes from `.ctl-action` so the inline
     "Max dmg" threshold input keeps its own size without triggering
     margin-left:auto. */
  .btn {
    display: inline-block;
    padding: 5px 12px;
    font-size: 12px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
    cursor: pointer;
    text-decoration: none;
    white-space: nowrap;
  }

  .btn:hover {
    background-color: var(--hover-color);
  }

  @media (max-width: 640px) {
    /* Stack the three control groups vertically. Each group keeps its
       internal horizontal layout (with wrap) so related items stay grouped. */
    .controls {
      flex-direction: column;
      align-items: stretch;
      gap: 8px;
    }
    .ctl-group {
      width: 100%;
      gap: 6px 10px;
    }
    .ctl-action {
      margin-left: 0;
      flex: 1 1 100%;
      text-align: center;
      padding: 7px 12px;
    }
    /* Keep .filter horizontal on mobile too (label beside input) — the group
       wraps internally if it runs out of space, which is cleaner than every
       filter stacking label-above-input. */
    .filter input[type="number"] {
      width: 4.5rem;
    }
    .filter-range input[type="number"] {
      width: 3.5rem;
    }
    .table-wrap {
      max-height: 340px;
    }
  }
</style>

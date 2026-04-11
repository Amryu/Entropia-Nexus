// @ts-nocheck
// Core logic for the Effect Optimizer gear advisor tool.
// Handles effect extraction, scoring, suggestion engine (beam search + per-slot).

import { summarizeEffects, buildEffectCaps, getEffectStrength } from '$lib/utils/loadoutEffects.js';

// ---------------------------------------------------------------------------
// Presets
// ---------------------------------------------------------------------------

const PRESET_DEFS = [
  { id: 'max-crit-chance', label: 'Max Crit Chance', effects: ['Critical Chance Added'] },
  { id: 'max-reload', label: 'Max Reload', effects: ['Reload Speed Increased'] },
  { id: 'max-lifesteal', label: 'Max Lifesteal', effects: ['Lifesteal Added'] },
  { id: 'max-run-speed', label: 'Max Run Speed', effects: ['Run Speed Increased'] },
  { id: 'max-crit-damage', label: 'Max Crit Damage', effects: ['Critical Damage Added'] },
];

export function getEffectiveCapValue(effectName, effectCaps) {
  const caps = effectCaps?.[effectName];
  if (!caps) return null;
  const item = caps.item ?? Infinity;
  const total = caps.total ?? Infinity;
  const effective = Math.min(item, total);
  return Number.isFinite(effective) ? effective : null;
}

export function buildPresets(effectCaps) {
  return PRESET_DEFS.map(def => {
    const targets = {};
    for (const name of def.effects) {
      const cap = getEffectiveCapValue(name, effectCaps);
      if (cap != null) targets[name] = cap;
    }
    return { ...def, targets };
  });
}

// Keep static fallback for backwards compat
export const EFFECT_PRESETS = PRESET_DEFS;

// ---------------------------------------------------------------------------
// Effect categories for the target selection dialog
// ---------------------------------------------------------------------------

const OFFENSIVE_EFFECT_NAMES = new Set([
  'Critical Chance Added',
  'Critical Damage Added',
  'Reload Speed Increased',
  'Damage Done Increased',
  'Dominance Increased',
  'Melee Attack Speed',
]);

const DEFENSIVE_EFFECT_NAMES = new Set([
  'Health Added',
  'Lifesteal Added',
  'Damage Taken Decreased',
  'Evade Chance Increased',
  'Dodge Chance Increased',
  'Jamming Chance Increased',
  'Critical Damage Taken Decreased',
  'Regeneration Increased',
  'Regeneration Per Second',
]);

const UTILITY_EFFECT_NAMES = new Set([
  'Run Speed Increased',
  'Movement Speed Increased',
  'Carry Capacity Added',
  'Auto Loot',
  'Skill Gain Increased',
  'Skill Gain - Laser Increased',
  'Skill Gain - BLP Increased',
  'Skill Gain - Plasma Increased',
  'Skill Gain - Gauss Increased',
  'Skill Gain - Blades Increased',
  'Skill Gain - Brawler Increased',
  'Skill Gain - Clubs Increased',
  'Skill Gain - Power Fist Increased',
  'Skill Gain - Whips Increased',
  'Skill Gain - Paramedic Increased',
  'Skill Gain - Cryogenic Increased',
  'Skill Gain - Pyrokinetic Increased',
  'Skill Gain - Electrokinetic Increased',
  'Skill Gain - Mindforce Increased',
  'Taming Chance Increased',
]);

export function categorizeEffects(effectsCatalog, effectCaps) {
  const effects = (effectsCatalog || []).filter(e => e?.Properties?.IsPositive === true && e?.Name);
  const used = new Set();
  const build = (nameSet) => effects
    .filter(e => nameSet.has(e.Name))
    .map(e => { used.add(e.Name); return formatEffectForPicker(e, effectCaps); });

  const offensive = build(OFFENSIVE_EFFECT_NAMES);
  const defensive = build(DEFENSIVE_EFFECT_NAMES);
  const utility = build(UTILITY_EFFECT_NAMES);
  const misc = effects
    .filter(e => !used.has(e.Name))
    .map(e => formatEffectForPicker(e, effectCaps));

  return { offensive, defensive, utility, misc };
}

function formatEffectForPicker(effect, effectCaps) {
  const caps = effectCaps[effect.Name];
  const itemCap = caps?.item ?? null;
  const totalCap = caps?.total ?? null;
  return {
    name: effect.Name,
    unit: effect.Properties?.Unit || '',
    itemCap,
    totalCap,
  };
}

// Per-effect overcap penalty weights (1.0 = full penalty, lower = less bad to overcap)
const OVERCAP_WEIGHTS = {
  'Run Speed Increased': 0.3,
  'Critical Damage Added': 0.5,
  'Health Added': 0.4,
  'Critical Chance Added': 1.0,
  'Reload Speed Increased': 0.8,
  'Lifesteal Added': 0.9,
};
const DEFAULT_OVERCAP_WEIGHT = 0.8;

// Penalty per reuse of an item across selected results. Higher = more variety.
const DEFAULT_DIVERSITY_WEIGHT = 40;

// ---------------------------------------------------------------------------
// Effect extraction helpers
// ---------------------------------------------------------------------------

export function extractEquipEffects(item) {
  return item?.EffectsOnEquip || [];
}

export function extractArmorSetEffects(armorSet, pieceCount) {
  const all = armorSet?.EffectsOnSetEquip || [];
  // Keep effects where MinSetPieces <= pieceCount, deduplicate by effect name
  // keeping the highest-threshold version (most specific)
  const byName = new Map();
  for (const effect of all) {
    const minPieces = effect?.Values?.MinSetPieces ?? effect?.MinSetPieces ?? 0;
    if (minPieces > pieceCount) continue;
    const name = effect?.Name;
    if (!name) continue;
    const existing = byName.get(name);
    if (!existing || (existing.minPieces < minPieces)) {
      byName.set(name, { effect, minPieces });
    }
  }
  return [...byName.values()].map(x => x.effect);
}

export function getPetEffectKey(effect) {
  const name = effect?.Name || '';
  const strength = effect?.Properties?.Strength ?? effect?.Values?.Strength ?? effect?.Values?.Value ?? 0;
  return `${name}::${strength}`;
}

export function extractPetEffect(pet, selectedEffectKey) {
  if (!pet?.Effects || !selectedEffectKey) return null;
  const keyed = pet.Effects.find(e => getPetEffectKey(e) === selectedEffectKey);
  if (keyed) return keyed;
  return pet.Effects.find(e => e?.Name === selectedEffectKey) || null;
}

// ---------------------------------------------------------------------------
// Ring filtering
// ---------------------------------------------------------------------------

const RING_SLOT_RE = /ring|finger/i;

export function isRingSlot(slot) {
  return RING_SLOT_RE.test(slot || '');
}

export function getRingSide(slot) {
  const s = (slot || '').toLowerCase();
  if (s.includes('left')) return 'left';
  if (s.includes('right')) return 'right';
  return null;
}

export function filterRings(clothings, side) {
  return (clothings || []).filter(c => {
    const slot = c?.Properties?.Slot || '';
    if (!isRingSlot(slot)) return false;
    if (side) return getRingSide(slot) === side;
    return true;
  });
}

export function filterClothingBySlot(clothings, slotName) {
  return (clothings || []).filter(c => {
    const slot = c?.Properties?.Slot || '';
    return slot === slotName && !isRingSlot(slot);
  });
}

export function filterArmorSetsWithEffects(armorSets) {
  return (armorSets || []).filter(s =>
    Array.isArray(s?.EffectsOnSetEquip) && s.EffectsOnSetEquip.length > 0
  );
}

// ---------------------------------------------------------------------------
// Collect all effects from a loadout configuration
// ---------------------------------------------------------------------------

export function collectAllEffects(slots, entities) {
  const effects = [];

  // Left ring
  if (slots.leftRing) {
    effects.push(...extractEquipEffects(findByName(entities.leftRings, slots.leftRing)));
  }
  // Right ring
  if (slots.rightRing) {
    effects.push(...extractEquipEffects(findByName(entities.rightRings, slots.rightRing)));
  }
  // Armor set
  if (slots.armorSet) {
    const set = findByName(entities.armorSets, slots.armorSet);
    if (set) effects.push(...extractArmorSetEffects(set, slots.armorSetPieces || 7));
  }
  // Pet
  if (slots.pet && slots.petActiveEffect) {
    const pet = findByName(entities.pets, slots.pet);
    if (pet) {
      const eff = extractPetEffect(pet, slots.petActiveEffect);
      if (eff) effects.push(eff);
    }
  }
  // Secondary slots
  const secondaryKeys = ['weapon', 'amplifier', 'scope', 'scopeSight', 'sight', 'absorber', 'implant'];
  for (const key of secondaryKeys) {
    const name = slots.secondary?.[key];
    if (name && entities[key]) {
      effects.push(...extractEquipEffects(findByName(entities[key], name)));
    }
  }
  // Clothing secondary slots
  if (slots.secondary?.clothing) {
    for (const [, name] of Object.entries(slots.secondary.clothing)) {
      if (name) {
        const item = (entities.clothings || []).find(c => c.Name === name);
        if (item) effects.push(...extractEquipEffects(item));
      }
    }
  }

  return effects;
}

function findByName(list, name) {
  if (!name || !Array.isArray(list)) return null;
  return list.find(x => x.Name === name) || null;
}

// ---------------------------------------------------------------------------
// Aggregate effects using loadoutEffects.js
// ---------------------------------------------------------------------------

// Effects that use highest-value-wins instead of stacking
const MAX_VALUE_EFFECTS = new Set(['Auto Loot']);

export function aggregateEffects(itemEffects, effectsCatalog, effectCaps) {
  // Handle max-value effects: keep only the strongest instance
  const maxEffects = new Map();
  const stackingEffects = [];

  for (const eff of itemEffects) {
    const name = eff?.Name;
    if (name && MAX_VALUE_EFFECTS.has(name)) {
      const strength = getEffectStrength(eff);
      const current = maxEffects.get(name);
      if (!current || getEffectStrength(current) < strength) {
        maxEffects.set(name, eff);
      }
    } else {
      stackingEffects.push(eff);
    }
  }

  // Add back only the strongest instance of max-value effects
  for (const eff of maxEffects.values()) {
    stackingEffects.push(eff);
  }

  return summarizeEffects(
    { itemEffects: stackingEffects, actionEffects: [], bonusEffects: [] },
    { effectsCatalog, effectCaps }
  );
}

// ---------------------------------------------------------------------------
// Scoring
// ---------------------------------------------------------------------------

export function scoreCombination(targets, itemEffects, effectsCatalog, effectCaps, options = {}) {
  const { overcapMode = 'punish', priorities = null } = options;
  const summary = aggregateEffects(itemEffects, effectsCatalog, effectCaps);

  let score = 0;
  const details = [];
  const targetKeys = Object.keys(targets);
  const numTargets = targetKeys.length;

  for (const [effectName, targetValue] of Object.entries(targets)) {
    const entry = summary.find(e => e.name === effectName);
    const achieved = entry ? Math.abs(entry.signedTotal) : 0;
    const ratio = targetValue > 0 ? achieved / targetValue : 1;
    const diff = achieved - targetValue;

    // Priority multiplier: higher priority targets get more weight
    // priorities is an array of effect names in priority order (index 0 = highest)
    let priorityMult = 1;
    if (priorities && priorities.length > 1) {
      const idx = priorities.indexOf(effectName);
      if (idx >= 0) {
        priorityMult = 1 + (numTargets - idx) * 0.5;
      }
    }

    let effectScore = 0;

    if (Math.abs(diff) < 0.01) {
      // Perfect match
      effectScore = 1000;
    } else if (diff > 0) {
      // Overcapped
      if (overcapMode === 'reject') {
        // Hard reject: any overcap makes the combination unviable
        return { score: -Infinity, details: [], summary, rejected: true };
      } else if (overcapMode === 'punish') {
        const weight = OVERCAP_WEIGHTS[effectName] ?? DEFAULT_OVERCAP_WEIGHT;
        effectScore = 500 - (diff / targetValue) * 200 * weight;
      } else {
        // Ignore overcap - treat as near-perfect
        effectScore = 800;
      }
    } else {
      // Under target - heavier penalty
      effectScore = ratio * 400;
    }

    effectScore *= priorityMult;
    details.push({ effectName, targetValue, achieved, ratio, diff, effectScore });
    score += effectScore;
  }

  return { score, details, summary };
}

// ---------------------------------------------------------------------------
// Suggestion engine
// ---------------------------------------------------------------------------

// Get which target effects an item contributes to
function itemRelevance(item, targetNames, isArmorSet = false, pieceCount = 7) {
  const effects = isArmorSet
    ? extractArmorSetEffects(item, pieceCount)
    : extractEquipEffects(item);
  let relevant = 0;
  let totalStrength = 0;
  for (const eff of effects) {
    if (targetNames.has(eff?.Name)) {
      relevant++;
      totalStrength += getEffectStrength(eff);
    }
  }
  return { relevant, totalStrength };
}

function prefilterCandidates(items, targetNames, isArmorSet = false, pieceCount = 7) {
  return items
    .map(item => {
      const rel = itemRelevance(item, targetNames, isArmorSet, pieceCount);
      return { item, ...rel };
    })
    .filter(x => x.relevant > 0)
    .sort((a, b) => b.totalStrength - a.totalStrength || b.relevant - a.relevant);
}

// For pets, expand each pet into (pet, effectKey) candidates
function prefilterPetCandidates(pets, targetNames) {
  const candidates = [];
  for (const pet of (pets || [])) {
    for (const eff of (pet.Effects || [])) {
      if (targetNames.has(eff?.Name)) {
        candidates.push({
          item: pet,
          effectKey: getPetEffectKey(eff),
          effectName: eff?.Name,
          strength: getEffectStrength(eff),
        });
      }
    }
  }
  candidates.sort((a, b) => b.strength - a.strength);
  return candidates;
}

/**
 * Canonical signature for a set of effect objects. Two items are considered
 * interchangeable (alternatives) ONLY when every single effect matches exactly -
 * same effect names, same Values, and same count. Any difference in a Values
 * field or an extra / missing effect produces a distinct signature.
 */
function normalizeEffect(e) {
  if (!e?.Name) return null;
  const parts = [e.Name];
  if (e.Values && typeof e.Values === 'object') {
    const keys = Object.keys(e.Values).sort();
    for (const k of keys) {
      parts.push(`v.${k}=${JSON.stringify(e.Values[k])}`);
    }
  }
  if (e.Properties && typeof e.Properties === 'object') {
    const keys = Object.keys(e.Properties).sort();
    for (const k of keys) {
      parts.push(`p.${k}=${JSON.stringify(e.Properties[k])}`);
    }
  }
  return parts.join('~');
}

export function effectSignature(effects) {
  const entries = [];
  for (const e of (effects || [])) {
    const n = normalizeEffect(e);
    if (n) entries.push(n);
  }
  entries.sort();
  return entries.join('||');
}

/**
 * Group candidate entries by effect signature. Returns an array of groups,
 * each { signature, effects, members: [...] } where members are interchangeable.
 */
function groupSlotAlternatives(entries, getEffects) {
  const groups = new Map();
  for (const entry of entries) {
    const effs = getEffects(entry);
    const sig = effectSignature(effs);
    if (!sig) continue;
    let group = groups.get(sig);
    if (!group) {
      group = { signature: sig, effects: effs, members: [] };
      groups.set(sig, group);
    }
    group.members.push(entry);
  }
  return [...groups.values()];
}

/**
 * Find best equipment combinations via beam search.
 *
 * @param {object} slotConfigs - Map of slotKey to config:
 *   {
 *     type: 'ring' | 'armorSet' | 'pet' | 'equipment',
 *     items: Item[],          // candidate pool (ignored if locked)
 *     locked: boolean,        // true = keep current item, don't optimize
 *     currentEffects: Effect[], // effects from currently-equipped item (added to base when locked)
 *     pieceCount?: number,    // armorSet only
 *     pairExclude?: string,   // slotKey that cannot contain the same item (rings)
 *   }
 */
export function findBestCombinations(targets, slotConfigs, effectsCatalog, effectCaps, options = {}) {
  const {
    maxResults = 10,
    beamWidth = 100,
    topK = 20,
    diversityWeight = DEFAULT_DIVERSITY_WEIGHT,
  } = options;
  const targetNames = new Set(Object.keys(targets));

  // Aggregate base effects from all locked slots
  const lockedEffects = [];
  for (const cfg of Object.values(slotConfigs || {})) {
    if (cfg?.locked && Array.isArray(cfg.currentEffects)) {
      lockedEffects.push(...cfg.currentEffects);
    }
  }

  // Build per-slot group lists for unlocked slots
  const unlockedSlots = [];
  for (const [key, cfg] of Object.entries(slotConfigs || {})) {
    if (!cfg || cfg.locked) continue;
    const items = cfg.items || [];
    const pieceCount = cfg.pieceCount || 7;

    let prefiltered;
    let getEffects;

    if (cfg.type === 'pet') {
      prefiltered = prefilterPetCandidates(items, targetNames);
      getEffects = (entry) => {
        const e = extractPetEffect(entry.item, entry.effectKey);
        return e ? [e] : [];
      };
    } else if (cfg.type === 'armorSet') {
      prefiltered = prefilterCandidates(items, targetNames, true, pieceCount);
      getEffects = (entry) => extractArmorSetEffects(entry.item, pieceCount);
    } else {
      prefiltered = prefilterCandidates(items, targetNames);
      getEffects = (entry) => extractEquipEffects(entry.item);
    }

    const sliced = prefiltered.slice(0, topK);
    const groups = groupSlotAlternatives(sliced, getEffects);
    if (groups.length === 0) continue;

    unlockedSlots.push({
      key,
      type: cfg.type,
      pairExclude: cfg.pairExclude || null,
      groups,
    });
  }

  // Beam search over slot groups
  let beam = [{ items: {}, alternatives: {}, effects: [...lockedEffects], score: 0 }];

  for (const slot of unlockedSlots) {
    const nextBeam = [];

    for (const candidate of beam) {
      // Keep "skip this slot" as an option
      nextBeam.push({
        items: { ...candidate.items },
        alternatives: { ...candidate.alternatives },
        effects: [...candidate.effects],
        score: candidate.score,
      });

      for (const group of slot.groups) {
        const rep = group.members[0];
        const repName = rep.item?.Name;
        if (!repName) continue;

        // Rings: avoid same item in both ring slots
        if (slot.pairExclude) {
          const partner = candidate.items[slot.pairExclude];
          const partnerName = (partner && typeof partner === 'object') ? partner.name : partner;
          if (partnerName && partnerName === repName && group.members.length === 1) continue;
        }

        const newItems = { ...candidate.items };
        const newAlts = { ...candidate.alternatives };

        if (slot.type === 'pet') {
          newItems[slot.key] = { name: repName, effectKey: rep.effectKey };
          newAlts[slot.key] = group.members.map(m => ({ name: m.item.Name, effectKey: m.effectKey }));
        } else {
          newItems[slot.key] = repName;
          newAlts[slot.key] = group.members.map(m => m.item.Name);
        }

        const allEffects = [...candidate.effects, ...group.effects];
        const { score } = scoreCombination(targets, allEffects, effectsCatalog, effectCaps, options);
        nextBeam.push({ items: newItems, alternatives: newAlts, effects: allEffects, score });
      }
    }

    nextBeam.sort((a, b) => (b.score || 0) - (a.score || 0));
    beam = nextBeam.slice(0, beamWidth);
  }

  // Final scoring with details/summary
  const scored = beam.map(candidate => {
    const { score, details, summary } = scoreCombination(targets, candidate.effects, effectsCatalog, effectCaps, options);
    return { ...candidate, score, details, summary };
  });
  scored.sort((a, b) => b.score - a.score);

  // Dedup by total effect signature (collapses pure alternative-swap duplicates)
  const seen = new Set();
  const deduped = [];
  for (const r of scored) {
    const sig = effectSignature(r.effects);
    if (seen.has(sig)) continue;
    seen.add(sig);
    deduped.push(r);
  }

  // Greedy selection with diversity penalty: penalize reuse of the same item
  // across previously-selected results so the top-N vary.
  const selected = [];
  const itemUseCount = new Map();

  while (selected.length < maxResults && deduped.length > 0) {
    let bestIdx = -1;
    let bestAdjusted = -Infinity;
    for (let i = 0; i < deduped.length; i++) {
      const c = deduped[i];
      let penalty = 0;
      for (const val of Object.values(c.items)) {
        const name = (val && typeof val === 'object') ? val.name : val;
        if (!name) continue;
        penalty += (itemUseCount.get(name) || 0) * diversityWeight;
      }
      const adjusted = (c.score || 0) - penalty;
      if (adjusted > bestAdjusted) {
        bestAdjusted = adjusted;
        bestIdx = i;
      }
    }
    if (bestIdx === -1) break;
    const picked = deduped.splice(bestIdx, 1)[0];
    selected.push(picked);
    for (const val of Object.values(picked.items)) {
      const name = (val && typeof val === 'object') ? val.name : val;
      if (!name) continue;
      itemUseCount.set(name, (itemUseCount.get(name) || 0) + 1);
    }
  }

  return selected;
}

// ---------------------------------------------------------------------------
// Per-slot suggestion
// ---------------------------------------------------------------------------

/**
 * Suggest items for a specific slot.
 * @param {string} mode - 'contextual' (considers other equipped items) or 'standalone' (item's own contribution)
 */
export function suggestForSlot(slotKey, targets, currentSlots, entities, effectsCatalog, effectCaps, options = {}) {
  const { maxResults = 20, armorSetPieces = 7, mode = 'contextual' } = options;
  const targetNames = new Set(Object.keys(targets));

  // In contextual mode, collect effects from other slots
  const otherEffects = [];
  if (mode === 'contextual') {
    const slotKeys = ['leftRing', 'rightRing', 'armorSet', 'pet'];
    for (const key of slotKeys) {
      if (key === slotKey) continue;
      if (key === 'leftRing' && currentSlots.leftRing) {
        otherEffects.push(...extractEquipEffects(findByName(entities.leftRings, currentSlots.leftRing)));
      } else if (key === 'rightRing' && currentSlots.rightRing) {
        otherEffects.push(...extractEquipEffects(findByName(entities.rightRings, currentSlots.rightRing)));
      } else if (key === 'armorSet' && currentSlots.armorSet) {
        const set = findByName(entities.armorSets, currentSlots.armorSet);
        if (set) otherEffects.push(...extractArmorSetEffects(set, armorSetPieces));
      } else if (key === 'pet' && currentSlots.pet && currentSlots.petActiveEffect) {
        const pet = findByName(entities.pets, currentSlots.pet);
        if (pet) {
          const eff = extractPetEffect(pet, currentSlots.petActiveEffect);
          if (eff) otherEffects.push(eff);
        }
      }
    }
    if (currentSlots.secondary) {
      const secondaryKeys = ['weapon', 'amplifier', 'scope', 'scopeSight', 'sight', 'absorber', 'implant'];
      for (const key of secondaryKeys) {
        const name = currentSlots.secondary[key];
        if (name && entities[key]) {
          otherEffects.push(...extractEquipEffects(findByName(entities[key], name)));
        }
      }
    }
  }

  // Score a candidate item
  function scoreCandidate(slotEffects, itemName, extraProps = {}) {
    const allEffects = [...otherEffects, ...slotEffects];

    // Raw per-target item contribution (what the item itself provides)
    const itemValues = {};
    for (const effectName of Object.keys(targets)) {
      const itemEffect = slotEffects.find(e => e?.Name === effectName);
      itemValues[effectName] = itemEffect ? getEffectStrength(itemEffect) : 0;
    }

    if (mode === 'standalone') {
      // Standalone: measure what % of each target this item alone fills, averaged across all targets
      let totalPct = 0;
      const pctDetails = [];
      const numTargets = Object.keys(targets).length;
      for (const [effectName, targetValue] of Object.entries(targets)) {
        const itemStrength = itemValues[effectName];
        const pct = targetValue > 0 ? (itemStrength / targetValue) * 100 : 0;
        totalPct += Math.min(pct, 100);
        pctDetails.push({ effectName, targetValue, achieved: itemStrength, pct });
      }
      const avgPct = numTargets > 0 ? totalPct / numTargets : 0;
      return { name: itemName, score: avgPct, pctDetails, itemValues, ...extraProps };
    }

    // Contextual: full scoring with other effects
    const { score, details, summary } = scoreCombination(targets, allEffects, effectsCatalog, effectCaps, options);
    return { name: itemName, score, details, summary, itemValues, ...extraProps };
  }

  // Get candidates for this slot
  if (slotKey === 'pet') {
    const petCandidates = prefilterPetCandidates(entities.pets, targetNames);
    return petCandidates.map(entry => {
      const petEffect = extractPetEffect(entry.item, entry.effectKey);
      return scoreCandidate(petEffect ? [petEffect] : [], entry.item.Name, { effectKey: entry.effectKey });
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, maxResults);
  }

  let candidates;
  if (slotKey === 'armorSet') {
    candidates = prefilterCandidates(entities.armorSets || [], targetNames, true, armorSetPieces);
  } else if (slotKey === 'leftRing') {
    candidates = prefilterCandidates(entities.leftRings || [], targetNames);
  } else if (slotKey === 'rightRing') {
    candidates = prefilterCandidates(entities.rightRings || [], targetNames);
  } else {
    return [];
  }

  return candidates.map(entry => {
    const slotEffects = slotKey === 'armorSet'
      ? extractArmorSetEffects(entry.item, armorSetPieces)
      : extractEquipEffects(entry.item);
    return scoreCandidate(slotEffects, entry.item.Name);
  })
  .sort((a, b) => b.score - a.score)
  .slice(0, maxResults);
}

// ---------------------------------------------------------------------------
// Generic suggestion for any entity list (secondary/clothing slots)
// ---------------------------------------------------------------------------

export function suggestFromList(itemList, targets, otherEffects, effectsCatalog, effectCaps, options = {}) {
  const { maxResults = 20, mode = 'contextual' } = options;
  const targetNames = new Set(Object.keys(targets));
  const candidates = prefilterCandidates(itemList || [], targetNames);
  const baseEffects = mode === 'contextual' ? (otherEffects || []) : [];

  return candidates.map(entry => {
    const slotEffects = extractEquipEffects(entry.item);
    const allEffects = [...baseEffects, ...slotEffects];

    const itemValues = {};
    for (const effectName of Object.keys(targets)) {
      const itemEffect = slotEffects.find(e => e?.Name === effectName);
      itemValues[effectName] = itemEffect ? getEffectStrength(itemEffect) : 0;
    }

    if (mode === 'standalone') {
      let totalPct = 0;
      const pctDetails = [];
      const numTargets = Object.keys(targets).length;
      for (const [effectName, targetValue] of Object.entries(targets)) {
        const itemStrength = itemValues[effectName];
        const pct = targetValue > 0 ? (itemStrength / targetValue) * 100 : 0;
        totalPct += Math.min(pct, 100);
        pctDetails.push({ effectName, targetValue, achieved: itemStrength, pct });
      }
      const avgPct = numTargets > 0 ? totalPct / numTargets : 0;
      return { name: entry.item.Name, score: avgPct, pctDetails, itemValues };
    }

    const { score, details, summary } = scoreCombination(targets, allEffects, effectsCatalog, effectCaps, options);
    return { name: entry.item.Name, score, details, summary, itemValues };
  })
  .sort((a, b) => b.score - a.score)
  .slice(0, maxResults);
}

// ---------------------------------------------------------------------------
// Default set name
// ---------------------------------------------------------------------------

export function buildDefaultSetName(slots) {
  const parts = [];
  if (slots.leftRing) parts.push(slots.leftRing);
  if (slots.rightRing) parts.push(slots.rightRing);
  if (slots.armorSet) parts.push(slots.armorSet);
  if (slots.pet) parts.push(slots.pet);
  return parts.join(' + ') || 'Unnamed Set';
}

// ---------------------------------------------------------------------------
// Get all targetable effects (effects that appear on equipment)
// ---------------------------------------------------------------------------

export function getTargetableEffects(effectsCatalog) {
  return (effectsCatalog || [])
    .filter(e => e?.Properties?.IsPositive === true && e?.Name)
    .sort((a, b) => (a.Name || '').localeCompare(b.Name || ''));
}

// @ts-nocheck
// Core logic for the Effect Optimizer gear advisor tool.
// Handles effect extraction, scoring, suggestion engine (beam search + per-slot).

import { summarizeEffects, buildEffectCaps, getEffectStrength } from '$lib/utils/loadoutEffects.js';

// ---------------------------------------------------------------------------
// Presets
// ---------------------------------------------------------------------------

export const EFFECT_PRESETS = [
  { id: 'max-crit-chance', label: 'Max Crit Chance', targets: { 'Critical Chance Added': 10 } },
  { id: 'max-reload', label: 'Max Reload', targets: { 'Reload Speed Increased': 30 } },
  { id: 'max-lifesteal', label: 'Max Lifesteal', targets: { 'Lifesteal Added': 20 } },
  { id: 'max-run-speed', label: 'Max Run Speed', targets: { 'Run Speed Increased': 50 } },
  { id: 'max-crit-damage', label: 'Max Crit Damage', targets: { 'Critical Damage Added': 350 } },
];

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
  const secondaryKeys = ['weapon', 'amplifier', 'visionAttachment', 'absorber', 'implant'];
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

export function aggregateEffects(itemEffects, effectsCatalog, effectCaps) {
  return summarizeEffects(
    { itemEffects, actionEffects: [], bonusEffects: [] },
    { effectsCatalog, effectCaps }
  );
}

// ---------------------------------------------------------------------------
// Scoring
// ---------------------------------------------------------------------------

export function scoreCombination(targets, itemEffects, effectsCatalog, effectCaps, options = {}) {
  const { overcapMode = 'punish' } = options;
  const summary = aggregateEffects(itemEffects, effectsCatalog, effectCaps);

  let score = 0;
  const details = [];

  for (const [effectName, targetValue] of Object.entries(targets)) {
    const entry = summary.find(e => e.name === effectName);
    const achieved = entry ? Math.abs(entry.signedTotal) : 0;
    const ratio = targetValue > 0 ? achieved / targetValue : 1;
    const diff = achieved - targetValue;

    let effectScore = 0;

    if (Math.abs(diff) < 0.01) {
      // Perfect match
      effectScore = 1000;
    } else if (diff > 0) {
      // Overcapped
      if (overcapMode === 'punish') {
        const weight = OVERCAP_WEIGHTS[effectName] ?? DEFAULT_OVERCAP_WEIGHT;
        effectScore = 500 - (diff / targetValue) * 200 * weight;
      } else {
        // Ignore overcap - treat as perfect
        effectScore = 800;
      }
    } else {
      // Under target - heavier penalty
      effectScore = ratio * 400;
    }

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

export function findBestCombinations(targets, candidatesBySlot, effectsCatalog, effectCaps, options = {}) {
  const { maxResults = 10, beamWidth = 100, topK = 20 } = options;
  const targetNames = new Set(Object.keys(targets));

  // Pre-filter each slot
  const slots = [
    { key: 'leftRing', items: prefilterCandidates(candidatesBySlot.leftRings || [], targetNames).slice(0, topK), isPet: false },
    { key: 'rightRing', items: prefilterCandidates(candidatesBySlot.rightRings || [], targetNames).slice(0, topK), isPet: false },
    { key: 'armorSet', items: prefilterCandidates(candidatesBySlot.armorSets || [], targetNames, true, options.armorSetPieces || 7).slice(0, topK), isPet: false, isArmorSet: true },
    { key: 'pet', items: prefilterPetCandidates(candidatesBySlot.pets || [], targetNames).slice(0, topK), isPet: true },
  ];

  // Include locked items' effects as base
  const lockedEffects = [];
  if (options.lockedSlots) {
    for (const eff of (options.lockedSlots.effects || [])) {
      lockedEffects.push(eff);
    }
  }

  // Beam search
  let beam = [{ items: {}, effects: [...lockedEffects] }];

  for (const slot of slots) {
    if (options.lockedSlots?.[slot.key]) {
      // Skip locked slots - already included in lockedEffects
      continue;
    }

    const nextBeam = [];

    for (const candidate of beam) {
      // Also consider "empty" for this slot
      nextBeam.push({ ...candidate, items: { ...candidate.items } });

      for (const entry of slot.items) {
        let slotEffects;
        const newItems = { ...candidate.items };

        if (slot.isPet) {
          const petEffect = extractPetEffect(entry.item, entry.effectKey);
          slotEffects = petEffect ? [petEffect] : [];
          newItems[slot.key] = { name: entry.item.Name, effectKey: entry.effectKey };
        } else if (slot.isArmorSet) {
          slotEffects = extractArmorSetEffects(entry.item, options.armorSetPieces || 7);
          newItems[slot.key] = entry.item.Name;
        } else {
          slotEffects = extractEquipEffects(entry.item);
          newItems[slot.key] = entry.item.Name;

          // Prevent same ring in both slots
          if (slot.key === 'rightRing' && newItems.leftRing === entry.item.Name) continue;
        }

        const allEffects = [...candidate.effects, ...slotEffects];
        const { score } = scoreCombination(targets, allEffects, effectsCatalog, effectCaps, options);
        nextBeam.push({ items: newItems, effects: allEffects, score });
      }
    }

    // Keep top beamWidth candidates
    nextBeam.sort((a, b) => (b.score || 0) - (a.score || 0));
    beam = nextBeam.slice(0, beamWidth);
  }

  // Score final candidates
  const results = beam.map(candidate => {
    const { score, details, summary } = scoreCombination(targets, candidate.effects, effectsCatalog, effectCaps, options);
    return { ...candidate, score, details, summary };
  });

  results.sort((a, b) => b.score - a.score);

  // Deduplicate by item combination
  const seen = new Set();
  const unique = [];
  for (const r of results) {
    const key = JSON.stringify(r.items);
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(r);
    if (unique.length >= maxResults) break;
  }

  return unique;
}

// ---------------------------------------------------------------------------
// Per-slot suggestion
// ---------------------------------------------------------------------------

export function suggestForSlot(slotKey, targets, currentSlots, entities, effectsCatalog, effectCaps, options = {}) {
  const { maxResults = 5, armorSetPieces = 7 } = options;
  const targetNames = new Set(Object.keys(targets));

  // Collect effects from all slots except the one we're suggesting for
  const otherEffects = [];
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

  // Also include secondary slot effects
  if (currentSlots.secondary) {
    const secondaryKeys = ['weapon', 'amplifier', 'visionAttachment', 'absorber', 'implant'];
    for (const key of secondaryKeys) {
      const name = currentSlots.secondary[key];
      if (name && entities[key]) {
        otherEffects.push(...extractEquipEffects(findByName(entities[key], name)));
      }
    }
  }

  // Get candidates for this slot
  let candidates;
  if (slotKey === 'pet') {
    const petCandidates = prefilterPetCandidates(entities.pets, targetNames);
    return petCandidates.slice(0, maxResults * 3).map(entry => {
      const petEffect = extractPetEffect(entry.item, entry.effectKey);
      const allEffects = [...otherEffects, ...(petEffect ? [petEffect] : [])];
      const { score, details, summary } = scoreCombination(targets, allEffects, effectsCatalog, effectCaps, options);
      return { name: entry.item.Name, effectKey: entry.effectKey, score, details, summary };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, maxResults);
  }

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
    const allEffects = [...otherEffects, ...slotEffects];
    const { score, details, summary } = scoreCombination(targets, allEffects, effectsCatalog, effectCaps, options);
    return { name: entry.item.Name, score, details, summary };
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

// @ts-nocheck
// Utilities for aggregating and capping "effects" across loadout sources (items/actions/bonus).
// This logic is shared by the loadout manager and the share route.

import { clamp } from '$lib/utils/loadoutCalculations.js';

const SUFFIX_RULES = [
  { positive: 'Increased', negative: 'Decreased', type: 'mult' },
  { positive: 'Added', negative: 'Reduced', type: 'add' }
];

const OFFENSIVE_EFFECTS = [
  { key: 'reload', type: 'mult', base: 'Reload Speed', name: 'Reload Speed Increased' },
  { key: 'critChance', type: 'add', base: 'Critical Chance', name: 'Critical Chance Added' },
  { key: 'critDamage', type: 'add', base: 'Critical Damage', name: 'Critical Damage Added' },
  { key: 'damage', type: 'mult', base: 'Damage Done', name: 'Damage Done Increased' }
];

const DEFENSIVE_EFFECT_NAMES = new Set([
  'Health Added',
  'Lifesteal Added',
  'Damage Taken Decreased',
  'Evade Chance Increased',
  'Dodge Chance Increased',
  'Jamming Chance Increased',
  'Critical Damage Taken Decreased',
  'Evade, Dodge & Jamming Increased (Harlequin)'
]);

// Variant effects with parenthetical qualifiers that bypass normal caps
// but contribute to the same offensive stat as their base effect.
const OFFENSIVE_VARIANT_NAMES = new Map([
  ['Critical Damage Added (Harlequin)', 'critDamage']
]);

export function getEffectStrength(effect) {
  const value = effect?.Values?.Strength
    ?? effect?.Values?.Value
    ?? effect?.Properties?.Strength
    ?? effect?.Properties?.Value
    ?? 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function getEffectUnit(effectsCatalog, effectName, currentEffect = null) {
  if (effectName && Array.isArray(effectsCatalog)) {
    const match = effectsCatalog.find(effect => effect?.Name === effectName);
    if (match?.Properties?.Unit) return match.Properties.Unit;
  }
  return currentEffect?.Values?.Unit || currentEffect?.Properties?.Unit || '';
}

function parseCapValue(description, label) {
  if (!description) return null;
  const regex = new RegExp(`${label}\\s*cap\\s*:?\\s*([0-9]+(?:\\.[0-9]+)?)\\s*%?`, 'i');
  const match = description.match(regex);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

function parseCapsFromDescription(description) {
  if (!description) return null;
  const equipment = parseCapValue(description, 'equipment');
  const consumable = parseCapValue(description, 'consumable');
  const total = parseCapValue(description, 'total');
  if (equipment == null && consumable == null && total == null) return null;
  return { equipment, consumable, total };
}

export function buildEffectCaps(list) {
  const caps = {};
  (list || []).forEach(effect => {
    const limits = effect?.Properties?.Limits || effect?.Limits;
    if (limits && (limits.Item != null || limits.Action != null || limits.Total != null)) {
      const normalize = (value) => {
        // Negative/0/null limits mean "no cap" (caller expectation).
        if (value == null) return null;
        const num = Number(value);
        return Number.isFinite(num) && num > 0 ? num : null;
      };
      caps[effect.Name] = {
        item: normalize(limits.Item),
        action: normalize(limits.Action),
        total: normalize(limits.Total)
      };
      return;
    }

    // Back-compat: parse older description-based caps if present.
    const description = effect?.Properties?.Description || effect?.Description || '';
    const parsed = parseCapsFromDescription(description);
    if (parsed) {
      const normalize = (value) => {
        if (value == null) return null;
        const num = Number(value);
        return Number.isFinite(num) && num > 0 ? num : null;
      };
      caps[effect.Name] = {
        item: normalize(parsed.equipment),
        action: normalize(parsed.consumable),
        total: normalize(parsed.total)
      };
    }
  });
  return caps;
}

export function getCatalogPolarity(effectsCatalog, name) {
  if (!name || !Array.isArray(effectsCatalog)) return null;
  const catalog = effectsCatalog.find(effect => effect?.Name === name) || null;
  const isPositive = catalog?.Properties?.IsPositive;
  if (isPositive === true || isPositive === 1 || isPositive === 'true') return 'positive';
  if (isPositive === false || isPositive === 0 || isPositive === 'false') return 'negative';
  return null;
}

function parseSuffix(name) {
  if (!name) return null;
  for (const rule of SUFFIX_RULES) {
    if (name.endsWith(` ${rule.positive}`)) {
      return { type: rule.type, base: name.slice(0, -(rule.positive.length + 1)), direction: 1, rule };
    }
    if (name.endsWith(` ${rule.negative}`)) {
      return { type: rule.type, base: name.slice(0, -(rule.negative.length + 1)), direction: -1, rule };
    }
  }
  return null;
}

export function summarizeEffects({ itemEffects = [], actionEffects = [], bonusEffects = [] }, options = {}) {
  const effectsCatalog = options.effectsCatalog || [];
  const effectCaps = options.effectCaps || {};
  const getLimitsForName = (name) => effectCaps?.[name] || null;

  const summaryMap = new Map();
  const prefixMap = new Map();

  const accumulate = (effect, source) => {
    const name = effect?.Name;
    if (!name) return;
    const value = getEffectStrength(effect);
    if (!Number.isFinite(value)) return;
    const unit = getEffectUnit(effectsCatalog, name, effect) || '';
    const prefix = parseSuffix(name);
    if (prefix) {
      const key = `${prefix.type}::${prefix.base}::${unit}`;
      const current = prefixMap.get(key) || {
        base: prefix.base,
        unit,
        itemPos: 0,
        itemNeg: 0,
        actionPos: 0,
        actionNeg: 0,
        bonusPos: 0,
        bonusNeg: 0,
        rule: prefix.rule
      };
      const posKey = source === 'action' ? 'actionPos' : source === 'bonus' ? 'bonusPos' : 'itemPos';
      const negKey = source === 'action' ? 'actionNeg' : source === 'bonus' ? 'bonusNeg' : 'itemNeg';
      if (prefix.direction > 0) current[posKey] += value;
      else current[negKey] += value;
      prefixMap.set(key, current);
      return;
    }

    const key = `${name}::${unit}`;
    const current = summaryMap.get(key) || { name, unit, item: 0, action: 0, bonus: 0 };
    if (source === 'action') current.action += value;
    else if (source === 'bonus') current.bonus += value;
    else current.item += value;
    summaryMap.set(key, current);
  };

  itemEffects.forEach(effect => accumulate(effect, 'item'));
  actionEffects.forEach(effect => accumulate(effect, 'action'));
  bonusEffects.forEach(effect => accumulate(effect, 'bonus'));

  prefixMap.forEach(entry => {
    // Cancel within each source, cap each source, then combine and apply total cap.
    const rawItem = (entry.itemPos || 0) - (entry.itemNeg || 0);
    const rawAction = (entry.actionPos || 0) - (entry.actionNeg || 0);
    const rawBonus = (entry.bonusPos || 0) - (entry.bonusNeg || 0);

    const basePositiveName = `${entry.base} ${entry.rule.positive}`.trim();
    const baseNegativeName = `${entry.base} ${entry.rule.negative}`.trim();
    const limits = getLimitsForName(basePositiveName) || getLimitsForName(baseNegativeName);

    const cappedItem = limits?.item != null ? clamp(rawItem, -limits.item, limits.item) : rawItem;
    const cappedAction = limits?.action != null ? clamp(rawAction, -limits.action, limits.action) : rawAction;

    // Bonus ignores item/action caps but still contributes to total cap.
    const combined = cappedItem + cappedAction + rawBonus;
    const cappedTotal = limits?.total != null ? clamp(combined, -limits.total, limits.total) : combined;
    if (Math.abs(cappedTotal) <= 0.0001) return;

    const finalName = cappedTotal >= 0 ? basePositiveName : baseNegativeName;
    const polarity = getCatalogPolarity(effectsCatalog, finalName);

    summaryMap.set(`${finalName}::${entry.unit}`, {
      name: finalName,
      unit: entry.unit,
      prefix: { type: entry.rule.type, base: entry.base },
      rawItem,
      rawAction,
      rawBonus,
      cappedItem,
      cappedAction,
      signedTotal: cappedTotal,
      polarity,
      caps: limits || null,
      capped: {
        item: limits?.item != null && Math.abs(rawItem - cappedItem) > 0.0001,
        action: limits?.action != null && Math.abs(rawAction - cappedAction) > 0.0001,
        total: limits?.total != null && Math.abs((cappedItem + cappedAction + rawBonus) - cappedTotal) > 0.0001
      }
    });
  });

  return [...summaryMap.values()]
    .map(entry => {
      if (entry.signedTotal != null) return entry;
      const limits = getLimitsForName(entry.name);
      const rawItem = entry.item;
      const rawAction = entry.action;
      const rawBonus = entry.bonus || 0;
      const cappedItem = limits?.item != null ? clamp(rawItem, -limits.item, limits.item) : rawItem;
      const cappedAction = limits?.action != null ? clamp(rawAction, -limits.action, limits.action) : rawAction;
      const combined = cappedItem + cappedAction + rawBonus;
      const cappedTotal = limits?.total != null ? clamp(combined, -limits.total, limits.total) : combined;
      return {
        name: entry.name,
        unit: entry.unit,
        prefix: parseSuffix(entry.name),
        rawItem,
        rawAction,
        rawBonus,
        cappedItem,
        cappedAction,
        signedTotal: cappedTotal,
        polarity: getCatalogPolarity(effectsCatalog, entry.name),
        caps: limits || null,
        capped: {
          item: limits?.item != null && Math.abs(rawItem - cappedItem) > 0.0001,
          action: limits?.action != null && Math.abs(rawAction - cappedAction) > 0.0001,
          total: limits?.total != null && Math.abs((cappedItem + cappedAction + rawBonus) - cappedTotal) > 0.0001
        }
      };
    })
    .map(entry => {
      const cappedAny = !!(entry?.capped?.item || entry?.capped?.action || entry?.capped?.total);
      if (!cappedAny || !entry?.caps) {
        return { ...entry, cappedAny, capMessage: null };
      }

      const parts = [];
      if (entry.capped.item && entry.caps.item != null) {
        parts.push(`Item cap ${entry.caps.item}${entry.unit}: applied ${entry.cappedItem.toFixed(2)}${entry.unit} from ${entry.rawItem.toFixed(2)}${entry.unit}`);
      }
      if (entry.capped.action && entry.caps.action != null) {
        parts.push(`Action cap ${entry.caps.action}${entry.unit}: applied ${entry.cappedAction.toFixed(2)}${entry.unit} from ${entry.rawAction.toFixed(2)}${entry.unit}`);
      }
      if (entry.capped.total && entry.caps.total != null) {
        const rawCombined = entry.cappedItem + entry.cappedAction + (entry.rawBonus || 0);
        const bonusPart = entry.rawBonus ? ` (includes bonus ${entry.rawBonus.toFixed(2)}${entry.unit})` : '';
        parts.push(`Total cap ${entry.caps.total}${entry.unit}: applied ${entry.signedTotal.toFixed(2)}${entry.unit} from ${rawCombined.toFixed(2)}${entry.unit}${bonusPart}`);
      }

      return {
        ...entry,
        cappedAny,
        capMessage: parts.join(' • ')
      };
    })
    .filter(entry => Math.abs(entry.signedTotal) > 0.0001)
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function getOffensiveTotals(allEffects) {
  const list = Array.isArray(allEffects) ? allEffects : [];
  const totals = {
    damage: (list.find(effect => effect?.prefix?.type === 'mult' && effect?.prefix?.base === 'Damage Done')?.signedTotal) ?? 0,
    reload: (list.find(effect => effect?.prefix?.type === 'mult' && effect?.prefix?.base === 'Reload Speed')?.signedTotal) ?? 0,
    critChance: (list.find(effect => effect?.prefix?.type === 'add' && effect?.prefix?.base === 'Critical Chance')?.signedTotal) ?? 0,
    critDamage: (list.find(effect => effect?.prefix?.type === 'add' && effect?.prefix?.base === 'Critical Damage')?.signedTotal) ?? 0
  };
  for (const effect of list) {
    const key = OFFENSIVE_VARIANT_NAMES.get(effect?.name);
    if (key) totals[key] += effect.signedTotal ?? 0;
  }
  return totals;
}

export function groupEffects(allEffects) {
  const list = Array.isArray(allEffects) ? allEffects : [];
  const offensive = OFFENSIVE_EFFECTS
    .map(def => list.find(effect => effect?.prefix?.type === def.type && effect?.prefix?.base === def.base) || null)
    .filter(Boolean)
    .filter(effect => Math.abs(effect.signedTotal) > 0.0001);
  const offensiveVariants = list
    .filter(effect => OFFENSIVE_VARIANT_NAMES.has(effect?.name))
    .filter(effect => Math.abs(effect.signedTotal) > 0.0001);
  const defensive = list
    .filter(effect => DEFENSIVE_EFFECT_NAMES.has(effect.name))
    .filter(effect => Math.abs(effect.signedTotal) > 0.0001);
  const allOffensive = [...offensive, ...offensiveVariants];
  const offensiveNames = new Set(allOffensive.map(e => e.name));
  const utility = list
    .filter(effect => !offensiveNames.has(effect.name))
    .filter(effect => !effect?.prefix || !OFFENSIVE_EFFECTS.some(def => def.type === effect.prefix.type && def.base === effect.prefix.base))
    .filter(effect => !DEFENSIVE_EFFECT_NAMES.has(effect.name))
    .filter(effect => Math.abs(effect.signedTotal) > 0.0001);

  return { offensive: allOffensive, defensive, utility };
}


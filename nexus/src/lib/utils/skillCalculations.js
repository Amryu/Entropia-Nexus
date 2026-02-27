/**
 * Skill and profession calculation utilities for the Skills tool.
 */

import { REWARD_DIVISORS, getCodexCategory } from './codexUtils.js';

/** Base HP before skill contributions */
export const BASE_HP = 80;

/** Attribute skills are stored as raw values but contribute 100× to calculations */
export const ATTRIBUTE_MULTIPLIER = 100;

/**
 * Build a Set of attribute skill names from skill metadata.
 * @param {Array<{Name: string, Category: string|null}>} skillMetadata
 * @returns {Set<string>}
 */
export function buildAttributeSkillSet(skillMetadata) {
  const set = new Set();
  for (const s of skillMetadata) {
    if (s.Category === 'Attributes') set.add(s.Name);
  }
  return set;
}

/**
 * Get effective skill points, applying the x100 multiplier for attribute skills.
 * @param {number} points - raw skill points
 * @param {string} skillName
 * @param {Set<string>} attributeSkills - set of attribute skill names
 * @returns {number}
 */
export function getEffectivePoints(points, skillName, attributeSkills) {
  return attributeSkills.has(skillName) ? points * ATTRIBUTE_MULTIPLIER : points;
}

/**
 * PLACEHOLDER: Chip-out loss percentage.
 * Chipping out destroys X% of the ESI/skill value.
 * Set to 0 until the real value is known.
 */
export const CHIP_OUT_LOSS_PERCENT = 0;

/**
 * Fetch skill-point → PED conversions from the server.
 * @param {number[]} skillPointsArray
 * @returns {Promise<number[]>}
 */
export async function fetchSkillPEDValues(skillPointsArray) {
  const res = await fetch('/api/tools/skills/values', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ skillPointsToPED: skillPointsArray })
  });
  if (!res.ok) throw new Error(`Skill value API error: ${res.status}`);
  const data = await res.json();
  return data.skillPointsToPED;
}

/**
 * Fetch PED → skill-point conversions from the server.
 * @param {number[]} pedArray
 * @returns {Promise<number[]>}
 */
export async function fetchPEDToSkillPoints(pedArray) {
  const res = await fetch('/api/tools/skills/values', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pedToSkillPoints: pedArray })
  });
  if (!res.ok) throw new Error(`Skill value API error: ${res.status}`);
  const data = await res.json();
  return data.pedToSkillPoints;
}

/**
 * Fetch PED values for all skills at once.
 * Batches all non-zero skill values into a single API call.
 * @param {Object<string, number>} skillValues - { skillName: skillPoints }
 * @returns {Promise<{pedBySkill: Object<string, number>, totalValue: number}>}
 */
export async function fetchAllSkillPEDValues(skillValues) {
  const entries = Object.entries(skillValues).filter(([, v]) => typeof v === 'number' && v > 0);
  if (entries.length === 0) return { pedBySkill: {}, totalValue: 0 };

  const names = entries.map(([name]) => name);
  const points = entries.map(([, v]) => v);
  const pedValues = await fetchSkillPEDValues(points);

  const pedBySkill = {};
  let totalValue = 0;
  for (let i = 0; i < names.length; i++) {
    pedBySkill[names[i]] = pedValues[i];
    totalValue += pedValues[i];
  }

  return { pedBySkill, totalValue };
}

/**
 * Calculate a single profession level from skill values.
 * Formula: Level = Σ(effective_points × weight) / 10000
 * Attribute skills use effective_points = raw_points × 100.
 *
 * @param {Object<string, number>} skillValues - { skillName: skillPoints }
 * @param {Array<{Name: string, Weight: number}>} professionSkills - skills with weights for this profession
 * @param {Set<string>} [attributeSkills] - set of attribute skill names (for x100 multiplier)
 * @returns {number}
 */
export function calculateProfessionLevel(skillValues, professionSkills, attributeSkills = new Set()) {
  let sum = 0;
  for (const { Name, Weight } of professionSkills) {
    const points = skillValues[Name] || 0;
    const effective = getEffectivePoints(points, Name, attributeSkills);
    sum += effective * (Weight || 0);
  }
  return sum / 10000;
}

/**
 * Calculate all profession levels from skill values.
 *
 * @param {Object<string, number>} skillValues - { skillName: skillPoints }
 * @param {Array<{Name: string, Skills: Array<{Name: string, Weight: number}>}>} professions
 * @param {Array<{Name: string, Category: string|null}>} [skillMetadata] - skill metadata for attribute detection
 * @returns {Map<string, number>} profName → level
 */
export function calculateAllProfessionLevels(skillValues, professions, skillMetadata = []) {
  const attributeSkills = buildAttributeSkillSet(skillMetadata);
  const levels = new Map();
  for (const prof of professions) {
    const level = calculateProfessionLevel(skillValues, prof.Skills, attributeSkills);
    levels.set(prof.Name, level);
  }
  return levels;
}

/**
 * Calculate total HP from skill values.
 * Formula: Base HP (80) + Σ(effective_points / HPIncrease) for skills with HPIncrease > 0.
 * Attribute skills use effective_points = raw_points × 100.
 *
 * @param {Object<string, number>} skillValues - { skillName: skillPoints }
 * @param {Array<{Name: string, Category: string|null, HPIncrease: number|null}>} skillMetadata
 * @returns {number}
 */
export function calculateHP(skillValues, skillMetadata) {
  const attributeSkills = buildAttributeSkillSet(skillMetadata);
  let hp = BASE_HP;
  for (const { Name, HPIncrease } of skillMetadata) {
    if (HPIncrease != null && HPIncrease > 0) {
      const points = skillValues[Name] || 0;
      if (points > 0) {
        const effective = getEffectivePoints(points, Name, attributeSkills);
        hp += effective / HPIncrease;
      }
    }
  }
  return hp;
}

/**
 * Calculate the PED cost to chip in a skill (buy an ESI from the market).
 * @param {number} pedNeeded - PED value of the skill implant needed
 * @param {number} markupPercent - markup percentage (e.g., 150 = 150%)
 * @returns {number} total PED cost
 */
export function calculateChipInCost(pedNeeded, markupPercent) {
  return pedNeeded * (markupPercent / 100);
}

/**
 * Calculate the PED received from chipping out (extracting and selling an ESI).
 * Accounts for chip-out loss.
 * @param {number} pedExtracted - PED value of skill extracted
 * @param {number} markupPercent - markup percentage for selling
 * @returns {number} PED received
 */
export function calculateChipOutValue(pedExtracted, markupPercent) {
  const afterLoss = pedExtracted * (1 - CHIP_OUT_LOSS_PERCENT / 100);
  return afterLoss * (markupPercent / 100);
}

/**
 * Calculate the PED cycle cost to gain skill via codex.
 * @param {number} pedOfSkill - PED of skill to gain
 * @param {string} category - codex category ('cat1', 'cat2', 'cat3', 'cat4')
 * @returns {number} PED cycle cost
 */
export function calculateCodexCost(pedOfSkill, category) {
  const divisor = REWARD_DIVISORS[category];
  if (!divisor) return Infinity;
  return pedOfSkill * divisor;
}

/**
 * Find the cheapest path to reach a target profession level.
 *
 * Strategy: For each skill in the target profession, compute the cost-efficiency
 * (profession level gained per PED spent). Greedily allocate to the most efficient
 * skill until the target level is reached.
 *
 * @param {Object<string, number>} currentSkills - current skill values
 * @param {Array<{Name: string, Weight: number}>} professionSkills - skills with weights
 * @param {number} currentLevel - current profession level
 * @param {number} targetLevel - desired profession level
 * @param {Object<string, number>} markups - { skillName: markupPercent } for chip-in
 * @param {Object<string, string>} [methodOverrides={}] - per-skill method override: 'codex' | 'chip' | 'none'
 * @param {Set<string>} [attributeSkills] - set of attribute skill names (for x100 multiplier)
 * @returns {{
 *   totalCost: number,
 *   allocations: Array<{skill: string, currentPoints: number, addedPoints: number, method: string, cost: number, levelGain: number}>,
 *   feasible: boolean
 * }}
 */
export function findCheapestPath(currentSkills, professionSkills, currentLevel, targetLevel, markups, methodOverrides = {}, attributeSkills = new Set()) {
  const levelGap = targetLevel - currentLevel;
  if (levelGap <= 0) {
    return { totalCost: 0, allocations: [], feasible: true };
  }

  // Build per-skill cost info, filtering out 'none' overrides
  const skillOptions = professionSkills
    .filter(({ Name }) => methodOverrides[Name] !== 'none')
    .map(({ Name, Weight }) => {
      const codexCat = getCodexCategory(Name);
      const override = methodOverrides[Name]; // 'codex' | 'chip' | undefined (auto)

      // Cost per PED of skill via codex
      const codexCostPerPed = codexCat ? REWARD_DIVISORS[codexCat] : Infinity;

      // Cost per PED of skill via chip-in (markup)
      const markup = markups[Name] ?? 100;
      const chipCostPerPed = markup / 100; // 100% markup = 1 PED per PED of skill TT

      let cheaperCost, method;
      if (override === 'codex' && codexCat) {
        method = 'codex';
        cheaperCost = codexCostPerPed;
      } else if (override === 'chip') {
        method = 'chip';
        cheaperCost = chipCostPerPed;
      } else {
        // Auto: choose cheaper method
        cheaperCost = Math.min(codexCostPerPed, chipCostPerPed);
        method = codexCostPerPed <= chipCostPerPed ? 'codex' : 'chip';
      }

      // Level gain per raw skill point: (multiplier × weight) / 10000
      const multiplier = attributeSkills.has(Name) ? ATTRIBUTE_MULTIPLIER : 1;
      const levelPerPoint = (multiplier * Weight) / 10000;
      // Efficiency: level gain per PED spent = levelPerPoint / cheaperCost
      const efficiency = cheaperCost > 0 ? levelPerPoint / cheaperCost : 0;

      return {
        skill: Name,
        weight: Weight,
        codexCat,
        codexCostPerPed,
        chipCostPerPed: markup / 100,
        cheaperCost,
        method,
        levelPerPoint,
        efficiency
      };
    });

  // Sort by efficiency (highest first = best value)
  skillOptions.sort((a, b) => b.efficiency - a.efficiency);

  const allocations = [];
  let remainingLevelGap = levelGap;
  let totalCost = 0;

  for (const opt of skillOptions) {
    if (remainingLevelGap <= 0) break;
    if (opt.efficiency <= 0) continue;

    // How many skill points needed to fill the remaining gap via this skill alone
    const pointsNeeded = (remainingLevelGap * 10000) / opt.weight;
    const cost = pointsNeeded * opt.cheaperCost;

    allocations.push({
      skill: opt.skill,
      currentPoints: currentSkills[opt.skill] || 0,
      addedPoints: pointsNeeded,
      method: opt.method,
      codexCategory: opt.codexCat,
      cost,
      levelGain: pointsNeeded * opt.levelPerPoint
    });

    totalCost += cost;
    remainingLevelGap -= pointsNeeded * opt.levelPerPoint;
  }

  return {
    totalCost,
    allocations,
    feasible: remainingLevelGap <= 0.0001
  };
}

/**
 * Find the cheapest path to reach a target HP.
 *
 * Only considers skills with HPIncrease > 0. Greedy allocation by cost-efficiency.
 * HP per skill point = 1 / HPIncrease.
 *
 * @param {Object<string, number>} currentSkills - current skill values
 * @param {Array<{Name: string, HPIncrease: number|null, IsExtractable: boolean}>} skillMetadata
 * @param {number} currentHP - current calculated HP
 * @param {number} targetHP - desired HP
 * @param {Object<string, number>} markups - { skillName: markupPercent }
 * @param {Object<string, string>} [methodOverrides={}] - per-skill method override
 * @returns {{ totalCost: number, allocations: Array, feasible: boolean }}
 */
export function findCheapestHPPath(currentSkills, skillMetadata, currentHP, targetHP, markups, methodOverrides = {}) {
  const attributeSkills = buildAttributeSkillSet(skillMetadata);
  const hpGap = targetHP - currentHP;
  if (hpGap <= 0) {
    return { totalCost: 0, allocations: [], feasible: true };
  }

  const skillOptions = skillMetadata
    .filter(s => s.HPIncrease != null && s.HPIncrease > 0 && methodOverrides[s.Name] !== 'none')
    .map(s => {
      const codexCat = getCodexCategory(s.Name);
      const override = methodOverrides[s.Name];

      const codexCostPerPed = codexCat ? REWARD_DIVISORS[codexCat] : Infinity;
      const markup = markups[s.Name] ?? 100;
      const chipCostPerPed = markup / 100;

      let cheaperCost, method;
      if (override === 'codex' && codexCat) {
        method = 'codex';
        cheaperCost = codexCostPerPed;
      } else if (override === 'chip') {
        method = 'chip';
        cheaperCost = chipCostPerPed;
      } else {
        cheaperCost = Math.min(codexCostPerPed, chipCostPerPed);
        method = codexCostPerPed <= chipCostPerPed ? 'codex' : 'chip';
      }

      // HP per raw skill point: multiplier / HPIncrease
      const multiplier = attributeSkills.has(s.Name) ? ATTRIBUTE_MULTIPLIER : 1;
      const hpPerPoint = multiplier / s.HPIncrease;
      const efficiency = cheaperCost > 0 ? hpPerPoint / cheaperCost : 0;

      return {
        skill: s.Name,
        hpIncrease: s.HPIncrease,
        hpPerPoint,
        codexCat,
        cheaperCost,
        method,
        efficiency
      };
    });

  skillOptions.sort((a, b) => b.efficiency - a.efficiency);

  const allocations = [];
  let remainingHP = hpGap;
  let totalCost = 0;

  for (const opt of skillOptions) {
    if (remainingHP <= 0) break;
    if (opt.efficiency <= 0) continue;

    // points needed: HP * HPIncrease (inverse of hpPerPoint)
    const pointsNeeded = remainingHP * opt.hpIncrease;
    const cost = pointsNeeded * opt.cheaperCost;

    allocations.push({
      skill: opt.skill,
      currentPoints: currentSkills[opt.skill] || 0,
      addedPoints: pointsNeeded,
      method: opt.method,
      codexCategory: opt.codexCat,
      cost,
      hpGain: pointsNeeded * opt.hpPerPoint
    });

    totalCost += cost;
    remainingHP -= pointsNeeded * opt.hpPerPoint;
  }

  return {
    totalCost,
    allocations,
    feasible: remainingHP <= 0.0001
  };
}


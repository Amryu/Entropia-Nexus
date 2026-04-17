/**
 * Shared Codex constants and calculation utilities.
 * Extracted from MobCodex.svelte for reuse in the Skills tool optimizer.
 */

/** Rank multipliers for codex ranks 1-25 */
export const CODEX_MULTIPLIERS = [
  1, 2, 3, 4, 6,
  8, 10, 12, 14, 16,
  18, 20, 24, 28, 32,
  36, 40, 44, 48, 56,
  64, 72, 80, 90, 100
];

/** Skill category reward divisors: PED cycle cost per PED of skill gained */
export const REWARD_DIVISORS = { cat1: 200, cat2: 320, cat3: 640, cat4: 1000 };

export const FISH_CODEX_DIVISOR = 320;

/**
 * Fish codex skills with per-skill reward multipliers.
 * Every rank offers the same skills; multiplier scales the base reward.
 */
export const FISH_CODEX_SKILLS = [
  { name: 'Fishing', multiplier: 1.0 },
  { name: 'Casting', multiplier: 1.6 },
  { name: 'Angling', multiplier: 1.6 },
  { name: 'Fly Fishing', multiplier: 1.6 },
  { name: 'Deep Ocean Fishing', multiplier: 1.6 }
];

/**
 * Bonus skills available on fish codex ranks where rank % 5 === 2 (ranks 2, 7, 12, 17, 22).
 * These are additional skills on top of the base fishing skills, all at 1x multiplier.
 */
export const FISH_CODEX_BONUS_SKILLS = [
  { name: 'Fishing Rod Technology', multiplier: 1.0 },
  { name: 'Fishing Attachment Technology', multiplier: 1.0 },
  { name: 'Gutting', multiplier: 1.0 },
  { name: 'Anatomy', multiplier: 1.0 }
];

export function isFishBonusRank(rank) {
  return rank % 5 === 2;
}

/**
 * Codex skill categories — determines which skills are available at which ranks.
 * These are specific to the codex game mechanic and don't map to DB skill categories.
 */
export const CODEX_SKILL_CATEGORIES = {
  cat1: [
    'Aim', 'Anatomy', 'Athletics', 'BLP Weaponry Technology', 'Combat Reflexes',
    'Dexterity', 'Handgun', 'Heavy Melee Weapons', 'Laser Weaponry Technology',
    'Light Melee Weapons', 'Longblades', 'Power Fist', 'Rifle', 'Shortblades', 'Weapons Handling'
  ],
  cat2: [
    'Clubs', 'Courage', 'Cryogenics', 'Diagnosis', 'Electrokinesis',
    'Inflict Melee Damage', 'Inflict Ranged Damage', 'Melee Combat',
    'Perception', 'Plasma Weaponry Technology', 'Pyrokinesis'
  ],
  cat3: [
    'Alertness', 'Bioregenesis', 'Bravado', 'Concentration', 'Dodge',
    'Evade', 'First Aid', 'Telepathy', 'Translocation', 'Vehicle Repairing'
  ],
  cat4: [
    'Analysis', 'Animal Lore', 'Biology', 'Botany', 'Computer',
    'Explosive Projectile Weaponry Technology', 'Heavy Weapons',
    'Support Weapon Systems', 'Zoology'
  ],
  asteroid: [
    'Mining Laser Technology', 'Mining Laser Operator', 'Prospecting',
    'Surveying', 'Analysis', 'Fragmentating', 'Perception', 'Geology'
  ]
};

/** Reverse lookup: skill name → codex category */
const _skillToCategoryCache = new Map();
function _buildSkillToCategoryMap() {
  if (_skillToCategoryCache.size > 0) return _skillToCategoryCache;
  for (const [category, skills] of Object.entries(CODEX_SKILL_CATEGORIES)) {
    for (const skill of skills) {
      // A skill can appear in multiple categories (e.g. Analysis in cat4 + asteroid)
      // Store the primary (non-asteroid) category; asteroid is a separate codex type
      if (category !== 'asteroid' || !_skillToCategoryCache.has(skill)) {
        _skillToCategoryCache.set(skill, category);
      }
    }
  }
  return _skillToCategoryCache;
}

/**
 * Get the codex category for a skill name.
 * @param {string} skillName
 * @returns {string|null} 'cat1', 'cat2', 'cat3', 'cat4', or null if not a codex skill
 */
export function getCodexCategory(skillName) {
  const map = _buildSkillToCategoryMap();
  return map.get(skillName) || null;
}

/**
 * Determine which codex category a rank belongs to.
 * Ranks cycle: 1,2 → cat1; 3,4 → cat2; 5 → cat3; repeat.
 * @param {number} rank - 1-based rank number
 * @returns {'cat1'|'cat2'|'cat3'}
 */
export function getCategoryForRank(rank) {
  const mod = rank % 5;
  if (mod === 1 || mod === 2) return 'cat1';
  if (mod === 3 || mod === 4) return 'cat2';
  return 'cat3';
}

/**
 * Calculate cumulative cost up to a rank (inclusive).
 * @param {number} upToRank - 0-based rank index
 * @param {number} baseCost - base PED cost per rank 1
 * @returns {number}
 */
export function getCumulativeCost(upToRank, baseCost) {
  let total = 0;
  for (let i = 0; i <= upToRank; i++) {
    total += CODEX_MULTIPLIERS[i] * baseCost;
  }
  return total;
}

/**
 * Calculate cumulative skill gain for a category up to selected rank.
 * @param {string} category - 'cat1', 'cat2', or 'cat3'
 * @param {number} upToRank - 0-based rank index
 * @param {number} baseCost - base PED cost per rank 1
 * @returns {number}
 */
export function calcCumulativeSkillGain(category, upToRank, baseCost) {
  if (!baseCost) return 0;
  let total = 0;
  const divisor = REWARD_DIVISORS[category];
  if (!divisor) return 0;
  for (let i = 0; i <= upToRank; i++) {
    const rankCategory = getCategoryForRank(i + 1);
    if (rankCategory === category) {
      total += (CODEX_MULTIPLIERS[i] * baseCost) / divisor;
    }
  }
  return total;
}

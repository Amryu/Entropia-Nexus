<!--
  @component MobCodex
  Interactive codex calculator for mob hunting.
  Shows rank costs and skill rewards.
-->
<script>
  // @ts-nocheck
  import { getTypeLink } from '$lib/util';
  import {
    CODEX_MULTIPLIERS,
    REWARD_DIVISORS,
    CODEX_SKILL_CATEGORIES,
    FISH_CODEX_SKILLS,
    FISH_CODEX_BONUS_SKILLS,
    FISH_CODEX_DIVISOR,
    getCategoryForRank,
    getCumulativeCost,
    calcCumulativeSkillGain,
    isFishBonusRank
  } from '$lib/utils/codexUtils';

  /**
   * @typedef {Object} Props
   * @property {any} [baseCost]
   * @property {any} [codexType]
   * @property {string} [mobType] - Animal, Mutant, Robot - to determine which looter profession to check
   * @property {any} [skills] - Skills data from API
   */

  /** @type {Props} */
  let {
    baseCost = null,
    codexType = null,
    mobType = 'Animal',
    skills = []
  } = $props();

  // Build skill lookup from API data
  let skillLookup = $derived(skills.reduce((acc, skill) => {
    acc[skill.Name] = skill;
    return acc;
  }, {}));

  // Get looter profession name based on mob type
  let looterProfession = $derived(mobType === 'Animal' ? 'Animal Looter'
    : mobType === 'Mutant' ? 'Mutant Looter'
    : mobType === 'Robot' ? 'Robot Looter'
    : null);

  // Codex skill categories are a specific game mechanic that doesn't map directly
  // to database skill categories, so we use the hardcoded lists.
  // The skills API data is used for skill metadata (HP increase, profession weights).
  const SKILLS = CODEX_SKILL_CATEGORIES;

  const LOOTER_PROFESSIONS = ['Animal Looter', 'Mutant Looter', 'Robot Looter'];

  // Defense professions to check
  const DEFENSE_PROFESSIONS = ['Evader', 'Dodger', 'Jammer'];

  function formatWeight(weight) {
    const num = Number(weight);
    if (!Number.isFinite(num)) return String(weight);
    return num.toFixed(3).replace(/\.?0+$/, '');
  }

  function stripSuffix(value, suffix) {
    if (typeof value !== 'string') return value;
    return value.endsWith(suffix) ? value.slice(0, -suffix.length) : value;
  }

  function formatWeightedLooterProfessions(contributions) {
    const suffix = ' Looter';
    const byProfession = new Map((contributions || []).map(c => [c.profession, c]));
    const ordered = LOOTER_PROFESSIONS.map(p => byProfession.get(p)).filter(Boolean);
    if (!ordered.length) return '—';

    const parts = ordered.map(({ profession, weight }) => `${formatWeight(weight)} ${stripSuffix(profession, suffix)}`);
    if (parts.length === 1) return `${parts[0]}${suffix}`;
    return `${parts.join(' / ')}${suffix}`;
  }

  function formatWeightedDefenseProfessions(contributions) {
    const byProfession = new Map((contributions || []).map(c => [c.profession, c]));
    const ordered = DEFENSE_PROFESSIONS.map(p => byProfession.get(p)).filter(Boolean);
    if (!ordered.length) return '—';
    return ordered.map(({ profession, weight }) => `${formatWeight(weight)} ${profession}`).join(' / ');
  }

  function getBadgeTitle(badge) {
    if (!badge) return '';

    if (badge.type === 'hp') {
      const base = `HP per skill: ${badge.value}`;
      return badge.level === 'ineffective' ? `${base} (less effective)` : base;
    }

    if (badge.type === 'loot') {
      return `Looter contribution: ${formatWeightedLooterProfessions(badge.contributions)}`;
    }

    if (badge.type === 'defense') {
      return `Defense contribution: ${formatWeightedDefenseProfessions(badge.contributions)}`;
    }

    return '';
  }

  function getSkillBadges(skillName) {
    const skill = skillLookup[skillName];
    const badges = [];

    // Check HP contribution
    // Skills with HP increase <= 800 are considered effective
    // Skills with HP increase > 800 still give HP but are less effective
    const hpIncrease = skill?.Properties?.HpIncrease || 0;
    if (hpIncrease > 0) {
      if (hpIncrease <= 800) {
        // Effective HP skills - tiered by contribution amount
        if (hpIncrease >= 500) badges.push({ label: 'HP', level: 'high', value: hpIncrease, type: 'hp' });
        else if (hpIncrease >= 200) badges.push({ label: 'HP', level: 'medium', value: hpIncrease, type: 'hp' });
        else badges.push({ label: 'HP', level: 'low', value: hpIncrease, type: 'hp' });
      } else {
        // Less effective HP skills (>800) - show muted badge
        badges.push({ label: 'HP', level: 'ineffective', value: hpIncrease, type: 'hp' });
      }
    }

    // Check looter profession contribution (show for any looter profession, not just current mob type)
    if (skill?.Professions) {
      const looterContributions = LOOTER_PROFESSIONS
        .map(profession => {
          const contrib = skill.Professions.find(p => p.Profession?.Name === profession);
          return contrib?.Weight != null ? { profession, weight: contrib.Weight } : null;
        })
        .filter(Boolean)
        .filter(c => c.weight > 0);

      if (looterContributions.length > 0) {
        // Use current mob's looter weight for badge level, fall back to max across all
        const current = looterProfession ? looterContributions.find(c => c.profession === looterProfession) : null;
        const weight = current?.weight ?? Math.max(...looterContributions.map(c => c.weight));
        if (weight >= 0.8) badges.push({ label: 'Loot', level: 'high', value: weight, type: 'loot', contributions: looterContributions });
        else if (weight >= 0.4) badges.push({ label: 'Loot', level: 'medium', value: weight, type: 'loot', contributions: looterContributions });
        else badges.push({ label: 'Loot', level: 'low', value: weight, type: 'loot', contributions: looterContributions });
      }
    }

    // Check defense profession contribution (Evader/Dodger/Jammer)
    if (skill?.Professions) {
      const defenseContributions = DEFENSE_PROFESSIONS
        .map(profession => {
          const contrib = skill.Professions.find(p => p.Profession?.Name === profession);
          return contrib?.Weight != null ? { profession, weight: contrib.Weight } : null;
        })
        .filter(Boolean)
        .filter(c => c.weight > 0);

      if (defenseContributions.length > 0) {
        let maxDefenseWeight = 0;
        let defenseProf = null;
        for (const { profession, weight } of defenseContributions) {
          if (weight > maxDefenseWeight) {
            maxDefenseWeight = weight;
            defenseProf = profession;
          }
        }

        const shortLabel = defenseProf === 'Evader' ? 'Eva' : defenseProf === 'Dodger' ? 'Dod' : 'Jam';
        if (maxDefenseWeight >= 0.8) badges.push({ label: shortLabel, level: 'high', value: maxDefenseWeight, type: 'defense', contributions: defenseContributions });
        else if (maxDefenseWeight >= 0.4) badges.push({ label: shortLabel, level: 'medium', value: maxDefenseWeight, type: 'defense', contributions: defenseContributions });
        else badges.push({ label: shortLabel, level: 'low', value: maxDefenseWeight, type: 'defense', contributions: defenseContributions });
      }
    }

    return badges;
  }


  let isFishCodex = $derived(codexType === 'Fish');

  let selectedRank = $state(0);
  let showCumulative = $state(false);

  let category = $derived(isFishCodex ? 'fish' : getCategoryForRank(selectedRank + 1));
  let skillsForRank = $derived(
    isFishCodex ? FISH_CODEX_SKILLS.map(s => s.name)
    : codexType === 'Asteroid' ? SKILLS.asteroid
    : SKILLS[category]
  );
  let rewardDivisor = $derived(isFishCodex ? FISH_CODEX_DIVISOR : REWARD_DIVISORS[category]);
  let isCat4Rank = $derived(codexType === 'MobLooter' && (selectedRank + 1) % 10 === 5);
  let isFishBonus = $derived(isFishCodex && isFishBonusRank(selectedRank + 1));
  let costForRank = $derived(baseCost ? CODEX_MULTIPLIERS[selectedRank] * baseCost : null);
  let cumulativeCost = $derived(baseCost ? getCumulativeCost(selectedRank, baseCost) : null);
  let displayCost = $derived(showCumulative ? cumulativeCost : costForRank);
  let rewardValue = $derived(costForRank ? (costForRank / rewardDivisor).toFixed(4) : 'N/A');
  let cat4RewardValue = $derived(costForRank ? (costForRank / REWARD_DIVISORS.cat4).toFixed(4) : 'N/A');

  let fishMultiplierBySkill = $derived.by(() => {
    const map = {};
    for (const s of FISH_CODEX_SKILLS) map[s.name] = s.multiplier;
    return map;
  });

  let fishBonusMultiplierBySkill = $derived.by(() => {
    const map = {};
    for (const s of FISH_CODEX_BONUS_SKILLS) map[s.name] = s.multiplier;
    return map;
  });

  function getFishRewardValue(skillName) {
    if (!costForRank) return 'N/A';
    const mult = fishMultiplierBySkill[skillName] ?? 1;
    return (costForRank / rewardDivisor * mult).toFixed(4);
  }

  function getFishBonusRewardValue(skillName) {
    if (!costForRank) return 'N/A';
    const mult = fishBonusMultiplierBySkill[skillName] ?? 1;
    return (costForRank / rewardDivisor * mult).toFixed(4);
  }

  // Reactive cumulative skill gains - these update when selectedRank changes
  let cumulativeCat1 = $derived(calcCumulativeSkillGain('cat1', selectedRank, baseCost).toFixed(4));
  let cumulativeCat2 = $derived(calcCumulativeSkillGain('cat2', selectedRank, baseCost).toFixed(4));
  let cumulativeCat3 = $derived(calcCumulativeSkillGain('cat3', selectedRank, baseCost).toFixed(4));
</script>

<div class="codex-calculator">
  {#if baseCost == null}
    <div class="no-data">No codex data available for this mob.</div>
  {:else}
    <div class="calculator-layout">
      <!-- Rank Selection Grid -->
      <div class="rank-section">
        <div class="section-header">Select Rank</div>
        <div class="rank-grid">
          {#each Array(5) as _, row}
            <div class="rank-row">
              {#each CODEX_MULTIPLIERS.slice(row * 5, row * 5 + 5) as multiplier, col}
                {@const rankIndex = row * 5 + col}
                {@const isSelected = selectedRank === rankIndex}
                {@const rankCategory = isFishCodex ? 'fish' : getCategoryForRank(rankIndex + 1)}
                {@const isCat4 = codexType === 'MobLooter' && (rankIndex + 1) % 10 === 5}
                {@const isFishBonusBtn = isFishCodex && isFishBonusRank(rankIndex + 1)}
                {@const displayValue = showCumulative ? getCumulativeCost(rankIndex, baseCost) : multiplier * baseCost}
                <button
                  class="rank-btn cat-{rankCategory}"
                  class:selected={isSelected}
                  class:cat4-bonus={isCat4}
                  class:fish-bonus={isFishBonusBtn}
                  onclick={() => selectedRank = rankIndex}
                  title="Rank {rankIndex + 1}: {displayValue} PED"
                >
                  <span class="rank-number">{rankIndex + 1}</span>
                  <span class="rank-cost">{displayValue}</span>
                  <span class="rank-unit">PED</span>
                </button>
              {/each}
            </div>
          {/each}
        </div>

        <!-- View Mode Toggle -->
        <div class="view-toggle">
          <button
            class="toggle-btn"
            class:active={!showCumulative}
            onclick={() => showCumulative = false}
          >
            Per Rank
          </button>
          <button
            class="toggle-btn"
            class:active={showCumulative}
            onclick={() => showCumulative = true}
          >
            Cumulative
          </button>
        </div>

        <!-- Legend -->
        {#if !isFishCodex}
          <div class="legend">
            <div class="legend-item">
              <span class="legend-swatch cat-cat1"></span>
              <span>Cat 1</span>
            </div>
            <div class="legend-item">
              <span class="legend-swatch cat-cat2"></span>
              <span>Cat 2</span>
            </div>
            <div class="legend-item">
              <span class="legend-swatch cat-cat3"></span>
              <span>Cat 3</span>
            </div>
            {#if codexType === 'MobLooter'}
              <div class="legend-item">
                <span class="legend-swatch cat4-bonus"></span>
                <span>+Cat 4</span>
              </div>
            {/if}
          </div>
        {:else}
          <div class="legend">
            <div class="legend-item">
              <span class="legend-swatch cat-fish"></span>
              <span>Fishing</span>
            </div>
            <div class="legend-item">
              <span class="legend-swatch fish-bonus"></span>
              <span>+Bonus</span>
            </div>
          </div>
        {/if}
      </div>

      <!-- Rewards Panel -->
      <div class="rewards-panel">
        <div class="rewards-header">
          <div class="rewards-title">
            <span class="rank-label">Rank {selectedRank + 1}</span>
            {#if isFishCodex}
              <span class="category-badge cat-fish">Fishing</span>
            {:else}
              <span class="category-badge cat-{category}">Category {category.slice(-1)}</span>
            {/if}
          </div>
          <div class="cost-display">
            <span class="cost-label">{showCumulative ? 'Total' : 'Cost'}</span>
            <span class="cost-value">{displayCost}</span>
            <span class="cost-unit">PED</span>
          </div>
        </div>

        <div class="skills-section">
          <div class="skills-header">
            <span class="header-skill">Choose One Skill</span>
            <span class="header-contrib">Contrib.</span>
            <span class="header-gain">Gain (PED)</span>
          </div>

          <div class="skills-list">
            {#each skillsForRank as skill}
              {@const badges = getSkillBadges(skill)}
              {@const fishMult = isFishCodex ? fishMultiplierBySkill[skill] : null}
              <div class="skill-row" class:has-badge={badges.length > 0}>
                <a href={getTypeLink(skill, 'Skill')} class="skill-name skill-link">{skill}</a>
                <span class="skill-badges">
                  {#if fishMult != null}
                    <span class="skill-badge fish-mult" title="{fishMult}x reward multiplier">{fishMult}x</span>
                  {/if}
                  {#each badges as badge}
                    <span
                      class="skill-badge {badge.level} {badge.type}"
                      title={getBadgeTitle(badge)}
                    >{badge.label}</span>
                  {/each}
                </span>
                <span class="skill-value">{isFishCodex ? getFishRewardValue(skill) : rewardValue}</span>
              </div>
            {/each}
          </div>
        </div>

        {#if isCat4Rank}
          <div class="cat4-section">
            <div class="cat4-header">
              <span>Category 4 Bonus (Choose One)</span>
              <span class="cat4-badge">Bonus</span>
            </div>
            <div class="skills-list cat4">
              {#each SKILLS.cat4 as skill}
                {@const badges = getSkillBadges(skill)}
                <div class="skill-row" class:has-badge={badges.length > 0}>
                  <a href={getTypeLink(skill, 'Skill')} class="skill-name skill-link">{skill}</a>
                  <span class="skill-badges">
                    {#each badges as badge}
                      <span
                        class="skill-badge {badge.level} {badge.type}"
                        title={getBadgeTitle(badge)}
                      >{badge.label}</span>
                    {/each}
                  </span>
                  <span class="skill-value">{cat4RewardValue}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if isFishBonus}
          <div class="fish-bonus-section">
            <div class="fish-bonus-header">
              <span>Bonus Skills (Choose One)</span>
              <span class="fish-bonus-badge">Bonus</span>
            </div>
            <div class="skills-list fish-bonus">
              {#each FISH_CODEX_BONUS_SKILLS as bonusSkill}
                {@const badges = getSkillBadges(bonusSkill.name)}
                <div class="skill-row" class:has-badge={badges.length > 0}>
                  <a href={getTypeLink(bonusSkill.name, 'Skill')} class="skill-name skill-link">{bonusSkill.name}</a>
                  <span class="skill-badges">
                    <span class="skill-badge fish-mult" title="{bonusSkill.multiplier}x reward multiplier">{bonusSkill.multiplier}x</span>
                    {#each badges as badge}
                      <span
                        class="skill-badge {badge.level} {badge.type}"
                        title={getBadgeTitle(badge)}
                      >{badge.label}</span>
                    {/each}
                  </span>
                  <span class="skill-value">{getFishBonusRewardValue(bonusSkill.name)}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Cumulative Summary by Category -->
        <div class="cumulative-summary">
          <div class="summary-title">Cumulative Skill Gain (Ranks 1-{selectedRank + 1})</div>
          {#if isFishCodex}
            <div class="summary-grid fish-summary">
              {#each FISH_CODEX_SKILLS as fs}
                {@const cumGain = baseCost ? Array.from({ length: selectedRank + 1 }, (_, i) => CODEX_MULTIPLIERS[i] * baseCost / FISH_CODEX_DIVISOR * fs.multiplier).reduce((a, b) => a + b, 0).toFixed(4) : '0'}
                <div class="summary-item cat-fish">
                  <span class="summary-label">{fs.name} ({fs.multiplier}x)</span>
                  <span class="summary-value">{cumGain} PED</span>
                </div>
              {/each}
              {#each FISH_CODEX_BONUS_SKILLS as bs}
                {@const bonusCumGain = baseCost ? Array.from({ length: selectedRank + 1 }, (_, i) => isFishBonusRank(i + 1) ? CODEX_MULTIPLIERS[i] * baseCost / FISH_CODEX_DIVISOR * bs.multiplier : 0).reduce((a, b) => a + b, 0).toFixed(4) : '0'}
                <div class="summary-item cat-fish-bonus">
                  <span class="summary-label">{bs.name} ({bs.multiplier}x)</span>
                  <span class="summary-value">{bonusCumGain} PED</span>
                </div>
              {/each}
            </div>
          {:else}
            <div class="summary-grid">
              <div class="summary-item cat-cat1">
                <span class="summary-label">Cat 1</span>
                <span class="summary-value">{cumulativeCat1} PED</span>
              </div>
              <div class="summary-item cat-cat2">
                <span class="summary-label">Cat 2</span>
                <span class="summary-value">{cumulativeCat2} PED</span>
              </div>
              <div class="summary-item cat-cat3">
                <span class="summary-label">Cat 3</span>
                <span class="summary-value">{cumulativeCat3} PED</span>
              </div>
            </div>
          {/if}
        </div>
      </div>
    </div>

    <div class="codex-footer">
      <span class="codex-type">
        Codex Type: <strong>{codexType || 'Mob'}</strong>
      </span>
      {#if codexType === 'MobLooter'}
        <span class="cat4-note">Category 4 bonus available on ranks 5, 15, 25</span>
      {/if}
      {#if isFishCodex}
        <span class="cat4-note">Bonus skills on ranks 2, 7, 12, 17, 22</span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .codex-calculator {
    width: 100%;
    container-type: inline-size;
  }

  .calculator-layout {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 20px;
    align-items: start;
  }

  /* Rank Selection Section */
  .rank-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .section-header {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--text-muted);
    letter-spacing: 0.5px;
  }

  .rank-grid {
    display: flex;
    flex-direction: column;
    gap: 3px;
    background: var(--border-color);
    padding: 3px;
    border-radius: 8px;
  }

  .rank-row {
    display: flex;
    gap: 3px;
  }

  .rank-btn {
    width: 72px;
    height: 60px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1px;
    border: 2px solid transparent;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s ease;
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  /* Category colors using theme-aware colors */
  .rank-btn.cat-cat1 {
    background-color: var(--cat1-bg, rgba(100, 149, 237, 0.3));
  }

  .rank-btn.cat-cat2 {
    background-color: var(--cat2-bg, rgba(147, 112, 219, 0.3));
  }

  .rank-btn.cat-cat3 {
    background-color: var(--cat3-bg, rgba(60, 179, 113, 0.3));
  }

  .rank-btn.cat-fish {
    background-color: var(--cat-fish-bg, rgba(56, 189, 248, 0.25));
  }

  .rank-btn.cat4-bonus {
    position: relative;
    box-shadow: inset 0 0 0 2px var(--warning-color);
  }

  .rank-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .rank-btn.selected {
    border-color: var(--accent-color);
    background-color: var(--accent-color);
    color: white;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  }

  .rank-btn.selected .rank-number,
  .rank-btn.selected .rank-cost,
  .rank-btn.selected .rank-unit {
    color: white;
  }

  .rank-number {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
  }

  .rank-cost {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-color);
    line-height: 1;
  }

  .rank-unit {
    font-size: 9px;
    font-weight: 500;
    color: var(--text-muted);
  }

  /* View Mode Toggle */
  .view-toggle {
    display: flex;
    gap: 2px;
    background: var(--border-color);
    padding: 2px;
    border-radius: 6px;
  }

  .toggle-btn {
    flex: 1;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    background: transparent;
    color: var(--text-muted);
    transition: all 0.15s ease;
  }

  .toggle-btn:hover {
    color: var(--text-color);
  }

  .toggle-btn.active {
    background: var(--accent-color);
    color: white;
  }

  /* Legend */
  .legend {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-muted);
  }

  .legend-swatch {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid var(--border-color);
  }

  .legend-swatch.cat-cat1 {
    background-color: var(--cat1-bg, rgba(100, 149, 237, 0.3));
  }

  .legend-swatch.cat-cat2 {
    background-color: var(--cat2-bg, rgba(147, 112, 219, 0.3));
  }

  .legend-swatch.cat-cat3 {
    background-color: var(--cat3-bg, rgba(60, 179, 113, 0.3));
  }

  .legend-swatch.cat4-bonus {
    background-color: var(--hover-color);
    box-shadow: inset 0 0 0 2px var(--warning-color);
  }

  /* Rewards Panel - No fixed height, grows to fit content */
  .rewards-panel {
    min-width: 320px;
    display: flex;
    flex-direction: column;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .rewards-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 16px;
    background: var(--hover-color);
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .rewards-title {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .rank-label {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-color);
  }

  .category-badge {
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
    text-transform: uppercase;
  }

  .category-badge.cat-cat1 {
    background-color: var(--cat1-bg, rgba(100, 149, 237, 0.3));
    color: var(--text-color);
  }

  .category-badge.cat-cat2 {
    background-color: var(--cat2-bg, rgba(147, 112, 219, 0.3));
    color: var(--text-color);
  }

  .category-badge.cat-cat3 {
    background-color: var(--cat3-bg, rgba(60, 179, 113, 0.3));
    color: var(--text-color);
  }

  .category-badge.cat-fish {
    background-color: var(--cat-fish-bg, rgba(56, 189, 248, 0.25));
    color: var(--text-color);
  }

  .cost-display {
    text-align: right;
  }

  .cost-label {
    display: block;
    font-size: 10px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .cost-value {
    font-size: 22px;
    font-weight: 700;
    color: var(--accent-color);
  }

  .cost-unit {
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted);
    margin-left: 2px;
  }

  /* Skills Section */
  .skills-section {
    flex: 1;
    padding: 12px 16px;
    min-height: 0;
  }

  .skills-header {
    display: grid;
    grid-template-columns: 1fr 60px 80px;
    gap: 8px;
    font-weight: 600;
    color: var(--text-muted);
    font-size: 10px;
    text-transform: uppercase;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 6px;
  }

  .header-skill {
    text-align: left;
  }

  .header-contrib {
    text-align: center;
  }

  .header-gain {
    text-align: right;
  }

  .skills-list {
    display: flex;
    flex-direction: column;
  }

  .skill-row {
    display: grid;
    grid-template-columns: 1fr 60px 80px;
    gap: 8px;
    align-items: center;
    padding: 4px 0;
    border-bottom: 1px solid var(--border-color);
  }

  .skill-row:last-child {
    border-bottom: none;
  }

  .skill-row.has-badge {
    background-color: rgba(74, 222, 128, 0.05);
  }

  .skill-name {
    font-size: 12px;
    color: var(--text-color);
  }

  .skill-name.skill-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
    transition: color 0.15s;
  }

  .skill-name.skill-link:hover {
    text-decoration: underline;
    color: var(--accent-color-hover, #3a8eef);
  }

  .skill-badges {
    display: flex;
    gap: 4px;
    justify-content: center;
  }

  .skill-badge {
    font-size: 9px;
    font-weight: 600;
    padding: 2px 5px;
    border-radius: 3px;
    text-transform: uppercase;
  }

  .skill-badge.fish-mult {
    background-color: var(--cat-fish-bg, rgba(56, 189, 248, 0.25));
    color: var(--text-color);
  }

  /* HP badges - darker green for better readability */
  .skill-badge.hp.high {
    background-color: var(--success-color);
    color: white;
  }

  .skill-badge.hp.medium {
    background-color: var(--success-color);
    color: white;
  }

  .skill-badge.hp.low {
    background-color: rgba(22, 163, 74, 0.2);
    color: var(--success-color);
    border: 1px solid var(--success-color);
  }

  .skill-badge.hp.ineffective {
    background-color: rgba(22, 163, 74, 0.2);
    color: var(--success-color);
    border: 1px solid var(--success-color);
  }

  /* Loot badges - gold/yellow */
  .skill-badge.loot.high {
    background-color: var(--warning-color);
    color: #000;
  }

  .skill-badge.loot.medium {
    background-color: var(--warning-bg);
    color: var(--warning-color);
    border: 1px solid var(--warning-color);
  }

  .skill-badge.loot.low {
    background-color: transparent;
    color: var(--warning-color);
    border: 1px solid var(--warning-color);
    opacity: 0.7;
  }

  /* Defense badges - blue */
  .skill-badge.defense.high {
    background-color: var(--accent-color);
    color: white;
  }

  .skill-badge.defense.medium {
    background-color: rgba(74, 158, 255, 0.15);
    color: var(--accent-color);
    border: 1px solid var(--accent-color);
  }

  .skill-badge.defense.low {
    background-color: transparent;
    color: var(--accent-color);
    border: 1px solid var(--accent-color);
    opacity: 0.7;
  }

  .skill-value {
    font-size: 12px;
    font-weight: 600;
    color: var(--accent-color);
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  /* Cat 4 Section */
  .cat4-section {
    border-top: 1px solid var(--border-color);
    padding: 12px 16px;
    background: var(--warning-bg);
    flex-shrink: 0;
  }

  .cat4-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-weight: 600;
    font-size: 12px;
    color: var(--warning-color);
  }

  .cat4-badge {
    font-size: 9px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--warning-color);
    color: white;
    text-transform: uppercase;
  }

  .skills-list.cat4 .skill-row {
    border-color: rgba(0, 0, 0, 0.1);
    padding: 4px 0;
  }

  .skills-list.cat4 .skill-value {
    color: var(--warning-color);
  }

  /* Fish Bonus Section */
  .rank-btn.fish-bonus {
    position: relative;
    box-shadow: inset 0 0 0 2px var(--info-color, #38bdf8);
  }

  .fish-bonus-section {
    border-top: 1px solid var(--border-color);
    padding: 12px 16px;
    background: var(--cat-fish-bonus-bg, rgba(56, 189, 248, 0.08));
    flex-shrink: 0;
  }

  .fish-bonus-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-weight: 600;
    font-size: 12px;
    color: var(--info-color, #38bdf8);
  }

  .fish-bonus-badge {
    font-size: 9px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--info-color, #38bdf8);
    color: white;
    text-transform: uppercase;
  }

  .skills-list.fish-bonus .skill-row {
    border-color: rgba(0, 0, 0, 0.1);
    padding: 4px 0;
  }

  .skills-list.fish-bonus .skill-value {
    color: var(--info-color, #38bdf8);
  }

  .summary-item.cat-fish-bonus {
    background-color: var(--cat-fish-bonus-bg, rgba(56, 189, 248, 0.1));
  }

  .legend-swatch.fish-bonus {
    background-color: var(--cat-fish-bg, rgba(56, 189, 248, 0.25));
    box-shadow: inset 0 0 0 2px var(--info-color, #38bdf8);
  }

  /* Cumulative Summary */
  .cumulative-summary {
    padding: 12px 16px;
    background: var(--hover-color);
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .summary-title {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    margin-bottom: 8px;
  }

  .summary-grid {
    display: flex;
    gap: 8px;
  }

  .summary-item {
    flex: 1;
    padding: 8px;
    border-radius: 6px;
    text-align: center;
  }

  .summary-item.cat-cat1 {
    background-color: var(--cat1-bg, rgba(100, 149, 237, 0.3));
  }

  .summary-item.cat-cat2 {
    background-color: var(--cat2-bg, rgba(147, 112, 219, 0.3));
  }

  .summary-item.cat-cat3 {
    background-color: var(--cat3-bg, rgba(60, 179, 113, 0.3));
  }

  .summary-item.cat-fish {
    background-color: var(--cat-fish-bg, rgba(56, 189, 248, 0.25));
  }

  .summary-grid.fish-summary {
    flex-direction: column;
    gap: 4px;
  }

  .fish-summary .summary-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 10px;
  }

  .fish-summary .summary-label {
    margin-bottom: 0;
  }

  .summary-label {
    display: block;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    margin-bottom: 2px;
  }

  .summary-value {
    font-size: 11px;
    font-weight: 700;
    color: var(--text-color);
  }

  /* Footer */
  .codex-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
    font-size: 12px;
    color: var(--text-muted);
  }

  .codex-type strong {
    color: var(--text-color);
  }

  .cat4-note {
    font-size: 11px;
    padding: 4px 8px;
    background: var(--warning-bg);
    color: var(--warning-color);
    border-radius: 4px;
  }

  .no-data {
    color: var(--text-muted);
    font-style: italic;
    padding: 32px;
    text-align: center;
    background: var(--hover-color);
    border-radius: 8px;
    border: 1px dashed var(--border-color);
  }

  /* Tablet/Small Desktop - adjust layout earlier to avoid squeeze */
  @media (min-width: 768px) and (max-width: 899px) {
    .calculator-layout {
      grid-template-columns: 1fr;
      gap: 16px;
    }

    .rank-section {
      max-width: 100%;
    }

    .rank-grid {
      width: fit-content;
      margin: 0 auto;
    }

    .rewards-panel {
      min-width: 0;
      width: 100%;
    }

    .skills-section {
      max-height: 280px;
      overflow-y: auto;
    }

    .skills-header,
    .skill-row {
      grid-template-columns: 1fr 50px 70px;
    }
  }

  /* Container-based fallback for narrow desktop panes */
  @container (max-width: 900px) {
    .calculator-layout {
      grid-template-columns: 1fr;
      gap: 16px;
    }

    .rank-section {
      max-width: 100%;
    }

    .rank-grid {
      width: fit-content;
      margin: 0 auto;
    }

    .rewards-panel {
      min-width: 0;
      width: 100%;
    }

    .skills-section {
      max-height: 280px;
      overflow-y: auto;
    }

    .skills-header,
    .skill-row {
      grid-template-columns: 1fr 50px 70px;
    }
  }

  /* Tablet - stack vertically but keep sizes */
  @media (max-width: 899px) {
    .calculator-layout {
      grid-template-columns: 1fr;
      gap: 16px;
    }

    .rank-section {
      width: 100%;
    }

    .rank-grid {
      width: fit-content;
      margin: 0 auto;
    }

    .view-toggle {
      max-width: 380px;
      margin: 0 auto;
    }

    .legend {
      justify-content: center;
    }

    .rewards-panel {
      height: auto;
    }

    .skills-section {
      max-height: 280px;
      overflow-y: auto;
    }
  }

  /* Mobile portrait - smaller buttons */
  @media (max-width: 500px) {
    .rank-btn {
      width: 56px;
      height: 50px;
    }

    .rank-cost {
      font-size: 11px;
    }

    .rank-number {
      font-size: 9px;
    }

    .rank-unit {
      font-size: 7px;
    }

    .codex-footer {
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
    }

    .summary-grid {
      flex-direction: column;
      gap: 6px;
    }

    .summary-item {
      padding: 6px 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .summary-label {
      margin-bottom: 0;
    }

    .rewards-header {
      flex-direction: column;
      gap: 8px;
      align-items: flex-start;
    }

    .cost-display {
      text-align: left;
    }
  }
</style>

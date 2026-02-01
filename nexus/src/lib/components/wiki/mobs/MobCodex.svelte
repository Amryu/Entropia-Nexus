<!--
  @component MobCodex
  Interactive codex calculator for mob hunting.
  Shows rank costs and skill rewards.
-->
<script>
  // @ts-nocheck
  import { getTypeLink } from '$lib/util';

  export let baseCost = null;
  export let codexType = null;
  export let mobType = 'Animal';  // Animal, Mutant, Robot - to determine which looter profession to check
  export let skills = [];  // Skills data from API

  const CODEX_MULTIPLIERS = [
    1, 2, 3, 4, 6,
    8, 10, 12, 14, 16,
    18, 20, 24, 28, 32,
    36, 40, 44, 48, 56,
    64, 72, 80, 90, 100
  ];

  // Skill category reward divisors
  const REWARD_DIVISORS = { cat1: 200, cat2: 320, cat3: 640, cat4: 1000 };

  // Fallback skill lists if API data not available
  const SKILLS_FALLBACK = {
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

  // Build skill lookup from API data
  $: skillLookup = skills.reduce((acc, skill) => {
    acc[skill.Name] = skill;
    return acc;
  }, {});

  // Get looter profession name based on mob type
  $: looterProfession = mobType === 'Animal' ? 'Animal Looter'
    : mobType === 'Mutant' ? 'Mutant Looter'
    : mobType === 'Robot' ? 'Robot Looter'
    : null;

  // Codex skill categories are a specific game mechanic that doesn't map directly
  // to database skill categories, so we use the hardcoded lists.
  // The skills API data is used for skill metadata (HP increase, profession weights).
  const SKILLS = SKILLS_FALLBACK;

  // Defense professions to check
  const DEFENSE_PROFESSIONS = ['Evader', 'Dodger', 'Jammer'];

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

    // Check looter profession contribution
    if (skill?.Professions && looterProfession) {
      const looterContrib = skill.Professions.find(p => p.Profession?.Name === looterProfession);
      if (looterContrib?.Weight != null) {
        const weight = looterContrib.Weight;
        if (weight >= 0.8) badges.push({ label: 'Loot', level: 'high', value: weight, type: 'loot' });
        else if (weight >= 0.4) badges.push({ label: 'Loot', level: 'medium', value: weight, type: 'loot' });
        else if (weight > 0) badges.push({ label: 'Loot', level: 'low', value: weight, type: 'loot' });
      }
    }

    // Check defense profession contribution (Evader/Dodger/Jammer)
    if (skill?.Professions) {
      let maxDefenseWeight = 0;
      let defenseProf = null;
      for (const prof of DEFENSE_PROFESSIONS) {
        const contrib = skill.Professions.find(p => p.Profession?.Name === prof);
        if (contrib?.Weight != null && contrib.Weight > maxDefenseWeight) {
          maxDefenseWeight = contrib.Weight;
          defenseProf = prof;
        }
      }
      if (maxDefenseWeight > 0) {
        const shortLabel = defenseProf === 'Evader' ? 'Eva' : defenseProf === 'Dodger' ? 'Dod' : 'Jam';
        if (maxDefenseWeight >= 0.8) badges.push({ label: shortLabel, level: 'high', value: maxDefenseWeight, type: 'defense' });
        else if (maxDefenseWeight >= 0.4) badges.push({ label: shortLabel, level: 'medium', value: maxDefenseWeight, type: 'defense' });
        else badges.push({ label: shortLabel, level: 'low', value: maxDefenseWeight, type: 'defense' });
      }
    }

    return badges;
  }

  function getCategoryForRank(rank) {
    const mod = rank % 5;
    if (mod === 1 || mod === 2) return 'cat1';
    if (mod === 3 || mod === 4) return 'cat2';
    return 'cat3';
  }

  // Calculate cumulative cost up to a rank
  function getCumulativeCost(upToRank) {
    let total = 0;
    for (let i = 0; i <= upToRank; i++) {
      total += CODEX_MULTIPLIERS[i] * baseCost;
    }
    return total;
  }

  // Calculate cumulative skill gain for a category up to selected rank
  function calcCumulativeSkillGain(category, upToRank, base) {
    if (!base) return '0.0000';
    let total = 0;
    const divisor = REWARD_DIVISORS[category];
    for (let i = 0; i <= upToRank; i++) {
      const rankCategory = getCategoryForRank(i + 1);
      if (rankCategory === category) {
        total += (CODEX_MULTIPLIERS[i] * base) / divisor;
      }
    }
    return total.toFixed(4);
  }

  let selectedRank = 0;
  let showCumulative = false;

  $: category = getCategoryForRank(selectedRank + 1);
  $: skillsForRank = codexType === 'Asteroid' ? SKILLS.asteroid : SKILLS[category];
  $: rewardDivisor = REWARD_DIVISORS[category];
  $: isCat4Rank = codexType === 'MobLooter' && (selectedRank + 1) % 10 === 5;
  $: costForRank = baseCost ? CODEX_MULTIPLIERS[selectedRank] * baseCost : null;
  $: cumulativeCost = baseCost ? getCumulativeCost(selectedRank) : null;
  $: displayCost = showCumulative ? cumulativeCost : costForRank;
  $: rewardValue = costForRank ? (costForRank / rewardDivisor).toFixed(4) : 'N/A';
  $: cat4RewardValue = costForRank ? (costForRank / REWARD_DIVISORS.cat4).toFixed(4) : 'N/A';

  // Reactive cumulative skill gains - these update when selectedRank changes
  $: cumulativeCat1 = calcCumulativeSkillGain('cat1', selectedRank, baseCost);
  $: cumulativeCat2 = calcCumulativeSkillGain('cat2', selectedRank, baseCost);
  $: cumulativeCat3 = calcCumulativeSkillGain('cat3', selectedRank, baseCost);
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
                {@const rankCategory = getCategoryForRank(rankIndex + 1)}
                {@const isCat4 = codexType === 'MobLooter' && (rankIndex + 1) % 10 === 5}
                {@const displayValue = showCumulative ? getCumulativeCost(rankIndex) : multiplier * baseCost}
                <button
                  class="rank-btn cat-{rankCategory}"
                  class:selected={isSelected}
                  class:cat4-bonus={isCat4}
                  on:click={() => selectedRank = rankIndex}
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
            on:click={() => showCumulative = false}
          >
            Per Rank
          </button>
          <button
            class="toggle-btn"
            class:active={showCumulative}
            on:click={() => showCumulative = true}
          >
            Cumulative
          </button>
        </div>

        <!-- Legend -->
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
      </div>

      <!-- Rewards Panel -->
      <div class="rewards-panel">
        <div class="rewards-header">
          <div class="rewards-title">
            <span class="rank-label">Rank {selectedRank + 1}</span>
            <span class="category-badge cat-{category}">Category {category.slice(-1)}</span>
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
              <div class="skill-row" class:has-badge={badges.length > 0}>
                <a href={getTypeLink(skill, 'Skill')} class="skill-name skill-link">{skill}</a>
                <span class="skill-badges">
                  {#each badges as badge}
                    <span
                      class="skill-badge {badge.level} {badge.type}"
                      title="{badge.type === 'hp' ? (badge.level === 'ineffective' ? `HP per skill: ${badge.value} (less effective)` : `HP per skill: ${badge.value}`) : badge.type === 'loot' ? `${looterProfession} contribution: ${badge.value}` : `${badge.label === 'Eva' ? 'Evader' : badge.label === 'Dod' ? 'Dodger' : 'Jammer'} contribution: ${badge.value}`}"
                    >{badge.label}</span>
                  {/each}
                </span>
                <span class="skill-value">{rewardValue}</span>
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
                        title="{badge.type === 'hp' ? (badge.level === 'ineffective' ? `HP per skill: ${badge.value} (less effective)` : `HP per skill: ${badge.value}`) : badge.type === 'loot' ? `${looterProfession} contribution: ${badge.value}` : `${badge.label === 'Eva' ? 'Evader' : badge.label === 'Dod' ? 'Dodger' : 'Jammer'} contribution: ${badge.value}`}"
                      >{badge.label}</span>
                    {/each}
                  </span>
                  <span class="skill-value">{cat4RewardValue}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Cumulative Summary by Category -->
        <div class="cumulative-summary">
          <div class="summary-title">Cumulative Skill Gain (Ranks 1-{selectedRank + 1})</div>
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
      min-height: 400px;
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

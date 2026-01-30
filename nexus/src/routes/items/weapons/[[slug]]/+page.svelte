<!--
  @component Weapon Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: All numeric stats + damage breakdown
  Article: Description → Tiers → Acquisition
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { encodeURIComponentSafe, hasItemTag, clampDecimals, getTypeLink } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  // Weapon-specific components
  import WeaponDamageGrid from '$lib/components/wiki/weapons/WeaponDamageGrid.svelte';
  import WeaponEffects from '$lib/components/wiki/weapons/WeaponEffects.svelte';
  import WeaponTiers from '$lib/components/wiki/weapons/WeaponTiers.svelte';

  // Legacy components for comparison
  import Acquisition from '$lib/components/Acquisition.svelte';

  export let data;

  $: weapon = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: additional = data.additional || {};

  // Build navigation items from grouped weapons
  $: navItems = allItems;

  // Navigation filters
  const navFilters = [
    {
      key: 'Properties.Class',
      label: 'Class',
      values: [
        { value: 'Ranged', label: 'Ranged' },
        { value: 'Melee', label: 'Melee' },
        { value: 'Mindforce', label: 'Mindforce' },
        { value: 'Attached', label: 'Attached' },
      ]
    }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Weapons', href: '/items/weapons' },
    ...(weapon ? [{ label: weapon.Name }] : [])
  ];

  // SEO
  $: seoDescription = weapon?.Properties?.Description ||
    `${weapon?.Name || 'Weapon'} - ${weapon?.Properties?.Class || ''} ${weapon?.Properties?.Type || ''} weapon in Entropia Universe.`;

  $: canonicalUrl = weapon
    ? `https://entropianexus.com/items/weapons/${encodeURIComponentSafe(weapon.Name)}`
    : 'https://entropianexus.com/items/weapons';

  // Check if weapon is tierable
  $: isTierable = weapon && !hasItemTag(weapon.Name, 'L');
  $: hasEffects = (weapon?.EffectsOnEquip?.length > 0) || (weapon?.EffectsOnUse?.length > 0);

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    tiers: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-weapon-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-weapon-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== RELOAD/USES TOGGLE ==========
  let showReload = true;

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-weapon-show-reload');
      if (stored !== null) {
        showReload = stored === 'true';
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function toggleReloadUses() {
    showReload = !showReload;
    try {
      localStorage.setItem('wiki-weapon-show-reload', String(showReload));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== CALCULATOR FUNCTIONS ==========
  function getTotalDamage(item) {
    if (!item?.Properties?.Damage) return null;
    const d = item.Properties.Damage;
    return (d.Impact || 0) + (d.Cut || 0) + (d.Stab || 0) + (d.Penetration || 0) +
           (d.Shrapnel || 0) + (d.Burn || 0) + (d.Cold || 0) + (d.Acid || 0) + (d.Electric || 0);
  }

  function getEffectiveDamage(item) {
    const totalDamage = getTotalDamage(item);
    if (totalDamage === null || totalDamage === 0) return null;
    const multiplier = 0.88 * 0.75 + 0.02 * 1.75;
    return totalDamage * multiplier;
  }

  function getReload(item) {
    if (!item?.Properties?.UsesPerMinute) return null;
    return 60 / item.Properties.UsesPerMinute;
  }

  function getCostPerUse(item) {
    const decay = item?.Properties?.Economy?.Decay;
    const ammoBurn = item?.Properties?.Economy?.AmmoBurn ?? 0;
    if (decay === null || decay === undefined) return null;
    return decay + (ammoBurn / 100);
  }

  function getDps(item) {
    const reload = getReload(item);
    const effectiveDamage = getEffectiveDamage(item);
    if (effectiveDamage === null || reload === null) return null;
    return effectiveDamage / reload;
  }

  function getDpp(item) {
    const cost = getCostPerUse(item);
    const effectiveDamage = getEffectiveDamage(item);
    if (cost === null || cost === 0 || effectiveDamage === null) return null;
    return effectiveDamage / cost;
  }

  function getEfficiency(item) {
    return item?.Properties?.Economy?.Efficiency || null;
  }

  function getTotalUses(item) {
    const maxTT = item?.Properties?.Economy?.MaxTT;
    const minTT = item?.Properties?.Economy?.MinTT ?? 0;
    const decay = item?.Properties?.Economy?.Decay;
    if (maxTT === null || maxTT === undefined || decay === null || decay === undefined || decay === 0) return null;
    return Math.floor((maxTT - minTT) / (decay / 100));
  }

  // Skill-related getters
  function getSkillInfo(item) {
    return item?.Properties?.Skill || null;
  }

  function getProfessionNames(item) {
    // Profession names are at top level, not in Properties.Skill
    return {
      hit: item?.ProfessionHit?.Name || null,
      dmg: item?.ProfessionDmg?.Name || null
    };
  }

  function getSkillIntervals(item) {
    const skill = getSkillInfo(item);
    if (!skill) return null;
    return {
      hit: {
        min: skill.Hit?.LearningIntervalStart ?? null,
        max: skill.Hit?.LearningIntervalEnd ?? null
      },
      dmg: {
        min: skill.Dmg?.LearningIntervalStart ?? null,
        max: skill.Dmg?.LearningIntervalEnd ?? null
      }
    };
  }

  // Reactive calculations
  $: dps = getDps(weapon);
  $: dpp = getDpp(weapon);
  $: efficiency = getEfficiency(weapon);
  $: costPerUse = getCostPerUse(weapon);
  $: reload = getReload(weapon);
  $: totalUses = getTotalUses(weapon);
  $: effectiveDamage = getEffectiveDamage(weapon);
  $: skillInfo = getSkillInfo(weapon);
  $: professionNames = getProfessionNames(weapon);
  $: skillIntervals = getSkillIntervals(weapon);
</script>

<WikiSEO
  title={weapon?.Name || 'Weapons'}
  description={seoDescription}
  entityType="weapon"
  entity={weapon}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Weapons"
  {breadcrumbs}
  entity={weapon}
  entityType="Weapon"
  basePath="/items/weapons"
  {navItems}
  {navFilters}
  {user}
  editable={true}
>
  {#if weapon}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <div class="icon-placeholder">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
              <rect x="3" y="3" width="18" height="18" rx="2" />
            </svg>
          </div>
          <div class="infobox-title">{weapon.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">{weapon.Properties?.Class || 'Unknown'}</span>
            <span>{weapon.Properties?.Category || ''} &bull; {weapon.Properties?.Type || ''}</span>
          </div>
        </div>

        <!-- Tier 1 Stats (toned down) -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Efficiency</span>
            <span class="stat-value">{efficiency ? `${efficiency.toFixed(1)}%` : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">DPS</span>
            <span class="stat-value">{dps ? dps.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">DPP</span>
            <span class="stat-value">{dpp ? dpp.toFixed(2) : 'N/A'}</span>
          </div>
        </div>

        <!-- Tier 2 Stats -->
        <div class="stats-section tier-2">
          <h4 class="section-title">Performance</h4>
          <div class="stat-row">
            <span class="stat-label">Effective Dmg</span>
            <span class="stat-value">{effectiveDamage ? effectiveDamage.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Range</span>
            <span class="stat-value">{weapon.Properties?.Range ? `${weapon.Properties.Range}m` : 'N/A'}</span>
          </div>
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div class="stat-row toggleable" on:click={toggleReloadUses} title="Click to toggle between Reload and Uses/min">
            {#if showReload}
              <span class="stat-label">Reload <span class="toggle-hint">⇄</span></span>
              <span class="stat-value">{reload ? `${reload.toFixed(2)}s` : 'N/A'}</span>
            {:else}
              <span class="stat-label">Uses/min <span class="toggle-hint">⇄</span></span>
              <span class="stat-value">{weapon.Properties?.UsesPerMinute ? clampDecimals(weapon.Properties.UsesPerMinute, 0, 2) : 'N/A'}</span>
            {/if}
          </div>
          <div class="stat-row">
            <span class="stat-label">Cost/Use</span>
            <span class="stat-value">{costPerUse ? `${costPerUse.toFixed(4)} PEC` : 'N/A'}</span>
          </div>
        </div>

        <!-- Economy Stats -->
        <div class="stats-section tier-3">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max TT</span>
            <span class="stat-value">{weapon.Properties?.Economy?.MaxTT?.toFixed(2) || 'N/A'} PED</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min TT</span>
            <span class="stat-value">{weapon.Properties?.Economy?.MinTT?.toFixed(2) || '0.00'} PED</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Decay</span>
            <span class="stat-value">{weapon.Properties?.Economy?.Decay?.toFixed(4) || 'N/A'} PEC</span>
          </div>
          {#if weapon.Ammo?.Name}
            <div class="stat-row">
              <span class="stat-label">Ammo Burn</span>
              <span class="stat-value">{weapon.Properties?.Economy?.AmmoBurn ?? 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Ammo</span>
              <span class="stat-value">{weapon.Ammo.Name}</span>
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Total Uses</span>
            <span class="stat-value">{totalUses ?? 'N/A'}</span>
          </div>
        </div>

        <!-- Skilling Info -->
        <div class="stats-section">
          <h4 class="section-title">Skilling</h4>
          <div class="stat-row">
            <span class="stat-label">SiB</span>
            <span class="stat-value" class:highlight-yes={skillInfo?.IsSiB}>{skillInfo?.IsSiB ? 'Yes' : 'No'}</span>
          </div>
          {#if professionNames.hit}
            <div class="stat-row">
              <span class="stat-label">Hit Profession</span>
              <span class="stat-value">
                <a href={getTypeLink(professionNames.hit, 'Profession')} class="profession-link">{professionNames.hit}</a>
              </span>
            </div>
            {#if skillIntervals?.hit?.min !== null || skillIntervals?.hit?.max !== null}
              <div class="stat-row indent">
                <span class="stat-label">Level Range</span>
                <span class="stat-value">{skillIntervals?.hit?.min ?? '?'} - {skillIntervals?.hit?.max ?? '?'}</span>
              </div>
            {/if}
          {/if}
          {#if professionNames.dmg}
            <div class="stat-row">
              <span class="stat-label">Dmg Profession</span>
              <span class="stat-value">
                <a href={getTypeLink(professionNames.dmg, 'Profession')} class="profession-link">{professionNames.dmg}</a>
              </span>
            </div>
            {#if skillIntervals?.dmg?.min !== null || skillIntervals?.dmg?.max !== null}
              <div class="stat-row indent">
                <span class="stat-label">Level Range</span>
                <span class="stat-value">{skillIntervals?.dmg?.min ?? '?'} - {skillIntervals?.dmg?.max ?? '?'}</span>
              </div>
            {/if}
          {/if}
        </div>

        <!-- Properties -->
        <div class="stats-section">
          <h4 class="section-title">Properties</h4>
          <div class="stat-row">
            <span class="stat-label">Class</span>
            <span class="stat-value">{weapon.Properties?.Class || 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Category</span>
            <span class="stat-value">{weapon.Properties?.Category || 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">{weapon.Properties?.Type || 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{weapon.Properties?.Weight ? `${clampDecimals(weapon.Properties.Weight, 1, 6)}kg` : 'N/A'}</span>
          </div>
        </div>

        <!-- Damage Breakdown (bars) -->
        <div class="stats-section damage-section">
          <h4 class="section-title">Damage Breakdown</h4>
          <WeaponDamageGrid {weapon} />
        </div>

        <!-- Effects (if any) -->
        {#if hasEffects}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects</h4>
            <WeaponEffects {weapon} combined={true} />
          </div>
        {/if}

        <!-- Loadout Calculator Link -->
        <a href="/tools/loadouts?weapon={encodeURIComponentSafe(weapon.Name)}" class="loadout-link-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="4" y="4" width="16" height="16" rx="2" />
            <path d="M9 9h6M9 12h6M9 15h4" />
          </svg>
          <span>Open in Loadout Calculator</span>
        </a>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{weapon.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if weapon.Properties?.Description}
            <div class="description-content">{weapon.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {weapon.Name} is a {weapon.Properties?.Class?.toLowerCase() || ''} {weapon.Properties?.Type?.toLowerCase() || ''} weapon.
            </div>
          {/if}
        </div>

        <!-- Tiering Section -->
        {#if isTierable}
          <DataSection
            title="Tiers"
            icon=""
            bind:expanded={panelStates.tiers}
            subtitle="{additional.tierInfo?.length || 0} tiers"
            on:toggle={savePanelStates}
          >
            <WeaponTiers {weapon} tierInfo={additional.tierInfo} />
          </DataSection>
        {/if}

        <!-- Acquisition Section -->
        {#if additional.acquisition}
          <DataSection
            title="Acquisition"
            icon=""
            bind:expanded={panelStates.acquisition}
            on:toggle={savePanelStates}
          >
            <Acquisition acquisition={additional.acquisition} />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Weapons</h2>
      <p>Select a weapon from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .layout-a {
    position: relative;
    width: 100%;
  }

  /* Clearfix to ensure spacing after floated infobox */
  .layout-a::after {
    content: '';
    display: block;
    clear: both;
  }

  /* Floating infobox - Wikipedia style */
  .wiki-infobox-float {
    float: right;
    width: 320px;
    margin: 0 0 0 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 16px;
  }

  .infobox-header {
    text-align: center;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .icon-placeholder {
    width: 80px;
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--bg-color, var(--primary-color));
    border: 2px dashed var(--border-color, #555);
    border-radius: 8px;
    color: var(--text-muted, #999);
    margin: 0 auto 12px;
  }

  .infobox-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .infobox-subtitle {
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-top: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .type-badge {
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
  }

  /* Stats sections */
  .stats-section {
    padding: 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  .stats-section.tier-1 {
    background: linear-gradient(135deg, #3a6d99 0%, #2d5577 100%);
    padding: 14px;
  }

  .stats-section.tier-1 .stat-row.primary {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    padding: 8px 12px;
    margin-bottom: 6px;
  }

  .stats-section.tier-1 .stat-row.primary:last-child {
    margin-bottom: 0;
  }

  .stats-section.tier-1 .stat-label {
    color: rgba(255, 255, 255, 0.9);
    font-size: 13px;
    text-transform: uppercase;
    font-weight: 500;
  }

  .stats-section.tier-1 .stat-value {
    color: #e8f4ff;
    font-size: 18px;
    font-weight: 700;
  }

  .section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 10px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 4px 0;
    font-size: 13px;
  }

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    font-weight: 500;
    color: var(--text-color);
  }

  .stat-value.highlight-yes {
    color: var(--success-color, #4ade80);
  }

  .stat-row.toggleable {
    cursor: pointer;
    padding: 4px 6px;
    margin: 0 -6px;
    border-radius: 4px;
    transition: background-color 0.15s;
  }

  .stat-row.toggleable:hover {
    background-color: var(--hover-color);
  }

  .toggle-hint {
    font-size: 10px;
    color: var(--text-muted, #999);
    margin-left: 4px;
    opacity: 0.7;
  }

  .stat-row.toggleable:hover .toggle-hint {
    opacity: 1;
  }

  .stat-row.indent {
    padding-left: 12px;
  }

  .stat-row.indent .stat-label {
    font-size: 11px;
  }

  .profession-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .profession-link:hover {
    text-decoration: underline;
  }

  .damage-section,
  .effects-section {
    padding: 12px;
  }

  .loadout-link-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 16px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    color: var(--text-color);
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.15s;
  }

  .loadout-link-btn:hover {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .loadout-link-btn svg {
    flex-shrink: 0;
  }

  .wiki-article {
    overflow: hidden; /* Contains floated infobox */
  }

  .article-title {
    font-size: 32px;
    font-weight: 600;
    margin: 0 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--accent-color, #4a9eff);
  }

  .description-panel {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }

  .description-content {
    font-size: 15px;
    line-height: 1.6;
    color: var(--text-color);
  }

  .description-content.placeholder {
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .no-selection {
    text-align: center;
    padding: 60px 20px;
  }

  .no-selection h2 {
    font-size: 28px;
    margin-bottom: 12px;
  }

  .no-selection p {
    color: var(--text-muted, #999);
    margin: 8px 0;
  }

  /* Tablet adjustments */
  @media (max-width: 1023px) {
    .wiki-infobox-float {
      width: 280px;
      margin-left: 16px;
      padding: 14px;
    }
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .layout-a {
      max-width: 100%;
    }

    .wiki-infobox-float {
      float: none;
      width: auto;
      margin: 0 0 16px 0;
    }

    /* Hide article title on mobile - redundant with infobox */
    .article-title {
      display: none;
    }

    .infobox-title {
      font-size: 16px;
    }

    .icon-placeholder {
      width: 60px;
      height: 60px;
    }

    .icon-placeholder svg {
      width: 36px;
      height: 36px;
    }
  }
</style>

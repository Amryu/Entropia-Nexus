<!--
  @component Medical Tools Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Handles 2 subtypes: tools, chips

  Legacy editConfig preserved in medicaltools-legacy/+page.svelte
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { hasItemTag, clampDecimals, encodeURIComponentSafe, getTimeString, getTypeLink } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  // Legacy components for data display
  import Tiering from '$lib/components/Tiering.svelte';
  import Acquisition from '$lib/components/Acquisition.svelte';

  export let data;

  $: medtool = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};

  // For multi-type pages, data.items is an object keyed by type
  $: allItems = (() => {
    if (!data.items) return [];
    if (additional.type && data.items[additional.type]) {
      return data.items[additional.type];
    }
    const combined = [];
    for (const [type, items] of Object.entries(data.items)) {
      for (const item of items) {
        combined.push({ ...item, _type: type });
      }
    }
    return combined;
  })();

  // Type navigation buttons
  const typeButtons = [
    { label: 'Tools', title: 'Medical Tools', type: 'tools' },
    { label: 'Chips', title: 'Medical Chips', type: 'chips' }
  ];

  // Type name mapping
  function getTypeName(type) {
    switch (type) {
      case 'tools': return 'Medical Tool';
      case 'chips': return 'Medical Chip';
      default: return 'Medical Tool';
    }
  }

  // Entity type for editing
  function getEntityType(type) {
    switch (type) {
      case 'tools': return 'MedicalTool';
      case 'chips': return 'MedicalChip';
      default: return 'MedicalTool';
    }
  }

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters - type buttons with deselection support
  $: navFilters = typeButtons.map(btn => ({
    label: btn.label,
    title: btn.title,
    type: btn.type,
    active: additional.type === btn.type,
    href: additional.type === btn.type ? '/items/medicaltools' : `/items/medicaltools/${btn.type}`
  }));

  // Type-specific sidebar table columns
  function getNavTableColumns(type) {
    switch (type) {
      case 'tools':
        return [
          { key: 'hps', header: 'HPS', width: '55px', filterPlaceholder: '>10', getValue: (item) => getHps(item), format: (v) => v != null ? v.toFixed(1) : '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      case 'chips':
        return [
          { key: 'hps', header: 'HPS', width: '55px', filterPlaceholder: '>10', getValue: (item) => getHps(item), format: (v) => v != null ? v.toFixed(1) : '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      default:
        return [
          { key: 'cat', header: 'Type', width: '55px', filterPlaceholder: 'Tool', getValue: (item) => item._type === 'tools' ? 'Tool' : 'Chip', format: (v) => v || '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
    }
  }

  $: navTableColumns = getNavTableColumns(additional.type);

  // Custom href generator for items
  function getItemHref(item, basePath) {
    const type = item._type || additional.type;
    if (type) {
      return `/items/medicaltools/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Medical Tools', href: '/items/medicaltools' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + 's', href: `/items/medicaltools/${additional.type}` }] : []),
    ...(medtool ? [{ label: medtool.Name }] : [])
  ];

  // SEO
  $: seoDescription = medtool?.Properties?.Description ||
    `${medtool?.Name || 'Medical Tool'} - ${getTypeName(additional.type)} in Entropia Universe.`;

  $: canonicalUrl = medtool
    ? `https://entropianexus.com/items/medicaltools/${additional.type}/${encodeURIComponentSafe(medtool.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/medicaltools/${additional.type}`
    : 'https://entropianexus.com/items/medicaltools';

  // ========== CALCULATION FUNCTIONS ==========
  function getCost(item) {
    if (!item?.Properties?.Economy?.Decay) return null;
    return item.Properties.Economy.Decay + (item.Properties.Economy.AmmoBurn ?? 0) / 100;
  }

  function getEffectiveHealing(item) {
    if (item?.Properties?.MaxHeal == null || item?.Properties?.MinHeal == null) return null;
    return (item.Properties.MaxHeal + item.Properties.MinHeal) / 2;
  }

  function getReload(item) {
    if (!item?.Properties?.UsesPerMinute) return null;
    return 60 / item.Properties.UsesPerMinute;
  }

  function getHps(item) {
    const reload = getReload(item);
    const effectiveHealing = getEffectiveHealing(item);
    if (reload == null || effectiveHealing == null) return null;
    return effectiveHealing / reload;
  }

  function getHpp(item) {
    const cost = getCost(item);
    const effectiveHealing = getEffectiveHealing(item);
    if (cost == null || effectiveHealing == null) return null;
    return effectiveHealing / cost;
  }

  function getTotalUses(item) {
    if (!item?.Properties?.Economy?.MaxTT || !item?.Properties?.Economy?.Decay) return null;
    const maxTT = item.Properties.Economy.MaxTT;
    const minTT = item.Properties.Economy.MinTT ?? 0;
    const decay = item.Properties.Economy.Decay;
    return Math.floor((maxTT - minTT) / (decay / 100));
  }

  // ========== COMPUTED VALUES ==========
  $: cost = getCost(medtool);
  $: reload = getReload(medtool);
  $: hps = getHps(medtool);
  $: hpp = getHpp(medtool);
  $: totalUses = getTotalUses(medtool);
  $: cyclePerRepair = totalUses && cost ? totalUses * (cost / 100) : null;
  $: cyclePerHour = reload && cost ? (3600 / reload) * (cost / 100) : null;
  $: timeToBreak = cyclePerHour > 0 && cyclePerRepair ? cyclePerRepair / cyclePerHour : null;

  // Check for effects
  $: hasEquipEffects = medtool?.EffectsOnEquip?.length > 0;
  $: hasUseEffects = medtool?.EffectsOnUse?.length > 0;

  // Check for tiering (tools only, non-L items)
  $: hasTiering = additional.type === 'tools' && medtool && !hasItemTag(medtool.Name, 'L');

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    tiering: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-medicaltools-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-medicaltools-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }
</script>

<WikiSEO
  title={medtool?.Name || `${getTypeName(additional.type)}s`}
  description={seoDescription}
  entityType={getEntityType(additional.type)}
  entity={medtool}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Medical Tools"
  {breadcrumbs}
  entity={medtool}
  entityType={getEntityType(additional.type)}
  basePath="/items/medicaltools/{additional.type || ''}"
  {navItems}
  {navFilters}
  {navTableColumns}
  navGetItemHref={getItemHref}
  {user}
  editable={true}
>
  {#if medtool}
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
          <div class="infobox-title">{medtool.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">{getTypeName(additional.type)}</span>
            {#if medtool.Properties?.Skill?.IsSiB}
              <span class="sib-badge">SiB</span>
            {/if}
          </div>
        </div>

        <!-- Tier-1 Stats -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">HPS</span>
            <span class="stat-value">{hps != null ? hps.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">HPP</span>
            <span class="stat-value">{hpp != null ? hpp.toFixed(4) : 'N/A'}</span>
          </div>
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{medtool.Properties?.Weight != null ? `${clampDecimals(medtool.Properties.Weight, 1, 6)}kg` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Reload</span>
            <span class="stat-value">{reload != null ? `${reload.toFixed(2)}s` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Uses/min</span>
            <span class="stat-value">{reload != null ? clampDecimals(60 / reload, 0, 2) : 'N/A'}</span>
          </div>
          {#if additional.type === 'chips' && medtool.Properties?.Range != null}
            <div class="stat-row">
              <span class="stat-label">Range</span>
              <span class="stat-value">{medtool.Properties.Range}m</span>
            </div>
          {/if}
        </div>

        <!-- Healing Stats -->
        <div class="stats-section">
          <h4 class="section-title">Healing</h4>
          <div class="stat-row">
            <span class="stat-label">HPS</span>
            <span class="stat-value highlight">{hps != null ? hps.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max. Heal</span>
            <span class="stat-value">{medtool.Properties?.MaxHeal != null ? `${medtool.Properties.MaxHeal.toFixed(2)} HP` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min. Heal</span>
            <span class="stat-value">{medtool.Properties?.MinHeal != null ? `${medtool.Properties.MinHeal.toFixed(2)} HP` : 'N/A'}</span>
          </div>
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">HPP</span>
            <span class="stat-value highlight">{hpp != null ? hpp.toFixed(4) : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max. TT</span>
            <span class="stat-value">{medtool.Properties?.Economy?.MaxTT != null ? `${clampDecimals(medtool.Properties.Economy.MaxTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min. TT</span>
            <span class="stat-value">{medtool.Properties?.Economy?.MinTT != null ? `${clampDecimals(medtool.Properties.Economy.MinTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Decay</span>
            <span class="stat-value">{medtool.Properties?.Economy?.Decay != null ? `${medtool.Properties.Economy.Decay.toFixed(4)} PEC` : 'N/A'}</span>
          </div>
          {#if additional.type === 'chips'}
            <div class="stat-row">
              <span class="stat-label">Ammo</span>
              <span class="stat-value">{medtool.Ammo?.Name || 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Ammo Burn</span>
              <span class="stat-value">{medtool.Properties?.Economy?.AmmoBurn ?? 'N/A'}</span>
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Cost</span>
            <span class="stat-value">{cost != null ? `${cost.toFixed(4)} PEC` : 'N/A'}</span>
          </div>
          {#if totalUses}
            <div class="stat-row">
              <span class="stat-label">Total Uses</span>
              <span class="stat-value">{totalUses}</span>
            </div>
          {/if}
        </div>

        <!-- Mindforce Stats (chips only) -->
        {#if additional.type === 'chips'}
          <div class="stats-section">
            <h4 class="section-title">Mindforce</h4>
            <div class="stat-row">
              <span class="stat-label">Level</span>
              <span class="stat-value">{medtool.Properties?.Mindforce?.Level ?? 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Concentration</span>
              <span class="stat-value">{medtool.Properties?.Mindforce?.Concentration != null ? `${medtool.Properties.Mindforce.Concentration}s` : 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cooldown</span>
              <span class="stat-value">{medtool.Properties?.Mindforce?.Cooldown != null ? `${medtool.Properties.Mindforce.Cooldown}s` : 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cooldown Group</span>
              <span class="stat-value">{medtool.Properties?.Mindforce?.CooldownGroup ?? 'N/A'}</span>
            </div>
          </div>
        {/if}

        <!-- Skill Stats -->
        <div class="stats-section">
          <h4 class="section-title">Skill</h4>
          <div class="stat-row">
            <span class="stat-label">SiB</span>
            <span class="stat-value">{medtool.Properties?.Skill?.IsSiB ? 'Yes' : 'No'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Profession</span>
            <span class="stat-value">
              <a href={getTypeLink(additional.type === 'chips' ? 'Biotropic' : 'Paramedic', 'Profession')} class="entity-link">
                {additional.type === 'chips' ? 'Biotropic' : 'Paramedic'}
              </a>
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Learning Range</span>
            <span class="stat-value">
              {medtool.Properties?.Skill?.LearningIntervalStart?.toFixed(1) ?? 'N/A'} - {medtool.Properties?.Skill?.LearningIntervalEnd?.toFixed(1) ?? 'N/A'}
            </span>
          </div>
        </div>

        <!-- Misc Stats -->
        {#if cyclePerRepair || cyclePerHour || timeToBreak}
          <div class="stats-section">
            <h4 class="section-title">Misc</h4>
            {#if cyclePerRepair}
              <div class="stat-row">
                <span class="stat-label">PED/repair</span>
                <span class="stat-value">{cyclePerRepair.toFixed(2)} PED</span>
              </div>
            {/if}
            {#if cyclePerHour}
              <div class="stat-row">
                <span class="stat-label">PED/h</span>
                <span class="stat-value">{cyclePerHour.toFixed(2)} PED</span>
              </div>
            {/if}
            {#if timeToBreak}
              <div class="stat-row">
                <span class="stat-label">Time to break</span>
                <span class="stat-value">{timeToBreak.toFixed(2)}h</span>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Effects on Equip -->
        {#if hasEquipEffects}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects on Equip</h4>
            {#each medtool.EffectsOnEquip.sort((a,b) => a.Name.localeCompare(b.Name)) as effect}
              <div class="stat-row">
                <span class="stat-label">{effect.Name}</span>
                <span class="stat-value effect-value">{effect.Values.Strength}{effect.Values.Unit}</span>
              </div>
            {/each}
          </div>
        {/if}

        <!-- Effects on Use -->
        {#if hasUseEffects}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects on Use</h4>
            {#each medtool.EffectsOnUse.sort((a,b) => a.Name.localeCompare(b.Name)) as effect}
              <div class="stat-row">
                <span class="stat-label">{effect.Name}</span>
                <span class="stat-value effect-value">{effect.Values.Strength}{effect.Values.Unit} for {getTimeString(effect.Values.DurationSeconds)}</span>
              </div>
            {/each}
          </div>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{medtool.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if medtool.Properties?.Description}
            <div class="description-content">{medtool.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {medtool.Name} is a {getTypeName(additional.type).toLowerCase()} used in Entropia Universe.
            </div>
          {/if}
        </div>

        <!-- Tiering Section (tools only, non-L items) -->
        {#if hasTiering && additional.tierInfo}
          <DataSection
            title="Tiering"
            icon=""
            bind:expanded={panelStates.tiering}
            on:toggle={savePanelStates}
          >
            <Tiering tieringInfo={additional.tierInfo} />
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
      <h2>{additional.type ? getTypeName(additional.type) + 's' : 'Medical Tools'}</h2>
      <p>Select a {additional.type ? getTypeName(additional.type).toLowerCase() : 'medical tool'} from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .layout-a {
    position: relative;
    width: 100%;
  }

  .layout-a::after {
    content: '';
    display: block;
    clear: both;
  }

  /* Floating infobox - Wikipedia style */
  .wiki-infobox-float {
    float: right;
    width: 300px;
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

  .sib-badge {
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
    background-color: #10b981;
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
    background: linear-gradient(135deg, #4a7c59 0%, #3a6349 100%);
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
    color: #e8f4e8;
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

  .stat-value.highlight {
    color: #4ade80;
    font-weight: 600;
  }

  .stat-value.effect-value {
    color: var(--accent-color, #4a9eff);
  }

  .entity-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .entity-link:hover {
    text-decoration: underline;
  }

  /* Effects styling */
  .effects-section .stat-row {
    padding: 3px 0;
  }

  .wiki-article {
    overflow: hidden;
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

<!--
  @component Tools Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: All numeric stats organized by section
  Article: Description → Tiering → Acquisition

  Handles 7 tool subtypes: refiners, scanners, finders, excavators, teleportationchips, effectchips, misctools
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { hasItemTag, encodeURIComponentSafe, clampDecimals, getTypeLink, getTimeString } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  // Legacy components for data display
  import Tiering from '$lib/components/Tiering.svelte';
  import Acquisition from '$lib/components/Acquisition.svelte';

  export let data;

  $: tool = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};

  // For multi-type pages, data.items is an object keyed by type
  // When no type is selected, show all items from all types (with _type added for linking)
  $: allItems = (() => {
    if (!data.items) return [];
    if (additional.type && data.items[additional.type]) {
      return data.items[additional.type];
    }
    // No type selected - combine all items from all types, adding _type for correct linking
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
    { label: 'Refiners', title: 'Refiners', type: 'refiners' },
    { label: 'Scanners', title: 'Scanners', type: 'scanners' },
    { label: 'Finders', title: 'Finders', type: 'finders' },
    { label: 'Excavators', title: 'Excavators', type: 'excavators' },
    { label: 'TP Chips', title: 'Teleportation Chips', type: 'teleportationchips' },
    { label: 'Effect Chips', title: 'Effect Chips', type: 'effectchips' },
    { label: 'Misc. Tools', title: 'Misc. Tools', type: 'misctools' }
  ];

  // Type name mapping
  function getTypeName(type) {
    switch (type) {
      case 'refiners': return 'Refiner';
      case 'scanners': return 'Scanner';
      case 'finders': return 'Finder';
      case 'excavators': return 'Excavator';
      case 'teleportationchips': return 'Teleportation Chip';
      case 'effectchips': return 'Effect Chip';
      case 'misctools': return 'Misc. Tool';
      default: return 'Tool';
    }
  }

  // Entity type for editing
  function getEntityType(type) {
    switch (type) {
      case 'refiners': return 'Refiner';
      case 'scanners': return 'Scanner';
      case 'finders': return 'Finder';
      case 'excavators': return 'Excavator';
      case 'teleportationchips': return 'TeleportationChip';
      case 'effectchips': return 'EffectChip';
      case 'misctools': return 'MiscTool';
      default: return 'Tool';
    }
  }

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters - type buttons
  // When a button is active, clicking it deselects (goes back to /items/tools to show all)
  $: navFilters = typeButtons.map(btn => ({
    label: btn.label,
    title: btn.title,
    type: btn.type,
    active: additional.type === btn.type,
    href: additional.type === btn.type ? '/items/tools' : `/items/tools/${btn.type}`
  }));

  // Type-specific sidebar table columns
  function getNavTableColumns(type) {
    switch (type) {
      case 'refiners':
        return [
          { key: 'tt', header: 'TT', width: '60px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 0, 2) : '-' },
          { key: 'decay', header: 'Dec', width: '55px', filterPlaceholder: '<0.5', getValue: (item) => item.Properties?.Economy?.Decay, format: (v) => v != null ? v.toFixed(2) : '-' }
        ];
      case 'scanners':
        return [
          { key: 'range', header: 'Rng', width: '50px', filterPlaceholder: '>50', getValue: (item) => item.Properties?.Range, format: (v) => v != null ? v : '-' },
          { key: 'upm', header: 'U/m', width: '50px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.UsesPerMinute, format: (v) => v != null ? clampDecimals(v, 0, 1) : '-' }
        ];
      case 'finders':
        return [
          { key: 'depth', header: 'Dpt', width: '50px', filterPlaceholder: '>200', getValue: (item) => item.Properties?.Depth, format: (v) => v != null ? v : '-' },
          { key: 'range', header: 'Rng', width: '50px', filterPlaceholder: '>50', getValue: (item) => item.Properties?.Range, format: (v) => v != null ? v : '-' }
        ];
      case 'excavators':
        return [
          { key: 'eff', header: 'Eff', width: '50px', filterPlaceholder: '>50', getValue: (item) => item.Properties?.Efficiency, format: (v) => v != null ? v : '-' },
          { key: 'effPed', header: 'E/P', width: '55px', filterPlaceholder: '>100', getValue: (item) => calcEfficiencyPerPed(item), format: (v) => v != null ? v.toFixed(1) : '-' }
        ];
      case 'teleportationchips':
        return [
          { key: 'range', header: 'Rng', width: '55px', filterPlaceholder: '>5', getValue: (item) => item.Properties?.Range, format: (v) => v != null ? `${v}km` : '-' },
          { key: 'level', header: 'Lvl', width: '45px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Mindforce?.Level, format: (v) => v != null ? v : '-' }
        ];
      case 'effectchips':
        return [
          { key: 'level', header: 'Lvl', width: '45px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Mindforce?.Level, format: (v) => v != null ? v : '-' },
          { key: 'range', header: 'Rng', width: '50px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Range, format: (v) => v != null ? v : '-' }
        ];
      case 'misctools':
        return [
          { key: 'tt', header: 'TT', width: '60px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 0, 2) : '-' },
          { key: 'decay', header: 'Dec', width: '55px', filterPlaceholder: '<0.5', getValue: (item) => item.Properties?.Economy?.Decay, format: (v) => v != null ? v.toFixed(2) : '-' }
        ];
      default:
        // All tools view - show TT and weight as generic columns
        return [
          { key: 'tt', header: 'TT', width: '60px', filterPlaceholder: '>10', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 0, 2) : '-' },
          { key: 'weight', header: 'Wt', width: '50px', filterPlaceholder: '<5', getValue: (item) => item.Properties?.Weight, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
    }
  }

  $: navTableColumns = getNavTableColumns(additional.type);

  // Custom href generator for items - handles _type property for "all items" view
  function getItemHref(item, basePath) {
    const type = item._type || additional.type;
    if (type) {
      return `/items/tools/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Tools', href: '/items/tools' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + 's', href: `/items/tools/${additional.type}` }] : []),
    ...(tool ? [{ label: tool.Name }] : [])
  ];

  // SEO
  $: seoDescription = tool?.Properties?.Description ||
    `${tool?.Name || 'Tool'} - ${getTypeName(additional.type)} in Entropia Universe.`;

  $: canonicalUrl = tool
    ? `https://entropianexus.com/items/tools/${additional.type}/${encodeURIComponentSafe(tool.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/tools/${additional.type}`
    : 'https://entropianexus.com/items/tools';

  // Check if item is tierable (not Limited)
  $: isTierable = tool && !hasItemTag(tool.Name, 'L') && ['finders', 'excavators'].includes(additional.type);
  $: hasEquipEffects = tool?.EffectsOnEquip?.length > 0;
  $: hasUseEffects = tool?.EffectsOnUse?.length > 0;

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    tiering: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-tool-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-tool-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== RELOAD/USES TOGGLE ==========
  let showReload = true;

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-tool-show-reload');
      if (stored !== null) {
        showReload = stored === 'true';
      }
    } catch (e) {}
  });

  function toggleReloadUses() {
    showReload = !showReload;
    try {
      localStorage.setItem('wiki-tool-show-reload', String(showReload));
    } catch (e) {}
  }

  // ========== CALCULATOR FUNCTIONS ==========
  function getTotalUses(item) {
    const maxTT = item?.Properties?.Economy?.MaxTT;
    const minTT = item?.Properties?.Economy?.MinTT ?? 0;
    const decay = item?.Properties?.Economy?.Decay;
    if (maxTT == null || decay == null || decay === 0) return null;
    return Math.floor((maxTT - minTT) / (decay / 100));
  }

  function getCost(item) {
    const decay = item?.Properties?.Economy?.Decay;
    const ammoBurn = item?.Properties?.Economy?.AmmoBurn;
    if (decay == null || ammoBurn == null) return null;
    return decay + ammoBurn / 100;
  }

  function getReload(item) {
    const upm = item?.Properties?.UsesPerMinute;
    if (upm == null || upm === 0) return null;
    return 60 / upm;
  }

  function calcEfficiencyPerPed(item) {
    const eff = item?.Properties?.Efficiency;
    const decay = item?.Properties?.Economy?.Decay;
    if (eff == null || decay == null || decay === 0) return null;
    return eff / (decay / 100);
  }

  function calcEfficiencyPerSec(item) {
    const eff = item?.Properties?.Efficiency;
    const reload = getReload(item);
    if (eff == null || reload == null || reload === 0) return null;
    return eff / reload;
  }

  // Reactive calculations
  $: totalUses = getTotalUses(tool);
  $: cost = getCost(tool);
  $: reload = getReload(tool);
  $: effPerPed = calcEfficiencyPerPed(tool);
  $: effPerSec = calcEfficiencyPerSec(tool);
</script>

<WikiSEO
  title={tool?.Name || `${getTypeName(additional.type)}s`}
  description={seoDescription}
  entityType={getEntityType(additional.type)}
  entity={tool}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Tools"
  {breadcrumbs}
  entity={tool}
  entityType={getEntityType(additional.type)}
  basePath="/items/tools/{additional.type || ''}"
  {navItems}
  {navFilters}
  {navTableColumns}
  navGetItemHref={getItemHref}
  {user}
  editable={true}
>
  {#if tool}
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
          <div class="infobox-title">{tool.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">{getTypeName(additional.type)}</span>
          </div>
        </div>

        <!-- Tier-1 Stats (type-specific primary stats) -->
        <div class="stats-section tier-1">
          {#if additional.type === 'refiners'}
            <div class="stat-row primary">
              <span class="stat-label">TT Value</span>
              <span class="stat-value">{tool.Properties?.Economy?.MaxTT != null ? `${clampDecimals(tool.Properties.Economy.MaxTT, 2, 4)} PED` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Decay</span>
              <span class="stat-value">{tool.Properties?.Economy?.Decay != null ? `${tool.Properties.Economy.Decay.toFixed(4)} PEC` : 'N/A'}</span>
            </div>
          {:else if additional.type === 'scanners'}
            <div class="stat-row primary">
              <span class="stat-label">Range</span>
              <span class="stat-value">{tool.Properties?.Range != null ? `${tool.Properties.Range}m` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Uses/min</span>
              <span class="stat-value">{tool.Properties?.UsesPerMinute != null ? clampDecimals(tool.Properties.UsesPerMinute, 0, 2) : 'N/A'}</span>
            </div>
          {:else if additional.type === 'finders'}
            <div class="stat-row primary">
              <span class="stat-label">Depth</span>
              <span class="stat-value">{tool.Properties?.Depth != null ? `${tool.Properties.Depth}m` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Range</span>
              <span class="stat-value">{tool.Properties?.Range != null ? `${tool.Properties.Range}m` : 'N/A'}</span>
            </div>
          {:else if additional.type === 'excavators'}
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{tool.Properties?.Efficiency ?? 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Eff/PED</span>
              <span class="stat-value">{effPerPed != null ? effPerPed.toFixed(1) : 'N/A'}</span>
            </div>
          {:else if additional.type === 'teleportationchips'}
            <div class="stat-row primary">
              <span class="stat-label">Range</span>
              <span class="stat-value">{tool.Properties?.Range != null ? `${tool.Properties.Range}km` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Cost/Use</span>
              <span class="stat-value">{cost != null ? `${cost.toFixed(2)} PEC` : 'N/A'}</span>
            </div>
          {:else if additional.type === 'effectchips'}
            <div class="stat-row primary">
              <span class="stat-label">Level</span>
              <span class="stat-value">{tool.Properties?.Mindforce?.Level ?? 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Range</span>
              <span class="stat-value">{tool.Properties?.Range != null ? `${tool.Properties.Range}m` : 'N/A'}</span>
            </div>
          {:else}
            <!-- misctools -->
            <div class="stat-row primary">
              <span class="stat-label">TT Value</span>
              <span class="stat-value">{tool.Properties?.Economy?.MaxTT != null ? `${clampDecimals(tool.Properties.Economy.MaxTT, 2, 4)} PED` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Decay</span>
              <span class="stat-value">{tool.Properties?.Economy?.Decay != null ? `${tool.Properties.Economy.Decay.toFixed(4)} PEC` : 'N/A'}</span>
            </div>
          {/if}
        </div>

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{tool.Properties?.Weight != null ? `${clampDecimals(tool.Properties.Weight, 1, 6)}kg` : 'N/A'}</span>
          </div>
          {#if additional.type === 'teleportationchips' || additional.type === 'effectchips'}
            <div class="stat-row">
              <span class="stat-label">Range</span>
              <span class="stat-value">{tool.Properties?.Range != null ? `${tool.Properties.Range}${additional.type === 'teleportationchips' ? 'km' : 'm'}` : 'N/A'}</span>
            </div>
          {/if}
          {#if additional.type !== 'refiners' && additional.type !== 'misctools'}
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div class="stat-row toggleable" on:click={toggleReloadUses} title="Click to toggle between Reload and Uses/min">
              {#if showReload}
                <span class="stat-label">Reload <span class="toggle-hint">⇄</span></span>
                <span class="stat-value">{reload != null ? `${reload.toFixed(2)}s` : 'N/A'}</span>
              {:else}
                <span class="stat-label">Uses/min <span class="toggle-hint">⇄</span></span>
                <span class="stat-value">{tool.Properties?.UsesPerMinute != null ? clampDecimals(tool.Properties.UsesPerMinute, 0, 2) : 'N/A'}</span>
              {/if}
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Total Uses</span>
            <span class="stat-value">{totalUses != null ? totalUses.toLocaleString() : 'N/A'}</span>
          </div>
        </div>

        <!-- Effects on Use (effect chips) - placed right after General -->
        {#if additional.type === 'effectchips' && hasUseEffects}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects on Use</h4>
            {#each tool.EffectsOnUse.sort((a,b) => a.Name.localeCompare(b.Name)) as effect}
              <div class="stat-row">
                <span class="stat-label">{effect.Name}</span>
                <span class="stat-value effect-value">{effect.Values.Strength}{effect.Values.Unit} for {getTimeString(effect.Values.DurationSeconds)}</span>
              </div>
            {/each}
          </div>
        {/if}

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Max TT</span>
            <span class="stat-value">{tool.Properties?.Economy?.MaxTT != null ? `${clampDecimals(tool.Properties.Economy.MaxTT, 2, 8)} PED` : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min TT</span>
            <span class="stat-value">{tool.Properties?.Economy?.MinTT != null ? `${clampDecimals(tool.Properties.Economy.MinTT, 2, 8)} PED` : '0.00 PED'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Decay</span>
            <span class="stat-value">{tool.Properties?.Economy?.Decay != null ? `${tool.Properties.Economy.Decay.toFixed(4)} PEC` : 'N/A'}</span>
          </div>
          {#if additional.type === 'finders'}
            <div class="stat-row">
              <span class="stat-label">Ammo</span>
              <span class="stat-value">Survey Probe</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Ammo Burn</span>
              <span class="stat-value">{tool.Properties?.Economy?.AmmoBurn ?? 'N/A'}/{(tool.Properties?.Economy?.AmmoBurn ?? 0) * 2}/{(tool.Properties?.Economy?.AmmoBurn ?? 0) * 3}</span>
            </div>
          {:else if additional.type === 'teleportationchips' || additional.type === 'effectchips'}
            <div class="stat-row">
              <span class="stat-label">Ammo</span>
              <span class="stat-value">{tool.Ammo?.Name ?? 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Ammo Burn</span>
              <span class="stat-value">{tool.Properties?.Economy?.AmmoBurn ?? 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cost/Use</span>
              <span class="stat-value">{cost != null ? `${cost.toFixed(2)} PEC` : 'N/A'}</span>
            </div>
            {#if additional.type === 'teleportationchips' && tool.Properties?.Range}
              <div class="stat-row">
                <span class="stat-label">Cost/km</span>
                <span class="stat-value">{cost != null ? `${(cost / tool.Properties.Range).toFixed(2)} PEC/km` : 'N/A'}</span>
              </div>
            {/if}
          {/if}
        </div>

        <!-- Mining Stats (finders/excavators) -->
        {#if additional.type === 'finders' || additional.type === 'excavators'}
          <div class="stats-section">
            <h4 class="section-title">Mining</h4>
            {#if additional.type === 'finders'}
              <div class="stat-row">
                <span class="stat-label">Depth</span>
                <span class="stat-value">{tool.Properties?.Depth != null ? `${tool.Properties.Depth}m` : 'N/A'}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Range</span>
                <span class="stat-value">{tool.Properties?.Range != null ? `${tool.Properties.Range}m` : 'N/A'}</span>
              </div>
            {:else}
              <div class="stat-row">
                <span class="stat-label">Efficiency</span>
                <span class="stat-value">{tool.Properties?.Efficiency ?? 'N/A'}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Efficiency/PED</span>
                <span class="stat-value">{effPerPed != null ? effPerPed.toFixed(1) : 'N/A'}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">Efficiency/s</span>
                <span class="stat-value">{effPerSec != null ? effPerSec.toFixed(2) : 'N/A'}</span>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Mindforce Stats (TP/Effect chips) -->
        {#if additional.type === 'teleportationchips' || additional.type === 'effectchips'}
          <div class="stats-section">
            <h4 class="section-title">Mindforce</h4>
            <div class="stat-row">
              <span class="stat-label">Level</span>
              <span class="stat-value">{tool.Properties?.Mindforce?.Level ?? 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Concentration</span>
              <span class="stat-value">{tool.Properties?.Mindforce?.Concentration != null ? `${tool.Properties.Mindforce.Concentration}s` : 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cooldown</span>
              <span class="stat-value">{tool.Properties?.Mindforce?.Cooldown != null ? `${tool.Properties.Mindforce.Cooldown}s` : 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cooldown Group</span>
              <span class="stat-value">{tool.Properties?.Mindforce?.CooldownGroup ?? 'N/A'}</span>
            </div>
          </div>
        {/if}

        <!-- Skilling Info -->
        {#if additional.type !== 'scanners' && additional.type !== 'refiners'}
          <div class="stats-section">
            <h4 class="section-title">Skilling</h4>
            {#if tool.Properties?.Skill?.IsSiB !== undefined}
              <div class="stat-row">
                <span class="stat-label">SiB</span>
                <span class="stat-value" class:highlight-yes={tool.Properties?.Skill?.IsSiB}>{tool.Properties?.Skill?.IsSiB ? 'Yes' : 'No'}</span>
              </div>
            {/if}
            {#if additional.type === 'finders'}
              <div class="stat-row">
                <span class="stat-label">Professions</span>
                <span class="stat-value">Prospector, Surveyor, Treasure Hunter</span>
              </div>
            {:else if additional.type === 'excavators'}
              <div class="stat-row">
                <span class="stat-label">Professions</span>
                <span class="stat-value">Driller, Miner, Archaeologist</span>
              </div>
            {:else if tool.Profession?.Name}
              <div class="stat-row">
                <span class="stat-label">Profession</span>
                <span class="stat-value">
                  <a href={getTypeLink(tool.Profession.Name, 'Profession')} class="profession-link">{tool.Profession.Name}</a>
                </span>
              </div>
            {/if}
            {#if tool.Properties?.Skill?.LearningIntervalStart != null || tool.Properties?.Skill?.LearningIntervalEnd != null}
              <div class="stat-row">
                <span class="stat-label">Level Range</span>
                <span class="stat-value">{tool.Properties?.Skill?.LearningIntervalStart?.toFixed(1) ?? '?'} - {tool.Properties?.Skill?.LearningIntervalEnd?.toFixed(1) ?? '?'}</span>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Effects on Equip (finders/excavators) -->
        {#if hasEquipEffects}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects on Equip</h4>
            {#each tool.EffectsOnEquip.sort((a,b) => a.Name.localeCompare(b.Name)) as effect}
              <div class="stat-row">
                <span class="stat-label">{effect.Name}</span>
                <span class="stat-value effect-value">{effect.Values.Strength}{effect.Values.Unit}</span>
              </div>
            {/each}
          </div>
        {/if}

      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{tool.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if tool.Properties?.Description}
            <div class="description-content">{tool.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {tool.Name} is a {getTypeName(additional.type).toLowerCase()} used in various activities in Entropia Universe.
            </div>
          {/if}
        </div>

        <!-- Tiering Section (finders/excavators, non-limited only) -->
        {#if isTierable && additional.tierInfo}
          <DataSection
            title="Tiers"
            icon=""
            bind:expanded={panelStates.tiering}
            subtitle="{additional.tierInfo?.length || 0} tiers"
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
      <h2>{additional.type ? getTypeName(additional.type) + 's' : 'Tools'}</h2>
      <p>Select a {additional.type ? getTypeName(additional.type).toLowerCase() : 'tool'} from the list to view details.</p>
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

  .stat-value.highlight-yes {
    color: var(--success-color, #4ade80);
  }

  .stat-value.effect-value {
    color: var(--accent-color, #4a9eff);
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

  .profession-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .profession-link:hover {
    text-decoration: underline;
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

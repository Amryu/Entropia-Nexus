<!--
  @component MobLocations
  Displays a table of mob spawn locations with coordinates and map links.
  Uses FancyTable for consistent styling with custom components for interactive elements.
-->
<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import WaypointCopyButton from '$lib/components/wiki/WaypointCopyButton.svelte';
  import MapLinkButton from './MapLinkButton.svelte';
  import { encodeURIComponentSafe } from '$lib/util';

  export let mobName = '';
  export let mobSpawns = [];

  function getLowestMaturityLevel(spawnMaturities, mob) {
    const levels = (spawnMaturities || [])
      .filter(sm => sm.Maturity?.Mob?.Name === mob)
      .map(sm => sm.Maturity?.Properties?.Level)
      .filter(l => l != null);
    return levels.length > 0 ? Math.min(...levels) : Infinity;
  }

  function formatMaturitiesRange(spawnMaturities, mob) {
    const mats = (spawnMaturities || [])
      .filter(sm => sm.Maturity?.Mob?.Name === mob);
    if (mats.length === 0) return 'All';

    const nonBoss = mats
      .filter(m => !m.Maturity?.Properties?.Boss)
      .sort((a, b) => (a.Maturity?.Properties?.Level ?? Infinity) - (b.Maturity?.Properties?.Level ?? Infinity));
    const bosses = mats.filter(m => m.Maturity?.Properties?.Boss);

    let result = '';
    if (nonBoss.length === 1) {
      result = nonBoss[0].Maturity?.Name || '<No Name>';
    } else if (nonBoss.length >= 2) {
      result = `${nonBoss[0].Maturity?.Name}-${nonBoss[nonBoss.length - 1].Maturity?.Name}`;
    }

    if (bosses.length > 0) {
      const bossNames = bosses.map(b => b.Maturity?.Name || '<No Name>').join(', ');
      result = result ? `${result}, ${bossNames}` : bossNames;
    }

    return result || 'All';
  }

  // Sort spawns by lowest maturity level of the current mob
  $: sortedSpawns = [...(mobSpawns || [])].sort((a, b) => {
    return getLowestMaturityLevel(a.Maturities, mobName) - getLowestMaturityLevel(b.Maturities, mobName);
  });

  const densityLabels = { 1: 'Low', 2: 'Medium', 3: 'High' };
  const densityColors = {
    1: { bg: 'rgba(202, 138, 4, 0.25)', color: '#eab308' },
    2: { bg: 'rgba(22, 163, 74, 0.25)', color: '#22c55e' },
    3: { bg: 'rgba(220, 38, 38, 0.25)', color: '#ef4444' }
  };

  function getDensityStyle(density) {
    const style = densityColors[density] || { bg: 'var(--hover-color)', color: 'var(--text-muted)' };
    return `background-color: ${style.bg}; color: ${style.color};`;
  }

  function getWaypoint(planet, x, y, z, name) {
    const technicalName = planet?.Properties?.TechnicalName || planet?.Name || 'Unknown';
    return `[${technicalName}, ${x}, ${y}, ${z}, ${name}]`;
  }

  // Transform data for FancyTable
  $: tableData = sortedSpawns.map(spawn => {
    const coords = spawn.Properties?.Coordinates || spawn.Properties?.Data || {};
    const x = coords.Longitude || coords.x || 0;
    const y = coords.Latitude || coords.y || 0;
    const z = coords.Altitude || 0;
    const waypoint = getWaypoint(spawn.Planet, x, y, z, mobName);
    const density = spawn.Properties?.Density;
    const otherMobs = [...new Set(spawn.Maturities?.map(sm => sm.Maturity?.Mob?.Name).filter(n => n && n !== mobName) || [])];

    return {
      id: spawn.Id,
      maturities: formatMaturitiesRange(spawn.Maturities, mobName),
      otherMobs: otherMobs,
      otherMobsHtml: otherMobs.length > 0
        ? otherMobs.map(m => `<a href="/information/mobs/${encodeURIComponentSafe(m)}" class="wiki-link-normal">${m}</a>`).join(', ')
        : '<span style="color: var(--text-muted); font-style: italic;">None</span>',
      waypoint: waypoint,
      density: density,
      densityLabel: density ? densityLabels[density] || 'N/A' : 'N/A',
      densityStyle: getDensityStyle(density),
      mapLink: `/maps/${(spawn.Planet?.Name || 'calypso').toLowerCase()}/${spawn.Id}`
    };
  });

  const columns = [
    {
      key: 'maturities',
      header: 'Maturities',
      main: true,
      formatter: (value) => `<span style="font-weight: 500;">${value}</span>`
    },
    {
      key: 'otherMobsHtml',
      header: 'Other Mobs',
      formatter: (value) => value
    },
    {
      key: 'waypoint',
      header: 'Location',
      component: WaypointCopyButton
    },
    {
      key: 'densityLabel',
      header: 'Density',
      formatter: (value, row) => row.density
        ? `<span style="display: inline-block; padding: 2px 8px; font-size: 11px; border-radius: 4px; font-weight: 500; ${row.densityStyle}">${value}</span>`
        : 'N/A'
    },
    {
      key: 'mapLink',
      header: 'Map',
      component: MapLinkButton
    }
  ];
</script>

<div class="locations-table-container">
  {#if !mobSpawns || mobSpawns.length === 0}
    <div class="no-data">No location data available.</div>
  {:else}
    <FancyTable
      {columns}
      data={tableData}
      searchable={tableData.length > 10}
      sortable={false}
      rowHeight={32}
      compact
      emptyMessage="No location data available."
    />
  {/if}
</div>

<style>
  .locations-table-container {
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  .locations-table-container :global(.fancy-table-container) {
    max-height: 596px;
  }

  @media (max-width: 899px) {
    .locations-table-container :global(.fancy-table-container) {
      max-height: 499px;
    }
  }

  .no-data {
    color: var(--text-muted, #999);
    font-style: italic;
    padding: 20px;
    text-align: center;
  }
</style>

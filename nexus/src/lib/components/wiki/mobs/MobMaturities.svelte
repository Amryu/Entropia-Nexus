<!--
  @component MobMaturities
  Displays a table of mob maturities with stats like HP, Level, Damage, Defense, etc.
  Uses FancyTable for consistent styling.
-->
<script>
  // @ts-nocheck
  import { tick, untrack } from 'svelte';
  import FancyTable from '$lib/components/FancyTable.svelte';

  /**
   * @typedef {Object} Props
   * @property {any} [maturities]
   * @property {any} [type]
   * @property {any} [selectedMaturityId]
   */

  /** @type {Props} */
  let { maturities = [], type = null, selectedMaturityId = null, loadoutStats = null } = $props();
  let tableContainer = $state();
  let lastSelectedKey = null;

  // Sort maturities: non-bosses first, by Level then Health (nulls at end)
  let sortedMaturities = $derived(maturities ? [...maturities].sort((a, b) => {
    const aIsBoss = a.Properties?.Boss === true;
    const bIsBoss = b.Properties?.Boss === true;

    // Bosses always at the bottom
    if (aIsBoss !== bIsBoss) {
      return aIsBoss ? 1 : -1;
    }

    const aHp = a.Properties?.Health;
    const aLvl = a.Properties?.Level;
    const bHp = b.Properties?.Health;
    const bLvl = b.Properties?.Level;

    const aHasValue = aLvl != null;
    const bHasValue = bLvl != null;

    // Items with null Level go to the end (within their boss group)
    if (aHasValue !== bHasValue) {
      return aHasValue ? -1 : 1;
    }

    // Both have null Level - treat as equal
    if (!aHasValue && !bHasValue) {
      return 0;
    }

    // Primary: Level ascending
    if (aLvl !== bLvl) return aLvl - bLvl;

    // Secondary: Health ascending (tiebreaker for same level)
    if (aHp != null && bHp != null) return aHp - bHp;
    if (aHp != null) return -1;
    if (bHp != null) return 1;
    return 0;
  }) : []);

  function getTotalDamage(attack) {
    return attack?.TotalDamage ?? null;
  }

  function getTotalDefense(maturity) {
    const def = maturity.Properties?.Defense;
    if (!def) return 0;
    return (def.Impact || 0) + (def.Cut || 0) + (def.Stab || 0) +
           (def.Penetration || 0) + (def.Shrapnel || 0) + (def.Burn || 0) +
           (def.Cold || 0) + (def.Acid || 0) + (def.Electric || 0);
  }

  function getDamageComposition(attack) {
    if (!attack?.Damage) return '';
    return Object.entries(attack.Damage)
      .filter(([key, value]) => value != null && value > 0)
      .map(([key, value]) => `${key}: ${value}%`)
      .join(', ');
  }

  let isAsteroid = $derived(type === 'Asteroid');

  // Transform data for FancyTable
  let tableData = $derived(sortedMaturities.map(maturity => {
    const hpPerLevel = maturity.Properties?.Health != null && maturity.Properties?.Level != null && maturity.Properties.Level > 0
      ? (maturity.Properties.Health / maturity.Properties.Level).toFixed(2)
      : null;
    const primaryAttack = maturity.Attacks?.find(a => a.Name === 'Primary') || maturity.Attacks?.[0];
    const secondaryAttack = maturity.Attacks?.find(a => a.Name === 'Secondary') || maturity.Attacks?.[1];
    const tertiaryAttack = maturity.Attacks?.find(a => a.Name === 'Tertiary') || maturity.Attacks?.[2];

    // Loadout-based kill stats
    const hp = maturity.Properties?.Health;
    let costToKill = null;
    let shotsToKill = null;
    let timeToKill = null;

    if (loadoutStats && hp != null) {
      const { dpp, effectiveDamage, reload } = loadoutStats;
      if (effectiveDamage > 0) {
        shotsToKill = Math.ceil(hp / effectiveDamage);
        if (reload > 0) {
          timeToKill = (shotsToKill - 1) * reload;
        }
      }
      if (dpp > 0) {
        costToKill = (hp / dpp) / 100; // PEC → PED
      }
    }

    return {
      id: maturity?.Id ?? null,
      name: sortedMaturities.length === 1 && (!maturity.Name || maturity.Name.trim().length === 0)
        ? 'Single Maturity'
        : maturity.Name || 'Unknown',
      level: maturity.Properties?.Level,
      hp,
      hpPerLevel: hpPerLevel,
      boss: maturity.Properties?.Boss === true,
      primaryDamage: getTotalDamage(primaryAttack),
      primaryTooltip: getDamageComposition(primaryAttack),
      secondaryDamage: getTotalDamage(secondaryAttack),
      secondaryTooltip: getDamageComposition(secondaryAttack),
      tertiaryDamage: getTotalDamage(tertiaryAttack),
      tertiaryTooltip: getDamageComposition(tertiaryAttack),
      defense: getTotalDefense(maturity),
      tameable: maturity.Properties?.Taming?.IsTameable || maturity.Properties?.TamingLevel > 0,
      tamingLevel: maturity.Properties?.Taming?.TamingLevel || maturity.Properties?.TamingLevel,
      costToKill,
      shotsToKill,
      timeToKill,
    };
  }));

  // Row class function for boss highlighting
  function getRowClass(row) {
    const classes = [];
    if (row.boss) classes.push('boss-row');
    if (selectedMaturityId != null && String(row.id) === String(selectedMaturityId)) {
      classes.push('selected-row');
    }
    return classes.length > 0 ? classes.join(' ') : null;
  }

  function scrollToSelectedRow() {
    if (selectedMaturityId == null || !tableContainer) return;

    const selectedIndex = tableData.findIndex(row => String(row.id) === String(selectedMaturityId));
    if (selectedIndex < 0) return;

    const tableBody = tableContainer.querySelector('.table-body');
    if (!tableBody) return;

    const rowTop = selectedIndex * 32;
    const targetScrollTop = Math.max(0, rowTop - Math.max(0, (tableBody.clientHeight - 32) / 2));
    tableBody.scrollTop = targetScrollTop;
  }

  let selectedKey = $derived(selectedMaturityId != null ? `${selectedMaturityId}-${tableData.length}` : null);
  $effect(() => {
    if (selectedKey && selectedKey !== untrack(() => lastSelectedKey)) {
      lastSelectedKey = selectedKey;
      tick().then(scrollToSelectedRow);
    }
  });

  // Base columns for asteroids
  const baseColumns = [
    {
      key: 'name',
      header: 'Name',
      main: true,
      width: '120px',
      formatter: (value) => `<span style="font-weight: 500;">${value}</span>`
    },
    {
      key: 'level',
      header: 'Level',
      sortable: true,
      formatter: (value) => value ?? 'N/A'
    },
    {
      key: 'hp',
      header: 'HP',
      sortable: true,
      formatter: (value) => value != null ? `<span style="font-family: monospace;">${value}</span>` : 'N/A'
    },
    {
      key: 'hpPerLevel',
      header: 'HP/Lv',
      sortable: true,
      formatter: (value) => value != null ? `<span style="font-family: monospace;">${value}</span>` : 'N/A'
    }
  ];

  // Additional columns for non-asteroids
  const mobColumns = [
    {
      key: 'boss',
      header: 'Boss',
      formatter: (value) => value ? 'Yes' : 'No'
    },
    {
      key: 'primaryDamage',
      header: 'Primary',
      sortable: true,
      formatter: (value, row) => value != null
        ? `<span style="text-decoration: underline; text-decoration-style: dotted; cursor: help;" title="${row.primaryTooltip}">${value}</span>`
        : 'N/A'
    },
    {
      key: 'secondaryDamage',
      header: 'Secondary',
      formatter: (value, row) => value != null
        ? `<span style="text-decoration: underline; text-decoration-style: dotted; cursor: help;" title="${row.secondaryTooltip}">${value}</span>`
        : 'N/A'
    },
    {
      key: 'tertiaryDamage',
      header: 'Tertiary',
      formatter: (value, row) => value != null
        ? `<span style="text-decoration: underline; text-decoration-style: dotted; cursor: help;" title="${row.tertiaryTooltip}">${value}</span>`
        : 'N/A'
    },
    {
      key: 'defense',
      header: 'Defense',
      sortable: true,
      formatter: (value) => `<span style="font-family: monospace;">${value}</span>`
    },
    {
      key: 'tameable',
      header: 'Tameable',
      formatter: (value, row) => value
        ? `<span style="color: var(--success-color, #4ade80); font-weight: 500;">Lvl ${row.tamingLevel}</span>`
        : 'No'
    }
  ];

  let loadoutColumns = $derived(loadoutStats ? [
    {
      key: 'costToKill',
      header: 'Cost/kill',
      sortable: true,
      formatter: (value) => value != null
        ? `<span style="font-family: monospace;">${value.toFixed(2)} PED</span>`
        : 'N/A'
    },
    {
      key: 'shotsToKill',
      header: 'Shots/kill',
      sortable: true,
      formatter: (value) => value != null
        ? `<span style="font-family: monospace;">${value}</span>`
        : 'N/A'
    },
    {
      key: 'timeToKill',
      header: 'Time/kill',
      sortable: true,
      formatter: (value) => value != null
        ? `<span style="font-family: monospace;">${value.toFixed(1)}s</span>`
        : 'N/A'
    }
  ] : []);

  let columns = $derived(isAsteroid
    ? [...baseColumns, ...loadoutColumns]
    : [...baseColumns, ...mobColumns, ...loadoutColumns]
  );
</script>

<div class="maturities-table-container" bind:this={tableContainer}>
  {#if !sortedMaturities || sortedMaturities.length === 0}
    <div class="no-data">No maturity data available.</div>
  {:else}
    <FancyTable
      {columns}
      data={tableData}
      searchable={false}
      sortable={true}
      rowHeight={32}
      compact
      fitContent
      rowClass={getRowClass}
      emptyMessage="No maturity data available."
    />
  {/if}
</div>

<style>
  .maturities-table-container {
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  .maturities-table-container :global(.fancy-table-container) {
    max-height: 596px;
  }

  @media (max-width: 899px) {
    .maturities-table-container :global(.fancy-table-container) {
      max-height: 499px;
    }
  }

  /* Boss row styling - subtle red background */
  .maturities-table-container :global(.table-row.boss-row) {
    background-color: rgba(220, 38, 38, 0.15);
  }

  .maturities-table-container :global(.table-row.boss-row:hover) {
    background-color: rgba(220, 38, 38, 0.25);
  }

  .maturities-table-container :global(.table-row.selected-row) {
    box-shadow: inset 0 0 0 2px var(--accent-color, #4a9eff);
    background-color: rgba(74, 158, 255, 0.18);
  }

  .maturities-table-container :global(.table-row.selected-row:hover) {
    background-color: rgba(74, 158, 255, 0.28);
  }

  .no-data {
    color: var(--text-muted, #999);
    font-style: italic;
    padding: 20px;
    text-align: center;
  }
</style>

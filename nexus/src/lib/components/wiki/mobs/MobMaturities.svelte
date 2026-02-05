<!--
  @component MobMaturities
  Displays a table of mob maturities with stats like HP, Level, Damage, Defense, etc.
  Uses FancyTable for consistent styling.
-->
<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';

  export let maturities = [];
  export let type = null;

  // Sort maturities: non-bosses first, by HP*Level (nulls at end)
  $: sortedMaturities = maturities ? [...maturities].sort((a, b) => {
    const aIsBoss = a.Properties?.Boss === true;
    const bIsBoss = b.Properties?.Boss === true;

    // Bosses always at the bottom
    if (aIsBoss !== bIsBoss) {
      return aIsBoss ? 1 : -1;
    }

    // Calculate HP * Level, treating null as Infinity (sort to end)
    const aHp = a.Properties?.Health;
    const aLvl = a.Properties?.Level;
    const bHp = b.Properties?.Health;
    const bLvl = b.Properties?.Level;

    const aHasValue = aHp != null && aLvl != null;
    const bHasValue = bHp != null && bLvl != null;

    // Items with null values go to the end (within their boss group)
    if (aHasValue !== bHasValue) {
      return aHasValue ? -1 : 1;
    }

    // Both have null values - treat as equal
    if (!aHasValue && !bHasValue) {
      return 0;
    }

    // Both have values - sort by HP * Level ascending
    return (aHp * aLvl) - (bHp * bLvl);
  }) : [];

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

  $: isAsteroid = type === 'Asteroid';

  // Transform data for FancyTable
  $: tableData = sortedMaturities.map(maturity => {
    const hpPerLevel = maturity.Properties?.Health != null && maturity.Properties?.Level != null && maturity.Properties.Level > 0
      ? (maturity.Properties.Health / maturity.Properties.Level).toFixed(2)
      : null;
    const primaryAttack = maturity.Attacks?.find(a => a.Name === 'Primary') || maturity.Attacks?.[0];
    const secondaryAttack = maturity.Attacks?.find(a => a.Name === 'Secondary') || maturity.Attacks?.[1];
    const tertiaryAttack = maturity.Attacks?.find(a => a.Name === 'Tertiary') || maturity.Attacks?.[2];

    return {
      name: sortedMaturities.length === 1 && (!maturity.Name || maturity.Name.trim().length === 0)
        ? 'Single Maturity'
        : maturity.Name || 'Unknown',
      level: maturity.Properties?.Level,
      hp: maturity.Properties?.Health,
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
      tamingLevel: maturity.Properties?.Taming?.TamingLevel || maturity.Properties?.TamingLevel
    };
  });

  // Row class function for boss highlighting
  function getRowClass(row) {
    return row.boss ? 'boss-row' : null;
  }

  // Base columns for asteroids
  const baseColumns = [
    {
      key: 'name',
      header: 'Name',
      width: '120px',
      main: true,  // Grow to fill available space
      formatter: (value) => `<span style="font-weight: 500;">${value}</span>`
    },
    {
      key: 'level',
      header: 'Level',
      width: '70px',
      sortable: true,
      formatter: (value) => value ?? 'N/A'
    },
    {
      key: 'hp',
      header: 'HP',
      width: '80px',
      sortable: true,
      formatter: (value) => value != null ? `<span style="font-family: monospace;">${value}</span>` : 'N/A'
    },
    {
      key: 'hpPerLevel',
      header: 'HP/Lv',
      width: '80px',
      sortable: true,
      formatter: (value) => value != null ? `<span style="font-family: monospace;">${value}</span>` : 'N/A'
    }
  ];

  // Additional columns for non-asteroids
  const mobColumns = [
    {
      key: 'boss',
      header: 'Boss',
      width: '60px',
      hideOnMobile: true,
      formatter: (value) => value ? 'Yes' : 'No'
    },
    {
      key: 'primaryDamage',
      header: 'Primary',
      width: '80px',
      sortable: true,
      formatter: (value, row) => value != null
        ? `<span style="text-decoration: underline; text-decoration-style: dotted; cursor: help;" title="${row.primaryTooltip}">${value}</span>`
        : 'N/A'
    },
    {
      key: 'secondaryDamage',
      header: 'Secondary',
      width: '90px',
      hideOnMobile: true,
      formatter: (value, row) => value != null
        ? `<span style="text-decoration: underline; text-decoration-style: dotted; cursor: help;" title="${row.secondaryTooltip}">${value}</span>`
        : 'N/A'
    },
    {
      key: 'tertiaryDamage',
      header: 'Tertiary',
      width: '80px',
      hideOnMobile: true,
      formatter: (value, row) => value != null
        ? `<span style="text-decoration: underline; text-decoration-style: dotted; cursor: help;" title="${row.tertiaryTooltip}">${value}</span>`
        : 'N/A'
    },
    {
      key: 'defense',
      header: 'Defense',
      width: '80px',
      sortable: true,
      hideOnMobile: true,
      formatter: (value) => `<span style="font-family: monospace;">${value}</span>`
    },
    {
      key: 'tameable',
      header: 'Tameable',
      width: '90px',
      hideOnMobile: true,
      formatter: (value, row) => value
        ? `<span style="color: var(--success-color, #4ade80); font-weight: 500;">Lvl ${row.tamingLevel}</span>`
        : 'No'
    }
  ];

  $: columns = isAsteroid ? baseColumns : [...baseColumns, ...mobColumns];
</script>

<div class="maturities-table-container">
  {#if !sortedMaturities || sortedMaturities.length === 0}
    <div class="no-data">No maturity data available.</div>
  {:else}
    <FancyTable
      {columns}
      data={tableData}
      searchable={false}
      sortable={true}
      rowHeight={40}
      rowClass={getRowClass}
      emptyMessage="No maturity data available."
    />
  {/if}
</div>

<style>
  .maturities-table-container {
    width: 100%;
  }

  .maturities-table-container :global(.fancy-table-container) {
    max-height: 500px;
  }

  /* Boss row styling - subtle red background */
  .maturities-table-container :global(.table-row.boss-row) {
    background-color: rgba(220, 38, 38, 0.15);
  }

  .maturities-table-container :global(.table-row.boss-row:hover) {
    background-color: rgba(220, 38, 38, 0.25);
  }

  .no-data {
    color: var(--text-muted, #999);
    font-style: italic;
    padding: 20px;
    text-align: center;
  }
</style>

<!--
  @component SkillProfessions
  Displays professions that are affected by this skill with their weights.
  Uses FancyTable for consistent styling.
-->
<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { encodeURIComponentSafe } from '$lib/util';

  export let professions = [];

  $: sortedProfessions = professions ? [...professions].sort((a, b) => {
    if (b.Weight !== a.Weight) return b.Weight - a.Weight;
    return a.Profession.Name.localeCompare(b.Profession.Name);
  }) : [];

  // Category badge colors
  const categoryColors = {
    'Combat': '#ef4444',
    'Mindforce': '#a855f7',
    'Resource Collecting': '#22c55e',
    'Manufacturing': '#f59e0b',
    'Miscellaneous': '#6b7280'
  };

  function getCategoryColor(category) {
    return categoryColors[category] || '#4a9eff';
  }

  // Transform data for FancyTable
  $: tableData = sortedProfessions.map(profEntry => ({
    name: profEntry.Profession.Name,
    nameLink: `/information/professions/${encodeURIComponentSafe(profEntry.Profession.Name)}`,
    category: profEntry.Profession.Properties?.Category || 'Unknown',
    categoryColor: getCategoryColor(profEntry.Profession.Properties?.Category),
    weight: profEntry.Weight
  }));

  const columns = [
    {
      key: 'name',
      header: 'Profession',
      main: true,
      formatter: (value, row) => `<a href="${row.nameLink}" class="wiki-link-normal">${value}</a>`
    },
    {
      key: 'category',
      header: 'Category',
      formatter: (value, row) => `<span style="display: inline-block; padding: 3px 8px; font-size: 10px; font-weight: 600; background-color: ${row.categoryColor}; color: white; border-radius: 4px; text-transform: uppercase;">${value}</span>`
    },
    {
      key: 'weight',
      header: 'Weight',
      sortable: true,
      formatter: (value) => `<span style="font-family: monospace; font-weight: 500;">${value}</span>`
    }
  ];
</script>

<div class="professions-table-container">
  {#if !sortedProfessions || sortedProfessions.length === 0}
    <div class="no-data">This skill does not contribute to any professions.</div>
  {:else}
    <FancyTable
      {columns}
      data={tableData}
      searchable={false}
      sortable={true}
      rowHeight={32}
      compact
      emptyMessage="This skill does not contribute to any professions."
    />
  {/if}
</div>

<style>
  .professions-table-container {
    width: 100%;
    max-width: 100%;
    min-height: 150px;
    overflow: hidden;
  }

  .professions-table-container :global(.fancy-table-container) {
    max-height: 596px;
  }

  @media (max-width: 899px) {
    .professions-table-container :global(.fancy-table-container) {
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

<!--
  @component ProfessionSkills
  Displays skill components that contribute to a profession with weight and HP increase.
  Uses FancyTable for consistent styling.
-->
<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { encodeURIComponentSafe } from '$lib/util';

  let { skills = [] } = $props();

  let sortedSkills = $derived(skills ? [...skills].sort((a, b) => b.Weight - a.Weight) : []);
  let totalWeight = $derived(sortedSkills.reduce((sum, s) => sum + (s.Weight || 0), 0));

  function getWeightPercent(weight) {
    if (!totalWeight || totalWeight === 0) return 0;
    return ((weight / totalWeight) * 100).toFixed(1);
  }

  // Transform data for FancyTable
  let tableData = $derived(sortedSkills.map(skillEntry => ({
    name: skillEntry.Skill.Name,
    nameLink: `/information/skills/${encodeURIComponentSafe(skillEntry.Skill.Name)}`,
    weight: skillEntry.Weight,
    percent: getWeightPercent(skillEntry.Weight),
    hpIncrease: skillEntry.Skill.Properties?.HpIncrease > 0 ? skillEntry.Skill.Properties.HpIncrease : null,
    isHidden: skillEntry.Skill.Properties?.IsHidden || false
  })));

  const columns = [
    {
      key: 'name',
      header: 'Skill',
      main: true,
      formatter: (value, row) => `<a href="${row.nameLink}" class="wiki-link-normal">${value}</a>`
    },
    {
      key: 'weight',
      header: 'Weight',
      sortable: true,
      formatter: (value) => `<span style="font-family: monospace;">${value}</span>`
    },
    {
      key: 'percent',
      header: '%',
      sortable: true,
      formatter: (value) => {
        return `<div style="display: flex; align-items: center; gap: 8px; position: relative; background-color: var(--bg-color, var(--primary-color)); border-radius: 4px; overflow: hidden; height: 20px; padding: 0 6px;">
          <div style="position: absolute; left: 0; top: 0; height: 100%; width: ${value}%; background-color: var(--accent-color, #4a9eff); opacity: 0.3; border-radius: 4px; min-width: 2px;"></div>
          <span style="position: relative; z-index: 1; font-size: 11px; font-family: monospace;">${value}%</span>
        </div>`;
      }
    },
    {
      key: 'hpIncrease',
      header: 'Points/HP',
      formatter: (value) => value != null ? `<span style="font-family: monospace;">${value}</span>` : 'N/A'
    },
    {
      key: 'isHidden',
      header: 'Hidden',
      formatter: (value) => value
        ? '<span style="display: inline-block; padding: 2px 6px; font-size: 10px; background-color: var(--warning-bg, rgba(251, 191, 36, 0.15)); color: var(--warning-color, #fbbf24); border-radius: 4px; font-weight: 500;">Yes</span>'
        : 'No'
    }
  ];

  // Footer with total
  let footer = $derived(tableData.length > 0 ? [
    { name: 'Total', weight: totalWeight, percent: '100.0', hpIncrease: '', isHidden: '' }
  ] : null);
</script>

<div class="skills-table-container">
  {#if !sortedSkills || sortedSkills.length === 0}
    <div class="no-data">No skill component data available.</div>
  {:else}
    <FancyTable
      {columns}
      data={tableData}
      {footer}
      footerLabelKey="name"
      searchable={false}
      sortable={true}
      rowHeight={32}
      compact
      fitContent
      emptyMessage="No skill component data available."
    />
  {/if}
</div>

<style>
  .skills-table-container {
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  .skills-table-container :global(.fancy-table-container) {
    max-height: 596px;
  }

  @media (max-width: 899px) {
    .skills-table-container :global(.fancy-table-container) {
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

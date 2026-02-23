<!--
  @component ProfessionUnlocks
  Displays skills that are unlocked by reaching certain levels in this profession.
  Uses FancyTable for consistent styling.
-->
<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { encodeURIComponentSafe } from '$lib/util';

  export let unlocks = [];

  $: sortedUnlocks = unlocks ? [...unlocks].sort((a, b) => a.Level - b.Level) : [];

  // Transform data for FancyTable
  $: tableData = sortedUnlocks.map(unlock => ({
    level: unlock.Level,
    skillName: unlock.Skill.Name,
    skillLink: `/information/skills/${encodeURIComponentSafe(unlock.Skill.Name)}`,
    isHidden: unlock.Skill.Properties?.IsHidden || false,
    hpIncrease: unlock.Skill.Properties?.HpIncrease > 0 ? unlock.Skill.Properties.HpIncrease : null
  }));

  const columns = [
    {
      key: 'level',
      header: 'Level',
      sortable: true,
      formatter: (value) => `<span style="display: inline-block; padding: 4px 10px; font-size: 12px; font-weight: 600; background: linear-gradient(135deg, #3a6d99 0%, #2d5577 100%); color: white; border-radius: 4px;">Lvl ${value}</span>`
    },
    {
      key: 'skillName',
      header: 'Skill Unlocked',
      main: true,
      formatter: (value, row) => {
        let html = `<a href="${row.skillLink}" class="wiki-link-normal">${value}</a>`;
        if (row.isHidden) {
          html += ' <span class="badge badge-subtle badge-warning">Hidden</span>';
        }
        return html;
      }
    },
    {
      key: 'hpIncrease',
      header: 'Points/HP',
      formatter: (value) => value != null ? `<span style="font-family: monospace;">${value}</span>` : 'N/A'
    }
  ];
</script>

<div class="unlocks-table-container">
  {#if !sortedUnlocks || sortedUnlocks.length === 0}
    <div class="no-data">This profession does not unlock any skills.</div>
  {:else}
    <FancyTable
      {columns}
      data={tableData}
      searchable={false}
      sortable={true}
      rowHeight={32}
      compact
      fitContent
      emptyMessage="This profession does not unlock any skills."
    />
  {/if}
</div>

<style>
  .unlocks-table-container {
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  .unlocks-table-container :global(.fancy-table-container) {
    max-height: 596px;
  }

  @media (max-width: 899px) {
    .unlocks-table-container :global(.fancy-table-container) {
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

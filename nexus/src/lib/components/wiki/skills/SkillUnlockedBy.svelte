<!--
  @component SkillUnlockedBy
  Displays professions that unlock this skill at certain levels.
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
    professionName: unlock.Profession.Name,
    professionLink: `/information/professions/${encodeURIComponentSafe(unlock.Profession.Name)}`,
    level: unlock.Level
  }));

  const columns = [
    {
      key: 'professionName',
      header: 'Profession',
      main: true,
      formatter: (value, row) => `<a href="${row.professionLink}" class="wiki-link-normal">${value}</a>`
    },
    {
      key: 'level',
      header: 'Unlock Level',
      sortable: true,
      formatter: (value) => `<span style="display: inline-block; padding: 4px 12px; font-size: 12px; font-weight: 600; background: linear-gradient(135deg, #3a6d99 0%, #2d5577 100%); color: white; border-radius: 4px;">Level ${value}</span>`
    }
  ];
</script>

<div class="unlocks-table-container">
  {#if !sortedUnlocks || sortedUnlocks.length === 0}
    <div class="no-data">This skill is not unlocked by any profession (always available).</div>
  {:else}
    <FancyTable
      {columns}
      data={tableData}
      searchable={false}
      sortable={true}
      rowHeight={32}
      compact
      fitContent
      emptyMessage="This skill is not unlocked by any profession."
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

<!--
  @component SkillUnlockedBy
  Displays professions that unlock this skill at certain levels.
  Uses FancyTable for consistent styling.
-->
<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { encodeURIComponentSafe } from '$lib/util';
  import ContributeCTA from '$lib/components/wiki/ContributeCTA.svelte';
  import { startEdit } from '$lib/stores/wikiEditState.js';

  let { unlocks = [] } = $props();

  let sortedUnlocks = $derived(unlocks ? [...unlocks].sort((a, b) => a.Level - b.Level) : []);

  // Transform data for FancyTable
  let tableData = $derived(sortedUnlocks.map(unlock => ({
    professionName: unlock.Profession.Name,
    professionLink: `/information/professions/${encodeURIComponentSafe(unlock.Profession.Name)}`,
    level: unlock.Level
  })));

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
    <ContributeCTA
      message="No unlock sources recorded - this skill is either always available or the data is missing."
      category="skill"
      onContribute={startEdit}
    />
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

</style>

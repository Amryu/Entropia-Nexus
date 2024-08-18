<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { encodeURIComponentSafe } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Table from '$lib/components/Table.svelte';

  export let data;

  let propertiesDataFunction = (skill) => {
    return {
      General: {
        Category: skill.Category?.Name ?? 'N/A',
        PointsPerHP: {
          Label: 'Points/HP',
          Tooltip: 'How many skill points are needed per HP increase.',
          Value: skill.Properties.HpIncrease
        },
        Hidden: skill.Properties.IsHidden ? 'Yes' : 'No'
      },
    };
  };

  let tableViewInfo = {
    columns: ['Name', 'Points/HP', 'Hidden'],
    columnWidths: ['1fr', '100px', '100px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Properties.HpIncrease > 0 ? item.Properties.HpIncrease : 'N/A',
        item.Properties.IsHidden ? 'Yes' : 'No'
      ];
    }
  };
</script>

<style>
  .container {
    display: grid;
    grid-template-columns: minmax(500px, 1fr) minmax(500px, 1fr);
    gap: 15px;
    align-items: start;
  }
</style>

<EntityViewer
  data={data}
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  editConfig={null}
  propertiesDataFunction={propertiesDataFunction}
  title='Skills'
  type='Skill'
  basePath='/information/skills'
  let:object>
  <div class="flex-item long-content">
    <h2>Professions</h2>
    <br />
    <div class="container">
      {#if object.Professions != null && object.Professions.length > 0}
      <Table
        title="Affected Professions"
        header={{
          values: ['Name', 'Weight', 'Category'],
          widths: ['1fr', 'max-content', 'max-content'],
        }}
        data={object.Professions.sort((a,b) => a.Profession.Name.localeCompare(b.Profession.Name)).map(profession => ({
          values: [
            profession.Profession.Name,
            profession.Weight,
            profession.Profession.Properties.Category ?? 'N/A'
          ],
          links: [`/information/professions/${encodeURIComponentSafe(profession.Profession.Name)}`, null, null, null]
        }))} />
      {:else}
        <div>No data available.</div>
      {/if}
      {#if object.Unlocks != null}
      <Table
        title="Unlocked By"
        header={{
          values: ['Name', 'Level'],
          widths: ['1fr', 'max-content']
        }}
        data={object.Unlocks.sort((a,b) => a.Profession.Name.localeCompare(b.Profession.Name)).map(profession => ({
          values: [
            profession.Profession.Name,
            profession.Level
          ],
          links: [`/information/professions/${encodeURIComponentSafe(profession.Profession.Name)}`, null, null, null]
        }))} />
      {/if}

    </div>
  </div>
</EntityViewer>
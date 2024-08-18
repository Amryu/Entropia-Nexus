<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { encodeURIComponentSafe } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Table from '$lib/components/Table.svelte';

  export let data;

  let propertiesDataFunction = (profession) => {
    return {
      General: {
        Category: profession.Category?.Name ?? 'N/A',
      },
    };
  };

  let tableViewInfo = {
    columns: ['Name', 'Category'],
    columnWidths: ['1fr', '150px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Category?.Name ?? 'N/A',
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
  title='Professions'
  type='Profession'
  basePath='/information/professions'
  let:object>
  <div class="flex-item long-content">
    <h2>Skills</h2>
    <br />
    <div class="container">
      <Table
        title="Skill Components"
        header={{
          values: ['Name', 'Weight', 'Points/HP', 'Hidden'],
          widths: ['1fr', 'max-content', 'max-content', 'max-content'],
        }}
        data={object.Skills.sort((a,b) => a.Skill.Name.localeCompare(b.Skill.Name)).map(skill => ({
          values: [
            skill.Skill.Name,
            skill.Weight,
            skill.Skill.Properties.HpIncrease,
            skill.Skill.Properties.IsHidden ? 'Yes' : 'No'
          ],
          links: [`/information/skills/${encodeURIComponentSafe(skill.Skill.Name)}`, null, null, null]
        }))} />
      {#if object.Unlocks != null}
      <Table
        title="Skill Unlocks"
        header={{
          values: ['Name', 'Level'],
          widths: ['1fr', 'max-content']
        }}
        data={object.Unlocks.sort((a,b) => a.Skill.Name.localeCompare(b.Skill.Name)).map(skill => ({
          values: [
            skill.Skill.Name,
            skill.Level
          ],
          links: [`/information/skills/${encodeURIComponentSafe(skill.Skill.Name)}`, null, null, null]
        }))} />
      {/if}
    </div>
  </div>
</EntityViewer>
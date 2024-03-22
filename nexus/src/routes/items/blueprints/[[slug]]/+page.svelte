<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";
  import Construction from "./Construction.svelte";

  export let data;

  const craftDuration = 5;

  let propertiesDataFunction = (blueprint) => {
    let cost = blueprint.Materials?.reduce((acc, mat) => acc + (mat.Item.Properties.Economy.MaxTT * mat.Amount), 0);

    let cyclePerHour = cost ? (3600 / craftDuration) * cost : null;

    return {
      General: {
        Weight: `0.1kg`,
        Level: blueprint.Properties?.Level ?? 'N/A',
        Type: blueprint.Properties?.Type ?? 'N/A',
        Book: blueprint.Book?.Name ?? 'N/A',
        ProductAmountInterval: {
          Label: 'Product Amount',
          Value: `${blueprint.Properties?.MinimumCraftAmount ?? 'N/A'} - ${blueprint.Properties?.MaximumCraftAmount ?? 'N/A'}`,
        }
      },
      Economy: {
        Cost: {
          Label: 'Cost',
          Value: cost != null ? `${cost.toFixed(2)} PED` : 'N/A',
          Bold: true
        },
        IsBoosted: {
          Label: 'Boosted',
          Tooltip: 'A boosted blueprint will return a significantly higher TT value.',
          Value: blueprint.Properties?.IsBoosted ? 'Yes' : 'No',
        }
      },
      Skill: {
        SiB: {
          Label: 'SiB',
          Tooltip: 'Skill Increase Bonus',
          Value: blueprint.Properties?.Skill.IsSiB ? 'Yes' : 'No',
        },
        Profession: {
          Label: 'Profession',
          Value: [blueprint.Profession?.Name ?? 'N/A', `${blueprint.Properties?.Skill.LearningIntervalStart ?? 'N/A'} - ${blueprint.Properties?.Skill.LearningIntervalEnd ?? 'N/A'}`],
        },
      },
      Misc: {
        CyclePerHour: {
          Label: 'PED/h',
          Tooltip: 'PED cycled per hour',
          Value: cyclePerHour != null ? `${cyclePerHour.toFixed(2)} PED` : 'N/A',
        }
      }
    };
  };

  let tableViewInfo = {
    columns: ['Name', 'Type', 'Level', 'Book', 'Cost', 'Boosted', 'SiB', 'Min', 'Max'],
    columnWidths: ['1fr', '170px', '70px', '250px', '90px', '70px', '70px', '70px', '70px'],
    rowValuesFunction: (item) => {
      let cost = item.Materials?.reduce((acc, mat) => acc + (mat.Item.Properties.Economy.MaxTT * mat.Amount), 0);

      return [
        item.Name,
        item.Properties?.Type ?? 'N/A',
        item.Properties?.Level ?? 'N/A',
        item.Book?.Name ?? 'N/A',
        cost != null ? clampDecimals(cost, 2, 4) + ' PED' : 'N/A',
        item.Properties?.IsBoosted ? 'Yes' : 'No',
        item.Properties?.Skill?.LearningIntervalStart != null ? 'Yes' : 'No',
        item.Properties?.Skill?.LearningIntervalStart != null ? item.Properties?.Skill?.LearningIntervalStart.toFixed(1) : 'N/A',
        item.Properties?.Skill?.LearningIntervalEnd != null ? item.Properties?.Skill?.LearningIntervalEnd.toFixed(1) : 'N/A',
      ];
    }
  };
</script>

<EntityViewer
  data={data}
  tableViewInfo={tableViewInfo}
  propertiesDataFunction={propertiesDataFunction}
  title='Blueprints'
  basePath='/items/blueprints'
  let:object
  let:additional>
  <div class="flex-item-double">
    <div class="big-title">{object.Name}</div>
  </div>
  <!-- Construction -->
  <div class="flex-item long-content">
    <Construction blueprint={object} />
  </div>
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>
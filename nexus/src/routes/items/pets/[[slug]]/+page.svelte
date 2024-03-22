<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import PetEffects from "./PetEffects.svelte";

  import EntityViewer from "$lib/components/EntityViewer.svelte";

  export let data;

  let propertiesDataFunction = (pet) => {
    return {
      General: {
        Rarity: pet.Properties?.Rarity ?? 'N/A',
        TrainingDifficulty: {
          Label: 'Training Difficulty',
          Value: pet.Properties?.TrainingDifficulty ?? 'N/A',
        },
        Planet: pet.Planet?.Name ?? 'N/A',
        Exportable: {
          Label: 'Exportable',
          Value: pet.Properties?.ExportableLevel > 0 ? `Level ${pet.Properties?.ExportableLevel}` : 'No',
        },
      },
      Economy: {
        NutrioCapacity: {
          Label: 'Nutrio Capacity',
          Value: pet.Properties?.NutrioCapacity != null ? `${(pet.Properties?.NutrioCapacity / 100).toFixed(2)} PED` : 'N/A',
        },
        NutrioConsumption: {
          Label: 'Nutrio Consumption',
          Value: pet.Properties?.NutrioConsumptionPerHour != null ? `${(pet.Properties?.NutrioConsumptionPerHour / 100).toFixed(2)} PED/h` : 'N/A',
        },
      },
      Skill: {
        Profession: {
          Label: 'Profession',
          Tooltip: 'The profession and level required to attempt to tame the pet',
          Value: ['Animal Tamer', pet.Properties?.TamingLevel ?? 'N/A'],
        }
      }
    };
  };

  let tableViewInfo = {
    columns: ['Name', 'Rarity', 'Training Difficulty', 'Planet', 'Exportable', 'Nutrio Capacity', 'Nutrio Consumption', 'Taming Level'],
    columnWidths: ['1fr', '100px', '130px', '130px', '100px', '120px', '150px', '110px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Properties?.Rarity ?? 'N/A',
        item.Properties?.TrainingDifficulty ?? 'N/A',
        item.Planet?.Name ?? 'N/A',
        item.Properties?.ExportableLevel > 0 ? `Level ${item.Properties?.ExportableLevel}` : 'No',
        item.Properties?.NutrioCapacity != null ? `${(item.Properties?.NutrioCapacity / 100).toFixed(2)} PED` : 'N/A',
        item.Properties?.NutrioConsumptionPerHour != null ? `${(item.Properties?.NutrioConsumptionPerHour / 100).toFixed(2)} PED/h` : 'N/A',
        item.Properties?.TamingLevel ?? 'N/A',
      ];
    }
  };
</script>

<EntityViewer
  data={data}
  tableViewInfo={tableViewInfo}
  propertiesDataFunction={propertiesDataFunction}
  title='Pets'
  basePath='/items/pets'
  let:object
  let:additional>
  <div class="flex-item-double">
    <div class="big-title">{object.Name}</div>
  </div>
  <div class="flex-item">
    <PetEffects pet={object} />
  </div>
</EntityViewer>
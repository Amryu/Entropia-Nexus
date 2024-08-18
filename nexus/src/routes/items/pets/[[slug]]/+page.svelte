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

  const editConfig = {
    constructor: () => ({
      Name: '',
      Properties: {
        Rarity: null,
        TrainingDifficulty: null,
        ExportableLevel: null,
        NutrioCapacity: null,
        NutrioConsumptionPerHour: null,
        TamingLevel: null,
      },
      Planet: {
        Name: null,
      },
      Effects: []
    }),
    dependencies: ['effects', 'planets'],
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
          { label: 'Rarity', type: 'select', options: _ => ['Common', 'Uncommon', 'Rare', 'Epic', 'Legendary', 'Mythic', 'Unique'], '_get': x => x.Properties.Rarity, '_set': (x, v) => x.Properties.Rarity = v },
          { label: 'Training Difficulty', type: 'select', options: _ => ['Easy', 'Average', 'Hard'], '_get': x => x.Properties.TrainingDifficulty, '_set': (x, v) => x.Properties.TrainingDifficulty = v },
          { label: 'Planet', type: 'select', options: (_, d) => d.planets.filter(x => x.Id > 0).map(x => x.Name), '_get': x => x.Planet.Name, '_set': (x, v) => x.Planet.Name = v },
          { label: 'Exportable Level', type: 'number', '_get': x => x.Properties.ExportableLevel, '_set': (x, v) => x.Properties.ExportableLevel = v },
        ]
      },
      {
        label: 'Economy',
        type: 'group',
        controls: [
          { label: 'Nutrio Capacity', type: 'number', '_get': x => x.Properties.NutrioCapacity, '_set': (x, v) => x.Properties.NutrioCapacity = v },
          { label: 'Nutrio/h (Metab.)', type: 'number', '_get': x => x.Properties.NutrioConsumptionPerHour, '_set': (x, v) => x.Properties.NutrioConsumptionPerHour = v },
        ]
      },
      {
        label: 'Skill',
        type: 'group',
        controls: [
          { label: 'Taming Level', type: 'number', '_get': x => x.Properties.TamingLevel, '_set': (x, v) => x.Properties.TamingLevel = v },
        ]
      },
      { label: 'Effects', type: 'list', config: {
        constructor: () => ({
          Name: null,
          Properties: {
            Strength: null,
            NutrioConsumptionPerHour: null,
            Unlock: {
              Level: null,
              CostPED: null,
              CostEssence: null,
              CostRareEssence: null,
              Criteria: null,
              CriteriaValue: null,
            }
          }
        }),
        dependencies: ['effects'],
        controls: [
          { label: 'Effect', type: 'select', options: (_, d) => d.effects.map(x => x.Name), '_get': x => x.Name, '_set': (x, v) => x.Name = v },
          { label: 'Strength', type: 'number', '_get': x => x.Properties.Strength, '_set': (x, v) => x.Properties.Strength = v },
          { label: 'Nutrio/h', type: 'number', '_get': x => x.Properties.NutrioConsumptionPerHour, '_set': (x, v) => x.Properties.NutrioConsumptionPerHour = v },
          {
            label: 'Unlock',
            type: 'group',
            controls: [
              { label: 'Level', type: 'number', '_get': x => x.Properties.Unlock.Level, '_set': (x, v) => x.Properties.Unlock.Level = v },
              { label: 'PED', type: 'number', '_get': x => x.Properties.Unlock.CostPED, '_set': (x, v) => x.Properties.Unlock.CostPED = v },
              { label: 'Essence', type: 'number', '_get': x => x.Properties.Unlock.CostEssence, '_set': (x, v) => x.Properties.Unlock.CostEssence = v },
              { label: 'Rare Essence', type: 'number', '_get': x => x.Properties.Unlock.CostRareEssence, '_set': (x, v) => x.Properties.Unlock.CostRareEssence = v },
              { label: 'Criteria', type: 'text', '_get': x => x.Properties.Unlock.Criteria, '_set': (x, v) => x.Properties.Unlock.Criteria = v },
              { label: 'Criteria Value', type: 'number', '_get': x => x.Properties.Unlock.CriteriaValue, '_set': (x, v) => x.Properties.Unlock.CriteriaValue = v },
            ]
          }
        ]
      }, '_get': x => x.Effects, '_set': (x, v) => x.Effects = v }
    ]
  }

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
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Pets'
  type='Pet'
  basePath='/items/pets'
  let:object
  let:additional>
  <div class="flex-item">
    <PetEffects pet={object} />
  </div>
</EntityViewer>
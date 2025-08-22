<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals, getTypeLink, hasItemTag } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";
  import Construction from "./Construction.svelte";

  export let data;

  const craftDuration = 5;

  // Cache expensive dropdown options to prevent recalculation on every keystroke
  let cachedProductOptions = [];
  let cachedProfessionOptions = [];
  let cachedBookOptions = [];
  let cachedMaterialOptions = [];
  let cachedBlueprintOptions = [];
  
  // Dependencies will be populated by EntityViewer when the edit form is shown
  let dependencies = null;
  
  $: {
    // Only recalculate when dependencies change, not on every keystroke
    if (dependencies) {
      cachedProductOptions = dependencies.items
        ?.filter(x => x.Properties?.Type !== 'Blueprint' && x.Properties?.Type !== 'Pet')
        ?.map(x => x.Name)
        ?.sort((a,b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })) || [];
      
      cachedProfessionOptions = dependencies.professions
        ?.filter(x => x.Category?.Name === 'Manufacturing')
        ?.map(x => x.Name) || [];
      
      cachedBookOptions = dependencies.blueprintbooks?.map(x => x.Name) || [];
  cachedMaterialOptions = dependencies.materials?.map(x => x.Name) || [];
  cachedBlueprintOptions = dependencies.blueprints?.map(x => x.Name) || [];
    }
  }

  let propertiesDataFunction = (blueprint) => {
    let cost = blueprint.Materials?.reduce((acc, mat) => acc + (mat.Item?.Properties?.Economy?.MaxTT * mat?.Amount), 0);

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
          LinkValue: [blueprint.Profession?.Name != null ? getTypeLink(blueprint.Profession.Name, 'Profession') : null, null],
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

  const editConfig = {
    constructor: () => ({
      Name: null,
      Properties: {
        Description: null,
        Type: null,
        Level: null,
        IsBoosted: false,
        MinimumCraftAmount: null,
        MaximumCraftAmount: null,
        Skill: {
          IsSiB: true,
          LearningIntervalStart: null,
          LearningIntervalEnd: null
        }
      },
      Book: {
        Name: null
      },
      Profession: {
        Name: null
      },
      Product: {
        Name: null
      },
      Materials: [],
      Drops: []
    }),
    dependencies: ['items', 'materials', 'blueprintbooks', 'professions', 'blueprints'],
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v, dependencies) => {
            x.Name = v;
            // If blueprint is limited (ends with (L)), set Book to "Limited (Vol. 1) (C)"
            if (hasItemTag(v, 'L')) {
              x.Book.Name = "Limited (Vol. 1) (C)";
            }
            
            // Try to auto-detect product from blueprint name
            if (v && !x.Product.Name && dependencies?.items && v.match(/\s+Blueprint(\s*\([^)]*\))?\s*$/)) {
              // Only auto-detect if name ends with "Blueprint" (with optional tags after)
              // Remove "Blueprint" and optional "(L)" from the end
              let productName = v;
              
              // Remove "(L)" if present
              if (hasItemTag(productName, 'L')) {
                productName = productName.replace(/\s*\([^)]*L[^)]*\)$/, '');
              }
              
              // Remove "Blueprint" from the end
              productName = productName.replace(/\s+Blueprint\s*$/, '').trim();
              
              // Try to find matching product in items
              const matchingItem = dependencies.items.find(item => 
                item.Name === productName && 
                item.Properties.Type !== 'Blueprint' && 
                item.Properties.Type !== 'Pet'
              );
              
              if (matchingItem) {
                x.Product.Name = matchingItem.Name;
              }
            }
          }},
          { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
          { label: 'Type', type: 'select', options: _ => [
            'Weapon',
            'Textile',
            'Vehicle',
            'Enhancer',
            'Furniture',
            'Tool',
            'Armor',
            'Attachment',
            'Metal Component',
            'Electrical Component',
            'Mechanical Component'
          ], '_get': x => x.Properties.Type, '_set': (x, v) => x.Properties.Type = v},
          { label: 'Level', type: 'number', step: 1, min: 0, '_get': x => x.Properties.Level, '_set': (x, v) => {
            // Clamp level to minimum 1
            const level = Math.max(1, v || 1);
            x.Properties.Level = level;
            
            // Update learning intervals based on level
            if (level >= 1 && level <= 12) {
              if (level === 11) {
                // Level 11 is special case: 30-35
                x.Properties.Skill.LearningIntervalStart = 30;
                x.Properties.Skill.LearningIntervalEnd = 35;
              } else if (level === 12) {
                // Level 12 is special case: 44-49
                x.Properties.Skill.LearningIntervalStart = 44;
                x.Properties.Skill.LearningIntervalEnd = 49;
              } else {
                // Level 1: 0-5, then add 2.5 to both bounds for each level
                const lowerBound = (level - 1) * 2.5;
                const upperBound = lowerBound + 5;
                x.Properties.Skill.LearningIntervalStart = lowerBound;
                x.Properties.Skill.LearningIntervalEnd = upperBound;
              }
            }
            // For levels < 1 (already clamped) and > 12: do nothing to intervals
          }},
          { label: 'Boosted', type: 'checkbox', '_get': x => x.Properties.IsBoosted, '_set': (x, v) => x.Properties.IsBoosted = v},
          { label: 'Book', type: 'select', options: (_, d) => {
            // Update dependencies for caching if not already set
            if (d && !dependencies) {
              dependencies = d;
            }
            return cachedBookOptions.length > 0 ? cachedBookOptions : (d.blueprintbooks?.map(x => x.Name) || []);
          }, '_get': x => x.Book.Name, '_set': (x, v) => x.Book.Name = v},
          { label: 'Product', type: 'select', options: (_, d) => {
            // Update dependencies for caching if not already set
            if (d && !dependencies) {
              dependencies = d;
            }
            if (cachedProductOptions.length > 0) {
              return cachedProductOptions;
            }
            // Fallback with same filtering logic
            return d.items?.filter(x => x.Properties?.Type !== 'Blueprint' && x.Properties?.Type !== 'Pet')?.map(x => x.Name)?.sort((a,b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })) || [];
          }, '_get': x => x.Product.Name, '_set': (x, v) => x.Product.Name = v},
          { label: 'Product Amount', type: 'range', step: 1, min: 1, '_get': x => [x.Properties.MinimumCraftAmount, x.Properties.MaximumCraftAmount], '_set': (x, v) => { x.Properties.MinimumCraftAmount = v[0]; x.Properties.MaximumCraftAmount = v[1]; }},
        ]
      },
      {
        label: 'Skill',
        type: 'group',
        controls: [
          { label: 'SiB', type: 'checkbox', '_get': x => x.Properties.Skill.IsSiB, '_set': (x, v) => x.Properties.Skill.IsSiB = v},
          { label: 'Profession', type: 'select', options: (_, d) => {
            // Update dependencies for caching if not already set
            if (d && !dependencies) {
              dependencies = d;
            }
            return cachedProfessionOptions.length > 0 ? cachedProfessionOptions : (d.professions?.filter(x => x.Category.Name === 'Manufacturing')?.map(x => x.Name) || []);
          }, '_get': x => x.Profession.Name, '_set': (x, v) => x.Profession.Name = v},
          { label: 'Learning Interval', type: 'range', step: 0.1, min: 0, '_get': x => [x.Properties.Skill.LearningIntervalStart, x.Properties.Skill.LearningIntervalEnd], '_set': (x, v) => { x.Properties.Skill.LearningIntervalStart = v[0]; x.Properties.Skill.LearningIntervalEnd = v[1]; }},
        ]
      },
      { label: 'Materials', type: 'list', config: {
        constructor: () => ({
          Item: {
            Name: null,
          },
          Amount: null
        }),
        dependencies: ['materials'],
        controls: [
          { label: 'Material', type: 'select', options: (_, d) => {
            // Update dependencies for caching if not already set  
            if (d && !dependencies) {
              dependencies = d;
            }
            return cachedMaterialOptions.length > 0 ? cachedMaterialOptions : (d.materials?.map(x => x.Name) || []);
          }, '_get': x => x.Item?.Name, '_set': (x, v) => x.Item.Name = v},
          { label: 'Amount', type: 'number', step: 1, min: 1, '_get': x => x.Amount, '_set': (x, v) => x.Amount = v},
        ]
      }, '_get': x => x.Materials, '_set': (x, v) => x.Materials = v}
      ,
      { label: 'Drops', type: 'list', config: {
        constructor: () => ({ Name: null }),
        dependencies: ['blueprints'],
        controls: [
          { label: 'Blueprint', type: 'select', options: (_, d) => {
            if (d && !dependencies) { dependencies = d; }
            return cachedBlueprintOptions.length > 0 ? cachedBlueprintOptions : (d.blueprints?.map(x => x.Name) || []);
          }, '_get': x => x.Name, '_set': (x, v) => x.Name = v }
        ]
      }, '_get': x => x.Drops, '_set': (x, v) => x.Drops = v }
    ]
  }

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
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Blueprints'
  type='Blueprint'
  basePath='/items/blueprints'
  let:object
  let:additional>
  <!-- Construction -->
  <div class="flex-item long-content">
    <Construction blueprint={object} />
  </div>
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>
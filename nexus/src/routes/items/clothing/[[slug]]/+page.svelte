<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";

  export let data;

  let propertiesDataFunction = (clothing) => {
    return {
      General: {
        Weight: clothing.Properties?.Weight != null ? `${clampDecimals(clothing.Properties?.Weight, 1, 6)}kg` : 'N/A',
        Type: clothing.Properties?.Type ?? 'N/A',
        Slot: clothing.Properties?.Slot ?? 'N/A',
        Gender: clothing.Properties?.Gender ?? 'N/A',
      },
      Economy: {
        MaxTT: {
          Label: 'Max. TT',
          Value: clothing.Properties?.Economy?.MaxTT != null ? `${clampDecimals(clothing.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        },
        MinTT: {
          Label: 'Min. TT',
          Value: clothing.Properties?.Economy?.MinTT != null ? `${clampDecimals(clothing.Properties?.Economy?.MinTT, 2, 8)} PED` : 'N/A',
        },
      }
    }
  };

  let tableViewInfo = {
    columns: ['Name', 'Weight', 'Type', 'Slot', 'Gender', 'Max. TT'],
    columnWidths: ['1fr', '80px', '100px', '100px', '100px', '100px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
        item.Properties?.Type ?? 'N/A',
        item.Properties?.Slot ?? 'N/A',
        item.Properties?.Gender ?? 'N/A',
        item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
      ];
    }
  };
</script>

<EntityViewer
  data={data}
  tableViewInfo={tableViewInfo}
  propertiesDataFunction={propertiesDataFunction}
  title='Clothing'
  basePath='/items/clothing'
  let:object
  let:additional>
  <div class="flex-item-double">
    <div class="big-title">{object.Name}</div>
  </div>
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>
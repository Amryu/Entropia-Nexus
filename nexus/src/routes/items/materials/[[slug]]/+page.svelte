<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals } from '$lib/util.js';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";

  export let data;

  let propertiesDataFunction = (material) => {
    return {
      General: {
        Weight: material.Properties?.Weight != null ? `${clampDecimals(material.Properties?.Weight, 1, 6)}kg` : 'N/A',
      },
      Economy: {
        Value: material.Properties?.Economy?.MaxTT != null ? `${clampDecimals(material.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
      }
    };
  };

  let tableViewInfo = {
    columns: ['Name', 'Weight', 'Max. TT'],
    columnWidths: ['1fr', '80px', '100px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Properties?.Weight != null ? `${clampDecimals(item.Properties?.Weight, 1, 6)}kg` : 'N/A',
        item.Properties?.Economy?.MaxTT != null ? `${clampDecimals(item.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
      ];
    }
  };
</script>

<EntityViewer
  data={data}
  tableViewInfo={tableViewInfo}
  propertiesDataFunction={propertiesDataFunction}
  title='Materials'
  basePath='/items/materials'
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
<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { hasItemTag, clampDecimals } from "$lib/util";

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  
  import Tiering from "$lib/components/Tiering.svelte";
  import Acquisition from "$lib/components/Acquisition.svelte";
  import ArmorSetPieces from "./ArmorSetPieces.svelte";

  export let data;

  function getTotalDefense(item) {
    return (item.Properties?.Defense?.Impact ?? 0) + (item.Properties?.Defense?.Cut ?? 0) + (item.Properties?.Defense?.Stab ?? 0) + (item.Properties?.Defense?.Penetration ?? 0) + (item.Properties?.Defense?.Shrapnel ?? 0) + (item.Properties?.Defense?.Burn ?? 0) + (item.Properties?.Defense?.Cold ?? 0) + (item.Properties?.Defense?.Acid ?? 0) + (item.Properties?.Defense?.Electric ?? 0);
  }

  function getMaxArmorDecay(item) {
    return item.Properties?.Economy.Durability && getTotalDefense(item)
      ? getTotalDefense(item) * ((100000 - item.Properties?.Economy.Durability) / 100000) * 0.05
      : null;
  }

  function getTotalAbsorption(item) {
    return item.Properties?.Economy.MaxTT && getMaxArmorDecay(item)
      ? getTotalDefense(item) * ((item.Properties?.Economy.MaxTT - (item.Properties?.Economy.MinTT ?? 0)) / (getMaxArmorDecay(item) / 100))
      : null;
  }

  let propertiesDataFunction = (armorSet) => {
    return {
      General: {
        Weight: armorSet.Properties?.Weight != null ? `${clampDecimals(armorSet.Properties?.Weight, 1, 6)}kg` : 'N/A',
      },
      Economy: {
        MaxTT: {
          Label: 'Max. TT',
          Value: armorSet.Properties?.Economy?.MaxTT != null ? `${clampDecimals(armorSet.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        },
        MinTT: {
          Label: 'Min. TT',
          Value: armorSet.Properties?.Economy?.MinTT != null ? `${clampDecimals(armorSet.Properties?.Economy?.MinTT, 2, 8)} PED` : 'N/A',
        },
        MaxDecay: {
          Label: 'Maximum Decay',
          Tooltip: 'The maximum amount of decay the armor can take at once, if it uses its full protection.',
          Value: getMaxArmorDecay(armorSet) != null ? `${getMaxArmorDecay(armorSet).toFixed(4)} PEC` : 'N/A',
        },
        Durability: armorSet.Properties?.Economy?.Durability ?? 'N/A',
      },
      Defense: {
        Impact: `${armorSet.Properties?.Defense?.Impact?.toFixed(1) ?? 'N/A'}`,
        Cut: `${armorSet.Properties?.Defense?.Cut?.toFixed(1) ?? 'N/A'}`,
        Stab: `${armorSet.Properties?.Defense?.Stab?.toFixed(1) ?? 'N/A'}`,
        Penetration: `${armorSet.Properties?.Defense?.Penetration?.toFixed(1) ?? 'N/A'}`,
        Shrapnel: `${armorSet.Properties?.Defense?.Shrapnel?.toFixed(1) ?? 'N/A'}`,
        Burn: `${armorSet.Properties?.Defense?.Burn?.toFixed(1) ?? 'N/A'}`,
        Cold: `${armorSet.Properties?.Defense?.Cold?.toFixed(1) ?? 'N/A'}`,
        Acid: `${armorSet.Properties?.Defense?.Acid?.toFixed(1) ?? 'N/A'}`,
        Electric: `${armorSet.Properties?.Defense?.Electric?.toFixed(1) ?? 'N/A'}`,
        Total: {
          Label: 'Total',
          Value: getTotalDefense(armorSet) != null ? `${getTotalDefense(armorSet).toFixed(1)}` : 'N/A',
          Bold: true,
        },
      },
      Misc: {
        TotalAbsorption: {
          Label: 'Total Absorption',
          Tooltip: 'The total amount of damage the plate can absorb before it breaks. This number does not take block into account.',
          Value: getTotalAbsorption(armorSet) != null ? `${getTotalAbsorption(armorSet).toFixed(0)} HP` : 'N/A',
        }
      }
    };
  };

  let tableViewInfo = {
    columns: ['Name', 'Weight', 'Max. TT', 'Durability', 'Total Absorption', 'Imp', 'Cut', 'Stab', 'Pen', 'Shrap', 'Burn', 'Cold', 'Acid', 'Elec', 'Total'],
    columnWidths: ['1fr', '80px', '100px', '90px', '130px', '70px', '70px', '70px', '70px', '70px', '70px', '70px', '70px', '70px', '70px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Properties?.Weight != null ? `${item.Properties?.Weight.toFixed(1)}kg` : 'N/A',
        item.Properties?.Economy?.MaxTT != null ? `${item.Properties?.Economy?.MaxTT.toFixed(2)} PED` : 'N/A',
        item.Properties?.Economy?.Durability ?? 'N/A',
        getTotalAbsorption(item) != null ? `${getTotalAbsorption(item).toFixed(0)} HP` : 'N/A',
        item.Properties?.Defense?.Impact?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Cut?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Stab?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Penetration?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Shrapnel?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Burn?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Cold?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Acid?.toFixed(1) ?? 'N/A',
        item.Properties?.Defense?.Electric?.toFixed(1) ?? 'N/A',
        getTotalDefense(item) != null ? `${getTotalDefense(item).toFixed(1)}` : 'N/A',
      ];
    }
  };
</script>

<EntityViewer
  data={data}
  tableViewInfo={tableViewInfo}
  propertiesDataFunction={propertiesDataFunction}
  title='Armor Sets'
  basePath='/items/armorsets'
  let:object
  let:additional>
  <div class="flex-item-double">
    <div class="big-title">{object.Name} Armor</div>
  </div>
  <!-- Set Pieces -->
  <div class="flex-item long-content">
    <ArmorSetPieces armorSet={object} />
  </div>
  {#if !hasItemTag(object.Name, 'L')}
  <!-- Tiering -->
  <div class="flex-item long-content">
    <Tiering tieringInfo={additional.tierInfo} setPieceCount={object?.Armors?.filter(x => x.Properties.Gender === 'Both' || x.Properties.Gender === 'Male').length ?? 0} />
  </div>
  {/if}
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>
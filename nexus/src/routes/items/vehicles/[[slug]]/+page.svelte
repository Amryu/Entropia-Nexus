<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import { clampDecimals } from '$lib/util.js';

  import EntityViewer from '$lib/components/EntityViewer.svelte';
  import Acquisition from "$lib/components/Acquisition.svelte";

  export let data;

  let propertiesDataFunction = (vehicle) => {
    let totalDefense = vehicle.Properties?.Defense?.Stab + vehicle.Properties?.Defense?.Cut + vehicle.Properties?.Defense?.Impact + vehicle.Properties?.Defense?.Penetration + vehicle.Properties?.Defense?.Shrapnel + vehicle.Properties?.Defense?.Burn + vehicle.Properties?.Defense?.Cold + vehicle.Properties?.Defense?.Acid + vehicle.Properties?.Defense?.Electric;

    return {
      General: {
        Weight: vehicle.Properties?.Weight != null ? `${clampDecimals(vehicle.Properties?.Weight, 1, 6)}kg` : 'N/A',
        SpawnedWeight: {
          Label: 'Spawned Weight',
          Value: vehicle.Properties?.SpawnedWeight != null ? `${vehicle.Properties?.SpawnedWeight.toFixed(1)}kg` : 'N/A',
        }
      },
      Economy: {
        MaxTT: {
          Label: 'Max. TT',
          Value: vehicle.Properties?.Economy?.MaxTT != null ? `${clampDecimals(vehicle.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        },
        MinTT: {
          Label: 'Min. TT',
          Value: vehicle.Properties?.Economy?.MinTT != null ? `${clampDecimals(vehicle.Properties?.Economy?.MinTT, 2, 8)} PED` : 'N/A',
        },
        Durability: vehicle.Properties?.Economy?.Durability != null ? vehicle.Properties?.Economy?.Durability : 'N/A',
        Fuel: vehicle.Fuel?.Name ?? 'N/A',
        ConsumptionActive: {
          Label: 'Consumption Active',
          Value: vehicle.Properties?.Economy?.FuelConsumptionActive != null ? `${vehicle.Properties?.Economy?.FuelConsumptionActive.toFixed(2)} PED/km` : 'N/A',
        },
        ConsumptionPassive: {
          Label: 'Consumption Passive',
          Value: vehicle.Properties?.Economy?.FuelConsumptionPassive != null ? `${vehicle.Properties?.Economy?.FuelConsumptionPassive.toFixed(2)} PED/min` : 'N/A',
        },
      },
      Vehicle: {
        Passengers: vehicle.Properties?.PassengerCount != null ? vehicle.Properties?.PassengerCount : 'N/A',
        ItemCapacity: {
          Label: 'Item Capacity',
          Tooltip: 'Maximum number of items that can be stored in the vehicle',
          Value: vehicle.Properties?.ItemCapacity != null ? vehicle.Properties?.ItemCapacity : 'N/A',
        },
        WeightCapacity: {
          Label: 'Weight Capacity',
          Tooltip: 'Maximum weight that can be stored in the vehicle',
          Value: vehicle.Properties?.WeightCapacity != null ? `${vehicle.Properties?.WeightCapacity.toFixed(1)}kg` : 'N/A',
        },
        WheelGrip: {
          Label: 'Wheel Grip',
          Value: vehicle.Properties?.WheelGrip != null ? vehicle.Properties?.WheelGrip : 'N/A',
        },
        EnginePower: {
          Label: 'Engine Power',
          Value: vehicle.Properties?.EnginePower != null ? vehicle.Properties?.EnginePower : 'N/A',
        },
        MaxSpeed: {
          Label: 'Max. Speed',
          Value: vehicle.Properties?.MaxSpeed != null ? `${vehicle.Properties?.MaxSpeed.toFixed(2)} km/h` : 'N/A',
        },
        MaxSI: {
          Label: 'Max. SI',
          Tooltip: 'Maximum SI (Structural Integrity) of the vehicle. This is the maximum damage the vehicle can take before it is destroyed and must be repaired.',
          Value: vehicle.Properties?.MaxStructuralIntegrity != null ? vehicle.Properties?.MaxStructuralIntegrity : 'N/A',
        },
      },
      Defense: {
        Stab: vehicle.Properties?.Defense?.Stab != null ? vehicle.Properties?.Defense?.Stab.toFixed(1) : 'N/A',
        Cut: vehicle.Properties?.Defense?.Cut != null ? vehicle.Properties?.Defense?.Cut.toFixed(1) : 'N/A',
        Impact: vehicle.Properties?.Defense?.Impact != null ? vehicle.Properties?.Defense?.Impact.toFixed(1) : 'N/A',
        Penetration: vehicle.Properties?.Defense?.Penetration != null ? vehicle.Properties?.Defense?.Penetration.toFixed(1) : 'N/A',
        Shrapnel: vehicle.Properties?.Defense?.Shrapnel != null ? vehicle.Properties?.Defense?.Shrapnel.toFixed(1) : 'N/A',
        Burn: vehicle.Properties?.Defense?.Burn != null ? vehicle.Properties?.Defense?.Burn.toFixed(1) : 'N/A',
        Cold: vehicle.Properties?.Defense?.Cold != null ? vehicle.Properties?.Defense?.Cold.toFixed(1) : 'N/A',
        Acid: vehicle.Properties?.Defense?.Acid != null ? vehicle.Properties?.Defense?.Acid.toFixed(1) : 'N/A',
        Electric: vehicle.Properties?.Defense?.Electric != null ? vehicle.Properties?.Defense?.Electric.toFixed(1) : 'N/A',
        Total: {
          Value: totalDefense !== null ? totalDefense.toFixed(1) : 'N/A',
          Bold: true,
        }
      }
    };
  };
  
  let tableViewInfo = {
    columns: ['Name', 'Weight', 'Max. TT', 'Durability', 'Fuel', 'Usage (A)', 'Usage (P)', 'Seats', 'Item Cap.', 'Weight Cap.', 'Max. Speed', 'Max. SI'],
    columnWidths: ['1fr', '80px', '100px', '90px', '80px', '110px', '110px', '60px', '80px', '90px', '100px', '80px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Properties?.Weight != null ? `${item.Properties?.Weight.toFixed(1)}kg` : 'N/A',
        item.Properties?.Economy?.MaxTT != null ? `${item.Properties?.Economy?.MaxTT.toFixed(2)} PED` : 'N/A',
        item.Properties?.Economy?.Durability != null ? item.Properties?.Economy?.Durability : 'N/A',
        item.Fuel?.Name ?? 'N/A',
        item.Properties?.Economy?.FuelConsumptionActive != null ? `${item.Properties?.Economy?.FuelConsumptionActive.toFixed(2)} PED/km` : 'N/A',
        item.Properties?.Economy?.FuelConsumptionPassive != null ? `${item.Properties?.Economy?.FuelConsumptionPassive.toFixed(2)} PED/min` : 'N/A',
        item.Properties?.PassengerCount != null ? item.Properties?.PassengerCount : 'N/A',
        item.Properties?.ItemCapacity != null ? item.Properties?.ItemCapacity : 'N/A',
        item.Properties?.WeightCapacity != null ? `${item.Properties?.WeightCapacity.toFixed(1)}kg` : 'N/A',
        item.Properties?.MaxSpeed != null ? `${item.Properties?.MaxSpeed.toFixed(2)} km/h` : 'N/A',
        item.Properties?.MaxStructuralIntegrity != null ? item.Properties?.MaxStructuralIntegrity : 'N/A',
      ];
    }
  };
</script>

<EntityViewer
  data={data}
  tableViewInfo={tableViewInfo}
  propertiesDataFunction={propertiesDataFunction}
  title='Vehicles'
  basePath='/items/vehicles'
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
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
        },
        Type: vehicle.Properties?.Type ?? 'N/A',
      },
      Economy: {
        MaxTT: {
          Label: 'Max. TT (PED)',
          Value: vehicle.Properties?.Economy?.MaxTT != null ? `${clampDecimals(vehicle.Properties?.Economy?.MaxTT, 2, 8)} PED` : 'N/A',
        },
        MinTT: {
          Label: 'Min. TT (PED)',
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
        AttachmentSlots: {
          Label: 'Attachment Slots',
          Value: vehicle.AttachmentSlots?.length > 0 ? vehicle.AttachmentSlots.map(x => x.Name).join(', ') : 'N/A',
        }
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

  const editConfig = {
    constructor: () => ({
      Name: '',
      Properties: {
        Description: null,
        Weight: null,
        Type: null,
        SpawnedWeight: null,
        PassengerCount: null,
        ItemCapacity: null,
        WeightCapacity: null,
        WheelGrip: null,
        EnginePower: null,
        MaxSpeed: null,
        MaxStructuralIntegrity: null,
        Economy: {
          MaxTT: null,
          MinTT: null,
          Durability: null,
          FuelConsumptionActive: null,
          FuelConsumptionPassive: null,
        },
        Defense: {
          Stab: null,
          Cut: null,
          Impact: null,
          Penetration: null,
          Shrapnel: null,
          Burn: null,
          Cold: null,
          Acid: null,
          Electric: null,
        }
      },
      Fuel: {
        Name: null,
      },
      AttachmentSlots: []
    }),
    dependencies: ['materials', 'vehicleattachmenttypes'],
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { label: 'Name', type: 'text', '_get': x => x.Name, '_set': (x, v) => x.Name = v },
          { label: 'Description', type: 'textarea', '_get': x => x.Properties.Description, '_set': (x, v) => x.Properties.Description = v },
          { label: 'Weight', type: 'number', '_get': x => x.Properties.Weight, '_set': (x, v) => x.Properties.Weight = v },
          { label: 'Type', type: 'select', options: () => ['Land', 'Air', 'Sea', 'Amphibious', 'Space'], '_get': x => x.Properties.Type, '_set': (x, v) => { x.Properties.Type = v; if (['Air','Sea','Space'].includes(v)) { x.Properties.WheelGrip = null; } } },
        ]
      },
      {
        label: 'Economy',
        type: 'group',
        controls: [
          { label: 'Max. TT (PED)', type: 'number', '_get': x => x.Properties.Economy.MaxTT, '_set': (x, v) => x.Properties.Economy.MaxTT = v },
          { label: 'Min. TT (PED)', type: 'number', '_get': x => x.Properties.Economy.MinTT, '_set': (x, v) => x.Properties.Economy.MinTT = v },
          { label: 'Durability', type: 'number', '_get': x => x.Properties.Economy.Durability, '_set': (x, v) => x.Properties.Economy.Durability = parseInt(v) || null },
          { label: 'Fuel', type: 'select', options: (_, d) => ['', ...d.materials.filter(x => x.Properties.Type === 'Refined Enmatter').map(x => x.Name)], '_get': x => x.Fuel?.Name, '_set': (x, v) => x.Fuel.Name = v || null },
          { label: 'Fuel/km (Active)', type: 'number', '_get': x => x.Properties.Economy.FuelConsumptionActive, '_set': (x, v) => x.Properties.Economy.FuelConsumptionActive = v },
          { label: 'Fuel/min (Passive)', type: 'number', '_get': x => x.Properties.Economy.FuelConsumptionPassive, '_set': (x, v) => x.Properties.Economy.FuelConsumptionPassive = v },
        ]
      },
      {
        label: 'Vehicle Details',
        type: 'group',
        controls: [
          { label: 'Spawned Weight', type: 'number', '_get': x => x.Properties.SpawnedWeight, '_set': (x, v) => x.Properties.SpawnedWeight = v },
          { label: 'Passenger Count', type: 'number', '_get': x => x.Properties.PassengerCount, '_set': (x, v) => x.Properties.PassengerCount = parseInt(v) || null },
          { label: 'Item Capacity', type: 'number', '_get': x => x.Properties.ItemCapacity, '_set': (x, v) => x.Properties.ItemCapacity = parseInt(v) || null },
          { label: 'Weight Capacity', type: 'number', '_get': x => x.Properties.WeightCapacity, '_set': (x, v) => x.Properties.WeightCapacity = v },
          { '_if': x => !['Air','Sea','Space'].includes(x.Properties.Type), label: 'Wheel Grip', type: 'number', '_get': x => x.Properties.WheelGrip, '_set': (x, v) => x.Properties.WheelGrip = v },
          { label: 'Engine Power', type: 'number', '_get': x => x.Properties.EnginePower, '_set': (x, v) => x.Properties.EnginePower = v },
          { label: 'Max. Speed', type: 'number', '_get': x => x.Properties.MaxSpeed, '_set': (x, v) => x.Properties.MaxSpeed = v },
          { label: 'Max. SI', type: 'number', '_get': x => x.Properties.MaxStructuralIntegrity, '_set': (x, v) => x.Properties.MaxStructuralIntegrity = v },
        ]
      },
      { label: 'Attachment Slots', type: 'list', config: {
        constructor: () => ({
          Name: null,
        }),
        dependencies: ['vehicleattachmenttypes'],
        controls: [
          { label: 'Type', type: 'select', options: (_, d) => d.vehicleattachmenttypes.map(x => x.Name), '_get': x => x.Name, '_set': (x, v) => x.Name = v },
        ]
      }, '_get': x => x.AttachmentSlots, '_set': (x, v) => x.AttachmentSlots = v },
      {
        label: 'Defense',
        type: 'group',
        controls: [
          { label: 'Stab', type: 'number', '_get': x => x.Properties.Defense.Stab, '_set': (x, v) => x.Properties.Defense.Stab = v },
          { label: 'Cut', type: 'number', '_get': x => x.Properties.Defense.Cut, '_set': (x, v) => x.Properties.Defense.Cut = v },
          { label: 'Impact', type: 'number', '_get': x => x.Properties.Defense.Impact, '_set': (x, v) => x.Properties.Defense.Impact = v },
          { label: 'Penetration', type: 'number', '_get': x => x.Properties.Defense.Penetration, '_set': (x, v) => x.Properties.Defense.Penetration = v },
          { label: 'Shrapnel', type: 'number', '_get': x => x.Properties.Defense.Shrapnel, '_set': (x, v) => x.Properties.Defense.Shrapnel = v },
          { label: 'Burn', type: 'number', '_get': x => x.Properties.Defense.Burn, '_set': (x, v) => x.Properties.Defense.Burn = v },
          { label: 'Cold', type: 'number', '_get': x => x.Properties.Defense.Cold, '_set': (x, v) => x.Properties.Defense.Cold = v },
          { label: 'Acid', type: 'number', '_get': x => x.Properties.Defense.Acid, '_set': (x, v) => x.Properties.Defense.Acid = v },
          { label: 'Electric', type: 'number', '_get': x => x.Properties.Defense.Electric, '_set': (x, v) => x.Properties.Defense.Electric = v },
        ]
      }
    ]
  }
  
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
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Vehicles'
  type='Vehicle'
  basePath='/items/vehicles'
  let:object
  let:additional>
  <!-- Acquisition -->
  <div class="flex-item long-content">
    <Acquisition acquisition={additional.acquisition} />
  </div>
</EntityViewer>
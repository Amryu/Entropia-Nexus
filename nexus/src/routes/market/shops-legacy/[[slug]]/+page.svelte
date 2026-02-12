<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Table from "$lib/components/Table.svelte";
  import { waypoint } from "$lib/components/Properties.svelte";
  import { apiCall, getItemLink } from '$lib/util';

  export let data;

  // Constants for section names
  const SECTION_NAMES = ['Indoor', 'Display', 'Additional'];

  const navButtonInfo = [
    {
      Label: 'Cly',
      Title: 'Calypso',
      Type: 'calypso',
      IsRoute: false
    },
    {
      Label: 'Ars',
      Title: 'ARIS',
      Type: 'aris',
      IsRoute: false
    },
    {
      Label: 'Cyr',
      Title: 'Cyrene',
      Type: 'cyrene',
      IsRoute: false
    },
    {
      Label: 'Ark',
      Title: 'Arkadia',
      Type: 'arkadia',
      IsRoute: false
    },
    {
      Label: 'Mnr',
      Title: 'Monria',
      Type: 'monria',
      IsRoute: false
    },
    {
      Label: 'Rck',
      Title: 'ROCKtropia',
      Type: 'rocktropia',
      IsRoute: false
    },
    {
      Label: 'Tou',
      Title: 'Toulan',
      Type: 'toulan',
      IsRoute: false
    },
    {
      Label: 'NI',
      Title: 'Next Island',
      Type: 'nextisland',
      IsRoute: false
    }
  ]

  let propertiesDataFunction = (shop) => {
    // Ensure shop is not null and has the expected structure
    if (!shop) {
      return {
        General: {
          Owner: 'No Owner',
          Planet: 'N/A',
          Location: 'N/A'
        },
        Inventory: {
          Groups: {
            Label: 'Groups',
            Value: '0'
          },
          Items: {
            Label: 'Total Items',
            Value: '0'
          }
        }
      };
    }

    // Calculate total items and groups in inventory
    const totalGroups = shop.InventoryGroups?.length || 0;
    const totalItems = shop.InventoryGroups?.reduce((acc, group) => acc + (group.Items?.length || 0), 0) || 0;
    
    return {
      General: {
        Owner: shop.Owner?.Name ?? 'No Owner',
        Planet: shop.Planet?.Name ?? 'N/A',
        Location: waypoint(
          'Location',
          shop.Planet?.Properties?.TechnicalName ?? shop.Planet?.Name,
          shop.Coordinates,
          shop.Name
        )
      }
    };
  };

  // Custom edit configuration for shops
  const editConfig = {
    constructor: () => ({
      Name: '',
      Description: null,
      Planet: {
        Name: null
      },
      Coordinates: {
        Longitude: null,
        Latitude: null,
        Altitude: null
      },
      MaxGuests: null,
      HasAdditionalArea: false,
      Sections: [
        { Name: SECTION_NAMES[0], MaxItemPoints: null },
        { Name: SECTION_NAMES[1], MaxItemPoints: null }
      ]
    }),
    dependencies: ['planets'],
    controls: [
      {
        label: 'General',
        type: 'group',
        controls: [
          { 
            label: 'Name', 
            type: 'text', 
            '_get': x => x.Name, 
            '_set': (x, v) => x.Name = v 
          },
          { 
            label: 'Description', 
            type: 'textarea', 
            '_get': x => x.Description, 
            '_set': (x, v) => x.Description = v 
          },
          { 
            label: 'Planet', 
            type: 'select', 
            options: (_, d) => d.planets.filter(x => x.Id > 0).map(x => x.Name), 
            '_get': x => x.Planet?.Name, 
            '_set': (x, v, d) => {
              if (!x.Planet) x.Planet = { Name: null };
              x.Planet.Name = v;
              // Note: PlanetId should be set by backend validation
            },
            // Disable planet editing if owner is set
            '_if': (x) => !x.Owner?.Name
          },
          { 
            label: 'Coordinates', 
            type: 'waypoint',
            '_get': x => [
              x.Coordinates?.Longitude || 0, 
              x.Coordinates?.Latitude || 0, 
              x.Coordinates?.Altitude || 0
            ], 
            '_set': (x, v) => { 
              if (!x.Coordinates) x.Coordinates = { Longitude: null, Latitude: null, Altitude: null };
              if (v && v.length >= 3) { 
                x.Coordinates.Longitude = parseFloat(v[0]) || null;
                x.Coordinates.Latitude = parseFloat(v[1]) || null;
                x.Coordinates.Altitude = parseFloat(v[2]) || null;
              } 
            },
            // Disable coordinates editing if owner is set
            '_if': (x) => !x.Owner?.Name
          },
          { 
            label: 'Max Guests', 
            type: 'number', 
            step: 1, 
            min: 0, 
            '_get': x => x.MaxGuests, 
            '_set': (x, v) => x.MaxGuests = parseInt(v) || null 
          }
        ]
      },
      {
        label: 'Estate Areas',
        type: 'group',
        controls: [
          { 
            label: 'Has Additional Area', 
            type: 'checkbox', 
            '_get': x => x.HasAdditionalArea, 
            '_set': (x, v) => {
              x.HasAdditionalArea = v;
              // Add or remove Additional section
              if (v && !x.Sections.find(s => s.Name === SECTION_NAMES[2])) {
                x.Sections.push({ Name: SECTION_NAMES[2], MaxItemPoints: null });
              } else if (!v) {
                x.Sections = x.Sections.filter(s => s.Name !== SECTION_NAMES[2]);
              }
            }
          }
        ]
      },
      {
        label: 'Sections',
        type: 'array',
        size: (x) => x.HasAdditionalArea ? 3 : 2,
        config: {
          constructor: () => ({
            Name: '',
            MaxItemPoints: null
          }),
          controls: [
            { 
              label: 'Max Item Points', 
              type: 'number', 
              step: 1, 
              min: 0, 
              '_get': x => x.MaxItemPoints, 
              '_set': (x, v) => x.MaxItemPoints = parseInt(v) || null 
            }
          ]
        },
        indexFunc: (x, i) => {
          return x && x.Name === SECTION_NAMES[i];
        },
        itemNameFunc: (i) => {
          return `${SECTION_NAMES[i]} Area`;
        },
        '_get': x => {
          const result = [];
          
          // Always include Indoor and Display
          result[0] = x.Sections?.find(s => s.Name === SECTION_NAMES[0]) || { Name: SECTION_NAMES[0], MaxItemPoints: null };
          result[1] = x.Sections?.find(s => s.Name === SECTION_NAMES[1]) || { Name: SECTION_NAMES[1], MaxItemPoints: null };
          
          // Include Additional only if HasAdditionalArea is true
          if (x.HasAdditionalArea) {
            result[2] = x.Sections?.find(s => s.Name === SECTION_NAMES[2]) || { Name: SECTION_NAMES[2], MaxItemPoints: null };
          }
          
          return result;
        },
        '_set': (x, v) => {
          // Filter out null/undefined values and update sections
          x.Sections = v.filter(section => section != null);
          
          // Update HasAdditionalArea based on whether Additional section exists
          x.HasAdditionalArea = x.Sections.some(s => s.Name === SECTION_NAMES[2]);
        }
      }
    ]
  }

  // Function to check if user can edit this shop
  function canUserEditShop(shop, user) {
    if (!shop || !user?.verified) return false;
    if (user?.administrator) return true;
    
    // Owner check
    if (shop?.OwnerId != null && String(shop.OwnerId) === String(user.id)) return true;
    
    // Manager check
    return shop?.Managers?.some(manager => manager.user_id === user?.id) || false;
  }

  let viewInfoSection = {
    columns: ['Name', 'Owner', 'Planet', 'Coordinates'],
    columnWidths: ['1fr', '150px', '100px', '150px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Owner?.Name ?? 'No Owner',
        item.Planet?.Name ?? 'N/A',
        (item.Coordinates?.Longitude) && (item.Coordinates?.Latitude)
          ? `${item.Coordinates?.Longitude}, ${item.Coordinates?.Latitude}`
          : 'N/A',
      ];
    }
  };

  let tableViewInfo = {
    all: viewInfoSection,
    calypso: viewInfoSection,
    aris: viewInfoSection,
    cyrene: viewInfoSection,
    arkadia: viewInfoSection,
    monria: viewInfoSection,
    rocktropia: viewInfoSection,
    toulan: viewInfoSection,
    nextisland: viewInfoSection,
  }

  // Cache of item details by ItemId
  let itemDetails = {};

  // Prefetch all unique item IDs for the current shop using batch endpoint
  $: prefetchItems = (async () => {
    const ids = Array.from(new Set((data?.object?.InventoryGroups || [])
      .flatMap(g => (g?.Items || []).map(i => i.ItemId ?? i.item_id))
      .filter(Boolean)));
    if (ids.length === 0) { itemDetails = {}; return; }
    const results = await apiCall(fetch, `/items?Ids=${ids.join(',')}`);
    const map = {};
    (results || []).forEach(item => { if (item?.Id) map[item.Id] = item; });
    itemDetails = map;
  })();
</script>

<EntityViewer
  data={data}
  user={data.session.user}
  tableViewInfo={tableViewInfo}
  navButtonInfo={navButtonInfo}
  editConfig={editConfig}
  propertiesDataFunction={propertiesDataFunction}
  title='Shops'
  type='Shop'
  basePath='/market/shops'
  ownershipBasedEditing={true}
  getOwnershipInfo={canUserEditShop}
  let:object
  let:additional>

  <div class="flex-item">
    <div class="content-block">
      {#key object?.Id}
        {#if !object?.InventoryGroups || object.InventoryGroups.length === 0 || object.InventoryGroups.every(g => (g?.Items || []).length === 0)}
          <div style="text-align: center; color: var(--text-muted, #888); margin: 2rem 0; font-size: 1.1rem;">
            The shop owner has not yet added any items for display. Try again later!
          </div>
        {:else}
          {#each (object?.InventoryGroups || []) as group}
            {#if group && (group.Items || []).length > 0}
              <Table
                title={group.Name || group.name}
                header={{
                  values: ['Item', 'Stack Size', 'Markup %'],
                  widths: ['1fr', '120px', '120px']
                }}
                data={(group.Items || []).map(item => {
                  const id = item.ItemId ?? item.item_id;
                  const it = id ? itemDetails[id] : null;
                  return {
                    values: [
                      it?.Name || it?.name || 'Unknown Item',
                      (item.StackSize ?? item.stack_size ?? 0).toString(),
                      ((item.Markup ?? item.markup ?? 0).toFixed ? (item.Markup ?? 0).toFixed(2) : Number(item.Markup ?? item.markup ?? 0).toFixed(2)) + '%'
                    ],
                    links: [it ? getItemLink(it) : null]
                  };
                })}
                options={{ searchable: true, sortable: true }}
                style="margin-bottom: 1rem;" />
            {/if}
          {/each}
        {/if}
      {/key}
    </div>
  </div>
</EntityViewer>

<script>
  // @ts-nocheck
  import { navigate } from '$lib/util';

  import Table from './Table.svelte';

  let {
    planet,
    locations = $bindable([]),
    selected = $bindable(),
    hovered = $bindable()
  } = $props();

  let selectedPlanet = $state();
  let planetSimpleName = $state();

  $effect(() => {
    planetSimpleName = planet.Name.replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
  });
  $effect(() => {
    selectedPlanet = planetSimpleName;
  });
  $effect(() => {
    if (selectedPlanet !== planetSimpleName) {
      navigate('/maps/' + selectedPlanet);
    }
  });

  const planetList = {
    Calypso: [
      { Name: 'Calypso', _type: 'calypso' },
      { Name: 'Setesh', _type: 'setesh' },
      { Name: 'ARIS', _type: 'aris' }
    ],
    Arkadia: [
      { Name: 'Arkadia', _type: 'arkadia' },
      { Name: 'Arkadia Underground', _type: 'arkadiaunderground' },
      { Name: 'Arkadia Moon', _type: 'arkadiamoon' }
    ],
    Cyrene: [{ Name: 'Cyrene', _type: 'cyrene' }],
    Rocktropia: [
      { Name: 'ROCKtropia', _type: 'rocktropia' },
      { Name: 'HELL', _type: 'hell' },
      { Name: 'Hunt the THING', _type: 'huntthething'},
      { Name: 'Secret Island', _type: 'secretisland'}
    ],
    NextIsland: [
      { Name: 'Next Island', _type: 'nextisland' },
      { Name: 'Ancient Greece', _type: 'ancientgreece' }
    ],
    Toulan: [{ Name: 'Toulan', _type: 'toulan' }],
    Monria: [
      { Name: 'Monria', _type: 'monria' },
      { Name: 'DSEC9', _type: 'dsec9' },
    ],
    Space: [
      { Name: 'Space', _type: 'space' },
      { Name: 'Crystal Palace', _type: 'crystalpalace'},
      { Name: 'Asteroid F.O.M.A', _type: 'asteroidfoma'},
    ]
  };

  const DEFAULT_VISIBLE_LOCATION_TYPES = new Set(['Teleporter']);
  const DEFAULT_VISIBLE_AREA_TYPES = new Set(['LandArea']);
  let searchQuery = $state('');
  
  let filteredElements = $state([]);

  $effect(() => {
    if (locations) {
      filteredElements = locations.filter((item) => {
        const type = item?.Properties?.Type;
        const areaType = item?.Properties?.AreaType;
        if (!type) return false;
        if (areaType === 'MobArea') return false;
        if (type === 'Area' || areaType) {
          return DEFAULT_VISIBLE_AREA_TYPES.has(areaType);
        }
        return DEFAULT_VISIBLE_LOCATION_TYPES.has(type);
      });
      if (searchQuery.trim()) {
        const query = searchQuery.trim().toLowerCase();
        filteredElements = filteredElements.filter((item) => item?.Name?.toLowerCase().includes(query));
      }
    }
  });

  function getSymbolByLocation(location) {
    switch (location.Properties?.Type) {
      case 'Teleporter':
        return 'TP';
      case 'LandArea':
        return 'LA';
      case 'ZoneArea':
        return 'Z';
      case 'PvpLootArea':
        return 'PvP';
      case 'PvpArea':
        return 'PvP';
      case 'MobArea':
        return 'Mob';
      case 'Mission':
        return 'Msn';
      default:
        return '';
    }
  }


  function locationEquals(a, b) {
    return a.Name === b.Name
      && a.Properties.Type === b.Properties.Type
      && a.Properties.Coordinates.Longitude === b.Properties.Coordinates.Longitude
      && a.Properties.Coordinates.Latitude === b.Properties.Coordinates.Latitude
      && a.Properties.Coordinates.Altitude === b.Properties.Coordinates.Altitude;
  }

</script>

<style>
  .width100 {
    width: calc(100% - 8px);
  }

  .list-wrapper {
    position: relative;
  }

  .search-input {
    margin-bottom: 10px;
  }

  .big-dropdown {
    width: 100%;
    font-size: 26px;
  }

</style>

<div class="list-wrapper">
  <select bind:value={selectedPlanet} class="big-dropdown">
    {#each Object.values(planetList) as item}
      <optgroup label={item[0].Name}>
        {#each item as planet}
          <option value={planet._type}>{planet.Name}</option>
        {/each}
      </optgroup>
    {/each}
  </select>
  <br />

  <input class="search-input width100" type="text" placeholder="Search..." bind:value={searchQuery} onfocus={(evt) => { if (evt.target.selectionStart === evt.target.selectionEnd) evt.target.select(); }} style="font-size: 20px;">

  <div style="display: flex; overflow-x: auto; overflow-y: hidden; flex-grow: 1;">
    {#if filteredElements.length === 0}
    <div style="text-align: center; margin: auto;">
      <br />
      No items found...<br />
      <br />
      <input type="button" value="Clear Search" onclick={() => searchQuery = ''} />
    </div>
    {:else}
      <Table
        style='width: 300px'
        header={
          { 
            values: ['', 'Name'],
            widths: ['max-content', '1fr']
          }
        }
        data={
          filteredElements.map((item) => {
            return {
              values: [getSymbolByLocation(item), item.Name],
              trStyle: item === selected ? `font-weight: bold;` : '',
              payload: item
            };
          })
        }
        options={
          { 
            highlightOnHover: true,
            virtual: true
          }
        }
        onrowClick={(row) => {
          // Set selection immediately and update the URL
          const clicked = row.data.payload;
          selected = clicked;
          if (clicked?.Id) {
            navigate(`/maps/${planetSimpleName}/${clicked.Id}`);
          }
        }}
        onrowHover={(row) => {
          if (row === null) {
            hovered = null;
            return;
          }

          hovered = filteredElements.find(x => locationEquals(x, row.data.payload));
        }} />
    {/if}
  </div>
</div>

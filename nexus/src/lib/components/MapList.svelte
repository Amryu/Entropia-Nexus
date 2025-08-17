<script>
  // @ts-nocheck
  import { locationFilter } from '$lib/mapUtil';
  import { navigate } from '$lib/util';

  import Table from './Table.svelte';

  export let planet;
  export let locations = [];
  export let selected
  export let hovered;

  let selectedPlanet;
  let planetSimpleName;

  $: planetSimpleName = planet.Name.replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
  $: selectedPlanet = planetSimpleName;
  $: if (selectedPlanet !== planetSimpleName) {
    navigate('/maps/' + selectedPlanet);
  }

  const planetList = {
    Calypso: [
      { Name: 'Calypso', _type: 'calypso' },
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

  export const mapSettings = {
    filters: {
      search: '',
    },
    locations: {
      enabled: true,
      teleporters: true,
      outposts: false,
      missions: false,
    },
    areas: {
      enabled: true,
      landAreas: true,
      zoneAreas: true,
      pvpAreas: true,
      eventAreas: true,
      waveEventAreas: true,
    },
    mobs: {
      enabled: true,
      rookie: true,
      adept: true,
      intermediate: true,
      expert: true,
      uber: true,
    },
    settings: {
      showGrid: false,
      showSpaceLootable: false,
    }
  }

  const filterButtons = {
    Locations: {
      Label: 'Locations',
      Title: 'Locations',
      Toggles: [
        { Label: 'Teleporters', Type: 'teleporters' },
        { Label: 'Outposts', Type: 'outposts' },
        { Label: 'Missions', Type: 'missions' },
      ]
    },
    Areas: {
      Label: 'Areas', 
      Title: 'Areas',
      Toggles: [
        { Label: 'Land Areas', Type: 'landAreas' },
        { Label: 'Zones', Type: 'zoneAreas' },
        { Label: 'PvP Areas', Type: 'pvpAreas' },
        { Label: 'Event Areas', Type: 'eventAreas' },
        { Label: 'Wave Events', Type: 'waveEventAreas' },
      ]
    },
    Mobs: {
      Label: 'Mobs',
      Title: 'Mobs',
      Toggles: [
        { Label: 'Rookie', Type: 'rookie' },
        { Label: 'Adept', Type: 'adept' },
        { Label: 'Intermediate', Type: 'intermediate' },
        { Label: 'Expert', Type: 'expert' },
        { Label: 'Uber', Type: 'uber' },
      ]
    },
    Settings: {
      Label: 'Settings',
      Title: 'Settings',
      Toggles: [
        { Label: 'Show Tile Grid', Type: 'showGrid' },
        { Label: 'Show Lootable Areas in Space', Type: 'showSpaceLootable' },
      ]
    }
  };
  
  let filteredElements = [];

  $: if (locations) {
    filteredElements = locations.filter((item) => locationFilter(item, mapSettings));
  }

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

  let settingsDialogPos = { x: 0, y: 0 };
  let settingsDialogVisible = false;
  let settingsDialogType = null;

  function toggleSettingsDialog(e, type) {
    if (settingsDialogVisible && settingsDialogType === type) {
      settingsDialogVisible = false;
      return;
    }

    settingsDialogType = type;
    settingsDialogVisible = true;

    // position dialog below pressed button
    settingsDialogPos = {
      x: '0px',
      y: e.target.offsetTop + e.target.offsetHeight + 5 + 'px'
    };
  }

  function locationEquals(a, b) {
    return a.Name === b.Name
      && a.Properties.Type === b.Properties.Type
      && a.Properties.Coordinates.Longitude === b.Properties.Coordinates.Longitude
      && a.Properties.Coordinates.Latitude === b.Properties.Coordinates.Latitude
      && a.Properties.Coordinates.Altitude === b.Properties.Coordinates.Altitude;
  }

  $: if (!settingsDialogVisible) settingsDialogType = null;
</script>

<style>
  .width100 {
    width: calc(100% - 8px);
  }

  .button-container {
    display: grid;
    text-align: center;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    gap: 0 4px;
    width: 100%;
  }

  .square-button {
    width: 100%;
    height: 32px;
    background-color: var(--primary-color);
    border: none;
    margin-right: 5px;
    font-size: 12px;
  }

  .square-button:not([disabled]):hover {
    cursor: pointer;
    background-color: var(--hover-color);
  }

  .square-button:not([disabled]).selected {
    border: 1px solid var(--text-color);
    background-color: gray;
  }

  .list-wrapper {
    position: relative;
  }

  .info-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }

  .search-input {
    margin-bottom: 10px;
  }

  .big-dropdown {
    width: 100%;
    font-size: 26px;
  }

  .settings-dialog {
    position: absolute;
    width: 300px;
    background-color: var(--secondary-color);
    border: 1px solid var(--text-color);
    display: none;
    grid-template-columns: max-content 1fr;
    text-align: left;
  }

  .settings-dialog.visible {
    display: grid;
  }
</style>

<div class="list-wrapper">
  <select bind:value={selectedPlanet} class="big-dropdown">
    {#each Object.values(planetList) as item}
      <optgroup label={item[0].Name}>
        {#each item as planet}
          <option value={planet._type}>{planet.Name}</option>
        {/each}
    {/each}
  </select>
  <br />

  <div class="info-container">
    <div class="button-container">
      {#each Object.entries(filterButtons) as [key, value]}
        <div>
          <button class="square-button" title={value.Title} on:click={(e) => toggleSettingsDialog(e, key)} class:selected={settingsDialogType === key}>
            {value.Label}
          </button>
        </div>
      {/each}
    </div>
  </div>

  <input class="search-input width100" type="text" placeholder="Search..." bind:value={mapSettings.filters.search} on:focus={(evt) => { if (evt.target.selectionStart === evt.target.selectionEnd) evt.target.select(); }} style="font-size: 20px;">
  
  <div class="settings-dialog" style="top: {settingsDialogPos.y}" class:visible={settingsDialogVisible}>
    {#if settingsDialogType === 'Locations'}
      <input type="checkbox" bind:checked={mapSettings.locations.enabled} /> Enabled<br />
      {#each filterButtons.Locations.Toggles as item}
        <input type="checkbox" disabled={!mapSettings.locations.enabled} bind:checked={mapSettings.locations[item.Type]} /> {item.Label}<br />
      {/each}
    {/if}
    {#if settingsDialogType === 'Areas'}
    <input type="checkbox" bind:checked={mapSettings.areas.enabled} /> Enabled<br />
      {#each filterButtons.Areas.Toggles as item}
        <input type="checkbox" disabled={!mapSettings.areas.enabled} bind:checked={mapSettings.areas[item.Type]} /> {item.Label}<br />
      {/each}
    {/if}
    {#if settingsDialogType === 'Mobs'}
    <input type="checkbox" bind:checked={mapSettings.mobs.enabled} /> Enabled<br />
      {#each filterButtons.Mobs.Toggles as item}
        <input type="checkbox" disabled={!mapSettings.mobs.enabled} bind:checked={mapSettings.mobs[item.Type]} /> {item.Label}<br />
      {/each}
    {/if}
    {#if settingsDialogType === 'Settings'}
      {#each filterButtons.Settings.Toggles as item}
        <input type="checkbox" bind:checked={mapSettings.settings[item.Type]} /> {item.Label}<br />
      {/each}
    {/if}
    <input type="button" value="Close" on:click={() => settingsDialogVisible = false } style="grid-column: span 2;" />
  </div>

  <div style="display: flex; overflow-x: auto; overflow-y: hidden; flex-grow: 1;">
    {#if filteredElements.length === 0}
    <div style="text-align: center; margin: auto;">
      <br />
      No items found...<br />
      <br />
      <input type="button" value="Clear Search" on:click="{() => mapSettings.filters.search = ''}" />
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
        on:rowClick={(evt) => {
          // Set selection immediately and update the URL
          const clicked = evt.detail.data.payload;
          selected = clicked;
          locations = locations;
          if (clicked?.Id) {
            navigate(`/maps/${planetSimpleName}/${clicked.Id}`);
          }
        }}
        on:rowHover={(evt) => {
          if (evt.detail === null) {
            hovered = null;
            return;
          }

          hovered = filteredElements.find(x => locationEquals(x, evt.detail.data.payload));
        }} />
    {/if}
  </div>
</div>
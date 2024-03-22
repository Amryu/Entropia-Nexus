<script>
  // @ts-nocheck

  import { goto } from '$app/navigation';
  import { navigate } from '$lib/util';

  import Table from './Table.svelte';

  export let planets = [];
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
    Calypso: [{ Name: 'Calypso', _type: 'calypso' }],
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
      { Name: 'DSEC-9', _type: 'dsec9' },
    ],
    Space: [
      { Name: 'Space', _type: 'space' },
      { Name: 'Crystal Palace', _type: 'crystalpalace'},
      { Name: 'Asteroid F.O.M.A', _type: 'asteroidfoma'},
    ]
  };

  const filterButtons = {
    Teleporters: { Label: 'T', Title: 'Teleporters', Type: 'teleporters' },
    Areas: { Label: 'A', Title: 'Areas', Type: 'areas' },
    Creatures: { Label: 'C', Title: 'Creatures', Type: 'creatures' },
    Missions: { Label: 'M', Title: 'Missions', Type: 'missions' },
  };

  let search = '';
  let isMultiType;
  
  let filteredElements = [];

  $: if (locations) {
    filteredElements = locations.filter((item) => {
      return !(isMultiType && currentCategorySelected && item._type !== currentCategorySelected);
    });

    const searchTerm = search?.toLowerCase();
    filteredElements = !search.trim() ? filteredElements : filteredElements.filter((item) => {
      return item.Name.toLowerCase().includes(searchTerm);
    });
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
      case 'Creature':
        return 'C';
      case 'Mission':
        return 'M';
      default:
        return '';
    }
  }
</script>

<style>
  .width100 {
    width: calc(100% - 8px);
  }

  .button-container {
    display: flex;
    text-align: center;
  }

  .square-button {
    width: 32px;
    height: 32px;
    background-color: lightgrey;
    border: none;
    margin-right: 5px;
    font-size: 12px;
  }

  .square-button:not([disabled]):hover {
    cursor: pointer;
    background-color: white;
  }

  .square-button:not([disabled]).selected {
    border: 1px solid black;
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
      <!--
      <button class="square-button {currentCategorySelected === null ? 'selected' : ''}" on:click={() => currentCategorySelected = null} title='All'>All</button>
      {#each filterButtonInfo as buttonInfo}
        <button class="square-button {currentCategorySelected === buttonInfo.Type ? 'selected' : ''}" on:click={() => currentCategorySelected = buttonInfo.Type} title='{buttonInfo.Title}'>{buttonInfo.Label}</button>
      {/each}
      -->
    </div>
  </div>
  <input class="search-input width100" type="text" placeholder="Search..." bind:value={search} on:focus={(evt) => { if (evt.target.selectionStart === evt.target.selectionEnd) evt.target.select(); }} style="font-size: 20px;">

  <div style="display: flex; overflow-x: auto; overflow-y: hidden; flex-grow: 1;">
    {#if filteredElements.length === 0}
    <div style="text-align: center; margin: auto;">
      <br />
      No items found...<br />
      <br />
      <input type="button" value="Clear Search" on:click="{() => search = ''}" />
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
          let selectedName = evt.detail.data.values[1];
          
          selected = filteredElements.find(x => x.Name === selectedName);
          
          filteredElements = filteredElements;

          navigate(`/maps/${planetSimpleName}/${encodeURIComponent(selectedName)}`);
        }}
        on:rowHover={(evt) => {
          if (evt.detail === null) {
            hovered = null;
            return;
          }

          let hoveredName = evt.detail.data.values[1];

          hovered = filteredElements.find(x => x.Name === hoveredName);
        }} />
    {/if}
  </div>
</div>
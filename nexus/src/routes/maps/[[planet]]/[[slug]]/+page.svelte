<script>
  //@ts-nocheck
  import '$lib/style.css';

  import { page } from '$app/stores';
  import { loading } from '../../../../stores';
  import { getErrorMessage, getPlanetName } from '$lib/util';

  import MapList from '$lib/components/MapList.svelte';
  import Properties from '$lib/components/Properties.svelte';
  import Map from '$lib/components/Map.svelte';

  export let data;

  let items, location, locations, areas, error;
  let currentPlanet;
  let mapName;

  let mapSettings;
  let propertiesData = {};

  let selectedLocation = null;
  let hoveredLocation = null;

  $: if (data) {
    items = data.items;
    location = data.object;
    locations = data?.additional?.locations;
    areas = data?.additional?.areas;
    error = data.error;
    currentPlanet = data?.additional?.planet;

    mapName = currentPlanet.Name;
    selectedLocation = location;
  }

  $: if (selectedLocation) {
    console.log('page', selectedLocation);

    propertiesData = {
      General: {
        Name: selectedLocation.Name,
        Type: selectedLocation.Properties?.Type ?? 'N/A',
        Waypoint: `[${selectedLocation.Planet.Name}, ${selectedLocation.Properties.Coordinates.Longitude}, ${selectedLocation.Properties.Coordinates.Latitude}, ${selectedLocation.Properties.Coordinates.Altitude}, ${selectedLocation.Name}]`,
      }
    }
  }
</script>

<style>
  .flex-content {
    padding: 0;
    height: 100%;
    position: relative;
    overflow: hidden;
  }
</style>

<svelte:head>
  <title>Entropia Nexus - {$page.params.planet ? getPlanetName($page.params.planet) : 'No'} Map</title>
</svelte:head>
<div class="flex-container">
  <div class="map-list centered">
    <MapList
      planet={currentPlanet}
      planets={items}
      locations={locations}
      bind:selected={selectedLocation}
      bind:hovered={hoveredLocation}
      bind:mapSettings={mapSettings} />
  </div>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="flex-content">
    {#if error == null}
      {#if $loading}
        <div class="loading">
          <div class="spinner"></div>
        </div>
      {/if}
      <Map
        mapName={mapName}
        planet={currentPlanet}
        locations={locations}
        bind:selected={selectedLocation}
        bind:hovered={hoveredLocation} />
    {:else}
      <div class="info error"><h2>{error}</h2><br />{getErrorMessage(error)}</div>
    {/if}
  </div>
  <div class="prop-list centered">
    <Properties imageUrl='' data={propertiesData} />
  </div>
</div>
<script>
  //@ts-nocheck
  import '$lib/style.css';

  import { page } from '$app/stores';
  import { loading } from '../../../../stores';
  import { getErrorMessage, getParams, getPlanetName } from '$lib/util';

  import MapList from '$lib/components/MapList.svelte';
  import Properties, { waypoint } from '$lib/components/Properties.svelte';
  import Map from '$lib/components/Map.svelte';

  export let data;

  let params = getParams($page);

  let items, location, locations, error;
  let currentPlanet;
  let mapName;

  let mapSettings;
  let propertiesData = {};

  let selectedLocation = null;
  let hoveredLocation = null;
  let currentSlug = null;

  // Helper to find location by Id or slug
  function findLocationBySlug(slug, locations) {
    if (!slug || !locations) return null;
    // Try by Id first
    let found = locations.find(l => l.Id == slug);
    if (found) return found;
    // Fallback: try by name (case-insensitive, spaces/underscores ignored)
    const norm = s => s?.toString().replace(/[_\s]+/g, '').toLowerCase();
    return locations.find(l => norm(l.Name) === norm(slug));
  }

  $: if (data) {
    items = data.items;
    location = data.object;
    locations = data?.additional?.locations;
    error = data.error;
    currentPlanet = data?.additional?.planet;

    mapName = currentPlanet.Name;
  }

  // Keep selection in sync with slug, but only when the slug actually changes
  $: if (locations) {
    const slug = $page.params.slug;
    if (slug !== currentSlug) {
      currentSlug = slug;
      const found = findLocationBySlug(slug, locations) || location;
      selectedLocation = found;
    }
  }

  $: if (selectedLocation) {
    propertiesData = {
      General: {
        Name: selectedLocation.Name,
        Type: selectedLocation.Properties?.Type ?? 'N/A',
        Waypoint: waypoint(
          'Location',
          selectedLocation.Planet?.Properties?.TechnicalName ?? selectedLocation.Planet?.Name,
          selectedLocation.Properties?.Coordinates,
          selectedLocation.Name
        ),
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
  <title>Entropia Nexus - {params.planet ? getPlanetName(params.planet) : 'No'} Map</title>
  <meta name="description" content="An interactive map of {params.planet ? getPlanetName(params.planet) : 'Unknown'}.">
  <meta name="keywords" content="{getPlanetName(params.planet)}, Planet, Interactive Map, Interactive, Entropia Universe, Entropia, Entropia Nexus, EU, PE, Items, Mobs, Maps, Tools, MindArk, Wiki">
  <link rel="canonical" href="https://entropianexus.com/maps/{params.planet}" />
</svelte:head>
<div class="flex-container">
  <div class="map-list centered">
    <MapList
      planet={currentPlanet}
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
      <h1 style="display: none;">Interactive {mapName} Teleporter, Mob and Locations Map</h1>
      <Map
        mapName={mapName}
        planet={currentPlanet}
        locations={locations}
        mapSettings={mapSettings}
        bind:selected={selectedLocation}
        bind:hovered={hoveredLocation} />
    {:else}
      <div class="info error"><h2>{error}</h2><br />{getErrorMessage(error)}</div>
    {/if}
  </div>
  <div class="prop-list centered">
    <Properties imageUrl='' title={selectedLocation != null ? selectedLocation.Name : ''} data={propertiesData} />
  </div>
</div>
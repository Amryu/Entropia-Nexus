<script>
  //@ts-nocheck
  import Table from "$lib/components/Table.svelte";

  export let mobName;
  export let mobSpawns;

  function getWaypoint(planet, x, y, z, name) {
    return `[${planet.Properties.TechnicalName}, ${x}, ${y}, ${z}, ${name}]`;
  }
</script>

<h2>Locations</h2>
{#if (!mobSpawns || mobSpawns.length === 0)}
<br />  
<div>No data available.</div>
{:else}
<Table
  style="grid-column: span 2;"
  header = { 
    {
      values: ['Maturities', 'Other Mobs', 'Location', 'Density', 'Actions'],
      widths: ['1fr', 'minmax(100px, max-content)', 'minmax(100px, max-content)', 'minmax(100px, max-content)', 'max-content']
    }
  }
  data = {mobSpawns.map(spawn => {
    let waypoint = getWaypoint(spawn.Planet, spawn.Properties.Coordinates.Longitude, spawn.Properties.Coordinates.Latitude, spawn.Properties.Coordinates.Altitude, mobName);
    return {
      values: [
        spawn.Maturities.map(spawnMaturity => spawnMaturity.Maturity.Name || '<No Name>').join(', '),
        spawn.Maturities.map(spawnMaturity => spawnMaturity.Maturity.Mob.Name).filter((name, index, a) => name !== mobName && a.indexOf(name) === index).join(', ') || 'None',
        `<a href="#" onclick="navigator.clipboard.writeText(\`/wp ${waypoint}\`)" title="Click to Copy">/wp ${waypoint}</a>`,
        spawn.Properties.Density || 'N/A',
        `<a style="text-decoration: underline;" href="/maps/${spawn.Planet.Name.toLowerCase()}/${spawn.Id}" title="View on Map">Go to Map</a>`
      ]
    };
  })}
  options={{searchable: true}} />
{/if}
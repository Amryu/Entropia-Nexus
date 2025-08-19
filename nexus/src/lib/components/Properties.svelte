<script context="module">
  // Waypoint helper to be used by pages when constructing Properties data rows
  // Returns an object understood by this component to render a clickable waypoint value
  export function waypoint(label, planet, coordinates, name) {
    const lon = coordinates?.Longitude;
    const lat = coordinates?.Latitude;
    if (lon == null || lat == null) return 'N/A';

    return {
      Label: label,
      // Non-primitive Value to trigger auto display of lon/lat when Waypoint is present
      Value: `${lon}, ${lat}, ${coordinates?.Altitude ?? 100}`,
      Waypoint: {
        Planet: planet,
        Longitude: lon,
        Latitude: lat,
        Altitude: coordinates?.Altitude ?? 100,
        Name: name
      },
      Tooltip: 'Click to copy waypoint'
    };
  }
</script>
<script>
  // @ts-nocheck
  import '$lib/style.css';

  import Table from "$lib/components/Table.svelte";

  export let imageUrl;
  export let title;
  export let data = {};
</script>

<style>
  .container {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .image {
    min-width: 128px;
    min-height: 128px;
    max-width: 128px;
    max-height: 128px;
    background-image: url();
    background-size: cover;
    background-position: center;
    background-color: #ccc;
    margin-top: 8px;
    margin-bottom: 20px;
  }

  h2 {
    margin-top: 0;
    margin-bottom: 0;
    font-size: inherit;
  }
</style>

<div class="container">
  {#if data}
  <h2><img class="image" alt={title} title={title} style={imageUrl ? `background-image: url(${imageUrl});` : ''} /></h2>
  <div class="flex">
    {#each Object.entries(data) as [key, value]}
      {#if value !== null}
        <div class="mr-20">
          <Table
            style = 'text-align: left; width: 300px; max-width: 300px; margin-bottom: 2px;'
            title = {key}
            header = {
              {
                widths: ['100px', null],
              }
            }
            data = {
              Object.entries(value).map(([label, value]) => {
                if (typeof value === 'string' || typeof value === 'number') {
                  return [{
                    values: [label, value],
                    trStyle: value.Bold ? 'font-weight: bold;' : ''
                  }];
                }
                else if (value !== null && typeof value === 'object') {
                  if (Array.isArray(value.Value) && value.Value.length > 0) {
                    return value.Value.map((item, index) => {
                      return {
                        values: [value.Label ?? label, item],
                        spans: [value.Value.length, null],
                        tooltips: [value.Tooltip ?? null, null],
                        trStyle: value.Bold ? 'font-weight: bold;' : '',
                        links: [value.LinkKey ?? null, value.LinkValue ? value.LinkValue[index] : null],
                        copyables: [false, value.Copyable ? (Array.isArray(value.Copyable) ? value.Copyable[index] : true) : false],
                        onClicks: [null, value.OnClick ? (Array.isArray(value.OnClick) ? value.OnClick[index] : value.OnClick) : null]
                      }
                    });
                  }
                  else if (value.Value !== null && (typeof value.Value === 'string' || typeof value.Value === 'number')) {
                    // If a Waypoint payload is present, make the value (coordinates) clickable/copyable
                    const hasWp = value.Waypoint != null;
                    const lon = hasWp ? (value.Waypoint.Longitude ?? value.Waypoint.X ?? null) : null;
                    const lat = hasWp ? (value.Waypoint.Latitude ?? value.Waypoint.Y ?? null) : null;
                    const alt = hasWp ? (value.Waypoint.Altitude ?? value.Waypoint.Z ?? 100) : null;
                    const planet = hasWp ? (value.Waypoint.Planet ?? null) : null;
                    const name = hasWp ? (value.Waypoint.Name ?? null) : null;
                    const displayVal = hasWp && lon != null && lat != null ? `${lon}, ${lat}` : value.Value;
                    const onClick = value.OnClick ?? (hasWp && planet != null && lon != null && lat != null ? (() => {
                      const wp = `[${planet}, ${lon}, ${lat}, ${alt}, ${name ?? ''}]`;
                      navigator.clipboard.writeText(`/wp ${wp}`);
                    }) : null);
                    const isClickable = value.Copyable === true || (onClick != null);
                    return [{
                      values: [value.Label ?? label, displayVal],
                      // Show tooltip on the value cell so coordinates are underlined and discoverable
                      tooltips: [isClickable ? null : (value.Tooltip ?? null), isClickable ? (value.Tooltip ?? 'Click to copy waypoint') : null],
                      trStyle: value.Bold ? 'font-weight: bold;' : '',
                      links: [value.LinkKey ?? null, value.LinkValue ?? null],
                      copyables: [false, isClickable],
                      onClicks: [null, onClick]
                    }];
                  }
                }
                else if (value !== null) {
                  return [{
                    values: [label, value.Value],
                    tooltips: [value.Tooltip ?? null, null],
                    trStyle: value.Bold ? 'font-weight: bold;' : '',
                    links: [value.LinkKey ?? null, value.LinkValue ?? null],
                    copyables: [false, value.Copyable === true],
                    onClicks: [null, value.OnClick ?? null]
                  }];
                }
              }).flat().filter(x => x != null)
            } />
        </div>
      {/if}
    {/each}
  </div>
  {/if}
</div>
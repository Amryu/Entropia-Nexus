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
  <h2><img class="image" alt={title} title={title} /></h2>
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
                        links: [value.LinkKey ?? null, value.LinkValue ? value.LinkValue[index] : null]
                      }
                    });
                  }
                  else if (value.Value !== null && (typeof value.Value === 'string' || typeof value.Value === 'number')) {
                    return [{
                      values: [value.Label ?? label, value.Value],
                      tooltips: [value.Tooltip ?? null, null],
                      trStyle: value.Bold ? 'font-weight: bold;' : '',
                      links: [value.LinkKey ?? null, value.LinkValue ?? null]
                    }];
                  }
                }
                else if (value !== null) {
                  return [{
                    values: [label, value.Value],
                    tooltips: [value.Tooltip ?? null, null],
                    trStyle: value.Bold ? 'font-weight: bold;' : '',
                    links: [value.LinkKey ?? null, value.LinkValue ?? null]
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

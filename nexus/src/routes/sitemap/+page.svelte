<script>
  
  /**
   * @typedef {Object} Props
   * @property {any} data
   */

  /** @type {Props} */
  let { data } = $props();
</script>
<style>
  p {
    width: 600px;
    margin: auto;
    font-size: 20px;
    margin-bottom: 40px;
  }

  a {
    text-decoration: underline;
  }

  h2 {
    margin-left: 20px;
  }
</style>
<svelte:head>
  <title>Entropia Nexus - Sitemap</title>
  <meta name="description" content="A collection of all links on this site.">
  <meta name="keywords" content="Sitemap, Entropia Universe, Entropia, Entropia Nexus, EU, PE, Items, Mobs, Maps, Tools, MindArk, Wiki">
  <link rel="canonical" href="https://entropianexus.com/sitemap" />
</svelte:head>
<div style="width: 100%; height: 100%; overflow-y: auto;">
  <div style="margin-left: 100px; margin-right: 100px; margin-top: 50px;">
    <h1 style="text-align: center;">Sitemap</h1>
    {#if data && data.links}
      {#each Object.keys(data.links) as section (section)}
        <h2>{section[0].toUpperCase() + section.substring(1)}</h2>
        <ul>
          {#each data.links[section] as item}
            <li><a href={`https://entropianexus.com${item}`}>{`https://entropianexus.com${item}`}</a></li>
          {/each}
        </ul>
      {/each}
    {:else}
      <p>Loading...</p>
    {/if}
  </div>
</div>
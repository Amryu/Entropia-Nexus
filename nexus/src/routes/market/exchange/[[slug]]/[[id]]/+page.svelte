<script lang="ts">
  // @ts-nocheck
  import ExchangeBrowser from './ExchangeBrowser.svelte';
  
  let { data } = $props();
</script>

<svelte:head>
  <title>Exchange - Market - Entropia Nexus</title>
  <meta name="description" content="Browse item listings and market orders on the Entropia Universe exchange." />
  <link rel="canonical" href="https://entropianexus.com/market/exchange" />
</svelte:head>

<ExchangeBrowser {data} />
<script>
  //@ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import InventoryPage from './InventoryPage.svelte';

  let user = null;
  let loaded = false;

  $: user = $page.data?.user ?? null;

  onMount(() => {
    loaded = true;
  });
</script>

<svelte:head>
  <title>Inventory | Entropia Nexus</title>
</svelte:head>

{#if loaded}
  <InventoryPage {user} />
{/if}

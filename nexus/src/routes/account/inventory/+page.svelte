<script>
  import { run } from 'svelte/legacy';

  //@ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import InventoryPage from './InventoryPage.svelte';

  let user = $state(null);
  let loaded = $state(false);

  run(() => {
    user = $page.data?.session?.user ?? null;
  });

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

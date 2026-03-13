<script lang="ts">
  // @ts-nocheck
  import ExchangeBrowser from './ExchangeBrowser.svelte';
  
  let { data } = $props();
</script>

<ExchangeBrowser {data} />
<!--
  @component WeaponDamageGrid (deprecated)
  Wrapper for DamageBreakdownGrid to keep legacy imports working.
-->
<script>
  // @ts-nocheck
  import DamageBreakdownGrid from '$lib/components/wiki/DamageBreakdownGrid.svelte';

  export let weapon = null;
  export let showZeros = false;
  export let compact = false;
</script>

<DamageBreakdownGrid {weapon} {showZeros} {compact} />

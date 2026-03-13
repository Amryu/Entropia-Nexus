<!--
  @component WeaponDamageGrid (deprecated)
  Wrapper for DamageBreakdownGrid to keep legacy imports working.
-->
<script>
  // @ts-nocheck
  import DamageBreakdownGrid from '$lib/components/wiki/DamageBreakdownGrid.svelte';

  /**
   * @typedef {Object} Props
   * @property {any} [weapon]
   * @property {boolean} [showZeros]
   * @property {boolean} [compact]
   */

  /** @type {Props} */
  let { weapon = null, showZeros = false, compact = false } = $props();
</script>

<DamageBreakdownGrid {weapon} {showZeros} {compact} />

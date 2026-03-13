<!--
  @component MapLinkButton
  A link button that navigates to a spawn location on the map, used in MobLocations FancyTable.
-->
<script>
  
  /**
   * @typedef {Object} Props
   * @property {any} [row]
   * @property {string} [value]
   */

  /** @type {Props} */
  let { row = {}, value = '' } = $props();
</script>

<a
  href={value}
  class="map-link"
  title="View on map"
>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon>
    <line x1="8" y1="2" x2="8" y2="18"></line>
    <line x1="16" y1="6" x2="16" y2="22"></line>
  </svg>
  Map
</a>

<style>
  .map-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
    font-weight: 500;
    padding: 4px 8px;
    border-radius: 4px;
    transition: background-color 0.15s;
  }

  .map-link:hover {
    background-color: var(--hover-color);
    text-decoration: underline;
  }
</style>

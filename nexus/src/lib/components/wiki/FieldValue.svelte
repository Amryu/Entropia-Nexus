<!--
  @component FieldValue
  Small helper that renders either a formatted value or an inline
  MissingFieldCTA when the value is missing. Keeps infobox stat rows tidy:

    <span class="stat-value">
      <FieldValue value={weapon.Decay} field="Decay" category="weapon"
                  format={(v) => v.toFixed(4) + ' PEC'} onContribute={startEdit} />
    </span>

  Treats null/undefined/empty string/NaN/empty collections as missing.
  Numbers like 0 and booleans like false are kept (they're real data).
-->
<script>
  // @ts-nocheck
  import MissingFieldCTA from './MissingFieldCTA.svelte';
  import { isMissing } from './contributeCategories.js';

  /**
   * @typedef {Object} Props
   * @property {any} value
   * @property {string} field
   * @property {string} [category]
   * @property {(v: any) => string} [format]
   * @property {boolean} [compact]
   * @property {() => void} [onContribute]
   * @property {import('svelte').Snippet<[any]>} [children]
   */

  /** @type {Props} */
  let {
    value,
    field,
    category = 'general',
    format,
    compact = false,
    onContribute,
    children,
  } = $props();

  let missing = $derived(isMissing(value));
</script>

{#if missing}
  <MissingFieldCTA {field} {category} {compact} {onContribute} />
{:else if children}
  {@render children(value)}
{:else if format}
  {format(value)}
{:else}
  {value}
{/if}

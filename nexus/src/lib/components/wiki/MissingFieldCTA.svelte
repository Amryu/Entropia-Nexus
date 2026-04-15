<!--
  @component MissingFieldCTA
  Inline single-field variant. Renders a small "+ Add {field}" link inside
  a stat-value span, visually popping so a visitor scanning for a specific
  stat sees immediately that the field is editable.

  Layout-neutral by design: renders as inline text, inherits font metrics,
  and avoids any padding/transform/box-shadow that would shift neighbouring
  elements between populated and missing rows.
-->
<script>
  // @ts-nocheck
  import ContributeDialog from './ContributeDialog.svelte';

  /**
   * @typedef {Object} Props
   * @property {string} field
   * @property {string} [category]
   * @property {boolean} [compact]
   * @property {() => void} [onContribute]
   */

  /** @type {Props} */
  let {
    field,
    category = 'general',
    compact = false,
    onContribute,
  } = $props();

  let dialogOpen = $state(false);

  function openDialog(e) {
    e?.stopPropagation?.();
    dialogOpen = true;
  }

  function closeDialog() {
    dialogOpen = false;
  }
</script>

<button
  type="button"
  class="missing-field-cta"
  onclick={openDialog}
  title={`Add ${field}`}
  aria-label={`Add ${field}`}
>+ {compact ? 'add' : `Add ${field}`}</button>

<ContributeDialog
  show={dialogOpen}
  {field}
  {category}
  {onContribute}
  onclose={closeDialog}
/>

<style>
  .missing-field-cta {
    /* Inline text, not a block - must never reflow the surrounding row. */
    display: inline;
    padding: 0;
    margin: 0;
    border: 0;
    background: none;
    /* Inherit all type metrics so a row with this CTA is pixel-identical to
       a row with plain text. */
    font: inherit;
    line-height: inherit;
    color: var(--accent-color, #4a9eff);
    text-decoration: underline;
    text-decoration-style: dashed;
    text-underline-offset: 2px;
    cursor: pointer;
    white-space: nowrap;
  }

  .missing-field-cta:hover {
    /* Hover keeps the same colour family so it stays readable on dark
       backgrounds. Bumps to the brighter accent-hover variable and uses
       a solid underline instead of dashed. No box growth. */
    color: var(--accent-color-hover, #4a9eff);
    text-decoration-style: solid;
    filter: brightness(1.15);
  }

  .missing-field-cta:focus-visible {
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: 1px;
    border-radius: 2px;
  }
</style>

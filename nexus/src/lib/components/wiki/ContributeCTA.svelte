<!--
  @component ContributeCTA
  Block-variant empty-state CTA. Replaces existing `.no-data` divs on wiki
  sections. Styled to match the muted empty-state language already used in
  the codebase, with an accent button underneath that opens ContributeDialog.
-->
<script>
  // @ts-nocheck
  import ContributeDialog from './ContributeDialog.svelte';

  /**
   * @typedef {Object} Props
   * @property {string} [message]
   * @property {string} [category]
   * @property {() => void} [onContribute]
   */

  /** @type {Props} */
  let {
    message = 'No data available.',
    category = 'general',
    onContribute,
  } = $props();

  let dialogOpen = $state(false);

  function openDialog() {
    dialogOpen = true;
  }

  function closeDialog() {
    dialogOpen = false;
  }
</script>

<div class="contribute-cta">
  <p class="contribute-cta-message">{message}</p>
  <button type="button" class="contribute-cta-btn" onclick={openDialog}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
    <span>Help fill this in</span>
  </button>
  <p class="contribute-cta-hint">Earn PED through our bounty program.</p>
</div>

<ContributeDialog
  show={dialogOpen}
  {category}
  {onContribute}
  onclose={closeDialog}
/>

<style>
  .contribute-cta {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 28px 20px;
    text-align: center;
  }

  .contribute-cta-message {
    margin: 0;
    color: var(--text-muted, #999);
    font-style: italic;
    font-size: 14px;
  }

  .contribute-cta-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: filter 0.15s, transform 0.15s;
    font-family: inherit;
  }

  .contribute-cta-btn:hover {
    filter: brightness(1.1);
    transform: translateY(-1px);
  }

  .contribute-cta-hint {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted, #999);
  }
</style>

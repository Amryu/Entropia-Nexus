<!--
  @component ExchangeRedirectWarning
  Warning shown when creating an auction for a single non-customized item.
  Suggests using the Exchange instead.
-->
<script>
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  

  
  /**
   * @typedef {Object} Props
   * @property {boolean} [visible]
   * @property {number|null} [itemId]
   */

  /** @type {Props} */
  let { visible = false, itemId = null } = $props();

  let dismissed = $state(false);

  function handleDismiss() {
    dismissed = true;
    dispatch('dismiss');
  }
</script>

{#if visible && !dismissed}
  <div class="redirect-warning">
    <div class="warning-icon">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
    </div>
    <div class="warning-content">
      <p class="warning-text">
        Single standard items are better suited for the <strong>Exchange</strong>,
        which has lower fees and instant matching.
      </p>
      <div class="warning-actions">
        {#if itemId}
          <a href="/market/exchange?item={itemId}" class="btn btn-accent">Go to Exchange</a>
        {/if}
        <button class="btn btn-secondary" onclick={handleDismiss}>Continue with Auction</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .redirect-warning {
    display: flex;
    gap: 12px;
    padding: 1rem;
    margin-bottom: 1.5rem;
    background: var(--warning-bg);
    border: 1px solid var(--warning-color);
    border-radius: 8px;
  }

  .warning-icon {
    flex-shrink: 0;
    color: var(--warning-color);
    margin-top: 2px;
  }

  .warning-content {
    flex: 1;
  }

  .warning-text {
    margin: 0 0 0.75rem 0;
    font-size: 0.9rem;
    color: var(--text-color);
    line-height: 1.5;
  }

  .warning-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .btn {
    padding: 6px 14px;
    font-size: 0.85rem;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
  }

  .btn-accent {
    background: var(--accent-color);
    border: 1px solid var(--accent-color);
    color: white;
  }

  .btn-accent:hover {
    background: var(--accent-color-hover, #3a8eef);
  }

  .btn-secondary {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .btn-secondary:hover {
    background: var(--hover-color);
  }
</style>

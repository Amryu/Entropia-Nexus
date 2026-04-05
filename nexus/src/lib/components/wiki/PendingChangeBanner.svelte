<!--
  @component PendingChangeBanner
  Shared pending-change banner for wiki pages.
-->
<script>
  /**
   * @typedef {Object} Props
   * @property {any} [pendingChange]
   * @property {boolean} [viewing]
   * @property {any} [onToggle]
   * @property {string} [entityLabel] Noun for the entity, e.g. "weapon", "mob", "location"
   */

  /** @type {Props} */
  let { pendingChange = null, viewing = false, onToggle = () => {}, entityLabel = 'entity' } = $props();

  let showBanner = $derived(!!pendingChange);
  let author = $derived(pendingChange?.author_name || 'Unknown');
</script>

{#if showBanner}
  <div class="pending-change-banner" class:viewing>
    <div class="banner-content">
      <span class="banner-icon">⏳</span>
      <span class="banner-text">
        This {entityLabel} has a pending change by <strong>{author}</strong> ({pendingChange.state})
      </span>
    </div>
    <button class="banner-toggle" onclick={onToggle}>
      {viewing ? 'View Current' : 'View Pending'}
    </button>
  </div>
{/if}

<style>
  .pending-change-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    margin-bottom: 16px;
    background-color: var(--warning-bg);
    border: 1px solid var(--warning-color);
    border-radius: 8px;
  }

  .pending-change-banner.viewing {
    border-color: var(--accent-color);
  }

  .banner-content {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
    flex: 1;
  }

  .banner-icon {
    font-size: 18px;
    flex-shrink: 0;
  }

  .banner-text {
    font-size: 14px;
    color: var(--text-color);
  }

  .banner-toggle {
    padding: 6px 12px;
    background-color: var(--accent-color);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .banner-toggle:hover {
    background-color: var(--accent-color-hover);
  }

  @media (max-width: 899px) {
    .pending-change-banner {
      flex-direction: column;
      align-items: flex-start;
    }
    .banner-toggle {
      align-self: stretch;
      text-align: center;
    }
  }
</style>

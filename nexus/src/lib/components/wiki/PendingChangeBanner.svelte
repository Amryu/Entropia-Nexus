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
   */

  /** @type {Props} */
  let { pendingChange = null, viewing = false, onToggle = () => {} } = $props();

  let showBanner = $derived(!!pendingChange);
</script>

{#if showBanner}
  <div class="pending-change-banner" class:viewing>
    <div class="banner-content">
      <span class="banner-icon">⏳</span>
      <span class="banner-text">
        {#if viewing}
          Viewing {pendingChange.state === 'Pending' ? 'pending' : 'draft'} changes
        {:else}
          {pendingChange.state === 'Pending' ? 'Pending changes' : 'Draft changes'} available
        {/if}
      </span>
    </div>
    <button class="banner-toggle" onclick={onToggle}>
      {viewing ? 'View Original' : 'View Changes'}
    </button>
  </div>
{/if}

<!--
  @component PendingChangeBanner
  Shared pending-change banner for wiki pages.
-->
<script>
  // @ts-nocheck
  export let pendingChange = null;
  export let viewing = false;
  export let onToggle = () => {};

  $: showBanner = !!pendingChange;
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
    <button class="banner-toggle" on:click={onToggle}>
      {viewing ? 'View Original' : 'View Changes'}
    </button>
  </div>
{/if}

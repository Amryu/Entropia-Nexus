<!--
  @component AuctionCountdown
  Live countdown timer for auction end time.
  Switches to urgent styling in the last hour.
-->
<script>
  import { onMount, onDestroy } from 'svelte';
  import { getTimeRemaining } from '$lib/common/auctionUtils.js';

  /** @type {string|Date} Auction end time */
  export let endsAt;

  /** @type {boolean} Whether auction is frozen (paused countdown) */
  export let frozen = false;

  /** @type {'normal'|'compact'} Display size */
  export let size = 'normal';

  let remaining = getTimeRemaining(endsAt);
  let interval;

  function update() {
    remaining = getTimeRemaining(endsAt);
    if (remaining.expired && interval) {
      clearInterval(interval);
    }
  }

  onMount(() => {
    if (!frozen) {
      interval = setInterval(update, 1000);
    }
  });

  onDestroy(() => {
    if (interval) clearInterval(interval);
  });

  $: urgent = !frozen && remaining.total > 0 && remaining.total < 3600000; // Last hour
  $: veryUrgent = !frozen && remaining.total > 0 && remaining.total < 300000; // Last 5 min

  function pad(n) {
    return String(n).padStart(2, '0');
  }
</script>

{#if frozen}
  <span class="countdown frozen {size}">Frozen</span>
{:else if remaining.expired}
  <span class="countdown expired {size}">Ended</span>
{:else}
  <span class="countdown {size}" class:urgent class:veryUrgent>
    {#if remaining.days > 0}
      {remaining.days}d {pad(remaining.hours)}h {pad(remaining.minutes)}m
    {:else if remaining.hours > 0}
      {remaining.hours}h {pad(remaining.minutes)}m {pad(remaining.seconds)}s
    {:else}
      {pad(remaining.minutes)}m {pad(remaining.seconds)}s
    {/if}
  </span>
{/if}

<style>
  .countdown {
    font-variant-numeric: tabular-nums;
    font-weight: 500;
  }

  .countdown.normal {
    font-size: 0.9rem;
  }

  .countdown.compact {
    font-size: 0.8rem;
  }

  .countdown.urgent {
    color: var(--warning-color);
  }

  .countdown.veryUrgent {
    color: var(--error-color);
    animation: pulse 1s ease-in-out infinite;
  }

  .countdown.frozen {
    color: var(--error-color);
    font-style: italic;
  }

  .countdown.expired {
    color: var(--text-muted);
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
</style>

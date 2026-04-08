<!--
  @component AdSlot
  Renders a Google AdSense manual ad unit. Handles SPA re-initialization,
  adblock detection, and SSR safety.

  Props:
  - adSlot: string - The AdSense ad unit slot ID
  - adFormat: 'auto' | 'rectangle' | 'vertical' | 'horizontal' | 'autorelaxed' - Ad format
  - fullWidthResponsive: boolean - Whether the ad should be full-width responsive
  - width: string | undefined - Fixed width (e.g. '160px')
  - height: string | undefined - Fixed height (e.g. '600px')
  - style: string - Additional inline CSS for the container
  - matchedContentRows: number | undefined - Row count for multiplex (autorelaxed) ads
  - matchedContentColumns: number | undefined - Column count for multiplex (autorelaxed) ads
-->
<script>
  import { page } from '$app/stores';
  import { browser } from '$app/environment';
  import { getRevenueBlocked } from '$lib/stores/revenue-state.svelte.js';

  const AD_CLIENT = 'ca-pub-9726361132383377';

  let {
    adSlot,
    adFormat = 'auto',
    fullWidthResponsive = true,
    width = undefined,
    height = undefined,
    style = '',
    matchedContentRows = undefined,
    matchedContentColumns = undefined
  } = $props();

  // Track path to regenerate ads on SPA navigation
  let adKey = $state(0);
  let prevPath = '';

  $effect(() => {
    const newPath = $page.url.pathname;
    if (prevPath && newPath !== prevPath) {
      adKey++;
    }
    prevPath = newPath;
  });

  let blocked = $derived(browser && getRevenueBlocked());

  // Build inline style for the ins element
  let insStyle = $derived.by(() => {
    let s = 'display:block;';
    if (width) s += `width:${width};`;
    if (height) s += `height:${height};`;
    if (style) s += style;
    return s;
  });

  /** Svelte action: initialize the ad unit after DOM insertion */
  function initAd(node) {
    if (!browser) return;
    // Small delay to let the DOM settle before pushing
    const timer = setTimeout(() => {
      try {
        (/** @type {any} */ (window).adsbygoogle = /** @type {any} */ (window).adsbygoogle || []).push({});
      } catch {
        // Ad init failed (blocked, not loaded, etc.) - silent
      }
    }, 100);
    return {
      destroy() {
        clearTimeout(timer);
      }
    };
  }
</script>

{#if !blocked}
  {#key adKey}
    <div class="ad-slot-container">
      <ins
        class="adsbygoogle"
        style={insStyle}
        data-ad-client={AD_CLIENT}
        data-ad-slot={adSlot}
        data-ad-format={adFormat}
        data-full-width-responsive={fullWidthResponsive}
        data-matched-content-rows-num={matchedContentRows}
        data-matched-content-columns-num={matchedContentColumns}
        use:initAd
      ></ins>
    </div>
  {/key}
{/if}

<style>
  .ad-slot-container {
    overflow: hidden;
    /* Prevent ad iframes from capturing scroll events */
    touch-action: pan-y;
  }

  .ad-slot-container :global(iframe) {
    pointer-events: auto;
    touch-action: pan-y;
  }
</style>

<!--
  @component AdSlot
  Renders a Google AdSense manual ad unit. Handles SPA re-initialization,
  adblock detection, and SSR safety.

  The parent wrapper starts hidden and is revealed only when an ad actually
  fills the slot, preventing empty gaps from margins on unfilled slots.

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
  import { getContentBlocked } from '$lib/stores/feature-state.svelte.js';

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

  let blocked = $derived(browser && getContentBlocked());

  // Build inline style for the ins element
  // Fixed-size ads (with width+height) use inline-block; responsive ads use block
  let insStyle = $derived.by(() => {
    let s = (width && height) ? 'display:inline-block;' : 'display:block;';
    if (width) s += `width:${width};`;
    if (height) s += `height:${height};`;
    if (style) s += style;
    return s;
  });

  /** Svelte action: initialize the ad unit after DOM insertion.
   *  Uses IntersectionObserver to defer init until the slot is actually visible,
   *  which handles responsive layouts where the container starts as display:none. */
  function initAd(node) {
    if (!browser) return;
    let initialized = false;

    // AdSense requires slots to be visible with real dimensions to process them.
    // Render visible, then collapse only unfilled slots (Google's approved method).
    const wrapper = node.closest('.ad-slot-container')?.parentElement;

    function pushAd() {
      if (initialized) return;
      initialized = true;
      try {
        (/** @type {any} */ (window).adsbygoogle = /** @type {any} */ (window).adsbygoogle || []).push({});
      } catch {
        // Ad init failed (blocked, not loaded, etc.) - silent
      }
    }

    function collapseWrapper() {
      // In dev mode, keep the wrapper visible so debug placeholders are shown
      if (wrapper && !import.meta.env.DEV) wrapper.style.display = 'none';
    }

    function showDebugPlaceholder(status) {
      if (!wrapper || !import.meta.env.DEV) return;
      const ph = document.createElement('div');
      ph.style.cssText = 'border:2px dashed #4a9eff;background:#1a1a2e;color:#4a9eff;padding:12px;font:12px/1.4 sans-serif;border-radius:4px;text-align:center;margin:4px 0;';
      ph.textContent = `AdSense: ${status} (slot ${adSlot})`;
      node.closest('.ad-slot-container')?.appendChild(ph);
    }

    // Watch for AdSense setting status attributes on the <ins> element.
    // data-ad-status = "filled" | "unfilled" (set on most slots)
    // data-adsbygoogle-status = "done" (set on ALL processed slots)
    // Some slots get "done" without data-ad-status - treat as unfilled.
    let resolved = false;
    const statusObserver = new MutationObserver(() => {
      if (resolved) return;
      const adStatus = node.getAttribute('data-ad-status');
      const doneStatus = node.getAttribute('data-adsbygoogle-status');

      if (adStatus === 'filled') {
        resolved = true;
        showDebugPlaceholder('filled');
        statusObserver.disconnect();
      } else if (adStatus === 'unfilled') {
        resolved = true;
        collapseWrapper();
        showDebugPlaceholder('unfilled - no ad available');
        statusObserver.disconnect();
      } else if (doneStatus === 'done' && !adStatus) {
        // AdSense processed but silently produced nothing
        resolved = true;
        collapseWrapper();
        showDebugPlaceholder('done but empty - no ad rendered');
        statusObserver.disconnect();
      }
    });
    statusObserver.observe(node, { attributes: true, attributeFilter: ['data-ad-status', 'data-adsbygoogle-status'] });

    // Fallback: if neither status is set (script blocked), collapse after 5s.
    const sizeFallback = setTimeout(() => {
      if (resolved) return;
      if (!node.querySelector('iframe') && node.offsetHeight <= 1) {
        collapseWrapper();
        showDebugPlaceholder('no response - script blocked or not loaded');
      }
      statusObserver.disconnect();
    }, 5000);

    // Use IntersectionObserver to wait until the element is actually visible
    // This handles responsive layouts where ads are in display:none containers
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && !initialized) {
          // Small delay to let the DOM settle
          setTimeout(pushAd, 100);
          observer.disconnect();
        }
      }
    }, { threshold: 0 });

    observer.observe(node);

    // Fallback: if the element is already visible, init after a short delay
    const fallback = setTimeout(() => {
      if (!initialized && node.offsetParent !== null) {
        pushAd();
        observer.disconnect();
      }
    }, 300);

    return {
      destroy() {
        observer.disconnect();
        statusObserver.disconnect();
        clearTimeout(fallback);
        clearTimeout(sizeFallback);
      }
    };
  }
</script>

{#if !blocked}
  {#key adKey}
    <div class="ad-slot-container" class:multiplex={adFormat === 'autorelaxed'}>
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

  /* Multiplex (autorelaxed) ads render tall content grids - cap to a
     reasonable height so they don't dominate the page. */
  .ad-slot-container.multiplex {
    max-height: 150px;
  }

  .ad-slot-container :global(iframe) {
    pointer-events: auto;
    touch-action: pan-y;
  }
</style>

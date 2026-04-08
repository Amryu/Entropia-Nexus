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

    // Collapse the parent wrapper (e.g. .wiki-content-ad) to zero height so
    // unfilled ads don't leave a visible gap.  We use height:0 + overflow:hidden
    // instead of display:none so the <ins> element stays in the DOM and the
    // IntersectionObserver can still fire, allowing AdSense to process the slot.
    const wrapper = node.closest('.ad-slot-container')?.parentElement;
    const savedStyles = wrapper ? { height: wrapper.style.height, overflow: wrapper.style.overflow, margin: wrapper.style.margin, padding: wrapper.style.padding } : null;
    if (wrapper) {
      wrapper.style.height = '0';
      wrapper.style.overflow = 'hidden';
      wrapper.style.margin = '0';
      wrapper.style.padding = '0';
    }

    function pushAd() {
      if (initialized) return;
      initialized = true;
      try {
        (/** @type {any} */ (window).adsbygoogle = /** @type {any} */ (window).adsbygoogle || []).push({});
      } catch {
        // Ad init failed (blocked, not loaded, etc.) - silent
      }
    }

    function revealWrapper() {
      if (wrapper && savedStyles) {
        wrapper.style.height = savedStyles.height;
        wrapper.style.overflow = savedStyles.overflow;
        wrapper.style.margin = savedStyles.margin;
        wrapper.style.padding = savedStyles.padding;
      }
    }

    function collapseWrapper() {
      if (wrapper) wrapper.style.display = 'none';
    }

    // Watch for AdSense setting data-ad-status on the <ins> element.
    const statusObserver = new MutationObserver(() => {
      const status = node.getAttribute('data-ad-status');
      if (status === 'filled') {
        revealWrapper();
        statusObserver.disconnect();
      } else if (status === 'unfilled') {
        collapseWrapper();
        statusObserver.disconnect();
      }
    });
    statusObserver.observe(node, { attributes: true, attributeFilter: ['data-ad-status'] });

    // Fallback: if data-ad-status is never set, check for content after 5s.
    const sizeFallback = setTimeout(() => {
      if (node.querySelector('iframe') || node.offsetHeight > 1) {
        revealWrapper();
      } else {
        collapseWrapper();
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

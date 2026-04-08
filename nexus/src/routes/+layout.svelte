<script>
  //@ts-nocheck
  import '$lib/style.css';

  import { pageParams, initialViewportWidth } from '../stores.js';

  import Menu from "$lib/components/Menu.svelte";
  import Toasts from "$lib/components/Toasts.svelte";
  import ConsentBanner from "$lib/components/ConsentBanner.svelte";
  import SupportNotice from "$lib/components/SupportNotice.svelte";
  import { onMount, onDestroy } from 'svelte';
  import { page, navigating } from '$app/stores';
  import { invalidateAll, afterNavigate } from '$app/navigation';
  import { decodeURIComponentSafe, copyToClipboard } from '$lib/util.js';

  let { data, children } = $props();
  // SvelteKit passes params to all layouts/pages - we use $page.params instead
  // Declared as const to accept prop without Svelte "unused" warning
  export const params = {};

  $page;

  let isEmbed = $derived($page.url.searchParams.get('embed') === '1');

  // Set initial viewport width from server-side detection
  $effect(() => {
    if (data.initialViewportWidth) {
      initialViewportWidth.set(data.initialViewportWidth);
    }
  });

  // Whenever the page store updates, decode the parameters
  $effect(() => {
    pageParams.set(
      Object.fromEntries(
        Object.entries($page.params).map(([key, value]) => [
          key,
          decodeURIComponentSafe(value)
        ])
      )
    );
  });
  
  // Poll verification status for unverified users every 30s
  const VERIFICATION_POLL_MS = 30_000;
  let verificationTimer = null;

  function startVerificationPoll() {
    stopVerificationPoll();
    verificationTimer = setInterval(async () => {
      try {
        const res = await fetch('/api/user/verified');
        if (!res.ok) return;
        const { verified } = await res.json();
        if (verified) {
          stopVerificationPoll();
          await invalidateAll();
        }
      } catch { /* network error, retry next interval */ }
    }, VERIFICATION_POLL_MS);
  }

  function stopVerificationPoll() {
    if (verificationTimer) {
      clearInterval(verificationTimer);
      verificationTimer = null;
    }
  }

  // Start/stop polling reactively based on user verification state
  $effect(() => {
    const user = data?.session?.user;
    if (user && !user.verified) {
      startVerificationPoll();
    } else {
      stopVerificationPoll();
    }
  });

  // Viewport cookie storage - debounced to avoid excessive cookie writes
  let viewportDebounceTimer = null;
  const VIEWPORT_COOKIE_NAME = 'nexus_viewport';
  const VIEWPORT_DEBOUNCE_MS = 1000;

  function storeViewportWidth(width) {
    if (typeof document === 'undefined') return;
    // Store for 30 days
    const expires = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toUTCString();
    document.cookie = `${VIEWPORT_COOKIE_NAME}=${width}; path=/; expires=${expires}; SameSite=Lax`;
  }

  function handleResize() {
    if (viewportDebounceTimer) {
      clearTimeout(viewportDebounceTimer);
    }
    viewportDebounceTimer = setTimeout(() => {
      storeViewportWidth(window.innerWidth);
    }, VIEWPORT_DEBOUNCE_MS);
  }

  // Global click-to-copy for inline waypoint elements in rendered rich text
  function handleWaypointClick(e) {
    const wpSpan = e.target.closest('.waypoint-inline[data-waypoint]');
    if (!wpSpan) return;
    const waypoint = wpSpan.getAttribute('data-waypoint');
    if (!waypoint) return;
    copyToClipboard(`/wp ${waypoint}`).then(success => {
      if (!success) return;
      wpSpan.classList.add('copied');
      setTimeout(() => wpSpan.classList.remove('copied'), 1500);
    });
  }

  onMount(() => {
    // Ensure dark mode — remove any leftover light-mode class from previous versions
    document.body.classList.remove('light-mode');

    if (typeof window !== 'undefined') {
      // Store initial viewport width
      storeViewportWidth(window.innerWidth);

      // Listen for resize to update the cookie
      window.addEventListener('resize', handleResize);
    }

    // Global waypoint copy handler for all rendered description content
    document.addEventListener('click', handleWaypointClick);

    // Analytics beacon: proves JS execution for bot detection (no cookies, no tracking)
    if (navigator.sendBeacon) navigator.sendBeacon('/api/beacon');
  });

  // Re-trigger AdSense auto ads on SPA navigation so Google re-scans the new page content
  afterNavigate(() => {
    try {
      const adsbygoogle = /** @type {any} */ (window).adsbygoogle;
      if (adsbygoogle) adsbygoogle.push({});
    } catch { /* ad script not loaded or blocked */ }
  });

  onDestroy(() => {
    stopVerificationPoll();
    if (viewportDebounceTimer) {
      clearTimeout(viewportDebounceTimer);
    }
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', handleResize);
      document.removeEventListener('click', handleWaypointClick);
    }
  });
</script>
<style global>
:global(html), :global(body) {
  height: 100%;
  margin: 0;
  padding: 0;
  font-family: Calibri, 'Trebuchet MS', sans-serif;
  overflow: hidden;
  color: var(--text-color);
  background-color: var(--primary-color);
}

:global(a) {
  text-decoration: none;
  color: var(--text-color);
}

.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.app-content {
  flex: 1;
  overflow: auto;
  min-height: 0;
}

.nav-progress-bar {
  height: 2px;
  flex-shrink: 0;
  margin-bottom: -2px;
  position: relative;
  z-index: 100;
  background: linear-gradient(90deg, transparent, var(--accent-color, #4a9eff), transparent);
  background-size: 200% 100%;
  animation: nav-progress-slide 1.2s linear infinite;
}

@keyframes nav-progress-slide {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>

<svelte:head>
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="manifest" href="/site.webmanifest">
  <link rel="alternate" type="application/rss+xml" title="Entropia Nexus" href="/feed.xml">
</svelte:head>
{#if !isEmbed}<Toasts /><ConsentBanner /><SupportNotice />{/if}
<div class="app-layout">
  {#if !isEmbed}
    <Menu user={data?.session?.user} realUser={data?.session?.realUser} />
    {#if $navigating}
      <div class="nav-progress-bar"></div>
    {/if}
  {/if}
  <div class="app-content">
    {@render children?.()}
  </div>
</div>


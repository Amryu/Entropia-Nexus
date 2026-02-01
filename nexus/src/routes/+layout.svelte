<script>
  //@ts-nocheck

  import '$lib/style.css';

  import { darkMode, pageParams, initialViewportWidth } from '../stores.js';

  import Menu from "$lib/components/Menu.svelte";
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { decodeURIComponentSafe } from '$lib/util.js';

  export let data;
  // SvelteKit passes params to all layouts/pages - we use $page.params instead
  // but need to declare this to avoid console warnings
  export let params = {};

  let darkModeValue = true;
  $page;

  // Set initial viewport width from server-side detection
  $: if (data.initialViewportWidth) {
    initialViewportWidth.set(data.initialViewportWidth);
  }

  // Whenever the page store updates, decode the parameters
  $: {
    pageParams.set(
      Object.fromEntries(
        Object.entries($page.params).map(([key, value]) => [
          key,
          decodeURIComponentSafe(value)
        ])
      )
    );
  }
  
  const unsubscribe = darkMode.subscribe(value => {
    darkModeValue = value;
    updateDarkMode();
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

  onMount(() => {
    updateDarkMode();

    if (typeof window !== 'undefined') {
      darkMode.set(localStorage.getItem('darkMode') === 'true');

      // Store initial viewport width
      storeViewportWidth(window.innerWidth);

      // Listen for resize to update the cookie
      window.addEventListener('resize', handleResize);
    }
  });

  function updateDarkMode() {
    if (typeof window === 'undefined') return;

    if (darkModeValue === true) {
      document.body.classList.remove('light-mode');
    } else {
      document.body.classList.add('light-mode');
    }
  }

  // Remember to unsubscribe when the component is destroyed
  onDestroy(() => {
    unsubscribe();
    if (viewportDebounceTimer) {
      clearTimeout(viewportDebounceTimer);
    }
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', handleResize);
    }
  });
</script>
<style global>
:global(html), :global(body) {
  height: 100%;
  margin: 0;
  padding: 0;
  font-family: 'Gill Sans', 'Gill Sans MT', Calibri, 'Trebuchet MS', sans-serif;
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
  overflow: hidden;
}

.app-content {
  flex: 1;
  overflow: auto;
  min-height: 0;
}
</style>

<svelte:head>
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="manifest" href="/site.webmanifest">
</svelte:head>
<div class="app-layout">
  <Menu user={data?.session?.user} realUser={data?.session?.realUser} />
  <div class="app-content">
    <slot></slot>
  </div>
</div>
<script>
  //@ts-nocheck
  import '$lib/style.css';

  import { darkMode, pageParams, initialViewportWidth } from '../stores.js';

  import Menu from "$lib/components/Menu.svelte";
  import Toasts from "$lib/components/Toasts.svelte";
  import { onMount, onDestroy } from 'svelte';
  import { page, navigating } from '$app/stores';
  import { decodeURIComponentSafe } from '$lib/util.js';

  export let data;
  // SvelteKit passes params to all layouts/pages - we use $page.params instead
  // Declared as const to accept prop without Svelte "unused" warning
  export const params = {};

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

  function saveDarkModeToServer(isDark) {
    fetch('/api/users/preferences', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: 'darkMode', data: isDark })
    }).catch(() => {}); // fire and forget
  }

  onMount(() => {
    updateDarkMode();

    if (typeof window !== 'undefined') {
      // Theme migration: force all users to re-evaluate based on OS preference,
      // defaulting to dark mode. After this one-time migration, respect their choice.
      const THEME_VERSION = 2;
      const storedVersion = localStorage.getItem('themeVersion');
      let migrated = false;

      if (storedVersion === String(THEME_VERSION)) {
        // Already migrated — use their stored preference
        darkMode.set(localStorage.getItem('darkMode') === 'true');
      } else {
        // New user or pre-migration user: check OS/browser preference
        const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
        const useDark = !prefersLight;
        darkMode.set(useDark);
        localStorage.setItem('darkMode', useDark ? 'true' : 'false');
        localStorage.setItem('themeVersion', String(THEME_VERSION));
        migrated = true;
      }

      // Sync dark mode with server for logged-in users
      const user = data?.session?.user;
      if (user) {
        if (migrated) {
          // Just migrated — push new value to server
          saveDarkModeToServer(darkModeValue);
        } else {
          // Load from server for cross-device sync
          fetch('/api/users/preferences/darkMode')
            .then(res => res.ok ? res.json() : null)
            .then(pref => {
              if (pref?.data !== null && pref?.data !== undefined) {
                const serverDark = pref.data === true;
                if (serverDark !== darkModeValue) {
                  darkMode.set(serverDark);
                  localStorage.setItem('darkMode', serverDark ? 'true' : 'false');
                }
              } else {
                // Server has no value yet — seed it from localStorage
                saveDarkModeToServer(darkModeValue);
              }
            })
            .catch(() => {}); // localStorage is fine as fallback
        }
      }

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
</svelte:head>
<Toasts />
<div class="app-layout">
  <Menu user={data?.session?.user} realUser={data?.session?.realUser} />
  {#if $navigating}
    <div class="nav-progress-bar"></div>
  {/if}
  <div class="app-content">
    <slot></slot>
  </div>
</div>

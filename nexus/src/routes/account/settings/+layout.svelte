<script>
  // @ts-nocheck
  import { page } from '$app/stores';
  /**
   * @typedef {Object} Props
   * @property {import('svelte').Snippet} [children]
   */

  /** @type {Props} */
  let { children } = $props();

  const navItems = [
    {
      heading: 'Promos',
      items: [
        { label: 'Overview', href: '/account/settings/promos' },
        { label: 'My Promos', href: '/account/settings/promos/library' },
        { label: 'My Bookings', href: '/account/settings/promos/bookings' }
      ]
    },
    {
      heading: 'Developer',
      items: [
        { label: 'Applications', href: '/account/settings/developer' },
        { label: 'Authorized Apps', href: '/account/settings/authorizations' },
        { label: 'API Reference', href: '/account/settings/api-docs' }
      ]
    }
  ];

  let mobileSidebarOpen = $state(false);

  function closeSidebar() {
    mobileSidebarOpen = false;
  }
</script>

<svelte:head>
  <title>Settings | Entropia Nexus</title>
</svelte:head>

<div class="settings-layout">
  <aside class="settings-sidebar" class:mobile-open={mobileSidebarOpen}>
    <h2 class="settings-title">Settings</h2>
    <nav>
      {#each navItems as section}
        <div class="nav-section">
          <h3 class="nav-heading">{section.heading}</h3>
          {#each section.items as item}
            <a
              href={item.href}
              class="nav-item"
              class:active={$page.url.pathname === item.href}
              onclick={closeSidebar}
            >
              {item.label}
            </a>
          {/each}
        </div>
      {/each}
    </nav>
  </aside>

  {#if mobileSidebarOpen}
    <div class="sidebar-overlay" role="presentation" onclick={closeSidebar}></div>
  {/if}

  <button class="sidebar-toggle" onclick={() => mobileSidebarOpen = !mobileSidebarOpen}>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
    Settings
  </button>

  <div class="settings-content">
    {@render children?.()}
  </div>
</div>

<style>
  .settings-layout {
    display: flex;
    height: 100%;
    position: relative;
    min-height: 0;
  }

  .settings-sidebar {
    width: 200px;
    flex-shrink: 0;
    overflow-y: auto;
    padding: 1.5rem 1rem;
    border-right: 1px solid var(--border-color);
  }

  .settings-title {
    font-size: 1.1rem;
    color: var(--text-primary);
    margin: 0 0 1.25rem;
    padding: 0 0.5rem;
  }

  .nav-section {
    margin-bottom: 1.25rem;
  }

  .nav-heading {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    margin: 0 0 0.5rem;
    padding: 0 0.5rem;
    font-weight: 600;
  }

  .nav-item {
    display: block;
    padding: 0.4rem 0.5rem;
    border-radius: 6px;
    color: var(--text-primary);
    text-decoration: none;
    font-size: 0.85rem;
    transition: background 0.15s;
  }

  .nav-item:hover {
    background: var(--hover-bg);
  }

  .nav-item.active {
    background: var(--accent-color);
    color: white;
  }

  .sidebar-toggle {
    display: none;
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 60;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    border: none;
    background: var(--accent-color);
    color: #fff;
    font-size: 0.85rem;
    cursor: pointer;
    align-items: center;
    gap: 0.375rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }

  .sidebar-overlay {
    display: none;
  }

  .settings-content {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
  }

  @media (max-width: 768px) {
    .settings-sidebar {
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      bottom: 0;
      z-index: 101;
      background: var(--primary-color);
      box-shadow: 2px 0 12px rgba(0, 0, 0, 0.3);
      border-right: 1px solid var(--border-color);
    }

    .settings-sidebar.mobile-open {
      display: block;
    }

    .sidebar-toggle {
      display: flex;
    }

    .sidebar-overlay {
      display: block;
      position: fixed;
      inset: 0;
      z-index: 100;
      background: rgba(0, 0, 0, 0.4);
    }

    .settings-content {
      padding-top: 0;
    }
  }
</style>

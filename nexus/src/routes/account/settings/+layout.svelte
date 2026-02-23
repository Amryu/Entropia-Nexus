<script>
  // @ts-nocheck
  import { page } from '$app/stores';

  const navItems = [
    {
      heading: 'Developer',
      items: [
        { label: 'Applications', href: '/account/settings/developer' },
        { label: 'Authorized Apps', href: '/account/settings/authorizations' }
      ]
    }
  ];

  let mobileSidebarOpen = false;

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
              on:click={closeSidebar}
            >
              {item.label}
            </a>
          {/each}
        </div>
      {/each}
    </nav>
  </aside>

  {#if mobileSidebarOpen}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="sidebar-overlay" on:click={closeSidebar}></div>
  {/if}

  <button class="sidebar-toggle" on:click={() => mobileSidebarOpen = !mobileSidebarOpen}>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
    Settings
  </button>

  <div class="settings-content">
    <slot />
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
    position: absolute;
    top: 0.75rem;
    left: 0.75rem;
    z-index: 10;
    padding: 0.4rem 0.75rem;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background: var(--card-bg);
    color: var(--text-primary);
    font-size: 0.85rem;
    cursor: pointer;
    align-items: center;
    gap: 0.375rem;
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
      background: var(--card-bg);
      box-shadow: 2px 0 12px rgba(0, 0, 0, 0.3);
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
      padding-top: 3rem;
    }
  }
</style>

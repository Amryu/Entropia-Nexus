<script>
  // @ts-nocheck
  import { page } from '$app/stores';

  export let data;

  let sidebarOpen = false;

  const navItems = [
    { path: '/admin', label: 'Dashboard', icon: '📊' },
    { path: '/admin/changes', label: 'Changes', icon: '📝' },
    { path: '/admin/images', label: 'Images', icon: '🖼️' },
    { path: '/admin/users', label: 'Users', icon: '👥' }
  ];

  // Use reactive statement to compute active states based on current path
  $: currentPath = $page.url.pathname;
  $: activeStates = navItems.reduce((acc, item) => {
    if (item.path === '/admin') {
      acc[item.path] = currentPath === '/admin';
    } else {
      acc[item.path] = currentPath.startsWith(item.path);
    }
    return acc;
  }, {});

  function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
  }

  function closeSidebar() {
    sidebarOpen = false;
  }
</script>

<style>
  .admin-layout {
    display: flex;
    height: 100%;
    overflow: hidden;
    position: relative;
  }

  .admin-sidebar {
    width: 220px;
    background-color: var(--secondary-color);
    border-right: 1px solid var(--border-color);
    padding: 16px 0;
    flex-shrink: 0;
    overflow-y: auto;
    z-index: 50;
  }

  .sidebar-header {
    padding: 0 16px 16px;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 16px;
  }

  .sidebar-header h2 {
    margin: 0;
    font-size: 18px;
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    color: var(--text-color);
    text-decoration: none;
    transition: background-color 0.15s ease;
    font-size: 14px;
  }

  .nav-item:hover {
    background-color: var(--hover-color);
  }

  .nav-item.active {
    background-color: rgba(59, 130, 246, 0.15);
    border-right: 3px solid var(--accent-color);
    color: var(--accent-color);
  }

  .nav-icon {
    font-size: 16px;
    width: 24px;
    text-align: center;
  }

  .admin-content {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    background-color: var(--primary-color);
  }

  /* Mobile toggle button */
  .sidebar-toggle {
    display: none;
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 60;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background-color: var(--accent-color);
    color: white;
    border: none;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    font-size: 20px;
    align-items: center;
    justify-content: center;
    transition: background-color 0.15s ease, transform 0.15s ease;
  }

  .sidebar-toggle:hover {
    background-color: var(--accent-color-hover);
    transform: scale(1.05);
  }

  /* Mobile overlay */
  .sidebar-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 40;
  }

  .sidebar-overlay.open {
    display: block;
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    .admin-sidebar {
      position: fixed;
      top: 0;
      left: 0;
      bottom: 0;
      transform: translateX(-100%);
      transition: transform 0.3s ease;
    }

    .admin-sidebar.open {
      transform: translateX(0);
    }

    .sidebar-toggle {
      display: flex;
    }

    .admin-content {
      padding: 16px;
    }
  }
</style>

<div class="admin-layout">
  <!-- Mobile overlay -->
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="sidebar-overlay" class:open={sidebarOpen} on:click={closeSidebar}></div>

  <nav class="admin-sidebar" class:open={sidebarOpen}>
    <div class="sidebar-header">
      <h2>
        <span>⚙️</span>
        Admin Panel
      </h2>
    </div>

    {#each navItems as item}
      <a href={item.path} class="nav-item" class:active={activeStates[item.path]} on:click={closeSidebar}>
        <span class="nav-icon">{item.icon}</span>
        {item.label}
      </a>
    {/each}
  </nav>

  <main class="admin-content">
    <slot />
  </main>

  <!-- Mobile toggle button -->
  <button class="sidebar-toggle" on:click={toggleSidebar} aria-label="Toggle sidebar">
    {#if sidebarOpen}
      ✕
    {:else}
      ☰
    {/if}
  </button>
</div>

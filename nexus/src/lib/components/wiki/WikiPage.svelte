<!--
  @component WikiPage
  Main responsive container for wiki entity pages.
  Provides mobile-first layout with navigation drawer and content area.
  Header is inline within content (no fixed bar) to avoid scroll issues.
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { editMode, resetEditState, startEdit } from '$lib/stores/wikiEditState.js';
  import { encodeURIComponentSafe } from '$lib/util';
  import WikiNavigation from './WikiNavigation.svelte';
  import MobileDrawer from './MobileDrawer.svelte';
  import EditActionBar from './EditActionBar.svelte';

  /** @type {string} Page title shown in header */
  export let title = '';

  /** @type {Array} Breadcrumb items [{label, href}, ...] */
  export let breadcrumbs = [];

  /** @type {object|null} Current entity being viewed/edited */
  export let entity = null;

  /** @type {string} Entity type for API calls */
  export let entityType = '';

  /** @type {string} Base path for navigation links */
  export let basePath = '';

  /** @type {Array} Items for navigation list */
  export let navItems = [];

  /** @type {object|null} Current user */
  export let user = null;

  /** @type {boolean} Whether editing is allowed */
  export let editable = false;

  /** @type {Array} Filter options for navigation */
  export let navFilters = [];

  /** @type {Function|null} Custom save handler */
  export let onSave = null;

  /** @type {Function|null} Custom submit handler */
  export let onSubmit = null;

  /** @type {Array|null} Custom table columns for navigation sidebar */
  export let navTableColumns = null;

  /** @type {Object|null} Custom column formatters for navigation sidebar */
  export let navColumnFormatters = null;

  /** @type {Function|null} Custom function to generate item href in navigation */
  export let navGetItemHref = null;

  // Mobile drawer state
  let drawerOpen = false;

  // Sidebar expanded state (for table view)
  let sidebarExpanded = false;

  // Screen size tracking
  let windowWidth = 0;
  let isMobile = false;
  let isTablet = false;

  $: isMobile = windowWidth < 768;
  $: isTablet = windowWidth >= 768 && windowWidth < 1024;

  function toggleDrawer() {
    drawerOpen = !drawerOpen;
  }

  function closeDrawer() {
    drawerOpen = false;
  }

  function toggleSidebarExpand() {
    sidebarExpanded = !sidebarExpanded;
  }

  function handleCreate() {
    if (basePath) {
      goto(`${basePath}?mode=create`);
    }
  }

  function handleEdit() {
    if (entity) {
      startEdit(entity);
    }
  }

  function handleHistory() {
    if (entity && basePath) {
      goto(`${basePath}/${encodeURIComponentSafe(entity.Name)}?mode=history`);
    }
  }

  // Clean up edit state when component is destroyed
  onDestroy(() => {
    resetEditState();
  });

  onMount(() => {
    windowWidth = window.innerWidth;
  });
</script>

<svelte:window bind:innerWidth={windowWidth} />

<div class="wiki-page" class:mobile={isMobile} class:tablet={isTablet} class:sidebar-expanded={sidebarExpanded}>
  <!-- Mobile Navigation Drawer -->
  {#if isMobile}
    <MobileDrawer bind:open={drawerOpen} on:close={closeDrawer}>
      <WikiNavigation
        items={navItems}
        filters={navFilters}
        {basePath}
        {title}
        currentSlug={entity?.Name}
        customGetItemHref={navGetItemHref}
        on:select={closeDrawer}
      />
    </MobileDrawer>
  {/if}

  <div class="wiki-layout">
    <!-- Desktop/Tablet Sidebar -->
    {#if !isMobile}
      <aside class="wiki-sidebar">
        <WikiNavigation
          items={navItems}
          filters={navFilters}
          {basePath}
          {title}
          currentSlug={entity?.Name}
          expanded={sidebarExpanded}
          on:toggleExpand={toggleSidebarExpand}
          tableColumns={navTableColumns}
          columnFormatters={navColumnFormatters}
          customGetItemHref={navGetItemHref}
        />
      </aside>
    {/if}

    <!-- Main Content Area -->
    <main class="wiki-content">
      <!-- Inline Content Header -->
      <div class="content-header">
        <div class="header-left">
          {#if isMobile}
            <button class="nav-toggle-btn" on:click={toggleDrawer} aria-label="Browse items">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="7" height="7" rx="1" />
                <rect x="14" y="3" width="7" height="7" rx="1" />
                <rect x="3" y="14" width="7" height="7" rx="1" />
                <rect x="14" y="14" width="7" height="7" rx="1" />
              </svg>
            </button>
          {/if}

          {#if breadcrumbs.length > 0}
            <nav class="breadcrumbs" aria-label="Breadcrumb">
              {#each breadcrumbs as crumb, i}
                {#if i > 0}
                  <span class="breadcrumb-sep">/</span>
                {/if}
                {#if crumb.href}
                  <a href={crumb.href} class="breadcrumb-link">{crumb.label}</a>
                {:else}
                  <span class="breadcrumb-current">{crumb.label}</span>
                {/if}
              {/each}
            </nav>
          {/if}
        </div>

        <div class="header-actions">
          {#if editable && user}
            <button class="action-btn create" on:click={handleCreate} title="Create new">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>New</span>
            </button>
          {/if}
          {#if entity && editable && user}
            {#if !$editMode}
              <button class="action-btn" on:click={handleEdit} title="Edit">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
                <span>Edit</span>
              </button>
            {/if}
            <button class="action-btn secondary" on:click={handleHistory} title="History">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <span>History</span>
            </button>
          {/if}
        </div>
      </div>

      <!-- Main Content Slot -->
      <div class="content-body">
        <slot {entity} {user} />
      </div>
    </main>
  </div>

  <!-- Edit Action Bar (shown when in edit mode) -->
  {#if $editMode}
    <EditActionBar {onSave} {onSubmit} />
  {/if}
</div>

<style>
  .wiki-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    background-color: var(--primary-color);
    color: var(--text-color);
  }

  .wiki-layout {
    display: flex;
    flex: 1;
    min-height: 0; /* Important for proper flex scrolling */
  }

  .wiki-sidebar {
    display: flex;
    flex-direction: column;
    width: 280px;
    min-width: 280px;
    max-width: 280px;
    background-color: var(--secondary-color);
    border-right: 1px solid var(--border-color, #ccc);
    transition: width 0.3s ease, min-width 0.3s ease, max-width 0.3s ease;
  }

  .wiki-page.sidebar-expanded .wiki-sidebar {
    width: 50%;
    min-width: 280px;
    max-width: 700px;
  }

  .wiki-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0; /* Prevent flex overflow */
    overflow: hidden;
  }

  .content-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 20px;
    border-bottom: 1px solid var(--border-color, #555);
    background-color: var(--secondary-color);
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }

  .nav-toggle-btn {
    padding: 6px;
    background: var(--hover-color);
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
    cursor: pointer;
    border-radius: 6px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .nav-toggle-btn:hover {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .breadcrumbs {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    overflow: hidden;
    white-space: nowrap;
  }

  .breadcrumb-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .breadcrumb-link:hover {
    text-decoration: underline;
  }

  .breadcrumb-sep {
    color: var(--text-muted, #999);
  }

  .breadcrumb-current {
    color: var(--text-color);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .header-actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }

  .action-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 500;
    background-color: var(--accent-color, #4a9eff);
    border: none;
    border-radius: 6px;
    color: white;
    cursor: pointer;
    transition: all 0.15s;
  }

  .action-btn:hover {
    filter: brightness(1.1);
  }

  .action-btn.create {
    background-color: var(--success-color, #4ade80);
  }

  .action-btn.secondary {
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
  }

  .action-btn.secondary:hover {
    background-color: var(--hover-color);
    filter: none;
  }

  .content-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
  }

  /* Tablet adjustments */
  .wiki-page.tablet .wiki-sidebar {
    width: 240px;
    min-width: 240px;
    max-width: 240px;
  }

  .wiki-page.tablet .content-body {
    padding: 16px;
  }

  .wiki-page.tablet.sidebar-expanded .wiki-sidebar {
    width: 45%;
    min-width: 240px;
    max-width: 600px;
  }

  /* Mobile adjustments */
  .wiki-page.mobile .wiki-layout {
    flex-direction: column;
  }

  .wiki-page.mobile .content-header {
    padding: 10px 12px;
  }

  .wiki-page.mobile .breadcrumbs {
    font-size: 13px;
  }

  .wiki-page.mobile .action-btn span {
    display: none; /* Hide text, show only icons on mobile */
  }

  .wiki-page.mobile .action-btn {
    padding: 8px;
  }

  .wiki-page.mobile .content-body {
    padding: 12px;
  }
</style>

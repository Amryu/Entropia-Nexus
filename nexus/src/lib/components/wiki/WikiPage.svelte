<!--
  @component WikiPage
  Main responsive container for wiki entity pages.
  Provides mobile-first layout with navigation drawer and content area.
  Header is inline within content (no fixed bar) to avoid scroll issues.
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy, tick } from 'svelte';
  import { page, navigating } from '$app/stores';
  import { goto, afterNavigate, beforeNavigate } from '$app/navigation';
  import { editMode, isCreateMode, hasChanges, resetEditState, startEdit, cancelEdit } from '$lib/stores/wikiEditState.js';
  import { initialViewportWidth } from '../../../stores.js';
  import WikiNavigation from './WikiNavigation.svelte';
  import MobileDrawer from './MobileDrawer.svelte';
  import EditActionBar from './EditActionBar.svelte';

  /** @type {string} Page title shown in header */
  export let title = '';

  /** @type {Array} Breadcrumb items [{label, href}, ...] */
  export let breadcrumbs = [];

  /** @type {object|null} Current entity being viewed/edited */
  export let entity = null;

  /** @type {string} Base path for navigation links */
  export let basePath = '';

  /** @type {Array} Items for navigation list */
  export let navItems = [];

  /** @type {object|null} Current user */
  export let user = null;

  /** @type {boolean} Whether the page supports editing (shows login/verify button if not authenticated) */
  export let editable = false;

  /** @type {boolean} Whether the current user can edit (has permission) */
  export let canEdit = false;

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

  /** @type {Array|null} Additional table columns for full-width mode (superset of navTableColumns) */
  export let navFullWidthColumns = null;

  /** @type {Array|null} All possible columns for column configuration */
  export let navAllAvailableColumns = null;

  /** @type {string} Unique ID for localStorage column preferences key */
  export let navPageTypeId = '';

  /** @type {Function|null} Custom function to generate item href in navigation */
  export let navGetItemHref = null;

  /** @type {boolean} Whether the user can create new entities (may be limited) */
  export let canCreateNew = true;

  /** @type {Array<{label: string, href: string}>|null} Category options for create dropdown (multi-type pages) */
  export let createCategories = null;

  /** @type {Array} User's pending create changes to show at top of sidebar */
  export let userPendingCreates = [];

  /** @type {Array} User's pending update changes to highlight in sidebar */
  export let userPendingUpdates = [];

  /** @type {string} Optional CSS class added to the root .wiki-page element for scoping */
  export let pageClass = '';

  // Mobile drawer state - can be bound from parent
  export let drawerOpen = false;

  // Sidebar expanded state (for table view) - exported for pages with custom sidebars
  export let sidebarExpanded = false;

  // Sidebar full-width state (takes entire page, hides content) - exported for pages with custom sidebars
  export let sidebarFullWidth = false;

  // Auth help dialog state
  let showAuthDialog = false;

  // Screen size tracking - initialize from server-detected viewport to avoid layout flash
  // The store is set by the layout based on User-Agent detection or stored cookie
  // This will be updated immediately on mount with actual window width
  // IMPORTANT: Breakpoints aligned with global 900px mobile breakpoint (see style.css)
  let windowWidth = $initialViewportWidth;
  let windowHeight = 0;
  let isMobile = false;
  let isTablet = false;
  let mounted = false;
  let hasCustomSidebar = false;

  // Portrait orientation check (height > width)
  $: isPortrait = windowHeight > windowWidth;

  // Mobile: < 900px (sidebar hidden, mobile drawer)
  // Tablet: 900px - 1399px (sidebar visible, infobox stacks)
  // Desktop: >= 1400px (full layout with floating infobox)
  $: isMobile = windowWidth < 900;
  $: isTablet = !isMobile && windowWidth < 1400;
  $: hasCustomSidebar = !!$$slots.sidebar;

  function toggleDrawer() {
    drawerOpen = !drawerOpen;
  }

  function closeDrawer() {
    drawerOpen = false;
  }

  function openDrawer() {
    drawerOpen = true;
  }

  function handleDrawerItemSelect() {
    // This is no longer needed - drawer closes via afterNavigate
  }

  // Handle drawer state and edit mode after navigation completes
  // Using requestAnimationFrame ensures we run after the browser's paint cycle,
  // when all component props have been fully propagated
  afterNavigate((navigation) => {
    const isMobileAfterNav = window.innerWidth < 900;
    const navMode = navigation?.to?.url?.searchParams?.get('mode');
    const changeIdFromNav = navigation?.to?.url?.searchParams?.get('changeId');
    const isCreateView = navMode === 'create';

    // Handle drawer state immediately (doesn't depend on data props)
    if (isMobileAfterNav && !entity && !isCreateView) {
      drawerOpen = true;
    } else if (drawerOpen) {
      drawerOpen = false;
    }

    // Handle edit mode after props are fully settled
    // Use requestAnimationFrame + tick to ensure parent component has updated WikiPage's props
    requestAnimationFrame(async () => {
      await tick();
      const changeId = changeIdFromNav ?? currentChangeId;
      const inCreateMode = isCreateView || $isCreateMode;

      if (inCreateMode) {
        if (!$editMode) {
          startEdit(entity);
        }
        return;
      }

      const hasPendingChange = checkHasUserPendingChange(entity, changeId, userPendingUpdates, userPendingCreates);

      if (!entity) {
        if ($editMode) {
          cancelEdit();
        }
        return;
      }

      if (hasPendingChange && !$editMode) {
        startEdit(entity);
      } else if (!hasPendingChange && $editMode) {
        cancelEdit();
      }
    });
  });

  function toggleSidebarExpand() {
    sidebarExpanded = !sidebarExpanded;
  }

  function toggleSidebarFullWidth() {
    sidebarFullWidth = !sidebarFullWidth;
  }

  function handleCreate() {
    if (basePath) {
      if ($editMode && $hasChanges) {
        if (!confirm('You have unsaved changes. Start a new creation?')) return;
      }
      skipNavGuard = true;
      goto(`${basePath}?mode=create`);
    }
  }

  // Create category dropdown state (for multi-type pages)
  let createDropdownOpen = false;

  function toggleCreateDropdown() {
    createDropdownOpen = !createDropdownOpen;
  }

  function closeCreateDropdown() {
    createDropdownOpen = false;
  }

  function handleCreateCategory(category) {
    if ($editMode && $hasChanges) {
      if (!confirm('You have unsaved changes. Start a new creation?')) return;
    }
    skipNavGuard = true;
    createDropdownOpen = false;
    goto(`${category.href}?mode=create`);
  }

  function handleEdit() {
    if (entity) {
      startEdit(entity);
    }
  }

  function handleCancelEdit() {
    cancelEdit();
  }


  function openAuthDialog() {
    showAuthDialog = true;
  }

  function closeAuthDialog() {
    showAuthDialog = false;
  }

  // Determine if user needs to authenticate or verify
  $: needsAuth = editable && !user;
  $: needsVerification = editable && user && !user.verified;

  // Login URL with redirect back to current page
  $: loginUrl = `/discord/login?redirect=${encodeURIComponent($page.url.pathname + $page.url.search)}`;

  // Get current changeId from URL (for highlighting pending creates in sidebar)
  $: currentChangeId = $page.url.searchParams.get('changeId');

  // Helper function to check if current entity has a pending change by the user
  function checkHasUserPendingChange(currentEntity, changeId, pendingUpdates, pendingCreates) {
    // Check for pending create first (via changeId in URL) - doesn't require an entity
    if (changeId && pendingCreates && pendingCreates.some(change =>
      String(change.id) === String(changeId)
    )) {
      return true;
    }

    // Check for pending update - requires a valid entity with an ID
    const entityId = currentEntity?.Id ?? currentEntity?.ItemId;
    if (entityId && pendingUpdates) {
      return pendingUpdates.some(change =>
        (change.data?.Id ?? change.data?.ItemId) && String(change.data?.Id ?? change.data?.ItemId) === String(entityId)
      );
    }

    return false;
  }

  // Navigation guard: warn about unsaved changes
  let skipNavGuard = false;
  beforeNavigate(({ cancel }) => {
    if (skipNavGuard) { skipNavGuard = false; return; }
    if (!$editMode || !$hasChanges) return;
    if (!confirm('You have unsaved changes. Are you sure you want to leave?')) {
      cancel();
    }
  });

  // Browser close/reload guard
  function handleBeforeUnload(e) {
    if ($editMode && $hasChanges) {
      e.preventDefault();
      e.returnValue = '';
    }
  }

  // Clean up edit state when component is destroyed
  onDestroy(() => {
    resetEditState();
    if (typeof window !== 'undefined') {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    }
  });

  onMount(() => {
    window.addEventListener('beforeunload', handleBeforeUnload);
    windowWidth = window.innerWidth;
    mounted = true;

    // Auto-open drawer on mobile when no entity is selected
    const isMobileOnMount = window.innerWidth < 900;
    if (isMobileOnMount && !entity && !$isCreateMode) {
      drawerOpen = true;
    }

    // Handle initial edit mode (afterNavigate doesn't run on initial load)
    if ($isCreateMode) {
      if (!$editMode) {
        startEdit(entity);
      }
      return;
    }

    const hasPendingChange = checkHasUserPendingChange(entity, currentChangeId, userPendingUpdates, userPendingCreates);
    if (!entity) {
      if ($editMode) {
        cancelEdit();
      }
      return;
    }

    if (hasPendingChange && !$editMode) {
      startEdit(entity);
    }
  });
</script>

<svelte:window bind:innerWidth={windowWidth} bind:innerHeight={windowHeight} />

<div class="wiki-page {pageClass}" class:mobile={isMobile} class:tablet={isTablet} class:sidebar-expanded={sidebarExpanded} class:sidebar-full-width={sidebarFullWidth}>
  <!-- Mobile Navigation Drawer -->
  {#if isMobile}
    <MobileDrawer bind:open={drawerOpen} on:close={closeDrawer}>
      {#if hasCustomSidebar}
        <slot name="sidebar" {isMobile} />
      {:else}
        <WikiNavigation
          items={navItems}
          filters={navFilters}
          {basePath}
          {title}
          currentSlug={entity?.Name}
          currentChangeId={currentChangeId}
          customGetItemHref={navGetItemHref}
          {userPendingCreates}
          {userPendingUpdates}
        />
      {/if}
    </MobileDrawer>
  {/if}

  <div class="wiki-layout">
    <!-- Desktop/Tablet Sidebar -->
    {#if !isMobile}
      <aside class="wiki-sidebar">
        {#if hasCustomSidebar}
          <slot name="sidebar" {isMobile} />
        {:else}
          <WikiNavigation
            items={navItems}
            filters={navFilters}
            {basePath}
            {title}
            currentSlug={entity?.Name}
            currentChangeId={currentChangeId}
            expanded={sidebarExpanded}
            fullWidth={sidebarFullWidth}
            on:toggleExpand={toggleSidebarExpand}
            on:toggleFullWidth={toggleSidebarFullWidth}
            tableColumns={navTableColumns}
            fullWidthColumns={navFullWidthColumns}
            allAvailableColumns={navAllAvailableColumns}
            pageTypeId={navPageTypeId}
            columnFormatters={navColumnFormatters}
            customGetItemHref={navGetItemHref}
            {userPendingCreates}
            {userPendingUpdates}
          />
        {/if}
      </aside>
    {/if}

    <!-- Main Content Area -->
    <main class="wiki-content" class:navigating={!!$navigating}>
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
          <slot name="header-actions">
            {#if canEdit}
              <div class="create-btn-wrapper">
                <button
                  class="action-btn create"
                  on:click={createCategories ? toggleCreateDropdown : handleCreate}
                  title={canCreateNew ? 'Create new' : 'You have reached the limit of 50 pending creations'}
                  disabled={!canCreateNew}
                  aria-haspopup={createCategories ? 'true' : undefined}
                  aria-expanded={createCategories ? createDropdownOpen : undefined}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                  <span>New</span>
                  {#if createCategories}
                    <svg class="dropdown-chevron" class:open={createDropdownOpen} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  {/if}
                </button>
                {#if createDropdownOpen}
                  <!-- svelte-ignore a11y-no-static-element-interactions -->
                  <div class="create-dropdown-backdrop" on:click={closeCreateDropdown}></div>
                  <div class="create-dropdown" role="menu" on:keydown={(e) => e.key === 'Escape' && closeCreateDropdown()}>
                    {#each createCategories as category}
                      <button
                        class="create-dropdown-item"
                        role="menuitem"
                        on:click={() => handleCreateCategory(category)}
                      >
                        {category.label}
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}
            {#if entity && canEdit && !$isCreateMode}
              {#if $editMode}
                <button class="action-btn cancel" on:click={handleCancelEdit} title="Cancel editing">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                  <span>Cancel</span>
                </button>
              {:else}
                <button class="action-btn" on:click={handleEdit} title="Edit">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                  <span>Edit</span>
                </button>
              {/if}
            {:else if editable && (needsAuth || needsVerification) && !$isCreateMode}
              <button class="auth-hint-btn" on:click={openAuthDialog} title="Login required">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <span>{needsAuth ? 'Login to edit' : 'Verify to edit'}</span>
              </button>
            {/if}
          </slot>
        </div>
      </div>

      <!-- Main Content Slot -->
      <div class="content-body" class:editing={$editMode}>
        <slot {entity} {user} {isMobile} {openDrawer} />
      </div>
    </main>
  </div>

  <!-- Edit Action Bar (shown when in edit mode) -->
  {#if $editMode}
    <EditActionBar {onSave} {onSubmit} {basePath} {user} entityName={entity?.Name || ''} />
  {/if}

  <!-- Auth Help Dialog -->
  {#if showAuthDialog}
    <div class="dialog-overlay" on:click={closeAuthDialog} on:keydown={(e) => e.key === 'Escape' && closeAuthDialog()}>
      <div class="dialog-content" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="auth-dialog-title">
        <button class="dialog-close" on:click={closeAuthDialog} aria-label="Close">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        <h2 id="auth-dialog-title" class="dialog-title">
          {needsAuth ? 'Login Required' : 'Verification Required'}
        </h2>

        {#if needsAuth}
          <div class="dialog-body">
            <p>To create, edit, or view history of wiki entries, you need to log in and verify your account.</p>

            <div class="auth-steps">
              <div class="auth-step">
                <span class="step-number">1</span>
                <div class="step-content">
                  <strong>Login with Discord</strong>
                  <p>Click the button below to log in using your Discord account.</p>
                </div>
              </div>

              <div class="auth-step">
                <span class="step-number">2</span>
                <div class="step-content">
                  <strong>Join our Discord Server</strong>
                  <p>After logging in, join the Entropia Nexus Discord server if you haven't already.</p>
                </div>
              </div>

              <div class="auth-step">
                <span class="step-number">3</span>
                <div class="step-content">
                  <strong>Complete Verification</strong>
                  <p>A verification thread will automatically open (may take up to 5 minutes). Follow the instructions to verify your Entropia Universe character.</p>
                </div>
              </div>
            </div>

            <div class="dialog-actions">
              <a href={loginUrl} class="dialog-btn primary">Login with Discord</a>
              <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener" class="dialog-btn secondary">Join Discord Server</a>
            </div>
          </div>
        {:else}
          <div class="dialog-body">
            <p>Your account needs to be verified before you can create, edit, or view history of wiki entries.</p>

            <div class="auth-steps">
              <div class="auth-step">
                <span class="step-number">1</span>
                <div class="step-content">
                  <strong>Join our Discord Server</strong>
                  <p>Make sure you've joined the Entropia Nexus Discord server.</p>
                </div>
              </div>

              <div class="auth-step">
                <span class="step-number">2</span>
                <div class="step-content">
                  <strong>Wait for Verification Thread</strong>
                  <p>A verification thread will automatically open in your Discord DMs or in a private channel. This may take up to 5 minutes after joining.</p>
                </div>
              </div>

              <div class="auth-step">
                <span class="step-number">3</span>
                <div class="step-content">
                  <strong>Follow Verification Instructions</strong>
                  <p>Respond to the verification thread with the requested information about your Entropia Universe character.</p>
                </div>
              </div>
            </div>

            <div class="dialog-actions">
              <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener" class="dialog-btn primary">Join Discord Server</a>
              <button class="dialog-btn secondary" on:click={closeAuthDialog}>Close</button>
            </div>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .wiki-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    background-color: var(--primary-color);
    color: var(--text-color);
    overflow-x: hidden;
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

  .wiki-page.sidebar-full-width .wiki-sidebar {
    width: 100%;
    min-width: 100%;
    max-width: 100%;
  }

  .wiki-page.sidebar-full-width:not(.mobile) .wiki-content {
    display: none;
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
    padding: 7px 20px;
    min-height: 45px;
    box-sizing: border-box;
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
    max-height: 32px;
    box-sizing: border-box;
  }

  .action-btn:hover {
    background-color: var(--button-accent-hover, #1e40af);
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  }

  .action-btn.create {
    background-color: var(--success-color, #4ade80);
  }

  .action-btn.create:hover {
    background-color: var(--button-success-hover, #047857);
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  }

  .action-btn.cancel {
    background-color: var(--error-color, #ef4444);
  }

  .action-btn.cancel:hover {
    background-color: var(--button-error-hover, #b91c1c);
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
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

  .action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .action-btn:disabled:hover {
    background-color: var(--accent-color, #4a9eff);
    transform: none;
    box-shadow: none;
  }

  .action-btn.create:disabled:hover {
    background-color: var(--success-color, #4ade80);
    transform: none;
    box-shadow: none;
  }

  .action-btn.cancel:disabled:hover {
    background-color: var(--error-color, #ef4444);
    transform: none;
    box-shadow: none;
  }

  /* Create button wrapper for dropdown positioning */
  .create-btn-wrapper {
    position: relative;
  }

  .dropdown-chevron {
    transition: transform 0.15s ease;
    margin-left: -2px;
  }

  .dropdown-chevron.open {
    transform: rotate(180deg);
  }

  .create-dropdown-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 99;
  }

  .create-dropdown {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    min-width: 180px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
    z-index: 100;
    padding: 4px 0;
  }

  .create-dropdown-item {
    display: block;
    width: 100%;
    padding: 10px 14px;
    font-size: 13px;
    color: var(--text-color);
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    transition: background-color 0.15s ease;
    white-space: nowrap;
  }

  .create-dropdown-item:hover {
    background-color: var(--hover-color);
  }

  .create-dropdown-item:focus-visible {
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: -2px;
  }

  .content-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    transition: opacity 0.15s ease;
  }

  /* Fade content while navigating to show loading state */
  .wiki-content.navigating .content-body {
    opacity: 0.4;
    pointer-events: none;
  }

  /* Add bottom padding when edit action bar is visible */
  .content-body.editing {
    padding-bottom: 100px;
  }

  /* Tablet adjustments */
  .wiki-page.tablet .content-body {
    padding: 16px;
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

  .wiki-page.mobile .dropdown-chevron {
    display: none;
  }

  .wiki-page.mobile .action-btn {
    padding: 8px;
  }

  .wiki-page.mobile .create-dropdown {
    min-width: 160px;
  }

  .wiki-page.mobile .content-body {
    padding: 12px;
  }

  .wiki-page.mobile .content-body.editing {
    padding-bottom: 120px; /* Taller on mobile due to stacked action bar layout */
  }

  /* Auth hint button */
  .auth-hint-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 6px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 13px;
    transition: all 0.15s;
    max-height: 32px;
    box-sizing: border-box;
  }

  .auth-hint-btn:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color);
  }

  .wiki-page.mobile .auth-hint-btn span {
    display: none;
  }

  .wiki-page.mobile .auth-hint-btn {
    padding: 8px;
  }

  /* Dialog styles */
  .dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
    box-sizing: border-box;
  }

  .dialog-content {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 12px;
    max-width: 500px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    position: relative;
    padding: 24px;
    box-sizing: border-box;
  }

  .dialog-close {
    position: absolute;
    top: 12px;
    right: 12px;
    background: transparent;
    border: none;
    color: var(--text-muted, #999);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: all 0.15s;
  }

  .dialog-close:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .dialog-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-color);
    margin: 0 0 16px 0;
    padding-right: 32px;
  }

  .dialog-body {
    color: var(--text-color);
  }

  .dialog-body > p {
    margin: 0 0 20px 0;
    color: var(--text-muted, #999);
    line-height: 1.5;
  }

  .auth-steps {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 24px;
  }

  .auth-step {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }

  .step-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 50%;
    font-size: 14px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .step-content {
    flex: 1;
    min-width: 0;
  }

  .step-content strong {
    display: block;
    color: var(--text-color);
    margin-bottom: 4px;
  }

  .step-content p {
    margin: 0;
    font-size: 13px;
    color: var(--text-muted, #999);
    line-height: 1.4;
  }

  .dialog-actions {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }

  .dialog-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 10px 20px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.15s;
    border: none;
  }

  .dialog-btn.primary {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .dialog-btn.primary:hover {
    filter: brightness(1.1);
  }

  .dialog-btn.secondary {
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
  }

  .dialog-btn.secondary:hover {
    background-color: var(--hover-color);
  }
</style>

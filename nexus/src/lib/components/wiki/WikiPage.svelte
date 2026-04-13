<!--
  @component WikiPage
  Main responsive container for wiki entity pages.
  Provides mobile-first layout with navigation drawer and content area.
  Header is inline within content (no fixed bar) to avoid scroll issues.
-->
<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import { page, navigating } from '$app/stores';
  import { goto, afterNavigate, beforeNavigate } from '$app/navigation';
  import { editMode, isCreateMode, hasChanges, resetEditState, startEdit, cancelEdit, consumeNavGuardSuppression } from '$lib/stores/wikiEditState.js';
  import { initialViewportWidth } from '../../../stores.js';
  import WikiNavigation from './WikiNavigation.svelte';
  import MobileDrawer from './MobileDrawer.svelte';
  import EditActionBar from './EditActionBar.svelte';
  import AdSlot from '$lib/components/AdSlot.svelte';

  /**
   * @typedef {Object} Props
   * @property {string} [title] Page title shown in header
   * @property {Array} [breadcrumbs] Breadcrumb items [{label, href}, ...]
   * @property {object|null} [entity] Current entity being viewed/edited
   * @property {string} [basePath] Base path for navigation links
   * @property {Array} [navItems] Items for navigation list
   * @property {object|null} [user] Current user
   * @property {boolean} [editable] Whether the page supports editing
   * @property {boolean} [canEdit] Whether the current user can edit
   * @property {Array} [navFilters] Filter options for navigation
   * @property {Function|null} [onSave] Custom save handler
   * @property {Function|null} [onSubmit] Custom submit handler
   * @property {Array|null} [navTableColumns] Custom table columns for navigation sidebar
   * @property {Object|null} [navColumnFormatters] Custom column formatters for navigation sidebar
   * @property {Array|null} [navFullWidthColumns] Additional table columns for full-width mode
   * @property {Array|null} [navAllAvailableColumns] All possible columns for column configuration
   * @property {string} [navPageTypeId] Unique ID for localStorage column preferences key
   * @property {Function|null} [navGetItemHref] Custom function to generate item href in navigation
   * @property {boolean} [canCreateNew] Whether the user can create new entities
   * @property {Array<{label: string, href: string}>|null} [createCategories] Category options for create dropdown
   * @property {Array} [userPendingCreates] User's pending create changes
   * @property {Array} [userPendingUpdates] User's pending update changes
   * @property {string} [pageClass] Optional CSS class added to the root element
   * @property {boolean} [editDepsLoading] Whether edit dependencies are currently being loaded
   * @property {boolean} [drawerOpen] Mobile drawer state (bindable)
   * @property {boolean} [sidebarExpanded] Sidebar expanded state (bindable)
   * @property {boolean} [sidebarFullWidth] Sidebar full-width state (bindable)
   * @property {import('svelte').Snippet<[{entity: object|null, user: object|null, isMobile: boolean, openDrawer: Function}]>} [children] Default content snippet
   * @property {import('svelte').Snippet<[{isMobile: boolean}]>} [sidebar] Sidebar snippet
   * @property {import('svelte').Snippet} [headerActions] Header actions snippet (replaces default edit/create buttons)
   * @property {import('svelte').Snippet} [afterHeader] After-header snippet
   */

  /** @type {Props} */
  let {
    title = '',
    breadcrumbs = [],
    entity = null,
    basePath = '',
    navItems = [],
    user = null,
    editable = false,
    canEdit = false,
    navFilters = [],
    onSave = null,
    onSubmit = null,
    navTableColumns = null,
    navColumnFormatters = null,
    navFullWidthColumns = null,
    navAllAvailableColumns = null,
    navPageTypeId = '',
    navGetItemHref = null,
    canCreateNew = true,
    createCategories = null,
    userPendingCreates = [],
    userPendingUpdates = [],
    pageClass = '',
    editDepsLoading = false,
    drawerOpen = $bindable(false),
    sidebarExpanded = $bindable(false),
    sidebarFullWidth = $bindable(false),
    children,
    sidebar,
    headerActions,
    afterHeader,
  } = $props();

  // Bridge URL query params to WikiNavigation initialFilters so menu
  // links like /items/weapons?group=ranged auto-apply the filter.
  let initialFiltersFromUrl = $derived((() => {
    const out = {};
    const sp = $page.url.searchParams;
    for (const f of navFilters || []) {
      if (!f?.key) continue;
      const v = sp.get(f.key);
      if (v !== null && v !== '') out[f.key] = v;
    }
    return out;
  })());

  // Auth help dialog state
  let showAuthDialog = $state(false);

  // Screen size tracking - initialize from server-detected viewport to avoid layout flash
  // The store is set by the layout based on User-Agent detection or stored cookie
  // This will be updated immediately on mount with actual window width
  // IMPORTANT: Breakpoints aligned with global 900px mobile breakpoint (see style.css)
  let windowWidth = $state($initialViewportWidth);
  let windowHeight = $state(0);
  let mounted = $state(false);

  // Create category dropdown state (for multi-type pages)
  let createDropdownOpen = $state(false);

  // Navigation guard: warn about unsaved changes
  let skipNavGuard = $state(false);

  // Portrait orientation check (height > width)
  let isPortrait = $derived(windowHeight > windowWidth);

  // Mobile: < 900px (sidebar hidden, mobile drawer)
  // Tablet: 900px - 1399px (sidebar visible, infobox stacks)
  // Desktop: >= 1400px (full layout with floating infobox)
  let isMobile = $derived(windowWidth < 900);
  let isTablet = $derived(!isMobile && windowWidth < 1400);
  let hasCustomSidebar = $derived(!!sidebar);

  // Determine if user needs to authenticate or verify
  let needsAuth = $derived(editable && !user);
  let needsVerification = $derived(editable && user && !user.verified);

  // Login URL with redirect back to current page
  let loginUrl = $derived(`/discord/login?redirect=${encodeURIComponent($page.url.pathname + $page.url.search)}`);

  // Get current changeId from URL (for highlighting pending creates in sidebar)
  let currentChangeId = $derived($page.url.searchParams.get('changeId'));

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
    const isEditView = navMode === 'edit';

    // Handle drawer state from the URL, not the entity prop (which may still be
    // null during streaming/loading, causing the drawer to flash back open).
    const toPath = navigation?.to?.url?.pathname || '';
    const hasSlug = basePath && toPath.length > basePath.length + 1;
    if (isMobileAfterNav && !hasSlug && !isCreateView) {
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
          startEdit();
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

      if ((hasPendingChange || isEditView) && !$editMode) {
        startEdit();
      } else if (!hasPendingChange && !isEditView && $editMode) {
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
      startEdit();
      const url = new URL(window.location.href);
      url.searchParams.set('mode', 'edit');
      history.replaceState(history.state, '', url);
    }
  }

  function handleCancelEdit() {
    cancelEdit();
    clearEditModeUrl();
  }

  function clearEditModeUrl() {
    const url = new URL(window.location.href);
    if (url.searchParams.has('mode')) {
      url.searchParams.delete('mode');
      url.searchParams.delete('changeId');
      history.replaceState(history.state, '', url);
    }
  }


  function openAuthDialog() {
    showAuthDialog = true;
  }

  function closeAuthDialog() {
    showAuthDialog = false;
  }

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

  beforeNavigate(({ cancel }) => {
    if (skipNavGuard) { skipNavGuard = false; return; }
    if (consumeNavGuardSuppression()) return;
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

    // Auto-open drawer on mobile when no entity is selected (check URL, not prop)
    const isMobileOnMount = window.innerWidth < 900;
    const mountPath = $page.url.pathname;
    const mountHasSlug = basePath && mountPath.length > basePath.length + 1;
    if (isMobileOnMount && !mountHasSlug && !$isCreateMode) {
      drawerOpen = true;
    }

    // Handle initial edit mode (afterNavigate doesn't run on initial load)
    if ($isCreateMode) {
      if (!$editMode) {
        startEdit();
      }
      return;
    }

    const initialMode = $page.url.searchParams.get('mode');
    const hasPendingChange = checkHasUserPendingChange(entity, currentChangeId, userPendingUpdates, userPendingCreates);
    if (!entity) {
      if ($editMode) {
        cancelEdit();
      }
      return;
    }

    if ((hasPendingChange || initialMode === 'edit') && !$editMode) {
      startEdit();
    }
  });
</script>

<svelte:window bind:innerWidth={windowWidth} bind:innerHeight={windowHeight} />

<div class="wiki-page {pageClass}" class:mobile={isMobile} class:tablet={isTablet} class:sidebar-expanded={sidebarExpanded} class:sidebar-full-width={sidebarFullWidth}>
  <!-- Mobile Navigation Drawer -->
  {#if isMobile}
    <MobileDrawer bind:open={drawerOpen}>
      {#if hasCustomSidebar}
        {@render sidebar?.({ isMobile })}
      {:else}
        <WikiNavigation
          items={navItems}
          filters={navFilters}
          initialFilters={initialFiltersFromUrl}
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
          {@render sidebar?.({ isMobile })}
        {:else}
          <WikiNavigation
            items={navItems}
            filters={navFilters}
            initialFilters={initialFiltersFromUrl}
            {basePath}
            {title}
            currentSlug={entity?.Name}
            currentChangeId={currentChangeId}
            expanded={sidebarExpanded}
            fullWidth={sidebarFullWidth}
            ontoggleexpand={toggleSidebarExpand}
            ontogglefullwidth={toggleSidebarFullWidth}
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
        {#if !sidebarExpanded && !sidebarFullWidth}
          <div class="sidebar-ad">
            <AdSlot adSlot="5222854398" adFormat="auto" />
          </div>
        {/if}
      </aside>
    {/if}

    <!-- Main Content Area -->
    <main class="wiki-content" class:navigating={!!$navigating}>
      <!-- Inline Content Header -->
      <div class="content-header">
        <div class="header-left">
          {#if isMobile}
            <button class="nav-toggle-btn" onclick={toggleDrawer} aria-label="Browse items">
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
          {#if headerActions}
            {@render headerActions()}
          {:else}
            {#if canEdit}
              <div class="create-btn-wrapper">
                <button
                  class="action-btn create"
                  onclick={createCategories ? toggleCreateDropdown : handleCreate}
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
                  <div class="create-dropdown-backdrop" onclick={closeCreateDropdown} onkeydown={(e) => e.key === 'Escape' && closeCreateDropdown()} role="presentation"></div>
                  <div class="create-dropdown" role="menu" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && closeCreateDropdown()}>
                    {#each createCategories as category}
                      <button
                        class="create-dropdown-item"
                        role="menuitem"
                        onclick={() => handleCreateCategory(category)}
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
                <button class="action-btn cancel" onclick={handleCancelEdit} title="Cancel editing">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                  <span>Cancel</span>
                </button>
              {:else}
                <button class="action-btn" onclick={handleEdit} title="Edit">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                  <span>Edit</span>
                </button>
              {/if}
            {:else if editable && (needsAuth || needsVerification) && !$isCreateMode}
              <button class="auth-hint-btn" onclick={openAuthDialog} title="Login required">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <span>{needsAuth ? 'Login to edit' : 'Verify to edit'}</span>
              </button>
            {/if}
          {/if}
        </div>
      </div>

      {#if afterHeader}
        {@render afterHeader()}
      {/if}

      <!-- Main Content Slot -->
      <div class="content-body" class:editing={$editMode}>
        {#if editDepsLoading}
          <div class="edit-deps-loading">
            <div class="edit-deps-spinner"></div>
            <span>Loading editor...</span>
          </div>
        {/if}
        {@render children?.({ entity, user, isMobile, openDrawer })}
      </div>
    </main>
  </div>

  <!-- Edit Action Bar (shown when in edit mode) -->
  {#if $editMode}
    <EditActionBar {onSave} {onSubmit} {basePath} {user} entityName={entity?.Name || ''} onexitedit={clearEditModeUrl} />
  {/if}

  <!-- Auth Help Dialog -->
  {#if showAuthDialog}
    <div class="dialog-overlay" role="presentation" onclick={closeAuthDialog} onkeydown={(e) => e.key === 'Escape' && closeAuthDialog()}>
      <div class="dialog-content" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-modal="true" aria-labelledby="auth-dialog-title">
        <button class="dialog-close" onclick={closeAuthDialog} aria-label="Close">
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
              <button class="dialog-btn secondary" onclick={closeAuthDialog}>Close</button>
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

  .edit-deps-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 2rem;
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .edit-deps-spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
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
    min-height: 0; /* Allow flex to constrain height so content-body can scroll */
    overflow: hidden;
    background-color: var(--secondary-color);
    border-right: 1px solid var(--border-color, #ccc);
    transition: width 0.3s ease, min-width 0.3s ease, max-width 0.3s ease;
  }

  /* SSR safety net: the desktop sidebar is conditionally rendered via the
     JS-gated {#if !isMobile} block. If the server guessed a desktop viewport
     for a user who is actually on mobile, the sidebar would flash in the
     initial SSR paint until hydration swaps to the MobileDrawer. This media
     query forces the sidebar hidden below 900px regardless of SSR state so
     the first paint on a real mobile browser is always clean. */
  @media (max-width: 899px) {
    .wiki-sidebar {
      display: none !important;
    }
  }

  .sidebar-ad {
    flex-shrink: 0;
    padding: 8px;
    max-height: 200px;
    overflow: hidden;
    display: flex;
    justify-content: center;
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

  /* Use media queries (not JS-driven .mobile/.tablet classes) so padding is
     correct on the very first SSR paint and doesn't flicker on hydration. */
  @media (max-width: 1399px) {
    .content-body {
      padding: 16px;
    }
  }

  @media (max-width: 899px) {
    .content-body {
      padding: 12px;
    }
  }

  /* Fade content while navigating to show loading state */
  .wiki-content.navigating .content-body {
    opacity: 0.4;
    pointer-events: none;
  }

  /* Add bottom padding when edit action bar is visible.
     Height is measured at runtime by EditActionBar and exposed as --edit-bar-height. */
  .content-body.editing {
    padding-bottom: calc(var(--edit-bar-height, 60px) + 24px);
  }

  /* Mobile adjustments */
  .wiki-page.mobile .wiki-layout {
    flex-direction: column;
  }

  @media (max-width: 899px) {
    .content-header {
      padding: 10px 12px;
    }
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

  .wiki-page.mobile .content-body.editing {
    /* Stacked action bar on mobile is ~2× taller; same CSS var still applies */
    padding-bottom: calc(var(--edit-bar-height, 120px) + 24px);
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

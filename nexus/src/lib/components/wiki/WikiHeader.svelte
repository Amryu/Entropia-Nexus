<!--
  @component WikiHeader
  Header component with breadcrumbs, title, and action buttons.
  Includes edit/history toggle and mobile navigation trigger.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { editMode, startEdit, cancelEdit, hasChanges } from '$lib/stores/wikiEditState.js';
  import { encodeURIComponentSafe } from '$lib/util';

  const dispatch = createEventDispatcher();

  /** @type {string} Page title */
  export let title = '';

  /** @type {Array} Breadcrumb items [{label, href}, ...] */
  export let breadcrumbs = [];

  /** @type {object|null} Current entity */
  export let entity = null;

  /** @type {object|null} Current user */
  export let user = null;

  /** @type {boolean} Whether editing is allowed */
  export let editable = false;

  /** @type {boolean} Whether we're on mobile */
  export let isMobile = false;

  // Check if user can edit
  $: canEdit = editable && user && user.verified;

  function handleEditClick() {
    if ($editMode) {
      // Already in edit mode, confirm cancel
      if ($hasChanges) {
        if (confirm('You have unsaved changes. Are you sure you want to cancel?')) {
          cancelEdit();
        }
      } else {
        cancelEdit();
      }
    } else {
      startEdit();
    }
  }


  function toggleNav() {
    dispatch('toggleNav');
  }
</script>

<header class="wiki-header" class:mobile={isMobile}>
  <div class="header-left">
    {#if isMobile}
      <button class="nav-toggle" on:click={toggleNav} aria-label="Toggle navigation">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M3 12h18M3 6h18M3 18h18" />
        </svg>
      </button>
    {/if}

    <nav class="breadcrumbs" aria-label="Breadcrumb">
      {#each breadcrumbs as crumb, i}
        {#if i > 0}
          <span class="breadcrumb-separator">/</span>
        {/if}
        {#if crumb.href && i < breadcrumbs.length - 1}
          <a href={crumb.href} class="breadcrumb-link">{crumb.label}</a>
        {:else}
          <span class="breadcrumb-current">{crumb.label}</span>
        {/if}
      {/each}
    </nav>
  </div>

  <div class="header-center">
    <h1 class="header-title">{title || entity?.Name || 'Untitled'}</h1>
  </div>

  <div class="header-actions">
    {#if canEdit}
      <button
        class="action-btn"
        class:active={$editMode}
        on:click={handleEditClick}
        title={$editMode ? 'Cancel editing' : 'Edit this page'}
      >
        {#if $editMode}
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
          <span class="btn-text">Cancel</span>
        {:else}
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
          <span class="btn-text">Edit</span>
        {/if}
      </button>
    {/if}

  </div>
</header>

<style>
  .wiki-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    background-color: var(--secondary-color);
    border-bottom: 1px solid var(--border-color, #ccc);
    min-height: 64px;
    gap: 16px;
  }

  .wiki-header.mobile {
    padding: 8px 12px;
    min-height: 56px;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 0 1 auto;
    min-width: 0;
  }

  .header-center {
    flex: 1;
    text-align: center;
    min-width: 0;
  }

  .header-title {
    font-size: 24px;
    font-weight: 500;
    margin: 0;
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .wiki-header.mobile .header-title {
    font-size: 18px;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 0 0 auto;
  }

  .nav-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    padding: 0;
    background: transparent;
    border: none;
    color: var(--text-color);
    cursor: pointer;
    border-radius: 4px;
  }

  .nav-toggle:hover {
    background-color: var(--hover-color);
  }

  .breadcrumbs {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    color: var(--text-muted, #999);
    overflow: hidden;
  }

  .wiki-header.mobile .breadcrumbs {
    display: none;
  }

  .breadcrumb-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .breadcrumb-link:hover {
    text-decoration: underline;
  }

  .breadcrumb-separator {
    color: var(--text-muted, #999);
  }

  .breadcrumb-current {
    color: var(--text-color);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .action-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    background-color: var(--primary-color);
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
    font-size: 14px;
    cursor: pointer;
    border-radius: 4px;
    transition: background-color 0.15s;
  }

  .action-btn:hover {
    background-color: var(--hover-color);
  }

  .action-btn.active {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .action-btn.active:hover {
    background-color: var(--accent-color-hover, #3a8eef);
  }

  .wiki-header.mobile .btn-text {
    display: none;
  }

  .wiki-header.mobile .action-btn {
    padding: 8px;
  }
</style>

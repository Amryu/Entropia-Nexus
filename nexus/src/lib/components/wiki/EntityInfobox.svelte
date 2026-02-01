<!--
  @component EntityInfobox
  Compact infobox displaying entity icon and key stats.
  Adapts layout for mobile (horizontal) and desktop (vertical/floating).
  In edit mode, clicking the icon opens the image upload dialog.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher, onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { editMode, isCreateMode } from '$lib/stores/wikiEditState.js';
  import ImageUploadDialog from './ImageUploadDialog.svelte';

  const dispatch = createEventDispatcher();

  /** @type {object|null} Entity object */
  export let entity = null;

  /** @type {string} Entity name (fallback if entity is null) */
  export let name = '';

  /** @type {string} Entity type label (e.g., "Melee Weapon") */
  export let type = '';

  /** @type {string} Entity subtype/class (e.g., "Sword") */
  export let subtype = '';

  /** @type {string|null} Image URL */
  export let imageUrl = null;

  /** @type {Array} Key stats to display [{label, value, suffix?}] */
  export let stats = [];

  /** @type {boolean} Whether to show in compact/horizontal mode */
  export let compact = false;

  /** @type {string} Layout variant: 'default', 'floating', 'card' */
  export let variant = 'default';

  /** @type {string} Entity type for uploads (e.g., 'weapon') */
  export let entityType = '';

  /** @type {string|number|null} Entity ID for uploads */
  export let entityId = null;

  /** @type {object|null} Current user session */
  export let user = null;

  // Image upload dialog state
  let showUploadDialog = false;
  let pendingImagePreview = null;
  let imageLoadFailed = false;

  // User's pending image (fetched from server)
  let userPendingImage = null;
  let pendingImageChecked = false;
  let lastCheckedEntityId = null;

  $: displayName = entity?.Name || name;
  $: displayType = entity?.Properties?.Type || type;
  $: displaySubtype = entity?.Properties?.Class || subtype;

  // Can upload only when editing an existing entity (not create mode) and user is verified
  $: canUpload = $editMode && !$isCreateMode && entityId && user?.verified;

  // Reset image load state when imageUrl changes
  $: if (imageUrl) {
    imageLoadFailed = false;
  }

  // Fetch user's pending image when entity changes (if user is logged in)
  $: if (browser && user && entityType && entityId && entityId !== lastCheckedEntityId) {
    lastCheckedEntityId = entityId;
    pendingImageChecked = false;
    userPendingImage = null;
    fetchUserPendingImage();
  }

  async function fetchUserPendingImage() {
    if (!browser || !user || !entityType || !entityId) {
      pendingImageChecked = true;
      return;
    }

    try {
      const response = await fetch(`/api/uploads/pending/${entityType}/${entityId}`);
      if (response.ok) {
        const data = await response.json();
        if (data.hasPending) {
          userPendingImage = data;
        }
      }
    } catch (err) {
      console.error('Failed to check for pending image:', err);
    } finally {
      pendingImageChecked = true;
    }
  }

  // Show image priority: just uploaded preview > user's pending image > approved image > placeholder
  $: displayImageUrl = pendingImagePreview ||
    (userPendingImage?.previewUrl) ||
    (!imageLoadFailed ? imageUrl : null);

  // Show pending overlay for just-uploaded preview OR user's existing pending image
  $: showPendingOverlay = pendingImagePreview || (userPendingImage?.previewUrl && displayImageUrl === userPendingImage.previewUrl);

  function handleIconClick() {
    if (canUpload) {
      showUploadDialog = true;
    }
  }

  function handleImageUploaded(event) {
    const { previewUrl } = event.detail;
    pendingImagePreview = previewUrl;
    userPendingImage = null; // Clear old pending image since we just uploaded a new one
    imageLoadFailed = false;
    dispatch('imageUploaded', event.detail);
  }

  function handleImageError() {
    // Image failed to load (404), show placeholder instead
    imageLoadFailed = true;
  }

  function handleKeydown(event) {
    if (canUpload && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      showUploadDialog = true;
    }
  }
</script>

<div class="entity-infobox" class:compact class:floating={variant === 'floating'} class:card={variant === 'card'}>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class="infobox-icon"
    class:editable={canUpload}
    class:create-mode={$isCreateMode && $editMode}
    on:click={handleIconClick}
    on:keydown={handleKeydown}
    role={canUpload ? 'button' : undefined}
    tabindex={canUpload ? 0 : undefined}
    title={canUpload ? 'Click to upload image' : ($isCreateMode && $editMode ? 'Image upload available after entity is approved' : '')}
  >
    {#if displayImageUrl}
      <img src={displayImageUrl} alt={displayName} class="entity-image" on:error={handleImageError} />
      {#if showPendingOverlay}
        <div class="pending-overlay">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <span>Pending Approval</span>
        </div>
      {/if}
      {#if canUpload}
        <div class="upload-overlay">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <span>Change Image</span>
        </div>
      {/if}
    {:else}
      <div class="icon-placeholder">
        {#if canUpload}
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <span class="upload-hint">Click to upload</span>
        {:else if $isCreateMode && $editMode}
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <path d="M21 15l-5-5L5 21" />
          </svg>
          <span class="create-mode-hint">Available after approval</span>
        {:else}
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <path d="M21 15l-5-5L5 21" />
          </svg>
        {/if}
      </div>
    {/if}
  </div>

  <div class="infobox-content">
    <h2 class="entity-name">{displayName}</h2>

    {#if displayType || displaySubtype}
      <div class="entity-type">
        {#if displayType}
          <span class="type-badge">{displayType}</span>
        {/if}
        {#if displaySubtype}
          <span class="subtype">{displaySubtype}</span>
        {/if}
      </div>
    {/if}

    {#if stats.length > 0}
      <div class="quick-stats">
        {#each stats as stat}
          <div class="stat-item">
            <span class="stat-label">{stat.label}</span>
            <span class="stat-value">
              {stat.value}{#if stat.suffix}<span class="stat-suffix">{stat.suffix}</span>{/if}
            </span>
          </div>
        {/each}
      </div>
    {/if}

    <slot name="extra" />
  </div>
</div>

<ImageUploadDialog
  bind:open={showUploadDialog}
  {entityType}
  {entityId}
  entityName={displayName}
  on:uploaded={handleImageUploaded}
  on:close={() => showUploadDialog = false}
/>

<style>
  .entity-infobox {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
  }

  /* Compact/horizontal layout (for mobile or inline use) */
  .entity-infobox.compact {
    flex-direction: row;
    align-items: flex-start;
    padding: 12px;
    gap: 12px;
  }

  .entity-infobox.compact .infobox-icon {
    flex-shrink: 0;
  }

  .entity-infobox.compact .entity-name {
    font-size: 18px;
  }

  .entity-infobox.compact .quick-stats {
    flex-direction: row;
    flex-wrap: wrap;
    gap: 8px 16px;
  }

  /* Floating variant (Wikipedia-style right sidebar) */
  .entity-infobox.floating {
    float: right;
    width: 280px;
    margin: 0 0 16px 20px;
  }

  /* Card variant (full width, centered content) */
  .entity-infobox.card {
    align-items: center;
    text-align: center;
  }

  .entity-infobox.card .quick-stats {
    justify-content: center;
  }

  .infobox-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
  }

  .infobox-icon.editable {
    cursor: pointer;
  }

  .infobox-icon.editable:hover .upload-overlay,
  .infobox-icon.editable:focus .upload-overlay {
    opacity: 1;
  }

  .infobox-icon.editable:hover .entity-image,
  .infobox-icon.editable:focus .entity-image {
    opacity: 0.7;
  }

  .infobox-icon.editable:hover .icon-placeholder,
  .infobox-icon.editable:focus .icon-placeholder {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .infobox-icon.create-mode {
    cursor: not-allowed;
  }

  .entity-image {
    width: 320px;
    height: 320px;
    object-fit: contain;
    border-radius: 6px;
    background-color: var(--bg-color, var(--primary-color));
    transition: opacity 0.2s;
  }

  .entity-infobox.compact .entity-image {
    width: 80px;
    height: 80px;
  }

  .icon-placeholder {
    width: 320px;
    height: 320px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    background-color: var(--bg-color, var(--primary-color));
    border: 2px dashed var(--border-color);
    border-radius: 6px;
    color: var(--text-muted);
    transition: border-color 0.2s, background-color 0.2s;
  }

  .icon-placeholder .upload-hint,
  .icon-placeholder .create-mode-hint {
    font-size: 13px;
    color: var(--text-muted);
  }

  .entity-infobox.compact .icon-placeholder {
    width: 80px;
    height: 80px;
  }

  .entity-infobox.compact .icon-placeholder svg {
    width: 36px;
    height: 36px;
  }

  .entity-infobox.compact .icon-placeholder .upload-hint,
  .entity-infobox.compact .icon-placeholder .create-mode-hint {
    display: none;
  }

  .upload-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    background-color: rgba(0, 0, 0, 0.6);
    border-radius: 6px;
    color: white;
    opacity: 0;
    transition: opacity 0.2s;
    pointer-events: none;
  }

  .upload-overlay span {
    font-size: 14px;
    font-weight: 500;
  }

  .pending-overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 8px 12px;
    background-color: rgba(255, 165, 0, 0.9);
    border-radius: 0 0 6px 6px;
    color: #1a1a1a;
    font-size: 13px;
    font-weight: 500;
  }

  .pending-overlay svg {
    flex-shrink: 0;
  }

  .infobox-content {
    flex: 1;
    min-width: 0;
  }

  .entity-name {
    font-size: 22px;
    font-weight: 600;
    margin: 0 0 6px 0;
    color: var(--text-color);
    line-height: 1.2;
  }

  .entity-type {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }

  .type-badge {
    display: inline-block;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .subtype {
    font-size: 14px;
    color: var(--text-muted, #999);
  }

  .quick-stats {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
    font-size: 14px;
  }

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    font-weight: 500;
    color: var(--text-color);
  }

  .stat-suffix {
    font-weight: 400;
    color: var(--text-muted, #999);
    margin-left: 2px;
  }

  /* Mobile adjustments - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
    .entity-infobox {
      padding: 12px;
    }

    .entity-infobox.floating {
      float: none;
      width: 100%;
      margin: 0 0 12px 0;
    }

    .entity-name {
      font-size: 20px;
    }

    /* Scale down large icon to fit mobile */
    .entity-image,
    .icon-placeholder {
      width: 100%;
      max-width: 320px;
      height: auto;
      aspect-ratio: 1;
    }

    .entity-infobox.compact .entity-image,
    .entity-infobox.compact .icon-placeholder {
      width: 80px;
      height: 80px;
      max-width: none;
      aspect-ratio: auto;
    }
  }
</style>

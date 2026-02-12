<!--
  @component EntityImageUpload
  Consolidated component for entity image display and upload.
  Handles image checking, pending image display, upload dialog, and all styling.

  Usage:
  <EntityImageUpload
    entityId={entity?.Id}
    entityName={entity?.Name}
    entityType="weapon"
    {user}
    isEditMode={$editMode}
    {isCreateMode}
  />
-->
<script>
  // @ts-nocheck
  import { browser } from '$app/environment';
  import { darkMode } from '../../../stores.js';
  import ImageUploadDialog from './ImageUploadDialog.svelte';

  /** @type {string|number|null} Entity ID */
  export let entityId = null;

  /** @type {string} Entity name for display */
  export let entityName = '';

  /** @type {string} Entity type (e.g., 'weapon', 'armorset', 'mob') */
  export let entityType = '';

  /** @type {object|null} Current user */
  export let user = null;

  /** @type {boolean} Whether edit mode is active */
  export let isEditMode = false;

  /** @type {boolean} Whether this is a new entity being created */
  export let isCreateMode = false;

  // State
  let showUploadDialog = false;
  let pendingImagePreview = null;
  let imageExists = false;
  let imageChecked = false;
  let lastCheckedId = null;

  // User's pending image (fetched from server)
  let userPendingImage = null;
  let pendingImageFetched = false;

  // Can upload when editing existing entity (not create mode) and user is verified
  $: canUploadImage = isEditMode && !isCreateMode && entityId && user?.verified;

  // Check if image exists when entity ID changes (client-side only)
  $: if (browser && entityId && entityId !== lastCheckedId) {
    lastCheckedId = entityId;
    imageExists = false;
    imageChecked = false;
    pendingImagePreview = null;
    userPendingImage = null;
    pendingImageFetched = false;

    // Check image availability using fetch
    // 200 = image exists, 204 = no image (not an error)
    fetch(`/api/img/${entityType}/${entityId}`, { method: 'HEAD' })
      .then(response => {
        imageExists = response.status === 200;
        imageChecked = true;
      })
      .catch(() => {
        imageExists = false;
        imageChecked = true;
      });

    // Also fetch user's pending image if logged in
    if (user) {
      fetchUserPendingImage();
    }
  }

  // Re-fetch pending image when user becomes available (after login)
  $: if (browser && user && entityId && !pendingImageFetched) {
    fetchUserPendingImage();
  }

  // Reset image state in create mode or when no entity is selected
  $: if (browser && (isCreateMode || !entityId)) {
    lastCheckedId = null;
    imageExists = false;
    imageChecked = false;
    pendingImagePreview = null;
    userPendingImage = null;
    pendingImageFetched = false;
  }

  async function fetchUserPendingImage() {
    if (!browser || !user || !entityId) {
      pendingImageFetched = true;
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
      // Silently fail - pending image display is not critical
    } finally {
      pendingImageFetched = true;
    }
  }

  // Image URL: just uploaded preview > user's pending image > approved image (if exists) > none
  $: entityImageUrl = (!isCreateMode && entityId)
    ? (pendingImagePreview ||
      userPendingImage?.previewUrl ||
      (imageChecked && imageExists ? `/api/img/${entityType}/${entityId}?mode=${$darkMode ? 'dark' : 'light'}` : null))
    : null;

  // Show pending overlay for just-uploaded preview OR user's existing pending image
  $: showPendingOverlay = !isCreateMode && (pendingImagePreview || (userPendingImage?.previewUrl && entityImageUrl === userPendingImage.previewUrl));

  function handleIconClick() {
    if (canUploadImage) {
      showUploadDialog = true;
    }
  }

  function handleImageUploaded(event) {
    pendingImagePreview = event.detail.previewUrl;
    userPendingImage = null; // Clear old pending image since we just uploaded a new one
    imageExists = true;
    imageChecked = true;
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
<div
  class="entity-icon-wrapper"
  class:editable={canUploadImage}
  class:create-mode={isCreateMode && isEditMode}
  on:click={handleIconClick}
  role={canUploadImage ? 'button' : undefined}
  tabindex={canUploadImage ? 0 : undefined}
  title={canUploadImage ? 'Click to upload image' : (isCreateMode && isEditMode ? 'Image upload available after entity is approved' : '')}
>
  <!-- Show image if URL is available -->
  {#if entityImageUrl}
    <img src={entityImageUrl} alt={entityName} class="entity-image" />
    {#if showPendingOverlay}
      <div class="pending-overlay">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <span>Pending Approval</span>
      </div>
    {/if}
    {#if canUploadImage}
      <div class="upload-overlay">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        <span>Change</span>
      </div>
    {/if}
  {:else}
    <div class="icon-placeholder">
      {#if canUploadImage}
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        <span class="upload-hint">Click to upload</span>
      {:else if isCreateMode && isEditMode}
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

<!-- Image Upload Dialog -->
<ImageUploadDialog
  bind:open={showUploadDialog}
  {entityType}
  {entityId}
  {entityName}
  on:uploaded={handleImageUploaded}
  on:close={() => showUploadDialog = false}
/>

<style>
  .entity-icon-wrapper {
    position: relative;
    width: 100%;
    aspect-ratio: 1;
    margin-bottom: 12px;
    box-sizing: border-box;
  }

  .entity-icon-wrapper.editable {
    cursor: pointer;
  }

  .entity-icon-wrapper.editable:hover .upload-overlay,
  .entity-icon-wrapper.editable:focus .upload-overlay {
    opacity: 1;
  }

  .entity-icon-wrapper.editable:hover .entity-image,
  .entity-icon-wrapper.editable:focus .entity-image {
    opacity: 0.7;
  }

  .entity-icon-wrapper.editable:hover .icon-placeholder,
  .entity-icon-wrapper.editable:focus .icon-placeholder {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .entity-image {
    width: 100%;
    height: 100%;
    object-fit: contain;
    border-radius: 8px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color);
    transition: opacity 0.2s;
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
    border-radius: 8px;
    color: white;
    opacity: 0;
    transition: opacity 0.2s;
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
    gap: 6px;
    padding: 8px;
    background: linear-gradient(0deg, rgba(245, 158, 11, 0.9) 0%, rgba(245, 158, 11, 0.7) 100%);
    border-radius: 0 0 8px 8px;
    color: white;
    font-size: 12px;
    font-weight: 500;
  }

  .pending-overlay svg {
    flex-shrink: 0;
  }

  .icon-placeholder {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    background-color: var(--bg-color, var(--primary-color));
    border: 2px dashed var(--border-color, #555);
    border-radius: 8px;
    color: var(--text-muted, #999);
    transition: border-color 0.2s, background-color 0.2s;
  }

  .icon-placeholder .upload-hint,
  .icon-placeholder .create-mode-hint {
    font-size: 13px;
    color: var(--text-muted);
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .entity-icon-wrapper {
      max-width: 200px;
      margin: 0 auto 12px;
    }

    .icon-placeholder svg {
      width: 48px;
      height: 48px;
    }
  }
</style>

<!--
  @component ImageUploadDialog
  Dialog for uploading and cropping entity images.
  Uses svelte-easy-crop with configurable aspect ratio.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher, onMount } from 'svelte';
  import { browser } from '$app/environment';
  import Cropper from 'svelte-easy-crop';
  import { addToast } from '$lib/stores/toasts.js';

  const dispatch = createEventDispatcher();

  /** @type {boolean} Whether dialog is open */
  export let open = false;

  /** @type {string} Entity type (e.g., 'weapon') */
  export let entityType = '';

  /** @type {string|number} Entity ID */
  export let entityId = '';

  /** @type {string} Entity name for display */
  export let entityName = '';
  /** @type {boolean} Show delete option (user images) */
  export let showDelete = false;
  /** @type {boolean} Whether entity currently has an image */
  export let hasImage = false;

  /** @type {number} Crop aspect ratio (width/height). Default 1 = square */
  export let aspect = 1;

  /** @type {number} Maximum output width */
  export let maxWidth = 320;

  /** @type {number} Maximum output height */
  export let maxHeight = 320;

  // State
  let fileInput;
  let imageSrc = '';
  let crop = { x: 0, y: 0 };
  let zoom = 1;
  let croppedAreaPixels = null;
  let uploading = false;
  let error = '';
  let step = 'select'; // 'select', 'crop', 'uploading'

  function handleClose() {
    reset();
    dispatch('close');
  }

  function reset() {
    imageSrc = '';
    crop = { x: 0, y: 0 };
    zoom = 1;
    croppedAreaPixels = null;
    error = '';
    step = 'select';
    uploading = false;
  }

  function handleFileSelect(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      error = 'Please select an image file.';
      return;
    }

    // Validate file size (2MB max)
    if (file.size > 2 * 1024 * 1024) {
      error = 'Image must be smaller than 2MB.';
      return;
    }

    error = '';

    // Read file as data URL for cropping
    const reader = new FileReader();
    reader.onload = (e) => {
      imageSrc = e.target.result;
      step = 'crop';
    };
    reader.onerror = () => {
      error = 'Failed to read image file.';
    };
    reader.readAsDataURL(file);
  }

  function handleCropComplete(event) {
    croppedAreaPixels = event.detail.pixels;
  }

  async function handleUpload() {
    if (!croppedAreaPixels || !imageSrc) {
      error = 'Please crop the image first.';
      return;
    }

    uploading = true;
    step = 'uploading';
    error = '';

    try {
      // Create cropped image
      const croppedBlob = await getCroppedImage(imageSrc, croppedAreaPixels);

      // Create form data
      const formData = new FormData();
      formData.append('image', croppedBlob, 'image.webp');
      formData.append('entityType', entityType);
      formData.append('entityId', String(entityId));
      if (entityName) formData.append('entityName', entityName);

      // Upload to server
      const uploadUrl = entityType === 'user'
        ? `/api/image/user/${entityId}`
        : '/api/uploads/entity-image';

      const response = await fetch(uploadUrl, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || `Upload failed: ${response.status}`);
      }

      const result = await response.json().catch(() => ({}));

      dispatch('uploaded', {
        tempPath: result.tempPath,
        previewUrl: result.previewUrl,
        imageUrl: entityType === 'user' ? `/api/image/user/${entityId}` : null
      });

      addToast('Image uploaded — pending approval', { type: 'success' });
      handleClose();
    } catch (err) {
      console.error('Upload error:', err);
      error = err.message || 'Failed to upload image.';
      addToast(error, { type: 'error' });
      step = 'crop';
    } finally {
      uploading = false;
    }
  }

  /**
   * Create a cropped image from the source and crop area.
   * Outputs at max maxWidth x maxHeight, preserving the crop aspect ratio.
   */
  async function getCroppedImage(imageSrc, cropArea) {
    if (!browser) {
      return Promise.reject(new Error('Image cropping only available in browser'));
    }

    return new Promise((resolve, reject) => {
      const image = new Image();
      image.crossOrigin = 'anonymous';

      image.onload = () => {
        const canvas = document.createElement('canvas');

        // Scale down to fit within maxWidth x maxHeight while preserving aspect ratio
        const scaleW = maxWidth / cropArea.width;
        const scaleH = maxHeight / cropArea.height;
        const scale = Math.min(1, scaleW, scaleH);
        const outputWidth = Math.round(cropArea.width * scale);
        const outputHeight = Math.round(cropArea.height * scale);

        canvas.width = outputWidth;
        canvas.height = outputHeight;

        const ctx = canvas.getContext('2d');
        if (!ctx) {
          reject(new Error('Failed to get canvas context'));
          return;
        }

        // Draw the cropped area to the canvas, scaled to output size
        ctx.drawImage(
          image,
          cropArea.x,
          cropArea.y,
          cropArea.width,
          cropArea.height,
          0,
          0,
          outputWidth,
          outputHeight
        );

        // Convert to blob
        canvas.toBlob(
          (blob) => {
            if (blob) {
              resolve(blob);
            } else {
              reject(new Error('Failed to create image blob'));
            }
          },
          'image/webp',
          0.9
        );
      };

      image.onerror = () => {
        reject(new Error('Failed to load image for cropping'));
      };

      image.src = imageSrc;
    });
  }

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget) {
      handleClose();
    }
  }

  function handleKeydown(event) {
    if (event.key === 'Escape') {
      handleClose();
    }
  }

  async function handleDelete() {
    if (!showDelete) return;
    if (!hasImage) return;
    uploading = true;
    error = '';
    try {
      const response = await fetch(`/api/image/user/${entityId}`, { method: 'DELETE' });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || `Delete failed: ${response.status}`);
      }
      dispatch('deleted');
      addToast('Image deleted', { type: 'success' });
      handleClose();
    } catch (err) {
      error = err.message || 'Failed to delete image.';
      addToast(error, { type: 'error' });
    } finally {
      uploading = false;
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <div class="dialog-backdrop" on:click={handleBackdropClick}>
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
      <div class="dialog-header">
        <h2 id="dialog-title">Upload Image</h2>
        <button class="close-btn" on:click={handleClose} aria-label="Close">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="dialog-content">
        {#if step === 'select'}
          <div class="upload-zone">
            <input
              bind:this={fileInput}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              on:change={handleFileSelect}
              class="file-input"
              id="image-upload"
            />
            <label for="image-upload" class="upload-label">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <span class="upload-text">Click to select an image</span>
              <span class="upload-hint">JPEG, PNG, WebP, or GIF (max 2MB)</span>
            </label>
          </div>
        {:else if step === 'crop'}
          <div class="crop-container">
            <Cropper
              image={imageSrc}
              bind:crop
              bind:zoom
              {aspect}
              on:cropcomplete={handleCropComplete}
            />
          </div>
          <div class="zoom-control">
            <label for="zoom-slider">Zoom:</label>
            <input
              id="zoom-slider"
              type="range"
              min="1"
              max="3"
              step="0.1"
              bind:value={zoom}
            />
          </div>
        {:else if step === 'uploading'}
          <div class="uploading-state">
            <div class="spinner"></div>
            <span>Uploading image...</span>
          </div>
        {/if}

        {#if error}
          <div class="error-message">{error}</div>
        {/if}

        {#if entityName}
          <p class="entity-info">Uploading image for: <strong>{entityName}</strong></p>
        {/if}
      </div>

      <div class="dialog-footer">
        {#if step === 'crop'}
          <button class="btn btn-secondary" on:click={() => { step = 'select'; imageSrc = ''; }}>
            Back
          </button>
          <button class="btn btn-primary" on:click={handleUpload} disabled={uploading || !croppedAreaPixels}>
            Upload
          </button>
        {:else if step === 'select'}
          {#if showDelete}
            <button class="btn btn-danger" on:click={handleDelete} disabled={uploading || !hasImage}>
              Delete Image
            </button>
          {/if}
          <button class="btn btn-secondary" on:click={handleClose}>
            Cancel
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-backdrop {
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
  }

  .dialog {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    width: 100%;
    max-width: 500px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color);
  }

  .dialog-header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .close-btn {
    background: none;
    border: none;
    padding: 4px;
    cursor: pointer;
    color: var(--text-muted);
    border-radius: 4px;
  }

  .close-btn:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .dialog-content {
    padding: 20px;
    flex: 1;
    overflow-y: auto;
  }

  .upload-zone {
    border: 2px dashed var(--border-color);
    border-radius: 8px;
    padding: 40px 20px;
    text-align: center;
    transition: border-color 0.2s, background-color 0.2s;
  }

  .upload-zone:hover {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .file-input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
  }

  .upload-label {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    color: var(--text-muted);
  }

  .upload-label svg {
    color: var(--accent-color);
  }

  .upload-text {
    font-size: 16px;
    color: var(--text-color);
  }

  .upload-hint {
    font-size: 13px;
    color: var(--text-muted);
  }

  .crop-container {
    position: relative;
    width: 100%;
    height: 300px;
    background-color: var(--bg-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .zoom-control {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 16px;
    padding: 0 4px;
  }

  .zoom-control label {
    font-size: 14px;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .zoom-control input[type="range"] {
    flex: 1;
    height: 4px;
    background: var(--border-color);
    border-radius: 2px;
    appearance: none;
    cursor: pointer;
  }

  .zoom-control input[type="range"]::-webkit-slider-thumb {
    appearance: none;
    width: 16px;
    height: 16px;
    background: var(--accent-color);
    border-radius: 50%;
    cursor: pointer;
  }

  .uploading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    padding: 40px;
    color: var(--text-muted);
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .error-message {
    margin-top: 16px;
    padding: 0.75rem;
    background: var(--error-bg);
    border: 1px solid var(--error-color);
    border-radius: 4px;
    color: var(--error-color);
    font-size: 0.9rem;
  }

  .entity-info {
    margin-top: 16px;
    font-size: 13px;
    color: var(--text-muted);
    text-align: center;
  }

  .entity-info strong {
    color: var(--text-color);
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 16px 20px;
    border-top: 1px solid var(--border-color);
  }

  .btn {
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    background-color: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .btn-secondary:hover:not(:disabled) {
    background-color: var(--hover-color);
  }

  .btn-primary {
    background-color: var(--accent-color);
    border: 1px solid var(--accent-color);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background-color: var(--accent-color-hover, #3a8eef);
  }

  .btn-danger {
    background-color: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: var(--error-color);
  }

  .btn-danger:hover:not(:disabled) {
    background-color: rgba(239, 68, 68, 0.25);
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .dialog {
      max-height: 85vh;
    }

    .dialog-content {
      padding: 16px;
    }

    .crop-container {
      height: 250px;
    }
  }
</style>
